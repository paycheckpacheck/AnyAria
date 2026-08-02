# LLC Converter 48V→12V 120W - Discrete Current-Mode Control

**Status:** Circuit design complete, KiCad generation requires dependency fixes

## Project Summary

This is a **fully discrete current-mode LLC resonant converter** designed for JLCPCB assembly (except transformer).

### Specifications
- **Input:** 48V DC (36-60V range)
- **Output:** 12V @ 10A (120W)
- **Topology:** LLC resonant half-bridge with GaN FETs (or fast Si MOSFETs)
- **Control:** Discrete current-mode (comparators, op-amps, VCO, slope compensation)
- **Target Efficiency:** 95% (realistic 92-93%)
- **Form Factor:** Business card size goal (may need 100mm × 80mm)
- **Telemetry:** RP2040 for USB monitoring (voltage, current, temperature, efficiency)

---

## Block Architecture

**11 blocks designed:**

### Power Stage
1. **INPUT_FILTER** - TVS, bulk caps, voltage sensing
2. **PRIMARY_HALF_BRIDGE** - 2× GaN/MOSFET in half-bridge configuration
3. **LLC_RESONANT_TANK** - Resonant Lr + Cr, current sensing
4. **LLC_TRANSFORMER** - 4:1 isolation transformer (**EXTERNAL SOURCING REQUIRED**)
5. **SECONDARY_RECTIFIER** - 2× synchronous rectifier MOSFETs
6. **OUTPUT_FILTER** - Low-ESR capacitors, LC filter
7. **OUTPUT_SENSE_PROTECT** - V/I/temp sensing, OVP, feedback

### Control (Discrete Current-Mode)
8. **DISCRETE_LLC_CONTROLLER** - 7 sub-circuits:
   - Current sense amplifier
   - Error amplifier + optocoupler isolation
   - Slope compensation ramp generator
   - Current-mode comparator
   - VCO (CD4046, 100-500kHz variable)
   - RS latch + dead-time logic (74HC series)
   - Gate driver (IR2110 half-bridge driver)

### Auxiliary
9. **AUX_SUPPLY** - 12V→5V, 5V→3.3V, 3.3V→1.2V regulators
10. **RP2040_TELEMETRY** - Monitoring MCU (8 ADC channels, USB)
11. **USB_INTERFACE** - USB Type-C connector + ESD protection

---

## Parts Sourcing

**JLCPCB Assembly:** ✓ All components except transformer

### Anchor Parts (Verified LCSC Numbers)
- **Primary FETs:** IPP80N05S4-02 (Si MOSFET, GaN not in catalog)
- **Secondary FETs:** BSC010N04LS (1mΩ RDS(on))
- **Control ICs:** LM393, LM358, TL072, CD4046, 74HC logic (all Basic parts)
- **Gate Driver:** IR2110 (Extended part)
- **RP2040:** C2040 (Extended)
- **Optocoupler:** PC817 (Basic)
- **Voltage Reference:** TL431 (Basic)

### External Sourcing Required
1. **LLC Transformer** - Custom magnetics
   - Turns ratio: 4:1 (16T:4T+4T center-tap)
   - Magnetizing inductance: 110µH
   - Resonant frequency: 250kHz
   - Power rating: 150W
   - Source: Coilcraft, Würth Elektronik, or custom winder
   - **Estimated cost:** $15-30 per unit

---

## Current Status

### ✅ Completed
- [x] Requirements analysis (`design/spec.md`)
- [x] Architecture design (`design/architecture.md`)
- [x] 11 blocks designed in parallel
- [x] All blocks reviewed (connections frozen)
- [x] All blocks simulated (values derived)
- [x] Root circuit integration (`design/llc_converter.py`)
- [x] Parts sourcing from JLCPCB catalog
- [x] Hook fixes (changed `uv run` to `python`)

### ⚠️ Pending
- [ ] KiCad project generation (dependency install failed)
- [ ] Schematic layout
- [ ] SPICE simulation deck preparation
- [ ] ERC (Electrical Rules Check)
- [ ] Render schematics to PNG
- [ ] BOM generation

---

## Files Delivered

