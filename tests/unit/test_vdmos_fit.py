"""A model built from a datasheet has to be checked against that datasheet.

When a manufacturer publishes no SPICE model, the choice is between not
simulating and building one. A built model is only worth anything if it is
fitted to the datasheet's own numbers and then measured back out, because the
failure mode otherwise is silent: the simulation converges, the waveforms look
like a switching circuit, and the on-resistance is off by half.

These tests hold two things. That ``fit`` reproduces the datasheet's
on-resistance at the datasheet's own test point, and that a set of parameters
which cannot reproduce it raises instead of returning a model that nearly
works. The IRF3205's published numbers are used as the worked case, since
that is the part the example analyses.

Everything here needs ngspice, which KiCad ships. The tests skip rather than
fail where it cannot be loaded - on a machine whose Python and KiCad are built
for different architectures, for instance.
"""

import pytest

from circuit_synth.simulation.ngspice_run import (
    SimulationFailed,
    SimulationUnavailable,
    find_ngspice_library,
)
from circuit_synth.simulation.vdmos import (
    VdmosParameters,
    build_card,
    fit,
    measure_rds_on,
)

# IRF3205PbF, datasheet PD-94791B. On-resistance is a maximum at VGS = 10V and
# ID = 62A; the threshold is the midpoint of the published 2.0V to 4.0V band;
# gfs and the capacitances are as published.
IRF3205 = VdmosParameters(
    name="IRF3205",
    vto=3.0,
    kp=44.0,
    rds_on=0.008,
    rds_on_vgs=10.0,
    rds_on_id=62.0,
    vds_max=55.0,
    ciss=3247e-12,
    coss=781e-12,
    crss=211e-12,
)


@pytest.fixture(scope="module")
def ngspice():
    """Skip the module when ngspice cannot be loaded.

    Yields:
        The path to the ngspice shared library.
    """
    library = find_ngspice_library()
    if library is None:
        pytest.skip("ngspice was not found; KiCad ships it")

    try:
        measure_rds_on(build_card(IRF3205, 0.002), IRF3205.name, 10.0, 62.0)
    except (SimulationUnavailable, SimulationFailed) as error:
        pytest.skip(f"ngspice could not be run: {error}")

    yield library


class TestCapacitanceDerivation:
    """Datasheet capacitances are not the model's capacitances."""

    def test_gate_source_capacitance_is_ciss_less_crss(self):
        """Datasheets publish Ciss = Cgs + Cgd, so Cgs is the difference."""
        assert IRF3205.cgs == pytest.approx(3247e-12 - 211e-12)

    def test_drain_source_capacitance_is_coss_less_crss(self):
        """Datasheets publish Coss = Cds + Cgd, so Cds is the difference."""
        assert IRF3205.cjo == pytest.approx(781e-12 - 211e-12)

    def test_the_card_carries_the_datasheet_breakdown_voltage(self):
        """A model that does not know its own rating cannot warn about it."""
        assert "Vds=55" in build_card(IRF3205, 0.002)

    def test_the_card_names_the_part(self):
        """The model name is what Sim.Name on the symbol has to match."""
        assert build_card(IRF3205, 0.002).startswith(".model IRF3205 vdmos nchan")


class TestFitReproducesTheDatasheet:
    """The one number the model is fitted to has to come back out."""

    def test_the_fitted_model_matches_the_published_on_resistance(self, ngspice):
        """8.0 mOhm at VGS = 10V and ID = 62A, as PD-94791B states it."""
        model = fit(IRF3205)

        assert model.measured_rds_on == pytest.approx(0.008, rel=0.01)
        assert model.error < 0.01

    def test_the_fit_reports_what_it_does_not_cover(self, ngspice):
        """A model right about conduction and vague about switching says so."""
        model = fit(IRF3205)

        assert "Switching is approximate" in model.limits
        assert "No temperature dependence" in model.limits

    def test_an_unfittable_part_raises(self, ngspice):
        """A channel already above the quoted total cannot be made to fit."""
        # A threshold just under the gate drive leaves the channel barely
        # enhanced, so its resistance alone far exceeds 8 milliohms.
        impossible = VdmosParameters(
            name="IMPOSSIBLE",
            vto=9.9,
            kp=0.01,
            rds_on=0.008,
            rds_on_vgs=10.0,
            rds_on_id=62.0,
            vds_max=55.0,
            ciss=3247e-12,
            coss=781e-12,
            crss=211e-12,
        )

        with pytest.raises(ValueError, match="channel alone"):
            fit(impossible)

    def test_a_higher_drain_resistance_gives_a_higher_on_resistance(self, ngspice):
        """The quantity being bisected has to be monotonic for the fit to work."""
        low = measure_rds_on(build_card(IRF3205, 0.001), "IRF3205", 10.0, 62.0)
        high = measure_rds_on(build_card(IRF3205, 0.005), "IRF3205", 10.0, 62.0)

        assert high > low
