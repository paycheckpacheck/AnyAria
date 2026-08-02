"""
OUTPUT_FILTER block for LLC 48V→12V converter.

Passive output filtering stage:
- Bulk electrolytic capacitors for energy storage
- High-frequency ceramic capacitors for ripple filtering
- Output connector for 12V += 10A load connection

All values are PLACEHOLDERS pending simulation.
"""

from circuit_synth import Component, Net, circuit


@circuit(name="OUTPUT_FILTER")
def output_filter(RECT_P, VOUT_SENSE, ISENSE_P):
    """
    LLC converter output filter stage.

    Topology:
    - 2× 1000µF electrolytic capacitors in parallel (bulk filtering)
    - 6× 47µF ceramic capacitors in parallel (high-frequency filtering)
    - Screw terminal for output connection

    Ports:
        RECT_P: Rectified positive rail from SECONDARY_RECTIFIER block
        VOUT_SENSE: High-impedance voltage sense tap (to feedback/ADC)
        ISENSE_P: Positive current sense point (to shunt in OUTPUT_SENSE_PROTECT)

    Rails:
        GND: Ground reference (power symbol, connects by name)
        +12V: Filtered output rail (power symbol, generated here)

    Design targets:
        - Output ripple: < 100mV at 10A load
        - Total capacitance: ~2000µF bulk + ~300µF ceramic
        - ESR: < 50mΩ total
        - Hold-up: > 100µs (not critical for this design)
    """

    # =========================================================================
    # BULK ELECTROLYTIC CAPACITORS
    # =========================================================================
    # Two 1000µF in parallel for lower ESR and better ripple current handling
    # TI SLUA559A section 4.3: output cap sized for ripple voltage and holdup

    Component(
        symbol="Device:C_Polarized",
        footprint="Capacitor_THT:CP_Radial_D10.0mm_P5.00mm",
        ref="C_BULK",
        value="1000uF",  # PLACEHOLDER - simulator will verify
        LCSC="C484817",
        MPN="1000uF_25V_Rubycon",
        nets={"+": "RECT_P", "-": "GND"},
        fields={
            "Voltage": "25V",
            "Tolerance": "20%",
            "ESR": "TBD",  # PLACEHOLDER
            "RippleCurrent": "TBD",  # PLACEHOLDER
        },
    )

    Component(
        symbol="Device:C_Polarized",
        footprint="Capacitor_THT:CP_Radial_D10.0mm_P5.00mm",
        ref="C_BULK",
        value="1000uF",  # PLACEHOLDER - simulator will verify
        LCSC="C484817",
        MPN="1000uF_25V_Rubycon",
        nets={"+": "RECT_P", "-": "GND"},
        fields={
            "Voltage": "25V",
            "Tolerance": "20%",
            "ESR": "TBD",  # PLACEHOLDER
            "RippleCurrent": "TBD",  # PLACEHOLDER
        },
    )

    # =========================================================================
    # HIGH-FREQUENCY CERAMIC CAPACITORS
    # =========================================================================
    # 6× 47µF X5R/X7R ceramics in parallel for low-ESL HF filtering
    # Placed close to rectifier output, minimize loop inductance

    for i in range(6):
        Component(
            symbol="Device:C",
            footprint="Capacitor_SMD:C_1206_3216Metric",
            ref="C_HF",
            value="47uF",  # PLACEHOLDER - simulator will verify
            LCSC="C19666",
            MPN="47uF_25V_X5R_Samsung",
            nets={"1": "RECT_P", "2": "GND"},
            fields={
                "Voltage": "25V",
                "Dielectric": "X5R",
                "Tolerance": "20%",
            },
        )

    # =========================================================================
    # OUTPUT POWER RAIL
    # =========================================================================
    # Power symbol for +12V output rail (connects by name across design)
    # This is where the filtered 12V rail is "produced"

    Component(
        symbol="power:+12V",
        footprint="",
        ref="#PWR",
        value="+12V",
        nets={"1": "RECT_P"},  # RECT_P becomes +12V after filtering
    )

    Component(
        symbol="power:GND",
        footprint="",
        ref="#PWR",
        value="GND",
        nets={"1": "GND"},
    )

    # =========================================================================
    # VOLTAGE SENSE TAP
    # =========================================================================
    # High-impedance connection to OUTPUT_SENSE_PROTECT for feedback/ADC
    # 1kΩ series resistor to isolate capacitor bank from sense circuitry

    Component(
        symbol="Device:R",
        footprint="Resistor_SMD:R_0603_1608Metric",
        ref="R_VSENSE",
        value="1k",  # PLACEHOLDER - may adjust based on feedback circuit
        nets={"1": "RECT_P", "2": "VOUT_SENSE"},
        fields={
            "Power": "0.1W",
            "Tolerance": "1%",
        },
    )

    # =========================================================================
    # CURRENT SENSE CONNECTION
    # =========================================================================
    # ISENSE_P port connects to shunt resistor in OUTPUT_SENSE_PROTECT block
    # Current path: +12V → Load → Shunt → GND
    # Shunt is in OUTPUT_SENSE_PROTECT, this is just the connection point

    Component(
        symbol="power:+12V",
        footprint="",
        ref="#PWR",
        value="+12V",
        nets={"1": "ISENSE_P"},  # Connect to current sense path
    )

    # =========================================================================
    # OUTPUT CONNECTOR
    # =========================================================================
    # 2-pin screw terminal, 5.08mm pitch, 10A rated
    # Pin 1: +12V output
    # Pin 2: GND

    Component(
        symbol="Connector:Screw_Terminal_01x02",
        footprint="TerminalBlock:TerminalBlock_bornier-2_P5.08mm",
        ref="J_OUT",
        value="12V_OUT",
        LCSC="C8465",
        MPN="KF128-5.08-2P",
        nets={
            "1": "ISENSE_P",  # Positive output (goes through current sense)
            "2": "GND",  # Ground
        },
        fields={
            "Current": "10A",
            "WireGauge": "16-24AWG",
        },
    )


if __name__ == "__main__":
    # Test import
    print("OUTPUT_FILTER block loaded successfully")
    print("Ports: RECT_P (input), VOUT_SENSE (output), ISENSE_P (output)")
    print("Rails consumed: None (receives RECT_P from SECONDARY_RECTIFIER)")
    print("Rails produced: +12V (power symbol)")
