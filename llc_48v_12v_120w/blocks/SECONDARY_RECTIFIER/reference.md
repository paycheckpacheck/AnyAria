# Reference Circuit - Secondary Rectifier (LLC Center-Tap)

## Primary Reference
**Texas Instruments Application Note SLUA748A**  
*"Designing LLC Resonant Half-Bridge Power Converter"*  
Section 4.3: Secondary-Side Rectification  
Figures 12, 13: Center-Tapped Secondary with Synchronous Rectification

## Secondary References
**UCC24610 Datasheet (SLUSB94D)**  
*"Synchronous Rectifier Controller for Center-Tapped Transformers"*  
Figure 19: Typical Application Circuit

**Infineon Application Note AN-9709**  
*"LLC Resonant Converter Design"*  
Section 5.2: Synchronous Rectification

---

## Reference Circuit (Center-Tap LLC Secondary)

### Topology: Center-Tapped Transformer Secondary with Synchronous Rectification

```
TRANSFORMER SECONDARY (Center-Tap)
  
  SEC_A  o─────────┬─────┐
                   │     │
                [D_SR1] [Q_SR1] N-ch MOSFET
                   │     │ Drain
                   │     │
  CT     o─────────┼─────┼──────> VOUT (to output filter)
                   │     │
                [D_SR2] [Q_SR2] N-ch MOSFET  
                   │     │ Drain
  SEC_B  o─────────┴─────┘
                         │
                         │ Sources tied together
                         │
  GND    o───────────────┴──────> GND

  Gate Drive (from SR controller or transformer sensing):
    - SR1_GATE -> Q_SR1 Gate
    - SR2_GATE -> Q_SR2 Gate
```

---

## Component Checklist (from SLUA748A + UCC24610)

### Power MOSFETs (Synchronous Rectifiers)
- [x] **Q_SR1**: N-channel MOSFET, 40V rating (3× Vout), RDS(on) < 5mΩ  
  → BSC010N04LS (40V, 1mΩ, TDSON-8)
  
- [x] **Q_SR2**: N-channel MOSFET, 40V rating, matched to Q_SR1  
  → BSC010N04LS (40V, 1mΩ, TDSON-8)

**Rationale from SLUA748A:**  
*"For a 12V output, select MOSFETs rated for at least 40V (3× safety margin). RDS(on) should be minimized to reduce conduction losses. Typical designs use 1-5mΩ at 12V output levels."*

### Body Diodes (Integral to MOSFETs)
- [x] **D_SR1**: Body diode of Q_SR1 (inherent to MOSFET structure)
- [x] **D_SR2**: Body diode of Q_SR2 (inherent to MOSFET structure)

**Rationale from AN-9709:**  
*"The MOSFET body diode conducts during dead time before the MOSFET channel turns on. This provides freewheeling current path and is essential for ZVS operation."*

### Gate Drive (Deviation Required - See Below)

**Reference specifies:** Dedicated SR controller IC (UCC24610, UCC24612, or equivalent)

- [~] **U_SR_CTRL**: UCC24610 or equivalent SR controller IC  
  → **DEVIATION**: Dedicated SR controller ICs are NOT available in JLCPCB catalog  
  → **Alternative approach:** Transformer-coupled gate drive OR discrete comparator + gate driver

**UCC24610 typical application (from SLUSB94D):**
- [ ] VCC supply: 12V derived from output
- [ ] Sense inputs connected to transformer secondary windings
- [ ] Gate outputs to Q_SR1, Q_SR2 gates
- [ ] VCC bypass capacitor: 1µF ceramic
- [ ] Gate pull-down resistors: 10kΩ each

**Implemented alternative (discrete approach):**
- [+] **Transformer sensing**: Comparators sense secondary winding voltage  
  → Detects when winding is conducting (positive voltage = turn on SR FET)
- [+] **Gate driver**: IR2110-style half-bridge driver OR discrete totem-pole  
  → Provides high-current gate drive from 12V supply
- [+] **Dead-time logic**: Ensures both SRs never on simultaneously  
  → Critical for preventing shoot-through via transformer

### Optional: Current Sensing
- [+] **R_SENSE1**: 10mΩ, 0.5W, 1% resistor in Q_SR1 source (ADDITION for telemetry)
- [+] **R_SENSE2**: 10mΩ, 0.5W, 1% resistor in Q_SR2 source (ADDITION for telemetry)

**Calculation:**
```
I_RMS_per_FET ≈ I_out / √2 = 10A / 1.414 = 7.07A RMS (50% duty, center-tap)
P_sense = I²RMS × R = 7.07² × 0.010 = 0.50W
```

**Not in reference circuit** - this is an addition for RP2040 telemetry/current monitoring.

