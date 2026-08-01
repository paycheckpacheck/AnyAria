"""Lay out the three-phase driver's sheets.

The generator decides what connects to what. This decides how it is drawn: the
placement for each sheet, the wires between the parts, and where the rails and
labels go. Applying it is checked against the circuit the Python described, pin
for pin, so the drawing can never change the design.

Run it after generating the project:

    uv run python examples/three_phase_driver.py
    uv run python examples/layout_three_phase_driver.py
"""

import logging
import sys
from pathlib import Path

from circuit_synth.kicad.layout import (
    PlacementSpec,
    apply_placement,
    render_sheets,
    validate_layout,
)
from circuit_synth.kicad.layout.spec import ComponentPlacement as C
from circuit_synth.kicad.layout.spec import LabelPlacement as L
from circuit_synth.kicad.layout.spec import NotePlacement as N
from circuit_synth.kicad.layout.spec import PowerPlacement as P
from circuit_synth.kicad.layout.spec import SheetPinPlacement as SP
from circuit_synth.kicad.layout.spec import SheetPlacement as S

logging.disable(logging.CRITICAL)

PROJECT = Path(
    sys.argv[1] if len(sys.argv) > 1 else "examples/build/three_phase_driver"
)
ROOT = PROJECT / "ThreePhaseDriver.kicad_sch"
CIRCUIT_JSON = PROJECT / "ThreePhaseDriver.json"

# How far a stub runs off a pin before its label. Long enough to read as a wire.
STUB = 6.35


def port(text: str, at, rotation: float, shape: str) -> L:
    """Build a hierarchical label for a declared port.

    Args:
        text: The port name.
        at: The (x, y) anchor.
        rotation: Direction the text runs, in degrees.
        shape: The port direction.

    Returns:
        The label placement.
    """
    return L(text, at, rotation, "hierarchical", shape)


def ground(at) -> P:
    """Build a ground symbol.

    Args:
        at: The (x, y) connection point.

    Returns:
        The power symbol placement.
    """
    return P("power:GND", at, 0.0)


# --------------------------------------------------------------- back emf ---
# One phase's sensing, read left to right: the phase comes in, divides down,
# feeds the comparator's + input and contributes its resistor to the shared
# neutral, and the comparator's edge leaves on the right.
BACK_EMF = PlacementSpec(
    paper="A4",
    components=[
        C("R8", (63.5, 80.01), 0),    # divider, top
        C("R9", (63.5, 96.52), 0),    # divider, bottom
        C("R10", (76.2, 90.17), 0),   # this phase's leg of the virtual neutral
        C("R11", (127.0, 78.74), 0),  # output pullup
        C("U4", (101.6, 88.9), 0),    # zero-crossing comparator
        C("C17", (137.16, 74.93), 0),  # comparator decoupling
    ],
    wires=[
        # Supply rail across the top, tapped by everything that needs it
        ((50.8, 68.58), (137.16, 68.58)),
        ((99.06, 68.58), (99.06, 81.28)),
        ((127.0, 68.58), (127.0, 74.93)),
        ((137.16, 68.58), (137.16, 71.12)),
        ((137.16, 78.74), (137.16, 82.55)),
        # Phase in, through the divider, to ground
        ((50.8, 76.2), (63.5, 76.2)),
        ((63.5, 83.82), (63.5, 92.71)),
        ((63.5, 100.33), (63.5, 101.6)),
        # The divided phase runs across to the comparator's + input
        ((63.5, 83.82), (93.98, 83.82)),
        ((93.98, 83.82), (93.98, 86.36)),
        ((76.2, 83.82), (76.2, 86.36)),
        # The neutral leg, out to the port and back up to the - input
        ((76.2, 93.98), (76.2, 107.95)),
        ((50.8, 107.95), (88.9, 107.95)),
        ((88.9, 107.95), (88.9, 91.44)),
        ((88.9, 91.44), (93.98, 91.44)),
        # Comparator ground, and its enable held at the rail
        ((99.06, 96.52), (99.06, 101.6)),
        ((101.6, 96.52), (101.6, 106.68)),
        ((101.6, 106.68), (121.92, 106.68)),
        ((121.92, 106.68), (121.92, 68.58)),
        # The edge out, pulled up on its way
        ((109.22, 88.9), (114.3, 88.9)),
        ((114.3, 88.9), (114.3, 120.65)),
        ((114.3, 120.65), (133.35, 120.65)),
        ((127.0, 82.55), (127.0, 120.65)),
    ],
    notes=[N((50.8, 132.08), (114.3, 25.4))],
    junctions=[
        (63.5, 83.82),
        (76.2, 83.82),
        (76.2, 107.95),
        (99.06, 68.58),
        (121.92, 68.58),
        (127.0, 68.58),
        (127.0, 120.65),
    ],
    labels=[
        port("V3V3", (50.8, 68.58), 180, "input"),
        port("PHASE", (50.8, 76.2), 180, "input"),
        port("NEUTRAL", (50.8, 107.95), 180, "bidirectional"),
        port("ZC", (133.35, 120.65), 0, "output"),
    ],
    power=[
        ground((63.5, 101.6)),
        ground((99.06, 101.6)),
        ground((137.16, 82.55)),
    ],
)

