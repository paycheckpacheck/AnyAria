# LLC Resonant Tank - Design Rationale

## Overview

The LLC resonant tank is the defining element of the LLC converter topology. It provides:
- Zero-voltage switching (ZVS) for primary FETs (reduces switching loss)
- Zero-current switching (ZCS) for secondary rectifiers (reduces reverse recovery loss)
- Regulation via frequency modulation (100-500kHz operating range)
- Inherent current limiting (resonant behavior prevents runaway current)

## Circuit Topology

```
HB_OUT --[Cr 100nF]--+--[Rsense 10mΩ]--+--[Lr 25µH]-- PRI_DOT
                      |                 |
                  ISENSE_P          ISENSE_N
                                        |
                                   PRI_NODOT (via transformer)
```

### Resonant Capacitor (Cr)

**Value:** 100nF (initial, to be optimized by simulation)
**Voltage Rating:** 150V minimum
**Dielectric:** C0G/NP0 preferred, X7R acceptable with derating

**Purpose:**
- Blocks DC component (prevents transformer saturation)
- Forms series resonant tank with Lr
- Determines resonant frequency fr = 1/(2π√(Lr×Cr))

**Design Considerations:**
- ESR must be low to minimize losses at 250kHz
- Voltage rating must exceed peak AC voltage plus DC offset
- At 48V input, half-bridge produces 0-48V square wave
- Capacitor sees full AC swing, so 150V rating provides 3× margin

**Sourcing Challenge:**
- High-voltage C0G ceramics (>100V) are rare in JLCPCB Basic parts
- Film capacitors ideal but not found in automated search
- **DEVIATION:** Extended part or parallel array likely required
- Multiple lower-voltage ceramics in series can achieve voltage rating

### Resonant Inductor (Lr)

**Value:** 25µH (initial, integrated with transformer leakage)
**Current Rating:** 8A RMS minimum
**DCR:** <50mΩ to minimize conduction loss

**Purpose:**
- Forms series resonant tank with Cr
- Determines resonant frequency and quality factor
- Provides energy storage for ZVS operation

**Integration Approach (STANDARD PRACTICE):**
Lr is typically NOT a discrete component in LLC converters. Instead:
1. Transformer is designed with specific leakage inductance
2. Leakage inductance = Lr (the resonant inductance)
3. External Lr only if leakage insufficient or for tuning

**Advantages of integrated approach:**
- Reduces component count and board space
- Eliminates additional conductive loss
- Simplifies layout (one magnetic component, not two)
- Lower cost

**Transformer specification (to LLC_TRANSFORMER block):**
- Primary leakage inductance: Lr = [value from simulation] µH
- Tolerance: ±10% typical (affects resonant frequency)
- Magnetizing inductance: Lm ~ 4-6× Lr (industry standard ratio)

### Current Sense Resistor (Rsense)

**Value:** 10mΩ
**Power Rating:** 1W (2W preferred for margin)
**Tolerance:** 1%
**Package:** 2512 (low thermal resistance)

**Purpose:**
- Measure resonant current for current-mode control loop
- Provides cycle-by-cycle current limit protection
- Enables peak current mode control (better transient response)

**Signal Level Calculation:**
```
At 8A RMS resonant current:
Vsense = I × R = 8A × 10mΩ = 80mV RMS
Power = I² × R = 64 × 0.01 = 0.64W
```

**Design Trade-offs:**
- Higher Rsense → better signal-to-noise ratio → easier amplification
- Higher Rsense → more power loss → lower efficiency
- 10mΩ chosen as conservative middle ground
- 80mV signal is adequate for differential amplifier with gain ~40× to reach 3.2V

**Alternative Considered:**
Current transformer (CT) would provide:
- AC coupling (no DC offset)
- Galvanic isolation
- Higher signal level
- Zero power loss in sensed circuit

**Why CT NOT used:**
- Not available in JLCPCB catalog (assembly blocker)
- Requires external sourcing and hand assembly
- Adds cost and complexity
- Shunt resistor adequate for control requirements

## Resonant Frequency Design

**Target:** fr = 250kHz
**Operating Range:** 100-500kHz (frequency modulation for regulation)

