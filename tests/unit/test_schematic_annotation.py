"""What is written into a .kicad_sch has to be something KiCad will accept.

Two failures are guarded here, and both are quiet.

The first is a malformed file. A hyperlink goes inside ``(effects ...)``; put
it a level up and KiCad refuses the whole sheet with "Failed to load
schematic" and every part on the page disappears. An ``.include "models.lib"``
written into a directive carries quotes of its own, and unescaped they close
the s-expression string early and do the same thing. Neither is visible from
Python - the file looks fine and even parses with a lenient reader.

The second is a value that is right on the drawing and wrong in the
simulation. SPICE reads ``M`` as milli and ``MEG`` as mega, so a resistor
marked ``4M7`` handed to SPICE verbatim comes out a million times too small,
and ``220uF/50V`` does not parse at all. The simulation runs, converges and
reports nothing. So values are parsed here and emitted as plain numbers, and
these tests pin that down.

Where ``kicad-cli`` is installed the round trip is checked against KiCad
itself rather than against our belief about the format.
"""

import subprocess
from pathlib import Path

import pytest

from circuit_synth.simulation.annotate import (
    LINK_SCHEME,
    NOTE_COLOUR,
    Note,
    annotate_schematic,
    clear_notes,
    place_notes,
    symbol_centres,
    text_extent,
)
from circuit_synth.simulation.figures import Basis, BlockAnalysis
from circuit_synth.simulation.probe import (
    RECOGNISED_DIRECTIVES,
    Substitution,
    add_directives,
    apply_assignments,
    write_workbook,
)
from circuit_synth.simulation.spice_models import (
    ModelSpec,
    ValueError_,
    assign_models,
    parse_value,
    passive_assignment,
)

# A minimal sheet with one symbol on it, in the shape circuit-synth writes:
# tab-indented, one placed symbol with a Reference and a Value.
MINIMAL_SHEET = """(kicad_sch
\t(version 20250114)
\t(generator "circuit_synth")
\t(uuid "00000000-0000-0000-0000-000000000001")
\t(paper "A4")
\t(lib_symbols)
\t(symbol
\t\t(lib_id "Device:R")
\t\t(at 100 80 0)
\t\t(unit 1)
\t\t(exclude_from_sim no)
\t\t(uuid "00000000-0000-0000-0000-000000000002")
\t\t(property "Reference" "R1"
\t\t\t(at 102 78 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t)
\t\t)
\t\t(property "Value" "10k"
\t\t\t(at 102 82 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t)
\t\t)
\t)
\t(symbol_instances)
)
"""


@pytest.fixture
def sheet(tmp_path: Path) -> Path:
    """Write a minimal schematic to work on.

    Args:
        tmp_path: pytest's per-test temporary directory.

    Returns:
        Path to the written ``.kicad_sch``.
    """
    path = tmp_path / "Block.kicad_sch"
    path.write_text(MINIMAL_SHEET, encoding="utf-8")
    return path


def kicad_cli() -> str:
    """Locate kicad-cli, or skip the test.

    Returns:
        The path to kicad-cli.
    """
    from circuit_synth.kicad.layout.validate import find_kicad_cli

    cli = find_kicad_cli()
    if not cli:
        pytest.skip("kicad-cli is not installed")
    return cli


