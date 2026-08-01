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
from circuit_synth.kicad.layout.spec import PowerPlacement as P

logging.disable(logging.CRITICAL)

PROJECT = Path(
    sys.argv[1] if len(sys.argv) > 1 else "examples/build/three_phase_driver"
)
ROOT = PROJECT / "ThreePhaseDriver.kicad_sch"
CIRCUIT_JSON = PROJECT / "ThreePhaseDriver.json"


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


# ------------------------------------------------------------ half bridge ---
# The sheet reads in bands: the drive rail across the top, the bootstrap under
# it, then the high side gate path, the phase tie, and the low side gate path.
# The two MOSFETs stand as a totem pole on the right with the phase node
# between them, and the current sense sits below the shunt.
HALF_BRIDGE = PlacementSpec(
    paper="A3",
    components=[
        C("U4", (88.9, 101.6), 0),      # IR2101 gate driver
        C("C18", (68.58, 83.82), 0),    # driver decoupling
        C("D1", (116.84, 76.2), 0),     # bootstrap diode
        C("C17", (146.05, 88.9), 0),    # bootstrap capacitor
        C("R6", (130.81, 96.52), 90),   # high side gate resistor
        C("R7", (130.81, 109.22), 90),  # low side gate resistor
        C("Q1", (167.64, 91.44), 0),    # high side FET
        C("Q2", (167.64, 114.3), 0),    # low side FET
        C("R8", (170.18, 127.0), 0),    # Kelvin shunt
        C("U5", (127.0, 130.81), 0),    # current sense amplifier
        C("C19", (109.22, 127.0), 0),   # amplifier supply decoupling
        C("R9", (146.05, 130.81), 90),  # output filter resistor
        C("C20", (157.48, 137.16), 0),  # output filter capacitor
        C("R10", (184.15, 99.06), 90),  # back-EMF divider, top
        C("R11", (187.96, 110.49), 0),  # back-EMF divider, bottom
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
        # Kelvin taps into the current sense amplifier
        ((172.72, 129.54), (172.72, 128.27)),
        ((119.38, 128.27), (172.72, 128.27)),
        ((170.18, 132.08), (119.38, 132.08)),
        ((119.38, 132.08), (119.38, 133.35)),
        # Amplifier supply and grounds
        ((109.22, 123.19), (124.46, 123.19)),
        ((124.46, 119.38), (124.46, 123.19)),
        ((109.22, 130.81), (109.22, 134.62)),
        ((124.46, 138.43), (124.46, 142.24)),
        ((129.54, 138.43), (129.54, 142.24)),
        # Amplifier output through the filter to the ADC
        ((134.62, 130.81), (142.24, 130.81)),
        ((149.86, 130.81), (167.64, 130.81)),
        ((157.48, 130.81), (157.48, 133.35)),
        ((157.48, 140.97), (157.48, 144.78)),
        # Back-EMF divider off the phase node
        ((170.18, 99.06), (180.34, 99.06)),
        ((187.96, 99.06), (187.96, 106.68)),
        ((187.96, 114.3), (187.96, 118.11)),
        ((187.96, 102.87), (198.12, 102.87)),
    ],
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
        (124.46, 123.19),
        (157.48, 130.81),
        (187.96, 102.87),
    ],
    labels=[
        port("VDRV", (55.88, 76.2), 180, "input"),
        port("HI", (66.04, 101.6), 180, "input"),
        port("LI", (66.04, 104.14), 180, "input"),
        port("VM", (170.18, 81.28), 90, "input"),
        port("PHASE", (176.53, 104.14), 0, "output"),
        port("ISENSE", (167.64, 130.81), 0, "output"),
        port("BEMF", (198.12, 102.87), 0, "output"),
        port("VDRV", (124.46, 119.38), 90, "input"),
        L("BOOT", (127.0, 85.09), 0, "local"),
        L("HGATE", (140.97, 96.52), 0, "local"),
        L("LGATE", (140.97, 109.22), 0, "local"),
    ],
    power=[
        ground((68.58, 91.44)),
        ground((88.9, 119.38)),
        ground((180.34, 124.46)),
        ground((109.22, 134.62)),
        ground((124.46, 142.24)),
        ground((129.54, 142.24)),
        ground((157.48, 144.78)),
        ground((187.96, 118.11)),
    ],
)

