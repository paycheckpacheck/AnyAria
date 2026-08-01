# BLDC Motor Driver - Research Demo

This document shows how AnyAria will design a BLDC motor driver using **research-driven design** (Phase 2).

## User Request

```
Design a BLDC motor driver
- Input: 12-24V
- Output: 10A per phase
- Hall sensor control
- Budget: $15
```

## AnyAria Research Process (Automated)

### Step 1: Understand Requirements via Claude

**Claude API Call:**
```json
{
  "prompt": "Parse circuit requirements: BLDC motor driver, 12-24V, 10A per phase, hall sensors, $15 budget",
  "extract": ["topology", "voltage_range", "current", "control_method", "constraints"]
}
```

**Claude Response:**
```json
{
  "circuit_type": "bldc_motor_driver",
  "topology": "3-phase_inverter",
  "voltage_input": {"min": 12, "max": 24},
  "current_per_phase": 10.0,
  "control": "hall_sensor_commutation",
  "protection_required": ["overcurrent", "back_emf", "thermal"],
  "budget": 15.0,
  "unknowns": [
    "What components are needed for BLDC driver?",
    "How to select gate driver IC?",
    "MOSFET selection criteria?"
  ]
}
```

### Step 2: Web Research (Parallel Agents)

#### Agent 1: Learn BLDC Topology

**Web Search Query:** `"BLDC motor driver design guide reference schematic"`

**Sources Found:**
1. TI Application Note SLUA063: "Brushless DC Motor Control Made Easy"
2. Infineon: "BLDC Motor Control with XMC™ Microcontrollers"
3. ST AN4058: "BLDC motor control with back-EMF sensing"
4. ODrive open source motor controller (GitHub)

**Extracted Knowledge:**
```json
{
  "topology": {
    "description": "3-phase bridge inverter (6 MOSFETs)",
    "source": "TI SLUA063 page 4, Figure 2",
    "components": [
      "6x N-channel MOSFETs (high-side + low-side for 3 phases)",
      "3-phase gate driver IC with bootstrap",
      "Bootstrap diodes (3x)",
      "Bootstrap capacitors (3x)",
      "Bulk capacitor for input",
      "Current sense resistors (3x)",
      "Gate resistors (6x)"
    ]
  },
  "control_method": {
    "description": "6-step commutation using hall sensors",
    "source": "Infineon BLDC app note, section 3.2",
    "commutation_table": "Hall sensor states → MOSFET switching sequence"
  },
  "protection": {
    "overcurrent": "Shunt resistor + comparator or ADC",
    "back_emf": "Schottky diodes across motor phases",
    "thermal": "MOSFETs with thermal shutdown"
  }
}
```

#### Agent 2: Research Gate Driver ICs

**Web Search:** `"3-phase gate driver IC BLDC motor control"`

**Candidate ICs Found:**
1. **IR2130** (Infineon)
   - 3-phase bridge driver
   - 600V rating
   - Internal bootstrap diodes
   - Datasheet: https://www.infineon.com/dgdl/ir2130.pdf

2. **DRV8301** (TI)  
   - 3-phase driver with current sensing
   - Integrated gate drivers + shunt amps
   - Datasheet: https://www.ti.com/lit/ds/symlink/drv8301.pdf

3. **L6234** (ST)
   - 3-phase DMOS driver
   - 50V, 5A capability
   - Datasheet: https://www.st.com/resource/en/datasheet/l6234.pdf

**Datasheet Analysis (Agent downloads and parses):**

From **IR2130 datasheet**:
```json
{
  "typical_application": {
    "page": 12,
    "circuit": "3-phase BLDC motor drive",
    "bootstrap_caps": "0.1µF ceramic",
    "bootstrap_diodes": "Fast recovery, 1A",
    "gate_resistors": "10Ω recommended",
    "equations": {
      "bootstrap_cap": "C_boot ≥ Q_gate * 2 / ΔV_boot",
      "dead_time": "Set by external RC: t_dt = R_dt * C_dt",
      "gate_resistor": "R_g = (V_CC - V_GS) / I_gate_peak"
    }
  },
  "specifications": {
    "V_offset_max": 600,
    "I_out": "±0.5A",
    "V_cc": "10-20V",
    "dead_time": "programmable"
  },
  "jlc_availability": {
    "part_number": "C123456",
    "price": 2.50,
    "stock": 1000,
    "basic_part": false
  }
}
```

