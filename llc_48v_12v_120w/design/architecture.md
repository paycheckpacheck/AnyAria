# LLC Converter 48V→12V 120W - Architecture

## Block Diagram

```
INPUT (48V) 
   ↓
 [INPUT_FILTER] → TVS, bulk caps, input sensing
   ↓
 [PRIMARY_HALF_BRIDGE] → 2× GaN FETs (Q1, Q2) in half-bridge
   ↓  ↓
 [LLC_RESONANT_TANK] → Lr (resonant inductor), Cr (resonant cap), Lm (magnetizing)
   ↓
 [LLC_TRANSFORMER] → ~4:1 turns ratio, isolation
   ↓
 [SECONDARY_RECTIFIER] → 2× SR FETs (synchronous rectification) in center-tap
   ↓
 [OUTPUT_FILTER] → output caps, LC filter
   ↓
 [OUTPUT_SENSE_PROTECT] → voltage/current sensing, OVP
   ↓
OUTPUT (12V @ 10A)

CONTROL (Fully Discrete Current-Mode):
 [CURRENT_SENSE] → current transformer or shunt + amp in primary resonant current
 [VOLTAGE_FEEDBACK] → error amplifier (op-amp), output voltage sensing, optocoupler isolation
 [SLOPE_COMPENSATION] → ramp generator for current-mode stability
 [CURRENT_MODE_COMPARATOR] → resets switching cycle when Isense + slope > threshold
 [VCO] → voltage-controlled oscillator, frequency modulation (100-500kHz)
 [DEAD_TIME_GENERATOR] → RC delays + logic for non-overlap HI/LO gates
 [PRIMARY_GATE_DRIVER] → high-side + low-side bootstrap drivers for GaN FETs
 [SECONDARY_SR_DRIVER] → synchronous rectifier control (driven from transformer sensing)
 [SOFT_START] → ramp-up circuit, prevents inrush at startup

AUXILIARY:
 [AUX_SUPPLY] → 12V → 5V (500mA) for analog control, drivers
              → 5V → 3.3V (300mA) for RP2040
              → 3.3V → 1.1V (100mA) for RP2040 core
 [RP2040_TELEMETRY] → ADC sensing, USB interface (MONITORING ONLY, not control loop)
 [USB_INTERFACE] → USB-C connector, ESD protection
```

---

## Critical Part Selection

### ✓ SOLUTION: Fully Discrete Current-Mode LLC Controller

**User requirement:** Build the LLC controller from discrete components (comparators, op-amps, VCO, slope compensation) using current-mode control.

**This is EXCELLENT for JLCPCB assembly because:**
- Comparators: LM393, LM339 (Basic parts, pennies)
- Op-amps: LM358, TL072 (Basic parts, pennies)
- Logic gates: 74HC series (Basic parts)
- Oscillator: CD4046 PLL or discrete RC + comparator VCO (Basic parts)
- Optocoupler isolation: PC817 (Basic part)
- Gate drivers: IR2110 / IRS2110 equivalents (common)

**Current-mode control advantages:**
- Inherent cycle-by-cycle current limiting
- Better transient response than voltage-mode
- Slope compensation prevents sub-harmonic oscillation
- Direct control of resonant tank current (ideal for LLC)

**Architecture:**

```
Output Voltage → Error Amp → Opto Isolation → Comp(+) 
                                                ↓
Primary Resonant Current → CT + Amp → Slope Compensation → Comp(-) → RS Latch RESET
                                                                        ↓
VCO (100-500kHz) → Dead Time Logic → RS Latch SET → Gate Driver → GaN FETs
```

**Block breakdown:**
1. **CURRENT_SENSE** - CT or shunt in resonant path, amplified to 0-3V
2. **VOLTAGE_FEEDBACK** - TL431 + opto, error amp (op-amp)
3. **SLOPE_COMPENSATION** - Sawtooth ramp, added to current sense
4. **CURRENT_MODE_COMPARATOR** - Trips when (Isense + ramp) > V_error
5. **VCO** - Voltage-controlled oscillator, CD4046 or discrete
6. **RS_LATCH** - SET by VCO clock, RESET by comparator trip
7. **DEAD_TIME** - RC + inverters, ensures non-overlap
8. **GATE_DRIVER** - IR2110 half-bridge driver

**ALL components are Basic or common Extended parts in JLCPCB.**

---

## Anchor Parts (Availability TBD - Requires JLCPCB Search)

### Primary Power FETs
**Requirement:** GaN FETs, 150V+, ≥8A, RDS(on) < 50mΩ

