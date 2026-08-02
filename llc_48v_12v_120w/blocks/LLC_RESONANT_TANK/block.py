"""LLC Resonant Tank circuit block.

The resonant tank is the heart of the LLC converter, providing:
- Resonant frequency control for regulation (fr ~ 250kHz)
- Zero-voltage switching (ZVS) for primary FETs
- Zero-current switching (ZCS) for secondary rectifiers
- Current limiting through resonant behavior

Components:
- Cr: Resonant capacitor (~100nF, 150V+)
- Lr: Resonant inductor (~22-30µH, typically integrated with transformer leakage)
- Rsense: Current sense shunt for control loop feedback

The quality factor Q = sqrt(Lr/Cr) / (Rac) determines regulation range.
Target Q ~ 0.3-0.5 for good regulation without excessive frequency variation.

Resonant frequency: fr = 1 / (2π√(Lr × Cr))
For Lr=25µH, Cr=100nF: fr = 1/(2π√(25e-6 × 100e-9)) = 318kHz
"""

from circuit_synth import circuit, Component, Net


@circuit(name="LLC_RESONANT_TANK")
def llc_resonant_tank(HB_OUT, PRI_DOT, PRI_NODOT, ISENSE_P, ISENSE_N):
    """LLC resonant tank with current sensing.

    Topology:
        HB_OUT --[Cr]-- n1 --[Rsense]-- n2 --[Lr]-- PRI_DOT
                         |               |
                    ISENSE_P        ISENSE_N
                                         |
                                    PRI_NODOT (GND via transformer)

    Current sense:
        Voltage across Rsense is proportional to resonant current.
        ISENSE_P and ISENSE_N connect to differential amplifier.
    """

    # Internal nets
    n1 = Net("n1")  # Between Cr and Rsense
    n2 = Net("n2")  # Between Rsense and Lr

    # ==========================================================================
    # Resonant Capacitor Cr
    # ==========================================================================
    # Blocks DC, forms LC resonant tank with Lr
    # Value: PLACEHOLDER - to be determined by simulator for fr ~ 250kHz
    # Voltage: Must withstand full half-bridge swing (48V min, use 150V for margin)
    cr = Component(
        symbol="Device:C",
        footprint="Capacitor_SMD:C_1206_3216Metric",  # Large enough for high voltage
        ref="C",
        value="100nF",
        voltage="150V",
        dielectric="X7R",  # C0G preferred but may not be available
        LCSC="TBD",  # Manual selection required - see parts.json
        MPN="TBD",
    )
    cr[1] += HB_OUT
    cr[2] += n1

    # ==========================================================================
    # Current Sense Shunt Rsense
    # ==========================================================================
    # Measures resonant current for current-mode control
    # Value: Trade-off between signal level and power loss
    # 10mΩ += 8A RMS => 80mV signal, 0.64W dissipation
    rsense = Component(
        symbol="Device:R",
        footprint="Resistor_SMD:R_2512_6332Metric",  # High power rating package
        ref="R",
        value="10mΩ",
        power="1W",
        tolerance="1%",
        LCSC="TBD",  # Manual selection required - see parts.json
        MPN="TBD",
    )
    rsense[1] += n1
    rsense[2] += n2

    # Current sense outputs (differential)
    # These are taps on existing nets for the control loop
    n1 += ISENSE_P
    n2 += ISENSE_N

    # ==========================================================================
    # Resonant Inductor Lr
    # ==========================================================================
    # NOTE: In most LLC designs, Lr is the transformer's leakage inductance,
    # not a discrete component. This reduces BOM cost and board space.
    # This component may NOT be populated if transformer leakage is used.
    lr = Component(
        symbol="Device:L",
        footprint="Inductor_SMD:L_1210_3225Metric",  # Placeholder - high current inductor
        ref="L",
        value="25µH",
        current_rating="8A",
        LCSC="TBD",  # May not be needed if using transformer leakage
        MPN="TBD",
    )
    lr[1] += n2
    lr[2] += PRI_DOT

    # ==========================================================================
    # Transformer Primary Return
    # ==========================================================================
    # PRI_NODOT connects to GND (ground return path through transformer)
    # The transformer itself is in LLC_TRANSFORMER block
    # Using power symbol so it connects by name
    gnd_sym = Component(
        symbol="power:GND",
        ref="#PWR",
        value="GND",
    )
    gnd_sym[1] += PRI_NODOT

    # Return design parameters (placeholders for simulator)
    return {
        "resonant_frequency": "PLACEHOLDER",  # fr = 1/(2π√(Lr×Cr))
        "quality_factor": "PLACEHOLDER",  # Q ~ 0.3-0.5 for good regulation
        "peak_voltage_across_Cr": "PLACEHOLDER",  # Depends on load and frequency
        "rms_current": "PLACEHOLDER",  # ~8A at full load
    }
