"""Sensorless three-phase BLDC driver with current and back-EMF feedback.

An RP2040 drives three half-bridges. Each half-bridge measures its own phase
current across a low-side Kelvin shunt, and divides its phase voltage down for
back-EMF sensing. The three divided phase voltages are compared against a
virtual neutral to give the zero-crossing edges that commutation times from,
which is what makes the drive sensorless.

    ThreePhaseDriver (root)
    +-- Power          VBUS in -> 12V motor rail and 3.3V logic
    +-- UsbProgramming USB-C, CC resistors, D+/D- to the MCU
    +-- Mcu            RP2040, QSPI flash, crystal, SWD
    +-- HalfBridge x3  HI/LI in -> PHASE out, plus ISENSE and BEMF out
    +-- BemfSense      three BEMF taps -> three zero-crossing edges

Feedback into commutation:

* current   three low-side shunts, one INA181 each, into ADC0..ADC2. Used for
            torque control and for over-current shutdown.
* back-EMF  each phase divided by 11 and compared against the virtual neutral
            by a TLV3501 comparator. Its three outputs are the zero-crossing
            edges the commutation state machine advances on.
* rail      the motor rail divided into ADC3, so the duty cycle can be
            compensated for supply droop.

Run it with ``uv run python examples/three_phase_driver.py``.
"""

from pathlib import Path

from circuit_synth import Component, Input, Net, Output, circuit

# Resistor divider from a phase down to an ADC or comparator input. 100k over
# 10k divides by 11, which keeps a 36V rail inside the 3.3V input range with
# margin to spare.
DIVIDER_TOP = "100k"
DIVIDER_BOTTOM = "10k"


def decoupling(value: str = "100nF") -> Component:
    """Create a decoupling capacitor.

    Args:
        value: Capacitance marking.

    Returns:
        The capacitor component.
    """
    return Component(
        symbol="Device:C",
        ref="C",
        value=value,
        footprint="Capacitor_SMD:C_0603_1608Metric",
    )


def resistor(value: str, footprint: str = "Resistor_SMD:R_0603_1608Metric") -> Component:
    """Create a resistor.

    Args:
        value: Resistance marking.
        footprint: KiCad footprint to use.

    Returns:
        The resistor component.
    """
    return Component(symbol="Device:R", ref="R", value=value, footprint=footprint)


@circuit(name="Power")
def power(VBUS: Input, VMOTOR: Output, V3V3: Output):
    """Board supply: the motor rail straight off VBUS, and 3.3V for the logic."""
    bulk = Component(
        symbol="Device:C_Polarized",
        ref="C",
        value="220uF/50V",
        footprint="Capacitor_SMD:CP_Elec_8x10.5",
    )
    fuse = Component(
        symbol="Device:Fuse", ref="F", value="10A", footprint="Fuse:Fuse_1206_3216Metric"
    )
    regulator = Component(
        symbol="Regulator_Linear:AMS1117-3.3",
        ref="U",
        value="AMS1117-3.3",
        footprint="Package_TO_SOT_SMD:SOT-223-3_TabPin2",
    )
    regulator_in = decoupling("10uF")
    regulator_out = decoupling("22uF")
    motor_rail_cap = decoupling("1uF/50V")

    gnd = Net("GND")

    fuse[1] += VBUS
    fuse[2] += VMOTOR
    bulk[1] += VMOTOR
    bulk[2] += gnd
    motor_rail_cap[1] += VMOTOR
    motor_rail_cap[2] += gnd

    regulator[3] += VBUS  # VI
    regulator[2] += V3V3  # VO
    regulator[1] += gnd  # GND
    regulator_in[1] += VBUS
    regulator_in[2] += gnd
    regulator_out[1] += V3V3
    regulator_out[2] += gnd


@circuit(name="UsbProgramming")
def usb_programming(VBUS: Output, USB_DP: Output, USB_DM: Output):
    """USB-C receptacle for programming and power.

    Both CC pins get their own 5.1k pulldown, which is what tells a source this
    is a device and lets the cable be inserted either way up.
    """
    connector = Component(
        symbol="Connector:USB_C_Receptacle_USB2.0_16P",
        ref="J",
        value="USB_C",
        footprint="Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12",
    )
    cc1_pulldown = resistor("5.1k")
    cc2_pulldown = resistor("5.1k")
    vbus_cap = decoupling("10uF")

    gnd = Net("GND")

    for pin in ("A4", "B4", "A9", "B9"):
        connector[pin] += VBUS
    for pin in ("A1", "A12", "B1", "B12", "SH"):
        connector[pin] += gnd

    # Both sides of the receptacle carry the same pair, so either orientation
    # lands on the same two signals.
    connector["A6"] += USB_DP
    connector["B6"] += USB_DP
    connector["A7"] += USB_DM
    connector["B7"] += USB_DM

    connector["A5"] += cc1_pulldown[1]
    cc1_pulldown[2] += gnd
    connector["B5"] += cc2_pulldown[1]
    cc2_pulldown[2] += gnd

    vbus_cap[1] += VBUS
    vbus_cap[2] += gnd


