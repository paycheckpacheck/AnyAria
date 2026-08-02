# -*- coding: utf-8 -*-
"""The root sheet: the block diagram itself.

This is written at the architecture stage, with the stubs, and it is what makes
the pre-fan-out project worth looking at. It is also the only sheet nobody's
block agent owns, so it is the only layout the orchestrator writes.

A page of sheet symbols is a block diagram, so it is wired like one: every sheet
pin gets a short stub with a label on it rather than a wire run across the page
to the block it talks to. Four blocks with eight pins between them would already
be a rat's nest drawn point to point.
"""

from circuit_synth.kicad.layout.spec import GroupPlacement as G
from circuit_synth.kicad.layout.spec import LabelPlacement as L
from circuit_synth.kicad.layout.spec import NotePlacement as N
from circuit_synth.kicad.layout.spec import PlacementSpec
from circuit_synth.kicad.layout.spec import SheetPinPlacement as SP
from circuit_synth.kicad.layout.spec import SheetPlacement as S

# How far a stub runs off a sheet pin before its label.
STUB = 7.62

ROOT_SPEC = PlacementSpec(
    paper="A4",
    sheets=[
        # Left to right: what comes in, what makes the rail, what it drives.
        S(
            "Header",
            (25.4, 50.8),
            (40.64, 38.1),
            [
                SP("RAW_OUT", "right", 7.62),
                SP("VMON", "right", 15.24),
                SP("DRIVE_A", "right", 22.86),
                SP("DRIVE_B", "right", 30.48),
            ],
        ),
        S(
            "Supply",
            (101.6, 50.8),
            (40.64, 25.4),
            [SP("RAW_IN", "left", 7.62), SP("VMON", "left", 17.78)],
        ),
        S("Indicator", (180.34, 38.1), (38.1, 20.32), [SP("DRIVE", "left", 10.16)]),
        S("Indicator2", (180.34, 76.2), (38.1, 20.32), [SP("DRIVE", "left", 10.16)]),
    ],
    wires=[
        # Header's pins, on its right edge.
        ((66.04, 58.42), (73.66, 58.42)),
        ((66.04, 66.04), (73.66, 66.04)),
        ((66.04, 73.66), (73.66, 73.66)),
        ((66.04, 81.28), (73.66, 81.28)),
        # Supply's pins, on its left edge.
        ((93.98, 58.42), (101.6, 58.42)),
        ((93.98, 68.58), (101.6, 68.58)),
        # One stub per indicator.
        ((172.72, 48.26), (180.34, 48.26)),
        ((172.72, 86.36), (180.34, 86.36)),
    ],
    labels=[
        L("VRAW", (73.66, 58.42), 0.0),
        L("VMON", (73.66, 66.04), 0.0),
        L("LED_A", (73.66, 73.66), 0.0),
        L("LED_B", (73.66, 81.28), 0.0),
        L("VRAW", (93.98, 58.42), 180.0),
        L("VMON", (93.98, 68.58), 180.0),
        L("LED_A", (172.72, 48.26), 180.0),
        L("LED_B", (172.72, 86.36), 180.0),
    ],
    groups=[
        G(
            "BLOCK DIAGRAM",
            (19.05, 33.02),
            (222.25, 106.68),
            "Header is the only place the board meets anything outside it, so it is\n"
            "drawn first and everything else is downstream of it. Supply turns the raw\n"
            "input into the 3.3V rail and hands back a halved copy of it on VMON, which\n"
            "is why the monitor divider is inside Supply rather than inside the block\n"
            "that reads it. Indicator appears twice rather than once with two LEDs in\n"
            "it, because one indicator is one drive line; the two sheets are the same\n"
            "block and share one layout.\n"
            "+3V3 and GND are rails, so they are power symbols on the pages that use\n"
            "them and are deliberately absent from this diagram.",
        ),
    ],
    # Kept clear of the title block, which occupies the bottom right of the page.
    notes=[N((19.05, 149.86), (152.4, 25.4))],
)
