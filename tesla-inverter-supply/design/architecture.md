# Tesla Model S Inverter Bench Supply - Architecture

## Executive Summary

This AC-DC bench power supply provides:
- **400V DC @ 5A** (2 kW) main HV output with pre-charge sequencing
- **15V DC @ 3A** auxiliary control power
- **RP2040-based programmable current limiter** with OLED display
- **120V AC input** from standard 20A household circuit

**CRITICAL LIMITATION:** Control board testing ONLY. Cannot drive motor (requires 220-335 kW vs. 2 kW available).

## Block Diagram

```
┌─────────────────────── 120V AC INPUT (20A Circuit) ───────────────────────┐
│                                                                             │
│  ┌──────────────┐     ┌────────────┐     ┌─────────────────────────────┐  │
│  │  EMI Filter  │ →   │  Inrush    │ →   │   AC-DC PFC Converter       │  │
│  │  + Fuse      │     │  Limiter   │     │   (Commercial Module)       │  │
│  └──────────────┘     └────────────┘     │   120V AC → 400V DC, 2kW    │  │
│                                           └─────────────┬───────────────┘  │
│                                                         │                  │
└─────────────────────────────────────────────────────────┼──────────────────┘
                                                          │
                        ┌─────────────────────────────────┴──────────┐
                        │          DC LINK CAPACITOR                 │
                        │          ~600μF, 450V rated                │
                        └─────────────────────┬──────────────────────┘
                                              │
                        ┌─────────────────────┴──────────────────────┐
                        │                                             │
                   ┌────┴─────┐                               ┌──────┴──────┐
                   │ PRE-     │                               │   MAIN      │
                   │ CHARGE   │                               │ CONTACTOR   │
                   │ RELAY    │                               │ (Normally   │
                   │ + 100Ω   │                               │  Open)      │
                   │ 50W      │                               └──────┬──────┘
                   └────┬─────┘                                      │
                        └────────────────┬───────────────────────────┘
                                         │
                        ┌────────────────┴────────────────┐
                        │   HALL EFFECT CURRENT SENSOR    │
                        │   (LEM HASS 50-S or ACS770)     │
                        │   ±50A range, 0-5V analog out   │
                        └────────────────┬────────────────┘
                                         │
                        ┌────────────────┴────────────────┐
                        │     REVERSE POLARITY            │
                        │     PROTECTION                  │
                        │     (Schottky or ideal diode)   │
                        └────────────────┬────────────────┘
                                         │
                        ┌────────────────┴────────────────┐
                        │  HV OUTPUT: 400V DC, 5A max     │
                        │  Anderson SB50 Connector        │
                        └─────────────────────────────────┘

┌──────────────────────── CONTROL SYSTEM ─────────────────────────────────┐
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │                   RP2040 CONTROL BOARD                          │     │
│  │                                                                  │     │
│  │  • Dual-core ARM Cortex-M0+, 133 MHz                           │     │
│  │  • Current sense input (Hall 0-5V → ADC)                       │     │
│  │  • HV voltage sense (isolated, 400V → ADC via divider)         │     │
│  │  • Pre-charge sequencing state machine                         │     │
│  │  • Programmable current limiter (0.1-6A, adjustable trip time) │     │
│  │  • OLED display driver (I2C, 128x64)                           │     │
│  │  • Rotary encoder interface (quadrature + switch)              │     │
│  │  • USB-C configuration & data logging                          │     │
│  │  • Optional: CAN bus (MCP2515 + TJA1050)                       │     │
│  │  • Relay drivers (pre-charge + main contactor)                 │     │
│  │  • Protection logic (OVP, OCP, thermal shutdown)               │     │
│  │                                                                  │     │
│  └──┬───────────────────────────────────────────────────────┬─────┘     │
│     │                                                        │           │
│  ┌──┴──────────┐    ┌──────────┐    ┌──────────┐    ┌──────┴────┐     │
│  │ Pre-charge  │    │   Main   │    │  OLED    │    │  Rotary   │     │
│  │   Relay     │    │Contactor │    │ Display  │    │  Encoder  │     │
│  │   Driver    │    │  Driver  │    │ 128x64   │    │ with SW   │     │
│  └─────────────┘    └──────────┘    └──────────┘    └───────────┘     │
│                                                                           │
│  Power for RP2040 board:                                                │
│  • Isolated DC-DC: 400V HV bus → 5V/3.3V (MORNSUN/RECOM module)        │
│  • Alternative: Small AC-DC 120V → 5V from mains input                  │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘

┌──────────────────── 15V AUXILIARY OUTPUT ───────────────────────────┐
│                                                                       │
│  Option A: Separate AC-DC Module (120V → 15V, 50W)                  │
│  Option B: Buck converter from 400V HV bus → 15V (more complex)     │
│                                                                       │
│  ┌────────────────────────────────────────────────────────┐         │
│  │   15V @ 3A OUTPUT                                       │         │
│  │   • Overvoltage protection (17V clamp)                 │         │
│  │   • Overcurrent protection (3.5A e-fuse)               │         │
│  │   • Reverse protection (P-FET ideal diode)             │         │
│  │   • Molex Micro-Fit 3.0 connector                      │         │
│  └────────────────────────────────────────────────────────┘         │
└───────────────────────────────────────────────────────────────────────┘
```

