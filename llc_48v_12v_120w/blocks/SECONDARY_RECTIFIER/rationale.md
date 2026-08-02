# SECONDARY_RECTIFIER - Design Rationale

## Circuit Description

Center-tapped synchronous rectifier for LLC resonant converter secondary side. Two N-channel MOSFETs rectify alternating transformer windings, combining at the center-tap output. Body diodes provide freewheeling during dead time, MOSFETs conduct during active phase for low conduction loss.

---

## Reference Document

**Texas Instruments SLUA748A** - "Designing LLC Resonant Half-Bridge Power Converter", Section 4.3  
**UCC24610 Datasheet SLUSB94D** - Synchronous Rectifier Controller, Figure 19 typical application

Circuit copied from SLUA748A Figure 12 (center-tapped SR topology) with discrete gate drive implementation per requirement that all parts be JLCPCB-sourceable.

---

## Component Groups

### Group 1: Synchronous Rectifier MOSFETs

**Q_SR1, Q_SR2** - Infineon BSC010N04LS, 40V, 100A, 1mΩ RDS(on)

**Selection criteria (from SLUA748A section 4.3.2):**
- Voltage rating: 3× output voltage minimum → 40V for 12V output (meets 36V minimum)
- Current rating: >1.5× output current → 100A rating for 10A output (10× margin)
- RDS(on): Minimize to reduce conduction loss → 1mΩ is excellent for 12V output
- Package: TDSON-8 provides good thermal performance in compact size

**RDS(on) selection rationale:**
```
I_RMS per FET ≈ I_out / √2 = 10A / 1.414 = 7.07A (50% duty, center-tap)
P_cond = I²RMS × RDS(on) = 7.07² × 0.001Ω = 0.050W per FET

Target: < 1% of output power = 1.2W per FET
Actual: 0.050W per FET → 0.04% of output power
```

**Margin:** RDS(on) loss is negligible. Allows for temperature derating (RDS increases ~50% at 100°C).

**Body diode use (from AN-9709):**
The body diode conducts during dead time before gate turns on MOSFET channel. This is intentional and provides:
1. Freewheeling current path during dead time
2. Zero-voltage switching (ZVS) for primary FETs
3. Prevents reverse voltage across drain-source during off state

Body diode conduction time should be minimized (<5% of period) by fast gate drive turn-on.

**Matched pair:** Q_SR1 and Q_SR2 are identical parts for balanced rectification. RDS(on) mismatch causes unequal heating.

---

### Group 2: Current Sense Resistors (Optional)

**R_SENSE1, R_SENSE2** - 10mΩ, 2512 package, 0.5W, 1% tolerance

**NOT in reference circuit** - This is an ADDITION for RP2040 telemetry requirement.

**Calculation:**
```
I_RMS = 7A per FET (as calculated above)
P_dissipation = I²RMS × R = 7² × 0.010Ω = 0.49W per resistor
Total loss = 2 × 0.49W = 0.98W

Efficiency impact = 0.98W / 120W = 0.82% reduction
```

**Trade-off:** 
- **Benefit:** Enables real-time current measurement for efficiency monitoring and protection
- **Cost:** ~1W additional loss, ~0.8% efficiency reduction
- **Decision:** Include with DNF option - fit if telemetry needed, omit for maximum efficiency

**Matched pair:** 1% tolerance ensures balanced current sensing between windings.

**Alternative:** Hall-effect current sensor (ACS712 or similar) would eliminate resistor loss but adds cost and complexity. Current sense resistors chosen for simplicity and JLCPCB availability.

---

### Group 3: Gate Pull-Down Resistors

**R_GD1, R_GD2** - 10kΩ, 0603, 5% tolerance

**Purpose:** Ensure SR FETs remain off when gate drive is:
- Floating (during startup)
- Disabled (fault condition)
- Transitioning (preventing false turn-on from capacitive coupling)

**Value selection:**
```
Pull-down must overcome gate leakage and coupling:
- MOSFET gate leakage: <100nA typical
- Pull-down current at Vgs_th=2.5V: 2.5V / 10kΩ = 250µA >> 100nA

Must not load gate driver excessively:
- Gate driver source current (typical): 2.5A peak
- Pull-down sink during turn-on: 12V / 10kΩ = 1.2mA << 2.5A
```

