# INPUT_FILTER Reference Circuit

## Reference Documents

**Primary Reference:** Generic 48V DC input filter design for LLC converters
- Common industry practice for LLC resonant converters
- Input filtering requirements per power supply design guidelines

**Related:** 
- Texas Instruments: "LLC Resonant Converter Design" (SLUP263)
- ON Semiconductor: "LLC Resonant Half-Bridge Converter Design Guideline" (AN-4151)

## Typical Application Circuit

For a 48V input LLC converter (120W, 36-60V range):

```
VIN+ ----[J1-1 Screw Terminal]----+----[D1 TVS 58V]----+----[C1,C2 Bulk 100µF]----+----[C3,C4 Ceramic 10µF]----+---- VIN (to LLC)
                                   |                    |                           |                            |
                                   |                    |                           |                            +----[C5,C6 Ceramic 1µF]---- (local HF bypass)
                                   |                    |                           |
                                   |                    |                           +----[R1 47k]----+----[C7 100nF]----VSENSE (to RP2040 ADC)
                                   |                    |                                             |
VIN- ----[J1-2 Screw Terminal]----+--------------------+-----------------------------+---------------[R2 3.3k]----+---- GND
```

## Checklist

### Protection
- [ ] TVS diode across input (58V breakdown for 48V nominal)
  - SMBJ58A (C19195335): 58V standoff, 93.6V clamp @ 6.5A
  - Unidirectional, SMB package
  - Protects against transients up to 600W (10/1000µs pulse)

### Bulk Energy Storage
- [ ] 2× 100µF electrolytic capacitors (200µF total)
  - CS1J101M-CRG10 (C116430): 100µF 63V SMD electrolytic
  - Low ESR for ripple current handling
  - Parallel connection for doubled capacitance and halved ESR
  - Input energy storage: E = 0.5 × C × V² = 0.5 × 200µF × 48² = 230mJ

### High-Frequency Bypass
- [ ] 2× 10µF ceramic capacitors (1206)
  - CC1206KRX7R0BB473 (C107206): 47µF (actual, derated at 48V ~10-15µF)
  - X7R dielectric, 100V rating
  - Placed close to half-bridge input for switching noise filtering

- [ ] 2× 1µF ceramic capacitors (0805)  
  - CC0805KRX7R0BB222 (C107136): 2.2µF (actual, derated at 48V ~1µF)
  - X7R dielectric, 100V rating
  - Local HF bypass at switching frequency (~100-500kHz)

### Voltage Sensing
- [ ] Resistive divider for RP2040 ADC
  - R1: 47kΩ (high side) - 0603WAF4702T5E (C25819)
  - R2: 3.3kΩ (low side) - 0603WAF3301T5E (C22978)
  - Ratio: 48V × (3.3k / (47k + 3.3k)) = 3.14V (safe for 3.3V ADC max)
  - 1% tolerance for accuracy
  - Current draw: 48V / 50.3kΩ = 0.95mA (negligible)

- [ ] C7: 100nF filter capacitor on ADC input
  - CC0603KRX7R9BB104 (C14663): 100nF 50V X7R 0603
  - Forms RC filter with R2: τ = 3.3kΩ × 100nF = 330µs
  - Cutoff frequency: f_c = 1/(2π × 330µs) = 482Hz

### Input Connector
- [ ] 2-pin screw terminal, 5mm pitch, 15A rated
  - WJ127-5.0-02P-14-00A (C3703)
  - Green, through-hole mounting
  - Wire gauge: 14-26 AWG
  - More than adequate for 120W @ 48V = 2.5A

## Design Calculations

### Input Capacitance Sizing
For LLC converter with 100-500kHz switching:
- Bulk capacitance: 200µF (holdup time, input ripple)
- Ceramic HF bypass: 20µF + 2µF (switching noise filtering)

**Holdup time** (if input drops briefly):
- t_holdup = C × (V_max² - V_min²) / (2 × P_out)
- t_holdup = 200µF × (60² - 36²) / (2 × 120W)
- t_holdup = 200µF × 2304 / 240 = 1.92ms
- (Minimal holdup - LLC doesn't require it, just bulk storage)

### TVS Clamping Analysis
- SMBJ58A clamps at 93.6V @ 6.5A (600W pulse)
- For 48V nominal, this provides adequate margin
- Surge current capability: 6.5A >> 2.5A nominal

### Voltage Divider Accuracy
- R1 = 47kΩ ± 1%, R2 = 3.3kΩ ± 1%
- Worst case ratio: (3.3k × 1.01) / ((47k × 0.99) + (3.3k × 1.01)) = 0.0666
- Best case ratio: (3.3k × 0.99) / ((47k × 1.01) + (3.3k × 0.99)) = 0.0650
- At 48V input: 3.11V to 3.20V (well within 3.3V ADC range)
- At 60V max input: 3.90V to 4.00V **(EXCEEDS 3.3V ADC MAX!)**

**DESIGN NOTE:** Voltage divider is sized for 48V nominal. At 60V max input, ADC will saturate (but not damage, as it has clamping diodes). For full 36-60V range monitoring, either:
1. Use 68kΩ : 3.3kΩ divider (60V → 2.78V)
2. Add clamping diode at ADC input
3. Accept saturation at high input (telemetry only, not critical)

Current design: **Accept saturation at >55V input** (telemetry, not safety-critical)

## Deviations from Typical Reference

**None** - This is a standard input filter topology for LLC converters.

## Parts Cost Summary

| Part | Qty | Unit Price | Total | Type |
|------|-----|------------|-------|------|
| TVS Diode SMBJ58A | 1 | $0.0267 | $0.03 | Extended |
| 100µF 63V Electrolytic | 2 | $0.0964 | $0.19 | Extended |
| 10µF 100V Ceramic 1206 | 2 | $0.0393 | $0.08 | Extended |
| 1µF 100V Ceramic 0805 | 2 | $0.0202 | $0.04 | Extended |
| 47kΩ 0603 1% | 1 | $0.0070 | $0.01 | Basic |
| 3.3kΩ 0603 1% | 1 | $0.0086 | $0.01 | Basic |
| 100nF 0603 X7R | 1 | $0.0241 | $0.02 | Basic |
| Screw Terminal 2P 5mm | 1 | $0.1520 | $0.15 | Extended |
| **TOTAL** | **11** | | **$0.53** | |

**Note:** 5 Extended parts, 3 Basic parts. Consider if bulk cap or HF ceramics can be substituted with Basic parts to reduce assembly cost.
