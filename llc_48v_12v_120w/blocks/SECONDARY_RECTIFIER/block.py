"""
SECONDARY_RECTIFIER block for LLC 48V→12V converter.

Center-tapped synchronous rectification with two N-channel MOSFETs.
Transformer secondary windings drive SR FETs, output combines at center-tap.

Reference: SLUA748A section 4.3, UCC24610 typical application
"""

from circuit_synth import circuit, Component, Net


@circuit(name="SecondaryRectifier")
def secondary_rectifier(SEC_A, SEC_B, CT, SR1_GATE, SR2_GATE):
    """
    Center-tapped synchronous rectifier for LLC converter secondary.

    Two N-channel MOSFETs rectify the transformer secondary windings.
    Body diodes conduct during dead time, MOSFETs conduct during active phase.

    Ports:
        SEC_A: Transformer secondary winding A (top winding)
        SEC_B: Transformer secondary winding B (bottom winding)
        CT: Center-tap output (to output filter)
        SR1_GATE: Gate drive signal for Q_SR1 (from SR controller)
        SR2_GATE: Gate drive signal for Q_SR2 (from SR controller)

    Power symbols (not ports):
        GND: Common ground reference
        +12V: Gate drive supply (derived from output for VCC)
    """

    # Power symbols (connect by name, not ports)
    GND = Net("GND")
    VCC_SR = Net("+12V")  # Gate drive supply from output

    # Internal nets
    SR1_DRAIN = Net("SR1_DRAIN")
    SR2_DRAIN = Net("SR2_DRAIN")
    SR_SOURCE_COMMON = Net("SR_SOURCE_COMMON")

    # Optional current sense nets (for telemetry)
    SR1_SENSE = Net("SR1_ISENSE")
    SR2_SENSE = Net("SR2_ISENSE")

    # =========================================================================
    # Synchronous Rectifier FET 1 (Top winding SEC_A)
    # =========================================================================
    # Conducts when SEC_A is positive relative to CT
    # Body diode provides freewheeling during dead time

    Q_SR1 = Component(
        ref="Q_SR1",
        symbol="MOSFET_N_channel",  # Placeholder - will be imported from sourced part
        footprint="TDSON-8",         # Placeholder - will be imported
        value="BSC010N04LS",
        LCSC="C70783",              # Infineon BSC010N04LS, 40V, 1mΩ
        MPN="BSC010N04LS",
    )
    Q_SR1.connect(
        drain=SR1_DRAIN,
        gate=SR1_GATE,
        source=SR1_SENSE,  # Through current sense resistor to ground
    )

    # =========================================================================
    # Synchronous Rectifier FET 2 (Bottom winding SEC_B)
    # =========================================================================
    # Conducts when SEC_B is positive relative to CT
    # Matched to Q_SR1 for balanced rectification

    Q_SR2 = Component(
        ref="Q_SR2",
        symbol="MOSFET_N_channel",
        footprint="TDSON-8",
        value="BSC010N04LS",
        LCSC="C70783",
        MPN="BSC010N04LS",
    )
    Q_SR2.connect(
        drain=SR2_DRAIN,
        gate=SR2_GATE,
        source=SR2_SENSE,
    )

    # =========================================================================
    # Transformer Secondary Connections
    # =========================================================================
    # SEC_A winding connects to SR1 drain
    # SEC_B winding connects to SR2 drain
    # Center-tap combines the rectified outputs

    SEC_A.connect_to(SR1_DRAIN)
    SEC_B.connect_to(SR2_DRAIN)

    # Center-tap is the combined output
    # Both SR FETs pull current through CT when conducting
    CT.connect_to(SR_SOURCE_COMMON)

    # =========================================================================
    # Current Sense Resistors (Optional - for RP2040 telemetry)
    # =========================================================================
    # 10mΩ resistors in source path of each SR FET
    # Allows measurement of individual winding current
    # Trade-off: 0.5W dissipation per resistor at 10A

    R_SENSE1 = Component(
        ref="R_SENSE1",
        symbol="Resistor",
        footprint="R_2512",  # 0.5W power rating
        value="10m",          # PLACEHOLDER - simulator will verify
        tolerance="1%",
        power="0.5W",
        LCSC="TBD",          # To be sourced - low value current sense
        MPN="TBD",
    )
    R_SENSE1.connect(
        p1=SR1_SENSE,
        p2=SR_SOURCE_COMMON,
    )

    R_SENSE2 = Component(
        ref="R_SENSE2",
        symbol="Resistor",
        footprint="R_2512",
        value="10m",          # PLACEHOLDER - matched to R_SENSE1
        tolerance="1%",
        power="0.5W",
        LCSC="TBD",
        MPN="TBD",
    )
    R_SENSE2.connect(
        p1=SR2_SENSE,
        p2=SR_SOURCE_COMMON,
    )

    # Common source point ties to ground
    SR_SOURCE_COMMON.connect_to(GND)

    # =========================================================================
    # Gate Pull-Down Resistors
    # =========================================================================
    # Ensure SR FETs stay off when gate drive is floating
    # Important for startup and fault conditions

    R_GD1 = Component(
        ref="R_GD1",
        symbol="Resistor",
        footprint="R_0603",
        value="10k",          # PLACEHOLDER - standard gate pull-down
        tolerance="5%",
        power="0.1W",
        LCSC="C25804",       # Basic 10k 0603
        MPN="0603WAF1002T5E",
    )
    R_GD1.connect(
        p1=SR1_GATE,
        p2=GND,
    )

    R_GD2 = Component(
        ref="R_GD2",
        symbol="Resistor",
        footprint="R_0603",
        value="10k",
        tolerance="5%",
        power="0.1W",
        LCSC="C25804",
        MPN="0603WAF1002T5E",
    )
    R_GD2.connect(
        p1=SR2_GATE,
        p2=GND,
    )

    # =========================================================================
    # Gate Drive Decoupling
    # =========================================================================
    # If gate drive derives from +12V rail (for discrete driver implementation)
    # Decoupling cap provides transient current for fast gate charging

    C_VCC = Component(
        ref="C_VCC",
        symbol="Capacitor",
        footprint="C_0805",
        value="1u",           # PLACEHOLDER
        voltage="25V",
        dielectric="X7R",
        LCSC="C28323",       # Basic 1uF 25V X7R 0805
        MPN="CL21B105KAFNNNE",
    )
    C_VCC.connect(
        p1=VCC_SR,
        p2=GND,
    )

    # =========================================================================
    # Bootstrap Capacitors (if using bootstrap gate drive topology)
    # =========================================================================
    # NOTE: For low-side N-channel FETs with sources tied to ground,
    # bootstrap may not be needed. Include footprints for flexibility.
    # Mark as DNF (Do Not Fit) if gate drive implementation doesn't require.

    C_BST1 = Component(
        ref="C_BST1",
        symbol="Capacitor",
        footprint="C_0805",
        value="1u",           # PLACEHOLDER
        voltage="25V",
        dielectric="X7R",
        LCSC="C28323",
        MPN="CL21B105KAFNNNE",
        DNF=True,            # Default DNF - fit if bootstrap topology used
    )
    # Bootstrap cap would connect between gate drive supply and SR1 source
    # Connection deferred to gate driver block implementation

    C_BST2 = Component(
        ref="C_BST2",
        symbol="Capacitor",
        footprint="C_0805",
        value="1u",
        voltage="25V",
        dielectric="X7R",
        LCSC="C28323",
        MPN="CL21B105KAFNNNE",
        DNF=True,
    )

    # =========================================================================
    # Notes for Integration
    # =========================================================================
    #
    # Gate drive signals (SR1_GATE, SR2_GATE) must come from either:
    # 1. Dedicated SR controller IC (UCC24610, etc.) - NOT in JLCPCB catalog
    # 2. Discrete comparator + gate driver sensing transformer voltage
    # 3. Transformer-coupled gate drive (pulse transformer from primary)
    #
    # Dead time critical: SR1 and SR2 must NEVER conduct simultaneously
    # or transformer shoot-through occurs.
    #
    # Body diodes conduct during dead time - this is normal and required
    # for ZVS operation. SR turn-on should minimize body diode conduction
    # to reduce losses.
    #
    # Current sense resistors optional - can be DNF if telemetry not needed.
    # Omitting them saves 1W dissipation and improves efficiency ~0.8%.
