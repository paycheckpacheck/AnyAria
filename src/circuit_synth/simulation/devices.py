# -*- coding: utf-8 -*-
"""Integrated circuits as Python, built from their datasheets.

An IC has no netlist you can solve. What it has is a table of specified
behaviour - a propagation delay, a gain, a bandwidth, a hysteresis, an
under-voltage lockout - and that table is enough to write the part as a
function from its input waveforms to its output waveforms.

Every model here carries the numbers it was built from and the document they
came from. That is not documentation, it is the point: a simulation whose
numbers cannot be traced is a simulation nobody should act on, and a model that
quietly invents a parameter is worse than no model.

Where a datasheet does not specify something, the model says so in ``gaps``
rather than choosing a plausible value. A gate driver model that reports "no
figure for the output impedance, so the gate transition is the specified
propagation delay and nothing about the edge shape" is useful. One that assumes
2 ohms because that is typical is not.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np

from .cosim import Block, TimeWindow, Waveform

logger = logging.getLogger(__name__)


@dataclass
class Datasheet:
    """Where a model's numbers came from.

    Attributes:
        part: The part number the model is of.
        document: The datasheet's document number.
        revision: Its revision, when it has one. Datasheets disagree with
            themselves across revisions often enough that this matters.
        notes: Anything about the source worth carrying, such as a parameter
            being specified at only one temperature.
    """

    part: str
    document: str
    revision: str = ""
    notes: str = ""

    def __str__(self) -> str:
        revision = f" rev {self.revision}" if self.revision else ""
        return f"{self.part} ({self.document}{revision})"


class DeviceModel(Block):
    """An IC modelled from its datasheet.

    Attributes:
        datasheet: Where the numbers came from.
        gaps: What the datasheet does not specify, and so what this model does
            not represent.
    """

    def __init__(
        self,
        name: str,
        inputs: Sequence[str],
        outputs: Sequence[str],
        datasheet: Datasheet,
        gaps: Optional[Sequence[str]] = None,
    ):
        super().__init__(name, inputs, outputs)
        self.datasheet = datasheet
        self.gaps: List[str] = list(gaps or [])

    def provenance(self) -> str:
        """Say which datasheet this model was built from.

        Returns:
            One line.
        """
        gaps = f"; not modelled: {'; '.join(self.gaps)}" if self.gaps else ""
        return f"{self.datasheet}{gaps}"


def _delay(wave: np.ndarray, seconds: float, dt: float, hold: float) -> np.ndarray:
    """Delay a sampled signal, filling the start from the previous slice.

    Args:
        wave: The samples.
        seconds: How long to delay by.
        dt: The sample interval.
        hold: What the signal was before the slice began.

    Returns:
        The delayed samples, the same length as the input.
    """
    steps = int(round(seconds / dt))
    if steps <= 0:
        return wave
    if steps >= wave.size:
        return np.full(wave.shape, hold)
    return np.concatenate([np.full(steps, hold), wave[:-steps]])


class GateDriver(DeviceModel):
    """A half-bridge gate driver, such as the IR2101.

    The behaviour that matters to the rest of the board: it repeats its inputs
    at the gate voltage after a propagation delay, it refuses to do anything at
    all below its under-voltage lockout, and its high side is referenced to the
    switch node through a bootstrap that only charges while the low side is on.

    The lockout is the one people are surprised by. A driver whose VCC sits
    below UVLO does not drive weakly, it does not drive at all, and a schematic
    review will not tell you because the connection is correct.
    """

    def __init__(
        self,
        name: str,
        high_in: str,
        low_in: str,
        high_out: str,
        low_out: str,
        supply: str,
        datasheet: Datasheet,
        propagation_delay: float,
        uvlo_rising: float,
        uvlo_falling: float,
        output_high: float,
        input_threshold: float = 1.65,
        deadtime: float = 0.0,
    ):
        """Build a gate driver model.

        Args:
            name: Block name.
            high_in: Net carrying the high-side logic input.
            low_in: Net carrying the low-side logic input.
            high_out: Net for the high-side gate.
            low_out: Net for the low-side gate.
            supply: Net carrying the driver's own supply, watched for lockout.
            datasheet: Where these numbers came from.
            propagation_delay: Input to output delay, in seconds.
            uvlo_rising: Supply at which the driver starts working.
            uvlo_falling: Supply at which it stops.
            output_high: Gate voltage when driven high.
            input_threshold: Logic level at which an input counts as high, in
                volts. This is the datasheet's V_IH and has nothing to do with
                the output swing - a driver with a 12V output accepts 3.3V
                logic, and comparing the input against half the output instead
                is a mistake that makes the part look dead on a rail that
                suits it perfectly well.
            deadtime: Any dead time the part inserts itself, in seconds. Zero
                for a driver that does not, which is most of them - the
                IR2101 has none and expects the controller to provide it.
        """
        super().__init__(
            name,
            inputs=[high_in, low_in, supply],
            outputs=[high_out, low_out],
            datasheet=datasheet,
            gaps=[
                "output impedance and gate charge, so edge shape is not modelled",
                "bootstrap droop over a long high-side on-time",
                "shoot-through, since dead time is the controller's job here",
            ],
        )
        self.high_in, self.low_in, self.supply = high_in, low_in, supply
        self.high_out, self.low_out = high_out, low_out
        self.propagation_delay = propagation_delay
        self.uvlo_rising, self.uvlo_falling = uvlo_rising, uvlo_falling
        self.output_high = output_high
        self.input_threshold = input_threshold
        self.deadtime = deadtime
        self._enabled = False
        self._held = {high_out: 0.0, low_out: 0.0}

    def reset(self) -> None:
        """Return to the locked-out state the part powers up in."""
        self._enabled = False
        self._held = {self.high_out: 0.0, self.low_out: 0.0}

    def step(
        self, window: TimeWindow, inputs: Dict[str, Waveform]
    ) -> Dict[str, Waveform]:
        """Drive the gates, or refuse to.

        Args:
            window: The slice.
            inputs: The logic inputs and the supply.

        Returns:
            The two gate waveforms.
        """
        supply = inputs[self.supply].v
        threshold = self.uvlo_rising if not self._enabled else self.uvlo_falling
        enabled = supply >= threshold
        self._enabled = bool(enabled[-1]) if enabled.size else self._enabled

        high = (inputs[self.high_in].v > self.input_threshold).astype(float)
        low = (inputs[self.low_in].v > self.input_threshold).astype(float)

        high = _delay(high, self.propagation_delay, window.dt, self._held[self.high_out] > 0)
        low = _delay(low, self.propagation_delay, window.dt, self._held[self.low_out] > 0)

        high_gate = np.where(enabled, high * self.output_high, 0.0)
        low_gate = np.where(enabled, low * self.output_high, 0.0)

        self._held = {self.high_out: float(high_gate[-1]), self.low_out: float(low_gate[-1])}
        return {
            self.high_out: Waveform(window.t, high_gate, "V", self.high_out),
            self.low_out: Waveform(window.t, low_gate, "V", self.low_out),
        }


class CurrentSenseAmplifier(DeviceModel):
    """A current-shunt amplifier, such as the INA181.

    A gain, a bandwidth and an output that cannot leave its rails. The
    bandwidth is what stops it being a multiplication: a shunt amplifier
    watching a switching current is a low-pass filter on that current, and a
    controller that assumes otherwise reads a peak that is not there.
    """

    def __init__(
        self,
        name: str,
        shunt_voltage: str,
        output: str,
        datasheet: Datasheet,
        gain: float,
        bandwidth: float,
        supply: float,
        offset: float = 0.0,
        reference: float = 0.0,
    ):
        """Build a current-sense amplifier model.

        Args:
            name: Block name.
            shunt_voltage: Net carrying the voltage across the shunt.
            output: Net for the amplified output.
            datasheet: Where these numbers came from.
            gain: Volts out per volt in.
            bandwidth: Small-signal bandwidth, in hertz.
            supply: Supply rail, which the output cannot exceed.
            offset: Input offset voltage, in volts.
            reference: Output voltage for zero input.
        """
        super().__init__(
            name,
            inputs=[shunt_voltage],
            outputs=[output],
            datasheet=datasheet,
            gaps=[
                "common-mode rejection over the switching transient",
                "output slew rate, so a large step arrives faster than it would",
            ],
        )
        self.shunt_voltage, self.output = shunt_voltage, output
        self.gain, self.bandwidth = gain, bandwidth
        self.supply, self.offset, self.reference = supply, offset, reference
        self._state = reference

    def reset(self) -> None:
        """Return the filter to its reference level."""
        self._state = self.reference

    def step(
        self, window: TimeWindow, inputs: Dict[str, Waveform]
    ) -> Dict[str, Waveform]:
        """Amplify and band-limit the shunt voltage.

        Args:
            window: The slice.
            inputs: The shunt voltage.

        Returns:
            The output waveform.
        """
        target = (inputs[self.shunt_voltage].v + self.offset) * self.gain + self.reference

        # One pole at the specified bandwidth, integrated over the slice.
        alpha = 1.0 - np.exp(-2 * np.pi * self.bandwidth * window.dt)
        out = np.empty_like(target)
        state = self._state
        for index, value in enumerate(target):
            state += alpha * (value - state)
            out[index] = state
        self._state = state

        out = np.clip(out, 0.0, self.supply)
        return {self.output: Waveform(window.t, out, "V", self.output)}


class Comparator(DeviceModel):
    """A comparator with hysteresis and a propagation delay.

    Both matter to a controller. The hysteresis decides whether a noisy
    crossing produces one edge or twenty; the delay decides how late the
    controller learns about it, which for a commutation loop is the difference
    between running and stalling.
    """

    def __init__(
        self,
        name: str,
        positive: str,
        negative: str,
        output: str,
        datasheet: Datasheet,
        propagation_delay: float,
        hysteresis: float,
        output_high: float,
    ):
        """Build a comparator model.

        Args:
            name: Block name.
            positive: Net on the non-inverting input.
            negative: Net on the inverting input.
            output: Net for the output.
            datasheet: Where these numbers came from.
            propagation_delay: Input to output delay, in seconds.
            hysteresis: Total input hysteresis, in volts.
            output_high: Output voltage when high.
        """
        super().__init__(
            name,
            inputs=[positive, negative],
            outputs=[output],
            datasheet=datasheet,
            gaps=[
                "input offset drift with temperature",
                "output rise and fall times",
            ],
        )
        self.positive, self.negative, self.output = positive, negative, output
        self.propagation_delay = propagation_delay
        self.hysteresis = hysteresis
        self.output_high = output_high
        self._high = False

    def reset(self) -> None:
        """Return the output to low."""
        self._high = False

    def step(
        self, window: TimeWindow, inputs: Dict[str, Waveform]
    ) -> Dict[str, Waveform]:
        """Compare, with hysteresis, then delay the result.

        Args:
            window: The slice.
            inputs: The two inputs.

        Returns:
            The output waveform.
        """
        difference = inputs[self.positive].v - inputs[self.negative].v
        half = self.hysteresis / 2.0

        out = np.empty_like(difference)
        high = self._high
        for index, value in enumerate(difference):
            if high and value < -half:
                high = False
            elif not high and value > half:
                high = True
            out[index] = self.output_high if high else 0.0
        self._high = high

        out = _delay(out, self.propagation_delay, window.dt, self.output_high if high else 0.0)
        return {self.output: Waveform(window.t, out, "V", self.output)}


class LinearRegulator(DeviceModel):
    """An LDO, whose interesting behaviour is what it does *not* pass through.

    A regulator is a filter with a specification: ripple on its input appears
    on its output attenuated by the PSRR at that frequency, and that curve is
    the model. Treating it as a fixed voltage hides exactly the thing anybody
    simulates a supply to find out.
    """

    def __init__(
        self,
        name: str,
        input_net: str,
        output_net: str,
        datasheet: Datasheet,
        output_voltage: float,
        psrr_db: Dict[float, float],
        dropout: float,
        noise_rms: float = 0.0,
    ):
        """Build a regulator model.

        Args:
            name: Block name.
            input_net: Net on the input.
            output_net: Net on the output.
            datasheet: Where these numbers came from.
            output_voltage: Nominal output, in volts.
            psrr_db: Power supply rejection in dB against frequency in hertz,
                read off the datasheet curve.
            dropout: Dropout voltage at the load being simulated.
            noise_rms: Output noise, in volts RMS.
        """
        super().__init__(
            name,
            inputs=[input_net],
            outputs=[output_net],
            datasheet=datasheet,
            gaps=[
                "load transient response, which needs a load step to mean anything",
                "thermal behaviour and thermal shutdown",
            ],
        )
        self.input_net, self.output_net = input_net, output_net
        self.output_voltage = output_voltage
        self.psrr_db = dict(psrr_db)
        self.dropout = dropout
        self.noise_rms = noise_rms

    def rejection_at(self, frequency: float) -> float:
        """The PSRR at one frequency, interpolated across the curve.

        Args:
            frequency: The frequency of interest, in hertz.

        Returns:
            Rejection in dB.
        """
        points = sorted(self.psrr_db)
        values = [self.psrr_db[point] for point in points]
        return float(np.interp(frequency, points, values))

    def step(
        self, window: TimeWindow, inputs: Dict[str, Waveform]
    ) -> Dict[str, Waveform]:
        """Regulate, passing through what the PSRR does not reject.

        Args:
            window: The slice.
            inputs: The input waveform.

        Returns:
            The output waveform.
        """
        supply = inputs[self.input_net].v
        ripple = supply - np.mean(supply)

        # The dominant ripple frequency, from its zero crossings over the slice.
        crossings = np.count_nonzero(np.diff(np.signbit(ripple)))
        span = window.stop - window.start
        frequency = (crossings / 2.0) / span if span > 0 and crossings else 0.0

        attenuation = 10 ** (-self.rejection_at(frequency) / 20.0)
        out = self.output_voltage + ripple * attenuation

        if self.noise_rms:
            out = out + np.random.default_rng(0).normal(0.0, self.noise_rms, out.shape)

        # It cannot regulate above what it is given, less the dropout.
        out = np.minimum(out, supply - self.dropout)
        return {self.output_net: Waveform(window.t, out, "V", self.output_net)}