# The three phases are the same block, so one layout serves all of them.
BACK_EMF_RENAMES = {
    "BackEmf2": {
        "R8": "R16", "R9": "R17", "R10": "R18", "R11": "R19",
        "U4": "U7", "C17": "C22",
    },
    "BackEmf3": {
        "R8": "R24", "R9": "R25", "R10": "R26", "R11": "R27",
        "U4": "U10", "C17": "C27",
    },
}

# ------------------------------------------------------------ half bridge ---
# The sheet reads in bands: the drive rail across the top, the bootstrap under
# it, then the high side gate path, the phase tie, and the low side gate path.
# The two MOSFETs stand as a totem pole on the right with the phase node
# between them, the current sense sits below the shunt, and this phase's
# back-EMF sensing hangs off the phase node as its own nested sheet.
HALF_BRIDGE = PlacementSpec(
    paper="A3",
    components=[
        C("U5", (88.9, 101.6), 0),      # IR2101 gate driver
        C("C19", (68.58, 83.82), 0),    # driver decoupling
        C("D1", (116.84, 76.2), 0),     # bootstrap diode
        C("C18", (146.05, 88.9), 0),    # bootstrap capacitor
        C("R12", (130.81, 96.52), 90),  # high side gate resistor
        C("R13", (130.81, 109.22), 90),  # low side gate resistor
        C("Q1", (167.64, 91.44), 0),    # high side FET
        C("Q2", (167.64, 114.3), 0),    # low side FET
        C("R14", (170.18, 127.0), 0),    # Kelvin shunt
        C("U6", (196.85, 149.86), 0),    # current sense amplifier
        C("C20", (241.3, 144.78), 0),    # amplifier supply decoupling
        C("R15", (215.9, 149.86), 90),   # output filter resistor
        C("C21", (226.06, 156.21), 0),   # output filter capacitor
    ],
    sheets=[
        S(
            "BackEmf",
            (241.3, 91.44),
            (50.8, 33.02),
            [
                SP("PHASE", "left", 7.62),
                SP("V3V3", "left", 15.24),
                SP("NEUTRAL", "left", 22.86),
                SP("ZC", "right", 7.62),
            ],
        )
    ],
    wires=[
        # Drive rail across the top, with the driver and its decoupling on it
        ((55.88, 76.2), (113.03, 76.2)),
        ((68.58, 76.2), (68.58, 80.01)),
        ((68.58, 87.63), (68.58, 91.44)),
        ((88.9, 76.2), (88.9, 88.9)),
        # Logic inputs
        ((66.04, 101.6), (81.28, 101.6)),
        ((66.04, 104.14), (81.28, 104.14)),
        # Bootstrap: diode from the rail, capacitor referenced to the phase
        ((120.65, 76.2), (120.65, 93.98)),
        ((96.52, 93.98), (120.65, 93.98)),
        ((120.65, 85.09), (146.05, 85.09)),
        ((146.05, 92.71), (146.05, 101.6)),
        ((146.05, 101.6), (170.18, 101.6)),
        # High side gate path
        ((96.52, 96.52), (127.0, 96.52)),
        ((134.62, 96.52), (162.56, 96.52)),
        ((162.56, 96.52), (162.56, 91.44)),
        # Low side gate path
        ((96.52, 109.22), (127.0, 109.22)),
        ((134.62, 109.22), (162.56, 109.22)),
        ((162.56, 109.22), (162.56, 114.3)),
        # Phase node between the two devices, with the driver's VS tied to it
        ((170.18, 96.52), (170.18, 109.22)),
        ((96.52, 106.68), (170.18, 106.68)),
        ((170.18, 104.14), (176.53, 104.14)),
        # Motor rail into the high side drain
        ((170.18, 81.28), (170.18, 86.36)),
        # Driver ground
        ((88.9, 114.3), (88.9, 119.38)),
        # Low side return through the shunt
        ((170.18, 119.38), (170.18, 121.92)),
        ((172.72, 124.46), (180.34, 124.46)),
        # Kelvin taps into the current sense amplifier. They come down their own
        # channels to the left of the amplifier and enter its inputs from the
        # left, rather than crossing its body to reach them.
        ((172.72, 129.54), (184.15, 129.54)),
        ((184.15, 129.54), (184.15, 147.32)),
        ((184.15, 147.32), (189.23, 147.32)),
        ((170.18, 132.08), (179.07, 132.08)),
        ((179.07, 132.08), (179.07, 152.4)),
        ((179.07, 152.4), (189.23, 152.4)),
        # Amplifier supply and grounds
        ((194.31, 142.24), (194.31, 138.43)),
        ((194.31, 138.43), (247.65, 138.43)),
        ((241.3, 138.43), (241.3, 140.97)),
        ((241.3, 148.59), (241.3, 152.4)),
        ((194.31, 157.48), (194.31, 161.29)),
        ((199.39, 157.48), (199.39, 161.29)),
        # Amplifier output through the filter to the ADC
        ((204.47, 149.86), (212.09, 149.86)),
        ((219.71, 149.86), (231.14, 149.86)),
        ((226.06, 149.86), (226.06, 152.4)),
        ((226.06, 160.02), (226.06, 163.83)),
        # This phase's back-EMF sensing, fed from the phase node
        ((170.18, 99.06), (241.3, 99.06)),
        ((234.95, 106.68), (241.3, 106.68)),
        ((234.95, 114.3), (241.3, 114.3)),
        ((292.1, 99.06), (299.72, 99.06)),
    ],
    notes=[N((55.88, 175.26), (152.4, 25.4))],
    junctions=[
        (68.58, 76.2),
        (88.9, 76.2),
        (120.65, 85.09),
        (120.65, 93.98),
        (170.18, 96.52),
        (170.18, 99.06),
        (170.18, 101.6),
        (170.18, 104.14),
        (170.18, 106.68),
        (241.3, 138.43),
        (226.06, 149.86),
    ],
    labels=[
        port("VDRV", (55.88, 76.2), 180, "input"),
        port("HI", (66.04, 101.6), 180, "input"),
        port("LI", (66.04, 104.14), 180, "input"),
        port("VM", (170.18, 81.28), 90, "input"),
        port("PHASE", (176.53, 104.14), 0, "output"),
        port("ISENSE", (231.14, 149.86), 0, "output"),
        port("VDRV", (247.65, 138.43), 0, "input"),
        port("VDRV", (234.95, 106.68), 180, "input"),
        port("NEUTRAL", (234.95, 114.3), 180, "bidirectional"),
        port("ZC", (299.72, 99.06), 0, "output"),
        L("BOOT", (127.0, 85.09), 0, "local"),
        L("HGATE", (140.97, 96.52), 0, "local"),
        L("LGATE", (140.97, 109.22), 0, "local"),
    ],
    power=[
        ground((68.58, 91.44)),
        ground((88.9, 119.38)),
        ground((180.34, 124.46)),
        ground((241.3, 152.4)),
        ground((194.31, 161.29)),
        ground((199.39, 161.29)),
        ground((226.06, 163.83)),
    ],
)

