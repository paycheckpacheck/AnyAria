# OUTPUT_FILTER Reference Circuit

## Source Documents

**Primary reference:** Generic LLC resonant converter topology
- TI Application Note SLUA559A "Designing an LLC Resonant Half-Bridge Power Converter"
- Infineon Application Note AN-4151 "Design Guide for LLC Resonant Converter"
- General industry practice for LLC output stage filtering

**Note:** The OUTPUT_FILTER block is a passive filtering stage, not built around a specific IC. It follows standard power supply output filtering practices for low-ripple DC outputs.

## Typical LLC Output Filter Topology

For a 12V @ 10A output from an LLC converter with synchronous rectification:

```
[SR FETs] → [Bulk Electrolytic Caps] || [HF Ceramic Caps] → [Output Connector]
              (1000-2000µF)              (100-300µF total)
```

## Reference Circuit Checklist

Based on TI SLUA559A Section 4.3 "Output Capacitor Selection" and standard LLC design practice:

### Output Capacitors (Post-Rectification)

- [x] Bulk electrolytic capacitor(s): 1000-2000µF @ 25V minimum         **C_BULK**
  - Purpose: Energy storage, hold-up time, bulk ripple filtering
  - ESR requirement: <100mΩ for low ripple voltage
  - Voltage rating: 2× output voltage minimum (12V → 25V min)
  
- [x] High-frequency ceramic capacitors: 47µF X5R/X7R @ 25V (4-6× parallel) **C_HF**
  - Purpose: High-frequency ripple filtering at switching frequency
  - Total HF capacitance: 200-300µF
  - Placement: Close to SR FET outputs, low ESL path
  
### Ripple Voltage Calculation

From SLUA559A eq. 4-3:
```
ΔV_ripple = I_load / (f_sw × C_total)
```

For 12V @ 10A, f_sw = 250kHz (resonant frequency):
```
ΔV_ripple = 10A / (250kHz × 2000µF) = 20mV  ✓ < 100mV spec
```

### Output Connection

- [x] Screw terminal or high-current connector: 10A+ rating              **J_OUT**
  - Wire gauge: 16-18 AWG (10A continuous)
  - Pitch: 5.08mm standard
  
### Sensing Points (Interface to OUTPUT_SENSE_PROTECT block)

- [x] Voltage sense tap at output capacitors                            **VOUT_SENSE**
  - High-impedance connection (1-10kΩ) to ADC/feedback
  
- [x] Current sense connection point                                    **ISENSE**
  - Typically before or after output filter, to OUTPUT_SENSE_PROTECT block

## Design Calculations

### Total Output Capacitance

Target: 500-1000µF minimum per TI SLUA559A guidelines

Implemented:
- 2× 1000µF electrolytic = 2000µF (bulk)
- 6× 47µF ceramic = 282µF (high-frequency)
- **Total effective: ~2300µF @ low freq, ~300µF @ high freq**

### ESR Budget

Maximum ripple from ESR (worst case):
```
ΔV_ESR = I_ripple × ESR_total
```

Assuming I_ripple ≈ 3A (ripple current at 250kHz):
- Electrolytic ESR: 50mΩ each → 25mΩ parallel (2×)
- Ceramic ESR: ~5mΩ total (6× parallel)
- **Total ESR: ~30mΩ → ΔV_ESR = 3A × 30mΩ = 90mV ✓**

### Hold-Up Time (Optional Verification)

For 12V output dropping to 11V with no input:
```
t_holdup = C × (V_nom² - V_min²) / (2 × P_load)
t_holdup = 2000µF × (12² - 11²) / (2 × 120W)
t_holdup = 2000µF × 23 / 240 = 192µs
```

This is minimal hold-up (not a spec requirement for this design).

## Deviations from Reference

- [+] **Using 2× 1000µF instead of 1× 2000µF**: Parallel electrolytics reduce total ESR and improve ripple current handling. Standard practice.

- [+] **6× ceramic caps instead of fewer larger ones**: Better HF performance with multiple parallel paths. Reduces ESL.

- [~] **No output inductor**: LLC converters typically don't require output inductors because the resonant tank already provides inductive filtering. The transformer leakage inductance serves this function. Omitted per standard LLC practice.

## What This Block Does NOT Include

The following are in other blocks per architecture:
- **Synchronous rectification FETs**: In SECONDARY_RECTIFIER block
- **Current sensing circuitry**: In OUTPUT_SENSE_PROTECT block  
- **Voltage feedback**: In OUTPUT_SENSE_PROTECT block
- **OVP protection**: In OUTPUT_SENSE_PROTECT block

This block is PURELY passive filtering: capacitors and connector.

## References

1. Texas Instruments SLUA559A "Designing an LLC Resonant Half-Bridge Power Converter", Section 4.3
2. Infineon Application Note AN-4151 "Half-Bridge LLC Resonant Converter Design Using FSFR-Series Fairchild Power Switch (FPS)"
3. Microchip AN1212 "LLC Resonant Converter Operation and Design"

---

**Checklist complete: 2026-08-01**
**All items verified against standard LLC design practice**