# The three half-bridges are the same block, so one layout serves all of them.
HALF_BRIDGE_RENAMES = {
    "HalfBridge2": {
        "U4": "U6", "Q1": "Q3", "Q2": "Q4", "R6": "R12", "R7": "R13",
        "C17": "C21", "D1": "D2", "C18": "C22", "R8": "R14", "U5": "U7",
        "C19": "C23", "R9": "R15", "C20": "C24", "R10": "R16", "R11": "R17",
    },
    "HalfBridge3": {
        "U4": "U8", "Q1": "Q5", "Q2": "Q6", "R6": "R18", "R7": "R19",
        "C17": "C25", "D1": "D3", "C18": "C26", "R8": "R20", "U5": "U9",
        "C19": "C27", "R9": "R21", "C20": "C28", "R10": "R22", "R11": "R23",
    },
}

# ------------------------------------------------------------------ power ---
# Fused input into the motor rail, with the linear regulator making 3.3V.
POWER = PlacementSpec(
    paper="A4",
    components=[
        C("F1", (63.5, 76.2), 90),      # input fuse
        C("C2", (88.9, 83.82), 0),      # motor rail bulk
        C("C5", (104.14, 83.82), 0),    # motor rail ceramic
        C("C3", (76.2, 99.06), 0),      # regulator input
        C("U1", (114.3, 96.52), 0),     # AMS1117-3.3
        C("C4", (146.05, 104.14), 0),   # regulator output
    ],
    wires=[
        # VBUS in, through the fuse, into the motor rail
        ((45.72, 76.2), (59.69, 76.2)),
        ((67.31, 76.2), (127.0, 76.2)),
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
    ],
    junctions=[
        (88.9, 76.2),
        (104.14, 76.2),
        (127.0, 76.2),
        (50.8, 76.2),
        (76.2, 96.52),
        (146.05, 96.52),
    ],
    labels=[
        port("VBUS", (45.72, 76.2), 180, "input"),
        port("VMOTOR", (127.0, 71.12), 90, "output"),
        port("V3V3", (152.4, 96.52), 0, "output"),
    ],
    power=[
        ground((88.9, 91.44)),
        ground((104.14, 91.44)),
        ground((76.2, 106.68)),
        ground((114.3, 109.22)),
        ground((146.05, 111.76)),
    ],
)

# -------------------------------------------------------------------- usb ---
# The receptacle on the left, its CC pulldowns beneath it, VBUS and the data
# pair leaving to the right.
USB = PlacementSpec(
    paper="A4",
    components=[
        C("J1", (63.5, 88.9), 0),      # USB-C receptacle
        C("R1", (91.44, 90.17), 0),    # CC1 pulldown
        C("R2", (101.6, 92.71), 0),    # CC2 pulldown
        C("C1", (114.3, 80.01), 0),    # VBUS decoupling
    ],
    wires=[
        # VBUS out of the receptacle, with its decoupling
        ((78.74, 73.66), (132.08, 73.66)),
        ((114.3, 73.66), (114.3, 76.2)),
        ((114.3, 83.82), (114.3, 87.63)),
        # CC pulldowns
        ((78.74, 78.74), (91.44, 78.74)),
        ((91.44, 78.74), (91.44, 86.36)),
        ((91.44, 93.98), (91.44, 97.79)),
        ((78.74, 81.28), (101.6, 81.28)),
        ((101.6, 81.28), (101.6, 88.9)),
        ((101.6, 96.52), (101.6, 100.33)),
        # Data pair
        ((78.74, 91.44), (132.08, 91.44)),
        ((78.74, 86.36), (132.08, 86.36)),
        # Shell and ground returns
        ((63.5, 111.76), (63.5, 115.57)),
        ((55.88, 111.76), (55.88, 115.57)),
    ],
    junctions=[],
    labels=[
        port("VBUS", (132.08, 73.66), 0, "output"),
        port("USB_DP", (132.08, 91.44), 0, "output"),
        port("USB_DM", (132.08, 86.36), 0, "output"),
    ],
    power=[
        ground((63.5, 115.57)),
        ground((55.88, 115.57)),
        ground((91.44, 97.79)),
        ground((101.6, 100.33)),
        ground((114.3, 87.63)),
    ],
)


SHEETS = {
    "HalfBridge": HALF_BRIDGE,
    "HalfBridge2": HALF_BRIDGE.renamed(HALF_BRIDGE_RENAMES["HalfBridge2"]),
    "HalfBridge3": HALF_BRIDGE.renamed(HALF_BRIDGE_RENAMES["HalfBridge3"]),
    "Power": POWER,
    "UsbProgramming": USB,
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
    print(f"\nconnectivity problems: {len(problems)}")
    for problem in problems[:15]:
        print("  ", problem)
    if problems:
        return 1

    images = render_sheets(ROOT, PROJECT / "img")
    print(f"rendered {len(images)} sheet(s) to {PROJECT / 'img'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