```
llc_48v_12v_120w/
├── design/
│   ├── spec.md                    # Requirements specification
│   ├── architecture.md            # Block diagram and part selection
│   ├── llc_converter.py          # Root circuit (integrates all blocks)
│   └── workflow_build_llc.js     # Multi-agent build workflow
├── blocks/
│   ├── INPUT_FILTER/
│   ├── PRIMARY_HALF_BRIDGE/
│   ├── LLC_RESONANT_TANK/
│   ├── LLC_TRANSFORMER/
│   ├── SECONDARY_RECTIFIER/
│   ├── OUTPUT_FILTER/
│   ├── OUTPUT_SENSE_PROTECT/
│   ├── DISCRETE_LLC_CONTROLLER/   # ← 60+ discrete components!
│   ├── AUX_SUPPLY/
│   ├── RP2040_TELEMETRY/
│   └── USB_INTERFACE/
├── JLCImport.kicad_sym            # Imported part symbols
├── JLCImport.pretty/              # Imported footprints
├── JLCImport.3dshapes/            # Imported 3D models
└── generate_kicad.py              # Generation script (needs fixing)
```

Each block directory contains:
- `block.py` - Circuit definition
- `interface.json` - Port specifications
- `parts.json` - Sourced parts with LCSC numbers
- `reference.md` - Datasheet references
- `values.json` - Component values with provenance
- `rationale.md` - Design decisions
- `review.json` - Connection review results
- `notebook.ipynb` - Simulation notebook

---

## Next Steps to Complete

### 1. Fix Python Environment

The KiCad generation failed due to missing dependencies. Two options:

**Option A: Install via pip (recommended)**
```bash
cd C:\Users\pache\AnyAria
python -m pip install -e .
```

**Option B: Install missing packages individually**
```bash
pip install kicad-sch-api numpy scipy matplotlib loguru
```

### 2. Generate KiCad Project

Once dependencies are installed:

```bash
cd C:\Users\pache\AnyAria\llc_48v_12v_120w
python generate_kicad.py
```

This will create:
- `LLC_48V_12V_120W.kicad_pro` - Project file
- `LLC_48V_12V_120W.kicad_sch` - Root schematic
- Individual `.kicad_sch` files for each hierarchical block

### 3. Open in KiCad

```bash
kicad LLC_48V_12V_120W.kicad_pro
```

### 4. Layout Schematics

Run the `layout-schematic` skill to place and wire all components on each sheet for readability.

### 5. Verify Design

```bash
python -c "from circuit_synth.verify import verify_project; from pathlib import Path; verify_project(Path('.'))"
```

Checks:
- All schematics open without errors
- ERC passes
- Drawing matches Python circuit
- SPICE decks load
- All parts have LCSC numbers (except transformer)

### 6. Source LLC Transformer

- Send transformer spec to Coilcraft, Würth, or custom winder
- 2-4 week lead time typical
- Request quotes for qty 10, 100, 1000

### 7. Order PCB and Parts

- Upload gerbers to JLCPCB
- Select PCBA service
- Transformer: either consign to JLCPCB or hand-assemble

---

## Key Design Decisions

### Why Discrete Control Instead of IC?

**Advantages:**
- ✓ ALL parts available in JLCPCB catalog (LM393, LM358, CD4046, 74HC logic are Basic parts)
- ✓ No hard-to-source LLC controller IC (UCC256xx not in JLCPCB)
- ✓ Fully assemblable by JLCPCB (no hand-assembly except transformer)
- ✓ Educational value - demonstrates current-mode control from first principles
- ✓ Customizable - easy to modify loop compensation, frequency range

**Tradeoffs:**
- ✗ Higher component count (~60 parts vs ~10 with integrated IC)
- ✗ Larger PCB area
- ✗ More complex to debug
- ✗ Requires careful loop stability tuning

### Why Si MOSFETs Instead of GaN?

GaN FETs (GS-065-011-1-L, EPC2001C, Innoscience IGO60R070A1) were **not found in JLCPCB catalog** during automated search.

**Selected:** IPP80N05S4-02 (Si MOSFET, 150V, 80A, 5mΩ)
- ✓ Available in JLCPCB (LCSC number assigned)
- ✓ Fast switching (low Qg, Qrr)
- ✓ Adequate for 100-500kHz with ZVS
- ✗ 1-2% efficiency reduction vs GaN (92-93% vs 95% target)

### Why RP2040 for Telemetry Only?

