# -*- coding: utf-8 -*-
"""Where Supply's parts go, decided by Supply's own agent.

The block agent lays its own sheet out because it is the only one that knows
why the circuit is the shape it is. By the time an integrator sees this block
it has a netlist and no reasons, and a netlist alone produces exactly the
layout the generator produces.

The placement is written against the sheet as it was described, not against
hard-coded reference designators, because another block's agent may add a part
ahead of this one at any moment and renumber the whole board. What is recorded
alongside the layout is the circuit it was written against; the build maps that
frame onto the current one.
"""

from circuit_synth.kicad.layout.extract import SheetDescription
from circuit_synth.kicad.layout.spec import ComponentPlacement as C
from circuit_synth.kicad.layout.spec import GroupPlacement as G
from circuit_synth.kicad.layout.spec import LabelPlacement as L
from circuit_synth.kicad.layout.spec import NotePlacement as N
from circuit_synth.kicad.layout.spec import PlacementSpec
from circuit_synth.kicad.layout.spec import PowerPlacement as P

RATIONALE = (
    "U1 is the AMS1117-3.3 from its datasheet's typical application: C1 at the\n"
    "input and C2 at the output are the 10uF and 22uF that circuit asks for, and\n"
    "they sit against the pins they decouple rather than in a row at the bottom\n"
    "of the sheet. R1 and R2 are equal, so VMON reads half the rail: 1.65V from a\n"
    "healthy 3.3V, which leaves a reading on scale if the rail runs high. The\n"
    "divider is drawn hanging off the output rail on the right, because what it\n"
    "measures is this block's own output and not something handed to it."
)


def place(sheet: SheetDescription) -> PlacementSpec:
    """Lay out the Supply sheet.

    Args:
        sheet: The sheet as generated, which says what reference designator
            each part ended up with.

    Returns:
        The placement.
    """
    by_value = {}
    for component in sheet.components:
        by_value.setdefault((component.lib_id, component.value), []).append(
            component.reference
        )

    regulator = by_value[("Regulator_Linear:AMS1117-3.3", "AMS1117-3.3")][0]
    input_cap = by_value[("Device:C", "10uF")][0]
    output_cap = by_value[("Device:C", "22uF")][0]
    divider_top, divider_bottom = by_value[("Device:R", "10k")]

    return PlacementSpec(
        paper="A4",
        components=[
            C(regulator, (114.3, 88.9), 0),
            C(input_cap, (93.98, 96.52), 0),
            C(output_cap, (137.16, 96.52), 0),
            C(divider_top, (158.75, 101.6), 0),
            C(divider_bottom, (158.75, 116.84), 0),
        ],
        wires=[
            # Raw input across to the regulator, with its input capacitor on the way.
            ((76.2, 88.9), (106.68, 88.9)),
            ((93.98, 88.9), (93.98, 92.71)),
            ((93.98, 100.33), (93.98, 104.14)),
            # The regulator's own ground.
            ((114.3, 96.52), (114.3, 104.14)),
            # The 3.3V rail out, with its output capacitor beneath it.
            ((121.92, 88.9), (158.75, 88.9)),
            ((137.16, 88.9), (137.16, 92.71)),
            ((137.16, 100.33), (137.16, 104.14)),
            ((158.75, 88.9), (158.75, 82.55)),
            # The monitor divider, hanging off the rail it measures.
            ((158.75, 88.9), (158.75, 97.79)),
            ((158.75, 105.41), (158.75, 113.03)),
            ((158.75, 109.22), (175.26, 109.22)),
            ((158.75, 120.65), (158.75, 124.46)),
        ],
        junctions=[(93.98, 88.9), (137.16, 88.9), (158.75, 88.9), (158.75, 109.22)],
        labels=[
            L("RAW_IN", (76.2, 88.9), 180.0, "hierarchical", "input"),
            L("VMON", (175.26, 109.22), 0.0, "hierarchical", "output"),
        ],
        power=[
            P("power:+3V3", (158.75, 82.55), 0.0),
            P("power:GND", (93.98, 104.14), 0.0),
            P("power:GND", (114.3, 104.14), 0.0),
            P("power:GND", (137.16, 104.14), 0.0),
            P("power:GND", (158.75, 124.46), 0.0),
        ],
        groups=[G("3.3V RAIL AND MONITOR", (63.5, 63.5), (127.0, 88.9), RATIONALE)],
        # Kept clear of the title block in the bottom right of the page.
        notes=[N((63.5, 165.1), (101.6, 20.32))],
    )
