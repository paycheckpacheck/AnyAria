"""Simulate the driver with its firmware in the loop.

What makes a motor controller work is not the power stage, it is the control
loop: the MCU drives the gates, watches the back-EMF, and decides what to drive
next. Simulating the power stage with a fixed stimulus tells you almost nothing,
because the stimulus is the part under test.

So the excitation here is Python standing in for the firmware, and it sees what
the firmware will see - the comparator outputs and the current-sense outputs,
sampled once per control period, arriving after the delays the real parts have.
Every integrated circuit between the MCU and the motor is a model built from its
datasheet, because none of them has a netlist a solver can do anything with. The
windings are integrated directly, being one differential equation each.

Run it:

    uv run python examples/simulate_three_phase_driver.py
"""

import sys
from pathlib import Path
from typing import Dict

import numpy as np

from circuit_synth.simulation.cosim import (
    Block,
    CoSimulation,
    Firmware,
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

PHASES = ("A", "B", "C")

# The six-step sequence, as (high-side phase, low-side phase) per step. This is
# the commutation table the firmware will carry, and simulating it is the point
# of the exercise.
SIX_STEP = (("A", "B"), ("A", "C"), ("B", "C"), ("B", "A"), ("C", "A"), ("C", "B"))

MOTOR_POLE_PAIRS = 4
MOTOR_KV = 500.0  # rpm per volt
WINDING_L = 250e-6
WINDING_R = 0.35
SHUNT = 0.005
SENSE_GAIN = 50.0
RAIL = 24.0
CONTROL_PERIOD = 20e-6


class SensorlessCommutation(Firmware):
    """The firmware: six-step commutation from back-EMF zero crossings.

    Each control period it reads the three zero-crossing comparators and the
    three current-sense outputs, advances the commutation step when it sees the
    crossing it is waiting for, and drives the corresponding pair of gates.

    Open-loop ramp first, because a sensorless drive has no back-EMF to sense
    until it is already turning - which is exactly the awkward part of the
    design, and exactly the part a fixed-stimulus simulation would skip.
    """

    def __init__(
        self,
        name: str = "firmware",
        ramp_time: float = 0.02,
        current_limit: float = 6.0,
        start_hz: float = 5.0,
        ramp_hz: float = 60.0,
        period: float = CONTROL_PERIOD,
    ):
        """Build the controller.

        Args:
            name: Block name.
            ramp_time: How long to run open loop before trusting the
                comparators, in seconds.
            current_limit: Winding current to regulate to, in amps.
            start_hz: Electrical frequency to start the ramp at.
            ramp_hz: How much faster the ramp finishes than it starts.
            period: The control period, which is also the PWM period.
        """
        gates = [f"{phase}{side}" for phase in PHASES for side in ("H", "L")]
        super().__init__(
            name,
            inputs=[f"ZC_{phase}" for phase in PHASES]
            + [f"ISENSE_{phase}" for phase in PHASES],
            outputs=gates,
        )
        self.ramp_time = ramp_time
        self.current_limit = current_limit
        self.start_hz, self.ramp_hz = start_hz, ramp_hz
        self.period = period
        self.step_index = 0
        self.ramp_angle = 0.0
        self.high_side_on = True
        self.last_zc: Dict[str, float] = {phase: 0.0 for phase in PHASES}
        self.commutations = 0
        self.over_current_trips = 0

    def reset(self) -> None:
        """Start from step zero with no history."""
        super().reset()
        self.step_index = 0
        self.ramp_angle = 0.0
        self.high_side_on = True
        self.last_zc = {phase: 0.0 for phase in PHASES}
        self.commutations = 0
        self.over_current_trips = 0

    def control(self, t: float, feedback: Dict[str, float]) -> Dict[str, float]:
        """Decide the gate drive for this control period.

        Commutation and current control are separate jobs and both run every
        period. Making the over-current a trip that skips commutation, which is
        the obvious first attempt, stalls the motor: the current is high
        *because* it is not commutating, so the trip prevents the only thing
        that would clear it.

        Args:
            t: Start of the period, in seconds.
            feedback: Comparator outputs and current-sense outputs.

        Returns:
            The level to hold on each of the six gates.
        """
        self._commutate(t, feedback)
        self._regulate_current(feedback)
        return self._gates()

    def _commutate(self, t: float, feedback: Dict[str, float]) -> None:
        """Advance the commutation step when it is time to.

        Args:
            t: Start of the period, in seconds.
            feedback: The comparator outputs.
        """
        if t < self.ramp_time:
            # Open loop, accelerating: a sensorless drive has no back-EMF to
            # follow until it is already turning, and getting from standstill
            # to there is the awkward part of the design.
            fraction = t / self.ramp_time
            self.ramp_angle += (self.start_hz + fraction * self.ramp_hz) * self.period * 6
            if self.ramp_angle >= 1.0:
                self.ramp_angle -= 1.0
                self.step_index = (self.step_index + 1) % 6
                self.commutations += 1
            return

        # Closed loop: the undriven phase is the one whose back-EMF is visible,
        # and its crossing of the neutral is what says the rotor has arrived.
        floating = self._floating_phase()
        level = feedback.get(f"ZC_{floating}", 0.0)
        previous = self.last_zc[floating]
        crossed = (previous < 1.65 <= level) or (previous > 1.65 >= level)
        self.last_zc[floating] = level

        if crossed:
            self.step_index = (self.step_index + 1) % 6
            self.commutations += 1

    def _regulate_current(self, feedback: Dict[str, float]) -> None:
        """Hold the winding current between two limits.

        Bang-bang rather than a duty cycle, because the control period is the
        PWM period: the decision each period is whether the high side is on,
        and hysteresis is what stops it deciding differently every period.

        Args:
            feedback: The current-sense outputs.
        """
        high, _ = SIX_STEP[self.step_index]
        amps = feedback.get(f"ISENSE_{high}", 0.0) / (SENSE_GAIN * SHUNT)

        if amps > self.current_limit:
            self.high_side_on = False
            self.over_current_trips += 1
        elif amps < self.current_limit * 0.7:
            self.high_side_on = True

    def _floating_phase(self) -> str:
        """Which phase is undriven, and so has visible back-EMF.

        Returns:
            The phase letter.
        """
        high, low = SIX_STEP[self.step_index]
        return next(phase for phase in PHASES if phase not in (high, low))

    def _gates(self) -> Dict[str, float]:
        """Turn the commutation step into six gate levels.

        Returns:
            The level for each gate.
        """
        high, low = SIX_STEP[self.step_index]
        gates = {gate: 0.0 for gate in self.outputs}
        if self.high_side_on:
            gates[f"{high}H"] = 3.3
        gates[f"{low}L"] = 3.3
        return gates


class MotorBackEmf(Block):
    """The motor's back-EMF, from the speed the commutation implies.

    Not a datasheet model and not a solved network: a motor is a mechanical
    system, and this is the smallest thing that closes the loop honestly. It
    takes the electrical speed from how fast the firmware is commutating and
    produces three trapezoidal EMFs from it.
    """

    def __init__(self, name: str, firmware: SensorlessCommutation):
        """Build the motor.

        Args:
            name: Block name.
            firmware: The controller, read for its commutation count.
        """
        super().__init__(
            name, inputs=[], outputs=[f"BEMF_{phase}" for phase in PHASES] + ["VNEUTRAL"]
        )
        self.firmware = firmware
        self.angle = 0.0
        self._last_count = 0

    def reset(self) -> None:
        """Start from rest."""
        self.angle = 0.0
        self._last_count = 0

    def provenance(self) -> str:
        """Describe the motor model.

        Returns:
            One line.
        """
        return (
            f"trapezoidal back-EMF, {MOTOR_KV:g} rpm/V, {MOTOR_POLE_PAIRS} pole "
            f"pairs; mechanical load and inertia are NOT modelled"
        )

    def step(
        self, window: TimeWindow, inputs: Dict[str, Waveform]
    ) -> Dict[str, Waveform]:
        """Produce the three phase EMFs across the slice.

        Args:
            window: The slice.
            inputs: Unused.

        Returns:
            The three back-EMFs and the virtual neutral.
        """
        # Electrical speed from the commutation rate: six steps per revolution.
        span = window.stop - window.start
        steps = self.firmware.commutations - self._last_count
        self._last_count = self.firmware.commutations
        electrical_hz = (steps / 6.0) / span if span > 0 else 0.0

        amplitude = electrical_hz * 60.0 / MOTOR_POLE_PAIRS / MOTOR_KV

        out: Dict[str, Waveform] = {}
        phase_angle = self.angle + 2 * np.pi * electrical_hz * (window.t - window.start)
        for index, phase in enumerate(PHASES):
            shifted = phase_angle - index * 2 * np.pi / 3
            # Trapezoidal rather than sinusoidal, which is what a BLDC has.
            wave = np.clip(1.5 * np.sin(shifted), -1.0, 1.0) * amplitude
            out[f"BEMF_{phase}"] = Waveform(window.t, wave, "V", f"BEMF_{phase}")

        self.angle = float(phase_angle[-1]) if phase_angle.size else self.angle
        out["VNEUTRAL"] = Waveform(
            window.t, np.full(window.t.shape, RAIL / 2.0), "V", "VNEUTRAL"
        )
        return out


def build(driver_rail: float = 12.0) -> CoSimulation:
    """Assemble the whole driver: firmware, drivers, power stages, sensing.

    Args:
        driver_rail: What the IR2101's VCC is given, in volts. The schematic as
            drawn hands it the 3.3V logic rail, which is worth simulating.

    Returns:
        The simulation, ready to run.
    """
    firmware = SensorlessCommutation()
    blocks: list = [firmware, MotorBackEmf("motor", firmware)]

    ir2101 = Datasheet(
        part="IR2101",
        document="PD60147",
        revision="R",
        notes="propagation delay and UVLO are typical values at 25C",
    )
    ina181 = Datasheet(part="INA181A2", document="SBOS729", revision="D")
    tlv3501 = Datasheet(part="TLV3501", document="SLOS397", revision="D")

    for phase in PHASES:
        blocks.append(
            GateDriver(
                name=f"driver_{phase}",
                high_in=f"{phase}H",
                low_in=f"{phase}L",
                high_out=f"HGATE_{phase}",
                low_out=f"LGATE_{phase}",
                supply="VDRV",
                datasheet=ir2101,
                propagation_delay=680e-9,
                uvlo_rising=8.9,
                uvlo_falling=8.2,
                output_high=12.0,
                input_threshold=2.5,  # V_IH from PD60147
            )
        )
        blocks.append(
            SwitchingLeg(
                name=f"leg_{phase}",
                high_gate=f"HGATE_{phase}",
                low_gate=f"LGATE_{phase}",
                rail="VMOTOR",
                back_emf=f"BEMF_{phase}",
                phase=f"PHASE_{phase}",
                current=f"I_{phase}",
                shunt_voltage=f"VSHUNT_{phase}",
                inductance=WINDING_L,
                resistance=WINDING_R,
                shunt=SHUNT,
            )
        )
        blocks.append(
            CurrentSenseAmplifier(
                name=f"isense_{phase}",
                shunt_voltage=f"VSHUNT_{phase}",
                output=f"ISENSE_{phase}",
                datasheet=ina181,
                gain=SENSE_GAIN,
                bandwidth=350e3,
                supply=3.3,
            )
        )
        blocks.append(
            Comparator(
                name=f"zc_{phase}",
                positive=f"PHASE_{phase}",
                negative="VNEUTRAL",
                output=f"ZC_{phase}",
                datasheet=tlv3501,
                propagation_delay=4.5e-9,
                hysteresis=0.006,
                output_high=3.3,
            )
        )

    return CoSimulation(blocks, initial={"VMOTOR": RAIL, "VDRV": driver_rail})


def main() -> int:
    """Run the simulation and report what it found.

    Returns:
        Process exit status.
    """
    simulation = build()
    result = simulation.run(duration=0.05, control_period=CONTROL_PERIOD, dt=200e-9)

    firmware = next(
        block for block in simulation.blocks if isinstance(block, SensorlessCommutation)
    )

    print(result.summary())
    print()
    print(f"commutations        {firmware.commutations}")
    print(f"over-current trips  {firmware.over_current_trips}")
    for phase in PHASES:
        current = result[f"I_{phase}"]
        print(
            f"phase {phase}  RMS {current.rms():5.2f} A   peak {np.abs(current.v).max():5.2f} A"
        )

    # The same board with the gate driver on the rail the schematic actually
    # gives it. The IR2101 releases its lockout at 8.9V typical, so 3.3V is
    # below it and the part never drives at all - which no amount of reading
    # the schematic will tell you, because every connection is correct.
    as_drawn = build(driver_rail=3.3)
    drawn_result = as_drawn.run(duration=0.01, control_period=CONTROL_PERIOD, dt=200e-9)
    gate = drawn_result["HGATE_A"]
    print()
    print("With VDRV on the 3.3V logic rail, as the schematic wires it:")
    print(f"  highest gate voltage reached  {gate.v.max():.2f} V")
    print(f"  winding current, RMS          {drawn_result['I_A'].rms():.3f} A")
    if gate.v.max() < 1.0:
        print("  the IR2101 never leaves under-voltage lockout, so nothing moves")

    out = Path("examples/build/three_phase_driver/sim")
    out.mkdir(parents=True, exist_ok=True)
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        figure, axes = plt.subplots(3, 1, figsize=(11, 8), sharex=True)
        for phase in PHASES:
            axes[0].plot(result[f"I_{phase}"].t * 1e3, result[f"I_{phase}"].v, label=phase)
            axes[1].plot(result[f"PHASE_{phase}"].t * 1e3, result[f"PHASE_{phase}"].v, label=phase)
            axes[2].plot(result[f"ZC_{phase}"].t * 1e3, result[f"ZC_{phase}"].v, label=phase)
        axes[0].set_ylabel("winding current (A)")
        axes[1].set_ylabel("phase node (V)")
        axes[2].set_ylabel("zero cross (V)")
        axes[2].set_xlabel("time (ms)")
        for axis in axes:
            axis.legend(loc="upper right")
            axis.grid(alpha=0.3)
        figure.tight_layout()
        figure.savefig(out / "commutation.png", dpi=110)
        print(f"\nwrote {out / 'commutation.png'}")
    except ImportError:
        print("\nmatplotlib is not installed, so no plot was written")

    return 0


if __name__ == "__main__":
    sys.exit(main())
