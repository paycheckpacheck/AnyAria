"""Building a power MOSFET model out of datasheet parameters, and checking it.

Manufacturers publish SPICE models for some parts and not others. When there
is no model the choice is between not simulating and building one, and a built
model is defensible only if it is fitted to the datasheet's own numbers and
then checked against them.

ngspice's ``vdmos`` primitive is designed for exactly this. Its parameters map
onto quantities a power MOSFET datasheet actually publishes - threshold
voltage, transconductance, the three capacitances, the body diode - so the
model is mostly a transcription rather than a curve fit. The one parameter that
is not published is the drain resistance ``RD``, because the datasheet quotes
the *total* on-resistance including the channel. :func:`fit_drain_resistance`
solves for it by running the model at the datasheet's own test point and
bisecting until the two agree.

What this buys and what it does not is worth being precise about, because a
model that is right about one thing and wrong about another is the most
dangerous kind:

* **Conduction is trustworthy.** After fitting, the model reproduces the
  datasheet's on-resistance at its stated test point by construction, and
  :func:`validate_card` re-measures it to prove the fit took.
* **Switching is approximate.** The capacitances are single-point values from
  the datasheet, and real MOSFET capacitance varies by an order of magnitude
  over the drain voltage swing. Edge timing from this model is indicative, not
  a number to quote.
* **Temperature is absent.** A datasheet that gives on-resistance at one
  temperature - which most do - contains no information from which a
  temperature coefficient can be derived. The model runs at one temperature
  and says nothing about any other.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Where to look for the on-resistance fit. No power MOSFET has a total
# on-resistance outside this range, and bracketing it keeps the bisection
# honest about failing rather than converging on an endpoint.
_RD_SEARCH_RANGE = (0.0, 10.0)
_BISECTION_STEPS = 32


@dataclass(frozen=True)
class VdmosParameters:
    """The datasheet numbers an ngspice ``vdmos`` model is built from.

    Every field here is one a power MOSFET datasheet publishes, so a model
    built from it can be checked line by line against the document.

    Attributes:
        name: Model name, normally the part number.
        vto: Gate threshold voltage VGS(th), in volts. Datasheets give a wide
            min-to-max band; the midpoint is the usual choice and the spread
            should be reported as a limit on the result.
        kp: Transconductance parameter, in A/V^2. The forward transconductance
            gfs is the datasheet figure that maps onto it.
        rds_on: Total on-resistance at the test point, in ohms.
        rds_on_vgs: Gate voltage the on-resistance is quoted at, in volts.
        rds_on_id: Drain current the on-resistance is quoted at, in amps.
        vds_max: Drain-source breakdown voltage, in volts.
        ciss: Input capacitance, in farads.
        coss: Output capacitance, in farads.
        crss: Reverse transfer capacitance, in farads.
        rs: Source resistance, in ohms. Rarely published; the default is a
            small fraction of the on-resistance and is absorbed by the fit.
        rg: Internal gate resistance, in ohms. Rarely published.
        body_diode_is: Body diode saturation current, in amps.
        body_diode_rb: Body diode series resistance, in ohms.
    """

    name: str
    vto: float
    kp: float
    rds_on: float
    rds_on_vgs: float
    rds_on_id: float
    vds_max: float
    ciss: float
    coss: float
    crss: float
    rs: float = 0.0025
    rg: float = 1.5
    body_diode_is: float = 1e-12
    body_diode_rb: float = 0.002

    @property
    def cgs(self) -> float:
        """Gate-source capacitance implied by the datasheet capacitances.

        Datasheets give Ciss = Cgs + Cgd, so Cgs is the difference.

        Returns:
            The capacitance in farads.
        """
        return self.ciss - self.crss

    @property
    def cjo(self) -> float:
        """Drain-source junction capacitance implied by the datasheet.

        Datasheets give Coss = Cds + Cgd, so Cds is the difference.

        Returns:
            The capacitance in farads.
        """
        return self.coss - self.crss


def build_card(
    parameters: VdmosParameters,
    drain_resistance: float,
    channel: str = "nchan",
) -> str:
    """Write an ngspice ``.model`` card for a power MOSFET.

    Args:
        parameters: The datasheet numbers.
        drain_resistance: The fitted drain resistance, in ohms. Use
            :func:`fit_drain_resistance` rather than guessing.
        channel: ``"nchan"`` or ``"pchan"``.

    Returns:
        The model card, one line, ending in a newline.
    """
    # CGDMIN is the reverse transfer capacitance at high drain voltage, where
    # it is far below the quoted low-voltage figure. A quarter is the shape of
    # the curve on a typical power MOSFET; it is an approximation and the
    # model's switching behaviour is only as good as it.
    return (
        f".model {parameters.name} vdmos {channel} "
        f"VTO={parameters.vto:g} KP={parameters.kp:g} "
        f"RD={drain_resistance:.6g} RS={parameters.rs:g} RG={parameters.rg:g} "
        f"Vds={parameters.vds_max:g} "
        f"Cgs={parameters.cgs:.4g} "
        f"CGDMAX={parameters.crss:.4g} CGDMIN={parameters.crss / 4:.4g} "
        f"Cjo={parameters.cjo:.4g} "
        f"IS={parameters.body_diode_is:g} Rb={parameters.body_diode_rb:g} "
        f"Ksubthres=0.1\n"
    )


def measure_rds_on(card: str, name: str, vgs: float, current: float) -> float:
    """Measure a model's on-resistance by simulating its own test point.

    Args:
        card: The ``.model`` card.
        name: The model name, as it appears in the card.
        vgs: Gate voltage to hold, in volts.
        current: Drain current to force, in amps.

    Returns:
        The on-resistance in ohms.

    Raises:
        SimulationUnavailable: If ngspice cannot be loaded.
        SimulationFailed: If the run produced no result.
    """
    from .ngspice_run import run_transient

    deck = (
        ".title on-resistance measurement\n"
        f"{card}"
        f"Vgate gate 0 DC {vgs:g}\n"
        f"Idrain drain 0 DC {-current:g}\n"
        f"M1 drain gate 0 {name}\n"
        # A short transient rather than an operating point, because the
        # transient solver is what the design will actually be simulated with
        # and any convergence trouble should show up here.
        ".tran 1u 10u\n"
        ".end\n"
    )
    waveforms = run_transient(deck)
    return float(waveforms.signal("drain")[-1]) / current


def fit_drain_resistance(
    parameters: VdmosParameters,
    channel: str = "nchan",
    tolerance: float = 1e-4,
) -> float:
    """Solve for the drain resistance that reproduces the datasheet.

    The datasheet quotes a total on-resistance, of which the channel is part.
    The channel's contribution depends on the threshold voltage and
    transconductance in a way that is not worth deriving analytically, so this
    bisects the drain resistance until the simulated on-resistance matches the
    quoted one at its own test point.

    Args:
        parameters: The datasheet numbers.
        channel: ``"nchan"`` or ``"pchan"``.
        tolerance: Relative agreement to stop at.

    Returns:
        The drain resistance in ohms.

    Raises:
        ValueError: If no drain resistance reproduces the datasheet. That
            means the threshold and transconductance alone already account for
            more than the quoted on-resistance, so the model cannot represent
            the part and the numbers should be re-read from the document.
    """
    low, high = _RD_SEARCH_RANGE

    # With RD at zero the channel alone sets the on-resistance. If that is
    # already too high, no value of RD will help.
    floor = measure_rds_on(
        build_card(parameters, low, channel),
        parameters.name,
        parameters.rds_on_vgs,
        parameters.rds_on_id,
    )
    if floor > parameters.rds_on * (1 + tolerance):
        raise ValueError(
            f"{parameters.name}: the channel alone gives {floor * 1e3:.2f} mOhm, "
            f"already above the datasheet's {parameters.rds_on * 1e3:.2f} mOhm. "
            f"Check VTO and KP against the datasheet - the model cannot "
            f"represent this part as parameterised."
        )

    for _ in range(_BISECTION_STEPS):
        middle = (low + high) / 2
        measured = measure_rds_on(
            build_card(parameters, middle, channel),
            parameters.name,
            parameters.rds_on_vgs,
            parameters.rds_on_id,
        )
        if abs(measured - parameters.rds_on) <= parameters.rds_on * tolerance:
            low = high = middle
            break
        if measured > parameters.rds_on:
            high = middle
        else:
            low = middle

    fitted = (low + high) / 2
    logger.info(
        "%s: fitted RD = %.4f mOhm to match datasheet Rds(on) = %.2f mOhm "
        "at VGS=%gV, ID=%gA",
        parameters.name,
        fitted * 1e3,
        parameters.rds_on * 1e3,
        parameters.rds_on_vgs,
        parameters.rds_on_id,
    )
    return fitted


@dataclass(frozen=True)
class FittedModel:
    """A model card fitted to a datasheet, with the check that proves it.

    Attributes:
        card: The ``.model`` card.
        name: The model name.
        drain_resistance: The fitted drain resistance, in ohms.
        measured_rds_on: On-resistance measured back out of the fitted model.
        datasheet_rds_on: What the datasheet says it should be.
        limits: What the model is not evidence for.
    """

    card: str
    name: str
    drain_resistance: float
    measured_rds_on: float
    datasheet_rds_on: float
    limits: str

    @property
    def error(self) -> float:
        """Relative disagreement between the model and the datasheet.

        Returns:
            The fractional error in on-resistance.
        """
        return abs(self.measured_rds_on - self.datasheet_rds_on) / self.datasheet_rds_on

    def summary(self) -> str:
        """Write the report line for this model.

        Returns:
            A short description of the fit and its limits.
        """
        return (
            f"{self.name}: Rds(on) {self.measured_rds_on * 1e3:.2f} mOhm "
            f"vs datasheet {self.datasheet_rds_on * 1e3:.2f} mOhm "
            f"({self.error * 100:.1f}% error). {self.limits}"
        )


def fit(parameters: VdmosParameters, channel: str = "nchan") -> FittedModel:
    """Build a model card from datasheet parameters and verify it.

    Args:
        parameters: The datasheet numbers.
        channel: ``"nchan"`` or ``"pchan"``.

    Returns:
        The fitted model, carrying the measurement that shows the fit took.

    Raises:
        ValueError: If the fit did not converge, or if the fitted model does
            not reproduce the datasheet's on-resistance to within 1%. A model
            that cannot match the one number it was fitted to must not be used
            to produce figures for a schematic.
    """
    drain_resistance = fit_drain_resistance(parameters, channel)
    card = build_card(parameters, drain_resistance, channel)
    measured = measure_rds_on(
        card, parameters.name, parameters.rds_on_vgs, parameters.rds_on_id
    )

    model = FittedModel(
        card=card,
        name=parameters.name,
        drain_resistance=drain_resistance,
        measured_rds_on=measured,
        datasheet_rds_on=parameters.rds_on,
        limits=(
            "Conduction is fitted to the datasheet test point. Switching is "
            "approximate: the capacitances are single-point values and the "
            "real ones vary strongly with drain voltage. No temperature "
            "dependence."
        ),
    )

    if model.error > 0.01:
        raise ValueError(
            f"the fitted model reproduces Rds(on) to only {model.error * 100:.1f}%, "
            f"which is not close enough to base annotations on. Re-check VTO, "
            f"KP and the on-resistance test conditions against the datasheet."
        )

    logger.info("Fitted model: %s", model.summary())
    return model