**Selection Decision:**
```
Selected: IR2130
Rationale:
  - Proven BLDC application (datasheet page 12)
  - 600V rating (safe for 24V input with margin)
  - Internal bootstrap diodes (reduces BOM)
  - Available on JLC PCB
  - Cost: $2.50 (within budget)
Source: IR2130.pdf typical application, JLC search
```

#### Agent 3: Research MOSFETs

**Web Search:** `"N-channel MOSFET 30V 20A motor driver low Rds JLC PCB"`

**Filter Criteria (learned from research):**
- V_ds > 2x V_input_max = 48V minimum
- I_d > 1.5x I_phase = 15A minimum  
- Rds(on) low for efficiency
- Available on JLC PCB
- Price < $2 each

**Candidates:**
1. **IRFB4115**: 150V, 104A, Rds=3.7mΩ @ 10V, $1.20
2. **PSMN4R2-40YS**: 40V, 100A, Rds=4.2mΩ @ 10V, $0.85
3. **AOT460**: 60V, 70A, Rds=2.4mΩ @ 10V, $1.50

**Thermal Analysis (from datasheets):**

For **IRFB4115** at 10A:
```python
# From IRFB4115 datasheet
I_rms = 10 / sqrt(2) = 7.07A  # Sinusoidal approximation
Rds_on_25C = 3.7e-3  # Ω
temp_coeff = 0.0045  # per °C (from datasheet curve)

# Power dissipation (conduction)
P_cond = I_rms^2 * Rds_on = 7.07^2 * 0.0037 = 0.18W

# Switching loss (from datasheet switching times)
t_rise = 50ns, t_fall = 30ns
P_sw = 0.5 * V_ds * I * (t_rise + t_fall) * f_sw
P_sw = 0.5 * 24 * 10 * (80e-9) * 20e3 = 0.19W

# Total per MOSFET
P_total = 0.18 + 0.19 = 0.37W

# Junction temperature
theta_ja = 62°C/W (from datasheet, TO-220 package)
T_ambient = 40°C
T_junction = 40 + 0.37 * 62 = 63°C

# Check margin
T_junction_max = 175°C (from datasheet)
Margin = 175 - 63 = 112°C ✅ SAFE
```

**Selection:**
```
Selected: IRFB4115 (6 pieces)
Rationale:
  - Thermal margin: 112°C at 40°C ambient
  - Low Rds(on) = 3.7mΩ for efficiency
  - 150V rating (3x safety margin for 24V)
  - JLC Part C234567, $1.20 each
  - TO-220 package (good thermal performance)
Source: 
  - IRFB4115.pdf thermal curves
  - Calculation using datasheet equations
  - JLC PCB stock check
Total cost: $7.20 for 6 MOSFETs
```

#### Agent 4: Research Current Sensing

**Web Search:** `"motor current sensing shunt resistor amplifier"`

**Found Solutions:**
1. Low-side shunt + op-amp
2. High-side current sense amp (INA240, INA186)
3. Integrated in gate driver (DRV8301)

**Selected Approach:**
```
Low-side shunt resistor + INA240A3

Shunt Value Calculation:
  V_sense_max = 3.3V (ADC range)
  I_max = 10A
  Gain = 20V/V (INA240A3)
  
  R_shunt = V_sense_max / (Gain * I_max)
  R_shunt = 3.3 / (20 * 10) = 0.0165Ω
  
  Choose standard: 0.01Ω (2W rating)
  
  Actual V_sense = 0.01 * 10 * 20 = 2.0V ✅
  Power in shunt = 10^2 * 0.01 = 1W ✅ (2W rated)

Components:
  - 3x 0.01Ω 2W shunt resistors (JLC C678901, $0.25 each)
  - 1x INA240A3 current sense amp (JLC C789012, $1.50)
  
Source: INA240.pdf application section
Total: $2.25
```

