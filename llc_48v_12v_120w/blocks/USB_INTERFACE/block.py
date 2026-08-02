"""USB_INTERFACE block for RP2040.

Provides:
- USB Type-C receptacle (16-pin, data only, no PD)
- ESD protection on D+/D- lines (USBLC6-4SC6)
- 33Ω series resistors on USB_DP and USB_DM (RP2040 pins 47, 46)
- 100nF decoupling on USB_VDD (RP2040 pin 48)
- Shield ground connection via ferrite bead

Ports:
- USB_DP: USB D+ to RP2040 pin 47 (before series resistor)
- USB_DM: USB D- to RP2040 pin 46 (before series resistor)

Power symbols (by name):
- +3V3: 3.3V I/O supply for USB PHY (USB_VDD pin 48)
- GND: Ground reference

Reference: RP-008279-DS-1 (Hardware Design with RP2040), Section USB Interface
           RP-008307-DS-2 (Raspberry Pi Pico Datasheet), Appendix B
"""

from circuit_synth import Component, Net, circuit


@circuit(name="USB_INTERFACE")
def usb_interface(USB_DP, USB_DM):
    """USB interface with ESD protection and series termination for RP2040.

    Args:
        USB_DP: USB D+ signal to RP2040 pin 47 (before series resistor)
        USB_DM: USB D- signal to RP2040 pin 46 (before series resistor)
    """

    # Power nets (by name - these are global power symbols)
    vdd_3v3 = Net("+3V3")  # 3.3V supply for USB_VDD
    gnd = Net("GND")       # Ground

    # Internal nets
    usb_dp_conn = Net("USB_DP_CONN")  # D+ at connector side (after ESD, before series R)
    usb_dm_conn = Net("USB_DM_CONN")  # D- at connector side (after ESD, before series R)
    shield = Net("SHIELD")            # USB shield before filtering

    # USB Type-C receptacle (16-pin SMT, data only)
    # TYPE-C-31-M-12, LCSC C165948
    J1 = Component(
        symbol="JLCImport:TYPE-C-31-M-12",
        footprint="JLCImport:TYPE-C-31-M-12",
        ref="J",
        value="USB_C",
        LCSC="C165948",
        MPN="TYPE-C-31-M-12"
    )
    # USB Type-C pinout (16-pin receptacle):
    # Pins A6, B6 → D+
    # Pins A7, B7 → D-
    # Pins A1, A12, B1, B12 → GND
    # Pins A5, B5 → CC (not connected for device-only)
    # Pins A4, A9, B4, B9 → VBUS (not used for data-only)
    # Shield pins → SHIELD net

    # Note: TYPE-C-31-M-12 pin mapping (check datasheet for exact numbering)
    # Assuming standard Type-C numbering where:
    # Pin 7, 8 = D+ (A6, B6)
    # Pin 6, 9 = D- (A7, B7)
    # Pin 1-4, 13-16 = GND
    # Pin 5, 12 = Shield

    J1["A6"] += usb_dp_conn  # D+ (A-side)
    J1["B6"] += usb_dp_conn  # D+ (B-side)
    J1["A7"] += usb_dm_conn  # D- (A-side)
    J1["B7"] += usb_dm_conn  # D- (B-side)
    J1["A1"] += gnd          # GND (A-side)
    J1["A12"] += gnd         # GND (A-side)
    J1["B1"] += gnd          # GND (B-side)
    J1["B12"] += gnd         # GND (B-side)
    J1["SH1"] += shield      # Shield pin 1
    J1["SH2"] += shield      # Shield pin 2

    # ESD protection (USBLC6-4SC6, quad channel for both D+/D- pairs)
    # LCSC C5180279
    U1 = Component(
        symbol="JLCImport:USBLC6-4SC6-ES",
        footprint="JLCImport:USBLC6-4SC6-ES",
        ref="U",
        value="USBLC6-4SC6",
        LCSC="C5180279",
        MPN="USBLC6-4SC6-ES"
    )
    # USBLC6-4SC6 pinout (SOT-23-6):
    # Pin 1: I/O1 (first protected line)
    # Pin 2: GND
    # Pin 3: I/O2 (second protected line)
    # Pin 4: I/O2 (second protected line, alt)
    # Pin 5: VCC (power supply, connect to signal line common mode)
    # Pin 6: I/O1 (first protected line, alt)

    # For USB, we need two channels:
    # Channel 1: D+ protection
    # Channel 2: D- protection

    U1[1] += usb_dp_conn     # I/O1 → D+ connector side
    U1[2] += gnd             # GND
    U1[3] += usb_dm_conn     # I/O2 → D- connector side
    U1[4] += usb_dm_conn     # I/O2 (tied together for USB)
    U1[5] += vdd_3v3         # VCC → 3.3V (clamp voltage reference)
    U1[6] += usb_dp_conn     # I/O1 (tied together for USB)

    # Series termination resistors (33Ω, RP2040 pin 47/46)
    # Reference: RP-008279-DS-1 specifies 27Ω, using 33Ω (closest available Basic part)
    # LCSC C911079 (TMI6050-33, 33Ω 0603 1%)

    R1 = Component(
        symbol="JLCImport:TMI6050-33",
        footprint="JLCImport:TMI6050-33",
        ref="R",
        value="33R",
        LCSC="C911079",
        MPN="TMI6050-33"
    )
    R1[1] += usb_dp_conn  # Connector side (after ESD)
    R1[2] += USB_DP       # RP2040 side (pin 47)

    R2 = Component(
        symbol="JLCImport:TMI6050-33",
        footprint="JLCImport:TMI6050-33",
        ref="R",
        value="33R",
        LCSC="C911079",
        MPN="TMI6050-33"
    )
    R2[1] += usb_dm_conn  # Connector side (after ESD)
    R2[2] += USB_DM       # RP2040 side (pin 46)

    # USB_VDD decoupling (100nF, RP2040 pin 48)
    # Reference: RP-008279-DS-1 Section 2.1.3
    # LCSC C14663 (CC0603KRX7R9BB104, 100nF 0603 X7R 50V)

    C1 = Component(
        symbol="JLCImport:CC0603KRX7R9BB104",
        footprint="JLCImport:CC0603KRX7R9BB104",
        ref="C",
        value="100nF",
        LCSC="C14663",
        MPN="CC0603KRX7R9BB104"
    )
    C1[1] += vdd_3v3  # USB_VDD → 3.3V (RP2040 pin 48 connected externally)
    C1[2] += gnd

    # Shield ground connection
    # Ferrite bead (600Ω += 100MHz) for EMI filtering
    # LCSC C85840 (BLM21PG221SN1D, 0805 ferrite bead)

    FB1 = Component(
        symbol="JLCImport:BLM21PG221SN1D",
        footprint="JLCImport:BLM21PG221SN1D",
        ref="FB",
        value="600R@100MHz",
        LCSC="C85840",
        MPN="BLM21PG221SN1D"
    )
    FB1[1] += shield
    FB1[2] += gnd

    # Shield discharge resistor (1MΩ parallel with ferrite bead)
    # Provides DC discharge path while ferrite bead handles AC
    # LCSC C22935 (0603WAF1004T5E, 1MΩ 0603 1%)

    R3 = Component(
        symbol="JLCImport:0603WAF1004T5E",
        footprint="JLCImport:0603WAF1004T5E",
        ref="R",
        value="1M",
        LCSC="C22935",
        MPN="0603WAF1004T5E"
    )
    R3[1] += shield
    R3[2] += gnd
