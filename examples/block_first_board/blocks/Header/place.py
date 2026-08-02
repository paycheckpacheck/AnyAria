# -*- coding: utf-8 -*-
"""Where Header's part goes, decided by Header's own agent.

One connector, so the placement is entirely about which way round it faces and
where its five pins hand over to the rest of the board. It faces right, because
everything on the board is downstream of it and a source block that points
backwards makes every page after it read backwards too.
"""

from circuit_synth.kicad.layout.extract import SheetDescription
from circuit_synth.kicad.layout.spec import ComponentPlacement as C
from circuit_synth.kicad.layout.spec import GroupPlacement as G
from circuit_synth.kicad.layout.spec import LabelPlacement as L
from circuit_synth.kicad.layout.spec import NotePlacement as N
from circuit_synth.kicad.layout.spec import PlacementSpec
from circuit_synth.kicad.layout.spec import PowerPlacement as P

RATIONALE = (
    "J1 faces right, so everything leaves the block in the\n"
    "direction the rest of the board is drawn in. The pin order\n"
    "is the cable's, not the schematic's convenience: supply and\n"
    "its return are adjacent, so the pair stays together in the\n"
    "ribbon and the loop it makes is small. Ground leaves on a\n"
    "longer stub that drops clear of the signal labels rather\n"
    "than crossing them, since two wires that merely cross are\n"
    "not connected but a reader has to stop and check."
)


def place(sheet: SheetDescription) -> PlacementSpec:
    """Lay out the Header sheet.

    Args:
        sheet: The sheet as generated, which says what reference designator the
            connector ended up with.

    Returns:
        The placement.
    """
    connector = next(
        c.reference for c in sheet.components if c.lib_id.startswith("Connector")
    )

    return PlacementSpec(
        paper="A4",
        components=[C(connector, (101.6, 88.9), 180)],
        wires=[
            ((106.68, 83.82), (119.38, 83.82)),
            ((106.68, 86.36), (119.38, 86.36)),
            ((106.68, 88.9), (119.38, 88.9)),
            ((106.68, 93.98), (119.38, 93.98)),
            # Ground runs on past the labels before it drops, so that it does
            # not cross any of them.
            ((106.68, 91.44), (139.7, 91.44)),
            ((139.7, 91.44), (139.7, 101.6)),
            # Both flags hang off this block, because this connector is where
            # the supply and its return actually enter the board.
            ((113.03, 93.98), (113.03, 101.6)),
            ((139.7, 96.52), (147.32, 96.52)),
        ],
        junctions=[(113.03, 93.98), (139.7, 96.52)],
        labels=[
            L("DRIVE_B", (119.38, 83.82), 0.0, "hierarchical", "output"),
            L("DRIVE_A", (119.38, 86.36), 0.0, "hierarchical", "output"),
            L("VMON", (119.38, 88.9), 0.0, "hierarchical", "input"),
            L("RAW_OUT", (119.38, 93.98), 0.0, "hierarchical", "output"),
        ],
        power=[
            P("power:GND", (139.7, 101.6), 0.0),
            # Without these, ERC has no output power pin driving either net and
            # reports the regulator's VI and GND as undriven. The connector's
            # pins are passive, so the flags are how the schematic says that
            # power comes in here.
            P("power:PWR_FLAG", (113.03, 101.6), 180.0),
            P("power:PWR_FLAG", (147.32, 96.52), 0.0),
        ],
        groups=[G("BOARD CONNECTOR", (88.9, 60.96), (76.2, 76.2), RATIONALE)],
        notes=[N((88.9, 144.78), (76.2, 20.32))],
    )
