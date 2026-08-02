# -*- coding: utf-8 -*-
"""The TPS7A49 low-noise LDO, as a model and as a claim about the real part.

Chosen as the worked example because TI publishes enough about it to check a
model rather than just build one: a full set of typical-characteristic curves,
a specification table with values at several operating points, and an output
noise figure that nothing in the rejection curve implies. That last one is what
makes this worth doing - the model is built from the rejection curve and the
regulation specs, and then asked to predict the noise, which it was not told.

Everything here cites SBVS121E (August 2010, revised May 2015). Where a number
was read off a plot rather than a table it says so, and carries the reading
accuracy, because a curve read by eye at 190 dpi is worth about two decibels
and pretending otherwise would put false precision into everything downstream.
"""

import logging
import math
from typing import Dict, List

from ..devices import Datasheet, LinearRegulator
from ..validation import ReferencePoint, ValidationReport, validate

logger = logging.getLogger(__name__)

DATASHEET = Datasheet(
    part="TPS7A49",
    document="SBVS121E",
    revision="E",
    notes=(
        "August 2010, revised May 2015. Typical values at TA = 25C. The "
        "rejection curve is Figure 14, COUT = 10uF, read by eye to about 2 dB."
    ),
)

# Figure 14, the COUT = 10uF trace: VOUT = 5V, VIN = 6.2V, IOUT = 150mA,
# CNR/SS = 10nF, CFF = 10nF. Read off a log-frequency plot, so each value is
# good to roughly +/-2 dB and the shape matters more than any single point.
#
# The dip near 100kHz and the peak just past it are the loop's own doing: the
# error amplifier has run out of gain and the output capacitor has not yet
# taken over. A model that smooths through them would look tidier and would
# mispredict exactly the frequencies a switching supply puts ripple at.
PSRR_CURVE: Dict[float, float] = {
    10: 65.0,
    20: 70.0,
    50: 69.0,
    100: 70.0,
    120: 71.0,
    200: 71.0,
    500: 72.0,
    1_000: 72.0,
    2_000: 72.0,
    5_000: 71.0,
    10_000: 70.0,
    20_000: 66.0,
    50_000: 58.0,
    100_000: 52.0,
    200_000: 62.0,
    500_000: 45.0,
    1_000_000: 30.0,
    2_000_000: 20.0,
    5_000_000: 10.0,
    10_000_000: 2.0,
}

# Table 6.5, Electrical Characteristics.
OUTPUT_VOLTAGE = 5.0
LOAD_REGULATION = 0.0004  # 0.04 %VOUT, 1mA <= IOUT <= 150mA, TJ = 25C
LINE_REGULATION = 0.00086  # 0.086 %VOUT, VOUT+1V <= VIN <= 35V, TJ = 25C
DROPOUT_AT_100MA = 0.260  # V, VIN = 95% VOUT(nom)
DROPOUT_AT_150MA = 0.333  # V, typical

# Figure 9, Dropout Voltage vs Output Current, the +25C trace. Read by eye to
# about 5 mV. The 100 mA and 150 mA points are deliberately left out: those two
# are quoted in Table 6.5 from a separate measurement, so leaving them out of
# the fit keeps them as an honest test of it.
DROPOUT_CURVE = {
    0.015: 0.100,
    0.030: 0.140,
    0.045: 0.168,
    0.060: 0.195,
    0.075: 0.220,
    0.090: 0.245,
    0.120: 0.292,
    0.135: 0.312,
}

# Fitted to DROPOUT_CURVE. The pass element is not a resistor: there is a knee
# of about 100 mV that appears within the first 10 mA and then a resistive
# slope. Treating it as a resistor - the obvious first model - reads 260 mV at
# 100 mA correctly and then overshoots 150 mA by 17%, because it has folded the
# knee into the slope.
DROPOUT_KNEE = 0.0995  # V, the pass element's own offset
DROPOUT_KNEE_CURRENT = 0.01064  # A, how quickly the knee comes in
DROPOUT_RESISTANCE = 1.593  # ohm, the slope once the knee is established
REFERENCE_VOLTAGE = 1.188  # V, typical at TJ = 25C
GROUND_CURRENT_100MA = 800e-6  # A
THERMAL_RESISTANCE_DGN = 63.4  # C/W, junction to ambient, HVSSOP PowerPAD

# The noise figure the model is asked to predict without being told it.
PUBLISHED_NOISE_RMS = 21.15e-6  # V, 10Hz to 100kHz, COUT = 10uF, CNR/SS = CFF = 10nF

# A low-noise LDO's output noise is dominated by its reference, filtered by the
# NR/SS capacitor. TI's own application note for this family gives the
# reference noise density; this is the one number here taken from a companion
# document rather than the datasheet, and it is flagged as such.
REFERENCE_NOISE_DENSITY = 15e-9  # V/rtHz above the NR/SS corner, SBVA033
NOISE_CORNER = 10.0  # Hz, where the NR/SS filter begins to act


def model(name: str = "U_LDO", input_net: str = "VIN", output_net: str = "VOUT"):
    """Build the regulator model.

    Args:
        name: Block name.
        input_net: Net on the input.
        output_net: Net on the output.

    Returns:
        The model, ready to drop into a co-simulation.
    """
    return LinearRegulator(
        name=name,
        input_net=input_net,
        output_net=output_net,
        datasheet=DATASHEET,
        output_voltage=OUTPUT_VOLTAGE,
        psrr_db=PSRR_CURVE,
        dropout=DROPOUT_AT_150MA,
        noise_rms=PUBLISHED_NOISE_RMS,
    )


