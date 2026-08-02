# PRIMARY_HALF_BRIDGE Rationale

## Block Purpose

The PRIMARY_HALF_BRIDGE converts complementary low-voltage gate drive signals (HI_IN, LO_IN) from the discrete LLC controller into high-current, level-shifted gate drive for two high-voltage N-channel power MOSFETs in half-bridge configuration. The switching node (SW_OUT) generates a 0V-to-48V square wave at 100-500kHz to drive the LLC resonant tank.

## Reference Circuit

Based on IR2110/IRS2110 high-side/low-side gate driver datasheet (International Rectifier, now Infineon) typical half-bridge application circuit and Application Note AN-978: HV Floating MOS-Gate Driver ICs.

## Group 1: Gate Driver IC (U1 - IR2110 or equivalent)

**Purpose:** Provides level-shifted, high-current gate drive for both high-side and low-side MOSFETs. Bootstrap circuit enables floating high-side driver operation up to 500V offset.

**Key features:**
- High-side driver floats with switching node (VS pin)
- Bootstrap capacitor provides VB supply when VS is high
- Low-side driver referenced to COM (ground)
- Logic-level inputs (VDD = 5V) control high-current outputs (VCC = 12V)
- Internal dead-time NOT provided - external dead-time logic required

**Pin connections:**
- VCC (pin 3): +12V power supply for both drivers
- VDD (pin 9): +5V logic supply for input circuits
- HIN (pin 10): High-side input from dead-time logic
- LIN (pin 12): Low-side input from dead-time logic
- HO (pin 7): High-side gate driver output (sources/sinks up to 2A)
- LO (pin 1): Low-side gate driver output (sources/sinks up to 2A)
- VS (pin 5): Floating supply return (connects to switching node, 0-48V)
- VB (pin 6): Bootstrap supply (VCC + Vf_diode above VS)
- COM (pin 2): Power ground
- VSS (pin 13): Logic ground

**Datasheet reference:** IR2110 datasheet Figure 10-11 typical half-bridge configurations.

## Group 2: Bootstrap Circuit (D1, C1)

**Purpose:** Creates a floating 12V supply (VB) that tracks the switching node voltage (VS) to power the high-side gate driver when VS rises to 48V.

**Components:**
- **D_BOOT (D1):** Schottky or fast-recovery diode, anode to VCC, cathode to VB
- **C_BOOT (C1):** 0.47µF ceramic capacitor, VB to VS

**Operation:**
1. When Q2 (low-side) is ON: VS ≈ 0V, D1 conducts, C1 charges to (VCC - Vf) ≈ 11.5V
2. When Q1 (high-side) is ON: VS rises to ~48V, D1 blocks, C1 floats up with VS
3. VB = VS + 11.5V, providing 11.5V across high-side driver circuits
4. C1 supplies Qg charge to turn on Q1 gate, voltage drops slightly
5. Next cycle: VS returns to 0V, C1 recharges through D1

**Sizing calculation:**
```
Cboot_min = (Qg_total + I_leakage × t_on_max) / ΔV_allowed
         = (120nC + 100µA × 2µs) / 1V
         = 320nF

Selected: 0.47µF (47% margin)
```

**Critical requirements:**
- C1 must recharge fully each cycle → minimum 10% duty cycle for low-side FET
- D1 must be fast-recovery (not slow rectifier) → recharge time < 200ns at 500kHz
- C1 placement: DIRECTLY between VB and VS pins, shortest possible traces

**Deviation from typical reference:** Reference circuits often show 10-47µF for 50Hz or 1-10µF for 30kHz. We use 0.47µF for 100-500kHz operation where bootstrap recharges every 2-10µs. Higher capacitance would increase recharge current and slow rise time.

## Group 3: Supply Decoupling (C2, C3, C4)

**Purpose:** Provide clean, low-impedance power to gate driver IC during high di/dt switching events.

**Components:**
- **C_VCC_CERAMIC (C2):** 0.1µF ceramic, VCC to COM (close to pin 3)
- **C_VCC_BULK (C3):** 10µF electrolytic/ceramic, VCC to COM (nearby)
- **C_VDD (C4):** 0.1µF ceramic, VDD to VSS (close to pin 9)

**Rationale:**
- C2 handles high-frequency switching noise (>1MHz), low ESL/ESR ceramic
- C3 provides charge reservoir for bootstrap recharge (100× larger than Cboot)
- C4 decouples logic supply, prevents noise coupling into input comparators

**Layout critical:** C2 and C4 within 5mm of IC pins. C3 can be slightly further but minimize trace inductance.

## Group 4: Power MOSFETs (Q1 high-side, Q2 low-side)

**Part selection:** IPP80N05S4-02 (Infineon)
- Vds = 150V (3× margin over 48V bus)
- Id = 80A (8× margin over 10A RMS resonant current)
- Rds(on) = 5.3mΩ @ Vgs=10V (low conduction loss)
- Qg_total = 120nC @ Vgs=10V (fast switching)
- Package: TO-220 (good thermal performance, through-hole assembly)