HALF_BRIDGE_RENAMES = {
    "HalfBridge2": {
        "U5": "U8", "Q1": "Q3", "Q2": "Q4", "R12": "R20", "R13": "R21",
        "C18": "C23", "D1": "D2", "C19": "C24", "R14": "R22", "U6": "U9",
        "C20": "C25", "R15": "R23", "C21": "C26",
        "BackEmf": "BackEmf2",
    },
    "HalfBridge3": {
        "U5": "U11", "Q1": "Q5", "Q2": "Q6", "R12": "R28", "R13": "R29",
        "C18": "C28", "D1": "D3", "C19": "C29", "R14": "R30", "U6": "U12",
        "C20": "C30", "R15": "R31", "C21": "C31",
        "BackEmf": "BackEmf3",
    },
}

# ------------------------------------------------------------------ power ---
# Fused input into the motor rail, the linear regulator making 3.3V below it,
# and the rail monitor divider on the far right.
POWER = PlacementSpec(
    paper="A4",
    components=[
        C("F1", (63.5, 76.2), 90),      # input fuse
        C("C2", (88.9, 83.82), 0),      # motor rail bulk
        C("C5", (104.14, 83.82), 0),    # motor rail ceramic
        C("C3", (76.2, 99.06), 0),      # regulator input
        C("U1", (114.3, 96.52), 0),     # AMS1117-3.3
        C("C4", (146.05, 104.14), 0),   # regulator output
        C("R3", (165.1, 83.82), 0),     # rail monitor, top
        C("R4", (165.1, 96.52), 0),     # rail monitor, bottom
    ],
    wires=[
        # VBUS in, through the fuse, into the motor rail
        ((45.72, 76.2), (59.69, 76.2)),
        ((45.72, 76.2), (45.72, 71.12)),
        ((67.31, 76.2), (165.1, 76.2)),
        ((88.9, 76.2), (88.9, 80.01)),
        ((104.14, 76.2), (104.14, 80.01)),
        ((88.9, 87.63), (88.9, 91.44)),
        ((104.14, 87.63), (104.14, 91.44)),
        ((127.0, 76.2), (127.0, 71.12)),
        # VBUS also feeds the regulator input
        ((50.8, 76.2), (50.8, 96.52)),
        ((50.8, 96.52), (106.68, 96.52)),
        ((76.2, 96.52), (76.2, 95.25)),
        ((76.2, 102.87), (76.2, 106.68)),
        # Regulator ground and output
        ((114.3, 104.14), (114.3, 109.22)),
        ((121.92, 96.52), (152.4, 96.52)),
        ((146.05, 96.52), (146.05, 100.33)),
        ((146.05, 107.95), (146.05, 111.76)),
        # Rail monitor off the motor rail
        ((165.1, 76.2), (165.1, 80.01)),
        ((165.1, 87.63), (165.1, 92.71)),
        ((165.1, 87.63), (177.8, 87.63)),
        ((165.1, 100.33), (165.1, 104.14)),
    ],
    notes=[N((45.72, 127.0), (139.7, 25.4))],
    junctions=[
        (88.9, 76.2),
        (104.14, 76.2),
        (127.0, 76.2),
        (50.8, 76.2),
        (76.2, 96.52),
        (146.05, 96.52),
        (165.1, 87.63),
    ],
    labels=[
        port("VMOTOR", (127.0, 71.12), 90, "output"),
        port("V3V3", (152.4, 96.52), 0, "output"),
        port("VRAIL_SENSE", (177.8, 87.63), 0, "output"),
    ],
    power=[
        P("power:VBUS", (45.72, 71.12), 0),
        ground((88.9, 91.44)),
        ground((104.14, 91.44)),
        ground((76.2, 106.68)),
        ground((114.3, 109.22)),
        ground((146.05, 111.76)),
        ground((165.1, 104.14)),
    ],
)

