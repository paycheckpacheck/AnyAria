# LLC Transformer Design Rationale

## Isolation and Voltage Transformation

**From:** TI AN-2012 "LLC Resonant Converter Design Guide" (SLUA697A), Section 3.2

The LLC isolation transformer provides galvanic isolation between the 48V primary side and the 12V secondary side, while stepping down the voltage by a 4:1 ratio. The center-tapped secondary topology enables full-wave rectification with two synchronous rectifier MOSFETs, minimizing conduction losses compared to a bridge rectifier.

**Turns ratio selection (4:1):** Calculated from input/output voltage ratio. With 48V primary and 12V output, the ideal ratio is 4:1. This allows the LLC to operate near unity gain (Vout/Vin ≈ n) at resonant frequency, providing optimal efficiency. The LLC controller varies frequency above and below resonance to regulate output voltage under load variations.

**Center-tap topology:** Two 4-turn secondary windings in series with center tap at midpoint. This configuration requires only two SR FETs (one per half-cycle) instead of four in a bridge, reducing conduction losses and simplifying the SR driver. The center tap connects directly to the +12V output rail.

---

## Magnetizing Inductance and Resonant Tank Design

**Lm = 110 µH:** The magnetizing inductance is a critical parameter in LLC design, as it forms part of the resonant tank along with external Lr (25 µH) and Cr (resonant capacitor in LLC_RESONANT_TANK block).

**Design calculation:**
- LLC resonant tank ratio: k = Lr / Lm, typically 0.2-0.3 for good regulation range
- With Lr = 25 µH and k = 0.23: Lm = 25µH / 0.23 = 109 µH ≈ 110 µH
- Higher Lm reduces magnetizing current, improving efficiency
- Lower Lm would require larger external Lr or resonant capacitor

**Air gap requirement:** Without an air gap, the ETD29 N87 core would have Lm ≈ 760 µH (too high). A 0.2mm center-leg gap reduces effective permeability and sets Lm to the target 110 µH. The gap also prevents core saturation under transient conditions.

---

## Core Selection: ETD29

**From:** Ferroxcube "Soft Ferrites and Accessories" ETD29 datasheet

**Core product calculation:** Ae × Aw determines power handling capability.
- Required: (P × 10^6) / (4.44 × f × Bmax × Ku × J) = 354.7 mm^4
- ETD29: Ae × Aw = 5852 mm^4 → **16× margin** (excellent)

**Why ETD29:**
1. **Size:** Compact footprint (~30mm × 16mm) fits on credit-card-sized board
2. **Power capability:** 150W easily within core thermal limits
3. **Availability:** Standard size, readily available from Ferroxcube, TDK, EPCOS
4. **Assembly:** Through-hole mounting, compatible with PCBA + hand-assembly workflow

**Material selection (N87 or N97):**
- N87: Optimized for 100-500kHz, lower cost, widely available
- N97: Lower core losses at 250kHz, higher cost
- Either material is suitable; N87 is default, N97 is upgrade for 1-2% efficiency gain

---

## Primary Winding: 16 Turns

**Flux density constraint:** Bmax < 300mT for N87 ferrite to avoid saturation.

**Calculation:**
```
Bmax = (Vin_pk × 10^6) / (4 × Np × Ae × f)
     = (48V × 10^6) / (4 × 16 × 76mm² × 250kHz)
     = 158 mT
```

**Result:** 158 mT is well below 200 mT conservative limit (300 mT absolute max). This provides **21% margin** to saturation, important for LLC operation where input voltage may vary 36-60V.

**Minimum turns:** With fewer turns (e.g., 12T), flux would be 211 mT at 48V and 263 mT at 60V (too close to saturation). With more turns (e.g., 20T), wire gauge increases and window utilization becomes problematic.

**16 turns is optimal balance:** Safe flux density, manageable wire gauge, fits in ETD29 window.

---

## Secondary Winding: 4T + 4T Center-Tap

**Turns calculation:**
```
Ns = Np / n = 16T / 4 = 4T per half
```

**Center-tap implementation:**
- Two separate 4-turn windings OR one 8-turn winding with center tap exposed
- Each 4-turn section operates during alternate half-cycles
- Center tap is always at +12V output potential
- Winding ends (SEC_A, SEC_B) swing between 0V and +12V (approximately)

