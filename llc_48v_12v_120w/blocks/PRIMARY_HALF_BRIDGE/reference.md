# PRIMARY_HALF_BRIDGE Reference Circuit

## Source Document
**IR2110/IRS2110 High and Low Side Driver Datasheet**  
International Rectifier (now Infineon Technologies)  
Application Note AN-978: HV Floating MOS-Gate Driver ICs  
Typical half-bridge configuration for 100-500kHz switching

**Reference:** Industry-standard IR2110 half-bridge application circuit (Fig. 10-11 typical implementations)

## Reference Circuit Checklist

### Gate Driver IC (IR2110 or equivalent)
- [ ] VCC (pin 3): +12V to +15V supply for driver (use 12V from aux supply)
- [ ] VDD (pin 9): +5V logic supply for input circuits
- [ ] VSS (pin 13): Ground (COM) connection
- [ ] COM (pin 2): Power ground for low-side driver
- [ ] HIN (pin 10): High-side input (from dead-time logic)
- [ ] LIN (pin 12): Low-side input (from dead-time logic)
- [ ] HO (pin 7): High-side gate driver output → Q1 gate (through Rgate)
- [ ] LO (pin 1): Low-side gate driver output → Q2 gate (through Rgate)
- [ ] VS (pin 5): Floating supply return (connects to Q1 source = switching node)
- [ ] VB (pin 6): Bootstrap supply voltage (VCC + Vdiode above VS)

### Bootstrap Circuit
- [ ] Bootstrap capacitor Cboot: 0.22µF - 1.0µF, 25V ceramic, VB to VS
- [ ] Bootstrap diode Dboot: Fast recovery diode, VCC cathode to VB anode
- [ ] VCC bypass capacitor: 0.1µF ceramic + 10µF electrolytic, VCC to COM

### Gate Drive Resistors
- [ ] Rgate_high (R1): 5-10Ω series resistor, HO to Q1 gate
- [ ] Rgate_low (R2): 5-10Ω series resistor, LO to Q2 gate
- [ ] Rsg_high (R3): 10kΩ pull-down, Q1 gate to source
- [ ] Rsg_low (R4): 10kΩ pull-down, Q2 gate to source

### Power MOSFETs
- [ ] Q1 (high-side): N-channel MOSFET, drain to V_BUS (48V input)
- [ ] Q2 (low-side): N-channel MOSFET, source to GND
- [ ] Switching node: Q1 source connected to Q2 drain (output to resonant tank)

### Optional Snubber (for ringing suppression)
- [ ] Rsnub + Csnub: 10Ω + 1nF across each MOSFET drain-source

## Implementation Checklist - Verification Against block.py

### Gate Driver IC Connections
- [x] VCC (pin 3): +12V supply ← VCC_12V port
- [x] VDD (pin 9): +5V logic supply ← VDD_5V port
- [x] VSS (pin 13): GND
- [x] COM (pin 2): GND (common with VSS)
- [x] HIN (pin 10): ← HI_IN port
- [x] LIN (pin 12): ← LO_IN port
- [x] HO (pin 7): → net_ho → Rgate_high → Q1.G
- [x] LO (pin 1): → net_lo → Rgate_low → Q2.G
- [x] VS (pin 5): → net_vs (switching node, connects to Q1.S and Q2.D and SW_OUT)
- [x] VB (pin 6): ← net_vb from bootstrap circuit

### Bootstrap Circuit
- [x] Cboot (0.47µF 25V X7R): VB (net_vb) to VS (net_vs) - LCSC C15008
- [x] Dboot (Schottky 1N5819): Anode to VCC_12V, Cathode to VB (net_vb)
- [x] Cvcc_ceramic (0.1µF ceramic): VCC_12V to GND, close to IC
- [x] Cvcc_bulk (10µF ceramic/electrolytic): VCC_12V to GND, bulk filtering

### Gate Drive Network
- [x] Rgate_high (5.1Ω): HO (net_ho) → Q1 gate (net_q1_gate) - LCSC C23116
- [x] Rgate_low (5.1Ω): LO (net_lo) → Q2 gate (net_q2_gate) - LCSC C23116
- [x] Rsg_high (10kΩ): Q1 gate (net_q1_gate) → Q1 source (net_vs) - LCSC C98220
- [x] Rsg_low (10kΩ): Q2 gate (net_q2_gate) → Q2 source (GND) - LCSC C98220

### Power Stage
- [x] Q1 high-side: D → V_BUS_48V, G → net_q1_gate, S → net_vs (switching node)
- [x] Q2 low-side: D → net_vs (switching node), G → net_q2_gate, S → GND
- [x] Switching node output: net_vs → SW_OUT port