def kicad_reads(path: Path) -> bool:
    """Ask KiCad whether it can load a schematic.

    Args:
        path: The ``.kicad_sch`` to try.

    Returns:
        True when KiCad parsed the sheet.
    """
    finished = subprocess.run(
        [
            kicad_cli(),
            "sch",
            "export",
            "netlist",
            "-o",
            str(path.with_suffix(".net")),
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return finished.returncode == 0


class TestValueParsing:
    """A value on a drawing is not a value SPICE can read."""

    @pytest.mark.parametrize(
        "text, expected",
        [
            ("10k", 10_000.0),
            ("100nF", 100e-9),
            ("4k7", 4700.0),
            ("10R", 10.0),
            ("5mR", 0.005),
            ("220uF/50V", 220e-6),
            ("1uF/25V", 1e-6),
            ("15pF", 15e-12),
            ("0.35", 0.35),
            ("2.2u", 2.2e-6),
        ],
    )
    def test_schematic_values_parse(self, text, expected):
        """Every value form the example circuits use reads as a number."""
        assert parse_value(text) == pytest.approx(expected)

    def test_mega_is_mega_not_milli(self):
        """The drafting convention, not SPICE's, is what a drawing means."""
        assert parse_value("4M7") == pytest.approx(4.7e6)

    def test_milli_is_milli(self):
        """A lower-case m is milli, so a 5mR shunt is five milliohms."""
        assert parse_value("5mR") == pytest.approx(0.005)

    @pytest.mark.parametrize("text", ["", "DNP", "see BOM", "abc"])
    def test_an_unreadable_value_raises(self, text):
        """A value nobody can parse is an error, not a default of zero."""
        with pytest.raises(ValueError_):
            parse_value(text)

    def test_params_are_emitted_as_plain_numbers(self):
        """SPICE never sees the suffix, so it cannot misread it."""
        assignment = passive_assignment("R1", "Device:R", "4M7")

        assert assignment.properties["Sim.Params"] == "r=4.7e+06"

    def test_a_shunt_becomes_milliohms_not_millis(self):
        """The value SPICE gets for a 5mR shunt is 0.005, not 5."""
        assignment = passive_assignment("R8", "Device:R_Shunt", "5mR")

        assert assignment.properties["Sim.Params"] == "r=0.005"

    def test_the_value_field_is_bound_to_the_parameters(self):
        """What is drawn and what is simulated cannot drift apart."""
        assignment = passive_assignment("C1", "Device:C", "100nF")

        assert assignment.value_field == "${SIM.PARAMS}"
        assert assignment.properties["Sim.Params"] == "c=1e-07"


class TestModelGaps:
    """A part with no model is reported, never approximated."""

    class FakePart:
        """A stand-in for a circuit-synth Component."""

        def __init__(self, ref: str, symbol: str, value: str):
            """Store the three attributes the assigner reads.

            Args:
                ref: Reference designator.
                symbol: KiCad library id.
                value: Component value.
            """
            self.ref, self.symbol, self.value = ref, symbol, value

    def test_a_part_with_no_model_is_a_gap(self):
        """A gate driver with no SPICE model is reported, not guessed at."""
        parts = [self.FakePart("U4", "Driver_FET:IR2101", "IR2101")]

        assignments, gaps = assign_models(parts)

        assert assignments == []
        assert len(gaps) == 1
        assert "no SPICE model" in gaps[0].reason

    def test_passives_need_no_explicit_model(self):
        """A resistor's model follows from its symbol and value."""
        parts = [self.FakePart("R1", "Device:R", "10k")]

        assignments, gaps = assign_models(parts)

        assert gaps == []
        assert assignments[0].properties["Sim.Device"] == "R"

    def test_an_explicit_spec_covers_a_part(self):
        """A supplied model takes the part out of the gap list."""
        parts = [self.FakePart("Q1", "Transistor_FET:Q_NMOS_GDS", "IRF3205")]
        specs = {"Q1": ModelSpec(device="NMOS", type="VDMOS", pins="1=G 2=D 3=S")}

        assignments, gaps = assign_models(parts, specs)

        assert gaps == []
        assert assignments[0].properties["Sim.Pins"] == "1=G 2=D 3=S"

    def test_an_excluded_part_is_neither_assigned_nor_a_gap(self):
        """A deliberately omitted part is not reported as missing."""
        parts = [self.FakePart("J1", "Connector_Generic:Conn_01x03", "SWD")]

        assignments, gaps = assign_models(parts, excluded={"J1"})

        assert assignments == []
        assert gaps == []

    def test_a_substitution_must_state_its_cost(self):
        """A stand-in that claims to cost nothing does not exist."""
        with pytest.raises(ValueError, match="does not say what it costs"):
            Substitution("U4", "ideal sources", "no model published", limits="")


class TestDirectives:
    """A directive KiCad does not recognise is drawn, not run."""

    def test_an_unrecognised_directive_is_refused(self, sheet: Path):
        """`.foo` would be drawn on the sheet and never executed."""
        with pytest.raises(ValueError, match="not one KiCad's netlister"):
            add_directives(sheet, [".foo 1 2"])

    def test_a_directive_without_a_space_is_refused(self, sheet: Path):
        """KiCad matches the token followed by a space, so this would not run."""
        with pytest.raises(ValueError, match="not one KiCad's netlister"):
            add_directives(sheet, [".tran10n 1m"])

    def test_the_recognised_set_covers_what_an_analysis_needs(self):
        """Everything the skill emits has to be in KiCad's own list."""
        assert {".TRAN", ".INCLUDE", ".MODEL", ".IC", ".OPTIONS"} <= (
            RECOGNISED_DIRECTIVES
        )

    def test_quotes_in_an_include_are_escaped(self, sheet: Path):
        """An unescaped quote closes the string early and breaks the sheet."""
        add_directives(sheet, ['.include "models.lib"', ".tran 1u 1m"])

        text = sheet.read_text(encoding="utf-8")
        assert '\\"models.lib\\"' in text

    def test_directives_share_one_text_element(self, sheet: Path):
        """KiCad reads a multi-line text item, so one element carries them all."""
        add_directives(sheet, [".ic v(out)=0", ".tran 1u 1m"])

        text = sheet.read_text(encoding="utf-8")
        assert text.count("\t(text ") == 1
        assert "\\n" in text


class TestWorkbook:
    """The workbook is what makes the simulator open with a plot."""

    def test_a_workbook_without_traces_is_refused(self, tmp_path: Path):
        """An empty plot reads as a run that found nothing."""
        with pytest.raises(ValueError, match="no traces"):
            write_workbook(tmp_path / "a.wbk", ".tran 1u 1m", [])

    def test_the_project_is_pointed_at_the_workbook(self, tmp_path: Path):
        """KiCad only loads a workbook the project file names."""
        import json

        from circuit_synth.simulation.probe import link_workbook

        project = tmp_path / "Block.kicad_pro"
        project.write_text(json.dumps({"schematic": {}}), encoding="utf-8")
        workbook = tmp_path / "Block.wbk"
        write_workbook(workbook, ".tran 1u 1m", ["V(/OUT)"])

        assert link_workbook(project, workbook)

        stored = json.loads(project.read_text(encoding="utf-8"))
        assert stored["schematic"]["ngspice"]["workbook_filename"] == "Block.wbk"

    def test_a_missing_project_file_is_reported_not_created(self, tmp_path: Path):
        """Inventing a project file would hide a generation that went wrong."""
        from circuit_synth.simulation.probe import link_workbook

        assert not link_workbook(tmp_path / "absent.kicad_pro", tmp_path / "a.wbk")
        assert not (tmp_path / "absent.kicad_pro").exists()

    def test_the_workbook_names_the_analysis_and_the_signals(self, tmp_path: Path):
        """KiCad reads the analysis command and the traces out of this file."""
        import json

        path = tmp_path / "block.wbk"
        write_workbook(path, ".tran 1u 1m", ["V(/PHASE)", "V(/HGATE)"])
        workbook = json.loads(path.read_text(encoding="utf-8"))

        assert workbook["tabs"][0]["analysis"] == "TRAN"
        assert ".tran 1u 1m" in workbook["tabs"][0]["commands"]
        assert [t["signal"] for t in workbook["tabs"][0]["traces"]] == [
            "V(/PHASE)",
            "V(/HGATE)",
        ]


class TestNotePlacement:
    """A note goes on its part, and not on top of other text."""

    def test_a_symbol_centre_is_found(self, sheet: Path):
        """The note is centred on the symbol's own placement origin."""
        assert symbol_centres(sheet) == {"R1": (100.0, 80.0)}

    def test_notes_stack_centred_on_the_part(self):
        """Three figures put one above, one on and one below the centre."""
        analysis = BlockAnalysis(block="B")
        for name in ("Id", "Idrms", "Pcond"):
            analysis.record("R1", name, 1.0, "A", Basis.SIMULATED)

        notes = place_notes(analysis.by_reference()["R1"], (100.0, 80.0))

        assert [n.at[0] for n in notes] == [100.0, 100.0, 100.0]
        assert notes[0].at[1] < 80.0 < notes[2].at[1]
        # Centred: the middle line sits on the part.
        assert notes[1].at[1] == pytest.approx(80.0)

    def test_a_stack_moves_clear_of_existing_text(self):
        """A note must not land on the symbol's reference or value."""
        analysis = BlockAnalysis(block="B")
        analysis.record("R1", "Id", 1.0, "A", Basis.SIMULATED)
        figures = analysis.by_reference()["R1"]

        occupied = [text_extent("R1", (100.0, 80.0), 1.27)]
        notes = place_notes(figures, (100.0, 80.0), occupied)

        assert notes[0].at[1] != pytest.approx(80.0)

    def test_estimated_figures_never_reach_the_sheet(self, sheet: Path):
        """The annotator writes only what has evidence behind it."""
        analysis = BlockAnalysis(block="B")
        analysis.record("R1", "Tj", 120.0, "C", Basis.ESTIMATED)

        assert annotate_schematic(sheet, analysis) == []
        assert "Tj" not in sheet.read_text(encoding="utf-8")

    def test_a_figure_for_an_absent_part_is_skipped(self, sheet: Path):
        """One analysis can be applied across the sheets of a hierarchy."""
        analysis = BlockAnalysis(block="B")
        analysis.record("Q9", "Id", 1.0, "A", Basis.SIMULATED)

        assert annotate_schematic(sheet, analysis) == []

    def test_require_all_turns_an_absent_part_into_an_error(self, sheet: Path):
        """When annotating one block, a missing part is a mistake."""
        analysis = BlockAnalysis(block="B")
        analysis.record("Q9", "Id", 1.0, "A", Basis.SIMULATED)

        with pytest.raises(ValueError, match="no symbol for"):
            annotate_schematic(sheet, analysis, require_all=True)

    def test_re_annotating_replaces_rather_than_accumulates(self, sheet: Path):
        """Running an analysis twice must not double the notes."""
        analysis = BlockAnalysis(block="B")
        analysis.record("R1", "Id", 1.0, "A", Basis.SIMULATED)

        annotate_schematic(sheet, analysis)
        annotate_schematic(sheet, analysis)

        assert sheet.read_text(encoding="utf-8").count("\t(text ") == 1

    def test_clearing_leaves_other_text_alone(self, sheet: Path):
        """Only notes this module wrote are removed."""
        add_directives(sheet, [".tran 1u 1m"])
        analysis = BlockAnalysis(block="B")
        analysis.record("R1", "Id", 1.0, "A", Basis.SIMULATED)
        annotate_schematic(sheet, analysis)

        assert clear_notes(sheet) == 1
        assert ".tran 1u 1m" in sheet.read_text(encoding="utf-8")


class TestNoteRendering:
    """The note has to be red, and the link has to be where KiCad looks."""

    def test_a_note_is_red(self):
        """Red is what distinguishes an analysis note from a design note."""
        rendered = Note("Id = 4.7A", (100.0, 80.0)).render()

        assert (
            f"(color {NOTE_COLOUR[0]} {NOTE_COLOUR[1]} {NOTE_COLOUR[2]} 1)" in rendered
        )

    def test_the_link_sits_inside_effects_not_inside_font(self):
        """Inside font is a parse error and KiCad refuses the whole sheet."""
        rendered = Note(
            "Id = 4.7A", (100.0, 80.0), href="vscode://file/a.py:1"
        ).render()

        effects = rendered.index("(effects")
        font_close = rendered.index(")", rendered.index("(size"))
        href = rendered.index("(href")

        assert effects < href
        assert href > font_close, "href must be a sibling of font, not a child"

    def test_a_note_without_a_source_has_no_href(self):
        """A missing link is written as no link, never as an empty one."""
        assert "(href" not in Note("Id = 4.7A", (100.0, 80.0)).render()

    def test_notes_are_excluded_from_the_simulation(self):
        """An annotation must not be scanned as a SPICE directive."""
        assert "(exclude_from_sim yes)" in Note("Id = 4.7A", (1.0, 1.0)).render()


class TestKicadAcceptsTheOutput:
    """The only opinion that counts is KiCad's."""

    def test_an_annotated_sheet_still_loads(self, sheet: Path):
        """A malformed note makes every part on the page disappear."""
        analysis = BlockAnalysis(block="B")
        analysis.record("R1", "Id", 4.7, "A", Basis.SIMULATED)
        analysis.record("R1", "Pcond", 0.0079, "W", Basis.DERIVED)
        annotate_schematic(sheet, analysis)

        assert kicad_reads(sheet), sheet.read_text(encoding="utf-8")

    def test_a_sheet_with_directives_still_loads(self, sheet: Path):
        """An unescaped quote in an .include breaks the file silently."""
        add_directives(sheet, ['.include "models.lib"', ".tran 1u 1m uic"])

        assert kicad_reads(sheet), sheet.read_text(encoding="utf-8")

    def test_a_sheet_with_sim_properties_still_loads(self, sheet: Path):
        """Properties are injected by text splicing, so this is worth checking."""
        apply_assignments(sheet, [passive_assignment("R1", "Device:R", "10k")])

        assert kicad_reads(sheet), sheet.read_text(encoding="utf-8")

    def test_the_hyperlink_survives_kicads_own_writer(
        self, sheet: Path, tmp_path: Path
    ):
        """KiCad must keep the link when the user saves the file."""
        analysis = BlockAnalysis(block="B")
        analysis.record("R1", "Id", 4.7, "A", Basis.SIMULATED)
        annotate_schematic(sheet, analysis)

        finished = subprocess.run(
            [kicad_cli(), "sch", "upgrade", "--force", str(sheet)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert finished.returncode == 0, finished.stderr

        rewritten = sheet.read_text(encoding="utf-8")
        assert LINK_SCHEME in rewritten, "KiCad dropped the back-link"
        assert "(color 255 0 0 1)" in rewritten, "KiCad dropped the colour"

    def test_the_parts_and_directives_reach_the_spice_netlist(self, tmp_path: Path):
        """A symbol without Sim properties is absent from the deck, silently.

        This one is built through the real generator rather than from the
        fixture above, because KiCad leaves a part with no connections out of
        the netlist regardless of its properties, and that would hide the
        thing being checked.
        """
        from circuit_synth import Component, Net, circuit
        from circuit_synth.simulation.ngspice_run import (
            export_spice_netlist,
            missing_elements,
        )

        kicad_cli()

        @circuit(name="Divider")
        def divider():
            """Two resistors in series, which is enough to have a netlist."""
            top = Net("VIN")
            tap = Net("TAP")
            gnd = Net("GND")
            upper = Component(symbol="Device:R", ref="R", value="10k", footprint="")
            lower = Component(symbol="Device:R", ref="R", value="4k7", footprint="")
            upper[1] += top
            upper[2] += tap
            lower[1] += tap
            lower[2] += gnd

        project = tmp_path / "Divider"
        built = divider()
        built.generate_kicad_project(
            str(project), force_regenerate=True, generate_pcb=False
        )

        root = project / "Divider.kicad_sch"
        assignments = [
            passive_assignment(part.ref, part.symbol, part.value)
            for part in built.components.values()
        ]
        apply_assignments(root, assignments)
        add_directives(root, [".tran 1u 1m"])

        deck = export_spice_netlist(root)

        assert missing_elements(deck, ["R1", "R2"]) == [], deck
        assert ".tran 1u 1m" in deck, "the directive did not reach the deck"
        # 4k7 must arrive as 4700, not as something SPICE reads as 4.7 milli.
        assert "4700" in deck, deck