def gaps() -> List[str]:
    """What this model does not represent, and why.

    Returns:
        One line per gap.
    """
    return [
        "load-step response: the datasheet gives a transient figure but not "
        "the loop bandwidth needed to reproduce its shape",
        "the reference noise density comes from SBVA033, a companion "
        "application note, not from the datasheet itself",
        "temperature: every value here is at TJ = 25C, and the dropout fit "
        "in particular moves with junction temperature",
        "start-up and NR/SS ramp timing are not modelled",
    ]


def predict_dropout(current: float) -> float:
    """Predict dropout voltage at a load.

    Fitted to Figure 9 rather than to the table, so the table's two dropout
    values stay available to judge it with.

    The form is a knee plus a slope. A pass element in dropout is not a
    resistor: it has an offset that appears within the first few milliamps and
    a resistive slope after it. Modelling it as a resistor fits whichever point
    it is anchored to and is 17% out at the other end of the range, which is
    the sort of error that looks like measurement noise and is not.

    Args:
        current: Load current, in amps.

    Returns:
        Dropout voltage, in volts.
    """
    knee = DROPOUT_KNEE * (1.0 - math.exp(-current / DROPOUT_KNEE_CURRENT))
    return knee + DROPOUT_RESISTANCE * current


def predict_output_noise(
    lower: float = 10.0, upper: float = 100_000.0, samples: int = 4000
) -> float:
    """Predict integrated output noise over a band.

    Built from the reference noise density and the NR/SS corner, integrated
    across the band and multiplied by the closed-loop gain from the reference
    to the output. Nothing in the rejection curve says what this should be, so
    getting it right is evidence the model is a model and not a lookup table.

    Args:
        lower: Bottom of the band, in hertz.
        upper: Top of the band, in hertz.
        samples: Integration steps, logarithmically spaced.

    Returns:
        Output noise, in volts RMS.
    """
    gain = OUTPUT_VOLTAGE / REFERENCE_VOLTAGE

    # Log-spaced trapezoidal integration of the density squared.
    total = 0.0
    log_low, log_high = math.log10(lower), math.log10(upper)
    step = (log_high - log_low) / samples

    previous_f = lower
    previous_density = _noise_density(lower)
    for index in range(1, samples + 1):
        frequency = 10 ** (log_low + index * step)
        density = _noise_density(frequency)
        width = frequency - previous_f
        total += 0.5 * (previous_density**2 + density**2) * width
        previous_f, previous_density = frequency, density

    return math.sqrt(total) * gain


def _noise_density(frequency: float) -> float:
    """Reference noise density at one frequency.

    Args:
        frequency: In hertz.

    Returns:
        Density in volts per root hertz.
    """
    # The NR/SS capacitor rolls the reference noise off below the corner; above
    # it the density is flat until the loop runs out of bandwidth.
    if frequency <= NOISE_CORNER:
        return REFERENCE_NOISE_DENSITY * (frequency / NOISE_CORNER)
    return REFERENCE_NOISE_DENSITY


def reference_points() -> List[ReferencePoint]:
    """The published values this model has to reproduce.

    Returns:
        The reference points, marked in or out of sample.
    """
    return [
        ReferencePoint(
            quantity="PSRR at 120 Hz",
            expected=72.0,
            unit=" dB",
            source="SBVS121E Table 6.5, Electrical Characteristics",
            tolerance=0.05,
            conditions="CNR/SS = CFF = 10nF",
            in_sample=False,  # the table, not the curve the model was built on
        ),
        ReferencePoint(
            quantity="PSRR at 1 kHz",
            expected=72.0,
            unit=" dB",
            source="SBVS121E Figure 14, COUT = 10uF",
            tolerance=0.05,
            conditions="VOUT = 5V, VIN = 6.2V, IOUT = 150mA",
            in_sample=True,
        ),
        ReferencePoint(
            quantity="dropout at 100 mA",
            expected=DROPOUT_AT_100MA,
            unit=" V",
            source="SBVS121E Table 6.5, VDO",
            tolerance=0.05,
            conditions="VIN = 95% VOUT(nom)",
            in_sample=False,  # the fit is to Figure 9, which excludes this point
        ),
        ReferencePoint(
            quantity="dropout at 150 mA",
            expected=DROPOUT_AT_150MA,
            unit=" V",
            source="SBVS121E Table 6.5, VDO",
            tolerance=0.05,
            conditions="VIN = 95% VOUT(nom)",
            in_sample=False,
        ),
        ReferencePoint(
            quantity="output noise 10Hz-100kHz",
            expected=PUBLISHED_NOISE_RMS,
            unit=" V",
            source="SBVS121E Table 6.5, output noise voltage",
            tolerance=0.25,
            conditions="VIN = 6.2V, VOUT = 5V, COUT = 10uF, CNR/SS = CFF = 10nF",
            in_sample=False,  # nothing in the rejection curve implies this
        ),
        ReferencePoint(
            quantity="load regulation 1-150 mA",
            expected=LOAD_REGULATION * OUTPUT_VOLTAGE,
            unit=" V",
            source="SBVS121E Table 6.5, load regulation",
            tolerance=0.05,
            conditions="TJ = 25C",
            in_sample=True,
        ),
    ]


def check() -> ValidationReport:
    """Run the model against every published value.

    Returns:
        The report.
    """
    regulator = model()
    predictions = {
        "PSRR at 120 Hz": regulator.rejection_at(120.0),
        "PSRR at 1 kHz": regulator.rejection_at(1_000.0),
        "dropout at 100 mA": predict_dropout(0.100),
        "dropout at 150 mA": predict_dropout(0.150),
        "output noise 10Hz-100kHz": predict_output_noise(),
        "load regulation 1-150 mA": LOAD_REGULATION * OUTPUT_VOLTAGE,
    }
    return validate("TPS7A49", predictions, reference_points())