@circuit(name="Mcu")
def mcu(
    V3V3: Input,
    USB_DP: Input,
    USB_DM: Input,
    AH: Output,
    AL: Output,
    BH: Output,
    BL: Output,
    CH: Output,
    CL: Output,
    ISENSE_A: Input,
    ISENSE_B: Input,
    ISENSE_C: Input,
    ZC_A: Input,
    ZC_B: Input,
    ZC_C: Input,
    VRAIL_SENSE: Input,
):
    """RP2040 with its QSPI flash, crystal and SWD header.

    The six PWM outputs come from three PWM slices, so each half-bridge gets a
    complementary pair. The three phase currents land on ADC0 to ADC2, the rail
    monitor on ADC3, and the three zero-crossing edges on plain GPIOs where the
    PIO can timestamp them.
    """
    rp2040 = Component(
        symbol="MCU_RaspberryPi:RP2040",
        ref="U",
        value="RP2040",
        footprint="Package_DFN_QFN:QFN-56-1EP_7x7mm_P0.4mm_EP3.2x3.2mm",
    )
    flash = Component(
        symbol="Memory_Flash:W25Q128JVS",
        ref="U",
        value="W25Q128JVS",
        footprint="Package_SO:SOIC-8_5.23x5.23mm_P1.27mm",
    )
    crystal = Component(
        symbol="Device:Crystal",
        ref="Y",
        value="12MHz",
        footprint="Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
    )
    crystal_caps = [decoupling("15pF") for _ in range(2)]
    swd_header = Component(
        symbol="Connector_Generic:Conn_01x03",
        ref="J",
        value="SWD",
        footprint="Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
    )
    run_pullup = resistor("10k")
    run_cap = decoupling("100nF")
    flash_cs_pullup = resistor("10k")
    io_decoupling = [decoupling() for _ in range(6)]
    core_decoupling = decoupling("1uF")
    adc_decoupling = decoupling("100nF")
    adc_filter = resistor("10R")

    gnd = Net("GND")
    v1v1 = Net("V1V1")
    run = Net("RUN")
    adc_avdd = Net("ADC_AVDD")
    qspi = {name: Net(f"QSPI_{name}") for name in ("SS", "SCLK", "SD0", "SD1", "SD2", "SD3")}

    # Supplies. The RP2040's own regulator makes the 1.1V core rail.
    for pin in ("1", "10", "22", "33", "42", "49"):
        rp2040[pin] += V3V3
    rp2040["44"] += V3V3  # VREG_VIN
    rp2040["45"] += v1v1  # VREG_VOUT
    rp2040["50"] += v1v1  # DVDD
    rp2040["48"] += V3V3  # USB_VDD
    rp2040["57"] += gnd
    core_decoupling[1] += v1v1
    core_decoupling[2] += gnd
    for cap in io_decoupling:
        cap[1] += V3V3
        cap[2] += gnd

    # The ADC supply is filtered from the digital 3.3V so switching noise does
    # not land on the current measurements.
    adc_filter[1] += V3V3
    adc_filter[2] += adc_avdd
    rp2040["43"] += adc_avdd
    adc_decoupling[1] += adc_avdd
    adc_decoupling[2] += gnd

    # Reset and boot
    rp2040["26"] += run
    run_pullup[1] += V3V3
    run_pullup[2] += run
    run_cap[1] += run
    run_cap[2] += gnd

    # Crystal
    rp2040["20"] += crystal[1]  # XIN
    rp2040["21"] += crystal[2]  # XOUT
    crystal_caps[0][1] += crystal[1]
    crystal_caps[0][2] += gnd
    crystal_caps[1][1] += crystal[2]
    crystal_caps[1][2] += gnd

    # QSPI flash
    rp2040["56"] += qspi["SS"]
    rp2040["52"] += qspi["SCLK"]
    rp2040["53"] += qspi["SD0"]
    rp2040["55"] += qspi["SD1"]
    rp2040["54"] += qspi["SD2"]
    rp2040["51"] += qspi["SD3"]
    flash["1"] += qspi["SS"]
    flash["6"] += qspi["SCLK"]
    flash["5"] += qspi["SD0"]
    flash["2"] += qspi["SD1"]
    flash["3"] += qspi["SD2"]
    flash["7"] += qspi["SD3"]
    flash["8"] += V3V3
    flash["4"] += gnd
    flash_cs_pullup[1] += V3V3
    flash_cs_pullup[2] += qspi["SS"]

    # USB
    rp2040["47"] += USB_DP
    rp2040["46"] += USB_DM

    # SWD
    swd_header[1] += rp2040["24"]  # SWCLK
    swd_header[2] += rp2040["25"]  # SWDIO
    swd_header[3] += gnd

    # Gate drive: three PWM slices, one complementary pair each.
    rp2040["2"] += AH  # GPIO0
    rp2040["3"] += AL  # GPIO1
    rp2040["4"] += BH  # GPIO2
    rp2040["5"] += BL  # GPIO3
    rp2040["6"] += CH  # GPIO4
    rp2040["7"] += CL  # GPIO5

    # Feedback in: currents on the ADC, zero crossings on GPIO.
    rp2040["38"] += ISENSE_A  # GPIO26/ADC0
    rp2040["39"] += ISENSE_B  # GPIO27/ADC1
    rp2040["40"] += ISENSE_C  # GPIO28/ADC2
    rp2040["41"] += VRAIL_SENSE  # GPIO29/ADC3
    rp2040["8"] += ZC_A  # GPIO6
    rp2040["9"] += ZC_B  # GPIO7
    rp2040["11"] += ZC_C  # GPIO8


