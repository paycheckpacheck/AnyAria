# LLC Transformer Design Calculations

## Power Requirements
- Output power: 120W
- Efficiency target: 95% → Primary power: 120W / 0.95 = 126.3W
- Operating frequency: 250kHz (resonant frequency)

## Turns Ratio Calculation
- Primary voltage: 48V (square wave, peak-to-peak ~96V)
- Secondary voltage: 12V output
- With center-tap full-wave rectification: Vsec_rms = Vout × sqrt(2) = 12V × 1.414 = 16.97V
- With diode drops / SR losses: Add ~0.5V → Vsec_required ≈ 17.5V RMS
- Turns ratio n = Vpri_rms / Vsec_rms = 48V / 17.5V ≈ 2.74:1
- **Select n = 3:1** (allows some headroom for losses)
- **With center tap: 3:1:1 topology** (primary : secondary_half : secondary_half)

Wait, let me recalculate for LLC operation:
- LLC operates with varying frequency around resonance
- At resonant frequency, gain ≈ 1 (unity gain)
- Vout = Vin × n_effective
- For 48V → 12V: n = 48V / 12V = 4:1
- **With center-tap: 4:2:2 or simplified as 4:1:1 per half**

**Selected turns ratio: 4:1** (primary to each secondary half)

## Core Selection
Power handling: P = Bmax × Ae × f × Ku × J
Where:
- Bmax = 200mT (for N87 ferrite at 250kHz)
- f = 250kHz
- Ku = 0.4 (window utilization)
- J = 4 A/mm² (current density)

Required core product Ae × Aw:
Ae × Aw = (P × 10^6) / (4.44 × f × Bmax × Ku × J)
         = (126 W × 10^6) / (4.44 × 250000 × 0.2 × 0.4 × 4)
         = 126 × 10^6 / 355200
         = 354.7 mm^4

**Core candidates:**
- **ETD29**: Ae = 76 mm², Aw = 77 mm², Ae×Aw = 5852 mm^4 ✓
- **E32**: Ae = 83 mm², Aw = 60 mm², Ae×Aw = 4980 mm^4 ✓
- **PQ32/30**: Ae = 161 mm², Aw = 139 mm², Ae×Aw = 22379 mm^4 ✓ (oversized)

**Select: ETD29 (good fit, common size)**

## Wire Gauge Calculation

Primary current:
- Ipri_rms = P / Vpri = 126W / 48V = 2.63A RMS
- At 4 A/mm²: Awire_pri = 2.63A / 4 = 0.66 mm²
- **Primary wire: AWG 18 (0.82 mm²) or Litz equivalent**

Secondary current:
- Isec_rms = Iout / sqrt(2) = 10A / 1.414 = 7.07A per leg (center-tap)
- At 4 A/mm²: Awire_sec = 7.07A / 4 = 1.77 mm²
- **Secondary wire: AWG 14 (2.08 mm²) or Litz equivalent**

At 250kHz, skin depth δ = 0.13mm → **Litz wire strongly recommended**

## Turns Calculation

Select primary turns Np:
Bmax = (Vpri_pk × 10^6) / (4 × Np × Ae × f)

For Vpri_pk = 48V (square wave, half-bridge):
Np = (48 × 10^6) / (4 × 200mT × 76mm² × 250kHz)
   = 48 × 10^6 / 15200000
   = 3.16 turns

Too few turns! Increase for practical winding:
**Np = 16 turns** (primary)

Check flux density:
Bmax = (48 × 10^6) / (4 × 16 × 76 × 250000) = 158 mT ✓ (safe)

Secondary turns:
Ns = Np / n = 16 / 4 = **4 turns per half** (center-tap: 4T + 4T)

## Magnetizing Inductance (Lm)

Lm = (μ0 × μr × Np² × Ae) / le

For ETD29 with N87:
- μr ≈ 2200 (at 250kHz, low flux)
- Ae = 76 mm² = 76 × 10^-6 m²
- le = 71 mm = 0.071 m

Lm = (4π×10^-7 × 2200 × 16² × 76×10^-6) / 0.071
   = (1.257×10^-6 × 2200 × 256 × 76×10^-6) / 0.071
   = 54.2 × 10^-6 / 0.071
   = **763 µH** (without gap)

For target Lm = 120 µH, need air gap:
Gap length: lg = (μ0 × Np² × Ae / Lm) - le/μr
lg = (4π×10^-7 × 256 × 76×10^-6 / 120×10^-6) - 0.071/2200
   = 0.000204 - 0.000032
   = **0.172 mm gap** (172 µm)

**Practical: 0.2mm gap → Lm ≈ 110 µH**

## Leakage Inductance (Llk)

Target: 20-30 µH
Achieved by:
- Interleaving primary and secondary (reduces coupling)
- OR separate primary/secondary layers with small spacing
- Typical ETD29 with good coupling: Llk ≈ 2-5% of Lm
- With Lm = 110 µH: Natural Llk ≈ 2.2 - 5.5 µH

**For 25 µH leakage:** Deliberate poor coupling required, OR external series inductor.
**Decision: Use external Lr = 25 µH in series** (allows precise control)

## Final Transformer Specification

| Parameter | Value | Notes |
|-----------|-------|-------|
| Turns ratio | 16:4:4 | 4:1:1 (primary : sec_half : sec_half) |
| Primary turns | 16T | Litz wire AWG 18 equivalent |
| Secondary turns | 4T + 4T | Center-tapped, Litz wire AWG 14 equiv |
| Core | ETD29 | N87 or N97 ferrite |
| Air gap | 0.2mm | Central leg gap |
| Magnetizing inductance | 110 µH | Measured at 48V, 250kHz |
| Leakage inductance | <10 µH | Minimize in transformer design |
| External resonant inductor | 25 µH | Series with primary |
| Isolation voltage | 1500V | Basic insulation |
| Power rating | 150W | Continuous at 250kHz |
| Operating frequency | 100-500kHz | Variable for LLC control |
| Temperature rise | <40°C | At full load, natural convection |

## Winding Instructions

**Layer structure (minimize leakage):**
1. Primary layer 1: 8 turns (half of primary)
2. Insulation: 3 layers Kapton tape
3. Secondary: 4T + 4T center-tap (bifilar if possible)
4. Insulation: 3 layers Kapton tape  
5. Primary layer 2: 8 turns (second half, series with layer 1)

**OR use interleaved (better coupling, lower Llk):**
1. Primary 1: 8T
2. Insulation
3. Secondary: 4T + 4T
4. Insulation
5. Primary 2: 8T

**Wire specification:**
- Primary: Litz wire, 0.1mm × 80 strands or equivalent (250kHz optimized)
- Secondary: Litz wire, 0.1mm × 200 strands or equivalent

## Manufacturer Recommendations

**Off-the-shelf candidates** (verify availability):
- Coilcraft: Custom design service
- Würth Elektronik: 750343373 series (check turns ratio match)
- Bourns: Custom magnetics division
- Pulse Electronics: PA4000 series (check specs)

**Custom winder:**
- Provide this specification to magnetics house
- Request sample + test report (Lm, Llk, isolation, temp rise)
- Lead time: 2-4 weeks for prototype
- Cost estimate: $15-30 per unit (qty 10-100)

## Verification Required

- [ ] Measure Lm at 1kHz and 250kHz (should be ~110 µH ±10%)
- [ ] Measure Llk (should be <10 µH)
- [ ] Hipot test 2000V DC for 1 second (1500V rated)
- [ ] Thermal test at 150W, 250kHz (ΔT < 40°C)
- [ ] Turn ratio verification with LCR meter

