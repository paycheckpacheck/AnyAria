# AUX_SUPPLY - Design Rationale

## Overview

Three-stage cascaded auxiliary power supply providing 5V, 3.3V, and 1.2V rails from the main 12V LLC converter output.

**Total power budget:** 500mA @ 5V + 300mA @ 3.3V + 100mA @ 1.2V = 2.5W + 1.0W + 0.12W = 3.62W output

## Architecture Decision

**Cascaded topology** (12V→5V→3.3V→1.2V) chosen over independent regulators because:
1. Lower total parts count (3 regulators vs 3+ regulators with input muxing)
2. Simpler layout (no input distribution network)
3. Acceptable efficiency for low-power auxiliary loads
4. Sequential startup provides natural power sequencing

**Trade-off:** Cascaded LDOs have lower efficiency, but at these power levels (< 4W total), absolute power loss is acceptable.

---

## Stage 1: TPS5430 Buck Converter (12V → 5V @ 500mA)

**Part:** TPS5430DDAR (LCSC C9864, Basic part, $0.85)

**Why buck converter instead of LDO:**
- Power dissipation at 500mA: (12V - 5V) × 0.5A = 3.5W
- LDO would require significant heatsink; buck converter keeps dissipation < 0.5W
- Efficiency: ~85-90% vs ~42% for LDO

**Component values:**

| Component | Value | Source | Rationale |
|-----------|-------|--------|-----------|
| L1 | 22µH | Calculated | L = (VIN-VOUT)×(VOUT/VIN)/(ΔI_L×f_SW) = (12-5)×(5/12)/(0.15A×500kHz) ≈ 19µH → 22µH std |
| C_OUT | 47µF + 22µF | Calculated | Minimum 7.5µF for 50mV ripple; 69µF provides 4× margin after ceramic derating |
| R_FB | 10kΩ / 2.43kΩ | Calculated | VOUT = 0.8V × (1 + 10k/2.43k) = 4.11V (TO BE REFINED to exact 5.0V) |
| C_COMP | 10nF | Datasheet | Standard compensation for CCM operation per SLVS555 |

**Output ripple:** < 50mV peak-peak (calculated from ΔI_L / (8 × f_SW × C_OUT))

**Switching frequency:** 500kHz (internal, fixed per TPS5430 spec)

**Thermal:** P_loss ≈ 0.5W @ 85% efficiency, ΔT ≈ 50°C above ambient (acceptable in SOIC-8-EP with thermal pad)

---

## Stage 2: AMS1117-3.3 LDO (5V → 3.3V @ 300mA)

**Part:** AMS1117-3.3 (LCSC C6186, Basic part, $0.20)

**Why LDO here:**
- Low dropout: only (5V - 3.3V) = 1.7V drop
- Power dissipation: 1.7V × 0.3A = 0.51W (acceptable for SOT-223)
- Extremely low noise (important for RP2040 I/O supply)
- Standard, well-characterized part

**Thermal:** θ_JA ≈ 100°C/W for SOT-223 → ΔT ≈ 51°C above ambient (acceptable at 25°C ambient, no heatsink needed)

**Stability:** AMS1117 requires ceramic caps for stability; tantalum caps can cause oscillation. Using X7R ceramics as specified.

---

## Stage 3: WL2808E12-5/TR LDO (3.3V → 1.2V @ 100mA)

**Part:** WL2808E12-5/TR (LCSC C2931310, Extended part, $0.05)

**Output voltage deviation:**
- RP2040 datasheet (RP-008279-DS) specifies DVDD = 1.1V nominal, tolerance 1.08V - 1.32V
- WL2808E12 provides 1.2V fixed output
- **1.2V is within RP2040 spec and centered in the allowed range**
- Using 1.2V because 1.1V fixed LDOs are not readily available in JLCPCB catalog

**Why LDO here:**
- Very low dropout: (3.3V - 1.2V) = 2.1V drop
- Power dissipation: 2.1V × 0.1A = 0.21W (very low)
- Switching regulator at 100mA would be overkill and noisier
- Cost: $0.05 (cheapest solution)

**Thermal:** θ_JA ≈ 200°C/W for SOT-23-5 → ΔT ≈ 42°C above ambient (well within limits)

---

## Power Sequencing

**Natural startup order:** 12V present → 5V ramps up → 3.3V ramps up → 1.2V ramps up

**RP2040 requirements:** No specific sequencing required between 3.3V (IOVDD) and 1.2V (DVDD). Both can ramp simultaneously or in any order per RP-008279-DS section 2.1.4.

**Enable pins:** All regulators enabled by default:
- TPS5430 ENA pulled high via 100kΩ
- AMS1117 always-on (no enable pin)
- WL2808 EN tied to VIN (always enabled)

**Future:** Enable pins accessible if controlled shutdown/sequencing needed.

---

## Figures of Merit

| Parameter | Calculated | Measured | Target |
|-----------|-----------|----------|--------|
| 5V output ripple | < 50mV p-p | TBD | < 100mV |
| 3.3V output ripple | < 10mV p-p | TBD | < 50mV |
| 1.2V output ripple | < 5mV p-p | TBD | < 50mV |
| Total efficiency (12V → all outputs) | ~60% | TBD | > 50% |
| Total power dissipation | ~1.2W | TBD | < 2W |
| 5V line regulation | TBD | TBD | ±2% |
| 5V load regulation | TBD | TBD | ±5% |

---

## What Cannot Be Verified Without Hardware

1. **Actual efficiency under load** - Buck converter efficiency varies with load
2. **Ripple and noise measurements** - Requires oscilloscope
3. **Thermal performance** - Board layout and airflow dependent
4. **Transient response** - Load step response testing needed
5. **EMI/conducted emissions** - Buck converter switching noise
6. **RP2040 actual operating voltage** - Whether 1.2V DVDD is optimal or if 1.1V would be better (within spec but untested)

---

## Deviations from Ideal Design

1. **Cascaded LDOs reduce efficiency:** Independent regulators from 12V would be more efficient but require more parts and board area.

2. **WL2808 outputs 1.2V instead of 1.1V:** RP2040 nominally wants 1.1V, but 1.2V is within spec (1.08-1.32V). 1.1V fixed LDOs not readily available in JLCPCB catalog.

3. **No independent shutdown control:** All regulators powered when 12V is present. Enable pins accessible for future control if needed.

4. **No reverse-polarity protection on 12V input:** Assuming upstream protection in main LLC output stage.

---

## BOM Cost

| Part | LCSC | Type | Unit Price | Qty | Total |
|------|------|------|------------|-----|-------|
| TPS5430DDAR | C9864 | Basic | $0.85 | 1 | $0.85 |
| AMS1117-3.3 | C6186 | Basic | $0.20 | 1 | $0.20 |
| WL2808E12-5/TR | C2931310 | Extended | $0.05 | 1 | $0.05 |
| Passives (10 caps, 5 resistors, 1 inductor) | TBD | Basic | ~$0.50 | - | $0.50 |
| **Total** | | | | | **~$1.60** |

**Assembly cost:** 2 Basic parts + 1 Extended part → minimal Extended part loading fee.

---

## References

1. TPS5430 Datasheet (SLVS555) - Texas Instruments
2. AMS1117 Datasheet - Advanced Monolithic Systems
3. WL2808 Datasheet - Will Semiconductor
4. RP2040 Datasheet (RP-008279-DS) - Raspberry Pi Foundation, Chapter 2 (Power Supplies)
