# -*- coding: utf-8 -*-
"""The passive and primitive parts of a circuit, solved rather than modelled.

This is the half of a board SPICE is genuinely good at: resistors, capacitors,
inductors, switches and diodes, where the behaviour follows from the components
rather than from a datasheet table. Two ways to get it, and which one you can
use depends on the machine:

* :class:`SpiceNetwork` hands the network to ngspice, slice by slice, carrying
  state across the boundary. Use it when ngspice is loadable.
* :class:`StateSpaceNetwork` and :class:`SwitchingLeg` integrate the network
  directly in Python. Exact for linear networks, and they run everywhere.

The second is not a fallback of last resort. A first-order RL load has an exact
solution, and computing it is both faster and more accurate than asking a
general-purpose solver for a numerical one. It is also the only option on a
machine where KiCad ships an ngspice built for a different architecture than
the Python that would have to load it, which is common enough to plan for.
"""

import logging
from typing import Dict, List, Optional, Sequence

import numpy as np

from .cosim import Block, TimeWindow, Waveform

logger = logging.getLogger(__name__)


class SwitchingLeg(Block):
    """One half-bridge driving an inductive load.

    The physical part of a motor phase: two switches, the winding's inductance
    and resistance, the motor's back-EMF, and a shunt in the return path. Its
    behaviour is one first-order differential equation, integrated exactly over
    each sample, which makes it both faster and more accurate than handing the
    same network to a numerical solver.

    Body diodes are included, because without them the inductor current has
    nowhere to go when both switches are off and the simulation produces a
    voltage spike that does not happen.
    """

    def __init__(
        self,
        name: str,
        high_gate: str,
        low_gate: str,
        rail: str,
        back_emf: str,
        phase: str,
        current: str,
        shunt_voltage: str,
        inductance: float,
        resistance: float,
        shunt: float,
        gate_threshold: float = 4.0,
        on_resistance: float = 0.008,
        diode_drop: float = 0.7,
    ):
        """Build a switching leg.

        Args:
            name: Block name.
            high_gate: Net carrying the high-side gate voltage.
            low_gate: Net carrying the low-side gate voltage.
            rail: Net carrying the motor supply rail.
            back_emf: Net carrying the winding's back-EMF, in volts.
            phase: Net to write the phase node voltage to.
            current: Net to write the winding current to, in amps.
            shunt_voltage: Net to write the voltage across the shunt to.
            inductance: Winding inductance, in henries.
            resistance: Winding resistance, in ohms.
            shunt: Shunt resistance, in ohms.
            gate_threshold: Gate voltage above which a switch is on.
            on_resistance: Switch on-resistance, in ohms.
            diode_drop: Body diode forward voltage, in volts.
        """
        super().__init__(
            name,
            inputs=[high_gate, low_gate, rail, back_emf],
            outputs=[phase, current, shunt_voltage],
        )
        self.high_gate, self.low_gate = high_gate, low_gate
        self.rail, self.back_emf = rail, back_emf
        self.phase, self.current, self.shunt_voltage = phase, current, shunt_voltage
        self.inductance, self.resistance, self.shunt = inductance, resistance, shunt
        self.gate_threshold = gate_threshold
        self.on_resistance, self.diode_drop = on_resistance, diode_drop
        self._current = 0.0

    def reset(self) -> None:
        """Start with no current in the winding."""
        self._current = 0.0

    def provenance(self) -> str:
        """Describe what this block solves.

        Returns:
            One line.
        """
        return (
            f"first-order RL winding, {self.inductance * 1e6:g}uH / "
            f"{self.resistance:g}ohm, integrated exactly per sample; "
            f"NOT modelled: this leg returns to ground rather than to a "
            f"floating star point, so current in an undriven phase is "
            f"overstated, and switch capacitance and reverse recovery are absent"
        )

    def step(
        self, window: TimeWindow, inputs: Dict[str, Waveform]
    ) -> Dict[str, Waveform]:
        """Integrate the winding current over the slice.

        Args:
            window: The slice.
            inputs: Gates, rail and back-EMF.

        Returns:
            The phase voltage, winding current and shunt voltage.
        """
        high = inputs[self.high_gate].v > self.gate_threshold
        low = inputs[self.low_gate].v > self.gate_threshold
        rail = inputs[self.rail].v
        emf = inputs[self.back_emf].v

        total_r = self.resistance + self.on_resistance + self.shunt
        tau = self.inductance / total_r
        decay = np.exp(-window.dt / tau)

        current = np.empty(window.t.shape)
        phase = np.empty(window.t.shape)
        value = self._current

        for index in range(window.t.size):
            if high[index] and not low[index]:
                applied = rail[index]
            elif low[index] and not high[index]:
                applied = 0.0
            else:
                # Both off, and the inductor's current has to keep flowing. It
                # drags the phase node until a body diode conducts, and which
                # diode that is depends on which way the current is going:
                # outward current pulls the node below ground through the low
                # side, inward current pushes it above the rail through the
                # high side. Getting this the wrong way round turns switching
                # off into applying more voltage, and the current runs away.
                applied = (
                    -self.diode_drop if value > 0 else rail[index] + self.diode_drop
                )

            # Exact solution of L di/dt = (applied - emf) - i R over one sample.
            steady = (applied - emf[index]) / total_r
            value = steady + (value - steady) * decay
            current[index] = value
            phase[index] = applied - value * self.on_resistance

        self._current = value
        return {
            self.phase: Waveform(window.t, phase, "V", self.phase),
            self.current: Waveform(window.t, current, "A", self.current),
            self.shunt_voltage: Waveform(
                window.t, current * self.shunt, "V", self.shunt_voltage
            ),
        }


