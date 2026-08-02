"""A behavioural model is a claim, and a claim nobody checked is a guess.

Two things are checked here. The validation machinery itself - that it can tell
an in-sample point from an out-of-sample one, since a model checked only
against its own inputs has been checked for arithmetic and nothing else. And
the TPS7A49 model, against the values TI publishes for the real part.

The TPS7A49 is the worked example because TI publishes enough to *check* a
model rather than only to build one: a specification table, a full set of
typical-characteristic curves, and an integrated output noise figure that
nothing in the rejection curve implies.
"""

import pytest

from circuit_synth.simulation.parts import tps7a49
from circuit_synth.simulation.validation import ReferencePoint, validate


def test_a_reference_point_must_say_where_it_came_from():
    """A number nobody can look up is not evidence a model is right."""
    with pytest.raises(ValueError, match="no source"):
        ReferencePoint(quantity="gain", expected=1.0, unit="", source="  ")


def test_a_report_of_only_in_sample_points_says_so():
    """Reproducing your own inputs is arithmetic, not validation."""
    point = ReferencePoint(
        quantity="x", expected=1.0, unit="", source="doc", in_sample=True
    )
    report = validate("PART", {"x": 1.0}, [point])

    assert report.passed
    assert "checks the arithmetic and not the model" in report.summary()


def test_a_missing_prediction_is_a_gap_not_a_pass():
    """A model that does not predict a published behaviour has a gap."""
    point = ReferencePoint(quantity="noise", expected=1e-6, unit=" V", source="doc")
    report = validate("PART", {}, [point])

    assert report.missing == ["noise"]
    assert "the model does not predict this" in report.summary()


def test_a_limit_is_satisfied_by_staying_inside_it():
    """A part drawing less than its maximum has not failed to match."""
    point = ReferencePoint(
        quantity="Iq", expected=100e-6, unit=" A", source="doc", limit=True
    )

    assert validate("PART", {"Iq": 49e-6}, [point]).passed
    assert not validate("PART", {"Iq": 150e-6}, [point]).passed


def test_the_ldo_matches_its_datasheet():
    """Every published value, within the tolerance claimed for it."""
    report = tps7a49.check()

    assert report.passed, report.summary()


def test_most_of_the_ldo_check_is_out_of_sample():
    """Otherwise the check is of the arithmetic rather than of the model."""
    report = tps7a49.check()

    assert len(report.out_of_sample) >= 4


def test_the_ldo_predicts_a_noise_figure_it_was_not_given():
    """The strongest test available: a behaviour from a different mechanism.

    The model is built from the rejection curve and the regulation specs. The
    output noise comes from the reference's noise density and the NR/SS corner,
    which nothing in those implies. A model that could only reproduce its own
    inputs would fail here.
    """
    predicted = tps7a49.predict_output_noise()

    assert predicted == pytest.approx(tps7a49.PUBLISHED_NOISE_RMS, rel=0.25)


def test_dropout_is_not_a_straight_line_through_the_origin():
    """The pass element has an offset, and ignoring it is 17% wrong at 150 mA.

    That size of error looks like measurement scatter and is not, which is
    exactly why the model is fitted to the curve rather than anchored to one
    table value.
    """
    naive = (tps7a49.DROPOUT_AT_100MA / 0.100) * 0.150
    fitted = tps7a49.predict_dropout(0.150)

    assert abs(naive - tps7a49.DROPOUT_AT_150MA) / tps7a49.DROPOUT_AT_150MA > 0.15
    assert abs(fitted - tps7a49.DROPOUT_AT_150MA) / tps7a49.DROPOUT_AT_150MA < 0.05


def test_the_dropout_fit_excludes_the_points_it_is_judged_against():
    """Build from the figure, judge with the table, never both."""
    assert 0.100 not in tps7a49.DROPOUT_CURVE
    assert 0.150 not in tps7a49.DROPOUT_CURVE


