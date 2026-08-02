# -*- coding: utf-8 -*-
"""Where Indicator's parts go, decided by Indicator's own agent.

The block is instantiated twice, and this one placement is applied to both.
The second instance's parts have different reference designators, which the
build works out from the generated circuit rather than from a table kept here
by hand.
"""

from circuit_synth.kicad.layout.extract import SheetDescription
from circuit_synth.kicad.layout.spec import ComponentPlacement as C
from circuit_synth.kicad.layout.spec import GroupPlacement as G
from circuit_synth.kicad.layout.spec import LabelPlacement as L
from circuit_synth.kicad.layout.spec import NotePlacement as N
from circuit_synth.kicad.layout.spec import PlacementSpec
from circuit_synth.kicad.layout.spec import PowerPlacement as P

RATIONALE = (
    "A vertical stack, which is how anything hanging off a rail\n"
    "is conventionally drawn: the rail at the top, the series\n"
    "resistor, the LED below it, and the drive line leaving at\n"
    "the bottom. 1k8 off 3.3V gives about 1mA through a red LED\n"
    "at 1.9V forward, which is visible indoors and small enough\n"
    "that two of them cost the rail nothing. The resistor is on\n"
    "the rail side, so a drive line left floating leaves the LED\n"
    "dark. The DRIVE label sits on the cathode pin rather than\n"
    "on a stub, because Device:LED draws its emission arrows\n"
    "past the end of that pin and a stub would run under them."
)


def place(sheet: SheetDescription) -> PlacementSpec:
    """Lay out one Indicator sheet.

    Args:
        sheet: The sheet as generated, which says what reference designator
            each part ended up with.

    Returns:
        The placement.
    """
    series = next(c.reference for c in sheet.components if c.lib_id == "Device:R")
    led = next(c.reference for c in sheet.components if c.lib_id == "Device:LED")

    return PlacementSpec(
        paper="A4",
        components=[
            C(series, (127.0, 76.2), 0),
            # Turned so the anode is uppermost, which puts the current in the
            # direction the page is read.
            C(led, (127.0, 96.52), 90),
        ],
        wires=[
            ((127.0, 55.88), (127.0, 72.39)),
            ((127.0, 80.01), (127.0, 92.71)),
        ],
        # Reading left off the pin, into clear space, rather than downward
        # through the LED's own reference and value text.
        labels=[L("DRIVE", (127.0, 100.33), 180.0, "hierarchical", "input")],
        power=[P("power:+3V3", (127.0, 55.88), 0.0)],
        groups=[G("INDICATOR", (88.9, 45.72), (76.2, 88.9), RATIONALE)],
        notes=[N((88.9, 143.51), (76.2, 20.32))],
    )
