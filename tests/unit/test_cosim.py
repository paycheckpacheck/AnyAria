"""Simulating a board whose behaviour comes from its ICs and its firmware.

SPICE solves passives and primitives and cannot touch an integrated circuit: a
gate driver, a shunt amplifier or a comparator has no netlist to solve, and the
vendor's model, where there is one, will not run. So a board whose behaviour
comes from its ICs cannot be simulated by SPICE, which is most boards.

What is also missing from a SPICE-only view is the firmware. A motor
controller's behaviour is its control loop; simulating the power stage with a
fixed stimulus leaves out the part under test.

These tests cover the pieces that make the alternative trustworthy: that the
loop closes with the delay a real controller has, that a model refuses to
invent behaviour its datasheet does not specify, and that what was not modelled
is reported rather than hidden.
"""

from typing import Dict

import numpy as np
import pytest

from circuit_synth.simulation.cosim import (
    Block,
    CoSimulation,
    Firmware,
    FunctionBlock,
    TimeWindow,
    Waveform,
)
from circuit_synth.simulation.devices import (
    Comparator,
    CurrentSenseAmplifier,
    Datasheet,
    GateDriver,
)
from circuit_synth.simulation.plant import SwitchingLeg

SHEET = Datasheet(part="TEST", document="DOC-1", revision="A")


class Counter(Firmware):
    """Firmware that drives high once it has seen its own output come back."""

    def __init__(self):
        super().__init__("counter", inputs=["fb"], outputs=["drive"])
        self.seen = []

    def control(self, t: float, feedback: Dict[str, float]) -> Dict[str, float]:
        self.seen.append(feedback["fb"])
        return {"drive": 5.0 if feedback["fb"] > 0.5 else 0.0}


def test_the_firmware_sees_the_previous_period_not_this_one():
    """A controller acts on samples it has already taken.

    Modelling the loop as instantaneous would hide the delay that decides
    whether a control loop is stable, so the delay is built in rather than
    being an artefact.
    """
    firmware = Counter()
    echo = FunctionBlock(
        "echo", ["drive"], ["fb"],
        lambda window, inputs: {"fb": Waveform(window.t, inputs["drive"].v, "V", "fb")},
    )

    simulation = CoSimulation([firmware, echo], initial={"fb": 1.0})
    simulation.run(duration=4e-6, control_period=1e-6, dt=1e-7)

    # It sees the seeded 1.0 first, then what its own output produced.
    assert firmware.seen[0] == pytest.approx(1.0)
    assert firmware.seen[1] == pytest.approx(5.0)


def test_two_blocks_driving_one_net_is_an_error():
    """A wiring mistake, and one to fail on rather than resolve at run time."""
    one = FunctionBlock("one", [], ["net"], lambda w, i: {})
    two = FunctionBlock("two", [], ["net"], lambda w, i: {})

    with pytest.raises(ValueError, match="driven by both"):
        CoSimulation([one, two])


def test_the_firmware_cannot_decide_faster_than_the_simulation_resolves():
    """A control period shorter than the sample interval is a specification error."""
    simulation = CoSimulation([Counter()])

    with pytest.raises(ValueError, match="shorter than"):
        simulation.run(duration=1e-6, control_period=1e-9, dt=1e-7)


def test_every_block_says_what_it_was_built_on():
    """A simulation nobody can trace is a simulation nobody should act on."""
    firmware = Counter()
    simulation = CoSimulation([firmware])
    result = simulation.run(duration=2e-6, control_period=1e-6, dt=1e-7)

    assert "firmware under test" in result.blocks["counter"]


def driver(supply: float) -> tuple:
    """Build a gate driver and a supply for it.

    Args:
        supply: The rail to feed it.

    Returns:
        The driver and the source block.
    """
    part = GateDriver(
        "drv", "hin", "lin", "hgate", "lgate", "vcc",
        datasheet=SHEET,
        propagation_delay=0.0,
        uvlo_rising=8.9,
        uvlo_falling=8.2,
        output_high=12.0,
    )
    source = FunctionBlock(
        "src", [], ["hin", "lin", "vcc"],
        lambda window, inputs: {
            "hin": Waveform.constant(window, 3.3),
            "lin": Waveform.constant(window, 0.0),
            "vcc": Waveform.constant(window, supply),
        },
    )
    return part, source


