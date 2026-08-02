"""
PRIMARY_HALF_BRIDGE block for LLC 48V→12V converter.

Two N-channel power MOSFETs in half-bridge configuration, driven by IR2110
(or equivalent) high-side/low-side gate driver with bootstrap supply.

Ports:
- HI_IN, LO_IN: Gate drive inputs from dead-time logic (with non-overlap)
- SW_OUT: Switching node output to LLC resonant tank
- VCC_12V: +12V supply for gate driver
- VDD_5V: +5V logic supply for gate driver inputs

Power rails (not ports):
- V_BUS_48V: High voltage DC input (48V nominal)
- GND: Ground reference
"""

from circuit_synth import (
    Component,
    Net,
    circuit,
    Input,
    Output,
)


@circuit(name="PrimaryHalfBridge")
def primary_half_bridge(HI_IN, LO_IN, SW_OUT, VCC_12V, VDD_5V):
    """
    IR2110-based half-bridge gate driver with two N-channel power MOSFETs.

    Args:
        HI_IN: High-side gate drive input (from dead-time logic)
        LO_IN: Low-side gate drive input (from dead-time logic)
        SW_OUT: Switching node output (connects to LLC resonant tank)
        VCC_12V: +12V supply for gate driver power
        VDD_5V: +5V logic supply for gate driver control

    Notes:
        - V_BUS_48V and GND connect by name (power symbols)
        - Bootstrap circuit provides floating supply for high-side driver
        - Gate resistors limit di/dt and reduce ringing
        - Source-to-gate resistors prevent floating gates
    """

    # =========================================================================
    # Gate Driver IC: IR2110 or IRS2110 equivalent
    # =========================================================================
    # Note: Using generic symbol - actual part from JLCPCB catalog TBD

    # Internal nets for gate driver
    net_vs = Net("VS")  # Floating supply return (connects to switching node)
    net_vb = Net("VB")  # Bootstrap supply voltage
    net_ho = Net("HO")  # High-side driver output
    net_lo = Net("LO")  # Low-side driver output

    # IR2110 gate driver IC
    # Placeholder - actual sourced part will have specific symbol/footprint
    u_driver = Component(
        symbol="Driver_FET:IR2110",  # Placeholder symbol
        footprint="Package_SO:SOIC-14_3.9x8.7mm_P1.27mm",  # Typical IR2110 package
        ref="U",
        value="IR2110",
        manufacturer="Infineon",
        LCSC="C_TBD",  # To be determined from JLCPCB catalog
        MPN="IRS2110PBF",
    )

    # Pin connections per IR2110 datasheet
    u_driver[1] += net_lo           # LO: Low-side driver output
    u_driver[2] += "GND"            # COM: Power ground
    u_driver[3] += VCC_12V          # VCC: +12V supply
    u_driver[5] += net_vs           # VS: Floating supply return
    u_driver[6] += net_vb           # VB: Bootstrap supply
    u_driver[7] += net_ho           # HO: High-side driver output
    u_driver[9] += VDD_5V           # VDD: +5V logic supply
    u_driver[10] += HI_IN           # HIN: High-side input
    u_driver[12] += LO_IN           # LIN: Low-side input
    u_driver[13] += "GND"           # VSS: Logic ground
    # Pins 4, 8, 11, 14: NC (no connect) or specific functions per datasheet

    # =========================================================================
    # Bootstrap Circuit
    # =========================================================================

    # Bootstrap capacitor: Charges when low-side FET is on, supplies high-side
    # driver when high-side FET is on (VS rises to ~48V)
    c_boot = Component(
        symbol="Device:C",
        footprint="Capacitor_SMD:C_0805_2012Metric",
        ref="C",
        value="0.47uF",
        manufacturer="Samsung",
        LCSC="C15008",
        MPN="CL21B474KBFNNNE",
        voltage="25V",
        dielectric="X7R",
    )
    c_boot[1] += net_vb
    c_boot[2] += net_vs

    # Bootstrap diode: Allows Cboot to charge from VCC when VS is low
    # Use fast-recovery or Schottky for high-frequency operation
    d_boot = Component(
        symbol="Device:D_Schottky",
        footprint="Diode_SMD:D_SOD-123",  # Small signal Schottky
        ref="D",
        value="1N5819",  # Placeholder - use JLCPCB sourced part
        manufacturer="TBD",
        LCSC="C_TBD",
        MPN="TBD",
    )
    d_boot.pin["K"] += net_vb      # Cathode to VB
    d_boot.pin["A"] += VCC_12V     # Anode to VCC (charges Cboot when VS low)

    # VCC bypass capacitors (close to IC pins)
    c_vcc_ceramic = Component(
        symbol="Device:C",
        footprint="Capacitor_SMD:C_0603_1608Metric",
        ref="C",
        value="0.1uF",
        voltage="25V",
        dielectric="X7R",
    )
    c_vcc_ceramic[1] += VCC_12V
    c_vcc_ceramic[2] += "GND"

    c_vcc_bulk = Component(
        symbol="Device:C",
        footprint="Capacitor_SMD:C_1206_3216Metric",
        ref="C",
        value="10uF",
        voltage="25V",
        dielectric="X5R",
    )
    c_vcc_bulk[1] += VCC_12V
    c_vcc_bulk[2] += "GND"

    # VDD bypass capacitor
    c_vdd = Component(
        symbol="Device:C",
        footprint="Capacitor_SMD:C_0603_1608Metric",
        ref="C",
        value="0.1uF",
        voltage="10V",
        dielectric="X7R",
    )
    c_vdd[1] += VDD_5V
    c_vdd[2] += "GND"

    # =========================================================================
    # Power MOSFETs: Q1 (high-side), Q2 (low-side)
    # =========================================================================

    # Internal gate nets (after gate resistors)
    net_q1_gate = Net("Q1_GATE")
    net_q2_gate = Net("Q2_GATE")

    # Q1: High-side MOSFET
    q1 = Component(
        symbol="Device:Q_NMOS_GDS",
        footprint="Package_TO_SOT_THT:TO-220-3_Vertical",
        ref="Q",
        value="IPP80N05S4-02",
        manufacturer="Infineon",
        LCSC="C91735",
        MPN="IPP80N05S4-02",
        Vds="150V",
        Id="80A",
        Rds_on="5.3mΩ",
    )
    q1.pin["G"] += net_q1_gate      # Gate (after Rgate)
    q1.pin["D"] += "V_BUS_48V"      # Drain to high voltage bus
    q1.pin["S"] += net_vs           # Source to switching node (also VS for bootstrap)

    # Q2: Low-side MOSFET
    q2 = Component(
        symbol="Device:Q_NMOS_GDS",
        footprint="Package_TO_SOT_THT:TO-220-3_Vertical",
        ref="Q",
        value="IPP80N05S4-02",
        manufacturer="Infineon",
        LCSC="C91735",
        MPN="IPP80N05S4-02",
        Vds="150V",
        Id="80A",
        Rds_on="5.3mΩ",
    )
    q2.pin["G"] += net_q2_gate      # Gate (after Rgate)
    q2.pin["D"] += net_vs           # Drain to switching node
    q2.pin["S"] += "GND"            # Source to ground

    # Connect switching node to output port
    net_vs += SW_OUT

    # =========================================================================
    # Gate Drive Resistors
    # =========================================================================

    # R_gate_high: Limits di/dt, reduces ringing on Q1 gate
    r_gate_high = Component(
        symbol="Device:R",
        footprint="Resistor_SMD:R_0603_1608Metric",
        ref="R",
        value="5.1",
        manufacturer="YAGEO",
        LCSC="C23116",
        MPN="RC0603FR-075R1L",
        tolerance="1%",
        power="0.1W",
    )
    r_gate_high[1] += net_ho
    r_gate_high[2] += net_q1_gate

    # R_gate_low: Limits di/dt, reduces ringing on Q2 gate
    r_gate_low = Component(
        symbol="Device:R",
        footprint="Resistor_SMD:R_0603_1608Metric",
        ref="R",
        value="5.1",
        manufacturer="YAGEO",
        LCSC="C23116",
        MPN="RC0603FR-075R1L",
        tolerance="1%",
        power="0.1W",
    )
    r_gate_low[1] += net_lo
    r_gate_low[2] += net_q2_gate

    # =========================================================================
    # Source-to-Gate Pull-down Resistors (prevent floating gates)
    # =========================================================================

    # R_sg_high: Q1 gate to source pull-down
    r_sg_high = Component(
        symbol="Device:R",
        footprint="Resistor_SMD:R_0603_1608Metric",
        ref="R",
        value="10k",
        manufacturer="YAGEO",
        LCSC="C98220",
        MPN="RC0603FR-0710KL",
        tolerance="1%",
        power="0.1W",
    )
    r_sg_high[1] += net_q1_gate
    r_sg_high[2] += net_vs      # Q1 source (floating with switching node)

    # R_sg_low: Q2 gate to source pull-down
    r_sg_low = Component(
        symbol="Device:R",
        footprint="Resistor_SMD:R_0603_1608Metric",
        ref="R",
        value="10k",
        manufacturer="YAGEO",
        LCSC="C98220",
        MPN="RC0603FR-0710KL",
        tolerance="1%",
        power="0.1W",
    )
    r_sg_low[1] += net_q2_gate
    r_sg_low[2] += "GND"        # Q2 source (ground)

    # =========================================================================
    # Optional: Snubber Networks (evaluate during testing)
    # =========================================================================
    # RC snubber across each MOSFET drain-source for ringing suppression
    # Values: 10Ω + 1nF provides critical damping at ~10MHz
    # Can be marked DNF (do not fit) and populated if needed

    # Q1 snubber
    r_snub_q1 = Component(
        symbol="Device:R",
        footprint="Resistor_SMD:R_0603_1608Metric",
        ref="R",
        value="10",
        manufacturer="YAGEO",
        LCSC="C98682",
        MPN="RC0603JR-0710RL",
        tolerance="5%",
        power="0.1W",
        DNF=True,  # Do not fit - populate if ringing observed
    )

    c_snub_q1 = Component(
        symbol="Device:C",
        footprint="Capacitor_SMD:C_0603_1608Metric",
        ref="C",
        value="1nF",
        manufacturer="YAGEO",
        LCSC="C105620",
        MPN="CC0603JRNPO9BN102",
        voltage="100V",
        dielectric="C0G",
        DNF=True,
    )

    # Snubber network in series: R then C
    net_snub_q1 = Net("SNUB_Q1")
    r_snub_q1[1] += "V_BUS_48V"     # From Q1 drain
    r_snub_q1[2] += net_snub_q1
    c_snub_q1[1] += net_snub_q1
    c_snub_q1[2] += net_vs          # To Q1 source (switching node)

    # Q2 snubber
    r_snub_q2 = Component(
        symbol="Device:R",
        footprint="Resistor_SMD:R_0603_1608Metric",
        ref="R",
        value="10",
        manufacturer="YAGEO",
        LCSC="C98682",
        MPN="RC0603JR-0710RL",
        tolerance="5%",
        power="0.1W",
        DNF=True,
    )

    c_snub_q2 = Component(
        symbol="Device:C",
        footprint="Capacitor_SMD:C_0603_1608Metric",
        ref="C",
        value="1nF",
        manufacturer="YAGEO",
        LCSC="C105620",
        MPN="CC0603JRNPO9BN102",
        voltage="100V",
        dielectric="C0G",
        DNF=True,
    )

    net_snub_q2 = Net("SNUB_Q2")
    r_snub_q2[1] += net_vs          # From Q2 drain (switching node)
    r_snub_q2[2] += net_snub_q2
    c_snub_q2[1] += net_snub_q2
    c_snub_q2[2] += "GND"           # To Q2 source (ground)


# ============================================================================
# Block Interface Definition
# ============================================================================

if __name__ == "__main__":
    """
    Test instantiation of PRIMARY_HALF_BRIDGE block.
    """
    from circuit_synth import Net

    # Create test nets
    hi_in = Net("HI_IN_TEST")
    lo_in = Net("LO_IN_TEST")
    sw_out = Net("SW_OUT_TEST")
    vcc_12v = Net("VCC_12V_TEST")
    vdd_5v = Net("VDD_5V_TEST")

    # Instantiate block
    primary_half_bridge(hi_in, lo_in, sw_out, vcc_12v, vdd_5v)

    print("PRIMARY_HALF_BRIDGE block instantiated successfully.")