**Standard practice** from UCC24610 datasheet: 10kΩ gate pull-down on all SR FETs.

---

### Group 4: Gate Drive Decoupling

**C_VCC** - 1µF, 25V, X7R, 0805

**Purpose:** Decouple gate drive supply (+12V rail) to provide transient current for fast gate charging.

**Charge required per gate transition:**
```
Q_g = 70nC (BSC010N04LS total gate charge at 12V)
C_required = Q_g / ΔV_acceptable = 70nC / 0.5V = 140nF

Selected: 1µF (7× margin)
```

**Frequency response:**
At 250kHz switching frequency, both SR FETs switch per cycle:
```
I_avg = 2 × Q_g × f = 2 × 70nC × 250kHz = 35mA average
```

1µF capacitor provides low-impedance source for this current without voltage droop.

**Placement critical:** Must be placed close to gate driver IC VCC pin to minimize inductance during fast gate transients.

---

### Group 5: Bootstrap Capacitors (Conditional)

**C_BST1, C_BST2** - 1µF, 25V, X7R, 0805, **DNF by default**

**Purpose:** Provide gate drive voltage for bootstrap driver topology (e.g., IR2110-style high-side + low-side driver).

**Marked DNF because:**
In center-tap SR topology, both FETs are low-side (sources tied to ground). No high-side drive needed unless:
1. Gate driver topology uses bootstrap for some other reason
2. SR sources are not at ground potential (unusual)

**If fitted:** Standard 1µF bootstrap caps per IR2110 datasheet recommendation.

**Decision:** Include footprints for flexibility, mark DNF, fit only if specific gate driver implementation requires.

---

## Connections Verified Against Reference

### Transformer Secondary Windings
- **SEC_A → Q_SR1 drain**: Top winding conducts through SR1 during positive half-cycle
- **SEC_B → Q_SR2 drain**: Bottom winding conducts through SR2 during negative half-cycle
- **CT → Output**: Center-tap combines rectified current from both half-cycles

**From SLUA748A Figure 12:** This is the standard center-tap LLC SR connection. Each winding is rectified separately, output combines at CT.

### Gate Drive Signals
- **SR1_GATE → Q_SR1 gate**: Controls SR1 conduction, active when SEC_A positive
- **SR2_GATE → Q_SR2 gate**: Controls SR2 conduction, active when SEC_B positive

**Critical timing (from UCC24610 datasheet):**
- Dead time required: SR1 and SR2 **never** on simultaneously
- Turn-on delay: Minimize body diode conduction (<5% of period)
- Turn-off advance: Prevent reverse conduction into transformer

**Interlock required:** Gate drive logic must ensure SR1_GATE and SR2_GATE are mutually exclusive with dead time.

### Ground Reference
- **Both SR sources → GND**: Common ground return for output current
- **Gate pull-downs → GND**: Ensures gates referenced to source potential

**Single-point ground recommended** at output filter to minimize ground loop noise.

---

## Deviations from Reference Circuit

### 1. Current Sense Resistors (Addition)
**Reference:** No current sensing in minimal LLC SR circuit  
**Implemented:** 10mΩ source resistors

**Justification:** RP2040 telemetry requires output current measurement. Alternatives (Hall sensor, DCR sensing) add complexity or reduce accuracy. Resistor approach is simple, accurate, and allows per-winding current monitoring.

**Cost:** 1W loss, 0.8% efficiency reduction. Acceptable for evaluation/monitoring board. Production version could omit (DNF) for maximum efficiency.

### 2. SR Controller IC Not Included
**Reference:** UCC24610 or similar dedicated SR controller IC  
**Implemented:** Gate drive signals as ports, expecting discrete controller in separate block

**Justification:** UCC24610, UCC24612, LTC4440, etc. are NOT available in JLCPCB catalog (verified by architecture research). Dedicated SR controller ICs are specialized parts from TI/ADI/Linear and not stocked by JLCPCB.

**Alternative (discrete implementation in separate block):**
```
Transformer voltage sensing → Comparator → Gate driver → SR_GATE signal

Components (all JLCPCB Basic/Extended):
- LM339 quad comparator (voltage sensing)
- IR2110 gate driver (2.5A gate drive)
- 74HC logic (dead-time, interlock)
```

