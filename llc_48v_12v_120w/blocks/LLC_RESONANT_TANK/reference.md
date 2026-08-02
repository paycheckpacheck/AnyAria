# LLC Resonant Tank Reference Design

## Reference Source

**No single IC datasheet reference** - This block implements passive resonant tank components.

Primary references:
1. **Texas Instruments**: "Designing LLC Resonant Half-Bridge Power Converter" (SLUP263)
2. **Infineon**: "Resonant LLC Converter Operation and Design" (AN-4151)
3. **ON Semiconductor**: "LLC Resonant Half-Bridge Converter Design Guideline" (AND8311/D)

## Standard LLC Resonant Tank Topology

```
Half-Bridge Out --[Cr]--+--[Lr]-- Transformer Primary Dot
                         |
                     [Current Sense]
                         |
                    Transformer Primary Non-Dot
```

### Component Checklist

**Resonant Capacitor (Cr):**
- [x] Series with transformer primary (blocks DC)
- [x] Voltage rating > peak half-bridge voltage (150V for 48V input)
- [x] Low ESR (C0G/NP0 or film preferred)
- [x] Value: 47-150nF typical for 250kHz resonant frequency
- [~] DEVIATION: JLCPCB Basic parts search found no suitable high-voltage C0G ceramics
      - Extended part or parallel array of X7R ceramics may be required
      - Film capacitor ideal but not found in automated search

**Resonant Inductor (Lr):**
- [x] Series with resonant capacitor
- [x] Current rating > peak resonant current (8A RMS minimum)
- [x] Value: 20-40µH typical for 250kHz resonant frequency
- [~] INTEGRATION APPROACH: Use transformer leakage inductance (standard practice)
      - Discrete inductor NOT required in most LLC designs
      - Transformer designed for specific leakage inductance
      - Saves cost, space, and eliminates additional loss
- [~] If discrete inductor needed: Not found in JLCPCB Basic search
      - Extended part or external sourcing required

**Current Sense (Rsense):**
- [x] Low-value shunt resistor in resonant path
- [x] Differential voltage sensing for control loop
- [x] Value: 5-20mΩ typical (trade-off: signal vs. loss)
- [x] Power rating: > I²R at peak current (1W minimum)
- [~] DEVIATION: Current transformer would be ideal for AC sensing
      - Not available in JLCPCB catalog
      - Shunt resistor acceptable for current-mode control
      - Requires differential amplifier with good CMRR

## Design Equations (from TI SLUP263)

**Resonant Frequency:**
```
fr = 1 / (2π√(Lr × Cr))
```

**Quality Factor:**
```
Q = √(Lr/Cr) / Rac
where Rac = equivalent AC load resistance reflected to primary
```

**Recommended Q range: 0.3 to 0.5**
- Q too low: excessive frequency variation for regulation
- Q too high: narrow operating range, poor transient response

## Deviations from Ideal Reference Circuit

1. **Lr integrated with transformer** - Standard practice, not a deviation
   - Reduces component count
   - Improves efficiency (one magnetic component vs. two)
   - Requires careful transformer design

2. **Resistive current sensing** - Necessary compromise
   - Current transformer not in JLCPCB catalog
   - Shunt + diff-amp has adequate accuracy for control
   - 10mΩ @ 8A = 0.64W loss (acceptable)

3. **Capacitor sourcing** - ASSEMBLY RISK
   - High-voltage C0G ceramics rare in Basic parts
   - May require Extended part or manual sourcing
   - X7R acceptable if voltage derating applied

## Next Steps

1. **Simulation** (block-simulator) will determine:
   - Exact Lr and Cr values for fr = 250kHz
   - Quality factor Q and regulation range
   - Peak voltages and currents
   - Power dissipation in Rsense

2. **Transformer specification** (LLC_TRANSFORMER block) must include:
   - Designed leakage inductance Lr = [value from simulation]
   - Magnetizing inductance Lm ~ 4-6× Lr (typical)
   - Turns ratio for 48V → 12V conversion

3. **Manual part selection** required for Cr and Rsense from JLCPCB Extended catalog