def test_a_gate_driver_below_its_lockout_does_not_drive():
    """The failure a schematic review cannot find: every connection is correct.

    An IR2101 given 3.3V does not drive weakly. It does not drive at all, and
    the board does nothing, and nothing in the netlist says so.
    """
    part, source = driver(supply=3.3)
    result = CoSimulation([source, part]).run(2e-6, 1e-6, 1e-7)

    assert result["hgate"].v.max() == pytest.approx(0.0)


def test_a_gate_driver_above_its_lockout_drives():
    """The same driver, on a rail that suits it."""
    part, source = driver(supply=12.0)
    result = CoSimulation([source, part]).run(2e-6, 1e-6, 1e-7)

    assert result["hgate"].v.max() == pytest.approx(12.0)


def test_the_lockout_has_hysteresis():
    """Rising and falling thresholds differ, so a sagging rail does not chatter."""
    part, _ = driver(supply=8.5)

    assert part.uvlo_rising > part.uvlo_falling


def test_a_shunt_amplifier_band_limits_rather_than_multiplying():
    """A shunt amplifier watching a switching current is a low-pass filter.

    A controller that treats it as a multiplication reads a peak that is not
    there.
    """
    amplifier = CurrentSenseAmplifier(
        "amp", "shunt", "out", SHEET, gain=50.0, bandwidth=1e3, supply=3.3
    )
    window = TimeWindow(0.0, 1e-5, 1e-7)
    step = {"shunt": Waveform.constant(window, 0.02)}

    out = amplifier.step(window, step)["out"]

    # A 1kHz pole cannot follow a step inside 10us, so it is well short of the
    # 1.0V that a bare multiplication would give.
    assert out.v[-1] < 0.5


def test_a_shunt_amplifier_cannot_exceed_its_supply():
    """A real output saturates, and a controller has to see that it did."""
    amplifier = CurrentSenseAmplifier(
        "amp", "shunt", "out", SHEET, gain=50.0, bandwidth=1e9, supply=3.3
    )
    window = TimeWindow(0.0, 1e-5, 1e-7)

    out = amplifier.step(window, {"shunt": Waveform.constant(window, 1.0)})["out"]

    assert out.v.max() == pytest.approx(3.3)


def test_a_comparator_has_hysteresis():
    """Hysteresis decides whether a noisy crossing gives one edge or twenty."""
    part = Comparator("cmp", "p", "n", "out", SHEET, 0.0, hysteresis=0.1, output_high=3.3)
    window = TimeWindow(0.0, 1e-5, 1e-7)

    noise = np.full(window.t.shape, 0.0)
    noise[::2] = 0.02  # jitter smaller than the hysteresis band
    out = part.step(window, {
        "p": Waveform(window.t, noise, "V", "p"),
        "n": Waveform.constant(window, 0.0),
    })["out"]

    assert out.v.max() == pytest.approx(0.0)


def test_a_switching_leg_freewheels_the_right_way():
    """Turning the switches off must reduce the applied voltage, not raise it.

    With the body diodes the wrong way round, switching off applies more than
    the rail and the current runs away - which looks like a real instability
    and is not.
    """
    leg = SwitchingLeg(
        "leg", "hg", "lg", "rail", "emf", "phase", "i", "vshunt",
        inductance=250e-6, resistance=0.35, shunt=0.005,
    )
    window = TimeWindow(0.0, 1e-4, 1e-7)

    driven = leg.step(window, {
        "hg": Waveform.constant(window, 12.0),
        "lg": Waveform.constant(window, 0.0),
        "rail": Waveform.constant(window, 24.0),
        "emf": Waveform.constant(window, 0.0),
    })
    peak = driven["i"].final
    assert peak > 0

    coasting = leg.step(TimeWindow(1e-4, 2e-4, 1e-7), {
        "hg": Waveform.constant(window, 0.0),
        "lg": Waveform.constant(window, 0.0),
        "rail": Waveform.constant(window, 24.0),
        "emf": Waveform.constant(window, 0.0),
    })

    assert coasting["i"].final < peak


def test_a_model_reports_what_it_does_not_represent():
    """A gap that is stated is useful; one that is hidden is a trap."""
    part, _ = driver(supply=12.0)

    assert part.gaps
    assert "not modelled" in part.provenance()
