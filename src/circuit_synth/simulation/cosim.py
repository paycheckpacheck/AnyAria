# -*- coding: utf-8 -*-
"""Simulating a board the way it actually behaves: firmware in the loop.

SPICE simulates passives and primitives well and integrated circuits not at
all. A gate driver, a current-sense amplifier, a comparator, a PLL, a mixer -
none of them has a netlist you can solve, and the vendor's encrypted model, if
there is one, will not run in ngspice. So a board whose behaviour comes from
its ICs cannot be simulated by SPICE, which is most boards.

What a datasheet does give you is the behaviour: a propagation delay, a gain, a
bandwidth, a hysteresis, an under-voltage lockout, a PSRR curve. That is enough
to write the part as a function from its input waveforms to its output
waveforms, and a function composes with other functions.

The other thing missing from a SPICE-only view is the firmware. A motor
controller's behaviour *is* the control loop: the MCU drives the gates, watches
the back-EMF and the phase current, and decides what to drive next. Simulating
the power stage with a fixed stimulus tells you almost nothing, because the
stimulus is the interesting part.

So this module composes three kinds of block over a shared set of nets:

* **Firmware** - Python you write, standing in for what the MCU will run. It is
  the excitation, and it sees the feedback.
* **Device models** - one Python function per IC, built from its datasheet.
* **SPICE blocks** - the passives and primitives, solved by ngspice.

Time advances in slices. Within a slice every block is evaluated in dependency
order; the firmware sees the feedback from the *previous* slice, which is not a
simplification but what really happens - a controller acts on samples it has
already taken.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TimeWindow:
    """One slice of simulated time.

    Attributes:
        start: When the slice begins, in seconds.
        stop: When it ends, in seconds.
        dt: The sample interval within it. Fine enough to resolve the fastest
            edge that matters - a gate transition, not the control period.
    """

    start: float
    stop: float
    dt: float

    @property
    def t(self) -> np.ndarray:
        """The slice's time axis.

        Returns:
            Sample times from ``start`` up to but not including ``stop``.
        """
        return np.arange(self.start, self.stop, self.dt)

    def __len__(self) -> int:
        return len(self.t)


@dataclass
class Waveform:
    """A signal on a net over time.

    Attributes:
        t: Sample times, in seconds.
        v: Values at those times.
        unit: What the values are, such as ``"V"`` or ``"A"``.
        name: The net this is, for plots and error messages.
    """

    t: np.ndarray
    v: np.ndarray
    unit: str = "V"
    name: str = ""

    def __post_init__(self) -> None:
        self.t = np.asarray(self.t, dtype=float)
        self.v = np.asarray(self.v, dtype=float)
        if self.t.shape != self.v.shape:
            raise ValueError(
                f"{self.name or 'waveform'}: {self.t.size} times but {self.v.size} values"
            )

    @staticmethod
    def constant(window: TimeWindow, value: float, unit: str = "V", name: str = "") -> "Waveform":
        """Build a waveform that holds one value across a slice.

        Args:
            window: The slice.
            value: The value to hold.
            unit: What the value is.
            name: The net name.

        Returns:
            The waveform.
        """
        t = window.t
        return Waveform(t, np.full(t.shape, float(value)), unit, name)

    @property
    def final(self) -> float:
        """The last value, which is what carries into the next slice.

        Returns:
            The final sample, or 0.0 when the waveform is empty.
        """
        return float(self.v[-1]) if self.v.size else 0.0

    def mean(self) -> float:
        """The average value over the slice.

        Returns:
            The mean, or 0.0 when empty.
        """
        return float(np.mean(self.v)) if self.v.size else 0.0

    def rms(self) -> float:
        """The root-mean-square value over the slice.

        Returns:
            The RMS, or 0.0 when empty.
        """
        return float(np.sqrt(np.mean(self.v**2))) if self.v.size else 0.0


class Block(ABC):
    """One thing in the simulation that turns input nets into output nets.

    A block is deliberately not a netlist. It is whatever computes the outputs -
    a SPICE run, a datasheet-derived function, or the firmware - and the
    scheduler does not care which.

    Attributes:
        name: What this block is, used in the dependency order and in reports.
        inputs: Net names it reads.
        outputs: Net names it writes.
    """

    def __init__(self, name: str, inputs: Sequence[str], outputs: Sequence[str]):
        self.name = name
        self.inputs = list(inputs)
        self.outputs = list(outputs)

    @abstractmethod
    def step(
        self, window: TimeWindow, inputs: Dict[str, Waveform]
    ) -> Dict[str, Waveform]:
        """Compute this block's outputs across one slice.

        Args:
            window: The slice to compute.
            inputs: The waveform on each of ``self.inputs``.

        Returns:
            A waveform for each of ``self.outputs``.
        """

    def reset(self) -> None:
        """Return the block to its state at time zero.

        Blocks that hold state - a latch, an integrator, a firmware state
        machine - override this. The default does nothing.
        """

    def provenance(self) -> str:
        """Say where this block's behaviour came from.

        A simulation nobody can trace is a simulation nobody should believe, so
        every block says what it is built on: a datasheet and its revision, a
        SPICE model and its source, or "this is the firmware under test".

        Returns:
            One line.
        """
        return f"{type(self).__name__}, source not recorded"


class Firmware(Block):
    """The excitation: Python standing in for what the MCU will run.

    Subclass this and implement :meth:`control`. It is called once per control
    period with the feedback sampled at the end of the previous period, and
    returns the level to hold on each output for the coming period.

    That once-per-period shape is not a convenience. It is what a controller
    does: sample, decide, drive, and only look again next time round. Modelling
    it as continuous would hide the loop delay that decides whether a control
    loop is stable.
    """

    def __init__(self, name: str, inputs: Sequence[str], outputs: Sequence[str]):
        super().__init__(name, inputs, outputs)
        self.history: List[Dict[str, float]] = []

    @abstractmethod
    def control(self, t: float, feedback: Dict[str, float]) -> Dict[str, float]:
        """Decide what to drive for the coming control period.

        Args:
            t: The time this period starts, in seconds.
            feedback: The value of each input net, sampled at the end of the
                previous period.

        Returns:
            The level to hold on each output net for this period.
        """

    def step(
        self, window: TimeWindow, inputs: Dict[str, Waveform]
    ) -> Dict[str, Waveform]:
        """Run one control period.

        Args:
            window: The control period.
            inputs: The feedback waveforms from the previous period.

        Returns:
            A held level on each output.
        """
        sampled = {name: wave.final for name, wave in inputs.items()}
        decided = self.control(window.start, sampled)
        self.history.append({"t": window.start, **sampled, **decided})
        return {
            name: Waveform.constant(window, decided.get(name, 0.0), "V", name)
            for name in self.outputs
        }

    def reset(self) -> None:
        """Clear the recorded history."""
        self.history = []

    def provenance(self) -> str:
        """Describe the firmware.

        Returns:
            One line.
        """
        return f"{type(self).__name__}: firmware under test, not a model of anything"


class FunctionBlock(Block):
    """A block whose behaviour is a plain function of its inputs.

    Useful for a source, a load, or anything simple enough not to need a class.
    """

    def __init__(
        self,
        name: str,
        inputs: Sequence[str],
        outputs: Sequence[str],
        function: Callable[[TimeWindow, Dict[str, Waveform]], Dict[str, Waveform]],
        source: str = "",
    ):
        super().__init__(name, inputs, outputs)
        self._function = function
        self._source = source

    def step(
        self, window: TimeWindow, inputs: Dict[str, Waveform]
    ) -> Dict[str, Waveform]:
        """Call the function.

        Args:
            window: The slice.
            inputs: Input waveforms.

        Returns:
            The function's output waveforms.
        """
        return self._function(window, inputs)

    def provenance(self) -> str:
        """Describe the function's basis.

        Returns:
            One line.
        """
        return self._source or f"{self.name}: a hand-written function"


@dataclass
class CoSimulationResult:
    """Everything the run recorded.

    Attributes:
        nets: The full waveform on every net, concatenated across slices.
        blocks: What each block was built on, so the result can be traced.
        gaps: Anything that was not modelled, stated plainly. A result with
            gaps is still useful; a result whose gaps are hidden is not.
    """

    nets: Dict[str, Waveform] = field(default_factory=dict)
    blocks: Dict[str, str] = field(default_factory=dict)
    gaps: List[str] = field(default_factory=list)

    def __getitem__(self, net: str) -> Waveform:
        if net not in self.nets:
            raise KeyError(f"no net {net!r}; the run had {sorted(self.nets)}")
        return self.nets[net]

    def summary(self) -> str:
        """Describe the run for a person to read.

        Returns:
            The blocks, their sources, and the gaps.
        """
        lines = ["Blocks:"]
        lines += [f"  {name}: {source}" for name, source in sorted(self.blocks.items())]
        if self.gaps:
            lines.append("Not modelled:")
            lines += [f"  {gap}" for gap in self.gaps]
        return "\n".join(lines)


class CoSimulation:
    """Runs a set of blocks over shared nets, one time slice at a time.

    The feedback path is what makes this a co-simulation rather than a chain: a
    firmware block's inputs are produced by blocks that run after it. That cycle
    is broken by one control period of delay, which is what a real controller
    has.
    """

    def __init__(self, blocks: Iterable[Block], initial: Optional[Dict[str, float]] = None):
        """Build a simulation.

        Args:
            blocks: The blocks to run.
            initial: Starting value for any net, for the first slice before
                anything has driven it. Defaults to zero.

        Raises:
            ValueError: If two blocks drive the same net, which is a wiring
                error rather than something to resolve at run time.
        """
        self.blocks = list(blocks)
        self.initial = dict(initial or {})

        driver: Dict[str, str] = {}
        for block in self.blocks:
            for net in block.outputs:
                if net in driver:
                    raise ValueError(
                        f"net {net!r} is driven by both {driver[net]!r} and {block.name!r}"
                    )
                driver[net] = block.name
        self._driver = driver

    def _order(self) -> List[Block]:
        """Order the blocks so each runs after whatever feeds it.

        Firmware runs first: it is the excitation, and its own inputs come from
        the previous slice by construction, so it never waits for anything.

        Returns:
            The blocks in evaluation order.
        """
        firmware = [block for block in self.blocks if isinstance(block, Firmware)]
        rest = [block for block in self.blocks if not isinstance(block, Firmware)]

        ordered: List[Block] = list(firmware)
        available: Set[str] = {net for block in firmware for net in block.outputs}
        available |= set(self.initial)

        remaining = list(rest)
        while remaining:
            ready = [
                block
                for block in remaining
                if all(
                    net in available or self._driver.get(net) is None
                    for net in block.inputs
                )
            ]
            if not ready:
                # A cycle among the analogue blocks. Break it in net order so
                # the result is repeatable, and say so.
                ready = [remaining[0]]
                logger.debug("Breaking a feedback cycle at %s", ready[0].name)
            for block in ready:
                ordered.append(block)
                available |= set(block.outputs)
                remaining.remove(block)
        return ordered

    def run(
        self,
        duration: float,
        control_period: float,
        dt: float,
        record: Optional[Sequence[str]] = None,
    ) -> CoSimulationResult:
        """Run the simulation.

        Args:
            duration: How long to simulate, in seconds.
            control_period: How often the firmware decides. One slice.
            dt: The sample interval inside a slice. Small enough to resolve the
                fastest edge that matters.
            record: Which nets to keep. Defaults to all of them.

        Returns:
            The recorded waveforms, what each block was built on, and the gaps.

        Raises:
            ValueError: If the control period is not a multiple of dt, which
                would put slice boundaries between samples.
        """
        if control_period < dt:
            raise ValueError(
                f"the control period ({control_period}s) is shorter than the "
                f"sample interval ({dt}s); the firmware cannot decide faster "
                f"than the simulation resolves"
            )

        for block in self.blocks:
            block.reset()

        order = self._order()
        held: Dict[str, float] = dict(self.initial)
        collected: Dict[str, List[np.ndarray]] = {}
        times: List[np.ndarray] = []

        slices = int(round(duration / control_period))
        for index in range(slices):
            start = index * control_period
            window = TimeWindow(start, start + control_period, dt)
            times.append(window.t)

            available: Dict[str, Waveform] = {
                net: Waveform.constant(window, value, "V", net)
                for net, value in held.items()
            }

            for block in order:
                inputs = {
                    net: available.get(
                        net, Waveform.constant(window, held.get(net, 0.0), "V", net)
                    )
                    for net in block.inputs
                }
                for net, wave in block.step(window, inputs).items():
                    wave.name = wave.name or net
                    available[net] = wave

            for net, wave in available.items():
                if record is not None and net not in record:
                    continue
                collected.setdefault(net, []).append(wave.v)
                held[net] = wave.final

            # Nets nobody wrote this slice keep their level.
            for net, wave in available.items():
                held[net] = wave.final

        axis = np.concatenate(times) if times else np.array([])
        result = CoSimulationResult(
            nets={
                net: Waveform(axis, np.concatenate(pieces), "V", net)
                for net, pieces in collected.items()
                if len(np.concatenate(pieces)) == len(axis)
            },
            blocks={block.name: block.provenance() for block in self.blocks},
        )
        logger.info(
            "Co-simulated %gs in %d slices over %d net(s)",
            duration,
            slices,
            len(result.nets),
        )
        return result