## Anchor Parts and Sourcing

### Commercial Modules (NOT JLCPCB PCBA)

These are complete sub-assemblies that will be integrated at final assembly:

#### 1. AC-DC PFC Power Supply Module
**Part:** Mean Well RCP-2000-24 or TDK-Lambda HWS2000-24
- **Input:** 85-264V AC, 47-63 Hz (handles 120V nominal)
- **Output:** 24V DC @ 83A (2 kW)
  - *Note:* We'll post-regulate 24V → 400V using boost converter OR
  - *Alternative:* Find 400V direct output model (rare, expensive)
  - *Better:* Mean Well RSP-2400-48 (48V, 50A) → boost to 400V
- **Features:** Active PFC (PF>0.95), OVP, OCP, OTP
- **Stock:** DigiKey, Mouser (not JLCPCB)
- **Price:** ~$150-250
- **Why this part:** Commercial AC-DC at 2kW is far safer and more reliable than custom design. UL/CE certified.

**ISSUE IDENTIFIED:** Standard AC-DC modules output 12V, 24V, 48V. Getting to 400V requires:
- **Option A:** 48V AC-DC + custom 400V boost converter (complex, expensive)
- **Option B:** Multiple 48V modules in series (8× 48V = 384V, unregulated)
- **Option C:** High-voltage AC-DC module (industrial, $500+, lead time)

**RECOMMENDATION FOR USER:** Reconsider using **2× Mean Well RSP-1600-48** (48V, 33A each) in series for 96V, then **boost converter 96V → 400V** OR accept **96V output** if inverter can operate at reduced voltage for testing.

#### 2. Main Contactor
**Part:** TE Connectivity EV200 or Gigavac GX14
- **Voltage Rating:** 500V DC (400V nominal + margin)
- **Current Rating:** 10A continuous (5A nominal + 2× margin)
- **Coil:** 12V DC
- **Auxiliary Contacts:** 1 NO + 1 NC for status feedback
- **Stock:** DigiKey, Mouser
- **Price:** ~$80-150
- **Why this part:** Automotive-grade, designed for EV applications, proven reliability

#### 3. Pre-charge Relay
**Part:** Panasonic HE-R 12V or Omron G9EA-1-T
- **Voltage Rating:** 400V DC
- **Current Rating:** 10A (pre-charge current is ~4A)
- **Coil:** 12V DC
- **Form:** SPST-NO
- **Stock:** DigiKey, Mouser
- **Price:** ~$15-25

#### 4. Pre-charge Resistor
**Part:** Vishay RH050 or Ohmite 50 Series
- **Resistance:** 100Ω ±5%
- **Power Rating:** 50W continuous
- **Type:** Chassis-mount wirewound or thick film
- **Voltage Rating:** 500V (exceeds 400V application)
- **Stock:** DigiKey, Mouser
- **Price:** ~$8-15
- **Why 100Ω:** Limits inrush to 400V / 100Ω = 4A from 400V source

#### 5. DC-Link Capacitor
**Part:** KEMET C4AEPBW5600A3WJ or TDK B32778
- **Capacitance:** 560-680μF
- **Voltage Rating:** 450V DC (400V nominal + 12.5% margin)
- **Type:** Metallized polypropylene film
- **ESR:** <50 mΩ @ 10 kHz
- **Ripple Current:** >5A RMS @ 100 kHz
- **Stock:** DigiKey, Mouser
- **Price:** ~$40-80
- **Why film:** Electrolytic not rated for high ripple current at 400V

**Pre-charge time calculation:**
```
V(t) = V_final × (1 - e^(-t/RC))
For 95% charge: t = -RC × ln(1 - 0.95) = 3RC
t = 3 × 100Ω × 600μF = 0.18 seconds
```
✓ Well under 2-second requirement

