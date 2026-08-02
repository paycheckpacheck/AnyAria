"""The MOSFET model builder, which had never been executed.

``vdmos.py`` was written against a machine where ngspice was believed
unavailable, so every function in it that simulates anything was written and
never run. The belief was wrong. These tests are what stops it being written
again: they fit a real part and check the fit took.

The second test is the one worth having. It compares this repository's two
independent routes to the same number - a Python model built from the
normalised resistance curve, and an ngspice ``vdmos`` card fitted to the
specification table - at operating points neither was anchored to.
"""

import pytest

from circuit_synth.simulation.ngspice_runner import available

needs_ngspice = pytest.mark.skipif(
    not available(), reason="no ngspice this interpreter can reach"
)


def irf3205_parameters():
    """The IRF3205's datasheet numbers, from PD-94791B.

    Returns:
        The parameters.
    """
    from circuit_synth.simulation.vdmos import VdmosParameters

    return VdmosParameters(
        name="IRF3205",
        vto=3.0,  # VGS(th) 2.0 to 4.0, midpoint
        kp=44.0,  # gfs, minimum
        rds_on=0.008,
        rds_on_vgs=10.0,
        rds_on_id=62.0,
        vds_max=55.0,
        ciss=3247e-12,
        coss=510e-12,
        crss=120e-12,
    )


@needs_ngspice
def test_the_drain_resistance_fit_reproduces_the_datasheet_test_point():
    """The one parameter a datasheet does not give.

    Datasheets quote total on-resistance including the channel, and vdmos wants
    the drain resistance separately, so it is solved for by running the model
    at the datasheet's own test point. If the fit did not take, every number
    downstream is wrong by however much it missed.
    """
    from circuit_synth.simulation.vdmos import fit

    model = fit(irf3205_parameters())

    assert model.measured_rds_on == pytest.approx(0.008, rel=0.01)
    assert 0.0 < model.drain_resistance < 0.008
    assert "vdmos nchan" in model.card


@needs_ngspice
def test_two_independent_routes_to_the_same_on_resistance_agree():
    """One model from the curve, one from the table, compared off their anchors.

    The Python model takes on-resistance as independent of drain current, which
    is not true. This says how untrue: the SPICE model, which does represent the
    dependence, moves by under 1.5% across the whole current range - so the
    approximation costs less than the curve can be read to, and that bound is
    recorded in the model's gaps rather than left as a worry.
    """
    from circuit_synth.simulation.parts import irf3205
    from circuit_synth.simulation.vdmos import fit, measure_rds_on

    model = fit(irf3205_parameters())
    predicted = irf3205.on_resistance(25.0)

    for current in (5.0, 20.0, 80.0):
        simulated = measure_rds_on(model.card, model.name, 10.0, current)
        assert simulated == pytest.approx(predicted, rel=0.02)


def test_the_gap_states_the_measured_bound_rather_than_a_worry():
    """A gap with a number in it tells a reader whether to care."""
    from circuit_synth.simulation.parts import irf3205

    current = next(
        gap for gap in irf3205.gaps() if "independent of drain current" in gap
    )

    assert "-1.4%" in current and "+0.5%" in current