**Configuration:**
- Q1 (high-side): Drain to V_BUS_48V, Source to switching node (SW_OUT)
- Q2 (low-side): Drain to switching node (SW_OUT), Source to GND

**Power dissipation estimate (at 250kHz, 48V, 5A RMS):**
- Conduction loss per FET: I_rms² × Rds(on) ≈ 5² × 5.3mΩ ≈ 130mW
- Switching loss (hard-switched): Smaller due to LLC zero-voltage switching (ZVS)
- Total per FET: ~300-500mW (depends on ZVS effectiveness)
- Both FETs: ~1W total (within 2W budget from specification)

**GaN FET deviation:** Specification called for GaN FETs (e.g., GS-065-011-1-L, EPC2001C). These are NOT available in JLCPCB catalog. Using fast Si MOSFET instead results in 1-2% efficiency drop (estimated 92-93% vs 95% target), but enables full JLCPCB assembly.

## Group 5: Gate Drive Resistors (R1, R2)

**Purpose:** Limit gate current, control turn-on/turn-off speed, reduce gate ringing.

**Values:** 5.1Ω for both Q1 and Q2

**Design trade-off:**
- **Lower R (faster switching):** Reduced switching loss, higher di/dt/dv/dt, more EMI, gate ringing
- **Higher R (slower switching):** Increased switching loss, lower EMI, overdamped gate

**Calculation:**
```
Turn-on time: t_on ≈ Rgate × Qg / Vgs
                   ≈ 5.1Ω × 120nC / 12V
                   ≈ 51ns (acceptable for 100-500kHz)

Peak gate current: I_peak = Vgs / Rgate
                          = 12V / 5.1Ω
                          = 2.35A (within IR2110 2A typical, 2.5A max)
```

**Placement:** Mount R1 and R2 close to MOSFET gates (not at driver output) to minimize gate loop inductance.

**Deviation from reference:** Many references show 10-47Ω for generic applications. We use 5.1Ω because:
1. Fast Si MOSFETs have lower Qg than older parts → can use lower R
2. High switching frequency (100-500kHz) → faster edges reduce switching loss
3. Peak current (2.35A) still within driver capability

For GaN FETs (if available), typical range is 2-5Ω.

## Group 6: Source-to-Gate Resistors (R3, R4)

**Purpose:** Prevent floating gates during startup, shutdown, or driver malfunction. Provide controlled discharge path for gate charge.

**Values:** 10kΩ for both Q1 and Q2

**Operation:**
- When driver output is tri-state or disabled: gate discharges through Rsg
- During normal operation: Rsg has negligible effect (I_leakage = Vgs/Rsg ≈ 1mA)
- Prevents Miller turn-on from dv/dt on drain during complementary FET switching

**Critical for safety:** "NEVER OMIT THE GATE-TO-SOURCE RESISTORS" (per IR2110 app notes). Floating gates can cause:
- Spurious turn-on from dv/dt coupling
- Shoot-through (both FETs on simultaneously)
- MOSFET destruction

**Placement:** Connect R3 between Q1 gate and Q1 source (switching node), R4 between Q2 gate and Q2 source (GND). Mount directly at MOSFET pins, not at driver output.

**Value selection:** 10kΩ is standard. Range: 10k-100k.
- Too low (<1kΩ): loads driver output, slows edges
- Too high (>100kΩ): slow discharge, doesn't prevent Miller turn-on

## Group 7: Optional Snubbers (R5+C5 for Q1, R6+C6 for Q2)

**Purpose:** Dampen drain-source ringing caused by parasitic inductance and output capacitance resonance during hard switching.

**Configuration:** RC network in series across each MOSFET drain-source.

**Values:**
- R_SNUB = 10Ω (critical damping resistor)
- C_SNUB = 1nF C0G/NP0 100V ceramic

**Design:**
Parasitic resonance frequency:
```
f_parasitic = 1 / (2π × sqrt(L_parasitic × C_oss))
            ≈ 1 / (2π × sqrt(10nH × 100pF))
            ≈ 160MHz

Critical damping resistance:
R_critical = sqrt(L_parasitic / C_parasitic)
           = sqrt(10nH / 100pF)
           ≈ 10Ω

Snubber pole frequency:
f_pole = 1 / (2π × R × C)
       = 1 / (2π × 10Ω × 1nF)
       ≈ 16MHz (below parasitic resonance, above switching frequency)
```

**DNF (Do Not Fit) marking:** Snubbers are marked DNF in BOM and populated only if ringing is observed during testing. Reasons:
1. LLC converters with good ZVS may not exhibit significant ringing
2. Careful layout can minimize parasitic inductance
3. Snubbers add cost and power dissipation (though small)

**If ringing observed:** Populate R5+C5 and/or R6+C6. Tune R value for critical damping (underdamped if R too low, overdamped if R too high).