### Step 3: Calculate Component Values

Using equations extracted from datasheets:

**Bootstrap Capacitors:**
```python
# From IR2130 datasheet equation
Q_gate = 80nC  # IRFB4115 gate charge
Delta_V = 1V   # Allowed voltage drop
N = 2          # Safety factor

C_boot = Q_gate * N / Delta_V
C_boot = 80e-9 * 2 / 1.0 = 160nF

# Choose standard: 0.22µF (C456789, $0.10 each)
# Need 3 pieces (one per phase)
```

**Gate Resistors:**
```python
# From IR2130 datasheet
V_cc = 12V
V_gs = 10V (MOSFET gate threshold)
I_gate_peak = 0.5A (IR2130 output current)

R_gate = (V_cc - V_gs) / I_gate_peak
R_gate = (12 - 10) / 0.5 = 4Ω

# Choose standard: 10Ω for slower switching, reduce EMI
# (Trade: Slower switching but less noise)
# JLC C567890, $0.01 each, need 6 pieces
```

**Bulk Capacitor:**
```python
# Hold-up time for motor transients
I_motor_max = 10A * 3 phases = 30A
t_holdup = 10ms  # Minimum hold-up
V_min = 12V
V_max = 24V
Delta_V = 2V  # Allowed droop

C_bulk = I_motor_max * t_holdup / Delta_V
C_bulk = 30 * 0.01 / 2 = 150µF minimum

# Choose: 470µF/35V electrolytic (margin for ripple current)
# JLC C890123, $0.50
```

### Step 4: Generate Circuit

**Block Diagram:**
```
VIN (12-24V) 
  → [Bulk Cap 470µF]
  → [Linear Reg LM7812 → 12V for gate driver]
  → [IR2130 Gate Driver IC]
      ├─ Bootstrap (3x diodes + 3x caps)
      └─ Gate Resistors (6x 10Ω)
  → [6x IRFB4115 MOSFETs - 3-phase bridge]
      └─ Current Sense Shunts (3x 0.01Ω)
  → [INA240A3 Current Sense Amp]
  → [BLDC Motor - 3 phases]
  → [Hall Sensors - 3 inputs to MCU]
```

**Python Code (using circuit-synth):**
```python
from circuit_synth import Circuit, Component, Net

circuit = Circuit("BLDC Motor Driver - 12-24V, 10A/phase")

# Power input
vin = Component("VIN", "Connector", footprint="TerminalBlock_2pos")
c_bulk = Component("C_BULK", "470µF/35V", footprint="CP_Radial_D10.0mm_P5.00mm")

# Gate driver supply
u_reg = Component("U_REG", "LM7812", footprint="TO-220")
c_reg = Component("C_REG", "0.1µF", footprint="C_0805")

# Gate driver
u_driver = Component("U1", "IR2130", footprint="SOIC-28")

# Bootstrap components  
for i in [1, 2, 3]:
    Component(f"D_BOOT{i}", "1N4148", footprint="DO-35")
    Component(f"C_BOOT{i}", "0.22µF", footprint="C_0805")

# MOSFETs (3 phases, high+low side)
mosfets = []
for phase in ["A", "B", "C"]:
    for side in ["H", "L"]:
        mosfets.append(Component(
            f"Q_{phase}{side}",
            "IRFB4115",
            footprint="TO-220"
        ))

# Gate resistors
for i in range(1, 7):
    Component(f"R_GATE{i}", "10Ω", footprint="R_0805")

# Current sensing
for phase in ["A", "B", "C"]:
    Component(f"R_SENSE_{phase}", "0.01Ω/2W", footprint="R_2512")
u_sense = Component("U_SENSE", "INA240A3", footprint="SOIC-8")

# Motor connection
motor = Component("MOTOR", "BLDC_3Phase", footprint="TerminalBlock_3pos")

# Hall sensors
for i in [1, 2, 3]:
    Component(f"HALL{i}", "Connector", footprint="PinHeader_1x03")

# Nets (simplified - full netlist would be generated)
circuit.add_net(Net("VIN", [vin.pin(1), c_bulk.pin(1), u_reg.pin(1)]))
circuit.add_net(Net("GND", [vin.pin(2), c_bulk.pin(2)]))
circuit.add_net(Net("V12", [u_reg.pin(3), u_driver.pin("VCC")]))

# 3-phase outputs
for phase in ["A", "B", "C"]:
    circuit.add_net(Net(f"PHASE_{phase}", [
        mosfets[phase].pin("drain"),
        motor.pin(phase)
    ]))

# Generate KiCad file
circuit.to_kicad("bldc_driver.kicad_sch")
```

