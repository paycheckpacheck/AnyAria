"""
LLC 48V→12V 120W Resonant Converter - Complete Integration

This is the root circuit that integrates all subsystem blocks into a complete
LLC resonant converter design.

Architecture:
    INPUT_FILTER → PRIMARY_HALF_BRIDGE → LLC_RESONANT_TANK → LLC_TRANSFORMER
                                                                    ↓
    OUTPUT_SENSE_PROTECT ← OUTPUT_FILTER ← SECONDARY_RECTIFIER ←---+
              ↓
    DISCRETE_LLC_CONTROLLER (feedback + control)
              ↓
    PRIMARY_HALF_BRIDGE (gate drives)

    AUX_SUPPLY: Provides +5V, +3.3V, +1.2V for all control circuits
    RP2040_TELEMETRY: Monitors all sense points (ADC logging)
    USB_INTERFACE: Connects RP2040 to host PC

Power flow:
    48V DC → INPUT_FILTER → PRIMARY_HALF_BRIDGE → LLC_RESONANT_TANK →
    LLC_TRANSFORMER → SECONDARY_RECTIFIER → OUTPUT_FILTER → 12V 10A output

Control flow:
    OUTPUT_SENSE_PROTECT (voltage/current sense) → DISCRETE_LLC_CONTROLLER →
    PRIMARY_HALF_BRIDGE (gate drives)

Blocks designed:
    - INPUT_FILTER: 48V input protection, filtering, and voltage sensing
    - PRIMARY_HALF_BRIDGE: Half-bridge with gate driver
    - LLC_RESONANT_TANK: Lr-Cr resonant tank with current sense
    - LLC_TRANSFORMER: Isolation transformer with center-tap secondary
    - SECONDARY_RECTIFIER: Synchronous rectifier FETs
    - OUTPUT_FILTER: Output capacitors and sense taps
    - OUTPUT_SENSE_PROTECT: Voltage/current/temp sensing, OVP, feedback opto
    - DISCRETE_LLC_CONTROLLER: Full analog control loop (most complex block)
    - AUX_SUPPLY: 5V/3.3V/1.2V regulators
    - RP2040_TELEMETRY: Telemetry monitoring MCU
    - USB_INTERFACE: USB Type-C for RP2040
"""

import sys
from pathlib import Path

# Add blocks directory to path
blocks_dir = Path(__file__).parent.parent / "blocks"
sys.path.insert(0, str(blocks_dir))

from circuit_synth import circuit, Net

# Import all block circuits
from INPUT_FILTER.block import input_filter
from PRIMARY_HALF_BRIDGE.block import primary_half_bridge
from LLC_RESONANT_TANK.block import llc_resonant_tank
from LLC_TRANSFORMER.block import llc_transformer
from SECONDARY_RECTIFIER.block import secondary_rectifier
from OUTPUT_FILTER.block import output_filter
from OUTPUT_SENSE_PROTECT.block import output_sense_protect
from DISCRETE_LLC_CONTROLLER.block import discrete_llc_controller
from AUX_SUPPLY.block import aux_supply
from RP2040_TELEMETRY.block import rp2040_telemetry
from USB_INTERFACE.block import usb_interface


