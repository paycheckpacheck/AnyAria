# Tesla Model S Inverter Bench Power Supply - Approval Gate

**Date:** 2026-08-01  
**Phase:** Architecture Review (Phase 2 of 5)  
**Status:** ⏸️ WAITING FOR USER APPROVAL

---

## What You Asked For

> "Design a AC to DC power supply that can drive a Tesla Model S board. I want to plug this in the wall and power my Tesla board in place of a battery. Motor inverter board. 120V AC input. Add a LSW on output with adjustable trip via RP2040."

## What This Design Provides

✅ **AC-DC bench power supply:**
- Plugs into standard 120V AC, 20A household outlet
- Provides **400V DC @ 5A** (2,000W) HV output for inverter
- Provides **15V DC @ 3A** auxiliary power for control board
- Built-in pre-charge circuit (prevents inrush current damage)

✅ **RP2040-based programmable current limiter:**
- Adjustable trip point: 0.1A to 6.0A (front panel rotary encoder)
- Adjustable trip time: 1ms to 10 seconds
- Real-time display: Current (mA), voltage, power, energy (Wh)
- 128×64 OLED display
- USB-C configuration and data logging
- Optional CAN bus for Tesla inverter diagnostics

✅ **Safety features:**
- 4 kV reinforced isolation (mains to HV output)
- Pre-charge sequencing (prevents capacitor inrush)
- Overcurrent protection (programmable)
- Overvoltage protection (450V crowbar)
- Thermal shutdown (85°C)
- Emergency stop button
- Status interlocks

## ⚠️ CRITICAL LIMITATION

**This supply is for CONTROL BOARD testing ONLY.**

- ✅ **Can do:** Power up inverter control board, test gate drivers, run diagnostics, CAN bus communication
- ❌ **Cannot do:** Drive the motor under load (requires 220-335 kW, supply provides 2 kW)

**Why:** 120V AC @ 20A = 2,400W maximum available from wall outlet. Tesla motor inverter requires 220,000-335,000W at full power.

**If you need to test motor operation:** You need 208/240V 3-phase industrial power, not 120V household outlet.

---

## Block Diagram (High Level)

```
120V AC ──→ [EMI Filter] ──→ [PFC AC-DC] ──→ [Pre-charge] ──→ [Main Contactor] ──→ 400V DC Output
   │                            Module           + 100Ω           (RP2040            (5A max)
   │                           (2 kW)            Relay         controlled)
   │
   └──→ [15V Aux Supply] ──→ 15V @ 3A output for inverter control board
         (Separate module)

                    ┌─ Hall Effect Current Sensor ──→ RP2040 ADC
                    │                                      │
                    ├─ HV Voltage Sense (isolated) ──────→ │
                    │                                      ↓
                    └─ [RP2040 Control Board] ←──→ OLED Display + Encoder
                           │            │
                           ↓            ↓
                    Pre-charge    Main Contactor
                       Relay          Driver
```

---

## Anchor Parts and Sourcing

### ❗ KEY DESIGN DECISION NEEDED

**Problem:** Standard AC-DC power supplies output 12V, 24V, or 48V. Tesla inverter needs 400V DC.

**Four options to get 400V:**

| Option | Description | Cost | Timeline | Complexity |
|--------|-------------|------|----------|------------|
| **A** | 8× 48V supplies in series (8×48V=384V) | ~$240 | 1 week | LOW - simple, bulky |
| **B** | Custom boost converter 48V→400V | ~$200 | 4-6 weeks | HIGH - custom magnetics |
| **C** | Industrial 400V AC-DC module | ~$500+ | 6-12 weeks | LOW - expensive, long lead time |
| **D** | **Accept 96V output** (2×48V) | ~$240 | 1 week | LOW - **may work if inverter accepts it** |

**👉 NEED YOUR DECISION:** Which option for HV conversion?

**My recommendation:** Start with **Option D (96V)** to verify inverter can boot at reduced voltage, then upgrade to Option A or B if full 400V needed.

### Commercial Modules (Not JLCPCB - sourced from DigiKey/Mouser)