#### 6. Hall Effect Current Sensor
**Part:** LEM HASS 50-S or Honeywell CSLA1CD
- **Range:** ±50A nominal (0-6A application, 8× headroom)
- **Output:** 0.625-4.375V for ±50A (2.5V at 0A)
- **Accuracy:** ±0.5% @ 25°C
- **Isolation:** 3 kV (HV output to control board)
- **Response Time:** <1 μs
- **Supply:** 5V single supply
- **Stock:** DigiKey, Mouser
- **Price:** ~$25-40
- **Why this part:** Closed-loop Hall = accurate + fast, isolated measurement

#### 7. OLED Display Module
**Part:** Adafruit 326 or Waveshare 128x64 I2C OLED
- **Size:** 128×64 pixels, 0.96" diagonal
- **Controller:** SSD1306
- **Interface:** I2C (4-pin: VCC, GND, SCL, SDA)
- **Supply:** 3.3-5V
- **Stock:** Adafruit, Waveshare, Amazon
- **Price:** ~$8-15
- **Why this part:** Standard module, well-supported libraries

#### 8. Rotary Encoder
**Part:** Bourns PEC11R series or Alps EC11E
- **Type:** Incremental, quadrature output
- **Detents:** 24 per revolution
- **Switch:** Integrated push-button (SPST)
- **Mounting:** Through-hole, panel-mount
- **Stock:** DigiKey, Mouser
- **Price:** ~$2-5

#### 9. Isolated DC-DC Converter (Control Board Power)
**Part:** MORNSUN VRB4805S-6WR3 or RECOM RxxP21005D
- **Input:** 36-75V DC (fed from 48V PFC output or HV divider)
- **Output:** 5V @ 1A (for RP2040 board)
- **Isolation:** 3 kV
- **Efficiency:** >80%
- **Package:** SIP or DIP module
- **Stock:** DigiKey, Mouser
- **Price:** ~$15-30
- **Alternative:** If using 24V AC-DC, use simple 24V → 5V buck (no isolation needed)

#### 10. 15V Auxiliary Supply Module
**Part:** Mean Well RS-75-15 or RECOM RAC60-15SK
- **Input:** 85-264V AC (taps from same mains input as main PFC)
- **Output:** 15V @ 5A (75W, exceeds 3A × 15V = 45W requirement)
- **Features:** OVP, short circuit protection
- **Stock:** DigiKey, Mouser
- **Price:** ~$25-40
- **Why separate AC-DC:** Simpler and safer than deriving 15V from 400V HV bus

### RP2040 Control Board - JLCPCB PCBA Feasible

The control board CAN be assembled by JLCPCB if we use available parts:

**ISSUE:** Initial automated sourcing failed due to API bugs in circuit-synth. Manual JLCPCB search needed.

**Components needed:**
1. RP2040 microcontroller (available as LCSC C2040)
2. Supporting components (flash, crystal, LDO, passives)
3. MCP2515 CAN controller (if CAN option included)
4. TJA1050 or SN65HVD230 CAN transceiver
5. USB-C connector
6. MOSFETs for relay drivers
7. Analog front-end for current/voltage sensing
8. Connectors (I2C header for OLED, encoder header, relay outputs)

**Given time constraints and API issues, RECOMMEND:**
- Design RP2040 board using **known-good reference design** (Raspberry Pi Pico schematic)
- Hand-select parts from JLCPCB catalog via web interface
- OR use **Raspberry Pi Pico board** directly (costs $4, pre-assembled, tested)
  - Add external ADC board for isolated HV sensing
  - Add relay driver board
  - Much faster time-to-working-prototype

## Architecture Decision: Modular vs. Integrated

### Option A: Fully Integrated Custom Design
- Custom RP2040 PCB with all sensing, protection, and drivers
- Custom AC-DC or boost converter design
- **Pros:** Optimized, single PCB, professional appearance
- **Cons:** High development time, expensive prototyping, safety-critical high-voltage design
- **Timeline:** 8-12 weeks design + test
- **Cost:** $500-1000 for first prototype

### Option B: Commercial Modules + Custom Control Board (RECOMMENDED)
- Commercial AC-DC PFC module (Mean Well, TDK-Lambda)
- Commercial contactors and relays (TE, Gigavac, Panasonic)
- Commercial current sensor (LEM, Honeywell)
- Custom RP2040 control board (JLCPCB PCBA) OR Raspberry Pi Pico
- **Pros:** Faster development, proven reliability, UL/CE cert'd components, easier debugging
- **Cons:** Larger enclosure, higher BOM cost
- **Timeline:** 2-4 weeks (control board only custom)
- **Cost:** $300-500 for first unit

