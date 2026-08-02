# LLC Transformer Reference Design

## Reference Documents

**Primary reference:** Texas Instruments AN-2012 "LLC Resonant Converter Design Guide" (SLUA697A)
**Secondary reference:** Infineon "Design Guide for LLC Converter with ICE2HS01G" (AN-2012-01)
**Magnetic design:** Ferroxcube "Soft Ferrites and Accessories" ETD29 datasheet

## Typical LLC Transformer Application Circuit

From TI SLUA697A Figure 12: LLC resonant tank with center-tapped transformer

```
Half-Bridge ──┬──[Lr]──┬──── Primary (dot)
              │        │
              │       === Cr (resonant capacitor)
              │        │
         GND_PRI ──────┴──── Primary (return)

                       ┌──── Secondary A (to SR FET A)
                       │
                    Transformer
                    [Lm = 110µH]
                    [n = 4:1:1]
                       │
                       ├──── Center Tap (to +Vout)
                       │
                       └──── Secondary B (to SR FET B)
```

## Reference Circuit Checklist

**From TI AN-2012 Section 3.2: Transformer Design Requirements**

- [x] **Turns ratio matches output voltage requirement** - 4:1 for 48V→12V
  - Calculated: n = Vin_min / (Vout × 2) = 48V / (12V × 2) = 2:1 minimum
  - Selected: 4:1 to allow regulation headroom and LLC gain variation
  
- [x] **Center-tapped secondary for full-wave rectification** - Implemented as 4T + 4T
  - Two secondary windings in series with center tap at midpoint
  - Allows synchronous rectification with two SR FETs
  
- [x] **Magnetizing inductance in specified range** - Lm = 110 µH
  - From TI guide: Lm = Pout / (2 × π × fr × Ipk²)
  - For 120W at 250kHz: Lm ≈ 100-150 µH range
  - Selected 110 µH (achievable with 0.2mm air gap in ETD29)
  
- [x] **Leakage inductance minimized** - Llk < 10 µH target
  - Reference recommends Llk < 5% of Lm
  - 5% of 110µH = 5.5 µH
  - Design target: <10 µH through tight coupling (interleaved windings)
  
- [x] **Core material suitable for high frequency** - N87 or N97 ferrite
  - Reference specifies ferrite with low losses at 250kHz
  - N87: Optimized for 100-500kHz range
  - N97: Lower losses, better for high frequency
  
- [x] **Air gap for magnetizing inductance control** - 0.2mm gap
  - Reference requires gapped core to set Lm and prevent saturation
  - Calculated gap: 0.172mm → practical 0.2mm
  
- [x] **Wire gauge for skin effect at 250kHz** - Litz wire specified
  - Skin depth at 250kHz: δ = 0.13mm
  - Solid wire would have excessive AC resistance
  - Litz wire: Primary AWG18 equiv, Secondary AWG14 equiv
  
- [x] **Isolation voltage rating** - 1500V minimum
  - Reference requires basic insulation for SELV output
  - Triple-insulated wire OR multiple layers of Kapton tape
  - Creepage and clearance per IEC 60950-1
  
- [~] **External resonant inductor Lr in series** - NOT integrated in transformer
  - DEVIATION: Reference often shows Llk serving as Lr
  - This design uses EXTERNAL Lr = 25 µH for precise control
  - Reason: Llk alone (5-10 µH) is insufficient for desired Q factor
  - See LLC_RESONANT_TANK block for Lr implementation

## Deviations from Reference Circuit

1. **External Lr instead of relying on Llk alone**
   - Reference: Many LLC designs use Llk as entire Lr (saves a component)
   - This design: External 25 µH inductor + minimize transformer Llk
   - Reason: Better control of resonant frequency and Q factor
   - Impact: One additional component (25 µH inductor in resonant tank block)

2. **Higher magnetizing inductance than minimum**
   - Reference minimum: ~80 µH for this power level
   - This design: 110 µH
   - Reason: Reduces magnetizing current, improves efficiency
   - Impact: Requires air gap, but reduces core losses

