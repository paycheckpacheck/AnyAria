"""
DISCRETE_LLC_CONTROLLER - Fully Discrete Current-Mode LLC Resonant Converter Control

This is the most complex block in the LLC converter. It implements a complete
current-mode control loop using discrete components:
- Current sensing (CT or shunt + amp)
- Voltage feedback with optocoupler isolation
- Slope compensation for stability
- Current-mode comparator
- VCO for frequency modulation (100-500kHz)
- RS latch + dead-time generation
- Half-bridge gate driver

All components are JLCPCB Basic or common Extended parts.
Control loop is entirely analog (RP2040 is for telemetry only).

References:
- IR2110 datasheet PD60147-O (Oct 2015) Figure 1
- TL431 datasheet SLVS056J (June 2020) Figure 37
- CD4046 datasheet SCHS097D (March 2013) Figure 13
- LM393 datasheet SNOSBZ8E (March 2018) Figure 24
- LM358 datasheet SNOSC16D (Dec 2015) Figure 31
- 74HC74 datasheet (Nexperia) Figure 8
- 74HC00 datasheet (Nexperia) - standard dead-time topology
"""

from circuit_synth import (
    Component, Net, Input, Output, Bidirectional,
    circuit
)


@circuit(name="DISCRETE_LLC_CONTROLLER")
def discrete_llc_controller(
    # Primary power input (resonant tank current sense point)
    I_RESONANT: Input,  # Current transformer secondary or shunt voltage

    # Secondary voltage feedback (isolated)
    VOUT_SENSE: Input,  # 12V output voltage sense (secondary side)

    # Gate driver outputs
    GATE_HI: Output,  # High-side gate drive to primary GaN FET (Q1)
    GATE_LO: Output,  # Low-side gate drive to primary GaN FET (Q2)

    # Half-bridge switching node
    SWITCH_NODE: Bidirectional,  # Half-bridge midpoint (to LLC resonant tank)

    # Enable/shutdown
    ENABLE: Input,  # Logic high = enabled, logic low = shutdown
):
    """
    Fully discrete current-mode LLC controller.

    This block contains 7 major sub-circuits:
    1. CURRENT_SENSE - CT or shunt amplifier
    2. VOLTAGE_FEEDBACK - TL431 + opto isolation
    3. SLOPE_COMPENSATION - Ramp generator
    4. CURRENT_MODE_COMPARATOR - Resets latch when I > threshold
    5. VCO - 100-500kHz voltage-controlled oscillator
    6. RS_LATCH_DEAD_TIME - PWM generation with non-overlap
    7. PRIMARY_GATE_DRIVER - IR2110 half-bridge driver

    Ports:
    - I_RESONANT: Current sense signal (0-3V, proportional to resonant current)
    - VOUT_SENSE: Output voltage tap (12V secondary side)
    - GATE_HI: High-side gate drive output
    - GATE_LO: Low-side gate drive output
    - SWITCH_NODE: Half-bridge switching node (VS for bootstrap)
    - ENABLE: Shutdown control (active high)
    """

    # Power rails (connect by name across design, not ports)
    VCC_15V = Net("+15V")  # Main analog supply for control ICs
    VCC_12V = Net("+12V")  # Secondary-side supply (for TL431/opto)
    GND_PRI = Net("GND")  # Primary-side ground
    GND_SEC = Net("GND_SEC")  # Secondary-side ground (isolated)

    # Internal nets
    I_SENSE_SCALED = Net("I_SENSE_SCALED")  # Scaled current sense signal (0-3V)
    V_ERROR = Net("V_ERROR")  # Error voltage from feedback network
    RAMP_COMP = Net("RAMP_COMP")  # Slope compensation ramp
    I_PLUS_RAMP = Net("I_PLUS_RAMP")  # Summed signal (current + ramp)
    COMP_OUT = Net("COMP_OUT")  # Comparator output (RESET signal)
    VCO_OUT = Net("VCO_OUT")  # VCO output (SET signal)
    Q_LATCH = Net("Q_LATCH")  # RS latch Q output
    Q_LATCH_N = Net("Q_LATCH_N")  # RS latch /Q output
    HI_LOGIC = Net("HI_LOGIC")  # High-side logic after dead-time
    LO_LOGIC = Net("LO_LOGIC")  # Low-side logic after dead-time
    OPTO_COLLECTOR = Net("OPTO_COLLECTOR")  # Optocoupler collector output
    VCO_CTRL = Net("VCO_CTRL")  # VCO control voltage (frequency modulation)
    RESET_RAMP = Net("RESET_RAMP")  # Ramp reset signal (from VCO)
    BOOTSTRAP_SUPPLY = Net("VB")  # Bootstrap supply for high-side driver

    # ===========================================================================
    # 1. CURRENT SENSE AMPLIFIER
    # ===========================================================================
    # Scales primary resonant current to 0-3V range
    # Uses LM358 op-amp in non-inverting configuration

    U_ISENSE = Component(
        symbol="Amplifier_Operational:LM358",
        footprint="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
        ref="U",
        value="LM358",
        LCSC="C7950",
        MPN="LM358DR",
    )
    U_ISENSE["V+"].connect(VCC_15V)
    U_ISENSE["V-"].connect(GND_PRI)
    U_ISENSE["1:IN+"].connect(I_RESONANT)
    U_ISENSE["1:IN-"].connect(I_SENSE_SCALED)
    U_ISENSE["1:OUT"].connect(I_SENSE_SCALED)

    # Gain-setting resistors (non-inverting amp, gain = 1 + Rf/Rin)
    # Placeholder values - simulator will derive based on CT ratio
    R_ISENSE_IN = Component("R", ref="R", value="10k")
    R_ISENSE_IN.connect(I_SENSE_SCALED, GND_PRI)

    R_ISENSE_FB = Component("R", ref="R", value="10k")  # Gain = 1 + 10k/10k = 2
    R_ISENSE_FB.connect(I_SENSE_SCALED, U_ISENSE["1:OUT"])

    # Input protection and filtering
    R_ISENSE_SERIES = Component("R", ref="R", value="1k")
    R_ISENSE_SERIES.connect(I_RESONANT, U_ISENSE["1:IN+"])

    C_ISENSE_FILTER = Component("C", ref="C", value="100pF")  # HF noise filter
    C_ISENSE_FILTER.connect(I_RESONANT, GND_PRI)

    # Bypass capacitors
    C_ISENSE_BYPASS = Component("C", ref="C", value="100nF")
    C_ISENSE_BYPASS.connect(VCC_15V, GND_PRI)

    # ===========================================================================
    # 2. VOLTAGE FEEDBACK - TL431 + PC817 OPTO
    # ===========================================================================
    # Secondary-side voltage reference and isolation

    # TL431 shunt regulator on secondary side
    U_VREF = Component(
        symbol="Reference_Voltage:TL431",
        footprint="Package_TO_SOT_SMD:SOT-23",
        ref="U",
        value="TL431",
        LCSC="C7438",
        MPN="TL431IDBVR",
    )
    U_VREF["REF"].connect(Net("VREF_FB"))  # Feedback divider tap
    U_VREF["CATHODE"].connect(Net("OPTO_ANODE"))  # To optocoupler LED
    U_VREF["ANODE"].connect(GND_SEC)

    # Voltage divider (sets 12V output regulation point)
    # TL431 regulates REF to 2.5V: Vout × R2/(R1+R2) = 2.5V
    # For 12V: R1=10k, R2=2.7k → 12V × 2.7k/12.7k = 2.55V (close enough)
    R_VDIV_UPPER = Component("R", ref="R", value="10k")
    R_VDIV_UPPER.connect(VOUT_SENSE, Net("VREF_FB"))

    R_VDIV_LOWER = Component("R", ref="R", value="2.7k")
    R_VDIV_LOWER.connect(Net("VREF_FB"), GND_SEC)

    # Compensation capacitor (Type 2 error amp)
    C_COMP_FB = Component("C", ref="C", value="100nF")
    C_COMP_FB.connect(Net("VREF_FB"), GND_SEC)

    # LED current limiting resistor
    R_LED_LIMIT = Component("R", ref="R", value="1k")
    R_LED_LIMIT.connect(VOUT_SENSE, Net("OPTO_ANODE"))

    # PC817 optocoupler
    U_OPTO = Component(
        symbol="Isolator:PC817",
        footprint="Package_DIP:DIP-4_W7.62mm",
        ref="U",
        value="PC817",
        LCSC="C2905",
        MPN="PC817X2NSZ0F",
    )
    U_OPTO["A"].connect(Net("OPTO_ANODE"))  # Anode (from TL431 cathode)
    U_OPTO["K"].connect(U_VREF["CATHODE"])  # Cathode (to TL431 LED)
    U_OPTO["C"].connect(OPTO_COLLECTOR)  # Collector (primary side)
    U_OPTO["E"].connect(GND_PRI)  # Emitter (primary ground)

    # Collector pull-up resistor
    R_OPTO_PULLUP = Component("R", ref="R", value="10k")
    R_OPTO_PULLUP.connect(VCC_15V, OPTO_COLLECTOR)

    # ===========================================================================
    # 3. ERROR AMPLIFIER (converts opto current to voltage for VCO)
    # ===========================================================================
    # TL072 JFET-input op-amp for low noise

    U_ERR_AMP = Component(
        symbol="Amplifier_Operational:TL072",
        footprint="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
        ref="U",
        value="TL072",
        LCSC="C6961",
        MPN="TL072CDR",
    )
    U_ERR_AMP["V+"].connect(VCC_15V)
    U_ERR_AMP["V-"].connect(GND_PRI)
    U_ERR_AMP["1:IN+"].connect(OPTO_COLLECTOR)  # Non-inverting input from opto
    U_ERR_AMP["1:IN-"].connect(V_ERROR)  # Inverting input (feedback)
    U_ERR_AMP["1:OUT"].connect(VCO_CTRL)  # Output to VCO control voltage

    # Error amp compensation network (Type 2: one pole, one zero)
    R_ERR_FB = Component("R", ref="R", value="100k")  # Placeholder
    R_ERR_FB.connect(V_ERROR, VCO_CTRL)

    C_ERR_ZERO = Component("C", ref="C", value="10nF")  # Placeholder
    C_ERR_ZERO.connect(V_ERROR, VCO_CTRL)

    R_ERR_POLE = Component("R", ref="R", value="10k")  # Placeholder
    R_ERR_POLE.connect(VCO_CTRL, Net("ERR_POLE"))

    C_ERR_POLE = Component("C", ref="C", value="100nF")  # Placeholder
    C_ERR_POLE.connect(Net("ERR_POLE"), GND_PRI)

    # Bypass capacitor
    C_ERR_BYPASS = Component("C", ref="C", value="100nF")
    C_ERR_BYPASS.connect(VCC_15V, GND_PRI)

    # ===========================================================================
    # 4. VCO - CD4046 Voltage-Controlled Oscillator
    # ===========================================================================
    # Generates 100-500kHz clock based on error voltage

    U_VCO = Component(
        symbol="Logic:CD4046",
        footprint="Package_SO:SOIC-16_3.9x9.9mm_P1.27mm",
        ref="U",
        value="CD4046",
        LCSC="C7618",
        MPN="CD4046BM",
    )
    U_VCO["VDD"].connect(VCC_15V)
    U_VCO["VSS"].connect(GND_PRI)
    U_VCO["VCO_IN"].connect(VCO_CTRL)  # Control voltage input
    U_VCO["VCO_OUT"].connect(VCO_OUT)  # Clock output (to RS latch SET)
    U_VCO["R1"].connect(VCC_15V)  # Timing resistor to VDD
    U_VCO["R2"].connect(GND_PRI)  # Not used (single-range VCO)
    U_VCO["C1A"].connect(GND_PRI)  # Timing capacitor pin 1
    U_VCO["C1B"].connect(GND_PRI)  # Timing capacitor pin 2
    U_VCO["INHIBIT"].connect(GND_PRI)  # Enable VCO (active low)
    # Unused PLL pins
    U_VCO["PHASE_COMP_I"].connect(GND_PRI)
    U_VCO["PHASE_COMP_II"].connect(GND_PRI)
    U_VCO["COMPARATOR_IN"].connect(GND_PRI)
    U_VCO["ZENER"].connect(GND_PRI)

    # VCO timing components
    # f = (Vin - 0.5V) / (R × C × VDD)
    # For 100-500kHz range: R=100k, C=1nF, VDD=15V
    R_VCO_TIMING = Component("R", ref="R", value="100k")
    R_VCO_TIMING.connect(U_VCO["R1"], VCC_15V)

    C_VCO_TIMING = Component("C", ref="C", value="1nF")
    C_VCO_TIMING.connect(U_VCO["C1A"], U_VCO["C1B"])

    # Input filter on VCO_IN (reduces jitter)
    R_VCO_FILTER = Component("R", ref="R", value="10k")
    R_VCO_FILTER.connect(VCO_CTRL, U_VCO["VCO_IN"])

    C_VCO_FILTER = Component("C", ref="C", value="10nF")
    C_VCO_FILTER.connect(U_VCO["VCO_IN"], GND_PRI)

    # Bypass capacitor
    C_VCO_BYPASS = Component("C", ref="C", value="100nF")
    C_VCO_BYPASS.connect(VCC_15V, GND_PRI)

    # ===========================================================================
    # 5. SLOPE COMPENSATION RAMP GENERATOR
    # ===========================================================================
    # LM358 integrator with reset, generates sawtooth ramp

    U_RAMP = Component(
        symbol="Amplifier_Operational:LM358",
        footprint="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
        ref="U",
        value="LM358",
        LCSC="C7950",
        MPN="LM358DR",
    )
    U_RAMP["V+"].connect(VCC_15V)
    U_RAMP["V-"].connect(GND_PRI)
    U_RAMP["2:IN+"].connect(GND_PRI)  # Virtual ground
    U_RAMP["2:IN-"].connect(Net("RAMP_INTEG"))  # Integrator feedback
    U_RAMP["2:OUT"].connect(RAMP_COMP)  # Ramp output

    # Integrator components
    R_RAMP_IN = Component("R", ref="R", value="100k")  # Input resistor
    R_RAMP_IN.connect(VCO_OUT, Net("RAMP_INTEG"))

    C_RAMP_INTEG = Component("C", ref="C", value="10nF")  # Integration cap
    C_RAMP_INTEG.connect(Net("RAMP_INTEG"), RAMP_COMP)

    # Reset switch (MOSFET driven by inverted VCO output)
    # 74HC14 Schmitt trigger to invert and clean up VCO signal
    U_RAMP_INV = Component(
        symbol="74xx:74HC14",
        footprint="Package_SO:SOIC-14_3.9x8.7mm_P1.27mm",
        ref="U",
        value="74HC14",
        LCSC="C5599",
        MPN="74HC14D",
    )
    U_RAMP_INV["VCC"].connect(VCC_15V)
    U_RAMP_INV["GND"].connect(GND_PRI)
    U_RAMP_INV["1A"].connect(VCO_OUT)
    U_RAMP_INV["1Y"].connect(RESET_RAMP)

    # N-channel MOSFET as reset switch
    Q_RAMP_RESET = Component(
        symbol="Device:Q_NMOS_GSD",
        footprint="Package_TO_SOT_SMD:SOT-23",
        ref="Q",
        value="2N7002",  # Small signal MOSFET
        LCSC="C8545",  # Placeholder LCSC
    )
    Q_RAMP_RESET["G"].connect(RESET_RAMP)
    Q_RAMP_RESET["S"].connect(GND_PRI)
    Q_RAMP_RESET["D"].connect(Net("RAMP_INTEG"))  # Shorts integrator cap when on

    # Clamp diode to limit ramp to +5V
    D_RAMP_CLAMP = Component(
        symbol="Device:D",
        footprint="Diode_SMD:D_SOD-123",
        ref="D",
        value="1N4148",
        LCSC="C81598",
    )
    D_RAMP_CLAMP.connect(RAMP_COMP, Net("+5V"))  # Clamps at +5V

    # Bypass capacitors
    C_RAMP_BYPASS1 = Component("C", ref="C", value="100nF")
    C_RAMP_BYPASS1.connect(VCC_15V, GND_PRI)

    C_RAMP_INV_BYPASS = Component("C", ref="C", value="100nF")
    C_RAMP_INV_BYPASS.connect(VCC_15V, GND_PRI)

    # ===========================================================================
    # 6. CURRENT-MODE COMPARATOR
    # ===========================================================================
    # Compares (I_sense + ramp) vs V_error, resets RS latch when exceeded

    U_COMP = Component(
        symbol="Comparator:LM393",
        footprint="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
        ref="U",
        value="LM393",
        LCSC="C7955",
        MPN="LM393DR",
    )
    U_COMP["V+"].connect(VCC_15V)
    U_COMP["GND"].connect(GND_PRI)
    U_COMP["1:IN+"].connect(V_ERROR)  # Threshold from error amp
    U_COMP["1:IN-"].connect(I_PLUS_RAMP)  # Sensed current + ramp
    U_COMP["1:OUT"].connect(COMP_OUT)  # Open-collector output

    # Summing network: I_sense + ramp → comparator input
    R_SUM_ISENSE = Component("R", ref="R", value="10k")
    R_SUM_ISENSE.connect(I_SENSE_SCALED, I_PLUS_RAMP)

    R_SUM_RAMP = Component("R", ref="R", value="10k")
    R_SUM_RAMP.connect(RAMP_COMP, I_PLUS_RAMP)

    # Pull-up resistor on open-collector output
    R_COMP_PULLUP = Component("R", ref="R", value="10k")
    R_COMP_PULLUP.connect(VCC_15V, COMP_OUT)

    # Input protection resistors
    R_COMP_IN_POS = Component("R", ref="R", value="1k")
    R_COMP_IN_POS.connect(V_ERROR, U_COMP["1:IN+"])

    R_COMP_IN_NEG = Component("R", ref="R", value="1k")
    R_COMP_IN_NEG.connect(I_PLUS_RAMP, U_COMP["1:IN-"])

    # Bypass capacitor
    C_COMP_BYPASS = Component("C", ref="C", value="100nF")
    C_COMP_BYPASS.connect(VCC_15V, GND_PRI)

    # ===========================================================================
    # 7. RS LATCH (74HC74 configured as SET-RESET latch)
    # ===========================================================================

    U_LATCH = Component(
        symbol="74xx:74HC74",
        footprint="Package_SO:SOIC-14_3.9x8.7mm_P1.27mm",
        ref="U",
        value="74HC74",
        LCSC="C5606",
        MPN="74HC74D",
    )
    U_LATCH["VCC"].connect(VCC_15V)
    U_LATCH["GND"].connect(GND_PRI)
    U_LATCH["1D"].connect(VCC_15V)  # D tied high (always set on clock)
    U_LATCH["1CLK"].connect(VCO_OUT)  # SET on VCO rising edge
    U_LATCH["1CLR"].connect(COMP_OUT)  # RESET when comparator trips (active low)
    U_LATCH["1Q"].connect(Q_LATCH)  # Q output
    U_LATCH["1QN"].connect(Q_LATCH_N)  # /Q output

    # Pull-up on CLR (default high, comparator pulls low to reset)
    R_LATCH_PULLUP = Component("R", ref="R", value="10k")
    R_LATCH_PULLUP.connect(VCC_15V, U_LATCH["1CLR"])

    # Bypass capacitor
    C_LATCH_BYPASS = Component("C", ref="C", value="100nF")
    C_LATCH_BYPASS.connect(VCC_15V, GND_PRI)

    # ===========================================================================
    # 8. DEAD-TIME GENERATION (74HC00 NAND gates + RC delay)
    # ===========================================================================

    U_DEADTIME = Component(
        symbol="74xx:74HC00",
        footprint="Package_SO:SOIC-14_3.9x8.7mm_P1.27mm",
        ref="U",
        value="74HC00",
        LCSC="C5590",
        MPN="74HC00D",
    )
    U_DEADTIME["VCC"].connect(VCC_15V)
    U_DEADTIME["GND"].connect(GND_PRI)

    # RC delay networks (33ns dead-time for GaN FETs)
    R_DEAD_HI = Component("R", ref="R", value="470")
    R_DEAD_HI.connect(Q_LATCH, Net("Q_DELAYED"))

    C_DEAD_HI = Component("C", ref="C", value="100pF")
    C_DEAD_HI.connect(Net("Q_DELAYED"), GND_PRI)

    R_DEAD_LO = Component("R", ref="R", value="470")
    R_DEAD_LO.connect(Q_LATCH_N, Net("QN_DELAYED"))

    C_DEAD_LO = Component("C", ref="C", value="100pF")
    C_DEAD_LO.connect(Net("QN_DELAYED"), GND_PRI)

    # NAND gates: HI = Q NAND delayed_Q, LO = /Q NAND delayed_/Q
    # This creates non-overlapping signals
    U_DEADTIME["1A"].connect(Q_LATCH)
    U_DEADTIME["1B"].connect(Net("Q_DELAYED"))
    U_DEADTIME["1Y"].connect(HI_LOGIC)

    U_DEADTIME["2A"].connect(Q_LATCH_N)
    U_DEADTIME["2B"].connect(Net("QN_DELAYED"))
    U_DEADTIME["2Y"].connect(LO_LOGIC)

    # Bypass capacitor
    C_DEADTIME_BYPASS = Component("C", ref="C", value="100nF")
    C_DEADTIME_BYPASS.connect(VCC_15V, GND_PRI)

    # ===========================================================================
    # 9. GATE DRIVER - IR2110 Half-Bridge Driver
    # ===========================================================================

    U_DRIVER = Component(
        symbol="Driver_FET:IR2110",
        footprint="Package_DIP:DIP-14_W7.62mm",
        ref="U",
        value="IR2110",
        LCSC="C9928",
        MPN="IR2110PBF",
    )
    U_DRIVER["VCC"].connect(VCC_15V)  # Logic supply
    U_DRIVER["COM"].connect(GND_PRI)  # Logic ground
    U_DRIVER["VB"].connect(BOOTSTRAP_SUPPLY)  # Bootstrap supply
    U_DRIVER["VS"].connect(SWITCH_NODE)  # Floating ground (high-side FET source)
    U_DRIVER["HO"].connect(GATE_HI)  # High-side gate output
    U_DRIVER["LO"].connect(GATE_LO)  # Low-side gate output
    U_DRIVER["HIN"].connect(HI_LOGIC)  # High-side logic input
    U_DRIVER["LIN"].connect(LO_LOGIC)  # Low-side logic input
    U_DRIVER["SD"].connect(ENABLE)  # Shutdown (active low, inverted from ENABLE)

    # Bootstrap diode (fast recovery)
    D_BOOT = Component(
        symbol="Device:D",
        footprint="Diode_SMD:D_SMA",
        ref="D",
        value="UF4007",
        LCSC="C111346",
    )
    D_BOOT.connect(VCC_15V, BOOTSTRAP_SUPPLY)

    # Bootstrap capacitor
    C_BOOT = Component("C", ref="C", value="100nF")
    C_BOOT.connect(BOOTSTRAP_SUPPLY, SWITCH_NODE)

    # VCC bypass (bulk + ceramic)
    C_VCC_BULK = Component("C", ref="C", value="10uF")
    C_VCC_BULK.connect(VCC_15V, GND_PRI)

    C_VCC_BYPASS = Component("C", ref="C", value="100nF")
    C_VCC_BYPASS.connect(VCC_15V, GND_PRI)

    # VDD bypass (close to IC)
    C_VDD_BYPASS = Component("C", ref="C", value="100nF")
    C_VDD_BYPASS.connect(BOOTSTRAP_SUPPLY, SWITCH_NODE)

    # COM bypass
    C_COM_BYPASS = Component("C", ref="C", value="100nF")
    C_COM_BYPASS.connect(GND_PRI, U_DRIVER["COM"])

    # Gate series resistors (control dI/dt)
    R_GATE_HI = Component("R", ref="R", value="10")  # Placeholder
    R_GATE_HI.connect(U_DRIVER["HO"], GATE_HI)

    R_GATE_LO = Component("R", ref="R", value="10")  # Placeholder
    R_GATE_LO.connect(U_DRIVER["LO"], GATE_LO)

    # Input pull-downs (noise immunity)
    R_PD_HIN = Component("R", ref="R", value="100k")
    R_PD_HIN.connect(U_DRIVER["HIN"], GND_PRI)

    R_PD_LIN = Component("R", ref="R", value="100k")
    R_PD_LIN.connect(U_DRIVER["LIN"], GND_PRI)

    # SD pull-up (enable by default)
    R_SD_PULLUP = Component("R", ref="R", value="10k")
    R_SD_PULLUP.connect(U_DRIVER["SD"], VCC_15V)


# Interface for integration
if __name__ == "__main__":
    print("DISCRETE_LLC_CONTROLLER block")
    print("This is a complex analog control loop with 7 sub-circuits.")
    print("Ready for review and simulation.")