def test_the_rejection_curve_keeps_its_loop_features():
    """The dip and peak near crossover are where a switching supply puts ripple.

    A monotonic curve would be a tidier graph and would mispredict exactly the
    frequencies anybody builds an LDO to reject.
    """
    regulator = tps7a49.model()
    at_10k = regulator.rejection_at(10_000)
    at_100k = regulator.rejection_at(100_000)
    at_200k = regulator.rejection_at(200_000)

    assert at_100k < at_10k - 10  # the dip is real and large
    assert at_200k > at_100k  # and it recovers before rolling off


def test_the_model_carries_its_document_and_revision():
    """Datasheets disagree with themselves across revisions."""
    provenance = tps7a49.model().provenance()

    assert "SBVS121E" in provenance
    assert "not modelled" in provenance


def test_the_opamp_matches_its_datasheet():
    """Four published settling times, none of which the model was given.

    The model is built from gain-bandwidth, slew rate, phase margin and
    open-loop gain. Settling time follows from all four at once, so matching it
    cannot be arithmetic.
    """
    from circuit_synth.simulation.parts import tl072

    report = tl072.check()

    assert report.passed, report.summary()
    assert len(report.out_of_sample) == 4


def test_the_opamp_model_has_no_fitted_parameters():
    """Every number comes from the table; nothing was tuned to make it match."""
    from circuit_synth.simulation.parts import tl072

    amplifier = tl072.model()

    assert amplifier.gain_bandwidth == tl072.GAIN_BANDWIDTH
    assert amplifier.slew_rate == tl072.SLEW_RATE
    assert amplifier.phase_margin == tl072.PHASE_MARGIN


def test_damping_is_solved_rather_than_approximated():
    """The rule of thumb zeta = PM/100 drifts badly below 60 degrees.

    At 56 degrees it would give 0.56; the exact relation gives 0.554, and the
    settling time is sensitive enough to the difference to be worth solving.
    """
    from circuit_synth.simulation.parts import tl072

    assert tl072.model().damping == pytest.approx(0.554, abs=0.005)


def test_a_slower_amplifier_settles_more_slowly():
    """A sanity check that the model responds to its inputs at all."""
    from circuit_synth.simulation.parts import tl072

    fast = tl072.model().settling_time(2.0, 1e-3)
    slow = tl072.model(closed_loop_gain=10.0).settling_time(2.0, 1e-3)

    assert slow > fast


def test_the_datasheet_contradiction_is_recorded():
    """A tighter tolerance cannot be reached sooner than a looser one.

    The published 2V settling times say otherwise, so one of them is wrong. The
    model is not fitted to either, and the contradiction is written down rather
    than smoothed over - fitting a model to an impossibility makes it worse
    everywhere else.
    """
    from circuit_synth.simulation.parts import tl072

    tighter = tl072.SETTLING[(2.0, 1e-4)]
    looser = tl072.SETTLING[(2.0, 1e-3)]

    assert tighter < looser  # the contradiction, as published
    assert "cannot enter the tighter band" in tl072.inconsistency()


def test_the_buck_converter_matches_both_published_curves():
    """Efficiency across the load range, at two switching frequencies."""
    from circuit_synth.simulation.parts import tps62130

    report = tps62130.check()

    assert report.passed, report.summary()


def test_the_fitted_switching_term_predicts_a_frequency_it_was_not_fitted_to():
    """The test that separates a model from a curve fit.

    Gate charge and switching times are not published for an integrated
    converter, so one coefficient has to be fitted. Fitted at 2.5MHz, it is
    then asked for the 1.25MHz curve: if it stands for energy lost per cycle it
    must halve and the curve must follow, and if it stands for the shape of one
    graph it will not.
    """
    from circuit_synth.simulation.parts import tps62130

    out_of_sample = [c for c in tps62130.check().comparisons if not c.point.in_sample]

    assert len(out_of_sample) == 4
    assert all("1.25MHz" in c.point.quantity for c in out_of_sample)
    # The curve reads to about 1.5 points, so this is the source's accuracy.
    assert max(c.error for c in out_of_sample) < 0.02