class StateSpaceNetwork(Block):
    """Any linear passive network, as a state-space system.

    A filter, a divider with capacitance, a compensation network - anything
    made of resistors, capacitors and inductors is linear, and a linear system
    is ``dx/dt = Ax + Bu``, ``y = Cx + Du``. Integrating that over a slice is
    exact for a constant input and very close for a sampled one.

    Deriving A, B, C and D from a netlist is a job for the block that builds
    this; what this class does is run it and carry the state across slices.
    """

    def __init__(
        self,
        name: str,
        inputs: Sequence[str],
        outputs: Sequence[str],
        a: np.ndarray,
        b: np.ndarray,
        c: np.ndarray,
        d: Optional[np.ndarray] = None,
        description: str = "",
    ):
        """Build a linear network.

        Args:
            name: Block name.
            inputs: Net names for the inputs, in the order of ``B``'s columns.
            outputs: Net names for the outputs, in the order of ``C``'s rows.
            a: State matrix.
            b: Input matrix.
            c: Output matrix.
            d: Feedthrough matrix. Zero when omitted.
            description: What the network is, for the provenance line.
        """
        super().__init__(name, inputs, outputs)
        self.a = np.atleast_2d(np.asarray(a, dtype=float))
        self.b = np.atleast_2d(np.asarray(b, dtype=float))
        self.c = np.atleast_2d(np.asarray(c, dtype=float))
        self.d = (
            np.atleast_2d(np.asarray(d, dtype=float))
            if d is not None
            else np.zeros((self.c.shape[0], self.b.shape[1]))
        )
        self.description = description
        self._state = np.zeros(self.a.shape[0])

    def reset(self) -> None:
        """Return every state to zero."""
        self._state = np.zeros(self.a.shape[0])

    def provenance(self) -> str:
        """Describe the network.

        Returns:
            One line.
        """
        return self.description or (
            f"linear network, {self.a.shape[0]} state(s), integrated per sample"
        )

    def step(
        self, window: TimeWindow, inputs: Dict[str, Waveform]
    ) -> Dict[str, Waveform]:
        """Integrate the network across the slice.

        Args:
            window: The slice.
            inputs: The input waveforms.

        Returns:
            The output waveforms.
        """
        from scipy.linalg import expm

        stacked = np.vstack([inputs[net].v for net in self.inputs])
        samples = stacked.shape[1]

        # Zero-order hold discretisation: exact for an input held over dt.
        size = self.a.shape[0]
        joined = np.zeros((size + self.b.shape[1], size + self.b.shape[1]))
        joined[:size, :size] = self.a
        joined[:size, size:] = self.b
        discrete = expm(joined * window.dt)
        ad = discrete[:size, :size]
        bd = discrete[:size, size:]

        out = np.zeros((self.c.shape[0], samples))
        state = self._state
        for index in range(samples):
            u = stacked[:, index]
            out[:, index] = self.c @ state + self.d @ u
            state = ad @ state + bd @ u
        self._state = state

        return {
            net: Waveform(window.t, out[row], "V", net)
            for row, net in enumerate(self.outputs)
        }


