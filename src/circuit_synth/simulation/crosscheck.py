# -*- coding: utf-8 -*-
"""Check a behavioural model's arithmetic against a real simulator.

There are two different questions to ask about a model, and confusing them is
how a wrong one survives:

* **Is it the right part?** Only the datasheet answers that, which is what
  ``validation.validate`` and every ``check()`` in ``parts`` are for.
* **Is the maths right?** The datasheet cannot answer that. A model can be
  built from exactly the right numbers and still integrate them badly, and the
  result looks like a part that does not match its own specification.

This module answers the second. Where a model's behaviour reduces to a network
SPICE can represent exactly, the network is the reference and any difference is
the model's own numerical error.

The op-amp is the case in point. Its settling time comes from a hand-rolled
forward-Euler integration of a second-order system with a slew limit, and
forward Euler on a lightly damped system is exactly where numerical damping
creeps in unnoticed. Below the slew limit that system is a series RLC, so
ngspice can integrate the same problem with an implicit method and adaptive
steps, and the two must agree.

They do, to 0.24% for the TL072 at a 0.1V step. That is worth having as a
standing check rather than a one-off: it means a disagreement between that
model and its datasheet is about the part, and the datasheet contradiction
recorded in ``parts.tl072`` is not an artefact of the integrator.

**Stay inside what the reference actually represents.** The RLC is the model's
*linear* behaviour. Cross-checking a step large enough to slew would compare
two different problems and the difference would say nothing.
"""

import logging
import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .ngspice_runner import available, run_deck

logger = logging.getLogger(__name__)

__all__ = [
    "CrossCheck",
    "spice_second_order_step",
    "settling_time_of",
    "cross_check_settling",
    "slew_limited",
]

# Big enough that the reference network's own component values stay in a range
# ngspice solves comfortably, and otherwise arbitrary - the transfer function
# depends only on the products.
_REFERENCE_CAPACITANCE = 1e-9


@dataclass(frozen=True)
class CrossCheck:
    """A model's number beside an independent simulator's.

    Attributes:
        quantity: What was compared.
        model: The model's answer.
        reference: The simulator's answer.
        unit: For display.
        reference_note: What produced the reference, and what it represents.
        agreed: Whether they are within tolerance.
        tolerance: The fraction allowed, which is a claim about the discretisation
            rather than about the part.
    """

    quantity: str
    model: float
    reference: float
    unit: str
    reference_note: str
    tolerance: float

    @property
    def error(self) -> float:
        """Fractional difference from the reference.

        Returns:
            The magnitude of the relative error, or infinity when the reference
            is zero.
        """
        if self.reference == 0.0:
            return float("inf")
        return abs(self.model - self.reference) / abs(self.reference)

    @property
    def agreed(self) -> bool:
        """Whether the two are close enough to call the arithmetic sound.

        Returns:
            True when within tolerance.
        """
        return self.error <= self.tolerance

    def summary(self) -> str:
        """One line, for a report.

        Returns:
            The comparison.
        """
        verdict = "agrees" if self.agreed else "DISAGREES"
        return (
            f"[{verdict}] {self.quantity}: model {self.model:.4g}{self.unit}, "
            f"{self.reference_note} {self.reference:.4g}{self.unit}, "
            f"apart by {self.error * 100:.2f}%"
        )


def slew_limited(natural_frequency: float, step: float, slew_rate: float) -> bool:
    """Whether a step would hit the slew limit.

    The peak rate of an undamped second-order response to a step is the natural
    frequency times the step, so this is the test for whether a cross-check
    against a linear network is comparing the same problem.

    Args:
        natural_frequency: Closed-loop natural frequency, in radians per second.
        step: Step size, in volts.
        slew_rate: The part's slew rate, in volts per second.

    Returns:
        True when the linear response would exceed the slew rate.
    """
    return natural_frequency * step > slew_rate


