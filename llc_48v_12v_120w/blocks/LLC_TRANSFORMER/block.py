"""
LLC Transformer Block
Isolation transformer for LLC resonant converter, 48V primary to 12V secondary (center-tapped).
EXTERNAL PART - not sourced from JLCPCB.
"""

from circuit_synth import circuit, Component, Input, Output


@circuit(name="LLC_TRANSFORMER")
def llc_transformer(PRI_P, PRI_N, SEC_CT, SEC_A, SEC_B):
    """
    LLC isolation transformer with center-tapped secondary.

    Ports:
        PRI_P: Primary positive (from half-bridge switch node)
        PRI_N: Primary negative (return to input ground)
        SEC_CT: Secondary center-tap (connects to +12V output rail)
        SEC_A: Secondary winding A (to SR FET A drain)
        SEC_B: Secondary winding B (to SR FET B drain)

    Specifications:
        Turns ratio: 4:1:1 (16:4:4 actual turns)
        Magnetizing inductance: 110 µH ±10%
        Leakage inductance: <10 µH
        Isolation: 1500V minimum
        Power rating: 150W continuous
        Core: ETD29, N87 or N97 ferrite, 0.2mm air gap

    This is a CUSTOM EXTERNAL part - not available in JLCPCB catalog.
    Must be sourced from Coilcraft, Würth, custom winder, or pre-consigned.
    """

    # LLC isolation transformer
    # DEVIATION: This is a custom/external part, not JLCPCB catalog
    T1 = Component(
        "T1",
        value="LLC_XFMR_4:1:1",
        symbol="Transformer_1P_2S",  # KiCad generic transformer symbol
        footprint="Transformer_THT:Transformer_ETD29",  # Through-hole ETD29 core
        manufacturer="CUSTOM",
        part_number="LLC-XFMR-ETD29-16:4:4",
        description="LLC isolation transformer, 4:1:1 turns ratio, 110uH magnetizing inductance",
        datasheet="See transformer_calculations.md",
        fields={
            "Turns_Ratio": "4:1:1",
            "Primary_Turns": "16T",
            "Secondary_Turns": "4T+4T",
            "Lm": "110uH",
            "Llk": "<10uH",
            "Core": "ETD29 N87",
            "Gap": "0.2mm",
            "Isolation": "1500V",
            "Power": "150W",
            "Frequency": "250kHz",
            "Wire_Pri": "Litz AWG18 equiv",
            "Wire_Sec": "Litz AWG14 equiv",
            "Source": "EXTERNAL - Coilcraft/Würth/Custom",
            "Assembly_Note": "Pre-consign or hand-assemble"
        }
    )

    # Primary winding connections
    T1[1] += PRI_P    # Primary dot (to half-bridge switch node)
    T1[2] += PRI_N    # Primary return (to input ground)

    # Secondary center-tap winding connections
    T1[3] += SEC_A    # Secondary winding A (to SR FET A)
    T1[4] += SEC_CT   # Secondary center-tap (to +12V output)
    T1[5] += SEC_B    # Secondary winding B (to SR FET B)


# Port interface for block integration
__all__ = ["llc_transformer"]
