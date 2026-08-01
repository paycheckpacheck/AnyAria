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
