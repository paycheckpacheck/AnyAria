"""Turning circuit-synth components into the SPICE properties KiCad reads.

KiCad's built-in simulator does not read a netlist you hand it. It builds one
from properties on the symbols: ``Sim.Device`` says what kind of element the
part is, ``Sim.Pins`` says which symbol pin is which model terminal, and either
``Sim.Params`` carries the value inline or ``Sim.Library``/``Sim.Name`` point at
a model card in a file. Get those right and ``Simulate -> Probe`` works on the
generated sheet with nothing else to do; get them wrong and the part silently
drops out of the netlist.

Two things here are deliberate.

The first is that values are emitted as plain numbers. SPICE reads ``M`` as
milli and ``MEG`` as mega, which is the opposite of what an engineer writing
``4M7`` means, and a resistor that is a million times off is the kind of error
a simulation will happily run to completion with. :func:`parse_value` reads the
component value with the conventions a schematic uses and writes back an
unambiguous number.

The second is that a part with no model is a reported gap, never a guess. A
gate driver modelled as "probably close enough to an ideal buffer" produces
waveforms that look entirely plausible and are wrong about exactly the thing
somebody would run the simulation to find out. :func:`assign_models` returns
the gaps alongside the assignments so the caller has to deal with them.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

logger = logging.getLogger(__name__)

# Engineering suffixes as a schematic uses them, not as SPICE reads them.
# "M" is mega here because that is what somebody writing "4M7" on a drawing
# means; the value is converted to a bare number before it reaches SPICE.
_MULTIPLIERS: Mapping[str, float] = {
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "µ": 1e-6,  # micro sign
    "μ": 1e-6,  # Greek mu
    "m": 1e-3,
    "": 1.0,
    "k": 1e3,
    "K": 1e3,
    "M": 1e6,
    "G": 1e9,
}

# "100nF", "4k7", "10R", "5mR", "220uF/50V". The unit letter is optional and
# the multiplier may sit where the decimal point goes, which is the old
# drafting convention that survives because it cannot be lost to a bad
# photocopy.
_VALUE_PATTERN = re.compile(
    r"^\s*(\d*)(?:[.,](\d+))?\s*"
    r"([pnuµμmkKMG]?)\s*"
    r"(?:(\d+)\s*)?"
    r"(R|Ohm|ohm|Ω|F|H|A|V)?\s*$"
)

# The KiCad symbols whose SPICE element is unambiguous from the symbol alone.
PASSIVE_DEVICES: Mapping[str, Tuple[str, str]] = {
    "Device:R": ("R", "r"),
    "Device:R_Small": ("R", "r"),
    "Device:R_Shunt": ("R", "r"),
    "Device:C": ("C", "c"),
    "Device:C_Small": ("C", "c"),
    "Device:C_Polarized": ("C", "c"),
    "Device:L": ("L", "l"),
    "Device:L_Small": ("L", "l"),
}

# Two-terminal passives are all wired the same way round in KiCad's libraries.
PASSIVE_PINS = "1=+ 2=-"


class ValueError_(ValueError):
    """Raised when a component value cannot be read as a number."""


@dataclass(frozen=True)
class ModelSpec:
    """A SPICE model for a part the symbol alone does not describe.

    Anything that is not a plain resistor, capacitor or inductor needs one of
    these supplied explicitly, because guessing is what this module exists to
    prevent.

    Attributes:
        device: The ``Sim.Device`` value, such as ``"NMOS"``, ``"D"`` or
            ``"V"``.
        pins: The ``Sim.Pins`` value mapping symbol pin numbers to model
            terminals, such as ``"1=G 2=D 3=S"``. Getting this wrong wires the
            part into the simulation back to front and is not detectable from
            the waveforms.
        type: The ``Sim.Type`` value, such as ``"VDMOS"`` or ``"PULSE"``.
        library: Path to a model file, relative to the schematic, when the
            model lives in one.
        name: The model card's name inside that file.
        params: Inline parameters, such as
            ``"y1=0 y2=12 td=0 tr=50n tf=50n tw=20u per=50u"``.
        source: Where the model came from, for the report. A model file
            downloaded from the manufacturer should say so here.
    """

    device: str
    pins: str
    type: str = ""
    library: str = ""
    name: str = ""
    params: str = ""
    source: str = ""

    def properties(self) -> Dict[str, str]:
        """Render this model as the KiCad symbol properties that carry it.

        Returns:
            A mapping of property name to value, ready to be written into a
            ``(symbol ...)`` block. Empty fields are left out.
        """
        fields = {
            "Sim.Device": self.device,
            "Sim.Type": self.type,
            "Sim.Pins": self.pins,
            "Sim.Library": self.library,
            "Sim.Name": self.name,
            "Sim.Params": self.params,
        }
        return {key: value for key, value in fields.items() if value}


@dataclass(frozen=True)
class Assignment:
    """The SPICE properties to write onto one symbol.

    Attributes:
        reference: The reference designator, such as ``"Q1"``.
        properties: Property name to value, such as ``{"Sim.Device": "R"}``.
        value_field: What the symbol's ``Value`` property should become, or
            None to leave it alone. KiCad shows ``${SIM.PARAMS}`` on passives
            so the displayed value and the simulated value cannot drift apart.
        note: One line for the report describing what was assigned.
    """

    reference: str
    properties: Mapping[str, str]
    value_field: Optional[str] = None
    note: str = ""


@dataclass(frozen=True)
class ModelGap:
    """A part that could not be given a SPICE model.

    Attributes:
        reference: The reference designator.
        symbol: The KiCad library id, such as ``"Driver_FET:IR2101"``.
        reason: Why no model could be assigned, in plain language.
    """

    reference: str
    symbol: str
    reason: str

    def __str__(self) -> str:
        """Render the gap for a report.

        Returns:
            A one-line description.
        """
        return f"{self.reference} ({self.symbol}): {self.reason}"


def parse_value(text: str) -> float:
    """Read a schematic component value as a number.

    Handles the suffix forms a schematic uses - ``"100nF"``, ``"4k7"``,
    ``"10R"``, ``"5mR"`` - and drops a voltage or tolerance rating after a
    slash, so ``"220uF/50V"`` reads as 220 microfarads.

    Args:
        text: The value as written on the component, such as ``"100nF"``.

    Returns:
        The value in base SI units - ohms, farads or henries.

    Raises:
        ValueError_: If the text cannot be read as a number. Callers must
            treat this as a gap rather than substituting a default.
    """
    if not isinstance(text, str):
        raise ValueError_(f"value {text!r} is not a string")

    # "220uF/50V" - the rating after the slash is not part of the value.
    head = text.split("/")[0].strip()

    match = _VALUE_PATTERN.match(head)
    if not match:
        raise ValueError_(f"cannot read {text!r} as a component value")

    whole, decimal, multiplier, after, _unit = match.groups()

    if not whole and not decimal:
        raise ValueError_(f"cannot read {text!r} as a component value")

    if after:
        # "4k7" means 4.7k: the multiplier stands in for the decimal point.
        if decimal:
            raise ValueError_(f"{text!r} has both a decimal point and a suffix digit")
        number = float(f"{whole}.{after}")
    else:
        number = float(f"{whole or '0'}.{decimal or '0'}")

    return number * _MULTIPLIERS[multiplier]


def passive_assignment(reference: str, symbol: str, value: str) -> Optional[Assignment]:
    """Build the SPICE properties for a resistor, capacitor or inductor.

    Args:
        reference: The reference designator, such as ``"R1"``.
        symbol: The KiCad library id, such as ``"Device:R"``.
        value: The component value as written, such as ``"10k"``.

    Returns:
        The assignment, or None when the symbol is not a plain passive.

    Raises:
        ValueError_: If the symbol is a passive but its value cannot be read.
    """
    if symbol not in PASSIVE_DEVICES:
        return None

    device, parameter = PASSIVE_DEVICES[symbol]
    number = parse_value(value)
    # A repr rather than the original string: SPICE would read the "m" in
    # "5mR" as milli and the "M" in "4M7" as milli too, which is a factor of
    # a billion on the second one.
    params = f"{parameter}={number:.6g}"

    return Assignment(
        reference=reference,
        properties={
            "Sim.Device": device,
            "Sim.Type": "=",
            "Sim.Pins": PASSIVE_PINS,
            "Sim.Params": params,
        },
        # KiCad substitutes the parameters into the displayed value, so what
        # is drawn and what is simulated cannot disagree.
        value_field="${SIM.PARAMS}",
        note=f"{device} {params} from value {value!r}",
    )


def assign_models(
    components: Iterable,
    specs: Optional[Mapping[str, ModelSpec]] = None,
    excluded: Iterable[str] = (),
) -> Tuple[List[Assignment], List[ModelGap]]:
    """Work out the SPICE properties for every component in a block.

    Passives are handled from their symbol and value. Everything else needs an
    explicit :class:`ModelSpec`, and anything left over is returned as a gap
    rather than being approximated.

    Args:
        components: The circuit-synth ``Component`` objects to assign. Each
            must have ``ref``, ``symbol`` and ``value`` attributes.
        specs: Explicit models, keyed by reference designator.
        excluded: References that are deliberately left out of the
            simulation - a programming header, a test point - and so are not
            gaps. They are marked ``exclude_from_sim`` instead.

    Returns:
        A ``(assignments, gaps)`` pair. The gaps are the parts that would
        silently vanish from the simulation, and the caller must decide
        whether the remaining circuit is still worth simulating.
    """
    specs = dict(specs or {})
    excluded = set(excluded)
    assignments: List[Assignment] = []
    gaps: List[ModelGap] = []

    for component in components:
        reference = component.ref
        symbol = component.symbol

        if reference in excluded:
            logger.debug("%s excluded from simulation by request", reference)
            continue

        spec = specs.get(reference)
        if spec is not None:
            assignments.append(
                Assignment(
                    reference=reference,
                    properties=spec.properties(),
                    note=f"{spec.device} model{' ' + spec.name if spec.name else ''}"
                    f"{' from ' + spec.source if spec.source else ''}",
                )
            )
            continue

        try:
            passive = passive_assignment(reference, symbol, component.value)
        except ValueError_ as error:
            gaps.append(ModelGap(reference, symbol, str(error)))
            continue

        if passive is not None:
            assignments.append(passive)
            continue

        gaps.append(
            ModelGap(
                reference,
                symbol,
                "no SPICE model. Find one from the manufacturer, or exclude "
                "the part and say what the simulation therefore does not cover",
            )
        )

    logger.info(
        "Assigned SPICE models to %d parts, %d without a model",
        len(assignments),
        len(gaps),
    )
    return assignments, gaps


@dataclass
class ModelFile:
    """A SPICE model file to be written beside the schematic and included.

    Attributes:
        name: File name, such as ``"half_bridge_models.lib"``.
        content: The model cards.
        source: Where the cards came from, for the report.
    """

    name: str
    content: str
    source: str = ""
    cards: List[str] = field(default_factory=list)

    def add_card(self, card: str) -> None:
        """Append a model card.

        Args:
            card: A complete ``.model`` or ``.subckt`` block.
        """
        self.cards.append(card)
        self.content = "\n".join(self.cards) + "\n"