### Optional Snubber (marked DNF in block.py)
- [x] Rsnub_q1 + Csnub_q1 (10Ω + 1nF C0G 100V): V_BUS_48V → net_snub_q1 → net_vs
- [x] Rsnub_q2 + Csnub_q2 (10Ω + 1nF C0G 100V): net_vs → net_snub_q2 → GND
- [x] Both marked DNF=True (do not fit, populate only if ringing observed)

## Deviations from Reference

### Bootstrap Capacitor Value
- **Reference:** 22µF - 40µF for low frequency (50Hz), 4.7µF - 22µF for high frequency (30-50kHz)
- **Our design:** 0.47µF for 100-500kHz LLC switching
- **Reason:** At 100-500kHz, bootstrap capacitor recharges every 2-10µs. Required charge: Q = Qg_total = 120nC (for IPP80N05S4-02). With 0.47µF, voltage droop = 120nC / 0.47µF = 0.26mV per cycle. 10× margin provides stable operation. Higher values increase recharge current and slow bootstrap rise time.

### Gate Resistor Values
- **Reference:** Often shown as 10Ω - 47Ω for generic MOSFETs
- **Our design:** 5.1Ω
- **Reason:** Fast Si MOSFETs (low Qg, fast switching) at high frequency benefit from lower gate resistance. Trade-off: 5Ω provides reasonable di/dt control without excessive switching losses. For GaN FETs (if available), 2-5Ω is typical.

### VCC Supply Voltage
- **Reference:** 10-20V operating range, typically 15V for IGBTs
- **Our design:** 12V
- **Reason:** Available from auxiliary supply (12V → 5V buck), sufficient for MOSFET gate drive (Vgs = 10-12V), lower than VCC_max to improve reliability.

### Snubber Network
- **Reference:** Not always shown in basic circuits
- **Our design:** Optional 10Ω + 1nF RC snubber across each FET
- **Reason:** LLC converters operate near resonance with high di/dt and dv/dt. Ringing at turn-off can cause false triggering or EMI. Snubber provides critical damping. Values: R = sqrt(L_parasitic / C_parasitic) ≈ 10Ω for TO-220 package, C = 1nF provides ~10MHz pole for damping.

## Component Sizing Calculations

### Bootstrap Capacitor
```
Cboot_min = (Qg_total + I_leakage × t_on_max) / ΔV_allowed
Where:
  Qg_total = 120nC (IPP80N05S4-02 total gate charge at Vgs=10V)
  I_leakage ≈ 100µA (IR2110 high-side quiescent current)
  t_on_max = 2µs (at 500kHz, 100% duty - not realistic but worst case)
  ΔV_allowed = 1V (allows 1V droop on VB without losing gate drive)

Cboot_min = (120nC + 100µA × 2µs) / 1V = (120nC + 200nC) / 1V = 320nF

Selected: 0.47µF (47% margin)
```

### Gate Resistor
```
Rgate affects:
1. Turn-on time: t_on ≈ Rgate × Qg / Vgs ≈ 5Ω × 120nC / 12V = 50ns
2. Peak gate current: I_peak = Vgs / Rgate = 12V / 5Ω = 2.4A (within IR2110 capability)
3. Gate ringing: Higher R provides damping, lower R reduces losses

Selected: 5.1Ω (E24 series, balanced performance)
```

### Source-to-Gate Resistor
```
Rsg provides:
1. Gate discharge path when driver is off or floating
2. Prevents Miller turn-on from dv/dt during opposite FET switching
3. Should not load driver excessively

Typical range: 10kΩ - 100kΩ
Selected: 10kΩ (provides <1µA gate leakage path, doesn't load driver)
```

## Critical Layout Notes (for implementation)

1. **Bootstrap capacitor Cboot**: Mount directly between VB (pin 6) and VS (pin 5) with SHORTEST possible traces
2. **VCC bypass capacitor**: Mount 0.1µF ceramic within 5mm of VCC (pin 3) and COM (pin 2)
3. **Gate resistors**: Mount close to MOSFET gates to minimize inductance
4. **Gate-source resistors**: Connect directly at MOSFET pins (not at driver output)
5. **VS trace**: Keep low inductance - this is the switching node, high di/dt
6. **COM and VSS**: Star ground at a single point to avoid ground loops
7. **Bootstrap diode**: Use fast-recovery or Schottky to ensure quick recharge

## References

- IR2110/IRS2110 Datasheet, International Rectifier
- Application Note AN-978: HV Floating MOS-Gate Driver ICs
- "Using the IR2110 High and Low Side Driver," Tahmid's Electronics Blog
- Industry-standard half-bridge gate driver implementations

---

**Status:** Reference circuit documented. Awaiting Python circuit implementation and line-by-line verification.
