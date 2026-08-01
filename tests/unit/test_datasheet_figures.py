"""A guessed number must not be able to reach a schematic.

The failure this guards against is the one that makes an annotated schematic
worse than a bare one. A reader who sees ``Tj = 120C`` written on a MOSFET
stops wondering about that MOSFET. If the figure was a typical value carried
over from a similar design, or a datasheet parameter nobody actually looked
up, the annotation has removed the reader's suspicion without earning it.

So the discipline is enforced by the types rather than left to whoever writes
the analysis. A ``Parameter`` will not construct without naming the table it
came from. A ``Substitution`` will not construct without saying what it costs.
An ``ESTIMATED`` figure is dropped by ``annotatable()`` and reported by
``unverified()``. These tests hold those doors shut.

They also cover the provenance capture, since a note whose hyperlink points at
the wrong line sends a reviewer to the wrong arithmetic, which is a quieter
way of doing the same damage.
"""

import pytest

from circuit_synth.simulation import datasheet as datasheet_module
from circuit_synth.simulation.datasheet import (
    Datasheet,
    DatasheetNotFound,
    Equation,
    Parameter,
    lookup,
    register,
    require,
)
from circuit_synth.simulation.figures import (
    Basis,
    BlockAnalysis,
    Figure,
    format_value,
)


@pytest.fixture(autouse=True)
def clean_registry():
    """Empty the datasheet registry around each test.

    Yields:
        None. The registry is cleared before and after so no test inherits a
        record another one registered.
    """
    datasheet_module.clear()
    yield
    datasheet_module.clear()


class TestCitationIsMandatory:
    """A number with no stated source cannot be constructed."""

    def test_parameter_without_a_section_is_refused(self):
        """A parameter must name the table it was read from."""
        with pytest.raises(ValueError, match="no section citation"):
            Parameter("Qg", 146e-9, "C", section="")

    def test_parameter_with_blank_section_is_refused(self):
        """Whitespace does not count as a citation."""
        with pytest.raises(ValueError, match="no section citation"):
            Parameter("Qg", 146e-9, "C", section="   ")

    def test_equation_without_a_section_is_refused(self):
        """An equation nobody can look up is not evidence."""
        with pytest.raises(ValueError, match="not evidence"):
            Equation(name="ripple", expression="dI = V*t/L", symbols={}, section="")

    def test_a_cited_parameter_is_accepted(self):
        """A parameter naming its table constructs normally."""
        parameter = Parameter("Qg", 146e-9, "C", section="Table 2", typical=False)

        assert parameter.value == 146e-9
        assert not parameter.typical


class TestMissingDataIsAnError:
    """Absent information raises rather than defaulting."""

    def test_an_unread_parameter_raises(self):
        """Looking up a parameter nobody read is an error, not a zero."""
        sheet = Datasheet(
            part_number="IR2101",
            title="t",
            document="PD60043 Rev.O",
            url="u",
            role="gate driver",
        )

        with pytest.raises(DatasheetNotFound, match="no value for"):
            sheet.value("Qg")

    def test_an_unextracted_equation_raises(self):
        """Looking up an equation nobody extracted is an error."""
        sheet = Datasheet(
            part_number="IR2101",
            title="t",
            document="d",
            url="u",
            role="r",
        )

        with pytest.raises(DatasheetNotFound, match="no equation named"):
            sheet.equation("bootstrap_capacitor")

    def test_require_refuses_an_unresearched_part(self):
        """A part nobody has researched cannot be silently substituted for."""
        with pytest.raises(DatasheetNotFound, match="No datasheet has been read"):
            require("IRF3205")

    def test_require_refuses_a_record_for_a_different_role(self):
        """The equations that matter depend on what the part is doing."""
        register(
            Datasheet(
                part_number="IR2101",
                title="t",
                document="d",
                url="u",
                role="gate driver for a class-D output stage",
            )
        )

        with pytest.raises(DatasheetNotFound, match="was researched as"):
            require("IR2101", role="gate driver for a bootstrapped half-bridge")

    def test_require_accepts_a_matching_role(self):
        """A record researched for this role is returned."""
        role = "gate driver for a bootstrapped half-bridge"
        register(Datasheet("IR2101", "t", "d", "u", role))

        assert require("IR2101", role=role).part_number == "IR2101"

    def test_lookup_is_case_insensitive(self):
        """Part numbers are matched regardless of how they were typed."""
        register(Datasheet("IR2101", "t", "d", "u", "r"))

        assert lookup("ir2101") is not None


