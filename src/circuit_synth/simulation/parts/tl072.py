# -*- coding: utf-8 -*-
"""The TL072H JFET-input op-amp, as a model and as a claim about the real part.

The second worked example, chosen to test the procedure on behaviour the first
one could not reach. The LDO was checked on DC values and a frequency-domain
lookup; an op-amp's interesting behaviour is in the time domain, where a model
either reproduces a step response or it does not.

It is also a good test of "build from one set of numbers, judge with another".
Everything the model is built from - gain-bandwidth, slew rate, phase margin,
open-loop gain - lives in one part of the table. The four settling times it is
judged against live in another and follow from all four at once, so getting
them right cannot be arithmetic.

The model has **no fitted parameters**. Every number is read from the table.

One finding is recorded here rather than smoothed over: two of the published
settling times contradict each other, and the model's largest error is against
one of that pair. See :func:`inconsistency`.
"""

import logging
from typing import List

from ..devices import Datasheet, OpAmp
from ..validation import ReferencePoint, ValidationReport, validate

logger = logging.getLogger(__name__)

DATASHEET = Datasheet(
    part="TL072H",
    document="SLOS080",
    revision="AA",
    notes=(
        "Operating Characteristics, VS = 40V, TA = 25C. The settling times are "
        "all quoted at G = +1 with CL = 20pF, which is also the condition the "
        "phase margin is quoted at - so the four of them describe one circuit."
    ),
)

# Everything the model is built from. All from the specification table.
GAIN_BANDWIDTH = 5.25e6  # Hz, GBW
SLEW_RATE = 20e6  # V/s, VS = 40V, G = +1, CL = 20pF
PHASE_MARGIN = 56.0  # degrees, G = +1, RL = 10k, CL = 20pF
OPEN_LOOP_GAIN_DB = 120.0  # dB, typical
SUPPLY = 40.0  # V

# What the model is judged against. A different part of the same table, and a
# consequence of all four numbers above rather than any one of them.
SETTLING = {
    (10.0, 1e-3): 0.63e-6,
    (2.0, 1e-3): 0.56e-6,
    (10.0, 1e-4): 0.91e-6,
    (2.0, 1e-4): 0.48e-6,
}


def model(name: str = "U_OPAMP", closed_loop_gain: float = 1.0) -> OpAmp:
    """Build the op-amp model.

    Args:
        name: Block name.
        closed_loop_gain: The gain it is being used at. The published settling
            times are all at unity.

    Returns:
        The model, ready to drop into a co-simulation.
    """
    return OpAmp(
        name=name,
        positive="IN+",
        negative="IN-",
        output="OUT",
        datasheet=DATASHEET,
        gain_bandwidth=GAIN_BANDWIDTH,
        slew_rate=SLEW_RATE,
        phase_margin=PHASE_MARGIN,
        open_loop_gain_db=OPEN_LOOP_GAIN_DB,
        supply=SUPPLY,
        closed_loop_gain=closed_loop_gain,
    )


def inconsistency() -> str:
    """Describe the contradiction in the published settling times.

    A tighter tolerance cannot be reached sooner than a looser one: the output
    has to pass through the 0.1% band on its way into the 0.01% band. The table
    says otherwise for the 2V step - 0.48us to 0.01% against 0.56us to 0.1% -
    so at least one of those two numbers is wrong, and no model can match both.

    This is recorded rather than fitted around. A model tuned until it
    reproduced both would be tuned to reproduce an impossibility, and would be
    worse everywhere else for it.

    Returns:
        The finding, in one paragraph.
    """
    return (
        "SLOS080 Operating Characteristics quotes settling to 0.01% for a 2V "
        "step as 0.48us and settling to 0.1% for the same step as 0.56us. The "
        "output cannot enter the tighter band before the looser one, so one of "
        "these is wrong. The model is not fitted to either; the 0.1% figure is "
        "where its largest error falls."
    )


def gaps() -> List[str]:
    """What this model does not represent, and why.

    Returns:
        One line per gap.
    """
    return [
        "input offset and bias current: modelled as ideal, so the model says "
        "nothing about DC accuracy in a high-impedance divider",
        "noise: the datasheet gives a voltage noise density but the model "
        "does not carry it, so this is not a noise model",
        "output loading: every published figure is at RL = 10k and CL = 20pF, "
        "and a heavier load changes both the phase margin and the slew limit",
        "the published 2V settling times contradict each other; see "
        "inconsistency()",
        "temperature: every value here is at TA = 25C",
    ]


def reference_points() -> List[ReferencePoint]:
    """The published values this model has to reproduce.

    Returns:
        The reference points. All four are out of sample - the model is built
        from gain-bandwidth, slew rate, phase margin and open-loop gain, and
        none of those is a settling time.
    """
    points = []
    for (step, tolerance), published in SETTLING.items():
        contradicted = (step, tolerance) == (2.0, 1e-3)
        points.append(
            ReferencePoint(
                quantity=f"settling {step:g}V to {tolerance * 100:g}%",
                expected=published,
                unit=" s",
                source="SLOS080 Operating Characteristics, tS",
                # Wider on the contradicted point, and said out loud rather
                # than quietly loosened: it is checked against a number that
                # disagrees with its neighbour.
                tolerance=0.35 if contradicted else 0.15,
                conditions="VS = 40V, G = +1, CL = 20pF",
                in_sample=False,
            )
        )
    return points


def check() -> ValidationReport:
    """Run the model against every published settling time.

    Returns:
        The report.
    """
    amplifier = model()
    predictions = {
        f"settling {step:g}V to {tolerance * 100:g}%": amplifier.settling_time(
            step, tolerance
        )
        for (step, tolerance) in SETTLING
    }
    return validate("TL072H", predictions, reference_points())