# -------------------------------------------------------------------- usb ---
# The receptacle on the left, reading down its right edge in the order the
# symbol puts the pins: VBUS out along the top with its decoupling, the CC
# pulldowns below it, then the data pair, then the shell and ground.
#
# Both halves of the connector carry D+ and D-, so each pair is tied together
# on a stub beside the pins. The two data runs drop into their own channels
# below the pulldowns, which keeps them clear of the resistors and of each
# other - the alternative crosses two wires over a resistor for no reason.
USB = PlacementSpec(
    paper="A4",
    components=[
        C("J1", (63.5, 88.9), 0),     # USB-C receptacle
        C("R1", (101.6, 90.17), 0),   # CC1 pulldown
        C("R2", (91.44, 92.71), 0),   # CC2 pulldown
        C("C1", (114.3, 80.01), 0),   # VBUS decoupling
    ],
    wires=[
        # VBUS along the top, decoupled on its way out
        ((78.74, 73.66), (132.08, 73.66)),
        ((132.08, 73.66), (132.08, 68.58)),
        ((114.3, 73.66), (114.3, 76.2)),
        ((114.3, 83.82), (114.3, 87.63)),
        # CC1 to the further pulldown, CC2 to the nearer one, so the two runs
        # never have to cross
        ((78.74, 78.74), (101.6, 78.74)),
        ((101.6, 78.74), (101.6, 86.36)),
        ((101.6, 93.98), (101.6, 97.79)),
        ((78.74, 81.28), (91.44, 81.28)),
        ((91.44, 81.28), (91.44, 88.9)),
        ((91.44, 96.52), (91.44, 100.33)),
        # D-, both halves tied together, down its channel and out
        ((78.74, 86.36), (83.82, 86.36)),
        ((78.74, 88.9), (83.82, 88.9)),
        ((83.82, 86.36), (83.82, 107.95)),
        ((83.82, 107.95), (132.08, 107.95)),
        # D+, the same one channel further in
        ((78.74, 91.44), (81.28, 91.44)),
        ((78.74, 93.98), (81.28, 93.98)),
        ((81.28, 91.44), (81.28, 110.49)),
        ((81.28, 110.49), (132.08, 110.49)),
        # Shell and ground
        ((63.5, 111.76), (63.5, 115.57)),
        ((55.88, 111.76), (55.88, 115.57)),
    ],
    notes=[N((55.88, 127.0), (114.3, 25.4))],
    junctions=[
        (114.3, 73.66),
        (83.82, 88.9),
        (81.28, 93.98),
    ],
    labels=[
        port("USB_DM", (132.08, 107.95), 0, "output"),
        port("USB_DP", (132.08, 110.49), 0, "output"),
    ],
    power=[
        P("power:VBUS", (132.08, 68.58), 0),
        ground((63.5, 115.57)),
        ground((55.88, 115.57)),
        ground((101.6, 97.79)),
        ground((91.44, 100.33)),
        ground((114.3, 87.63)),
    ],
)


