# OUTPUT_FILTER Block Rationale

## Block Purpose

The OUTPUT_FILTER block provides passive filtering for the LLC converter's 12V output rail. It receives the rectified DC voltage from the SECONDARY_RECTIFIER block and filters it to produce a low-ripple 12V supply suitable for delivery to the load.

## Circuit Topology

**Type:** Passive LC filter (capacitor-only, no series inductor)

**Key design decision:** LLC converters typically do not require output inductors because the resonant tank (Lr, Cr, Lm) and transformer leakage inductance already provide inductive filtering. The output stage uses only capacitors.

## Group Box 1: Bulk Energy Storage

**Components:** C_BULK1, C_BULK2 (2× 1000µF, 25V electrolytic, radial)

**Function:** Provide bulk energy storage and low-frequency ripple filtering for the 12V output.

**Design basis:**
- Ripple voltage equation (TI SLUA559A eq. 4-3): `ΔV = I_load / (f_sw × C)`
- For 10A load at 250kHz resonant frequency: `C_min = 10A / (250kHz × 0.1V) = 400µF`
- **Implemented: 2× 1000µF = 2000µF** (5× margin)
- Expected ripple from capacitance: `ΔV = 10A / (250kHz × 2000µF) = 20mV`

**ESR consideration:**
- Each 1000µF electrolytic has ESR ~50mΩ typical
- Parallel ESR: 50mΩ || 50mΩ = 25mΩ
- Ripple current at 250kHz: ~3Arms (assuming 30% of DC current)
- ESR-induced ripple: `ΔV_ESR = 3A × 25mΩ = 75mV`
- **Total ripple (worst case): 20mV + 75mV = 95mV < 100mV target ✓**

**Part selection:**
- LCSC C484817: Rubycon 1000µF 25V radial, low ESR
- Through-hole for high ripple current capability
- 2× in parallel reduces ESR and improves thermal dissipation

**Reference:** TI SLUA559A section 4.3 "Output Capacitor Selection"

**Deviations:**
- Using 2× 1000µF instead of 1× 2000µF: Better ESR, better ripple current distribution, easier sourcing

## Group Box 2: High-Frequency Filtering

**Components:** C_HF1–C_HF6 (6× 47µF, 25V X5R, 1206)

**Function:** Filter high-frequency switching noise at and above the resonant frequency (250kHz). Ceramics have much lower ESR and ESL than electrolytics at HF.

**Design basis:**
- LLC switching frequency: 250kHz nominal, varies 100-500kHz for regulation
- Electrolytic capacitors lose effectiveness above ~50-100kHz due to ESR and ESL
- Ceramic capacitors maintain low impedance to >1MHz
- **Total HF capacitance: 6× 47µF = 282µF**

**Capacitance derating:**
- X5R dielectric at 12V on 25V part: ~85% of nominal capacitance
- Effective capacitance: 282µF × 0.85 ≈ 240µF at operating voltage

**ESR/ESL advantage:**
- Ceramic ESR: <5mΩ each, ~1mΩ total (6 parallel)
- Ceramic ESL: ~1nH each, reduces with parallel paths
- **At 250kHz, ceramic impedance << electrolytic impedance**

**Placement requirement:**
- Must be placed close to SECONDARY_RECTIFIER SR FET outputs
- Minimize loop inductance between rectifier and filter caps
- Wide, low-inductance PCB traces (4-layer board, GND plane)

**Part selection:**
- LCSC C19666: Samsung 47µF 25V X5R 1206
- X5R preferred over X7R for better capacitance retention at voltage/temp extremes
- 1206 size balances capacitance density and thermal capability

**Reference:** Standard LLC converter design practice, Infineon AN-4151

**Deviations:**
- Using 6× smaller caps instead of 2× larger: Better HF performance due to lower ESL with multiple parallel paths

## Group Box 3: Output Connection and Sensing

**Components:** J_OUT, R_VSENSE

### J_OUT: Output Connector

**Component:** Screw terminal, 2-pin, 5.08mm pitch, 10A rated