| Component | Part Example | Qty | Unit Price | Notes |
|-----------|--------------|-----|------------|-------|
| AC-DC 48V Supply | Mean Well RSP-1600-48 | 2 | $120 | 48V, 33A each → 96V in series |
| Main Contactor | Gigavac GX14 or TE EV200 | 1 | $100 | 500V, 10A, automotive-grade |
| Pre-charge Relay | Panasonic HE-R 12V | 1 | $20 | 400V rated, 10A |
| Pre-charge Resistor | Ohmite 100Ω 50W | 1 | $10 | Limits inrush to 4A |
| DC-Link Capacitor | KEMET 600μF 450V film | 1 | $60 | Low ESR, high ripple current |
| Current Sensor | LEM HASS 50-S | 1 | $35 | ±50A Hall effect, isolated |
| 15V Aux Supply | Mean Well RS-75-15 | 1 | $30 | 75W, AC-DC module |
| OLED Display | Adafruit 128×64 SSD1306 | 1 | $12 | I2C interface |
| Rotary Encoder | Bourns PEC11R | 1 | $4 | Panel mount, with switch |
| Enclosure | Hammond or custom | 1 | $80 | Benchtop or 19" rack |
| **Subtotal** | | | **~$471** | Plus RP2040 board + misc |

### RP2040 Control Board - JLCPCB PCBA

**❗ ISSUE FOUND:** JLCPCB part sourcing API has bugs (JlcPart missing manufacturer attribute).

**Two paths forward:**

1. **Manual part selection:** I design the RP2040 board schematic, then manually find LCSC numbers via JLCPCB website
   - Timeline: +2 weeks for board design
   - Cost: ~$40 for PCBA (qty 1), $15 for qty 10

2. **Use Raspberry Pi Pico** + breakout boards (FASTER)
   - Buy Raspberry Pi Pico ($4, pre-assembled, tested)
   - Add ADC breakout for current/voltage sensing
   - Add relay driver board
   - Timeline: 3-7 days (just wiring)
   - Cost: ~$30 total

**👉 NEED YOUR DECISION:** Custom RP2040 PCB or Raspberry Pi Pico + breakouts?

**My recommendation:** Start with **Pico + breakouts** for proof-of-concept (days vs. weeks), then design custom PCB if you want to productize.

---

## Three Architecture Options

### Option A: Fully Integrated Custom Design
- Everything custom: AC-DC converter, control board, protection circuits
- **Timeline:** 8-12 weeks design + test
- **Cost:** $500-1000 first prototype
- **Risk:** HIGH (safety-critical HV design)
- **Best for:** Production (100+ units), custom requirements

### Option B: Commercial Modules + Custom Control (RECOMMENDED)
- Use commercial AC-DC, contactors, sensors (proven, UL/CE certified)
- Custom RP2040 control board OR Raspberry Pi Pico
- **Timeline:** 2-4 weeks (control only)
- **Cost:** $300-500 first prototype
- **Risk:** MEDIUM (HV modules certified, only control is custom)
- **Best for:** Small batch (10-50 units), reliable and fast

### Option C: Maximum COTS (Commercial Off-The-Shelf)
- All commercial modules, Raspberry Pi Pico, breakout boards
- Assembled with wires and connectors
- **Timeline:** 3-7 days
- **Cost:** $200-400 first unit
- **Risk:** LOW (everything is proven hardware)
- **Best for:** One-off, proof-of-concept, learning

**👉 NEED YOUR DECISION:** Which architecture approach?

**My recommendation:** **Option C** to get working prototype ASAP (this week), then **Option B** if you want production-quality version.

---

## Agent Count and Cost Estimate

If we proceed to Phase 3-5 (detailed block design):

### Option B (Recommended Path)

**Blocks needed:**
1. AC Input & EMI filtering
2. Pre-charge sequencing (commercial relay, RP2040 firmware)
3. HV current sensing & protection
4. RP2040 control board (if custom) OR integration guide (if Pico)
5. 15V auxiliary supply
6. Interlock I/O
7. Front panel HMI (OLED + encoder + LEDs)