### Step 5: Generate Simulation

**Python Simulation Code** (auto-generated from datasheets):

```python
class BLDCDriver:
    """Generated from IR2130 + IRFB4115 datasheets"""
    
    def __init__(self):
        # From requirements
        self.Vin_max = 24
        self.I_phase = 10
        
        # From IRFB4115 datasheet
        self.Rds_on = 3.7e-3
        self.Q_gate = 80e-9
        self.theta_ja = 62
        
        # From IR2130 datasheet
        self.pwm_freq = 20e3
        
    def efficiency(self):
        """Calculate system efficiency"""
        # MOSFET losses (from datasheet equations)
        P_mosfet = self.calculate_mosfet_loss() * 6
        # Gate driver losses
        P_gate = self.Q_gate * 12 * self.pwm_freq * 6
        # Shunt losses  
        P_shunt = self.I_phase**2 * 0.01 * 3
        
        P_out = self.Vin_max * self.I_phase * 3 * 0.9
        P_in = P_out + P_mosfet + P_gate + P_shunt
        
        return P_out / P_in
```

### Step 6: BOM with Sources

| Ref | Part | Value | JLC Part | Price | Qty | Source |
|-----|------|-------|----------|-------|-----|--------|
| U1 | IR2130 | 3-ph gate driver | C123456 | $2.50 | 1 | IR2130.pdf Fig 12 |
| Q1-Q6 | IRFB4115 | N-MOSFET 150V | C234567 | $1.20 | 6 | Thermal calc |
| D1-D3 | 1N4148 | Fast diode | C345678 | $0.05 | 3 | IR2130 app note |
| C1-C3 | 0.22µF | Bootstrap cap | C456789 | $0.10 | 3 | Eq: C=Q*2/V |
| R1-R6 | 10Ω | Gate resistor | C567890 | $0.01 | 6 | IR2130 pg 15 |
| R_SA-C | 0.01Ω/2W | Current shunt | C678901 | $0.25 | 3 | INA240 app |
| U_SENSE | INA240A3 | Current amp | C789012 | $1.50 | 1 | INA240.pdf |
| C_BULK | 470µF/35V | Input bulk | C890123 | $0.50 | 1 | Hold-up calc |
| U_REG | LM7812 | 12V regulator | C901234 | $0.30 | 1 | IR2130 supply |

**Total BOM: $13.80** (within $15 budget ✅)

### Step 7: Verification

**Requirements Check:**
```
✅ Input: 12-24V (component ratings validated)
✅ Output: 10A per phase (MOSFET thermal margin: 112°C)
✅ Hall sensor control (3 inputs to MCU)
✅ Budget: $13.80 < $15
✅ Current sensing (INA240 with 0.01Ω shunts)
✅ Overcurrent protection (ADC monitoring)
✅ Thermal protection (MOSFET temp calculation)
```

**All Design Decisions Documented:**
- Every component selection has source
- Every value has equation reference
- Every equation has datasheet page number
- Total traceability from requirements → datasheets → circuit

## Result

A complete BLDC motor driver designed entirely through:
1. Web research (topology, design guides)
2. Datasheet analysis (component selection, equations)
3. JLC PCB search (availability, pricing)
4. Mathematical validation (thermal, electrical)

**No hardcoded knowledge used.** All learned from online sources.

This is how AnyAria will work in Phase 2! 🚀