**Why integer turns matter:** Fractional turns (e.g., 3.5T) are impractical in transformer winding. The 4:1 ratio yields clean integer turns on both primary (16T) and secondary (4T), simplifying manufacture and ensuring accurate voltage transformation.

---

## Leakage Inductance: Minimize to <10 µH

**Deviation from typical LLC design:** Many LLC converters rely on transformer leakage inductance (Llk) to provide part or all of the resonant inductance Lr. This design deliberately **minimizes** Llk and uses an external 25 µH inductor as Lr.

**Reasons:**
1. **Precision:** External inductor Lr has tighter tolerance (±5%) than Llk (±20%)
2. **Tuning:** Lr can be selected/adjusted independently of transformer design
3. **Reproducibility:** Llk varies transformer-to-transformer; external Lr is consistent
4. **Optimal Q factor:** Target Llk <10 µH + Lr 25 µH = 35 µH total, sets Q = 0.4 (ideal for regulation)

**How to minimize Llk:**
- **Interleaved winding:** Primary in two layers with secondary sandwiched between
- **Tight coupling:** Minimize spacing between primary and secondary
- **Short winding length:** Use full bobbin width to reduce turns per layer

**Target: Llk < 5% of Lm = 5.5 µH.** Achieving <10 µH is realistic with good winding technique.

---

## Wire Specification: Litz Wire for 250 kHz

**Skin effect at 250 kHz:** Skin depth δ = 66 / √f = 66 / √250000 = 0.13 mm

Solid copper wire experiences severe skin effect at this frequency, concentrating current in outer 0.13mm layer. For AWG 18 wire (1.02mm diameter), only 25% of cross-section is effective → 4× increase in AC resistance.

**Litz wire solution:**
- **Primary:** 0.1mm diameter strands × 80 strands = 0.62 mm² effective area (AWG 18 equivalent)
- **Secondary:** 0.1mm diameter strands × 200 strands = 1.57 mm² effective area (AWG 14 equivalent)

Each 0.1mm strand is smaller than skin depth (0.13mm), so full cross-section is utilized. Strands are twisted to average out magnetic field variation across the bundle.

**Impact:** Litz wire reduces AC resistance by 3-4× compared to solid wire at 250 kHz, directly improving efficiency by 1-2% and reducing winding hot spots.

**Cost tradeoff:** Litz wire costs 2-3× more than solid magnet wire, but at prototype quantities (10-100 units) the price difference is <$5/transformer. For 120W at 95% efficiency, 1% improvement saves 1.2W dissipation → well worth the cost.

---

## Isolation: 1500V Rating

**From:** IEC 60950-1 (now superseded by IEC 62368-1) basic insulation requirements

48V input is classified as Safety Extra-Low Voltage (SELV) if properly isolated. The 12V output must be isolated to at least 1500V to meet basic insulation requirements.

**Implementation:**
1. **Wire insulation:** Triple-insulated wire (3 layers of enamel + 1 layer polyester) OR standard magnet wire with tape barriers
2. **Layer insulation:** 3 layers of 0.05mm Kapton polyimide tape between primary and secondary (total 0.15mm)
3. **Creepage distance:** >4mm across bobbin surface (per IEC 60950-1 Table 2K)
4. **Clearance (through air):** >3mm between primary and secondary pins

**Verification:** Hipot test at 2000V DC for 60 seconds (133% of rating). Production transformers must pass this test with <1mA leakage current.

---

## Power and Thermal Rating

**Power throughput:** 150W continuous (120W output + 6W losses in transformer)

**Loss breakdown:**
- **Core loss:** ~1.5W at 158mT, 250kHz (from Ferroxcube loss curves for N87)
- **Copper loss (primary):** Ipri_rms² × Rac = 2.63² × 0.08Ω ≈ 0.55W
- **Copper loss (secondary):** Isec_rms² × Rac = 7.07² × 0.02Ω ≈ 1.0W (both halves)
- **Total:** ~3W dissipated in transformer

**Thermal resistance:** ETD29 core with natural convection: Rth ≈ 15°C/W
**Temperature rise:** ΔT = P × Rth = 3W × 15°C/W = **45°C**

This is close to the 40°C target. Improvements:
- Forced air cooling (small fan) → Rth = 8°C/W → ΔT = 24°C
- Better wire (lower Rac) → reduce copper loss by 0.5W → ΔT = 37°C
- Heatsinking bobbin to copper pour on PCB → Rth = 12°C/W → ΔT = 36°C