# -------------------------------------------------------------------- mcu ---
# A part with 57 pins does not get wired to everything by hand. The RP2040 sits
# in the middle with its supplies stubbed up, its interfaces stubbed left and
# its GPIO stubbed right, and the nets are carried by labels - which is how a
# dense MCU page is drawn and the only way it stays readable.
#
# What is wired is what belongs together: the decoupling along the rail at the
# top, the support parts in one row beneath it, the crystal beside its own two
# pins, and the flash and debug header off to the left.
MCU = PlacementSpec(
    paper="A3",
    components=[
        C("U2", (190.5, 152.4), 0),     # RP2040
        C("U3", (95.25, 165.1), 0),     # QSPI flash
        C("Y1", (146.05, 172.72), 270),  # 12MHz crystal
        C("C6", (133.35, 167.64), 270),  # crystal load, XIN
        C("C7", (133.35, 177.8), 270),   # crystal load, XOUT
        C("J2", (127.0, 200.66), 0),    # SWD header
        # IOVDD decoupling, one per supply pin, along the rail
        C("C9", (63.5, 97.79), 0),
        C("C10", (76.2, 97.79), 0),
        C("C11", (88.9, 97.79), 0),
        C("C12", (101.6, 97.79), 0),
        C("C13", (114.3, 97.79), 0),
        C("C14", (127.0, 97.79), 0),
        # Support parts: reset, flash chip select, ADC supply, core rail
        C("R5", (63.5, 132.08), 0),      # RUN pullup
        C("C8", (76.2, 132.08), 0),      # RUN delay
        C("R6", (88.9, 132.08), 0),      # QSPI_SS pullup
        C("R7", (101.6, 132.08), 0),     # ADC supply filter
        C("C16", (114.3, 132.08), 0),    # ADC supply decoupling
        C("C15", (127.0, 132.08), 0),    # core rail decoupling
    ],
    wires=[
        # 3.3V rail with a decoupling capacitor under each supply pin
        ((57.15, 88.9), (127.0, 88.9)),
        ((63.5, 88.9), (63.5, 93.98)),
        ((76.2, 88.9), (76.2, 93.98)),
        ((88.9, 88.9), (88.9, 93.98)),
        ((101.6, 88.9), (101.6, 93.98)),
        ((114.3, 88.9), (114.3, 93.98)),
        ((127.0, 88.9), (127.0, 93.98)),
        ((63.5, 101.6), (63.5, 105.41)),
        ((76.2, 101.6), (76.2, 105.41)),
        ((88.9, 101.6), (88.9, 105.41)),
        ((101.6, 101.6), (101.6, 105.41)),
        ((114.3, 101.6), (114.3, 105.41)),
        ((127.0, 101.6), (127.0, 105.41)),
        # Support row, each end stubbed to the net it joins
        ((63.5, 128.27), (63.5, 123.19)),
        ((63.5, 135.89), (63.5, 140.97)),
        ((76.2, 128.27), (76.2, 123.19)),
        ((76.2, 135.89), (76.2, 139.7)),
        ((88.9, 128.27), (88.9, 123.19)),
        ((88.9, 135.89), (88.9, 140.97)),
        ((101.6, 128.27), (101.6, 123.19)),
        ((101.6, 135.89), (101.6, 140.97)),
        ((114.3, 128.27), (114.3, 123.19)),
        ((114.3, 135.89), (114.3, 139.7)),
        ((127.0, 128.27), (127.0, 123.19)),
        ((127.0, 135.89), (127.0, 139.7)),
        # The MCU's supplies leave the top of the symbol
        ((177.8, 106.68), (177.8, 101.6)),
        ((180.34, 106.68), (180.34, 101.6)),
        ((187.96, 106.68), (187.96, 101.6)),
        ((193.04, 106.68), (193.04, 101.6)),
        ((198.12, 106.68), (198.12, 101.6)),
        ((203.2, 106.68), (203.2, 101.6)),
        ((190.5, 198.12), (190.5, 203.2)),
        # Interfaces leave the left edge
        ((165.1, 129.54), (158.75, 129.54)),
        ((165.1, 137.16), (158.75, 137.16)),
        ((165.1, 139.7), (158.75, 139.7)),
        ((165.1, 147.32), (158.75, 147.32)),
        ((165.1, 149.86), (158.75, 149.86)),
        ((165.1, 152.4), (158.75, 152.4)),
        ((165.1, 154.94), (158.75, 154.94)),
        ((165.1, 157.48), (158.75, 157.48)),
        ((165.1, 160.02), (158.75, 160.02)),
        ((165.1, 185.42), (158.75, 185.42)),
        ((165.1, 187.96), (158.75, 187.96)),
        # The crystal is wired rather than labelled: it belongs to the two pins
        # it sits between, and a label there would say nothing useful.
        ((137.16, 167.64), (165.1, 167.64)),
        ((146.05, 167.64), (146.05, 168.91)),
        ((137.16, 177.8), (165.1, 177.8)),
        ((146.05, 177.8), (146.05, 176.53)),
        ((129.54, 167.64), (129.54, 185.42)),
        # GPIO leaves the right edge
        ((215.9, 114.3), (222.25, 114.3)),
        ((215.9, 116.84), (222.25, 116.84)),
        ((215.9, 119.38), (222.25, 119.38)),
        ((215.9, 121.92), (222.25, 121.92)),
        ((215.9, 124.46), (222.25, 124.46)),
        ((215.9, 127.0), (222.25, 127.0)),
        ((215.9, 129.54), (222.25, 129.54)),
        ((215.9, 132.08), (222.25, 132.08)),
        ((215.9, 134.62), (222.25, 134.62)),
        ((215.9, 182.88), (222.25, 182.88)),
        ((215.9, 185.42), (222.25, 185.42)),
        ((215.9, 187.96), (222.25, 187.96)),
        ((215.9, 190.5), (222.25, 190.5)),
        # Flash
        ((85.09, 157.48), (78.74, 157.48)),
        ((85.09, 160.02), (78.74, 160.02)),
        ((85.09, 162.56), (78.74, 162.56)),
        ((85.09, 165.1), (78.74, 165.1)),
        ((85.09, 167.64), (78.74, 167.64)),
        ((85.09, 170.18), (78.74, 170.18)),
        ((95.25, 152.4), (95.25, 147.32)),
        ((95.25, 177.8), (95.25, 181.61)),
        # SWD header
        ((121.92, 198.12), (115.57, 198.12)),
        ((121.92, 200.66), (115.57, 200.66)),
        ((121.92, 203.2), (115.57, 203.2)),
        ((115.57, 203.2), (115.57, 208.28)),
    ],
    notes=[N((57.15, 220.98), (177.8, 25.4))],
    junctions=[
        (63.5, 88.9),
        (76.2, 88.9),
        (88.9, 88.9),
        (101.6, 88.9),
        (114.3, 88.9),
        (146.05, 167.64),
        (146.05, 177.8),
        (129.54, 177.8),
    ],
    labels=[
        port("V3V3", (57.15, 88.9), 180, "input"),
        port("USB_DM", (158.75, 137.16), 180, "input"),
        port("USB_DP", (158.75, 139.7), 180, "input"),
        port("AH", (222.25, 114.3), 0, "output"),
        port("AL", (222.25, 116.84), 0, "output"),
        port("BH", (222.25, 119.38), 0, "output"),
        port("BL", (222.25, 121.92), 0, "output"),
        port("CH", (222.25, 124.46), 0, "output"),
        port("CL", (222.25, 127.0), 0, "output"),
        port("ZC_A", (222.25, 129.54), 0, "input"),
        port("ZC_B", (222.25, 132.08), 0, "input"),
        port("ZC_C", (222.25, 134.62), 0, "input"),
        port("ISENSE_A", (222.25, 182.88), 0, "input"),
        port("ISENSE_B", (222.25, 185.42), 0, "input"),
        port("ISENSE_C", (222.25, 187.96), 0, "input"),
        port("VRAIL_SENSE", (222.25, 190.5), 0, "input"),
        L("V3V3", (177.8, 101.6), 90, "local"),
        L("ADC_AVDD", (180.34, 101.6), 90, "local"),
        L("V3V3", (187.96, 101.6), 90, "local"),
        L("V3V3", (193.04, 101.6), 90, "local"),
        L("V1V1", (198.12, 101.6), 90, "local"),
        L("V1V1", (203.2, 101.6), 90, "local"),
        L("V3V3", (63.5, 123.19), 90, "local"),
        L("RUN", (63.5, 140.97), 270, "local"),
        L("RUN", (76.2, 123.19), 90, "local"),
        L("V3V3", (88.9, 123.19), 90, "local"),
        L("QSPI_SS", (88.9, 140.97), 270, "local"),
        L("V3V3", (101.6, 123.19), 90, "local"),
        L("ADC_AVDD", (101.6, 140.97), 270, "local"),
        L("ADC_AVDD", (114.3, 123.19), 90, "local"),
        L("V1V1", (127.0, 123.19), 90, "local"),
        L("RUN", (158.75, 129.54), 180, "local"),
        L("QSPI_SS", (158.75, 147.32), 180, "local"),
        L("QSPI_SCLK", (158.75, 149.86), 180, "local"),
        L("QSPI_SD0", (158.75, 152.4), 180, "local"),
        L("QSPI_SD1", (158.75, 154.94), 180, "local"),
        L("QSPI_SD2", (158.75, 157.48), 180, "local"),
        L("QSPI_SD3", (158.75, 160.02), 180, "local"),
        L("SWCLK", (158.75, 185.42), 180, "local"),
        L("SWDIO", (158.75, 187.96), 180, "local"),
        L("QSPI_SS", (78.74, 157.48), 180, "local"),
        L("QSPI_SCLK", (78.74, 160.02), 180, "local"),
        L("QSPI_SD0", (78.74, 162.56), 180, "local"),
        L("QSPI_SD1", (78.74, 165.1), 180, "local"),
        L("QSPI_SD2", (78.74, 167.64), 180, "local"),
        L("QSPI_SD3", (78.74, 170.18), 180, "local"),
        L("V3V3", (95.25, 147.32), 90, "local"),
        L("SWCLK", (115.57, 198.12), 180, "local"),
        L("SWDIO", (115.57, 200.66), 180, "local"),
    ],
    power=[
        ground((63.5, 105.41)),
        ground((76.2, 105.41)),
        ground((88.9, 105.41)),
        ground((101.6, 105.41)),
        ground((114.3, 105.41)),
        ground((127.0, 105.41)),
        ground((76.2, 139.7)),
        ground((114.3, 139.7)),
        ground((127.0, 139.7)),
        ground((190.5, 203.2)),
        ground((129.54, 185.42)),
        ground((95.25, 181.61)),
        ground((115.57, 208.28)),
    ],
)