**Impact:** SR controller separated into its own block (SECONDARY_SR_DRIVER) for clarity. This block contains only the power rectification stage.

### 3. Bootstrap Capacitors Marked DNF
**Reference:** UCC24610 does not use bootstrap (dedicated SR driver outputs)  
**Implemented:** Bootstrap cap footprints included but DNF

**Justification:** Discrete gate drive implementation may or may not need bootstrap depending on topology chosen. Include footprints for flexibility without committing to specific driver architecture.

---

## Design Rules Applied

### Thermal
**Worst-case power dissipation:**
```
Per FET conduction loss: 0.05W (negligible)
Per FET switching loss: ~0.2W (estimated at 250kHz, 70nC Qg)
Per sense resistor: 0.5W

Total SR block dissipation: 2×(0.05+0.2) + 2×0.5 = 1.5W
```

**Thermal resistance (TDSON-8):**
- θJC: ~1.5°C/W (junction to case)
- θCA: ~50°C/W (case to ambient, minimal PCB copper)

**With 2oz copper pour under MOSFETs:**
- θJA effective: ~30°C/W
- Temperature rise: 1.5W × 30°C/W = 45°C
- Junction temp: 25°C + 45°C = 70°C (safe, Tj_max = 175°C)

**Layout requirement:** 2oz copper pour connecting MOSFET sources and drains to maximize heat spreading. Via stitching to inner layers for thermal conductivity.

### Voltage Stress
**Maximum voltage across SR FETs:**
```
V_DS_max = V_transformer_secondary_peak + margin
V_sec_peak ≈ (V_out + V_F) × √2 ≈ (12V + 0.5V) × 1.414 = 17.7V

Selected: 40V MOSFETs → 2.26× margin
```

**Sufficient for:**
- Normal operation
- Line transients (input voltage variation 36-60V scales secondary)
- Ringing/overshoot during switching

---

## What Cannot Be Verified (Requires Hardware)

1. **Exact gate drive timing**: Turn-on delay, turn-off advance, dead time duration
2. **Body diode conduction interval**: Should be <5% of switching period
3. **Switching waveforms**: Drain-source voltage ringing, dV/dt stress
4. **Thermal performance**: Actual junction temperature under continuous load
5. **EMI**: High dI/dt switching current through PCB traces
6. **Gate drive signal quality**: Ringing on gate drive, propagation delay through driver chain

---

## Integration Notes

### Upstream Connection (from LLC_TRANSFORMER)
- **SEC_A, SEC_B, CT**: Three-wire transformer secondary connection
- **Winding resistance**: Include in transformer spec, affects total loss
- **Leakage inductance**: Part of LLC resonant tank, not visible to SR block

### Downstream Connection (to OUTPUT_FILTER)
- **CT output**: Provides pulsed DC current to filter
- **Ripple current**: ~10A peak-to-peak at 2× switching frequency (500kHz for 250kHz primary)
- **Filter must handle high dI/dt**: Output capacitor ESR critical for ripple voltage

### Gate Drive Connection (from SECONDARY_SR_DRIVER block)
- **SR1_GATE, SR2_GATE**: Expecting 0-12V gate drive signals
- **Rise/fall time**: <100ns preferred to minimize body diode conduction
- **Dead time**: Minimum 50ns, maximum 500ns (trade-off between shoot-through and body diode loss)

---

## Success Criteria

- [x] Two SR MOSFETs selected with RDS(on) < 5mΩ → **1mΩ achieved**
- [x] Voltage rating 3× output voltage → **40V for 12V output, 3.3× margin**
- [x] Conduction loss < 1% of output power → **0.04% achieved**
- [x] All parts sourceable from JLCPCB → **MOSFETs confirmed Extended parts**
- [ ] Gate drive implementation → **Deferred to SECONDARY_SR_DRIVER block**
- [x] Body diode protection inherent → **MOSFET body diodes provide freewheeling**
- [x] Current sensing optional → **Footprints included, DNF for max efficiency**

---

*Rationale written: 2026-08-01*  
*All component values justified against reference or first principles*