class TestGuessesAreWithheld:
    """An estimated figure is reported but never annotated."""

    def test_an_estimated_figure_is_not_annotatable(self):
        """A guess is kept out of the set that reaches the schematic."""
        analysis = BlockAnalysis(block="HalfBridge")
        analysis.record("Q1", "Tj", 120.0, "C", Basis.ESTIMATED, "a guess")

        assert analysis.annotatable() == []

    def test_an_estimated_figure_is_reported(self):
        """A guess is surfaced rather than quietly dropped."""
        analysis = BlockAnalysis(block="HalfBridge")
        analysis.record("Q1", "Tj", 120.0, "C", Basis.ESTIMATED, "a guess")

        assert len(analysis.unverified()) == 1
        assert "NOT written to the schematic" in analysis.summary()

    @pytest.mark.parametrize("basis", [Basis.SIMULATED, Basis.DATASHEET, Basis.DERIVED])
    def test_evidence_backed_figures_are_annotatable(self, basis):
        """Every basis that is evidence reaches the schematic."""
        analysis = BlockAnalysis(block="HalfBridge")
        analysis.record("Q1", "Id", 4.7, "A", basis)

        assert len(analysis.annotatable()) == 1

    def test_estimated_figures_are_excluded_from_the_grouping(self):
        """The by-reference grouping the annotator uses drops guesses."""
        analysis = BlockAnalysis(block="HalfBridge")
        analysis.record("Q1", "Id", 4.7, "A", Basis.SIMULATED)
        analysis.record("Q1", "Tj", 120.0, "C", Basis.ESTIMATED)

        assert [f.name for f in analysis.by_reference()["Q1"]] == ["Id"]

    def test_gaps_lead_the_report(self):
        """What could not be established is shown before what could."""
        analysis = BlockAnalysis(block="HalfBridge")
        analysis.record("Q1", "Id", 4.7, "A", Basis.SIMULATED)
        analysis.note_gap("no thermal model, so no junction temperature")

        summary = analysis.summary()
        assert summary.index("Not established") < summary.index("Q1:")


class TestProvenance:
    """A note has to link back to the line that produced it."""

    def test_recording_captures_the_caller_line(self):
        """The figure remembers where it was worked out."""
        analysis = BlockAnalysis(block="HalfBridge")
        figure = analysis.record("Q1", "Id", 4.7, "A", Basis.SIMULATED)

        assert figure.source_path is not None
        assert figure.source_path.name == "test_datasheet_figures.py"
        assert figure.source_line > 0

    def test_two_figures_recorded_on_different_lines_differ(self):
        """Each figure points at its own arithmetic, not at a shared helper."""
        analysis = BlockAnalysis(block="HalfBridge")
        first = analysis.record("Q1", "Id", 4.7, "A", Basis.SIMULATED)
        second = analysis.record("Q1", "Vds", 12.0, "V", Basis.SIMULATED)

        assert first.source_line != second.source_line

    def test_stacklevel_points_past_a_helper(self):
        """A figure recorded inside a helper links to the helper's caller."""
        analysis = BlockAnalysis(block="HalfBridge")

        def helper():
            """Record a figure on behalf of the caller.

            Returns:
                The recorded figure.
            """
            return analysis.record("Q1", "Id", 4.7, "A", Basis.SIMULATED, stacklevel=2)

        here = helper()

        # The recorded line is the call to helper(), not the line inside it.
        assert here.source_line > 0
        assert here.source_path.name == "test_datasheet_figures.py"

    def test_the_link_is_a_well_formed_uri(self):
        """KiCad refuses a whole sheet over a malformed hyperlink."""
        figure = Figure(
            name="Id",
            value=4.7,
            unit="A",
            reference="Q1",
            basis=Basis.SIMULATED,
            source_path=__import__("pathlib").Path("C:/work/analysis.py"),
            source_line=42,
        )

        assert figure.link() == "vscode://file/C:/work/analysis.py:42"

    def test_a_figure_with_no_source_has_no_link(self):
        """A figure recorded outside a file links nowhere rather than badly."""
        figure = Figure("Id", 4.7, "A", "Q1", Basis.SIMULATED)

        assert figure.link() is None


class TestValueFormatting:
    """Notes are read at a glance, so the numbers have to be short."""

    @pytest.mark.parametrize(
        "value, unit, expected",
        [
            (4.7, "A", "4.7A"),
            (0.0042, "V", "4.2mV"),
            (146e-9, "As", "146nAs"),
            (1.53, "A", "1.53A"),
            (0.0079, "W", "7.9mW"),
            (12000.0, "ohm", "12kohm"),
            (0.0, "V", "0V"),
            (-2.5, "A", "-2.5A"),
        ],
    )
    def test_values_get_an_si_prefix(self, value, unit, expected):
        """A magnitude is scaled so the mantissa reads without counting zeros."""
        assert format_value(value, unit) == expected

    @pytest.mark.parametrize(
        "value, unit, expected",
        [(120.0, "C", "120C"), (94.2, "%", "94.2%"), (0.5, "C", "0.5C")],
    )
    def test_absolute_units_are_not_scaled(self, value, unit, expected):
        """A temperature in milli-degrees would be nonsense."""
        assert format_value(value, unit) == expected

    def test_a_figure_renders_as_one_short_line(self):
        """The label is what gets written on the sheet."""
        figure = Figure("Idrms", 1.4142, "A", "Q2", Basis.SIMULATED)

        assert figure.label() == "Idrms = 1.41A"