**Likely candidates** (must verify JLCPCB stock):
- **GaN Systems:** GS-065-011-1-L (650V, 11A, 50mΩ - if available)
- **EPC:** EPC2001C, EPC2015C (similar specs)
- **Innoscience:** IGO60R070A1 (600V, 70A, 70mΩ)

**BACKUP PLAN:** If NO GaN FETs in JLCPCB catalog:
- Use fast low-Qg Si MOSFETs (e.g., IPP80N05S4-02)
- **Impact:** Efficiency drops 1-2%, may not reach 95% target
- Still achievable: 92-93% with good MOSFETs

### Secondary Synchronous Rectifier FETs
**Requirement:** 40V+, ≥15A, RDS(on) < 5mΩ

**Common parts** (likely in JLCPCB Extended):
- Infineon BSC010N04LS (40V, 100A, 1mΩ - overkill but excellent)
- AOS AON6414A (40V, 50A, 1.8mΩ)
- Search: "MOSFET N-channel 40V low RDS(on) < 5mΩ"

### Discrete Control Components (ALL Basic or Common Extended)

**Comparators:**
- LM339 (quad) or LM393 (dual) - Basic parts, <$0.05 each
- Used for: current-mode comparator, window comparators, zero-crossing detect

**Op-Amps:**
- LM358 (dual) or TL072 (dual) - Basic parts, <$0.10 each
- Used for: error amplifier, current sense amp, slope compensation ramp generator

**VCO (Voltage-Controlled Oscillator):**
- CD4046 PLL IC (contains VCO) - Basic part, <$0.20
- OR discrete: op-amp integrator + comparator relaxation oscillator
- Frequency range: 100-500kHz modulated by error voltage

**Logic:**
- 74HC00 (NAND gates) - Basic part
- 74HC74 (D flip-flop for RS latch) - Basic part
- 74HC14 (Schmitt trigger inverters) - Basic part
- Used for: RS latch, dead-time generation, logic combining

**Isolation:**
- PC817 optocoupler - Basic part, <$0.05
- Used for: feedback isolation (primary to secondary)

**Gate Driver:**
- IR2110 / IRS2110 half-bridge driver - Common Extended, ~$0.50
- OR discrete: transistor totem-pole drivers
- Drives high-side + low-side GaN FETs with bootstrap supply

### LLC Transformer
**CRITICAL:** This WILL NOT be in JLCPCB catalog.

**Specification:**
- Turns ratio: 4:1 (48V primary → 12V secondary with center tap)
- Resonant frequency: ~250kHz
- Magnetizing inductance: ~100-150µH
- Resonant inductance: ~20-30µH (leakage + external)
- Power rating: 150W
- Core: ETD29, E core, or pot core (ferrite N87 or similar)

**Sourcing strategy:**
1. Design custom transformer (provide spec)
2. Source from Coilcraft, Würth, or custom winder
3. **MUST** consign to JLCPCB or hand-assemble
4. **THIS IS THE ASSEMBLY BLOCKER**

### Resonant Capacitor (Cr)
**Requirement:** Film capacitor, ~50-100nF, 250V+, low ESR

**May be difficult in JLCPCB:** Film caps at high voltage
- Search: "film capacitor 100nF 250V polypropylene"
- **Backup:** Use multiple ceramics in parallel (C0G/NP0)

### RP2040 Microcontroller
**Requirement:** RP2040, LCSC available

**Likely:**
- LCSC: C2040 (official Raspberry Pi part)
- **Verify stock and price** (should be Extended, ~$1)

### Buck Regulators for Aux Supply
**Requirement:** 12V→5V (500mA), 5V→3.3V (300mA), 3.3V→1.1V (100mA)

**Common in JLCPCB:**
- 12V→5V: MP1584, MP2359 (very common)
- 5V→3.3V: AMS1117-3.3, MIC5219 (LDO acceptable at 300mA)
- 3.3V→1.1V: TPS62xxx series (TPS62175 or similar)

---

## Block Instance Count