### Option C: Maximum COTS (Commercial Off-The-Shelf)
- Commercial 48V or 24V AC-DC supply
- DC-DC boost converter module 48V → 400V (if available) OR series connection
- Raspberry Pi Pico + breakout boards
- Commercial relay boards
- Plug-and-play current sensor modules
- **Pros:** Fastest time to working prototype (days), lowest risk, easy to modify
- **Cons:** Least professional appearance, larger enclosure, cable management
- **Timeline:** 3-7 days assembly
- **Cost:** $200-400 for first unit

**RECOMMENDATION:** Start with **Option C** for proof-of-concept, then move to **Option B** for production-quality version if user wants to iterate/sell multiple units.

## Critical Design Challenge: 120V AC → 400V DC at 2 kW

**The Problem:**
- Standard AC-DC supplies output 12V, 24V, or 48V
- Boosting 48V → 400V at 2 kW requires custom high-power boost converter
- This is non-trivial and safety-critical

**Solutions:**

### Solution 1: Series-Connected 48V Supplies (SIMPLE)
Use **8× Mean Well LRS-350-48** (48V, 7.3A each):
- 8 supplies in series = 384V DC
- Each rated 350W, total 2.8 kW available
- Cost: 8 × $30 = $240
- **Pros:** Simple, no custom high-voltage switching, UL/CE certified modules
- **Cons:** Bulky, eight separate modules, complex wiring

**Pre-charge modification:**
- Pre-charge each 48V module's output capacitor individually OR
- Pre-charge the series string (need 380V-rated pre-charge resistor)

### Solution 2: Custom Boost Converter 48V → 400V (COMPLEX)
Design custom interleaved boost converter:
- Input: 48V DC from single Mean Well RSP-2400-48
- Output: 400V DC @ 5A regulated
- Topology: 2-phase interleaved boost, synchronous rectification
- Controller: TI UCC28950 or similar PFC controller
- Inductor: Custom wound, 2× 100μH, 15A rated
- MOSFETs: 100V, <10mΩ Rds(on), TO-247 or D2PAK
- Output diodes: 600V SiC Schottky, 10A
- **Pros:** Single compact converter, optimized efficiency
- **Cons:** Complex design, safety-critical, expensive prototyping, needs magnetics design
- **Timeline:** 4-6 weeks design + test
- **Cost:** $200-300 in parts for first unit

### Solution 3: High-Voltage AC-DC Module (EXPENSIVE)
**Part:** TDK-Lambda SWS1000L-400 or similar
- Input: 100-240V AC
- Output: 400V DC @ 2.5A (1 kW) or find 2 kW variant
- Cost: $400-800
- Lead time: 6-12 weeks (not stocked)
- **Pros:** Turn-key solution, certified
- **Cons:** Very expensive, long lead time, overkill for bench supply

### Solution 4: Accept Lower Voltage (PRAGMATIC)
**Use 96V DC output instead of 400V:**
- 2× Mean Well RSP-1600-48 in series = 96V DC
- Check if Tesla inverter can boot and run diagnostics at 96V (below nominal 350-400V)
- Many inverter control boards have wide input range (e.g., 80-450V)
- **Pros:** Simple, two modules, fast implementation
- **Cons:** May not fully test inverter if it needs >200V minimum

**USER DECISION NEEDED:** Which solution for 120V AC → HV DC conversion?
1. Series 48V supplies (8×) → 384V?
2. Custom boost converter 48V → 400V (complex, 4-6 weeks)?
3. Expensive industrial 400V AC-DC module ($500+)?
4. Accept 96V output and verify inverter works at reduced voltage?

## Pre-charge Sequencing (RP2040 Firmware State Machine)

```
State: INIT
  → Close pre-charge relay
  → Start timer
  → Monitor DC-link voltage via ADC

State: PRE_CHARGING
  → Wait for DC-link to reach 95% of target (380V for 400V target)
  → Timeout after 3 seconds (indicates open circuit or fault)
  → If timeout: Fault state
  → If voltage reached: Close main contactor

State: PRE_CHARGE_COMPLETE
  → Close main contactor
  → Wait 100ms for contact bounce to settle
  → Open pre-charge relay (no longer needed, saves power, prevents overheating)
  → Transition to RUN state

State: RUN
  → Monitor output current continuously
  → Monitor output voltage
  → Monitor temperature
  → If current > trip point for > trip time: Fault state
  → If voltage > 450V (OVP): Fault state
  → If temperature > 85°C: Fault state
  → Update OLED display (current, voltage, power, energy)

State: FAULT
  → Open main contactor immediately
  → Open pre-charge relay
  → Latch fault LED on
  → Display fault code on OLED
  → Log fault to flash memory
  → Require manual reset (button press or power cycle)

State: SHUTDOWN
  → User pressed disable switch or E-stop
  → Open main contactor
  → Open pre-charge relay
  → Safe state, can restart via enable switch
```