def test_the_model_says_where_it_stops_applying():
    """Below continuous conduction the switching frequency is not the nominal one.

    Modelling power-save mode as if it ran at the labelled frequency would give
    confident numbers for a circuit that is not the one being described.
    """
    from circuit_synth.simulation.parts import tps62130

    floor = tps62130.continuous_conduction_floor()

    assert 0.2 < floor < 0.4
    assert all(current >= floor for current in tps62130.EFFICIENCY_2M5)


def test_the_unsourceable_parameter_is_declared():
    """A fitted coefficient must say it was fitted, and why it had to be."""
    from circuit_synth.simulation.parts import tps62130

    assert any("fitted" in gap for gap in tps62130.gaps())
    assert any("not published" in gap for gap in tps62130.gaps())


def test_the_mosfet_matches_the_ratings_on_its_own_front_page():
    """Four ratings, none of which the model was built from.

    The model is built from the normalised resistance curve, the 25C
    on-resistance and the thermal resistances. The dissipation limit, the
    derating factor and the two continuous current ratings are all
    consequences of the temperature loop rather than inputs to it.
    """
    from circuit_synth.simulation.parts import irf3205

    report = irf3205.check()

    assert report.passed, report.summary()
    assert len(report.out_of_sample) == 4


def test_on_resistance_more_than_doubles_over_the_rated_range():
    """The mechanism every earlier model here declared it did not have.

    A part sized on its 25C resistance is undersized by this factor, which is
    what makes the loop worth solving rather than approximating.
    """
    from circuit_synth.simulation.parts import irf3205

    cold = irf3205.on_resistance(25.0)
    hot = irf3205.on_resistance(175.0)

    assert hot / cold == pytest.approx(2.2, abs=0.05)


def test_the_junction_temperature_is_solved_not_calculated():
    """Dissipation depends on the temperature it produces.

    Using the 25C resistance would understate the temperature rise, and the
    gap grows with current - which is the whole point of solving for a fixed
    point instead of evaluating a formula once.
    """
    from circuit_synth.simulation.parts import irf3205

    solved = irf3205.junction_temperature(80.0, 25.0, irf3205.RTH_JC)
    naive_rise = 80.0**2 * irf3205.RDS_ON_25 * irf3205.RTH_JC

    assert solved.converged
    assert solved.junction_temperature > 25.0 + naive_rise
    # And the temperature it settled at is the one that reproduces itself.
    implied = 25.0 + solved.dissipation * irf3205.RTH_JC
    assert implied == pytest.approx(solved.junction_temperature, abs=0.5)


def test_thermal_runaway_is_a_result_and_not_an_error():
    """Above some current no temperature reproduces itself.

    The device heats faster than the path carries heat away at every
    temperature the datasheet describes. Returning a number anyway - or
    raising - would both be wrong; the finding is that there is no operating
    point.
    """
    from circuit_synth.simulation.parts import irf3205

    survives = irf3205.junction_temperature(10.0, 25.0, irf3205.RTH_JA)
    runs_away = irf3205.junction_temperature(15.0, 25.0, irf3205.RTH_JA)

    assert survives.converged and survives.within_rating
    assert not runs_away.converged
    assert "no stable junction temperature" in runs_away.note


def test_the_headline_current_needs_a_case_held_at_25c():
    """110A is at TC = 25C, which is an infinite heatsink.

    The same part in free air carries about a tenth of that. This is the
    number a design actually needs and the one the front page does not give.
    """
    from circuit_synth.simulation.parts import irf3205

    on_a_cold_case = irf3205.max_continuous_current(25.0, irf3205.RTH_JC)
    in_free_air = irf3205.max_continuous_current(25.0, irf3205.RTH_JA)

    assert on_a_cold_case > 100.0
    assert in_free_air < 13.0


