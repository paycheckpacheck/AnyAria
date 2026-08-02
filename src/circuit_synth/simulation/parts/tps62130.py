# -*- coding: utf-8 -*-
"""The TPS62130 synchronous buck converter, and the limit of this method.

The third worked example, and the one that finds where building a model purely
from a datasheet stops working.

Efficiency is the sum of three losses that trade places across the load range:
conduction, which grows as the square of current; switching, which is roughly
constant; and quiescent, which only matters when nothing else does. A model
that reproduces the shape has captured all three, so it is a good test.

The catch is that an integrated converter does not publish what the switching
loss needs. A discrete design would give gate charge and switching times; here
the FETs are inside the part and TI publishes neither. So exactly one
coefficient has to be fitted, and the question becomes whether it was fitted to
a real mechanism or to the shape of one curve.

That is answerable. It is fitted at 2.5MHz and then asked to predict the 1.25MHz
curve - the same silicon at half the switching frequency. If the coefficient
stands for switching loss it must halve, and the prediction must follow. It
does, to within the accuracy the curve can be read to.

Everything cites SLVSAG7F (November 2011, revised November 2021).
"""

import logging
from typing import Dict, List

from ..validation import ReferencePoint, ValidationReport, validate

logger = logging.getLogger(__name__)

DOCUMENT = "SLVSAG7F"

# Table 6.5, Electrical Characteristics.
R_HIGH_SIDE = 0.090  # ohm, VIN >= 6V
R_LOW_SIDE = 0.040  # ohm, VIN >= 6V
QUIESCENT_CURRENT = 17e-6  # A, EN high, IOUT = 0, not switching

# The inductor is not part of the IC, and the efficiency curves were measured
# with one. Section 9.2.2 of the typical application: 2.2uH, and 50 mohm is
# representative of that part in that size. This is the one number here from
# neither the table nor a figure, and it is flagged as such in the gaps.
INDUCTOR_DCR = 0.050  # ohm

# Figures 9-6 and 9-4, VOUT = 5V, VIN = 12V, read by eye to about 1.5 points.
# Only the PWM region is included. Below roughly 0.3A the converter is in
# power-save mode, where the switching frequency falls with load and is not the
# nominal figure the curve is labelled with - so those points describe a
# different circuit and modelling them as if they did not would be wrong.
EFFICIENCY_2M5 = {0.5: 87.0, 1.0: 92.0, 2.0: 93.3, 3.0: 91.0}
EFFICIENCY_1M25 = {0.5: 91.5, 1.0: 93.0, 2.0: 94.0, 3.0: 92.0}

# Fitted to EFFICIENCY_2M5 only. Stands for everything lost per switching
# cycle: gate drive, the overlap while a FET transitions, and the dead-time
# body-diode conduction. None of the three is published for an integrated
# converter, so this is the boundary of what the datasheet supports.
SWITCHING_ENERGY = 136.1e-9  # J per cycle, at VIN = 12V


def efficiency(
    output_current: float,
    switching_frequency: float,
    input_voltage: float = 12.0,
    output_voltage: float = 5.0,
) -> float:
    """Predict efficiency in continuous conduction.

    Args:
        output_current: Load current, in amps. Below about 0.3A the part is in
            power-save mode and this does not apply.
        switching_frequency: Nominal switching frequency, in hertz.
        input_voltage: Input voltage, in volts.
        output_voltage: Output voltage, in volts.

    Returns:
        Efficiency as a percentage.
    """
    duty = output_voltage / input_voltage

    conduction = output_current**2 * (
        duty * R_HIGH_SIDE + (1.0 - duty) * R_LOW_SIDE
    )
    inductor = output_current**2 * INDUCTOR_DCR
    switching = SWITCHING_ENERGY * switching_frequency
    quiescent = input_voltage * QUIESCENT_CURRENT

    delivered = output_voltage * output_current
    lost = conduction + inductor + switching + quiescent
    return 100.0 * delivered / (delivered + lost)


def continuous_conduction_floor(
    inductance: float = 2.2e-6,
    switching_frequency: float = 2.5e6,
    input_voltage: float = 12.0,
    output_voltage: float = 5.0,
) -> float:
    """The load below which the converter leaves continuous conduction.

    Below this the part enters power-save mode, its switching frequency falls
    with load, and :func:`efficiency` no longer describes it.

    Args:
        inductance: Output inductor, in henries.
        switching_frequency: Nominal switching frequency, in hertz.
        input_voltage: Input voltage, in volts.
        output_voltage: Output voltage, in volts.

    Returns:
        The boundary current, in amps.
    """
    duty = output_voltage / input_voltage
    ripple = (input_voltage - output_voltage) * duty / (inductance * switching_frequency)
    return ripple / 2.0


def gaps() -> List[str]:
    """What this model does not represent, and why.

    Returns:
        One line per gap.
    """
    return [
        "power-save mode below about 0.3A: the switching frequency falls with "
        "load and the datasheet does not give the law",
        "the switching-loss coefficient is fitted, because gate charge and "
        "switching times are not published for an integrated converter",
        "the inductor's DCR is assumed from the typical application, not "
        "measured, and it is an external part the curve depended on",
        "temperature: every value here is at 25C",
    ]


def reference_points() -> List[ReferencePoint]:
    """The published values this model has to reproduce.

    The 2.5MHz points are in sample - the switching coefficient was fitted to
    them. The 1.25MHz points are not, and they are the ones that matter: the
    same silicon at half the frequency, where a coefficient standing for a real
    per-cycle loss must halve and a coefficient standing for curve shape will
    not.

    Returns:
        The reference points.
    """
    points: List[ReferencePoint] = []
    for current, published in EFFICIENCY_2M5.items():
        points.append(
            ReferencePoint(
                quantity=f"efficiency {current:g}A at 2.5MHz",
                expected=published,
                unit="%",
                source=f"{DOCUMENT} Figure 9-6, VOUT = 5V, VIN = 12V",
                tolerance=0.03,
                conditions="TA = 25C, PWM",
                in_sample=True,
            )
        )
    for current, published in EFFICIENCY_1M25.items():
        points.append(
            ReferencePoint(
                quantity=f"efficiency {current:g}A at 1.25MHz",
                expected=published,
                unit="%",
                source=f"{DOCUMENT} Figure 9-4, VOUT = 5V, VIN = 12V",
                # The curve reads to about 1.5 points, so 3% of a 90% figure is
                # the accuracy of the source rather than a loose claim.
                tolerance=0.03,
                conditions="TA = 25C, PWM",
                in_sample=False,
            )
        )
    return points


def check() -> ValidationReport:
    """Run the model against both published efficiency curves.

    Returns:
        The report.
    """
    predictions: Dict[str, float] = {}
    for current in EFFICIENCY_2M5:
        predictions[f"efficiency {current:g}A at 2.5MHz"] = efficiency(current, 2.5e6)
    for current in EFFICIENCY_1M25:
        predictions[f"efficiency {current:g}A at 1.25MHz"] = efficiency(current, 1.25e6)
    return validate("TPS62130", predictions, reference_points())