# ------------------------------------------------------------------- root ---
# The top page is a block diagram and reads as one: supplies on the left, the
# MCU in the middle, the three half-bridges stacked on the right in phase
# order, and the motor beyond them. Every connection is a stub and a label
# rather than a wire, because a page of sheet symbols wired point to point is
# a rat's nest nobody can follow.


def bus(name: str, at, rotation: float) -> L:
    """Build a local label for a net crossing the top page.

    Args:
        name: The net name.
        at: The (x, y) anchor, on the end of a sheet pin's stub.
        rotation: Direction the text runs, in degrees.

    Returns:
        The label placement.
    """
    return L(name, at, rotation, "local")


def _stub(x: float, y: float, out: float):
    """Build a horizontal stub off a sheet pin.

    Args:
        x: The pin's x.
        y: The pin's y.
        out: How far to run, negative for leftwards.

    Returns:
        The wire segment.
    """
    return ((x, y), (x + out, y))


# Each half-bridge takes the same five signals in and gives the same three
# back, so the page is built once per phase from the nets that phase uses.
_LEG_PINS_IN = (("HI", 7.62), ("LI", 15.24), ("VM", 25.4), ("VDRV", 33.02),
                ("NEUTRAL", 43.18))
_LEG_PINS_OUT = (("PHASE", 7.62), ("ISENSE", 20.32), ("ZC", 27.94))
_LEGS = (
    ("HalfBridge", 38.1, ("AH", "AL", "VMOTOR", "V3V3", "VNEUTRAL"),
     ("PHASE_A", "ISENSE_A", "ZC_A")),
    ("HalfBridge2", 127.0, ("BH", "BL", "VMOTOR", "V3V3", "VNEUTRAL"),
     ("PHASE_B", "ISENSE_B", "ZC_B")),
    ("HalfBridge3", 215.9, ("CH", "CL", "VMOTOR", "V3V3", "VNEUTRAL"),
     ("PHASE_C", "ISENSE_C", "ZC_C")),
)
_LEG_X, _LEG_WIDTH, _LEG_HEIGHT = 330.2, 63.5, 68.58