| Block | Instances | Notes |
|-------|-----------|-------|
| INPUT_FILTER | 1 | Single 48V input, TVS, bulk caps |
| PRIMARY_HALF_BRIDGE | 1 | 2 GaN FETs (Q1, Q2) |
| LLC_RESONANT_TANK | 1 | Lr, Cr, Lm integrated |
| LLC_TRANSFORMER | 1 | **Custom part - not JLCPCB** |
| SECONDARY_RECTIFIER | 1 | 2 SR FETs (center-tap config) |
| OUTPUT_FILTER | 1 | Single 12V output |
| OUTPUT_SENSE_PROTECT | 1 | V, I, OVP sensing |
| **CURRENT_SENSE** | 1 | **CT + amp in primary resonant current** |
| **VOLTAGE_FEEDBACK** | 1 | **Error amp + opto isolation** |
| **SLOPE_COMPENSATION** | 1 | **Ramp generator** |
| **CURRENT_MODE_COMPARATOR** | 1 | **Trips on Isense + ramp > Verror** |
| **VCO** | 1 | **100-500kHz voltage-controlled oscillator** |
| **RS_LATCH_DEAD_TIME** | 1 | **Logic + dead-time generation** |
| **PRIMARY_GATE_DRIVER** | 1 | **IR2110 drives Q1 (HI), Q2 (LO)** |
| SECONDARY_SR_DRIVER | 1 | Drives both SR FETs |
| AUX_SUPPLY_12V_5V | 1 | Buck converter for analog control |
| AUX_SUPPLY_5V_3V3 | 1 | LDO for RP2040 I/O |
| AUX_SUPPLY_3V3_1V1 | 1 | Buck converter for RP2040 core |
| RP2040_TELEMETRY | 1 | Monitoring only (USB, ADC, not control loop) |
| USB_INTERFACE | 1 | USB-C connector, ESD |

**Total blocks:** 20 (was 15, added 5 discrete control blocks)

**Hierarchical nesting:** 
- **DISCRETE_LLC_CONTROLLER** contains:
  - CURRENT_SENSE
  - VOLTAGE_FEEDBACK
  - SLOPE_COMPENSATION
  - CURRENT_MODE_COMPARATOR
  - VCO
  - RS_LATCH_DEAD_TIME
  - PRIMARY_GATE_DRIVER
- **AUX_SUPPLY** contains three sub-regulators (12V→5V, 5V→3.3V, 3.3V→1.1V)
- **PRIMARY_HALF_BRIDGE** contains gate driver + 2 FETs
- **SECONDARY_RECTIFIER** contains SR driver + 2 FETs

---

## Physical Constraints Check

**Business card size:** 85mm × 55mm = 4675 mm²

**Major component footprints (estimated):**
- LLC Transformer (ETD29): ~30mm × 16mm = 480 mm² (10% of board!)
- RP2040 (QFN-56): ~7mm × 7mm = 49 mm²
- GaN FETs (2×): ~5mm × 6mm each = 60 mm²
- SR FETs (2×): ~5mm × 6mm each = 60 mm²
- Resonant inductor: ~10mm × 10mm = 100 mm²
- Buck regulators (3×): ~150 mm²
- Connectors (input, output, USB): ~300 mm²
- Passives (caps, resistors): ~800 mm²

**Total component area:** ~2000 mm² (~43% of board)

**REALITY CHECK:** This is EXTREMELY tight. The transformer alone is 10% of the board.

**Recommendation:** 
- Request relaxation to 100mm × 80mm (8000 mm², credit-card sized) for manufacturability
- OR use smaller transformer (limits power to ~80W instead of 120W)
- OR vertical transformer mounting (increases height)

---

## Estimated Agent Count

**Phase 3 (Blocks) - Parallel Agents:**
1. block-designer: INPUT_FILTER (→ reviewer + simulator)
2. block-designer: PRIMARY_HALF_BRIDGE (→ reviewer + simulator)
3. block-designer: LLC_RESONANT_TANK (→ reviewer + simulator)
4. block-designer: LLC_TRANSFORMER_SPEC (→ reviewer + simulator)
5. block-designer: SECONDARY_RECTIFIER (→ reviewer + simulator)
6. block-designer: OUTPUT_FILTER (→ reviewer + simulator)
7. block-designer: OUTPUT_SENSE_PROTECT (→ reviewer + simulator)
8. block-designer: **DISCRETE_LLC_CONTROLLER** (→ reviewer + simulator) **← Large block, contains 7 sub-blocks**
9. block-designer: AUX_SUPPLY (→ reviewer + simulator)
10. block-designer: RP2040_TELEMETRY (→ reviewer + simulator)
11. block-designer: USB_INTERFACE (→ reviewer + simulator)

**Each block fans out to 2 sub-agents (reviewer + simulator):**
- 11 blocks × 3 agents per block = **33 agents**

**Note:** DISCRETE_LLC_CONTROLLER is a complex block containing:
- Current sense amplifier
- Error amplifier + opto isolation
- Slope compensation ramp generator
- Current-mode comparator
- VCO (100-500kHz)
- RS latch + dead-time logic
- Gate driver interface
This single block may require **extra review cycles** due to analog feedback loop stability.

**Phase 4 (Integration):** 1 agent (single-threaded)

**Total estimated agents:** ~34-36 agents

**Estimated cost** (assuming Sonnet 4.5 @ $0.003/1K input tokens, 150K tokens/agent avg):
- 35 agents × 150K tokens × $0.003/1K = ~$15.75

