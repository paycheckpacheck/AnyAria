"""INPUT_FILTER block for LLC 48V→12V converter.

Provides:
- TVS overvoltage protection (58V breakdown)
- Bulk input capacitance (200µF electrolytic)
- High-frequency ceramic bypass (10µF + 1µF)
- Input voltage sensing for RP2040 ADC
- Screw terminal input connector

Ports:
- VIN_FILT: Filtered 48V output to LLC resonant tank
- VSENSE: Voltage sense output to RP2040 ADC (3.14V += 48V input)

Power symbols (by name):
- +48V: Unfiltered input from screw terminal (internal)
- GND: Ground reference
"""

from circuit_synth import Component, Net, circuit


@circuit(name="INPUT_FILTER")
def input_filter(VIN_FILT, VSENSE):
    """Input filter, protection, and sensing for 48V LLC converter.

    Args:
        VIN_FILT: Filtered 48V output to LLC resonant tank
        VSENSE: Voltage sense to RP2040 ADC (3.14V += 48V input)
    """

    # Power nets (by name - these are global power symbols)
    vin_raw = Net("+48V")  # Raw input from terminal
    gnd = Net("GND")       # Ground

    # Input screw terminal (creates +48V power net)
    J1 = Component(
        symbol="JLCImport:WJ127-5_0-2P",
        footprint="JLCImport:WJ127-5_0-2P",
        ref="J",
        value="TERM_2P_5mm",
        LCSC="C3703",
        MPN="WJ127-5.0-02P-14-00A"
    )
    J1[1] += vin_raw  # Pin 1 → +48V
    J1[2] += gnd      # Pin 2 → GND

    # TVS overvoltage protection (58V breakdown, 93.6V clamp)
    D1 = Component(
        symbol="JLCImport:SMBJ58A_C19195335",
        footprint="JLCImport:SMBJ58A_C19195335",
        ref="D",
        value="SMBJ58A",
        LCSC="C19195335",
        MPN="SMBJ58A"
    )
    D1["A"] += vin_raw  # Anode to +48V
    D1["K"] += gnd      # Cathode to GND (unidirectional)

    # Bulk electrolytic capacitors (2× 100µF = 200µF total)
    C_BULK = Component(
        symbol="JLCImport:CS1J101M-CRG10",
        footprint="JLCImport:CS1J101M-CRG10",
        ref="C",
        value="100µF",
        LCSC="C116430",
        MPN="CS1J101M-CRG10",
        instances=2  # C1, C2
    )
    C_BULK["1"] += vin_raw  # Pin 1 is positive
    C_BULK["2"] += gnd      # Pin 2 is negative

    # High-frequency ceramic bypass (10µF, 1206)
    C_HF_10U = Component(
        symbol="JLCImport:CC1206KRX7R0BB473",
        footprint="JLCImport:CC1206KRX7R0BB473",
        ref="C",
        value="10µF",
        LCSC="C107206",
        MPN="CC1206KRX7R0BB473",
        instances=2  # C3, C4
    )
    C_HF_10U["1"] += VIN_FILT  # Filtered output
    C_HF_10U["2"] += gnd

    # Additional HF bypass (1µF, 0805)
    C_HF_1U = Component(
        symbol="JLCImport:CC0805KRX7R0BB222",
        footprint="JLCImport:CC0805KRX7R0BB222",
        ref="C",
        value="1µF",
        LCSC="C107136",
        MPN="CC0805KRX7R0BB222",
        instances=2  # C5, C6
    )
    C_HF_1U["1"] += VIN_FILT
    C_HF_1U["2"] += gnd

    # Connect bulk caps to filtered output
    # (In reality, all caps in parallel on same net, but logically bulk → ceramic → output)
    vin_raw += VIN_FILT  # Bulk storage connected to filtered output

    # Voltage sensing divider (48V → 3.14V for RP2040 ADC)
    # R1: 47kΩ high side
    R1 = Component(
        symbol="JLCImport:0603WAF4702T5E",
        footprint="JLCImport:0603WAF4702T5E",
        ref="R",
        value="47kΩ",
        LCSC="C25819",
        MPN="0603WAF4702T5E"
    )
    R1["1"] += VIN_FILT  # Sense from filtered input
    vsense_mid = Net("VSENSE_MID")
    R1["2"] += vsense_mid

    # R2: 3.3kΩ low side
    R2 = Component(
        symbol="JLCImport:0603WAF3301T5E",
        footprint="JLCImport:0603WAF3301T5E",
        ref="R",
        value="3.3kΩ",
        LCSC="C22978",
        MPN="0603WAF3301T5E"
    )
    R2["1"] += vsense_mid
    R2["2"] += gnd

    # ADC input filter capacitor
    C_ADC = Component(
        symbol="JLCImport:CC0603KRX7R9BB104",
        footprint="JLCImport:CC0603KRX7R9BB104",
        ref="C",
        value="100nF",
        LCSC="C14663",
        MPN="CC0603KRX7R9BB104"
    )
    C_ADC["1"] += vsense_mid
    C_ADC["2"] += gnd

    # Output port: voltage sense to RP2040 ADC
    vsense_mid += VSENSE


if __name__ == "__main__":
    # Test: generate the circuit
    from pathlib import Path

    output_dir = Path(__file__).parent / "build"
    output_dir.mkdir(exist_ok=True)

    # Create top-level circuit that calls input_filter
    @circuit(name="INPUT_FILTER_TEST")
    def test_circuit():
        vin_filt = Net("VIN_FILT")
        vsense = Net("VSENSE")
        input_filter(vin_filt, vsense)

    # Generate KiCad project
    output_path = output_dir / "input_filter_test"
    test_circuit().generate_kicad_project(
        str(output_path),
        force_regenerate=True,
        generate_pcb=False
    )
    print(f"Generated {output_path}.kicad_pro")