def test_the_model_refuses_to_extrapolate_past_its_curve():
    """The curve is the only source for the coefficient.

    Past its ends there is nothing in the document to extrapolate from, and a
    silently extrapolated number would look exactly like a measured one.
    """
    from circuit_synth.simulation.parts import irf3205

    with pytest.raises(ValueError, match="outside Figure 4"):
        irf3205.on_resistance(200.0)


def test_the_published_current_ratings_contradict_each_other():
    """Their ratio is fixed by thermal headroom alone and has no freedom.

    sqrt((175-25)/(175-100)) is sqrt(2); the published 110/80 is 1.375. No
    single on-resistance reproduces both, so the model is fitted to neither.
    """
    from circuit_synth.simulation.parts import irf3205

    published_ratio = irf3205.ID_AT_25C / irf3205.ID_AT_100C
    required_ratio = 2.0**0.5

    assert abs(published_ratio - required_ratio) / required_ratio > 0.02
    assert "sqrt(2)" in irf3205.rating_inconsistency()


def test_an_order_code_finds_the_model_for_its_part():
    """A block holds an order code, not the family name the model is filed under.

    Nothing else in the flow would notice a simulator rebuilding a model that
    already exists, and two hand-built models of the same part give two
    different answers for one design.
    """
    from circuit_synth.simulation.parts import find

    match = find("TPS7A4901DGNR")

    assert match is not None
    assert match.model.validated_part == "TPS7A4901"
    assert match.exact
    assert match.caveat() is None


def test_a_family_member_matches_but_says_it_is_not_the_same_part():
    """Prefix matching is what makes this useful and how it gets a wrong answer.

    A TPS62133 is the TPS62130's silicon with a different feedback arrangement,
    so the mechanisms carry across and the numbers must be re-read. Returning
    it silently as a match would put an unchecked number in a report.
    """
    from circuit_synth.simulation.parts import find

    match = find("TPS62133RGTR")

    assert match is not None
    assert not match.exact
    assert "is not TPS62130" in match.caveat()
    assert "SLVSAG7F" in match.caveat()


def test_a_package_variant_is_not_the_validated_device():
    """A letter that changes the package is not a reel suffix.

    IRF3205S is the same die in a D2PAK. Every electrical number carries over
    and the thermal ones do not - which for a model whose subject is the
    thermal path is the entire question, so it must not come back exact.
    """
    from circuit_synth.simulation.parts import find

    assert find("IRF3205PBF").exact  # lead-free, same TO-220
    assert not find("IRF3205SPBF").exact  # D2PAK
    assert not find("IRF3205LPBF").exact  # TO-262


def test_a_part_nobody_has_modelled_returns_nothing():
    """Better an honest gap than the nearest model in the catalogue."""
    from circuit_synth.simulation.parts import find

    assert find("LM317T") is None
    assert find("") is None


def test_every_registered_model_still_matches_its_datasheet():
    """The check that stops a model rotting quietly.

    Each model passed when it was written. This is what notices when one stops
    passing - a refactor, a constant edited to make some other number work, or
    a datasheet revision nobody read.
    """
    from circuit_synth.simulation.parts import check_all

    reports = check_all()

    assert reports
    for prefix, report in reports.items():
        assert report.passed, f"{prefix}: {report.summary()}"


def test_every_registered_model_says_what_it_does_not_cover():
    """A model with no stated gaps is claiming to be the part."""
    from circuit_synth.simulation.parts import REGISTRY

    for prefix, model in REGISTRY.items():
        assert model.gaps(), f"{prefix} declares no gaps"
        assert model.document, f"{prefix} cites no document"


def test_the_catalogue_flags_a_fitted_model_as_fitted():
    """An agent choosing whether to trust a model needs that on the same page."""
    from circuit_synth.simulation.parts import catalogue

    text = catalogue()

    assert "TPS62130" in text
    assert "one coefficient was fitted" in text
    assert "out of sample" in text