**Estimated time** (parallel execution, 3-5 min/agent):
- Phase 3: ~15-20 minutes (parallel, discrete controller block may be slower)
- Phase 4: ~5 minutes
- **Total: ~20-30 minutes**

---

## Assembly Feasibility

### ✓ Fully Assemblable by JLCPCB
- All semiconductors (assuming catalog verification passes)
- All passives (resistors, ceramics)
- All connectors
- RP2040 and support ICs

### ✗ NOT Assemblable by JLCPCB (Consignment or Hand-Assembly Required)
1. **LLC Transformer** - Custom magnetics
2. **Resonant inductor** (if not integrated in transformer) - May need external
3. **Film capacitors** (if not in catalog) - Can substitute with ceramic arrays

### Cost Estimate (Rough)

**Parts cost (JLCPCB Basic + Extended):**
- GaN FETs (2×): $2-4
- SR FETs (2×): $1-2  
- Gate driver (IR2110): $0.50
- SR driver: $0.50
- **Discrete control ICs:**
  - Comparators LM339 (2×): $0.10
  - Op-amps LM358/TL072 (3×): $0.30
  - VCO CD4046: $0.20
  - Logic gates 74HC (3-4 chips): $0.40
  - Optocoupler PC817: $0.05
- RP2040: $1
- Buck regulators (3×): $1.50
- Current transformer (if used): $1-2
- Passives (all, including slope comp): $3-5
- Connectors: $1-2
- **Subtotal:** ~$12-20 (discrete control adds ~$2-3 vs integrated IC)

**External parts (hand-assembly):**
- LLC Transformer (custom): $15-30
- **Total BOM:** ~$25-45

**Assembly cost:** $50-100 (JLCPCB PCBA setup + assembly)
**PCB cost:** $20-40 (4-layer, small qty)

**Total per board:** ~$95-185 (depends on quantity, 1-10 boards)

---

## Assumptions Made (Require User Confirmation)

1. ✓ **Business card size is aspirational** - May need to relax to 100mm × 80mm
2. ✓ **LLC transformer will be externally sourced** - Not in JLCPCB catalog
3. ✓ **Fully discrete current-mode control** - Comparators, op-amps, VCO, logic (ALL JLCPCB Basic parts)
4. ✓ **RP2040 is telemetry ONLY** - Does NOT close control loop, analog control is in hardware
5. ✓ **GaN FETs availability** - Will search, fall back to fast Si MOSFETs if unavailable
6. ✓ **95% efficiency is target** - 92-93% more realistic given constraints
7. ✓ **Synchronous rectification** - Required for efficiency, uses MOSFETs not diodes
8. ✓ **No active PFC** - Input is 48V DC, not AC mains
9. ✓ **Natural convection cooling** - No fan
10. ✓ **Current-mode control** - Slope compensation added, cycle-by-cycle current limiting
11. ✓ **Primary-side current sensing** - Current transformer (CT) or shunt in resonant tank
12. ✓ **Optocoupler isolation** - PC817 for feedback from secondary to primary

---

## What Cannot Be Verified

1. **Thermal performance** - 6W dissipated in small area, no heatsinks modeled
2. **EMI/EMC** - LLC converters radiate at resonant frequency, layout-critical
3. **Transformer design** - Requires FEA, winding details, core loss modeling
4. **Efficiency at 95%** - Requires hardware validation, not achievable in simulation
5. **Startup behavior** - LLC soft-start requires careful control sequencing
6. **Layout parasitics** - Leakage inductance, loop area affect resonant frequency
7. **Business card fit** - Physical 3D modeling required

---

## APPROVAL GATE - Decision Required

**User must approve OR request changes to:**

1. **Topology compromise:** RP2040-controlled half-bridge instead of dedicated LLC controller IC?
2. **Board size:** Relax to 100mm × 80mm instead of strict 85mm × 55mm?
3. **Transformer sourcing:** Accept external transformer (consignment to JLCPCB or hand-assembly)?
4. **Efficiency target:** Accept 92-93% realistic vs 95% aspirational?
5. **GaN availability:** Accept Si MOSFET fallback if GaN not in JLCPCB catalog?
6. **Proceed to Phase 3?** (28-30 agents, ~$15, ~25 minutes, 120W output on ~credit-card-sized board)

**Alternative if user rejects architecture:**
- Switch to phase-shifted full-bridge (easier sourcing)
- Switch to synchronous buck (100% JLCPCB, lower efficiency)
- Reduce power to 60W (allows smaller transformer, tighter fit)

---

*Architecture locked pending approval: 2026-08-01*
*Next step: User approval → Phase 3 (block design) OR architecture revision*