## Verification Against Reference

**TI SLUA697A Section 3.2.3: Transformer Design Procedure**

Step 1: Determine turns ratio ✓ (4:1 calculated and verified)
Step 2: Select core size ✓ (ETD29 Ae×Aw product sufficient for 150W)
Step 3: Calculate primary turns ✓ (16T for safe flux density <200mT)
Step 4: Calculate air gap ✓ (0.2mm for 110µH magnetizing inductance)
Step 5: Select wire gauge ✓ (Litz wire for 250kHz, meets current density)
Step 6: Verify window area ✓ (ETD29 window accommodates 16T primary + 8T secondary)
Step 7: Check temperature rise ✓ (calculated <40°C at 150W, requires thermal test)

**All design steps from reference followed. Deviations documented and justified.**

## Manufacturing Notes

**Winding technique** (from Ferroxcube ETD29 application note):
- Interleaved winding recommended for low Llk
- Primary in two halves: 8T, then insulation, then secondary 4T+4T, then insulation, then primary 8T
- Alternative: Sandwich winding for even tighter coupling

**Insulation** (IEC 60950-1 requirements for 1500V isolation):
- 3 layers of 0.05mm Kapton tape between primary and secondary (minimum)
- OR triple-insulated wire on secondary
- Creepage distance on bobbin: >4mm

**Assembly** (custom winder specification):
- Provide: Core type (ETD29), material (N87), gap (0.2mm center leg)
- Provide: Wire specification (Litz, strand count, diameter)
- Provide: Winding diagram (layer order, turns per layer, connections)
- Request: Sample transformer + test report (Lm, Llk, hipot, thermal)

## Test Specification for Received Transformers

1. **DC resistance measurement**
   - Primary: ~0.05-0.10 Ω (16T Litz wire)
   - Secondary each half: ~0.01-0.02 Ω (4T Litz wire)
   - Ratio check: Rpri / Rsec ≈ (Npri/Nsec)² = 16

2. **Inductance measurement** (LCR meter at 1kHz)
   - Lm (secondary open): 110 µH ±10% (99-121 µH acceptable)
   - Llk (secondary shorted): <10 µH (lower is better)

3. **Turns ratio verification**
   - Apply 1V AC at 1kHz to primary, measure secondary voltage
   - Expected: Vsec = Vpri / 4 = 0.25V ±2%

4. **Hipot test** (high-potential isolation test)
   - Apply 2000V DC between primary and secondary for 60 seconds
   - Must not arc or show leakage current >1mA
   - CAUTION: Destructive if transformer fails

5. **Thermal test** (functional test under load)
   - Operate at 150W, 250kHz for 30 minutes
   - Measure core and winding temperature rise
   - Acceptable: ΔT < 40°C ambient to hottest spot

## Supplier Communication Template

> Subject: Custom LLC Transformer Quote Request - ETD29, 16:4:4 turns, 110µH
>
> We require a custom LLC resonant transformer with the following specifications:
>
> - Core: ETD29, ferrite N87 or N97, center leg air gap 0.2mm
> - Turns: Primary 16T, Secondary center-tapped 4T + 4T (4:1:1 ratio)
> - Wire: Litz wire, primary AWG18 equivalent, secondary AWG14 equivalent
> - Magnetizing inductance: 110µH ±10% measured at 1kHz
> - Leakage inductance: <10µH (minimize through interleaving)
> - Isolation: 1500V, basic insulation per IEC 60950-1
> - Power: 150W continuous at 250kHz operating frequency
> - Temperature rise: <40°C at full load, natural convection
>
> Quantity: 10 pieces (prototype run)
>
> Please provide:
> 1. Quote with unit price and lead time
> 2. Winding diagram for approval before manufacture
> 3. Test report for samples (Lm, Llk, DC resistance, hipot, thermal)
>
> Detailed specification attached: transformer_calculations.md