@circuit(name="LLC_Converter_48V_12V_120W")
def llc_converter():
    """
    Complete LLC resonant converter: 48V input → 12V 10A output.

    Power path: INPUT_FILTER → PRIMARY_HALF_BRIDGE → LLC_RESONANT_TANK →
                LLC_TRANSFORMER → SECONDARY_RECTIFIER → OUTPUT_FILTER

    Control: OUTPUT_SENSE_PROTECT → DISCRETE_LLC_CONTROLLER → PRIMARY_HALF_BRIDGE

    Auxiliary: AUX_SUPPLY, RP2040_TELEMETRY, USB_INTERFACE
    """

    # =========================================================================
    # Power Nets (Global)
    # =========================================================================
    # Primary side (isolated)
    v_bus_48v = Net("+48V")  # Raw 48V input from screw terminal
    v_filt_48v = Net("VIN_FILT")           # Filtered 48V to resonant tank
    gnd_primary = Net("GND")              # Primary ground

    # Secondary side (isolated from primary)
    v_12v = Net("+12V")       # Main 12V output rail
    gnd_secondary = Net("GND")            # Secondary ground (same symbol, isolated by transformer)

    # Auxiliary rails (derived from +12V secondary)
    v_5v = Net("+5V")          # 5V for analog control
    v_3v3 = Net("+3V3")      # 3.3V for RP2040 I/O
    v_1v2 = Net("+1V2")      # 1.2V for RP2040 core

    # =========================================================================
    # BLOCK 1: INPUT_FILTER
    # Purpose: 48V input protection, filtering, voltage sensing
    # =========================================================================
    vin_sense = Net("VIN_SENSE")  # Voltage sense to RP2040 ADC

    input_filter(
        VIN_FILT=v_filt_48v,  # Output: Filtered 48V
        VSENSE=vin_sense,     # Output: Voltage sense (3.14V @ 48V)
    )

    # =========================================================================
    # BLOCK 2: PRIMARY_HALF_BRIDGE
    # Purpose: Switch 48V at 100-500kHz to drive resonant tank
    # =========================================================================
    gate_hi = Net("GATE_HI")  # High-side gate from controller
    gate_lo = Net("GATE_LO")  # Low-side gate from controller
    sw_node = Net("SW_NODE")  # Switching node to resonant tank

    primary_half_bridge(
        HI_IN=gate_hi,        # Input: High-side gate drive
        LO_IN=gate_lo,        # Input: Low-side gate drive
        SW_OUT=sw_node,       # Output: Switch node (0-48V square wave)
        VCC_12V=v_5v,         # Input: Gate driver supply (using 5V, not 12V - see note)
        VDD_5V=v_5v,          # Input: Logic supply
    )
    # Note: Using +5V for VCC_12V because IR2110 VCC max = 20V, and we have 5V available

    # =========================================================================
    # BLOCK 3: LLC_RESONANT_TANK
    # Purpose: Lr-Cr series resonant tank with current sensing
    # =========================================================================
    pri_dot = Net("PRI_DOT")      # Transformer primary dot side
    pri_nodot = Net("PRI_NODOT")  # Transformer primary non-dot side
    isense_p = Net("ISENSE_P")    # Current sense positive
    isense_n = Net("ISENSE_N")    # Current sense negative

    llc_resonant_tank(
        HB_OUT=sw_node,        # Input: Half-bridge output
        PRI_DOT=pri_dot,       # Output: To transformer primary dot
        PRI_NODOT=pri_nodot,   # Output: To transformer primary non-dot
        ISENSE_P=isense_p,     # Output: Current sense+
        ISENSE_N=isense_n,     # Output: Current sense-
    )

    # =========================================================================
    # BLOCK 4: LLC_TRANSFORMER
    # Purpose: Galvanic isolation and voltage transformation
    # =========================================================================
    sec_ct = Net("SEC_CT")    # Secondary center-tap
    sec_a = Net("SEC_A")      # Secondary winding A
    sec_b = Net("SEC_B")      # Secondary winding B

    llc_transformer(
        PRI_P=pri_dot,        # Input: Primary dot
        PRI_N=pri_nodot,      # Input: Primary non-dot
        SEC_CT=sec_ct,        # Output: Center-tap
        SEC_A=sec_a,          # Output: Winding A
        SEC_B=sec_b,          # Output: Winding B
    )

    # =========================================================================
    # BLOCK 5: SECONDARY_RECTIFIER
    # Purpose: Synchronous rectification of transformer secondary
    # =========================================================================
    rect_out = Net("RECT_OUT")  # Rectified output to filter
    sr1_gate = Net("SR1_GATE")  # SR1 gate drive (to be implemented)
    sr2_gate = Net("SR2_GATE")  # SR2 gate drive (to be implemented)

    secondary_rectifier(
        SEC_A=sec_a,           # Input: Winding A
        SEC_B=sec_b,           # Input: Winding B
        CT=rect_out,           # Output: Rectified voltage
        SR1_GATE=sr1_gate,     # Input: SR1 gate (from SR controller TBD)
        SR2_GATE=sr2_gate,     # Input: SR2 gate (from SR controller TBD)
    )

    # =========================================================================
    # BLOCK 6: OUTPUT_FILTER
    # Purpose: Output capacitors and filtering
    # =========================================================================
    vout_sense_filt = Net("VOUT_SENSE_FILT")  # Voltage sense from filter
    isense_out_p = Net("ISENSE_OUT_P")         # Current sense point

    output_filter(
        RECT_P=rect_out,              # Input: Rectified voltage
        VOUT_SENSE=vout_sense_filt,   # Output: Voltage sense tap
        ISENSE_P=isense_out_p,        # Output: Current sense point
    )

    # =========================================================================
    # BLOCK 7: OUTPUT_SENSE_PROTECT
    # Purpose: Voltage/current/temp sensing, OVP, feedback optocoupler
    # =========================================================================
    vout_load = Net("VOUT_LOAD")      # Final output to load connector
    isense_out = Net("ISENSE_OUT")     # Current measurement (0-2.5V for 0-10A)
    vsense_out = Net("VSENSE_OUT")     # Voltage measurement (0-3.24V for 0-12V)
    temp_sense = Net("TEMP_SENSE")     # Temperature sense
    ovp_fault = Net("OVP_FAULT")       # OVP fault signal
    fb_iso = Net("FB_ISO")             # Isolated feedback to controller

    output_sense_protect(
        VOUT_POS=isense_out_p,         # Input: From filter
        VOUT_NEG=vout_load,            # Output: To load
        ISENSE_OUT=isense_out,         # Output: Current measurement
        VSENSE_OUT=vsense_out,         # Output: Voltage measurement
        TEMP_SENSE=temp_sense,         # Output: Temperature sense
        OVP_FAULT=ovp_fault,           # Output: OVP fault
        FB_ISO_OUT=fb_iso,             # Output: Isolated feedback
    )

    # =========================================================================
    # BLOCK 8: DISCRETE_LLC_CONTROLLER
    # Purpose: Complete analog control loop for LLC converter
    # =========================================================================
    i_resonant_sense = Net("I_RESONANT_SENSE")  # Processed resonant current
    enable_ctrl = Net("ENABLE_CTRL")            # Controller enable

    discrete_llc_controller(
        I_RESONANT=i_resonant_sense,   # Input: Resonant current sense
        VOUT_SENSE=fb_iso,             # Input: Isolated voltage feedback
        GATE_HI=gate_hi,               # Output: High-side gate
        GATE_LO=gate_lo,               # Output: Low-side gate
        SWITCH_NODE=sw_node,           # Bidirectional: Bootstrap reference
        ENABLE=enable_ctrl,            # Input: Enable signal
    )

    # =========================================================================
    # BLOCK 9: AUX_SUPPLY
    # Purpose: Generate 5V, 3.3V, 1.2V from 12V output
    # =========================================================================
    aux_supply(
        VIN_12V=v_12v,      # Input: 12V main output
        VOUT_5V=v_5v,       # Output: 5V rail
        VOUT_3V3=v_3v3,     # Output: 3.3V rail
        VOUT_1V2=v_1v2,     # Output: 1.2V rail
    )

    # =========================================================================
    # BLOCK 10: RP2040_TELEMETRY
    # Purpose: Telemetry monitoring (NOT control loop)
    # =========================================================================
    usb_dp = Net("USB_DP")  # USB D+
    usb_dm = Net("USB_DM")  # USB D-
    swclk = Net("SWCLK")    # SWD clock
    swdio = Net("SWDIO")    # SWD data
    run_reset = Net("RUN_RESET")  # Reset signal

    # ADC monitoring nets (8 channels)
    adc_vin = Net("ADC_VIN")          # Input voltage
    adc_vout = Net("ADC_VOUT")        # Output voltage
    adc_iout = Net("ADC_IOUT")        # Output current
    adc_temp_pri = Net("ADC_TEMP_PRI")    # Primary temp
    adc_temp_sec = Net("ADC_TEMP_SEC")    # Secondary temp
    adc_temp_xfmr = Net("ADC_TEMP_XFMR")  # Transformer temp
    adc_eff = Net("ADC_EFF")          # Efficiency calculation
    adc_spare = Net("ADC_SPARE")      # Spare ADC

    rp2040_telemetry(
        IOVDD_3V3=v_3v3,              # Power input
        USB_DP=usb_dp,                # USB D+
        USB_DM=usb_dm,                # USB D-
        ADC_VIN_SENSE=vin_sense,      # ADC0: Input voltage
        ADC_VOUT_SENSE=vsense_out,    # ADC1: Output voltage
        ADC_IOUT_SENSE=isense_out,    # ADC2: Output current
        ADC_TEMP_PRIMARY=adc_temp_pri,    # ADC3: Primary temp
        ADC_TEMP_SECONDARY=temp_sense,    # ADC4: Secondary temp
        ADC_TEMP_XFMR=adc_temp_xfmr,      # ADC5: Transformer temp
        ADC_EFFICIENCY=adc_eff,       # ADC6: Efficiency
        ADC_SPARE=adc_spare,          # ADC7: Spare
        SWCLK=swclk,                  # SWD clock
        SWDIO=swdio,                  # SWD data
        RUN_RESET=run_reset,          # Reset
    )

    # =========================================================================
    # BLOCK 11: USB_INTERFACE
    # Purpose: USB Type-C connector with ESD protection
    # =========================================================================
    usb_interface(
        USB_DP=usb_dp,     # Bidirectional: USB D+
        USB_DM=usb_dm,     # Bidirectional: USB D-
    )

    # =========================================================================
    # Notes and Unimplemented Features
    # =========================================================================
    # TODO: SR controller for synchronous rectifier gate drives (SR1_GATE, SR2_GATE)
    #       Currently using body diode conduction (passive rectification)
    #
    # TODO: Current sense amplifier from LLC resonant tank (ISENSE_P/N → I_RESONANT_SENSE)
    #       Needs differential amplifier to convert shunt voltage to 0-3V signal
    #
    # TODO: Controller enable logic (ENABLE_CTRL currently floating)
    #       Could tie to power-good signal or add enable button
    #
    # TODO: Temperature sensors for primary, secondary, transformer
    #       (ADC_TEMP_PRI, ADC_TEMP_XFMR currently unconnected)
    #
    # TODO: Efficiency measurement circuit (ADC_EFF)
    #       Requires input power and output power sensing


if __name__ == "__main__":
    # Generate KiCad project
    project_dir = Path(__file__).parent.parent

    print("Generating LLC converter KiCad project...")
    print(f"Project directory: {project_dir}")

    # Create circuit instance and generate KiCad project
    circuit_instance = llc_converter()
    circuit_instance.generate_kicad_project(
        str(project_dir / "LLC_48V_12V_120W"),
        force_regenerate=True,
        generate_pcb=True
    )

    print("✓ KiCad project generated")
    print("Next steps:")
    print("  1. Run layout-schematic skill to place and route all sheets")
    print("  2. Run make_spice_clean() to prepare SPICE decks")
    print("  3. Run verify_project() for complete validation")