class SpiceNetwork(Block):
    """A passive network solved by ngspice, one slice at a time.

    Use this where ngspice is loadable and the network is awkward to write as a
    state space - a bridge, a network with diodes, anything non-linear that
    still has a real device model.

    State is carried across slices by rewriting each reactive element's ``ic=``
    from the previous slice's final value and running with ``uic``. That is an
    approximation at the slice boundary, and it is a good one when the slice is
    short against the network's time constants. If it is not, shorten the
    slice.
    """

    def __init__(
        self,
        name: str,
        inputs: Sequence[str],
        outputs: Sequence[str],
        deck: str,
        description: str = "",
    ):
        """Build a SPICE-solved network.

        Args:
            name: Block name.
            inputs: Net names driven into the network, written as PWL sources.
            outputs: Net names read back out.
            deck: The network as a SPICE deck, without sources or analysis.
            description: What the network is.
        """
        super().__init__(name, inputs, outputs)
        self.deck = deck
        self.description = description
        self._state: Dict[str, float] = {}

    def reset(self) -> None:
        """Forget the carried state."""
        self._state = {}

    def provenance(self) -> str:
        """Describe the network and how it is solved.

        Returns:
            One line.
        """
        return self.description or f"{self.name}: solved by ngspice, per slice"

    def step(
        self, window: TimeWindow, inputs: Dict[str, Waveform]
    ) -> Dict[str, Waveform]:
        """Run the slice in ngspice.

        Args:
            window: The slice.
            inputs: The waveforms to drive in.

        Returns:
            The requested output waveforms.

        Raises:
            RuntimeError: If ngspice cannot be loaded, with the reason. This is
                worth failing on rather than silently returning zeros - a
                simulation that quietly did not run is the worst outcome here.
        """
        from .ngspice_run import SimulationUnavailable, run_transient

        sources = []
        for index, net in enumerate(self.inputs):
            wave = inputs[net]
            points = " ".join(
                f"{time - window.start:g} {value:g}"
                for time, value in zip(wave.t, wave.v)
            )
            sources.append(f"V_cosim{index} {net} 0 PWL({points})")

        deck = "\n".join(
            [".title cosim slice", self.deck, *sources,
             f".tran {window.dt:g} {window.stop - window.start:g} 0 {window.dt:g} uic",
             ".end", ""]
        )

        try:
            waves = run_transient(deck)
        except SimulationUnavailable as error:
            raise RuntimeError(
                f"{self.name} needs ngspice and it will not load: {error}. "
                f"Write this network as a StateSpaceNetwork, or run on a machine "
                f"whose ngspice matches its Python."
            ) from error

        result: Dict[str, Waveform] = {}
        for net in self.outputs:
            values = np.asarray(waves[net], dtype=float)
            result[net] = Waveform(window.t, np.resize(values, window.t.shape), "V", net)
            self._state[net] = result[net].final
        return result
