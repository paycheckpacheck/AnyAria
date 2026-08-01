# Tesla Model S Inverter Bench Power Supply - Requirements Specification

## Purpose
Bench test power supply for Tesla Model S motor inverter control board, replacing the HV battery with mains-powered equivalent. Enables inverter board testing, gate driver verification, and control system development without vehicle battery pack.

**CRITICAL LIMITATION:** This supply is designed for inverter control board testing ONLY. It cannot provide the 220-335 kW required for actual motor operation. Maximum output power limited by 120V AC mains input (~2 kW continuous).

## Input Specifications

### AC Mains Input
- **Voltage:** 120V AC ±10% (108-132V RMS)
- **Frequency:** 60 Hz ±3 Hz
- **Circuit Requirement:** Dedicated 20A circuit (2,400W available)
- **Peak Input Power:** 2,000W continuous, 2,400W max
- **Connector:** NEMA 5-20P plug (requires 20A outlet)
- **Protection:** Built-in EMI filter, inrush current limiting

### Power Factor and Efficiency
- **Power Factor Correction (PFC):** Active PFC, PF >0.95 at full load
- **Target Efficiency:** >90% at rated load
- **Standby Power:** <5W when disabled

## Output Specifications

### Main HV DC Rail (Simulated Battery)
- **Nominal Voltage:** 400V DC (adjustable 350-420V via front panel)
- **Voltage Tolerance:** ±2% under load
- **Voltage Ripple:** <2% pk-pk (JESD22-B111 requirement for automotive)
- **Maximum Current:** 5A continuous, 6A peak (1 second)
  - **Rationale:** 2,000W / 400V = 5A max continuous from 120V AC input
  - **Note:** Sufficient for control board, gate drivers, pre-charge, but NOT motor operation
- **Current Limit:** RP2040-programmable, 0.1A to 6A, trip time adjustable
- **Output Connector:** Anderson SB50 (common for EV applications, 50A rated)