_MCU_IN = (
    ("V3V3", 7.62, "V3V3"),
    ("USB_DP", 15.24, "USB_DP"),
    ("USB_DM", 22.86, "USB_DM"),
    ("VRAIL_SENSE", 33.02, "VRAIL_SENSE"),
    ("ISENSE_A", 43.18, "ISENSE_A"),
    ("ISENSE_B", 50.8, "ISENSE_B"),
    ("ISENSE_C", 58.42, "ISENSE_C"),
    ("ZC_A", 68.58, "ZC_A"),
    ("ZC_B", 76.2, "ZC_B"),
    ("ZC_C", 83.82, "ZC_C"),
)
_MCU_OUT = (
    ("AH", 7.62), ("AL", 15.24), ("BH", 25.4), ("BL", 33.02),
    ("CH", 43.18), ("CL", 50.8),
)
_MCU_X, _MCU_Y, _MCU_WIDTH = 177.8, 38.1, 76.2


def _root() -> PlacementSpec:
    """Build the top page's placement.

    Returns:
        The placement spec for the root sheet.
    """
    wires, labels = [], []
    sheets = [
        S("Power", (38.1, 38.1), (50.8, 30.48),
          [SP("VMOTOR", "right", 7.62), SP("V3V3", "right", 15.24),
           SP("VRAIL_SENSE", "right", 22.86)]),
        S("UsbProgramming", (38.1, 88.9), (50.8, 22.86),
          [SP("USB_DP", "right", 7.62), SP("USB_DM", "right", 15.24)]),
        S("Mcu", (_MCU_X, _MCU_Y), (_MCU_WIDTH, 88.9),
          [SP(name, "left", offset) for name, offset, _ in _MCU_IN]
          + [SP(name, "right", offset) for name, offset in _MCU_OUT]),
    ]

    # Supplies and USB leave their blocks to the right
    for offset, net in ((7.62, "VMOTOR"), (15.24, "V3V3"), (22.86, "VRAIL_SENSE")):
        wires.append(_stub(88.9, 38.1 + offset, 6.35))
        labels.append(bus(net, (95.25, 38.1 + offset), 0))
    for offset, net in ((7.62, "USB_DP"), (15.24, "USB_DM")):
        wires.append(_stub(88.9, 88.9 + offset, 6.35))
        labels.append(bus(net, (95.25, 88.9 + offset), 0))

    # The MCU takes its inputs on the left and gives the gate drive on the right
    for _, offset, net in _MCU_IN:
        wires.append(_stub(_MCU_X, _MCU_Y + offset, -6.35))
        labels.append(bus(net, (_MCU_X - 6.35, _MCU_Y + offset), 180))
    for net, offset in _MCU_OUT:
        wires.append(_stub(_MCU_X + _MCU_WIDTH, _MCU_Y + offset, 6.35))
        labels.append(bus(net, (_MCU_X + _MCU_WIDTH + 6.35, _MCU_Y + offset), 0))

    # One half-bridge per phase, stacked in phase order
    for name, top, nets_in, nets_out in _LEGS:
        sheets.append(
            S(name, (_LEG_X, top), (_LEG_WIDTH, _LEG_HEIGHT),
              [SP(pin, "left", offset) for pin, offset in _LEG_PINS_IN]
              + [SP(pin, "right", offset) for pin, offset in _LEG_PINS_OUT])
        )
        for (_, offset), net in zip(_LEG_PINS_IN, nets_in):
            wires.append(_stub(_LEG_X, top + offset, -6.35))
            labels.append(bus(net, (_LEG_X - 6.35, top + offset), 180))
        for (_, offset), net in zip(_LEG_PINS_OUT, nets_out):
            wires.append(_stub(_LEG_X + _LEG_WIDTH, top + offset, 6.35))
            labels.append(bus(net, (_LEG_X + _LEG_WIDTH + 6.35, top + offset), 0))

    # The motor, taking the three phases
    for index, net in enumerate(("PHASE_A", "PHASE_B", "PHASE_C")):
        y = 124.46 + index * 2.54
        wires.append(_stub(495.3, y, -6.35))
        labels.append(bus(net, (488.95, y), 180))

    return PlacementSpec(
        paper="A2",
        components=[C("J3", (500.38, 127.0), 0)],
        sheets=sheets,
        notes=[N((177.8, 190.5), (139.7, 25.4))],
        wires=wires,
        labels=labels,
    )


