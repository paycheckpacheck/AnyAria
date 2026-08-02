"""Two different questions, and only one of them the datasheet can answer.

Whether a model is the right part is settled against published values. Whether
its *arithmetic* is right is not - a model can be built from exactly the right
numbers and integrate them badly, and the result looks the same as a part that
does not meet its own specification.

The op-amp's settling time comes from a hand-rolled forward-Euler integration
of a lightly damped second-order system, which is precisely where numerical
damping creeps in unnoticed. Below the slew limit that system is a series RLC,
so ngspice integrates the identical problem with an implicit method, and the
two have to agree.
"""

import pytest

from circuit_synth.simulation.crosscheck import (
    cross_check_settling,
    settling_time_of,
    slew_limited,
    spice_second_order_step,
)
from circuit_synth.simulation.ngspice_runner import available

needs_ngspice = pytest.mark.skipif(
    not available(), reason="no ngspice this interpreter can reach"
)


def test_settling_needs_the_waveform_to_stay_in_the_band():
    """A response that rings back out had not settled when it first arrived.

    Taking the first entry would report a moment the output was not holding,
    which is the error that makes a marginal design look fine.
    """
    times = [0.0, 1.0, 2.0, 3.0, 4.0]
    rings_back_out = [0.0, 1.0, 1.5, 1.0, 1.0]

    assert settling_time_of(times, rings_back_out, 1.0, 0.1) == 3.0


def test_a_waveform_that_never_arrives_is_not_settled_at_zero():
    """NaN, not the last sample."""
    result = settling_time_of([0.0, 1.0], [0.0, 0.1], 1.0, 0.01)

    assert result != result  # NaN


def test_the_slew_test_is_about_whether_it_is_the_same_problem():
    """A step big enough to slew is not the linear network's response."""
    assert slew_limited(natural_frequency=3.3e7, step=2.0, slew_rate=20e6)
    assert not slew_limited(natural_frequency=3.3e7, step=0.1, slew_rate=20e6)


@needs_ngspice
def test_the_reference_network_has_the_damping_it_was_asked_for():
    """Overshoot follows from the damping ratio alone.

    exp(-pi*zeta/sqrt(1-zeta^2)) is 12.4% at zeta = 0.554, so if the RLC comes
    back with a different peak the component values are wrong and every
    comparison built on them is meaningless.
    """
    import math

    zeta = 0.5543
    times, values = spice_second_order_step(zeta, 3.2987e7, 1.0, 3e-6)
    expected = math.exp(-math.pi * zeta / math.sqrt(1 - zeta**2))

    assert max(values) - 1.0 == pytest.approx(expected, rel=0.05)


@needs_ngspice
def test_the_opamp_integrator_agrees_with_a_real_transient():
    """Forward Euler against an implicit solver on the same system.

    Agreement here is what lets the TL072's disagreement with its datasheet be
    read as a statement about the part - and it is, since one of the published
    settling times is impossible.
    """
    from circuit_synth.simulation.parts import tl072

    check = cross_check_settling(tl072.model(), step=0.1, tolerance=1e-3)

    assert check.agreed, check.summary()
    assert check.error < 0.02


@needs_ngspice
def test_agreement_holds_at_a_tighter_band():
    """The tighter band is later in the ring-down, where an integrator's error
    has had longer to accumulate."""
    from circuit_synth.simulation.parts import tl072

    check = cross_check_settling(tl072.model(), step=0.1, tolerance=1e-4)

    assert check.agreed, check.summary()


def test_comparing_a_slewing_step_is_refused():
    """Silently comparing two different problems would produce a number.

    It would look like a result and mean nothing, so it raises instead.
    """
    from circuit_synth.simulation.parts import tl072

    with pytest.raises(ValueError, match="slews at this bandwidth"):
        cross_check_settling(tl072.model(), step=2.0, tolerance=1e-3)