**Initial Calculation:**
```
fr = 1 / (2π√(Lr × Cr))
   = 1 / (2π√(25e-6 × 100e-9))
   = 318kHz
```

**Adjustment needed:** Simulation will optimize Lr and Cr to achieve target fr = 250kHz.

Possible adjustments:
- Increase Lr to 40µH, keep Cr = 100nF → fr = 252kHz ✓
- Keep Lr = 25µH, increase Cr to 160nF → fr = 252kHz ✓

Choice depends on:
- Transformer leakage inductance achievable
- Capacitor voltage rating vs. cost
- Quality factor Q for regulation range

## Quality Factor (Q)

**Target:** Q = 0.3 to 0.5 (per industry practice)

```
Q = √(Lr/Cr) / Rac
where Rac = equivalent AC load resistance reflected to primary
```

**Effect of Q on performance:**
- **Q too low (<0.2):** Excessive frequency variation for regulation, poor efficiency
- **Q too high (>0.8):** Narrow operating range, sensitive to load changes, risk of instability
- **Q = 0.3-0.5:** Good balance - wide regulation range, stable operation, good efficiency

**Rac estimation:**
```
Pout = 120W
Vout = 12V
Iout = 10A
Turns ratio n = 4:1 (48V → 12V)
Rac ≈ 8×n² × (Vout²/Pout) = 8×16 × (144/120) ≈ 154Ω (depends on operating point)
```

Simulation will calculate actual Q across load range.

## Deviations from Reference Designs

### Deviation 1: Integrated Lr (NOT a deviation - standard practice)
- Reference circuits often show discrete Lr for clarity
- Production designs integrate Lr into transformer leakage
- This is the **recommended approach**, not a compromise

### Deviation 2: Resistive current sensing (necessary compromise)
- Reference circuits sometimes show current transformer
- CT not available in JLCPCB catalog
- Shunt + differential amplifier is acceptable alternative
- **Impact:** 0.64W loss vs. 0W with CT (acceptable)
- **Benefit:** Fully assemblable by JLCPCB

### Deviation 3: Component sourcing (assembly risk)
- High-voltage C0G ceramics rare in Basic parts
- **Workaround:** Extended parts, or parallel array of X7R ceramics
- **Impact:** Higher assembly cost or more components
- **Mitigation:** Manual JLCPCB catalog search required before ordering

## Unverified Assumptions

1. **Actual resonant current waveform** - Assumed sinusoidal at 8A RMS
   - Real waveform has harmonics
   - Peak current may be higher than √2 × RMS
   - Simulation will reveal actual peak/RMS ratio

2. **Capacitor ESR at 250kHz** - Not modeled
   - ESR causes power loss Ploss = I²×ESR
   - C0G ceramics have very low ESR (<10mΩ typical)
   - X7R ESR higher, may impact efficiency
   - Needs measurement or detailed vendor data

3. **Inductor DCR and AC resistance** - Placeholder value
   - DCR = DC resistance (easy to measure)
   - AC resistance includes skin effect and proximity effect at 250kHz
   - Rac may be 2-3× DCR at high frequency
   - Impacts loss calculation and Q factor

4. **Transformer integration success** - Leakage inductance control
   - Achieving exact Lr via leakage requires careful winding
   - Tolerance typically ±10-20%
   - May need external inductor for fine tuning
   - Custom transformer vendor capability critical

## Next Steps for Block-Simulator

1. **Optimize Lr and Cr** for fr = 250kHz exactly
2. **Calculate Q** at full load, half load, and no load
3. **Verify frequency range** needed for regulation (should be <2:1 ratio)
4. **Determine peak voltages** across Cr and Lr (for component ratings)
5. **Calculate RMS and peak currents** in all components (for sizing)
6. **Power loss budget:** Rsense + Lr DCR + Cr ESR
7. **Sensitivity analysis:** Effect of component tolerance on fr and Q

## References

- TI SLUP263: "Designing LLC Resonant Half-Bridge Power Converter"
- Infineon AN-4151: "Resonant LLC Converter Operation and Design"
- ON Semi AND8311/D: "LLC Resonant Half-Bridge Converter Design Guideline"