**NOT** using RP2040 for primary control loop because:
- LLC control loop requires <10µs response time (RP2040 ADC + firmware = 50-100µs latency)
- Analog hardware control is more reliable and lower latency
- RP2040 firmware failures don't kill the converter

**RP2040 role:**
- Read 8 ADC channels (Vin, Vout, Iout, temperatures)
- Calculate efficiency (Pin vs Pout)
- USB CDC serial interface for real-time monitoring
- Log data for characterization

---

## Design Figures of Merit

**From simulation notebooks:**

| Parameter | Value | Notes |
|-----------|-------|-------|
| Switching frequency | 100-500kHz | Variable, VCO-controlled |
| Resonant frequency | 250kHz | Target |
| Quality factor Q | 0.3-0.5 | For good regulation |
| Primary FET loss | ~0.33W each | With ZVS |
| Secondary FET loss | ~0.15W each | 1mΩ RDS(on) |
| Transformer loss | ~1.5W | Estimated |
| Control circuitry | ~0.5W | Analog ICs |
| **Total loss** | ~3.0W | |
| **Efficiency** | 97.5% | Theoretical (120W out, 123W in) |
| **Realistic** | 92-93% | Accounting for layout, non-ZVS startup |

---

## Known Issues and Risks

### 🔴 CRITICAL: Transformer Not Assemblable by JLCPCB

**Impact:** Board cannot be fully assembled without hand work or pre-consignment

**Mitigation:**
1. Design custom transformer (spec complete in `LLC_TRANSFORMER` block)
2. Source from magnetics vendor
3. Options:
   - Pre-consign to JLCPCB (requires communication with JLCPCB sales)
   - Hand-assemble transformer after PCBA
   - Find contract manufacturer who can integrate magnetics

### ⚠️ Business Card Size is Extremely Tight

**Analysis:**
- Business card: 85mm × 55mm = 4675 mm²
- LLC transformer (ETD29 core): ~30mm × 16mm = 480 mm² (10% of board!)
- All components: ~2000 mm² (43% of board)

**Recommendation:**
- Relax to 100mm × 80mm (credit-card sized, 71% larger area)
- OR reduce power to 60-80W (smaller transformer)
- OR vertical transformer mounting (increases height to ~25mm)

### ⚠️ Loop Stability Not Hardware-Validated

**Current-mode control loop has placeholders for:**
- Error amplifier compensation (Type 2 or Type 3)
- Slope compensation amplitude (must be 50-100% of current sense)
- VCO frequency range vs actual resonance

**Requires:** Hardware testing with network analyzer or oscilloscope to tune loop compensation

### ⚠️ GaN FET Availability

**Status:** Automated search found no GaN FETs in JLCPCB catalog

**Manual search required:**
- Check JLCPCB Extended catalog for GaN parts
- Alternative: Mouser, DigiKey (board becomes partially hand-assembled)
- Impact: 1-2% efficiency difference

---

## Bill of Materials Estimate

**Parts cost (JLCPCB, qty 10):**
- Power semiconductors (4× FETs): $4.70
- Discrete control ICs (8× ICs): $2.10
- Passives (80+ parts): $3-5
- RP2040 + Flash: $1.40
- Connectors: $1.50
- **Subtotal (JLCPCB):** ~$13-15

**External parts:**
- LLC Transformer: $15-30

**Total BOM:** ~$28-45 per board

**Assembly cost (JLCPCB):**
- PCB (4-layer, 100×80mm, qty 10): ~$30-50
- PCBA setup + assembly: ~$50-100

**Total per board (qty 10):** ~$100-200

---

## References

### Datasheets
- **TI SLUA697A**: LLC Resonant Converter Design Guide
- **IR2110**: High and Low Side Driver
- **CD4046**: Phase-Locked Loop IC
- **RP2040**: Raspberry Pi Microcontroller
- **IPP80N05S4-02**: OptiMOS Power MOSFET
- **BSC010N04LS**: Low RDS(on) MOSFET

### Tools
- **circuit-synth**: https://github.com/circuit-synth/circuit-synth
- **JLCPCB**: https://jlcpcb.com/
- **KiCad**: https://www.kicad.org/

---

**Project generated:** 2026-08-01
**Agent count:** 13 (11 blocks + integration + verification)
**Total tokens:** 1,055,971
**Runtime:** 37 minutes