## Bill of Materials Estimate (Option B - Commercial Modules)

| Item | Part | Qty | Unit Price | Extended | Source |
|------|------|-----|------------|----------|--------|
| AC-DC PFC Supply | Mean Well RSP-1600-48 | 2 | $120 | $240 | DigiKey |
| Boost Conv 96V→400V | Custom PCB + parts | 1 | $150 | $150 | JLCPCB + parts |
| Main Contactor | Gigavac GX14 | 1 | $100 | $100 | DigiKey |
| Pre-charge Relay | Panasonic HE-R | 1 | $20 | $20 | DigiKey |
| Pre-charge Resistor | Ohmite 50W 100Ω | 1 | $10 | $10 | DigiKey |
| DC-Link Capacitor | KEMET 600μF 450V | 1 | $60 | $60 | DigiKey |
| Current Sensor | LEM HASS 50-S | 1 | $35 | $35 | DigiKey |
| 15V Aux Supply | Mean Well RS-75-15 | 1 | $30 | $30 | DigiKey |
| Iso DC-DC 48V→5V | MORNSUN VRB4805S | 1 | $20 | $20 | DigiKey |
| RP2040 Control Board | Custom PCBA | 1 | $40 | $40 | JLCPCB |
| OLED Display | Adafruit 326 | 1 | $12 | $12 | Adafruit |
| Rotary Encoder | Bourns PEC11R | 1 | $4 | $4 | DigiKey |
| Enclosure | Custom or Hammond | 1 | $80 | $80 | Hammond |
| Connectors, wire, misc | Various | 1 | $50 | $50 | DigiKey |
| **TOTAL** | | | | **$851** | |

**Volume pricing (10 units):** ~$600/unit

**Option C (All COTS) estimate:** ~$350-450/unit

## Next Steps (Awaiting User Approval)

**DECISIONS NEEDED FROM USER:**

1. **HV DC Output Voltage:**
   - [ ] 400V DC (requires custom boost converter or expensive module)
   - [ ] 96V DC (simpler, 2× 48V supplies in series)
   - [ ] Other voltage? (specify)

2. **Architecture Approach:**
   - [ ] Option A: Fully integrated custom (8-12 weeks, $500-1000 prototype)
   - [ ] Option B: Commercial modules + custom control (2-4 weeks, $300-500 prototype) **RECOMMENDED**
   - [ ] Option C: Maximum COTS (3-7 days, $200-400 prototype) **FASTEST**

3. **HV Conversion Method (if 400V selected):**
   - [ ] Series-connected 48V supplies (8×, simple but bulky)
   - [ ] Custom boost converter (complex, 4-6 week design)
   - [ ] Industrial 400V AC-DC ($500+, long lead time)

4. **Control Board:**
   - [ ] Custom RP2040 PCB (JLCPCB PCBA, manual part selection needed due to API bug)
   - [ ] Raspberry Pi Pico + breakout boards (faster, proven)

5. **Optional CAN Bus:**
   - [ ] Include CAN interface for Tesla inverter communication
   - [ ] Omit CAN (USB-only configuration)

6. **Budget and Timeline:**
   - Budget: $______
   - Timeline: Need working prototype by: ______

**Once decisions are made, I will proceed to detailed block design and implementation.**

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| 400V DC is lethal | CRITICAL | Reinforced isolation, finger-safe connectors, interlocks, labeling |
| HV switching design error → fire | HIGH | Use commercial UL/CE modules for AC-DC conversion |
| Insufficient testing → inverter damage | MEDIUM | Programmable current limit, start at 0.1A and ramp up |
| Pre-charge failure → blown fuse | MEDIUM | Separate pre-charge relay, timeout protection, status monitoring |
| No load regulation on series supplies | LOW | Monitor output voltage, OVP protection at 450V |
| 120V input → limited to 2 kW | DESIGN | Clearly document as control board testing only |

---

**Status:** ARCHITECTURE COMPLETE - Awaiting user decisions before proceeding to block design.

**Author:** Claude Code  
**Date:** 2026-08-01