def spice_second_order_step(
    damping: float,
    natural_frequency: float,
    step: float,
    duration: float,
    max_timestep: Optional[float] = None,
) -> Tuple[List[float], List[float]]:
    """Integrate a second-order step response in ngspice.

    The network is a series RLC with the output across the capacitor, whose
    transfer function is exactly the standard second-order form:

        wn = 1 / sqrt(L C)        zeta = (R / 2) sqrt(C / L)

    Args:
        damping: Damping ratio.
        natural_frequency: Natural frequency, in radians per second.
        step: Step size, in volts.
        duration: How long to run, in seconds.
        max_timestep: Largest step ngspice may take. Defaults to 1/2000 of the
            duration, which is fine enough that the reference is not itself the
            limiting error.

    Returns:
        A ``(times, values)`` pair.

    Raises:
        RuntimeError: If no ngspice is reachable, or the deck will not run.
            Callers that want to skip should ask :func:`available` first, since
            a cross-check that silently returns nothing is the failure mode this
            whole module exists to remove.
    """
    if not available():
        raise RuntimeError("no ngspice this process can reach")

    capacitance = _REFERENCE_CAPACITANCE
    inductance = 1.0 / (natural_frequency**2 * capacitance)
    resistance = 2.0 * damping * math.sqrt(inductance / capacitance)
    step_ceiling = max_timestep or duration / 2000.0

    deck = (
        "second order reference\n"
        f"V1 in 0 PWL(0 0 1p {step:.9g})\n"
        f"L1 in mid {inductance:.9e}\n"
        f"R1 mid out {resistance:.9f}\n"
        f"C1 out 0 {capacitance:.9e}\n"
        f".tran {step_ceiling:.9e} {duration:.9e}\n"
        ".end\n"
    )

    result = run_deck(deck, vectors=["time", "out"])
    if not result.ok:
        raise RuntimeError(f"the reference network would not run: {result.error}")
    return result.vectors["time"], result.vectors["out"]


def settling_time_of(
    times: Sequence[float],
    values: Sequence[float],
    step: float,
    tolerance: float,
) -> float:
    """When a waveform enters its settling band and stays there.

    Args:
        times: Sample times, in seconds.
        values: Sample values, in volts.
        step: The final value being settled to, in volts.
        tolerance: Fractional band, so 1e-3 is 0.1%.

    Returns:
        The settling time in seconds, or NaN when it never settles. Leaving the
        band resets the count - a waveform that rings back out had not settled,
        and taking the first entry would report a time the output was not
        holding.
    """
    band = tolerance * abs(step)
    entered: Optional[float] = None
    for moment, value in zip(times, values):
        if abs(value - step) <= band:
            if entered is None:
                entered = moment
        else:
            entered = None
    return entered if entered is not None else float("nan")


def cross_check_settling(
    amplifier,
    step: float,
    tolerance: float,
    agreement: float = 0.05,
) -> CrossCheck:
    """Compare an op-amp model's settling time against ngspice.

    Args:
        amplifier: An :class:`~.devices.OpAmp`.
        step: Step size, in volts. Keep it below the slew limit - see
            :func:`slew_limited` - or the two are not the same problem.
        tolerance: Settling band as a fraction.
        agreement: How far apart the two may be and still count as agreeing.
            This is a claim about discretisation, not about the part.

    Returns:
        The comparison.

    Raises:
        ValueError: If the step would slew, where the linear reference does not
            describe the model's behaviour and the comparison is meaningless.
    """
    if slew_limited(amplifier.natural_frequency, step, amplifier.slew_rate):
        raise ValueError(
            f"a {step:g}V step slews at this bandwidth, so the linear network "
            f"is not the same problem. Use a step below "
            f"{amplifier.slew_rate / amplifier.natural_frequency:.3g}V."
        )

    # Long enough for a lightly damped response to ring out, and set from the
    # part rather than from a guess.
    duration = 60.0 / (amplifier.damping * amplifier.natural_frequency)
    times, values = spice_second_order_step(
        amplifier.damping, amplifier.natural_frequency, step, duration
    )
    reference = settling_time_of(times, values, step, tolerance)

    return CrossCheck(
        quantity=f"settling to {tolerance * 100:g}% after a {step:g}V step",
        model=amplifier.settling_time(step, tolerance),
        reference=reference,
        unit=" s",
        reference_note="ngspice transient on the equivalent RLC",
        tolerance=agreement,
    )