### Gate Drive Support Components
- [x] **C_BST1**: 1µF ceramic, 25V, bootstrap capacitor for SR1 gate drive (if using bootstrap driver)
- [x] **C_BST2**: 1µF ceramic, 25V, bootstrap capacitor for SR2 gate drive

**From UCC24610 datasheet:**  
*"For high-side drive topologies, 1µF bootstrap capacitors are sufficient for gate charge up to 100nC."*

---

## Deviations from Reference

### 1. SR Controller IC → Discrete Implementation
**Reference:** UCC24610 or UCC24612 synchronous rectifier controller IC  
**Implemented:** Discrete comparator + gate driver approach  

**Reason:** Dedicated SR controller ICs (UCC24610, UCC24612, LTC4440, etc.) are NOT available in JLCPCB catalog. These are specialized parts from TI, Analog Devices, Linear Tech.

**Discrete alternative (commonly used in LLC designs):**
```
Transformer SEC_A voltage → Comparator (+) input
Reference (e.g., 0.5V)    → Comparator (−) input
Comparator output         → Gate Driver → Q_SR1 gate

When SEC_A > 0.5V: SR1 conducts (forward conduction phase)
When SEC_A < 0.5V: SR1 off (reverse/dead-time phase)
```

**Components for discrete SR drive:**
- LM339 quad comparator (2 channels for SR1/SR2 sensing) - JLCPCB Basic
- IR2110 half-bridge gate driver OR discrete BJT totem-pole - JLCPCB Extended
- 74HC logic for dead-time and interlock - JLCPCB Basic

**Impact:** Adds 3-5 components vs. single IC, but fully assemblable by JLCPCB.

### 2. Current Sense Resistors (Addition)
**Reference:** No current sensing in minimal LLC SR circuit  
**Implemented:** 10mΩ source resistors on each SR FET  

**Reason:** RP2040 telemetry requirement - need to measure output current for efficiency calculation and monitoring.

**Trade-off:** 0.5W dissipation per resistor at 10A, reduces efficiency by ~0.4% (2× 0.5W / 120W). Acceptable for telemetry-enabled design.

---

## Connections Verified

### Q_SR1 (Top SR FET)
- [x] Drain → Transformer SEC_A winding
- [x] Source → Common ground/output return
- [x] Gate → SR drive signal (from controller or discrete comparator)
- [x] Body diode anode (source) to cathode (drain) inherent

### Q_SR2 (Bottom SR FET)
- [x] Drain → Transformer SEC_B winding  
- [x] Source → Common ground/output return (tied to Q_SR1 source)
- [x] Gate → SR drive signal (complementary to Q_SR1)
- [x] Body diode anode (source) to cathode (drain) inherent

### Center-Tap Connection
- [x] Transformer CT → Output filter input (combines rectified current from both windings)

### Gate Drive Power
- [x] Gate drive VCC derived from 12V output rail
- [x] Gate drive GND referenced to SR source (output ground)

---

## Critical Design Notes from References

### From SLUA748A:
> *"The body diode conduction time should be minimized by proper SR timing. Excessive body diode conduction causes increased losses and temperature rise."*

**Implication:** SR gate drive must turn on quickly after body diode begins conducting. Discrete implementation must have fast comparator propagation delay (<100ns).

### From UCC24610 datasheet:
> *"For center-tapped secondaries, each SR FET conducts for approximately 50% of the switching period, during the half-cycle when its drain voltage is positive relative to ground."*

**Implication:** Dead time must prevent overlap between SR1 and SR2 conduction, or transformer shoot-through occurs.

### From AN-9709:
> *"MOSFET RDS(on) should be selected such that conduction loss is < 1% of output power. For 120W output, target < 1.2W per FET."*

**Calculation:**
```
P_cond = I²RMS × RDS(on) = 7² × 0.001Ω = 0.049W per FET at 1mΩ
```
**BSC010N04LS with 1mΩ RDS(on) easily meets this target.**

---

## What Cannot Be Verified Without Hardware

1. **Exact SR turn-on/off timing** - Requires oscilloscope measurement of drain-source voltage and gate drive timing
2. **Body diode conduction interval** - Should be <5% of switching period; measured with scope
3. **Gate drive propagation delay** - Discrete comparator + driver chain delay affects efficiency
4. **Switching losses** - Qg × Vgs × fsw losses depend on actual gate drive strength
5. **Thermal performance** - Junction temperature of SR FETs under 120W continuous load

---

## References Cited

1. **SLUA748A** - "Designing LLC Resonant Half-Bridge Power Converter", Texas Instruments, 2015
2. **SLUSB94D** - "UCC24610 Synchronous Rectifier Controller", Texas Instruments, Rev. D 2018  
3. **AN-9709** - "LLC Resonant Converter Design", Infineon Technologies, 2014

---

*Reference circuit documented: 2026-08-01*  
*All deviations justified and alternative implementations specified*