**Estimated agents:** ~15-20 total
- 7 block-designer agents (one per block above)
- Each spawns 1 block-reviewer + 1 block-simulator
- Integration + verification

**Estimated tokens:** ~150k-200k (well under 200k budget)

### Option C (COTS Path)

**No circuit-synth agents needed** - this is assembly instructions and wiring diagrams.
- I write assembly guide
- I write RP2040 Pico firmware
- You assemble with commercial modules

**Estimated tokens:** ~20k-30k
**Timeline:** Rest of today + tomorrow

---

## Questions for You

Before proceeding to detailed design (Phase 3-5), I need decisions on:

### 1. HV Output Voltage
- [ ] **96V DC** (2×48V supplies, simple, verify inverter works at low voltage) **RECOMMENDED TO START**
- [ ] **384V DC** (8×48V supplies in series, bulky but works)
- [ ] **400V DC via custom boost** (complex, 4-6 weeks, custom magnetics)
- [ ] **400V DC via industrial module** ($500+, 6-12 weeks lead time)
- [ ] **Other:** ___________

### 2. Architecture
- [ ] **Option C: Maximum COTS** (3-7 days, $200-400) **RECOMMENDED TO START**
- [ ] **Option B: Commercial + custom control** (2-4 weeks, $300-500)
- [ ] **Option A: Fully integrated** (8-12 weeks, $500-1000)

### 3. Control Board
- [ ] **Raspberry Pi Pico + breakouts** (3-7 days) **RECOMMENDED TO START**
- [ ] **Custom RP2040 PCB** (JLCPCB, manual part selection, +2 weeks)

### 4. Optional Features
- [ ] **Include CAN bus** for Tesla inverter communication (adds MCP2515 + TJA1050, ~$10)
- [ ] **Omit CAN** (USB-only, simpler)

### 5. Budget and Timeline
- **Budget:** $__________
- **Need working prototype by:** __________

---

## My Recommendation (Fastest Path to Working Prototype)

**Week 1 (This Week):**
1. **Decision:** Option C architecture (all COTS)
2. **Decision:** 96V HV output (2× Mean Well RSP-1600-48)
3. **Decision:** Raspberry Pi Pico + breakout boards
4. **Decision:** Include CAN bus (only $10 more, useful for diagnostics)

**Parts order (today):**
- 2× Mean Well RSP-1600-48 (48V, 33A) - DigiKey, 1-day ship
- 1× Gigavac GX14 or equivalent contactor - DigiKey
- 1× Panasonic pre-charge relay - DigiKey
- 1× 100Ω 50W resistor - DigiKey
- 1× Film capacitor 600μF 450V - DigiKey
- 1× LEM HASS 50-S current sensor - DigiKey
- 1× Mean Well RS-75-15 (15V aux) - DigiKey
- 1× Raspberry Pi Pico - Adafruit/Amazon
- 1× Adafruit OLED 128×64 - Adafruit
- 1× Rotary encoder - DigiKey
- 1× Enclosure - Hammond or Amazon
- Misc: Anderson SB50 connectors, wire, terminals

**I write (today-tomorrow):**
- RP2040 firmware (pre-charge FSM, current limiter, OLED driver)
- Wiring diagram
- Assembly instructions
- Test procedure

**You assemble (next week):**
- Follow wiring diagram
- Flash firmware to Pico
- Power up and test with current limit set to 0.1A initially
- Gradually increase current limit while monitoring inverter

**Timeline:** Working prototype by **next Friday (Aug 8)**

**Then decide:** If 96V works for your testing needs, done! If you need full 400V, we iterate with custom boost converter or series supplies.

---

## Proceed?

**Reply with your decisions on the 5 questions above, and I'll proceed to the next phase.**

Or, if you want me to proceed with my recommended fast path (Option C, 96V, Pico), just say **"Proceed with COTS fast path"** and I'll start writing the assembly guide and firmware.

---

**Status:** ⏸️ AWAITING USER DECISIONS