**Specification: <40°C rise is achievable** with good PCB thermal design (copper pour under transformer, vias to inner layers).

---

## External Sourcing Strategy

**Why not JLCPCB:** LLC transformers are specialized components requiring:
1. Custom turns ratio (4:1:1 center-tap)
2. Precise magnetizing inductance (110 µH ±10%)
3. Controlled leakage inductance (<10 µH)
4. High-frequency wire (Litz)
5. Isolation certification (1500V hipot test)

JLCPCB catalog focuses on standard transformers (audio, switching power supply, signal isolation) with fixed turns ratios and no LLC-specific parameters.

**Sourcing options:**

**Option 1: Coilcraft Custom Design Service**
- Submit specification (this document)
- 2-4 week lead time for prototype samples
- Cost: $20-30/unit for qty 10-100
- Includes test report and isolation certification
- **Best for production** (reliability, documentation)

**Option 2: Würth Elektronik Semi-Custom**
- Check 750343373 series for close match
- May require turns ratio compromise (e.g., accept 3:1 instead of 4:1)
- Faster lead time (1-2 weeks)
- Lower cost: $12-18/unit
- **Best for prototyping** if specs align

**Option 3: Local Custom Winder**
- Provide bobbin, core, wire, winding diagram
- 1-week lead time for samples
- Cost: $15-25/unit depending on labor rates
- No formal test report (requires in-house verification)
- **Best for rapid iteration** during development

**Recommendation for this project:**
Start with **Option 3** for first prototypes (fast turnaround, allows design changes). Once design is frozen, switch to **Option 1** (Coilcraft) for production run (documented, certified, reliable).

---

## Assembly Impact

**CRITICAL:** This transformer is the **only component** in the LLC converter that cannot be assembled by JLCPCB.

**Assembly workflow:**
1. JLCPCB assembles all components **except** T1 (transformer)
2. User receives boards with transformer footprint empty (through-hole pads)
3. **Hand-solder transformer** to board OR **consign transformer to JLCPCB**

**Consignment to JLCPCB:**
- Ship transformers to JLCPCB warehouse in advance
- Provide LCSC part number placeholder + consignment tracking info
- JLCPCB treats as "customer-provided component"
- Added cost: ~$0.50/board consignment fee + shipping

**Hand-assembly:**
- Transformer has 5 pins (2 primary, 3 secondary), through-hole
- Soldering time: ~2 minutes per board
- Requires soldering iron + solder (standard equipment)
- **Simplest option for <10 boards**

**Impact on project timeline:**
- JLCPCB PCBA: 5-7 days
- Transformer custom winding: 1-4 weeks (parallel)
- Hand-assembly: 30 minutes for 10 boards
- **Total: 1-4 weeks** (transformer lead time is critical path)

---

## What Is Not Verified

The following cannot be fully verified until hardware testing:

1. **Actual Lm and Llk values:** Depend on winding technique, cannot be simulated exactly
2. **Isolation voltage:** Requires physical hipot test
3. **Temperature rise:** Depends on PCB thermal design, airflow, enclosure
4. **EMI coupling:** Primary-to-secondary capacitance affects common-mode noise
5. **Acoustic noise:** Magnetostriction at 250 kHz may be audible (whistling)
6. **Long-term reliability:** Insulation aging, thermal cycling, humidity exposure

**All of these require physical transformer samples and testing.**

---

## Deviations from Standard LLC Practice

1. **External Lr instead of using Llk**
   - Standard: Rely on transformer leakage as entire resonant inductance
   - This design: Minimize Llk, use external 25 µH inductor
   - Justification: Better precision and tunability

2. **Higher Lm (110 µH) than minimum**
   - Standard: Use minimum Lm to reduce core size
   - This design: 110 µH for lower magnetizing current
   - Justification: Prioritize efficiency over size

3. **Litz wire specification**
   - Standard: Solid wire acceptable for <200 kHz
   - This design: Litz required even at 250 kHz
   - Justification: 1-2% efficiency gain worth the cost

**All deviations are documented and justified.** Reference circuits from TI and Infineon were followed for core design methodology, with conscious optimizations for this specific application (120W, 250 kHz, efficiency priority).

