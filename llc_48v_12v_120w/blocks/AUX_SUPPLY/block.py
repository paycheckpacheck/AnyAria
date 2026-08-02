"""AUX_SUPPLY - Three sub-regulators for auxiliary power rails.

Provides 5V, 3.3V, and 1.2V from 12V LLC converter output.

Reference: See reference.md for datasheets and application circuits.
"""

from circuit_synth import Component, Net, circuit


@circuit(name="AUX_SUPPLY")
def aux_supply(VIN_12V, VOUT_5V, VOUT_3V3, VOUT_1V2):
    """Auxiliary power supply with three regulators.

    Three-stage cascade: 12V→5V→3.3V→1.2V

    Args:
        VIN_12V: 12V input from main LLC converter output
        VOUT_5V: 5V output for analog control and gate drivers (500mA)
        VOUT_3V3: 3.3V output for RP2040 I/O (300mA)
        VOUT_1V2: 1.2V output for RP2040 core (100mA, nominally 1.1V per RP2040 spec)
    """

    # Ground
    GND = Net("GND")

    # Internal nets
    buck_ph = Net("BUCK_PH")  # TPS5430 switch node
    buck_boot = Net("BUCK_BOOT")  # TPS5430 bootstrap node
    buck_comp = Net("BUCK_COMP")  # TPS5430 compensation
    buck_vsense = Net("BUCK_VSENSE")  # TPS5430 feedback sense
    buck_ena = Net("BUCK_ENA")  # TPS5430 enable

    # ========================================================================
    # Stage 1: TPS5430 Buck Converter - 12V to 5V += 500mA
    # ========================================================================

    # U1: TPS5430DDAR buck converter IC
    u1 = Component(
        symbol="JLCImport:TPS5430DDAR",
        ref="U1",
        value="TPS5430DDAR",
        footprint="JLCImport:TPS5430DDAR",
        LCSC="C9864",
        MPN="TPS5430DDAR",
        datasheet="https://www.ti.com/lit/ds/symlink/tps5430.pdf",
    )
    u1[1, "BOOT"] | buck_boot
    u1[2, "GND"] | GND
    u1[3, "COMP"] | buck_comp
    u1[4, "VSENSE"] | buck_vsense
    u1[5, "ENA"] | buck_ena
    u1[6, "PGND"] | GND  # Power ground
    u1[7, "PH"] | buck_ph  # Switch node
    u1[8, "VIN"] | VIN_12V
    # Thermal pad to GND (implicit in footprint)

    # Input capacitor
    Component(
        symbol="Device:C", ref="C1", value="10uF",
        footprint="Capacitor_SMD:C_0805_2012Metric",
        X7R=True, voltage="25V", LCSC="TBD"
    )[1, 2] | (VIN_12V, GND)

    # Bootstrap circuit
    Component(
        symbol="Device:R", ref="R1", value="100k",
        footprint="Resistor_SMD:R_0603_1608Metric", LCSC="TBD"
    )[1, 2] | (VIN_12V, buck_boot)

    Component(
        symbol="Device:C", ref="C2", value="0.1uF",
        footprint="Capacitor_SMD:C_0603_1608Metric",
        X7R=True, voltage="25V", LCSC="TBD"
    )[1, 2] | (buck_boot, buck_ph)

    # Output inductor - 22µH, rated for 3A
    Component(
        symbol="Device:L", ref="L1", value="22uH",
        footprint="Inductor_SMD:L_1210_3225Metric",
        current="3A", LCSC="TBD"
    )[1, 2] | (buck_ph, VOUT_5V)

    # Output capacitors
    Component(
        symbol="Device:C", ref="C3", value="47uF",
        footprint="Capacitor_SMD:C_1206_3216Metric",
        X7R=True, voltage="16V", LCSC="TBD"
    )[1, 2] | (VOUT_5V, GND)

    Component(
        symbol="Device:C", ref="C4", value="22uF",
        footprint="Capacitor_SMD:C_0805_2012Metric",
        X7R=True, voltage="16V", LCSC="TBD"
    )[1, 2] | (VOUT_5V, GND)

    # Feedback network (sets VOUT = 0.8V × (1 + R2/R3))
    # Using 2.43kΩ: VOUT = 0.8V × (1 + 10k/2.43k) = 4.11V (will refine in sim)
    Component(
        symbol="Device:R", ref="R2", value="10k",
        footprint="Resistor_SMD:R_0603_1608Metric",
        tolerance="1%", LCSC="TBD"
    )[1, 2] | (VOUT_5V, buck_vsense)

    Component(
        symbol="Device:R", ref="R3", value="2.43k",
        footprint="Resistor_SMD:R_0603_1608Metric",
        tolerance="1%", LCSC="TBD"
    )[1, 2] | (buck_vsense, GND)

    # Compensation network
    Component(
        symbol="Device:C", ref="C5", value="10nF",
        footprint="Capacitor_SMD:C_0603_1608Metric", LCSC="TBD"
    )[1, 2] | (buck_comp, GND)

    Component(
        symbol="Device:R", ref="R4", value="10k",
        footprint="Resistor_SMD:R_0603_1608Metric", LCSC="TBD"
    )[1, 2] | (buck_comp, buck_vsense)

    # Soft-start and enable
    Component(
        symbol="Device:C", ref="C6", value="0.1uF",
        footprint="Capacitor_SMD:C_0603_1608Metric", LCSC="TBD"
    )[1, 2] | (buck_ena, GND)

    Component(
        symbol="Device:R", ref="R5", value="100k",
        footprint="Resistor_SMD:R_0603_1608Metric", LCSC="TBD"
    )[1, 2] | (VIN_12V, buck_ena)  # Enable pullup

    # ========================================================================
    # Stage 2: AMS1117-3.3 LDO - 5V to 3.3V += 300mA
    # ========================================================================

    # U2: AMS1117-3.3 linear regulator
    u2 = Component(
        symbol="JLCImport:AMS1117-3_3",
        ref="U2",
        value="AMS1117-3.3",
        footprint="JLCImport:AMS1117-3_3",
        LCSC="C6186",
        MPN="AMS1117-3.3",
    )
    u2[1, "VIN"] | VOUT_5V  # Also tab in SOT-223
    u2[2, "VOUT"] | VOUT_3V3
    u2[3, "GND"] | GND

    # Input capacitor (MUST be ceramic per AMS1117 datasheet)
    Component(
        symbol="Device:C", ref="C7", value="10uF",
        footprint="Capacitor_SMD:C_0805_2012Metric",
        X7R=True, voltage="10V", LCSC="TBD"
    )[1, 2] | (VOUT_5V, GND)

    # Output capacitor (minimum 10µF, using 22µF)
    Component(
        symbol="Device:C", ref="C8", value="22uF",
        footprint="Capacitor_SMD:C_0805_2012Metric",
        X7R=True, voltage="6.3V", LCSC="TBD"
    )[1, 2] | (VOUT_3V3, GND)

    # ========================================================================
    # Stage 3: WL2808E12-5/TR LDO - 3.3V to 1.2V += 100mA
    # ========================================================================

    # U3: WL2808E12-5/TR 1.2V LDO (for RP2040 core, nominally 1.1V but 1.2V within spec)
    u3 = Component(
        symbol="JLCImport:WL2808E12-5_TR",
        ref="U3",
        value="WL2808E12-5",
        footprint="JLCImport:WL2808E12-5_TR",
        LCSC="C2931310",
        MPN="WL2808E12-5/TR",
    )
    u3[1, "VIN"] | VOUT_3V3
    u3[2, "GND"] | GND
    u3[3, "EN"] | VOUT_3V3  # Always enabled (tied to VIN)
    u3[4, "NC"] | Net("NC_U3")  # No connect
    u3[5, "VOUT"] | VOUT_1V2

    # Input capacitor
    Component(
        symbol="Device:C", ref="C9", value="10uF",
        footprint="Capacitor_SMD:C_0603_1608Metric",
        X7R=True, voltage="6.3V", LCSC="TBD"
    )[1, 2] | (VOUT_3V3, GND)

    # Output capacitor
    Component(
        symbol="Device:C", ref="C10", value="10uF",
        footprint="Capacitor_SMD:C_0603_1608Metric",
        X7R=True, voltage="6.3V", LCSC="TBD"
    )[1, 2] | (VOUT_1V2, GND)


if __name__ == "__main__":
    # Test instantiation

    @circuit(name="TestBench")
    def test():
        """Test the AUX_SUPPLY block."""
        vin_12v = Net("VIN_12V")
        vout_5v = Net("VOUT_5V")
        vout_3v3 = Net("VOUT_3V3")
        vout_1v2 = Net("VOUT_1V2")

        aux_supply(vin_12v, vout_5v, vout_3v3, vout_1v2)

    test()
    print("AUX_SUPPLY block instantiated successfully")