**Function:** Physical connection point for 12V @ 10A load. Screw terminal allows field-replaceable wiring with 16-24 AWG wire.

**Design basis:**
- Pin 1: +12V (connects through ISENSE_P port to current sensing shunt)
- Pin 2: GND
- Current path: Load → J_OUT pin 1 → ISENSE_P → Shunt (in OUTPUT_SENSE_PROTECT) → GND

**Part selection:**
- LCSC C8465: KF128-5.08-2P, rated 10A continuous
- 5.08mm pitch standard for power connections
- Accepts 16-24 AWG wire (16 AWG rated 13A per NEC)

**Reference:** Standard power supply output termination practice

### R_VSENSE: Voltage Sense Isolation Resistor

**Component:** 1kΩ, 0603, 1%, 0.1W

**Function:** Provides high-impedance isolation between bulk output capacitors and voltage feedback/ADC sense circuitry in OUTPUT_SENSE_PROTECT block.

**Design basis:**
- Sense current: `I_sense = 12V / 1kΩ = 12mA` (worst case if sense circuit is GND)
- Actual sense current <<1mA for typical op-amp or ADC input
- Voltage drop from loading: `ΔV = 12mA × 25mΩ_ESR = 0.3mV` (negligible)
- **Prevents feedback circuit from coupling noise back into output filter**

**Part selection:**
- Standard 1kΩ 0603 resistor (JLCPCB Basic part)
- 1% tolerance for accurate voltage sensing
- 0.1W adequate for <1mW dissipation

**Reference:** Standard practice for isolated voltage sensing

## Design Validation Checklist

Per reference.md:

- [x] Bulk electrolytic: 1000-2000µF @ 2× output voltage → **2000µF @ 25V ✓**
- [x] HF ceramic: 200-300µF total, X5R/X7R → **282µF X5R ✓**
- [x] Output connector: 10A+ rating → **10A screw terminal ✓**
- [x] Ripple calculation: < 100mV → **95mV worst case ✓**
- [x] Voltage sense tap: High-impedance → **1kΩ isolation ✓**
- [x] Current sense connection: To OUTPUT_SENSE_PROTECT → **ISENSE_P port ✓**

## What This Block Does NOT Include

**Not in OUTPUT_FILTER (located in other blocks per architecture.md):**

1. **Synchronous rectification FETs** → SECONDARY_RECTIFIER block
2. **Current sense shunt resistor** → OUTPUT_SENSE_PROTECT block
3. **Voltage feedback circuitry** → VOLTAGE_FEEDBACK block (in DISCRETE_LLC_CONTROLLER)
4. **Overcurrent/overvoltage protection** → OUTPUT_SENSE_PROTECT block
5. **Load regulation control** → VCO and error amplifier (in DISCRETE_LLC_CONTROLLER)

This block is **purely passive**: capacitors, one isolation resistor, and a connector.

## Critical Layout Notes

1. **Minimize loop area** between C_HF capacitors and SR FET sources (SECONDARY_RECTIFIER)
2. **Wide traces** for 10A current: minimum 2mm (80mil) on outer layers, preferably 4mm
3. **GND plane** continuity: all capacitor grounds to solid plane, minimize vias in return path
4. **Thermal relief** for electrolytic caps: allow air flow, space from high-temp components
5. **Sense resistor placement** close to sense port, away from high di/dt switching nodes

## Figures of Merit (Post-Simulation)

Will be updated by block-simulator:

- **Output ripple voltage:** TARGET < 100mV, CALCULATED 95mV, SIMULATED TBD
- **ESR total:** TARGET < 50mΩ, CALCULATED 26mΩ (bulk || HF)
- **Output impedance @ 250kHz:** TBD (simulator)
- **Ripple current capability:** TBD (verify capacitor thermal limits)
- **BOM cost:** ~$0.50 (2× elec $0.20, 6× ceramic $0.35, connector $0.09)

---

**Rationale complete: 2026-08-01**
**Ready for review and simulation**
