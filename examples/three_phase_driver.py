"""Three-phase driver built from hierarchical blocks.

Exercises both of the circuit-synth features this repository is pinned to:

* hierarchical blocks with declared ports, so one half-bridge definition is
  instantiated three times with a different phase attached to each
* the port directions that make each block's interface show up as typed KiCad
  sheet pins

Run it with ``uv run python examples/three_phase_driver.py``.
"""

from pathlib import Path

from circuit_synth import Component, Input, Net, Output, circuit


@circuit(name="HalfBridge")
def half_bridge(HI: Input, LI: Input, PHASE: Output, VM: Input, VDRV: Input):
    """One half-bridge: high and low side drive in, motor phase out.

    An IR2101 high/low side driver with a bootstrap supply drives a pair of
    N-channel MOSFETs. Three of these make a three-phase inverter.
    """
    driver = Component(
        symbol="Driver_FET:IR2101",
        ref="U",
        value="IR2101",
        footprint="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
    )
    high_fet = Component(
        symbol="Transistor_FET:Q_NMOS_GDS",
        ref="Q",
        value="IRF3205",
        footprint="Package_TO_SOT_SMD:TO-263-3_TabPin2",
    )
    low_fet = Component(
        symbol="Transistor_FET:Q_NMOS_GDS",
        ref="Q",
        value="IRF3205",
        footprint="Package_TO_SOT_SMD:TO-263-3_TabPin2",
    )
    high_gate_resistor = Component(
        symbol="Device:R", ref="R", value="10R",
        footprint="Resistor_SMD:R_0805_2012Metric",
    )
    low_gate_resistor = Component(
        symbol="Device:R", ref="R", value="10R",
        footprint="Resistor_SMD:R_0805_2012Metric",
    )
    bootstrap_cap = Component(
        symbol="Device:C", ref="C", value="1uF/25V",
        footprint="Capacitor_SMD:C_0805_2012Metric",
    )
    bootstrap_diode = Component(
        symbol="Device:D_Schottky", ref="D", value="BAT54",
        footprint="Diode_SMD:D_SOD-123",
    )
    supply_cap = Component(
        symbol="Device:C", ref="C", value="100nF",
        footprint="Capacitor_SMD:C_0603_1608Metric",
    )

    gnd = Net("GND")
    boot = Net("BOOT")
    high_gate = Net("HGATE")
    low_gate = Net("LGATE")

    driver[1] += VDRV  # VCC
    driver[4] += gnd  # COM
    driver[2] += HI  # HIN
    driver[3] += LI  # LIN
    supply_cap[1] += VDRV
    supply_cap[2] += gnd

    # Bootstrap supply, referenced to the switching node.
    bootstrap_diode[1] += VDRV
    bootstrap_diode[2] += boot
    driver[8] += boot  # VB
    driver[6] += PHASE  # VS
    bootstrap_cap[1] += boot
    bootstrap_cap[2] += PHASE

    driver[7] += high_gate_resistor[1]  # HO
    high_gate_resistor[2] += high_gate
    driver[5] += low_gate_resistor[1]  # LO
    low_gate_resistor[2] += low_gate

    high_fet[1] += high_gate
    high_fet[2] += VM
    high_fet[3] += PHASE

    low_fet[1] += low_gate
    low_fet[2] += PHASE
    low_fet[3] += gnd


@circuit(name="ThreePhaseDriver")
def three_phase_driver():
    """Three half-bridges driving one BLDC motor."""
    v_motor = Net("V30")
    v_drive = Net("V3V3")

    gate_signals = [
        (Net("AH"), Net("AL"), Net("PHASE_A")),
        (Net("BH"), Net("BL"), Net("PHASE_B")),
        (Net("CH"), Net("CL"), Net("PHASE_C")),
    ]

    for high, low, phase in gate_signals:
        half_bridge(high, low, phase, v_motor, v_drive)

    motor = Component(
        symbol="Connector_Generic:Conn_01x03",
        ref="J",
        value="BLDC_MOTOR",
        footprint="Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
    )
    for index, (_, _, phase) in enumerate(gate_signals, start=1):
        motor[index] += phase


if __name__ == "__main__":
    output = Path(__file__).parent / "build" / "three_phase_driver"
    three_phase_driver().generate_kicad_project(
        str(output), force_regenerate=True, generate_pcb=False
    )
    print(f"Generated {output}.kicad_pro")