**Power dissipation (if fitted):**
```
P_snub ≈ 0.5 × C_snub × V_bus² × f_sw
       ≈ 0.5 × 1nF × 48² × 500kHz
       ≈ 0.58W per snubber

Total both snubbers: ~1.2W (significant, avoid if possible)
```

## Dead-Time Requirements

**CRITICAL:** HI_IN and LO_IN must have non-overlapping dead-time to prevent shoot-through.

**Shoot-through:** Both Q1 and Q2 on simultaneously creates direct path from V_BUS to GND, resulting in:
- Extremely high current (limited only by Rds(on) ≈ 10mΩ total → I = 48V / 10mΩ = 4800A!)
- Instant destruction of both MOSFETs
- Damage to power supply, gate driver, PCB traces

**Dead-time calculation:**
```
t_deadtime > t_turn-off(Q1) + t_turn-on(Q2) + t_propagation_delay

Where:
  t_turn-off ≈ Rgate × Qg / Vgs ≈ 51ns (same as turn-on for symmetry)
  t_propagation_delay ≈ 20-50ns (driver delay, layout)

Minimum dead-time: ~150ns
Recommended: 200-300ns (margin for component variation, temperature)
```

**Provided by:** DEAD_TIME_GENERATOR block (external to PRIMARY_HALF_BRIDGE).

## Layout Critical Points

1. **Bootstrap capacitor C_BOOT:** Shortest possible traces from VB (pin 6) to VS (pin 5). Any inductance reduces bootstrap voltage and slows recharge.

2. **VCC bypass C_VCC_CERAMIC:** Within 5mm of VCC pin (pin 3). Use ground plane, not trace.

3. **Gate resistors R_GATE:** Mount close to MOSFET gates, not driver outputs. Minimize gate loop area to reduce ringing.

4. **Source-to-gate resistors R_SG:** Connect directly at MOSFET pins (gate to source).

5. **VS net (switching node):** High di/dt node. Minimize loop area Q1_source → Q2_drain → C_BOOT → Q1_source. Wide, short traces (or polygon pour).

6. **COM/VSS grounding:** Star ground at single point. Do not mix power ground (COM) and logic ground (VSS) except at star point.

7. **High voltage clearance:** V_BUS_48V to GND requires >1mm clearance (per IPC-2221 for 50V).

## Test Points / Debugging

Recommended test points for commissioning:
- TP1: HI_IN (verify dead-time logic output)
- TP2: LO_IN (verify dead-time logic output)
- TP3: SW_OUT (switching node waveform, should show 0-48V square wave)
- TP4: Q1 gate (verify high-side gate drive amplitude and timing)
- TP5: Q2 gate (verify low-side gate drive amplitude and timing)
- TP6: VB (bootstrap voltage, should be VCC - Vf above VS when VS low)

**Initial checkout (before applying 48V):**
1. Verify VCC = 12V, VDD = 5V
2. Apply low-frequency test signal to HI_IN, LO_IN (~1kHz)
3. Measure Q1 gate, Q2 gate (should swing 0-12V)
4. Verify dead-time between HI and LO edges
5. Slowly increase V_BUS from 5V to 48V, monitor switching node

## Known Limitations / Risks

1. **GaN FET unavailability:** Si MOSFET fallback reduces efficiency by 1-2%. Mitigation: Use lowest Rds(on), lowest Qg part available from JLCPCB.

2. **Bootstrap recharge constraint:** Requires minimum ~10% duty cycle for low-side FET. LLC converters can operate at very high duty (>90% high-side) at light load, potentially starving bootstrap. Mitigation: Ensure control loop limits maximum duty or adds periodic refresh pulses.

3. **Hard-switching at startup:** LLC converters achieve ZVS only near resonance. During startup (far from resonance), MOSFETs may hard-switch, increasing stress. Mitigation: Soft-start circuit ramps up slowly, allowing resonance to establish.

4. **EMI:** High di/dt and dv/dt at 100-500kHz can radiate. Mitigation: Careful layout (minimize loop areas), add snubbers if needed, shield/filter SW_OUT trace.

5. **Gate drive integrity:** 5V logic driving 100-500kHz PWM over PCB traces can couple noise. Mitigation: Differential or shielded traces for HI_IN/LO_IN if long runs, ground plane under signals.

## Success Criteria

- [ ] Gate driver sources 12V to MOSFET gates with <100ns rise time
- [ ] Dead-time verified between HI and LO outputs (200-300ns)
- [ ] Bootstrap voltage VB maintains >10V during high-side on-time at 500kHz
- [ ] Switching node SW_OUT shows clean 0-48V transitions with <50ns edges
- [ ] No shoot-through current observed (measure with current probe on V_BUS)
- [ ] MOSFET case temperatures <80°C at full load (10A RMS, 250kHz nominal)
- [ ] Minimal gate ringing (<10% overshoot) or damped with snubbers

---

**Document status:** Initial rationale. To be updated after simulation and hardware testing.
