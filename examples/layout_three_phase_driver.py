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

from circuit_synth.kicad.layout import PlacementSpec, apply_placement
from circuit_synth.kicad.spice_hygiene import make_spice_clean
from circuit_synth.verify import verify_project
from circuit_synth.kicad.layout.extract import instance_renames
from circuit_synth.kicad.layout.spec import ComponentPlacement as C
from circuit_synth.kicad.layout.spec import LabelPlacement as L
from circuit_synth.kicad.layout.spec import GroupPlacement as G
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
        C("R12", (63.5, 80.01), 0),    # divider, top
        C("R13", (63.5, 96.52), 0),    # divider, bottom
        C("R14", (76.2, 90.17), 0),   # this phase's leg of the virtual neutral
        C("R15", (127.0, 78.74), 0),  # output pullup
        C("U4", (101.6, 88.9), 0),    # zero-crossing comparator
        C("C19", (137.16, 74.93), 0),  # comparator decoupling
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
    groups=[
        G(
            "BACK-EMF ZERO CROSSING",
            (38.1, 60.96),
            (127.0, 95.25),
            "R12 and R13 divide the phase by 11, which keeps a 36V rail inside the\n"
            "comparator's 3.3V input range with margin. R14 is this phase's leg of the\n"
            "star point the three phases share, so NEUTRAL sits at their average and the\n"
            "comparator sees the phase cross it. U4 is a push-pull part; R15 only holds\n"
            "the edge defined while it starts up. Valid because the comparison is\n"
            "ratiometric: both inputs are divided by the same network, so the crossing\n"
            "instant does not move with rail voltage.",
        ),
    ],
    notes=[N((38.1, 165.1), (127.0, 25.4))],
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
        C("C21", (68.58, 83.82), 0),    # driver decoupling
        C("D1", (116.84, 76.2), 0),     # bootstrap diode
        C("C20", (146.05, 88.9), 0),    # bootstrap capacitor
        C("R16", (130.81, 96.52), 90),  # high side gate resistor
        C("R17", (130.81, 109.22), 90),  # low side gate resistor
        C("Q1", (167.64, 91.44), 0),    # high side FET
        C("Q2", (167.64, 114.3), 0),    # low side FET
        C("R18", (170.18, 127.0), 0),    # Kelvin shunt
        C("U6", (196.85, 149.86), 0),    # current sense amplifier
        C("C22", (241.3, 144.78), 0),    # amplifier supply decoupling
        C("R19", (215.9, 149.86), 90),   # output filter resistor
        C("C23", (226.06, 156.21), 0),   # output filter capacitor
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
    groups=[
        G(
            "ONE PHASE: GATE DRIVE, POWER STAGE, CURRENT AND BACK-EMF SENSE",
            (45.72, 60.96),
            (266.7, 127.0),
            "The IR2101 drives both gates from one rail, its high side referenced to the\n"
            "phase node through the bootstrap D1/C20; C20 is refreshed every cycle the\n"
            "low side is on, which the commutation scheme guarantees. R16 and R17 damp\n"
            "the gate drive. The low side returns through R18, a Kelvin-connected shunt,\n"
            "so U6 measures the shunt voltage alone and not the drop along the power\n"
            "path; R19 and C23 roll the measurement off before the ADC. Back-EMF sensing\n"
            "for this phase is the nested BackEmf block, fed from the phase node.",
        ),
    ],
    notes=[N((45.72, 196.85), (203.2, 25.4))],
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
        ((45.72, 71.12), (35.56, 71.12)),
        ((88.9, 91.44), (80.01, 91.44)),
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
    groups=[
        G(
            "BOARD SUPPLY AND RAIL MONITOR",
            (33.02, 46.99),
            (177.8, 120.65),
            "F1 protects the board against a shorted bridge, which is the failure this\n"
            "supply has to survive. C2 is the bulk the motor rail needs to absorb the\n"
            "switching current, C5 the ceramic beside it for the fast edges the\n"
            "electrolytic cannot follow. U1 makes the logic rail from the same input;\n"
            "C3 and C4 are the input and output capacitors its datasheet asks for.\n"
            "R3 and R4 divide the motor rail by 11 into the MCU's ADC, so the duty\n"
            "cycle can be corrected for supply droop rather than assuming a fixed rail.",
        ),
    ],
    notes=[N((33.02, 175.26), (177.8, 20.32))],
    junctions=[
        (45.72, 71.12),
        (88.9, 91.44),
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
        P("power:PWR_FLAG", (35.56, 71.12), 0),
        P("power:PWR_FLAG", (80.01, 91.44), 0),
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
    groups=[
        G(
            "USB-C DEVICE PORT",
            (43.18, 55.88),
            (127.0, 101.6),
            "R1 and R2 are the 5.1k pulldowns a USB-C device puts on both CC pins; they\n"
            "are what tells a source this is a device, and having one on each is what\n"
            "lets the cable go in either way up. Both halves of the receptacle carry the\n"
            "same D+ and D-, so each pair is tied together at the connector. C1 decouples\n"
            "VBUS where it enters the board. Valid as a device-only port: no VBUS source\n"
            "path, no Rp, so the board can never try to power a host.",
        ),
    ],
    notes=[N((43.18, 165.1), (127.0, 25.4))],
    no_connects=[
        (78.74, 101.6),
        (78.74, 104.14),
    ],
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
# on the right with its supplies stubbed up, its interfaces stubbed left and
# its GPIO stubbed right; the nets are carried by labels, which is how a dense
# MCU page is drawn and the only way it stays readable.
#
# Everything around it is grouped into the circuit it belongs to, each boxed
# and titled, each carrying the reason it is drawn the way it is. The supply,
# flash, crystal, strap and USB circuits are copied from the minimal design in
# "Hardware design with RP2040" (RP-008279-DS chapter 2) rather than invented,
# so most of the reasoning is a citation - which is the point of writing it
# down: a reviewer can check the page against the document without guessing
# which document.
MCU = PlacementSpec(
    paper="A2",
    components=[
        C("U2", (482.6, 200.66), 0),     # RP2040
        # 3V3 decoupling
        C("C9", (68.58, 104.14), 0),
        C("C10", (81.28, 104.14), 0),
        C("C11", (93.98, 104.14), 0),
        C("C12", (106.68, 104.14), 0),
        C("C13", (119.38, 104.14), 0),
        C("C14", (132.08, 104.14), 0),
        C("C15", (144.78, 104.14), 0),   # USB_VDD
        C("C16", (157.48, 104.14), 0),   # VREG_VIN, 1uF
        # Core rail and ADC supply
        C("C17", (240.03, 104.14), 0),   # VREG_VOUT, 1uF
        C("R9", (265.43, 104.14), 0),    # ADC supply filter
        C("C18", (304.8, 104.14), 0),    # ADC supply decoupling
        # Reset and boot straps
        C("R7", (58.42, 201.93), 0),     # RUN pullup
        C("C8", (76.2, 201.93), 0),      # RUN delay
        C("R8", (93.98, 201.93), 0),     # QSPI_SS pullup
        C("R6", (127.0, 201.93), 0),     # BOOTSEL strap resistor
        C("J3", (156.21, 210.82), 0),    # USB_BOOT header
        # USB series termination
        C("R10", (279.4, 195.58), 90),
        C("R11", (279.4, 208.28), 90),
        # QSPI flash
        C("U3", (88.9, 311.15), 0),
        # Crystal
        C("Y1", (215.9, 306.07), 0),
        C("C6", (212.09, 316.23), 0),
        C("C7", (219.71, 316.23), 0),
        C("R5", (241.3, 306.07), 270),   # crystal series resistor
        # SWD
        C("J2", (393.7, 311.15), 0),
    ],
    groups=[
        G(
            "3V3 DECOUPLING",
            (38.1, 76.2),
            (152.4, 69.85),
            "One 100nF per power pin, as RP-008279-DS section 2.1.2 asks for: six for the\n"
            "IOVDD pins (C9-C14) and one for USB_VDD (C15). C16 is the exception the same\n"
            "section makes, because the internal regulator wants 1uF at its input rather\n"
            "than 100nF. Each capacitor taps the rail on its own stub, so on the board it\n"
            "can sit against the pin it decouples.",
        ),
        G(
            "CORE RAIL AND ADC SUPPLY",
            (215.9, 76.2),
            (114.3, 69.85),
            "C17 is the second 1uF the internal regulator needs, on VREG_VOUT. R9 and C18\n"
            "filter the ADC supply off the digital 3.3V; that is an addition to the\n"
            "reference design, made because the three phase currents are measured through\n"
            "this ADC and supply noise lands directly on those readings.",
        ),
        G(
            "RESET AND BOOT STRAPS",
            (38.1, 173.99),
            (177.8, 76.2),
            "R8 is the 10k pull-up RP-008279-DS section 2.2 requires on QSPI_SS, so the\n"
            "flash sees its chip select high as the rails come up. R6 and J3 are the\n"
            "BOOTSEL strap from the same section: shorting J3 pulls QSPI_SS low through 1k\n"
            "at reset and the part enumerates as mass storage, which is the only way to\n"
            "load the first program. R7 and C8 are an addition, to condition a reset\n"
            "button; the reference design leaves RUN bare on its internal pull-up.",
        ),
        G(
            "USB SERIES TERMINATION",
            (241.3, 173.99),
            (101.6, 76.2),
            "27R in series with each data line, from RP-008279-DS section 2.4.1, to meet\n"
            "the 90 ohm differential impedance of the USB pair. They belong against the\n"
            "RP2040 rather than the connector. No pull-ups or pull-downs are fitted: the\n"
            "RP2040's USB pins have them built in.",
        ),
        G(
            "QSPI FLASH",
            (38.1, 278.13),
            (101.6, 77.47),
            "W25Q128JVS, the device the reference design uses and the largest the RP2040\n"
            "supports. The six QSPI signals go straight to it. They are the fastest nets\n"
            "on the page, so on the board they want to be short and kept away from\n"
            "everything else.",
        ),
        G(
            "12MHZ CRYSTAL",
            (165.1, 278.13),
            (177.8, 77.47),
            "The circuit from RP-008279-DS section 2.3, copied rather than reworked: a\n"
            "12MHz ABM8-272-T3, two 15pF load capacitors at the crystal's own terminals,\n"
            "and R5, a 1k series resistor between XOUT and the crystal so it is not\n"
            "over-driven at an IOVDD of 3.3V. 15pF each gives 7.5pF in series, plus about\n"
            "3pF of parasitic, which is the 10pF the crystal is specified for. Any change\n"
            "here needs testing over temperature, which is why none was made.",
        ),
        G(
            "SWD DEBUG",
            (355.6, 278.13),
            (76.2, 77.47),
            "SWCLK and SWDIO on a 3-pin header with ground, for a debug probe. Not part\n"
            "of the reference design; the board can be programmed over USB without it,\n"
            "but not single-stepped.",
        ),
    ],
    wires=[
        # --- 3V3 decoupling: a rail with one capacitor under each supply pin
        ((58.42, 95.25), (170.18, 95.25)),
        ((68.58, 95.25), (68.58, 100.33)),
        ((81.28, 95.25), (81.28, 100.33)),
        ((93.98, 95.25), (93.98, 100.33)),
        ((106.68, 95.25), (106.68, 100.33)),
        ((119.38, 95.25), (119.38, 100.33)),
        ((132.08, 95.25), (132.08, 100.33)),
        ((144.78, 95.25), (144.78, 100.33)),
        ((157.48, 95.25), (157.48, 100.33)),
        ((68.58, 107.95), (68.58, 111.76)),
        ((81.28, 107.95), (81.28, 111.76)),
        ((93.98, 107.95), (93.98, 111.76)),
        ((106.68, 107.95), (106.68, 111.76)),
        ((119.38, 107.95), (119.38, 111.76)),
        ((132.08, 107.95), (132.08, 111.76)),
        ((144.78, 107.95), (144.78, 111.76)),
        ((157.48, 107.95), (157.48, 111.76)),
        # --- Core rail and ADC supply
        ((240.03, 100.33), (240.03, 95.25)),
        ((240.03, 107.95), (240.03, 111.76)),
        ((265.43, 100.33), (265.43, 95.25)),
        ((265.43, 107.95), (265.43, 116.84)),
        ((265.43, 116.84), (252.73, 116.84)),
        ((304.8, 100.33), (304.8, 95.25)),
        ((304.8, 107.95), (304.8, 111.76)),
        ((304.8, 95.25), (317.5, 95.25)),
        # --- Reset and boot straps
        ((58.42, 198.12), (58.42, 193.04)),
        ((58.42, 205.74), (58.42, 210.82)),
        ((76.2, 198.12), (76.2, 193.04)),
        ((76.2, 205.74), (76.2, 210.82)),
        ((93.98, 198.12), (93.98, 193.04)),
        ((93.98, 205.74), (93.98, 210.82)),
        ((127.0, 198.12), (127.0, 193.04)),
        ((127.0, 205.74), (127.0, 210.82)),
        ((127.0, 210.82), (151.13, 210.82)),
        ((151.13, 213.36), (144.78, 213.36)),
        ((144.78, 213.36), (144.78, 218.44)),
        # --- USB series termination
        ((275.59, 195.58), (266.7, 195.58)),
        ((283.21, 195.58), (304.8, 195.58)),
        ((275.59, 208.28), (266.7, 208.28)),
        ((283.21, 208.28), (304.8, 208.28)),
        # --- QSPI flash
        ((78.74, 303.53), (72.39, 303.53)),
        ((78.74, 306.07), (72.39, 306.07)),
        ((78.74, 308.61), (72.39, 308.61)),
        ((78.74, 311.15), (72.39, 311.15)),
        ((78.74, 313.69), (72.39, 313.69)),
        ((78.74, 316.23), (72.39, 316.23)),
        ((88.9, 298.45), (88.9, 293.37)),
        ((88.9, 323.85), (88.9, 327.66)),
        # --- Crystal
        ((185.42, 306.07), (212.09, 306.07)),
        ((212.09, 306.07), (212.09, 312.42)),
        ((219.71, 306.07), (219.71, 312.42)),
        ((219.71, 306.07), (237.49, 306.07)),
        ((245.11, 306.07), (266.7, 306.07)),
        ((212.09, 320.04), (212.09, 323.85)),
        ((219.71, 320.04), (219.71, 323.85)),
        # --- SWD
        ((388.62, 308.61), (382.27, 308.61)),
        ((388.62, 311.15), (382.27, 311.15)),
        ((388.62, 313.69), (374.65, 313.69)),
        ((374.65, 313.69), (374.65, 317.5)),
        # --- The MCU's own stubs: supplies up, interfaces left, GPIO right
        ((469.9, 154.94), (469.9, 149.86)),
        ((472.44, 154.94), (472.44, 149.86)),
        ((480.06, 154.94), (480.06, 149.86)),
        ((485.14, 154.94), (485.14, 149.86)),
        ((490.22, 154.94), (490.22, 149.86)),
        ((495.3, 154.94), (495.3, 149.86)),
        ((482.6, 246.38), (482.6, 250.19)),
        ((457.2, 177.8), (450.85, 177.8)),
        ((457.2, 185.42), (450.85, 185.42)),
        ((457.2, 187.96), (450.85, 187.96)),
        ((457.2, 195.58), (450.85, 195.58)),
        ((457.2, 198.12), (450.85, 198.12)),
        ((457.2, 200.66), (450.85, 200.66)),
        ((457.2, 203.2), (450.85, 203.2)),
        ((457.2, 205.74), (450.85, 205.74)),
        ((457.2, 208.28), (450.85, 208.28)),
        ((457.2, 215.9), (450.85, 215.9)),
        ((457.2, 226.06), (450.85, 226.06)),
        ((457.2, 233.68), (450.85, 233.68)),
        ((457.2, 236.22), (450.85, 236.22)),
        ((508.0, 162.56), (514.35, 162.56)),
        ((508.0, 165.1), (514.35, 165.1)),
        ((508.0, 167.64), (514.35, 167.64)),
        ((508.0, 170.18), (514.35, 170.18)),
        ((508.0, 172.72), (514.35, 172.72)),
        ((508.0, 175.26), (514.35, 175.26)),
        ((508.0, 177.8), (514.35, 177.8)),
        ((508.0, 180.34), (514.35, 180.34)),
        ((508.0, 182.88), (514.35, 182.88)),
        ((508.0, 231.14), (514.35, 231.14)),
        ((508.0, 233.68), (514.35, 233.68)),
        ((508.0, 236.22), (514.35, 236.22)),
        ((508.0, 238.76), (514.35, 238.76)),
    ],
    notes=[N((38.1, 25.4), (304.8, 30.48))],
    # The GPIO this design does not use, and TESTEN, are marked no-connect
    # rather than left bare: an unmarked floating pin and a pin somebody forgot
    # look identical to ERC, and only one of them is deliberate.
    no_connects=[
        (508.0, 185.42),
        (508.0, 187.96),
        (508.0, 190.5),
        (508.0, 193.04),
        (508.0, 195.58),
        (508.0, 198.12),
        (508.0, 200.66),
        (508.0, 203.2),
        (508.0, 205.74),
        (508.0, 208.28),
        (508.0, 210.82),
        (508.0, 213.36),
        (508.0, 215.9),
        (508.0, 218.44),
        (508.0, 220.98),
        (508.0, 223.52),
        (508.0, 226.06),
        (457.2, 170.18),
    ],
    junctions=[
        (68.58, 95.25),
        (81.28, 95.25),
        (93.98, 95.25),
        (106.68, 95.25),
        (119.38, 95.25),
        (132.08, 95.25),
        (144.78, 95.25),
        (157.48, 95.25),
        (212.09, 306.07),
        (219.71, 306.07),
    ],
    labels=[
        port("V3V3", (58.42, 95.25), 180, "input"),
        port("USB_DP", (304.8, 195.58), 0, "input"),
        port("USB_DM", (304.8, 208.28), 0, "input"),
        port("AH", (514.35, 162.56), 0, "output"),
        port("AL", (514.35, 165.1), 0, "output"),
        port("BH", (514.35, 167.64), 0, "output"),
        port("BL", (514.35, 170.18), 0, "output"),
        port("CH", (514.35, 172.72), 0, "output"),
        port("CL", (514.35, 175.26), 0, "output"),
        port("ZC_A", (514.35, 177.8), 0, "input"),
        port("ZC_B", (514.35, 180.34), 0, "input"),
        port("ZC_C", (514.35, 182.88), 0, "input"),
        port("ISENSE_A", (514.35, 231.14), 0, "input"),
        port("ISENSE_B", (514.35, 233.68), 0, "input"),
        port("ISENSE_C", (514.35, 236.22), 0, "input"),
        port("VRAIL_SENSE", (514.35, 238.76), 0, "input"),
        # Supply nets, named where they are made and where they are used
        L("V1V1", (240.03, 95.25), 90, "local"),
        L("V3V3", (265.43, 95.25), 90, "local"),
        L("ADC_AVDD", (252.73, 116.84), 180, "local"),
        L("ADC_AVDD", (304.8, 95.25), 90, "local"),
        L("V3V3", (58.42, 193.04), 90, "local"),
        L("RUN", (58.42, 210.82), 270, "local"),
        L("RUN", (76.2, 193.04), 90, "local"),
        L("V3V3", (93.98, 193.04), 90, "local"),
        L("QSPI_SS", (93.98, 210.82), 270, "local"),
        L("QSPI_SS", (127.0, 193.04), 90, "local"),
        L("USB_DP_R", (266.7, 195.58), 180, "local"),
        L("USB_DM_R", (266.7, 208.28), 180, "local"),
        L("QSPI_SS", (72.39, 303.53), 180, "local"),
        L("QSPI_SCLK", (72.39, 306.07), 180, "local"),
        L("QSPI_SD0", (72.39, 308.61), 180, "local"),
        L("QSPI_SD1", (72.39, 311.15), 180, "local"),
        L("QSPI_SD2", (72.39, 313.69), 180, "local"),
        L("QSPI_SD3", (72.39, 316.23), 180, "local"),
        L("V3V3", (88.9, 293.37), 90, "local"),
        L("XIN", (185.42, 306.07), 180, "local"),
        L("XOUT_DRV", (266.7, 306.07), 0, "local"),
        L("SWCLK", (382.27, 308.61), 180, "local"),
        L("SWDIO", (382.27, 311.15), 180, "local"),
        # The MCU's own pins
        L("V3V3", (469.9, 149.86), 90, "local"),
        L("ADC_AVDD", (472.44, 149.86), 90, "local"),
        L("V3V3", (480.06, 149.86), 90, "local"),
        L("V3V3", (485.14, 149.86), 90, "local"),
        L("V1V1", (490.22, 149.86), 90, "local"),
        L("V1V1", (495.3, 149.86), 90, "local"),
        L("RUN", (450.85, 177.8), 180, "local"),
        L("USB_DM_R", (450.85, 185.42), 180, "local"),
        L("USB_DP_R", (450.85, 187.96), 180, "local"),
        L("QSPI_SS", (450.85, 195.58), 180, "local"),
        L("QSPI_SCLK", (450.85, 198.12), 180, "local"),
        L("QSPI_SD0", (450.85, 200.66), 180, "local"),
        L("QSPI_SD1", (450.85, 203.2), 180, "local"),
        L("QSPI_SD2", (450.85, 205.74), 180, "local"),
        L("QSPI_SD3", (450.85, 208.28), 180, "local"),
        L("XIN", (450.85, 215.9), 180, "local"),
        L("XOUT_DRV", (450.85, 226.06), 180, "local"),
        L("SWCLK", (450.85, 233.68), 180, "local"),
        L("SWDIO", (450.85, 236.22), 180, "local"),
    ],
    power=[
        ground((68.58, 111.76)),
        ground((81.28, 111.76)),
        ground((93.98, 111.76)),
        ground((106.68, 111.76)),
        ground((119.38, 111.76)),
        ground((132.08, 111.76)),
        ground((144.78, 111.76)),
        ground((157.48, 111.76)),
        ground((240.03, 111.76)),
        ground((304.8, 111.76)),
        P("power:PWR_FLAG", (317.5, 95.25), 0),
        ground((76.2, 210.82)),
        ground((144.78, 218.44)),
        ground((88.9, 327.66)),
        ground((212.09, 323.85)),
        ground((219.71, 323.85)),
        ground((374.65, 317.5)),
        ground((482.6, 250.19)),
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
        components=[C("J4", (500.38, 127.0), 0)],
        sheets=sheets,
        notes=[N((177.8, 190.5), (139.7, 25.4))],
        wires=wires,
        labels=labels,
    )


ROOT_SPEC = _root()


# One layout per block. A block instantiated more than once is laid out once
# and renamed onto its other instances, using the mapping worked out from the
# generated circuit rather than a table kept up to date by hand.
BLOCKS = {
    "ThreePhaseDriver": ROOT_SPEC,
    "BackEmf": BACK_EMF,
    "HalfBridge": HALF_BRIDGE,
    "Power": POWER,
    "UsbProgramming": USB,
    "Mcu": MCU,
}


def sheets() -> dict:
    """Work out the layout for every sheet in the generated project.

    Returns:
        Sheet name to the placement to apply to it.
    """
    renames = instance_renames(CIRCUIT_JSON)
    result = {}
    for sheet, mapping in renames.items():
        block = next((name for name in BLOCKS if mapping.get(name) == sheet), None)
        if block:
            result[sheet] = BLOCKS[block].renamed(mapping)
    return result


def main() -> int:
    """Apply every sheet layout, then check the whole project.

    Returns:
        Process exit status: non-zero when any check failed.
    """
    for name, spec in sheets().items():
        written = apply_placement(PROJECT / f"{name}.kicad_sch", spec)
        print(f"{name:16s} {written}")

    # The values an engineer wants to read - 220uF/50V - are not values a
    # simulator can read, and a fuse called F1 is a controlled source as far as
    # SPICE is concerned. This gives every part a model or an exemption, so the
    # project opens in KiCad's simulator instead of failing to load.
    print(f"\n{make_spice_clean(PROJECT).summary()}")

    report = verify_project(ROOT, CIRCUIT_JSON)
    print()
    print(report.summary())
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