### Auxiliary 15V Rail (Control Board Power)
- **Voltage:** 15.0V DC ±3% (matches Tesla's newer 12V system output of 15.5V)
- **Maximum Current:** 3A continuous (45W)
  - **Rationale:** Tesla's DC-DC is 500W, but control board only uses fraction
- **Voltage Ripple:** <100mV pk-pk
- **Output Connector:** 2-pin Molex Micro-Fit 3.0

### Pre-charge Circuit
- **Pre-charge Resistor:** 100Ω, 50W (limits inrush to ~4A from 400V)
- **Pre-charge Time:** <2 seconds to reach 95% of set voltage
- **Pre-charge Relay:** 400V rated, 10A continuous
- **Main Contactor:** 500V rated, 10A continuous
- **Pre-charge Controller:** RP2040-based, monitors DC-link voltage
- **Threshold:** Main contactor closes when DC-link reaches 95% of output voltage

## Protection and Safety Features

### Primary Safety (Mains-Side)
- **Isolation:** 4 kV reinforced isolation (mains to all outputs)
- **Ground Fault Protection:** 30mA RCD recommended on facility circuit
- **Input Fuse:** 20A slow-blow on live conductor
- **Inrush Limiter:** NTC thermistor or active inrush current limiting
- **EMI Filter:** Meets FCC Part 15 Class B, EN 55011 Class B

### Output Protection (HV DC Side)
- **Overvoltage Protection (OVP):** Crowbar at 450V (SCR-based)
- **Overcurrent Protection (OCP):** RP2040-programmable, 0.1-6A, adjustable trip time
- **Short Circuit Protection:** <100μs hardware shutdown, auto-retry disabled
- **Reverse Polarity Protection:** Series Schottky diode or ideal diode controller
- **Thermal Shutdown:** 85°C case temperature limit

### Auxiliary Rail Protection
- **15V OVP:** 17V clamp
- **15V OCP:** 3.5A electronic fuse
- **Reverse Protection:** P-channel MOSFET ideal diode

### Interlocks and Status
- **HV Enable Input:** Dry contact, pulled high = enabled, open = disabled
- **HV Status Output:** Dry contact, closed when HV present and pre-charge complete
- **Fault Output:** Dry contact, closed on any fault condition
- **Front Panel LED Indicators:**
  - AC Input OK (green)
  - Pre-charging (yellow)
  - HV Ready (green)
  - Fault (red)
  - 15V Aux OK (green)

## RP2040 Adjustable Current Limiter

### Functionality
- **Microcontroller:** RP2040 (dual-core ARM Cortex-M0+, 133 MHz)
- **Current Measurement:** Hall effect sensor (50A range, 0-4V analog output)
- **Trip Current Setting:** 0.1A to 6.0A, set via:
  - Front panel rotary encoder with OLED display
  - USB serial interface (CDC ACM)
  - Optional: CAN bus interface for Tesla integration
- **Trip Time:** Adjustable 1ms to 10s (inverse-time curve programmable)
- **Trip Action:** Opens main contactor, latches fault LED, requires manual reset
- **Display:** 128x64 OLED
  - Real-time current (mA resolution)
  - Set trip point
  - Time since power-on
  - Energy delivered (Wh)
  - Fault history log

### Current Limiter Switch (LSW) Circuit
- **Sense Element:** Closed-loop Hall effect sensor (LEM HASS 50-S or equivalent)
  - 50A nominal range
  - 0.2% accuracy
  - Isolated measurement
- **Trip Comparator:** RP2040 ADC + firmware threshold
- **Trip Output:** Digital output drives main contactor coil via driver transistor
- **Response Time:** <10ms firmware loop, <100μs hardware backup
- **Hardware Backup:** Analog comparator for catastrophic overcurrent (>10A)

## Control and Monitoring Interface

### RP2040 Interfaces
- **USB-C:** Configuration, firmware updates, data logging
- **UART/Serial:** Debug console
- **I2C:** OLED display, digital potentiometer (if used)
- **ADC Inputs:**
  - Current sense (Hall effect 0-4V)
  - HV voltage sense (resistive divider, isolated)
  - 15V rail monitor
  - Temperature sensors (NTC thermistors)
- **Digital Outputs:**
  - Main contactor control
  - Pre-charge relay control
  - Fault LED
  - Status LEDs
- **Digital Inputs:**
  - Rotary encoder (trip setting)
  - Enable switch
  - Emergency stop (NC contact)

### Optional CAN Bus Interface
- **Transceiver:** MCP2515 (SPI to CAN) + TJA1050 (CAN transceiver)
- **Baud Rate:** 500 kbps (Tesla standard)
- **Connector:** 2-pin screw terminal or DB9
- **Use Case:** Monitor Tesla inverter CAN messages, log diagnostics
- **CAN IDs Published:**
  - Supply voltage, current, power
  - Fault status
  - Trip point setting
- **Not Required:** Supply operates standalone without CAN

## Environmental and Mechanical

### Operating Environment
- **Temperature Range:** 0°C to 40°C ambient
- **Humidity:** 20% to 80% RH, non-condensing
- **Altitude:** 0-2000m
- **Cooling:** Forced air (temperature-controlled fan)
- **Noise:** <50 dBA at 1 meter

### Physical
- **Form Factor:** Benchtop enclosure, 19" rackmount optional
- **Estimated Dimensions:** 430mm (W) × 200mm (H) × 300mm (D)
- **Weight:** <8 kg
- **Enclosure Material:** Powder-coated steel or aluminum
- **Color:** Lab grey or black
- **Mounting:** Rubber feet, rackmount ears optional

### Connectors and Controls (Front Panel)
- **HV Output:** Anderson SB50 connector (red housing = positive)
- **Aux 15V Output:** Molex Micro-Fit 3.0 (2-pin)
- **Enable Switch:** Illuminated toggle or pushbutton
- **Emergency Stop:** Large red mushroom button (NC contact)
- **OLED Display:** 128x64, white on black
- **Rotary Encoder:** Current limit adjustment with push-button select
- **LED Indicators:** As listed in Interlocks section

### Connectors and Controls (Rear Panel)
- **AC Input:** IEC C19 inlet with integrated fuse holder and switch
- **Earth Ground:** M4 stud for external earth connection
- **USB-C:** RP2040 configuration and logging
- **CAN Bus:** 2-pin 5mm screw terminal (optional)
- **Interlock I/O:** 6-pin terminal block
  - HV Enable In (dry contact)
  - HV Status Out (dry contact, NO/NC/COM)
  - Fault Out (dry contact, NO/NC/COM)

## Design Architecture (Block Diagram)

```
120V AC Input
    ↓
[EMI Filter] → [Inrush Limiter] → [PFC Stage] → 400V DC Bulk
                                                      ↓
                                    [Main Contactor] ←──────┐
                                                      ↓      │
                    [Pre-charge Relay + 100Ω Resistor]      │
                                    ↓                        │
                            [DC-Link Capacitor]              │
                                    ↓                        │
                    [Current Sense (Hall Effect)]           │
                                    ↓                        │
                          [HV Output: 400V, 5A] ────────────┤
                                                             │
[15V Auxiliary Supply] ←─────────────────────────────────┐  │
    ↓                                                     │  │
[RP2040 Control Board]                                   │  │
    - Current limiter logic                              │  │
    - Pre-charge sequencing ──────────────────────────────┼──┘
    - Display & user interface                           │
    - OVP/OCP shutdown control                           │
    - Status monitoring                                  │
    - USB/CAN communication                              │
    ↓                                                     │
[OLED Display] [LEDs] [Encoder] [Contactors] ───────────┘
```

## Part Sourcing Constraints

### Assembly
- **Target:** JLCPCB PCBA for control board (RP2040, protection, sensing)
- **Exceptions (Non-PCBA):**
  - PFC AC-DC module (commercial off-the-shelf, e.g., Mean Well RCP-2000 series)
  - Main contactor (TE Connectivity EV200 or Gigavac GX14 series)
  - Pre-charge relay (Panasonic HE-R, Omron G9EA)
  - DC-link capacitors (high voltage film capacitors, not suitable for reflow)
  - Hall effect current sensor (LEM, Honeywell)
  - AC inlet, enclosure, heatsinks, connectors

### RP2040 Control Board (JLCPCB PCBA)
- RP2040 microcontroller
- MCP2515 CAN controller (if CAN option included)
- TJA1050 CAN transceiver (if CAN option included)
- ADC support components (isolated amplifiers for HV sensing)
- Relay drivers (N-channel MOSFETs, gate drivers)
- Voltage references, protection diodes
- USB-C connector
- I2C OLED connector
- All passives (resistors, capacitors)

## Key Design Numbers (What Decides the Architecture)

1. **Output Power: 2,000W** (limited by 120V AC, 20A input)
   - Determines PFC stage rating, bulk capacitor size, HV current limit
   
2. **HV DC Bus Voltage: 400V**
   - Determines isolation requirements (4 kV), contactor ratings, capacitor voltage rating, OVP threshold
   
3. **Pre-charge Current Limit: ~4A** (400V / 100Ω)
   - Determines pre-charge resistor power rating (50W), relay rating (10A)
   
4. **Current Trip Range: 0.1-6A**
   - Determines Hall sensor range (50A nominal for headroom), ADC resolution requirements
   
5. **Pre-charge Time: <2 seconds**
   - Determines DC-link capacitance (C = t / (R × ln(1/(1-0.95))) ≈ 600μF for 2s, 100Ω)

## Assumptions

1. **Motor operation is NOT required.** User wants to bench-test inverter control board only. The 2 kW power limit allows:
   - Control board power-up and diagnostics
   - Gate driver supply charging
   - CAN bus communication testing
   - Pre-charge and contactor sequencing validation
   - Low-power inverter self-test modes
   - **Cannot** drive the motor under load (requires 220-335 kW)

2. **User has basic electrical safety knowledge.** 400V DC is lethal. Supply includes extensive protection, but user must understand HV safety procedures:
   - Verify output is disabled before connecting/disconnecting
   - Use HV-rated test equipment
   - Discharge DC-link capacitors after shutdown
   - Verify earth ground connection

3. **Cooling for inverter provided separately.** Tesla inverter is liquid-cooled. User must provide:
   - Coolant circulation (even for control board testing, some thermal management needed)
   - Coolant temperature monitoring
   - Thermal interlock (recommended)

4. **JLCPCB assembly for control board only.** High-power components (PFC module, contactors, HV capacitors, current sensor) are commercial modules integrated at final assembly.

5. **Front panel is custom fabricated.** Enclosure panel with cutouts for:
   - OLED display window
   - Rotary encoder shaft
   - LED bezels
   - Switch/button cutouts
   - Connector holes
   - Laser-engraved labels

6. **Current limit serves as both protection and bench testing tool.** Allows gradual power-up testing:
   - Start with 0.1A limit, verify control board boot
   - Increase gradually, monitor for faults
   - Set final limit based on known-good inverter draw

## What This Design Cannot Do (Critical Limitations)

1. **Cannot power motor under load.** 2 kW supply vs. 220 kW motor requirement.
2. **Cannot test full inverter power stage.** IGBTs can be gated, but not switching high current.
3. **Cannot validate thermal performance.** Inverter thermal design requires motor load.
4. **Cannot test regenerative braking.** No bi-directional power flow (supply is source only).
5. **Does not include Battery Management System (BMS) emulation.** If inverter expects BMS CAN messages, user must provide CAN message injection separately.
6. **Does not provide gate driver isolated supplies.** If inverter's gate drivers require external isolated DC-DC converters (some designs use them), user must add separately. Spec assumes gate drivers are powered from 15V aux rail or HV DC bus via onboard converters.

## Success Criteria

Design is successful if:

1. ✓ User can plug into standard 120V AC, 20A outlet
2. ✓ HV output delivers 400V DC at up to 5A continuous
3. ✓ Pre-charge circuit brings DC-link up safely without tripping breaker
4. ✓ Current limiter is user-adjustable 0.1-6A via front panel
5. ✓ RP2040 displays real-time current and energy on OLED
6. ✓ All protection features activate correctly (OVP at 450V, OCP at set point, thermal shutdown, short circuit)
7. ✓ 15V auxiliary rail powers inverter control board
8. ✓ Interlock I/O allows external enable/disable control
9. ✓ USB interface allows data logging and configuration
10. ✓ Unit is safe: reinforced isolation, earth bonding, finger-safe connectors, clear labeling

## Next Steps (Architecture Phase)

1. Find anchor part: PFC AC-DC module (commercial, e.g., Mean Well, TDK-Lambda)
2. Source contactors and relays (TE, Gigavac, Panasonic)
3. Select Hall effect current sensor (LEM, Honeywell)
4. Design RP2040 control board block diagram
5. Decompose into blocks:
   - AC input filtering and protection
   - PFC AC-DC converter (commercial module)
   - Pre-charge sequencing
   - HV current sensing and protection
   - RP2040 control and HMI
   - 15V auxiliary supply
   - Interlock I/O
6. Get user approval before proceeding to detailed design

---

**Document Status:** REQUIREMENTS FROZEN (do not edit after approval gate)
**Author:** Claude Code  
**Date:** 2026-08-01  
**Version:** 1.0
