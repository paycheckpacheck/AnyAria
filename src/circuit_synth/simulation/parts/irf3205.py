# -*- coding: utf-8 -*-
"""The IRF3205 power MOSFET, and the first model here that solves for itself.

The fourth worked example, and the one that closes the gap every earlier model
declared. The LDO, the op-amp and the buck converter all end their `gaps()`
with the same line - everything here is at 25C - because none of them has a
mechanism that would respond to temperature. A power MOSFET is nothing but that
mechanism:

    on-resistance rises with junction temperature
      -> dissipation rises, because it is I^2 R
        -> junction temperature rises
          -> back to the top

So there is no formula for the operating point. Given a current and a thermal
path, the junction temperature is the value that reproduces itself, and
:func:`junction_temperature` finds it by bisection. Two things follow that a
one-shot calculation cannot express, and both are design answers rather than
numerical trouble:

* **The fixed point may not exist.** Above some current the loop gains more
  than it loses on every pass and the part runs away. Non-convergence is that
  result, not a failure to compute one.
* **A part sized on its 25C resistance is undersized.** At 175C this device's
  on-resistance is 2.2 times its 25C value, so the dissipation at a given
  current is 2.2 times what the specification table suggests.

The model is built from the normalised resistance curve, the 25C on-resistance,
the thermal resistances and the maximum junction temperature. It is judged
against four ratings from a different part of the document, all of which are
consequences of exactly this loop: the power dissipation at 25C, the linear
derating factor, and the continuous drain current at two case temperatures.

Two findings are recorded rather than smoothed over. The published current
ratings contradict each other - see :func:`rating_inconsistency` - and the
datasheet says in a footnote that the higher of them exceeds what the package
can carry.

Everything cites PD-94791B (07/23/10).
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ..validation import ReferencePoint, ValidationReport, validate

logger = logging.getLogger(__name__)

DOCUMENT = "PD-94791B"

# Absolute Maximum Ratings and Electrical Characteristics, page 1 and 2.
RDS_ON_25 = 0.0080  # ohm, maximum, VGS = 10V, ID = 62A, TJ = 25C
RTH_JC = 0.75  # C/W, junction to case
RTH_CS = 0.50  # C/W, case to sink, flat and greased
RTH_JA = 62.0  # C/W, junction to ambient, free air, no heatsink
TJ_MAX = 175.0  # C
TJ_MIN = -55.0  # C

# The ratings the model is judged against, all from the same page and none of
# them used to build it.
PD_AT_25C = 200.0  # W, at TC = 25C
DERATING_FACTOR = 1.3  # W/C
ID_AT_25C = 110.0  # A, continuous, VGS = 10V
ID_AT_100C = 80.0  # A, continuous, VGS = 10V
PACKAGE_LIMIT_CURRENT = 75.0  # A, from the footnote to the current ratings

# Figure 4, normalised on-resistance against junction temperature, at
# VGS = 10V and ID = 107A.
#
# These are not eyeball readings. The figure is a vector path in the PDF, so
# the polyline was pulled out of the drawing operators and mapped through the
# axis calibration - which the gridline coordinates confirm land on exactly
# -40, -20, 0 ... 160. Reading the same curve off a 300 dpi render put the
# 100C point at 1.38 against an actual 1.505, an 8% error that would have gone
# straight into every prediction below. Where a curve is vector art, take the
# vectors.
RDS_ON_NORMALISED: Dict[float, float] = {
    -50.5: 0.655,
    -25.0: 0.751,
    0.2: 0.868,
    25.3: 1.002,
    50.8: 1.158,
    76.0: 1.331,
    99.1: 1.505,
    124.2: 1.717,
    149.7: 1.947,
    # The path's last vertex maps to 174.85C, and the figure's own end marker -
    # a separate vector glyph - maps to 174.85C too. Both are TJ(max) drawn
    # with a few tenths of a degree of plotting slop: the same marker at the
    # curve's middle maps to 25.02C, where the normalisation makes the true
    # value exactly 25. Recorded at 175.0 so the rating calculations, which all
    # need the resistance at exactly TJ(max), do not fall 0.2C off the end of
    # the only source for it.
    175.0: 2.199,
}

_CURVE: List[Tuple[float, float]] = sorted(RDS_ON_NORMALISED.items())
_CURVE_MIN = _CURVE[0][0]
_CURVE_MAX = _CURVE[-1][0]

_BISECTION_STEPS = 60


@dataclass(frozen=True)
class ThermalSolution:
    """Where a device settles, or the finding that it does not.

    Attributes:
        converged: True when a self-consistent junction temperature exists
            within the range the curve covers. False means the loop gains more
            than it loses - the part runs away, or settles somewhere the
            datasheet does not characterise. Either way it is not a design.
        junction_temperature: The settled junction temperature, in Celsius.
            Meaningless when ``converged`` is False.
        dissipation: Conduction loss at that temperature, in watts.
        on_resistance: On-resistance at that temperature, in ohms.
        within_rating: True when the settled temperature is at or below
            TJ(max). A device can converge and still be over its rating.
        note: What the result means, in one line.
    """

    converged: bool
    junction_temperature: float
    dissipation: float
    on_resistance: float
    within_rating: bool
    note: str


def on_resistance(junction_temperature: float) -> float:
    """On-resistance at a junction temperature.

    Args:
        junction_temperature: Junction temperature, in Celsius.

    Returns:
        On-resistance, in ohms.

    Raises:
        ValueError: If the temperature is outside the range Figure 4 covers.
            The curve is the only source for the coefficient, so extrapolating
            past it would be inventing one.
    """
    if not _CURVE_MIN <= junction_temperature <= _CURVE_MAX:
        raise ValueError(
            f"{junction_temperature:.1f}C is outside Figure 4, which runs "
            f"{_CURVE_MIN:.0f}C to {_CURVE_MAX:.0f}C. The temperature "
            f"coefficient has no other source in {DOCUMENT}."
        )

    for (low_t, low_r), (high_t, high_r) in zip(_CURVE, _CURVE[1:]):
        if low_t <= junction_temperature <= high_t:
            span = high_t - low_t
            fraction = (junction_temperature - low_t) / span
            return RDS_ON_25 * (low_r + fraction * (high_r - low_r))

    raise AssertionError("the curve is not covering its own range")


def junction_temperature(
    current: float,
    reference_temperature: float = 25.0,
    thermal_resistance: float = RTH_JC,
    duty: float = 1.0,
) -> ThermalSolution:
    """Solve for the junction temperature a current settles at.

    There is no closed form. The dissipation depends on the on-resistance,
    which depends on the temperature, which depends on the dissipation, so this
    looks for the temperature that reproduces itself:

        Tj = Tref + duty * I^2 * R(Tj) * Rth

    Args:
        current: Conducted current, in amps. RMS if the device is switching.
        reference_temperature: Case or ambient temperature, in Celsius,
            whichever end ``thermal_resistance`` is measured to.
        thermal_resistance: The path from junction to that reference, in C/W.
            :data:`RTH_JC` to a case held at temperature, :data:`RTH_JA` for
            free air, or the sum of the junction-to-case, case-to-sink and
            sink-to-ambient resistances for a real heatsink.
        duty: Fraction of the time the device conducts. A half-bridge switch
            carrying its current for half the cycle dissipates half as much.

    Returns:
        The solution, or the finding that there is not one.
    """
    def settles_at(temperature: float) -> float:
        """Temperature implied by dissipating at the given temperature."""
        dissipation = duty * current**2 * on_resistance(temperature)
        return reference_temperature + dissipation * thermal_resistance

    if not _CURVE_MIN <= reference_temperature <= _CURVE_MAX:
        raise ValueError(
            f"reference temperature {reference_temperature:.1f}C is outside "
            f"Figure 4's range"
        )

    # f(T) = settles_at(T) - T. It starts positive, because dissipation is
    # positive. A root is a fixed point. If it never crosses, the device heats
    # faster than the path can carry the heat away at every temperature the
    # datasheet describes.
    low, high = reference_temperature, _CURVE_MAX
    if settles_at(high) - high > 0:
        return ThermalSolution(
            converged=False,
            junction_temperature=float("nan"),
            dissipation=float("nan"),
            on_resistance=float("nan"),
            within_rating=False,
            note=(
                f"{current:.1f}A through {thermal_resistance:.2f}C/W from "
                f"{reference_temperature:.0f}C has no stable junction "
                f"temperature below {_CURVE_MAX:.0f}C. The device either runs "
                f"away or settles past its {TJ_MAX:.0f}C rating, and Figure 4 "
                f"stops there, so this model will not say which. Both answers "
                f"mean the same thing for a design."
            ),
        )

    for _ in range(_BISECTION_STEPS):
        middle = 0.5 * (low + high)
        if settles_at(middle) - middle > 0:
            low = middle
        else:
            high = middle

    settled = 0.5 * (low + high)
    resistance = on_resistance(settled)
    dissipation = duty * current**2 * resistance
    within = settled <= TJ_MAX
    return ThermalSolution(
        converged=True,
        junction_temperature=settled,
        dissipation=dissipation,
        on_resistance=resistance,
        within_rating=within,
        note=(
            f"{current:.1f}A settles at {settled:.0f}C, dissipating "
            f"{dissipation:.1f}W at {resistance * 1e3:.1f}mohm"
            + ("" if within else f" - over the {TJ_MAX:.0f}C rating")
        ),
    )


def max_continuous_current(
    reference_temperature: float = 25.0,
    thermal_resistance: float = RTH_JC,
    duty: float = 1.0,
) -> float:
    """The current that puts the junction exactly at its maximum.

    At the limit the junction is at TJ(max) by definition, so the resistance is
    known and the arithmetic closes - the iteration in
    :func:`junction_temperature` is only needed below the limit.

    Args:
        reference_temperature: Case or ambient temperature, in Celsius.
        thermal_resistance: Junction to that reference, in C/W.
        duty: Fraction of the time the device conducts.

    Returns:
        The current, in amps. Zero when the reference is already at or above
        the maximum junction temperature.
    """
    headroom = TJ_MAX - reference_temperature
    if headroom <= 0:
        return 0.0
    dissipation = headroom / thermal_resistance
    return (dissipation / (duty * on_resistance(TJ_MAX))) ** 0.5


def power_dissipation_limit(case_temperature: float = 25.0) -> float:
    """The dissipation that puts the junction at its maximum.

    Args:
        case_temperature: Case temperature, in Celsius.

    Returns:
        The limit, in watts.
    """
    return max(0.0, (TJ_MAX - case_temperature) / RTH_JC)


def derating_factor() -> float:
    """How fast the dissipation limit falls with case temperature.

    Returns:
        Watts per Celsius.
    """
    return 1.0 / RTH_JC


def rating_inconsistency() -> str:
    """Describe the contradiction between the two published current ratings.

    Both are calculated the same way - the current that puts the junction at
    TJ(max) - so their ratio is fixed by the thermal headroom alone and cannot
    depend on anything else:

        ID(25) / ID(100) = sqrt((175 - 25) / (175 - 100)) = sqrt(2) = 1.414

    The published pair gives 110 / 80 = 1.375, which is 2.8% away from a ratio
    that has no freedom in it. No single on-resistance reproduces both.

    Taking each in turn implies a different resistance at 175C: 16.5 mohm from
    the 25C rating, 15.6 mohm from the 100C rating. Figure 4 says 17.6 mohm.
    All three disagree, and the pattern says why - the ratings were computed
    from a typical on-resistance, and the table publishes only a maximum. The
    model uses the maximum, so it predicts low, and that is the safe direction.

    Returns:
        The finding, in one paragraph.
    """
    implied_from_25 = PD_AT_25C / ID_AT_25C**2
    implied_from_100 = (TJ_MAX - 100.0) / RTH_JC / ID_AT_100C**2
    return (
        f"{DOCUMENT} rates 110A at TC = 25C and 80A at TC = 100C. Both are "
        f"the current that reaches TJ(max), so the ratio must be sqrt(2) and "
        f"the published pair gives 1.375. The 25C rating implies "
        f"{implied_from_25 * 1e3:.1f}mohm at 175C, the 100C rating implies "
        f"{implied_from_100 * 1e3:.1f}mohm, and Figure 4 gives "
        f"{on_resistance(TJ_MAX) * 1e3:.1f}mohm - because the table publishes "
        f"only a maximum on-resistance and the ratings were calculated from a "
        f"typical. This model uses the maximum and therefore predicts low."
    )


def gaps() -> List[str]:
    """What this model does not represent, and why.

    Returns:
        One line per gap.
    """
    return [
        "switching loss: the gate charge and capacitances are published but "
        "the model covers conduction only, so it under-reports total loss in "
        "anything switching fast",
        "transient thermal impedance: this is the steady state, and a device "
        "that survives a pulse can fail the same current continuously",
        "the on-resistance is the published maximum, and the ratings in the "
        "same document were calculated from a typical - see "
        "rating_inconsistency()",
        f"the datasheet's own footnote says the package cannot carry more "
        f"than {PACKAGE_LIMIT_CURRENT:.0f}A whatever the thermal calculation "
        f"gives, and this model does not apply that ceiling",
        f"outside {_CURVE_MIN:.0f}C to {_CURVE_MAX:.0f}C there is no "
        f"temperature coefficient in the document, and on_resistance() raises "
        f"rather than extrapolating",
        "body-diode conduction during dead time is not included",
    ]


def reference_points() -> List[ReferencePoint]:
    """The published values this model has to reproduce.

    The on-resistance at 25C is the one in-sample point - it is what the curve
    is normalised to, so reproducing it is arithmetic. The four ratings are
    not: they live on the first page, they were calculated rather than
    measured, and every one of them is a consequence of the temperature loop.

    Returns:
        The reference points.
    """
    return [
        ReferencePoint(
            quantity="on-resistance at TJ = 25C",
            expected=RDS_ON_25,
            unit=" ohm",
            source=f"{DOCUMENT} Electrical Characteristics",
            tolerance=0.02,
            conditions="VGS = 10V, ID = 62A",
            in_sample=True,
        ),
        ReferencePoint(
            quantity="power dissipation at TC = 25C",
            expected=PD_AT_25C,
            unit=" W",
            source=f"{DOCUMENT} Absolute Maximum Ratings",
            tolerance=0.05,
            conditions="TJ(max) = 175C",
            in_sample=False,
        ),
        ReferencePoint(
            quantity="linear derating factor",
            expected=DERATING_FACTOR,
            unit=" W/C",
            source=f"{DOCUMENT} Absolute Maximum Ratings",
            tolerance=0.05,
            conditions="above TC = 25C",
            in_sample=False,
        ),
        ReferencePoint(
            quantity="continuous drain current at TC = 25C",
            expected=ID_AT_25C,
            unit=" A",
            # 10% rather than 5%: the rating was calculated from a typical
            # on-resistance and the table publishes only a maximum, so the
            # model is systematically low by a knowable amount. Widening the
            # tolerance and saying why beats fitting to close the gap.
            tolerance=0.10,
            source=f"{DOCUMENT} Absolute Maximum Ratings",
            conditions="VGS = 10V, calculated at TJ(max)",
            in_sample=False,
        ),
        ReferencePoint(
            quantity="continuous drain current at TC = 100C",
            expected=ID_AT_100C,
            unit=" A",
            tolerance=0.10,
            source=f"{DOCUMENT} Absolute Maximum Ratings",
            conditions="VGS = 10V, calculated at TJ(max)",
            in_sample=False,
        ),
    ]


def check() -> ValidationReport:
    """Run the model against every published value.

    Returns:
        The report.
    """
    predictions = {
        "on-resistance at TJ = 25C": on_resistance(25.0),
        "power dissipation at TC = 25C": power_dissipation_limit(25.0),
        "linear derating factor": derating_factor(),
        "continuous drain current at TC = 25C": max_continuous_current(25.0),
        "continuous drain current at TC = 100C": max_continuous_current(100.0),
    }
    return validate("IRF3205", predictions, reference_points())