ROOT_SPEC = _root()


SHEETS = {
    "ThreePhaseDriver": ROOT_SPEC,
    "BackEmf": BACK_EMF,
    "BackEmf2": BACK_EMF.renamed(BACK_EMF_RENAMES["BackEmf2"]),
    "BackEmf3": BACK_EMF.renamed(BACK_EMF_RENAMES["BackEmf3"]),
    "HalfBridge": HALF_BRIDGE,
    "HalfBridge2": HALF_BRIDGE.renamed(HALF_BRIDGE_RENAMES["HalfBridge2"]),
    "HalfBridge3": HALF_BRIDGE.renamed(HALF_BRIDGE_RENAMES["HalfBridge3"]),
    "Power": POWER,
    "UsbProgramming": USB,
    "Mcu": MCU,
}


def main() -> int:
    """Apply every sheet layout, then check and render the result.

    Returns:
        Process exit status: non-zero when the layout changed the circuit.
    """
    for name, spec in SHEETS.items():
        written = apply_placement(PROJECT / f"{name}.kicad_sch", spec)
        print(f"{name:16s} {written}")

    problems = validate_layout(ROOT, CIRCUIT_JSON)
    print(f"\nproblems: {len(problems)}")
    for problem in problems[:20]:
        print("  ", problem)
    if problems:
        return 1

    images = render_sheets(ROOT, PROJECT / "img")
    print(f"rendered {len(images)} sheet(s) to {PROJECT / 'img'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
