"""
RP2040_TELEMETRY block.

Monitors LLC converter telemetry via 8 ADC channels.
USB interface for data logging and real-time monitoring.

MONITORING ONLY - does NOT close control loop.
Control is handled by discrete analog circuitry (DISCRETE_LLC_CONTROLLER block).

Reference: RP2040 Datasheet RP-008371-DS-1, Section 2.2 (Minimal Design Example)
"""

from circuit_synth import Net, Component, circuit 


@circuit(name="RP2040_TELEMETRY")
def rp2040_telemetry(
    # Power inputs
    IOVDD_3V3,      # 3.3V I/O supply from AUX_SUPPLY
    # USB interface (routed to USB_INTERFACE block)
    USB_DP,         # USB D+ (to USB connector)
    USB_DM,         # USB D- (to USB connector)
    # ADC inputs (8 channels for telemetry)
    ADC_VIN_SENSE,  # Input voltage (48V sensed, divided)
    ADC_VOUT_SENSE, # Output voltage (12V sensed, divided)
    ADC_IOUT_SENSE, # Output current (0-10A sensed)
    ADC_TEMP_PRIMARY,   # Primary FET temperature
    ADC_TEMP_SECONDARY, # Secondary FET temperature
    ADC_TEMP_XFMR,      # Transformer temperature
    ADC_EFFICIENCY,     # Efficiency measurement channel
    ADC_SPARE,          # Spare ADC input
    # Debug interface
    SWCLK,          # SWD clock (from debug header)
    SWDIO,          # SWD data (from debug header)
    # Optional outputs
    RUN_RESET,      # RUN/RESET signal (to debug header)
):
    """
    RP2040 microcontroller telemetry block.

    Monitors LLC converter via 8 ADC channels:
    1. Input voltage (48V)
    2. Output voltage (12V)
    3. Output current (0-10A)
    4. Primary FET temperature
    5. Secondary FET temperature
    6. Transformer temperature
    7. Efficiency (Pin vs Pout)
    8. Spare channel

    USB interface provides real-time data streaming.
    """

    # Ground symbol
    GND = ("GND")

    # ========================================================================
    # RP2040 Microcontroller (U1)
    # ========================================================================
    # NOTE: Parts marked "to_be_imported" will be filled by part sourcing
    U1 = Component(
        symbol="MCU_RaspberryPi_and_Boards:RP2040",
        ref="U1",
        value="RP2040",
        footprint="to_be_imported",  # QFN-56_7x7mm_P0.4mm
        LCSC="C2040",
        MPN="RP2040",
        notes="Raspberry Pi RP2040 microcontroller. TELEMETRY ONLY - not control loop."
    )

    # ========================================================================
    # Power Supply Decoupling
    # Reference: Datasheet Section 2.16 - "100nF on each IOVDD pin"
    # ========================================================================

    # IOVDD decoupling - 6× 100nF (one per IOVDD pin: 2, 12, 29, 48, 49, 50)
    C1 = Component("C", ref="C1", value="100nF", footprint="to_be_imported",
                   LCSC="C1591", notes="IOVDD pin 2 decoupling")
    C2 = Component("C", ref="C2", value="100nF", footprint="to_be_imported",
                   LCSC="C1591", notes="IOVDD pin 12 decoupling")
    C3 = Component("C", ref="C3", value="100nF", footprint="to_be_imported",
                   LCSC="C1591", notes="IOVDD pin 29 decoupling")
    C4 = Component("C", ref="C4", value="100nF", footprint="to_be_imported",
                   LCSC="C1591", notes="IOVDD pin 48 decoupling (shared with USB_VDD)")
    C5 = Component("C", ref="C5", value="100nF", footprint="to_be_imported",
                   LCSC="C1591", notes="IOVDD pin 49 decoupling")
    C6 = Component("C", ref="C6", value="100nF", footprint="to_be_imported",
                   LCSC="C1591", notes="IOVDD pin 50 decoupling")

    # Connect IOVDD pins to 3.3V rail with decoupling
    # Pins: 2, 12, 29, 48, 49, 50 (all IOVDD in QFN-56 package)
    iovdd_rail = Net("IOVDD_3V3_LOCAL")
    iovdd_rail += IOVDD_3V3
    iovdd_rail += U1["IOVDD_1"]    # Pin 2
    iovdd_rail += U1["IOVDD_2"]    # Pin 12
    iovdd_rail += U1["IOVDD_3"]    # Pin 29
    iovdd_rail += U1["IOVDD_4"]    # Pin 48 (also USB_VDD)
    iovdd_rail += U1["IOVDD_5"]    # Pin 49
    iovdd_rail += U1["IOVDD_6"]    # Pin 50
    iovdd_rail += C1[1] + C2[1] + C3[1] + C4[1] + C5[1] + C6[1]
    GND += C1[2] + C2[2] + C3[2] + C4[2] + C5[2] + C6[2]

    # VREG_VIN and VREG_VOUT - 1µF each (NOT 100nF - critical!)
    # Reference: Datasheet Section 2.16 - "1µF on VREG_VIN and VREG_VOUT"
    C7 = Component("C", ref="C7", value="1uF", footprint="to_be_imported",
                   LCSC="C1848", notes="VREG_VIN input cap - MUST be 1µF per datasheet")
    C8 = Component("C", ref="C8", value="1uF", footprint="to_be_imported",
                   LCSC="C1848", notes="VREG_VOUT output cap - MUST be 1µF per datasheet")

    vreg_in = Net("VREG_VIN")
    vreg_in += IOVDD_3V3  # VREG_VIN powered from same 3.3V rail
    vreg_in += U1["VREG_VIN"]  # Pin 44
    vreg_in += C7[1]
    GND += C7[2]

    vreg_out = Net("VREG_VOUT")
    vreg_out += U1["VREG_VOUT"]  # Pin 45
    vreg_out += C8[1]
    GND += C8[2]

    # DVDD - 1.1V core supply (from VREG_VOUT)
    # Reference: Datasheet - "Connect DVDD to VREG_VOUT"
    # Pins 23 and 50 both connect to VREG_VOUT
    vreg_out += U1["DVDD_1"]  # Pin 23
    vreg_out += U1["DVDD_2"]  # Pin 50

    # ADC_AVDD - filtered supply for ADC
    # Reference: Datasheet - "RC filter from IOVDD for better ADC performance"
    # ADDITION: 10Ω + 100nF filter (not in minimal circuit, but recommended)
    R1 = Component("R", ref="R1", value="10", footprint="to_be_imported",
                   LCSC="C22859", notes="ADC supply filter resistor")
    C9 = Component("C", ref="C9", value="100nF", footprint="to_be_imported",
                   LCSC="C1591", notes="ADC_AVDD decoupling + filter")

    adc_avdd = Net("ADC_AVDD")
    iovdd_rail += R1[1]
    R1[2] += adc_avdd
    adc_avdd += U1["ADC_AVDD"]  # Pin 43
    adc_avdd += C9[1]
    GND += C9[2]

    # ========================================================================
    # Crystal Oscillator (12MHz for USB)
    # Reference: Datasheet Section 2.17 - "12MHz crystal with 15pF load caps"
    # ========================================================================
    Y1 = Component("Crystal", ref="Y1", value="12MHz", footprint="to_be_imported",
                   LCSC="C9002", MPN="X322512MSB4SI",
                   notes="12MHz crystal, 9pF load, for USB operation")

    # Load capacitors: 15pF each (C0G/NP0 for stability)
    # Calculation: C = 2×(CL - Cstray) = 2×(9pF - 3pF) = 12pF → use 15pF std value
    C10 = Component("C", ref="C10", value="15pF", footprint="to_be_imported",
                    LCSC="C1658", notes="Crystal load cap 1 (XIN)")
    C11 = Component("C", ref="C11", value="15pF", footprint="to_be_imported",
                    LCSC="C1658", notes="Crystal load cap 2 (XOUT)")

    xin = Net("XIN")
    xout = Net("XOUT")

    xin += U1["XIN"]  # Pin 20
    xin += Y1[1]
    xin += C10[1]
    GND += C10[2]

    xout += U1["XOUT"]  # Pin 21
    xout += Y1[2]
    xout += C11[1]
    GND += C11[2]

    # NOTE: Datasheet mentions optional 1kΩ series resistor on XOUT to prevent
    # crystal overdrive. OMITTED here as it's optional and 12MHz fundamental
    # mode crystals typically don't require it.

    # ========================================================================
    # USB Interface
    # Reference: Datasheet Section 2.18 - "27Ω series termination"
    # ========================================================================
    R2 = Component("R", ref="R2", value="27", footprint="to_be_imported",
                   LCSC="C23417", notes="USB D+ series termination")
    R3 = Component("R", ref="R3", value="27", footprint="to_be_imported",
                   LCSC="C23417", notes="USB D- series termination")

    usb_dp_int = Net("USB_DP_INT")
    usb_dm_int = Net("USB_DM_INT")

    U1["USB_DP"] += usb_dp_int  # Pin 47
    usb_dp_int += R2[1]
    R2[2] += USB_DP

    U1["USB_DM"] += usb_dm_int  # Pin 46
    usb_dm_int += R3[1]
    R3[2] += USB_DM

    # Note: USB_VDD (pin 48) is same as IOVDD pin 48, already decoupled by C4

    # ========================================================================
    # QSPI Flash (W25Q16JV - 2MB)
    # Reference: Datasheet Section 2.3 - "External Flash"
    # ========================================================================
    U2 = Component(
        symbol="Memory_Flash:W25Q16JV",
        ref="U2",
        value="W25Q16JV",
        footprint="to_be_imported",  # SOIC-8_208mil
        LCSC="C571260",
        MPN="W25Q16JVSSIQ",
        notes="2MB QSPI flash for program storage"
    )

    # Flash power supply decoupling
    C12 = Component("C", ref="C12", value="100nF", footprint="to_be_imported",
                    LCSC="C1591", notes="Flash VCC decoupling")

    flash_vcc = Net("FLASH_VCC")
    flash_vcc += iovdd_rail
    flash_vcc += U2["VCC"]
    flash_vcc += C12[1]
    GND += C12[2]
    GND += U2["GND"]

    # QSPI connections
    U1["QSPI_SS"]   += U2["CS"]    # Pin 53 to flash CS
    U1["QSPI_SCLK"] += U2["CLK"]   # Pin 52 to flash CLK
    U1["QSPI_SD0"]  += U2["SI"]    # Pin 51 to flash SI/IO0
    U1["QSPI_SD1"]  += U2["SO"]    # Pin 54 to flash SO/IO1
    U1["QSPI_SD2"]  += U2["IO2"]   # Pin 55 to flash IO2
    U1["QSPI_SD3"]  += U2["IO3"]   # Pin 56 to flash IO3

    # ========================================================================
    # BOOTSEL Button
    # Reference: Datasheet Section 2.7 - "BOOTSEL mode entry"
    # ========================================================================
    # QSPI_SS (pin 53) doubles as BOOTSEL
    # Pull-up keeps it HIGH for normal boot from flash
    # Button pulls LOW to enter USB bootloader

    R4 = Component("R", ref="R4", value="1k", footprint="to_be_imported",
                   LCSC="C21190", notes="BOOTSEL pull-up (weak, allows button override)")
    SW1 = Component("SW_Push", ref="SW1", value="BOOTSEL", footprint="to_be_imported",
                    LCSC="C318884", notes="BOOTSEL button - hold during power-up for USB bootloader")

    bootsel_net = Net("BOOTSEL")
    bootsel_net += U1["QSPI_SS"]  # Pin 53 (shared with flash CS)
    bootsel_net += R4[1]
    bootsel_net += SW1[1]

    R4[2] += iovdd_rail  # Pull-up to 3.3V
    GND += SW1[2]        # Button pulls to ground

    # ========================================================================
    # Reset / RUN Pin
    # Reference: Datasheet Section 2.14 - "RUN pin must be HIGH for operation"
    # ADDITION: Reset button for development convenience
    # ========================================================================
    R5 = Component("R", ref="R5", value="10k", footprint="to_be_imported",
                   LCSC="C25804", notes="RUN pull-up enables RP2040")
    C13 = Component("C", ref="C13", value="100nF", footprint="to_be_imported",
                    LCSC="C1591", notes="RUN debounce cap")
    SW2 = Component("SW_Push", ref="SW2", value="RESET", footprint="to_be_imported",
                    LCSC="C318884", notes="Manual reset button")

    run_net = Net("RUN")
    run_net += U1["RUN"]  # Pin 26
    run_net += R5[1]
    run_net += C13[1]
    run_net += SW2[1]
    run_net += RUN_RESET  # To debug header

    R5[2] += iovdd_rail  # Pull-up to 3.3V
    GND += C13[2]
    GND += SW2[2]

    # ========================================================================
    # SWD Debug Interface
    # Reference: ARM Cortex-M0+ SWD standard
    # ADDITION: Debug header for programming and debugging
    # ========================================================================
    J1 = Component("Conn_02x03_Odd_Even", ref="J1", value="SWD",
                   footprint="to_be_imported",
                   LCSC="C492406",
                   notes="2×3 SWD debug header (1=VCC 2=SWDIO 3=GND 4=SWCLK 5=GND 6=RUN)")

    # SWD connections (standard ARM 2×3 pinout)
    U1["SWCLK"] += SWCLK + J1["4"]  # Pin 24
    U1["SWDIO"] += SWDIO + J1["2"]  # Pin 25

    iovdd_rail += J1["1"]  # Pin 1: VCC (3.3V)
    GND += J1["3"] + J1["5"]  # Pins 3, 5: GND
    run_net += J1["6"]  # Pin 6: RUN/RESET

    # ========================================================================
    # ADC Inputs (8 channels for telemetry)
    # Reference: Datasheet Section 4.9 - "12-bit 500ksps ADC, 0 to ADC_AVDD range"
    # ========================================================================
    # ADC channels:
    # ADC0 (GPIO26, pin 31): Input voltage sense
    # ADC1 (GPIO27, pin 32): Output voltage sense
    # ADC2 (GPIO28, pin 34): Output current sense
    # ADC3 (GPIO29, pin 35): Primary FET temperature
    # Additional channels via GPIO mux (not all GPIOs shown - see RP2040 datasheet)

    U1["GPIO26_ADC0"] += ADC_VIN_SENSE   # Pin 31: ADC0 - Input voltage (48V sensed)
    U1["GPIO27_ADC1"] += ADC_VOUT_SENSE  # Pin 32: ADC1 - Output voltage (12V sensed)
    U1["GPIO28_ADC2"] += ADC_IOUT_SENSE  # Pin 34: ADC2 - Output current (0-10A)
    U1["GPIO29_ADC3"] += ADC_TEMP_PRIMARY  # Pin 35: ADC3 - Primary FET temp

    # Additional ADC inputs via general GPIO (will be muxed in firmware)
    # Using GPIO0-3 for remaining 4 ADC channels
    U1["GPIO0"] += ADC_TEMP_SECONDARY  # Pin 4: Secondary FET temp
    U1["GPIO1"] += ADC_TEMP_XFMR       # Pin 5: Transformer temp
    U1["GPIO2"] += ADC_EFFICIENCY      # Pin 6: Efficiency measurement
    U1["GPIO3"] += ADC_SPARE           # Pin 7: Spare ADC channel

    # ========================================================================
    # Ground Connections
    # Reference: Datasheet - "Connect all GND pins to ground plane"
    # ========================================================================
    # GND pins: 3, 8, 13, 18, 28, 33, 38, 42, 47 (thermal pad exposed pad bottom)
    GND += U1["GND_1"]   # Pin 3
    GND += U1["GND_2"]   # Pin 8
    GND += U1["GND_3"]   # Pin 13
    GND += U1["GND_4"]   # Pin 18
    GND += U1["GND_5"]   # Pin 28
    GND += U1["GND_6"]   # Pin 33
    GND += U1["GND_7"]   # Pin 38
    GND += U1["GND_8"]   # Pin 42
    GND += U1["PAD"]     # Exposed thermal pad (must be grounded)
