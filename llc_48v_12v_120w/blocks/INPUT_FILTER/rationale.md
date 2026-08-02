# INPUT_FILTER - Design Rationale

## Purpose

Provides input filtering, overvoltage protection, and voltage sensing for the 48V LLC converter input.

## Design Decisions

### TVS Diode Selection (SMBJ58A)
- **58V breakdown** chosen for 48V nominal (1.2× safety margin)
- **93.6V clamp @ 6.5A** protects downstream circuitry from transients
- **600W pulse rating** (10/1000µs) adequate for typical input surges
- **Unidirectional** - no negative voltage expected on 48V DC input
- **Trade-off:** Extended part ($0.0267), but TVS protection is essential

### Bulk Capacitance Strategy
- **2× 100µF electrolytic** instead of 1× 220µF+:
  - Better availability in JLCPCB catalog
  - Parallel connection halves ESR (better ripple current handling)
  - Total 200µF provides 230mJ energy storage @ 48V
  - SMD package (D10×L10.5mm) vs through-hole for compact layout
- **Trade-off:** Extended part ($0.10 each), but low-ESR electrolytics rare in Basic

### Ceramic Bypass Strategy
- **2× 10µF 1206 (100V rated)**:
  - Actual capacitance ~10-15µF at 48V DC bias (X7R derating)
  - 100V rating for derating headroom and transient margin
  - 1206 package for higher capacitance density than 0805
- **2× 1µF 0805 (100V rated)**:
  - Local HF bypass at switching frequency (~100-500kHz)
  - Lower ESL than larger packages for better HF performance
  - Parallel with 10µF for broadband filtering
- **Total ceramic: ~22µF effective** after derating
- **Trade-off:** All Extended parts, but 100V ceramics not available in Basic

### Voltage Sensing Divider
- **47kΩ : 3.3kΩ ratio** for 48V → 3.14V:
  - 3.14V safely below 3.3V ADC max (5% margin)
  - At 36V min: 2.36V (good ADC resolution)
  - At 60V max: 3.93V **(exceeds 3.3V - ADC will saturate)**
  - **Decision:** Accept saturation above ~50V. Telemetry only, not safety-critical.
  - **Alternative considered:** 68kΩ : 3.3kΩ would give 2.78V @ 60V, but loses resolution at low end.
- **1% tolerance resistors** for ±2% accuracy (sufficient for monitoring)
- **0.95mA quiescent current** (negligible vs 2.5A load)
- **Trade-off:** Basic parts (cheap), but limited ADC range at high input

### ADC Filter
- **100nF ceramic + 3.3kΩ** forms RC filter:
  - Cutoff: 482Hz (filters 100kHz+ switching noise)
  - Doesn't attenuate DC or slow transients
  - Prevents ADC aliasing from high-frequency noise
- **Trade-off:** Basic part, standard practice

### Input Connector
- **WJ127-5.0-02P screw terminal**:
  - 15A rating (6× margin for 2.5A nominal)
  - 5mm pitch (standard, good wire gauge range 14-26 AWG)
  - Through-hole for mechanical strength
  - Green color (power convention)
- **Trade-off:** Extended part ($0.15), but robust power connector needed

## Calculated Figures

### Input Impedance
At 100kHz switching frequency:
- Bulk electrolytics: Z ≈ 1/(2π × 100kHz × 200µF) = 8mΩ
- Ceramic total (~22µF): Z ≈ 72mΩ
- **Parallel combination dominates ripple filtering**

### Ripple Current Capability
- Each 100µF electrolytic rated for ~1A RMS ripple (typical for size)
- Parallel: 2A RMS total
- LLC resonant converter input ripple: ~0.5-1A RMS @ 100kHz (depends on resonant tank Q)
- **Margin: ~2× adequate**

### Thermal Dissipation
- TVS: 0W quiescent, designed for transient pulses
- Voltage divider: P = V²/R = 48² / 50.3kΩ = 46mW (negligible)
- **No thermal issues**

## Deviations from Reference

**None.** Standard LLC input filter topology.

## What Is NOT Verified

1. **Actual ripple current** - Depends on LLC resonant tank design (Q factor, switching frequency)
2. **EMI performance** - Common-mode noise, conducted emissions not analyzed
3. **Transient response** - TVS clamping under real surge conditions (requires hardware test)
4. **Holdup time** - 1.92ms calculated, but not required for LLC operation
5. **ADC saturation behavior** - Input >50V will saturate ADC, but RP2040 clamping diodes prevent damage
6. **Layout parasitics** - Bulk cap placement distance from half-bridge, HF ceramic effectiveness

## Cost vs Performance Trade-offs

**Total block cost: $0.53** (5 Extended parts, 3 Basic parts)

**Could reduce cost by:**
- Using lower-voltage ceramics (50V) → May find Basic parts, but less margin
- Single 220µF electrolytic → May save $0.10, but worse ESR/ripple
- Omitting TVS → Saves $0.03, but eliminates transient protection (NOT RECOMMENDED)

**Current choice optimizes:**
- Reliability (TVS protection, adequate margins)
- Availability (all parts in stock, JLCPCB assemblable)
- Performance (low ESR, good HF filtering)

## Block Interface Summary

**Inputs:**
- `+48V` power symbol (from screw terminal)
- `GND` power symbol

**Outputs:**
- `VIN_FILT`: Filtered 48V to LLC resonant tank
- `VSENSE`: Voltage sense to RP2040 ADC (3.14V @ 48V input)

**Figures of Merit:**
- Input capacitance (bulk): 200µF
- Input capacitance (ceramic): ~22µF effective
- TVS clamp: 93.6V @ 6.5A
- Sense ratio: 0.0655 (48V → 3.14V)
- Sense accuracy: ±2%