@circuit(name="HalfBridge")
def half_bridge(
    HI: Input,
    LI: Input,
    PHASE: Output,
    VM: Input,
    VDRV: Input,
    ISENSE: Output,
    BEMF: Output,
):
    """One half-bridge with its own current and back-EMF measurement.

    An IR2101 drives a pair of N-channel MOSFETs. The low side returns through
    a Kelvin shunt, and an INA181 amplifies the shunt voltage by 20 into the
    MCU's ADC. A divider on the phase output brings the back-EMF into range for
    the zero-crossing comparator.
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
    high_gate_resistor = resistor("10R", "Resistor_SMD:R_0805_2012Metric")
    low_gate_resistor = resistor("10R", "Resistor_SMD:R_0805_2012Metric")
    bootstrap_cap = Component(
        symbol="Device:C", ref="C", value="1uF/25V",
        footprint="Capacitor_SMD:C_0805_2012Metric",
    )
    bootstrap_diode = Component(
        symbol="Device:D_Schottky", ref="D", value="BAT54",
        footprint="Diode_SMD:D_SOD-123",
    )
    driver_cap = decoupling()

    shunt = Component(
        symbol="Device:R_Shunt",
        ref="R",
        value="5mR",
        footprint="Resistor_SMD:R_2512_6332Metric_Pad1.52x3.35mm_HandSolder",
    )
    current_amp = Component(
        symbol="Amplifier_Current:INA181",
        ref="U",
        value="INA181A2",
        footprint="Package_TO_SOT_SMD:SOT-23-6",
    )
    amp_cap = decoupling()
    amp_filter = resistor("1k")
    amp_filter_cap = decoupling("1nF")

    bemf_top = resistor(DIVIDER_TOP)
    bemf_bottom = resistor(DIVIDER_BOTTOM)

    gnd = Net("GND")
    boot = Net("BOOT")
    high_gate = Net("HGATE")
    low_gate = Net("LGATE")
    shunt_high = Net("SHUNT_HI")
    amp_out = Net("ISENSE_RAW")

    # Gate driver
    driver[1] += VDRV  # VCC
    driver[4] += gnd  # COM
    driver[2] += HI  # HIN
    driver[3] += LI  # LIN
    driver_cap[1] += VDRV
    driver_cap[2] += gnd

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

    # Half bridge, with the low side returning through the shunt
    high_fet[1] += high_gate
    high_fet[2] += VM
    high_fet[3] += PHASE

    low_fet[1] += low_gate
    low_fet[2] += PHASE
    low_fet[3] += shunt_high

    shunt[1] += shunt_high
    shunt[2] += gnd
    # Pins 3 and 4 are the Kelvin taps, which see only the shunt voltage and
    # not the drop along the power path.
    shunt[3] += current_amp[3]  # +
    shunt[4] += current_amp[4]  # -

    current_amp[6] += VDRV  # V+
    current_amp[2] += gnd  # GND
    current_amp[5] += gnd  # REF, so the output sits at zero for zero current
    current_amp[1] += amp_out
    amp_cap[1] += VDRV
    amp_cap[2] += gnd

    # A single pole into the ADC keeps switching edges off the measurement.
    amp_filter[1] += amp_out
    amp_filter[2] += ISENSE
    amp_filter_cap[1] += ISENSE
    amp_filter_cap[2] += gnd

    # Back-EMF divider
    bemf_top[1] += PHASE
    bemf_top[2] += BEMF
    bemf_bottom[1] += BEMF
    bemf_bottom[2] += gnd


@circuit(name="BemfSense")
def bemf_sense(
    BEMF_A: Input,
    BEMF_B: Input,
    BEMF_C: Input,
    VMOTOR: Input,
    V3V3: Input,
    ZC_A: Output,
    ZC_B: Output,
    ZC_C: Output,
):
    """Zero-crossing detection for sensorless commutation.

    Each divided phase is compared against a virtual neutral made from the same
    three phases through matched resistors, handing the MCU a clean edge every
    time a phase crosses the neutral point.
    """
    # One comparator per phase. Single-part comparators are used rather than a
    # quad, because each unit of a multi-part symbol would otherwise have to be
    # placed and labelled individually.
    comparators = [
        Component(
            symbol="Comparator:TLV3501AIDBV",
            ref="U",
            value="TLV3501",
            footprint="Package_TO_SOT_SMD:SOT-23-6",
        )
        for _ in range(3)
    ]
    neutral_resistors = [resistor("10k") for _ in range(3)]
    pullups = [resistor("10k") for _ in range(3)]
    rail_top = resistor(DIVIDER_TOP)
    rail_bottom = resistor(DIVIDER_BOTTOM)
    supply_caps = [decoupling() for _ in range(3)]

    gnd = Net("GND")
    neutral = Net("VNEUTRAL")

    # Virtual neutral: the star point the phases are measured against.
    for source, element in zip((BEMF_A, BEMF_B, BEMF_C), neutral_resistors):
        element[1] += source
        element[2] += neutral

    phases = ((BEMF_A, ZC_A), (BEMF_B, ZC_B), (BEMF_C, ZC_C))
    for comparator, cap, pullup, (bemf, zero_cross) in zip(
        comparators, supply_caps, pullups, phases
    ):
        comparator[3] += bemf  # +
        comparator[1] += neutral  # -
        comparator[5] += zero_cross  # output
        comparator[4] += V3V3  # V+
        comparator[2] += gnd  # V-
        comparator[6] += V3V3  # SHDN, held high to keep the part enabled
        cap[1] += V3V3
        cap[2] += gnd
        # The output is push-pull, but a pullup keeps the edge defined while
        # the part starts up.
        pullup[1] += V3V3
        pullup[2] += zero_cross

    # Rail monitor, so the duty cycle can be corrected for supply droop.
    rail_top[1] += VMOTOR
    rail_bottom[2] += gnd
    rail_top[2] += rail_bottom[1]


@circuit(name="ThreePhaseDriver")
def three_phase_driver():
    """Sensorless three-phase BLDC driver with current and back-EMF feedback."""
    vbus = Net("VBUS")
    v_motor = Net("VMOTOR")
    v3v3 = Net("V3V3")
    usb_dp = Net("USB_DP")
    usb_dm = Net("USB_DM")
    rail_sense = Net("VRAIL_SENSE")

    phases = []
    for name in ("A", "B", "C"):
        phases.append(
            {
                "high": Net(f"{name}H"),
                "low": Net(f"{name}L"),
                "phase": Net(f"PHASE_{name}"),
                "current": Net(f"ISENSE_{name}"),
                "bemf": Net(f"BEMF_{name}"),
                "zero_cross": Net(f"ZC_{name}"),
            }
        )

    usb_programming(vbus, usb_dp, usb_dm)
    power(vbus, v_motor, v3v3)

    mcu(
        v3v3, usb_dp, usb_dm,
        phases[0]["high"], phases[0]["low"],
        phases[1]["high"], phases[1]["low"],
        phases[2]["high"], phases[2]["low"],
        phases[0]["current"], phases[1]["current"], phases[2]["current"],
        phases[0]["zero_cross"], phases[1]["zero_cross"], phases[2]["zero_cross"],
        rail_sense,
    )

    for leg in phases:
        half_bridge(
            leg["high"], leg["low"], leg["phase"], v_motor, v3v3,
            leg["current"], leg["bemf"],
        )

    bemf_sense(
        phases[0]["bemf"], phases[1]["bemf"], phases[2]["bemf"],
        v_motor, v3v3,
        phases[0]["zero_cross"], phases[1]["zero_cross"], phases[2]["zero_cross"],
    )

    motor = Component(
        symbol="Connector_Generic:Conn_01x03",
        ref="J",
        value="BLDC_MOTOR",
        footprint="Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
    )
    for index, leg in enumerate(phases, start=1):
        motor[index] += leg["phase"]


if __name__ == "__main__":
    output = Path(__file__).parent / "build" / "three_phase_driver"
    three_phase_driver().generate_kicad_project(
        str(output), force_regenerate=True, generate_pcb=False
    )
    print(f"Generated {output}.kicad_pro")
