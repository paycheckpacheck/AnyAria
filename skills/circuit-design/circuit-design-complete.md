---
name: anyaria
description: AI-powered circuit design - generate complete circuits from requirements
triggers:
  - anyaria
  - circuit design
  - design circuit
---

# AnyAria Circuit Design Skill

Generate complete circuits from high-level requirements using AI-driven design.

## Usage

When user invokes with `/anyaria [requirements]`, execute this workflow.

## Step-by-Step Workflow

### Step 1: Parse Requirements (2 minutes)

Extract structured requirements from user input:

```python
requirements = {
    "input": {"voltage": 12.0, "current": None},
    "output": {"voltage": 3.3, "current": 2.0},
    "budget": 5.0,
    "foms": ["efficiency > 85%", "ripple < 50mV"],
    "preferences": ["JLC stock", "small footprint"]
}
```

### Step 2: Generate Block Diagram (3 minutes)

Create high-level architecture:

```
Input (12V) → Buck Converter → Output Filter → 3.3V @ 2A
              ↓
              Feedback Loop
```

Each block specifies:
- Inputs/outputs
- Power budget
- Key components needed

### Step 3: Research Components (Fan-out 3 parallel agents, 5 minutes)

Launch parallel research agents:

**Agent 1: Find Buck Converter IC**
```
Search JLC PCB for:
- Buck regulator IC
- Input: 12V
- Output: 3.3V @ 2A
- In stock, prefer <$1
```

**Agent 2: Find Passives (L, C)**
```
Search for:
- Inductor: 10-47µH, >2A rating
- Output cap: 22-100µF, low ESR
- Input cap: 10-22µF
- In stock at JLC
```

**Agent 3: Read Datasheets**
```
Download datasheet for selected buck IC
Extract:
- Typical application circuit
- Design equations
- Component value recommendations
```

### Step 4: Generate Circuit with circuit-synth (3 minutes)

```python
from circuit_synth import Circuit, Component, Net

circuit = Circuit("Buck Converter 12V to 3.3V @ 2A")

# From research agents
buck_ic = Component("U1", "TPS54331", footprint="SOT23-6")
inductor = Component("L1", "22µH", footprint="IND_4x4")
cap_out = Component("C_OUT", "47µF", footprint="0805")
cap_in = Component("C_IN", "10µF", footprint="0805")

# Build topology from datasheet
circuit.add_net(Net("VIN", [buck_ic.VIN, cap_in.pos]))
circuit.add_net(Net("SW", [buck_ic.SW, inductor.pin1]))
circuit.add_net(Net("VOUT", [inductor.pin2, cap_out.pos]))
circuit.add_net(Net("FB", [buck_ic.FB, voltage_divider]))

# Generate KiCad file
circuit.to_kicad("buck_converter.kicad_sch")
```

### Step 5: Generate Python Simulation (4 minutes)

Create simulation model for each block:

```python
class BuckConverter_U1:
    """Simulation of TPS54331 buck converter"""
    
    def __init__(self):
        # Design values from datasheet equations
        self.Vin = 12.0
        self.Vout = 3.3
        self.Iout_max = 2.0
        
        # Component values
        self.L = 22e-6  # 22µH
        self.C_out = 47e-6  # 47µF
        self.fs = 500e3  # 500kHz switching
        
        # From datasheet: calculate inductor ripple current
        self.dI_L = (self.Vin - self.Vout) * self.Vout / (self.L * self.fs * self.Vin)
        
        # Output voltage ripple
        ESR = 0.01  # 10mΩ ESR
        self.dV_out = self.dI_L * ESR
        
    def efficiency(self):
        """Estimate efficiency from datasheet curves"""
        # Typical efficiency at this operating point
        return 0.87  # 87% from datasheet graph
    
    def simulate_transient(self, load_step, dt=1e-6):
        """Simulate load transient response"""
        import numpy as np
        
        # LC filter transfer function
        omega0 = 1 / np.sqrt(self.L * self.C_out)
        
        # Simulate step response
        t = np.arange(0, 1e-3, dt)
        response = self.Vout * (1 - np.exp(-t * omega0))
        
        return t, response
    
    def power_dissipation(self, temp_ambient=25):
        """Calculate power dissipation and junction temp"""
        P_in = self.Vin * self.Iout_max / self.efficiency()
        P_out = self.Vout * self.Iout_max
        P_loss = P_in - P_out
        
        # Thermal calculation
        theta_ja = 120  # °C/W from datasheet
        T_junction = temp_ambient + P_loss * theta_ja
        
        return {
            "power_loss": P_loss,
            "junction_temp": T_junction,
            "safe": T_junction < 125  # Max rating
        }
```

### Step 6: Tune Component Values (3 minutes)

Iterate simulation to optimize values:

```python
# Test different inductor values
for L in [10e-6, 22e-6, 47e-6]:
    converter.L = L
    ripple = converter.dI_L
    
    # Check ripple current < 30% of output current
    if ripple < 0.3 * converter.Iout_max:
        # Check output voltage ripple
        if converter.dV_out < 0.05:  # <50mV
            selected_L = L
            break

# Verify efficiency meets spec
eff = converter.efficiency()
assert eff > 0.85, "Efficiency requirement not met"
```

### Step 7: Derating Verification (2 minutes)

Verify all components properly derated:

```python
def verify_derating(circuit, conditions):
    """Check all components are properly derated"""
    
    results = []
    
    for component in circuit.components:
        # Voltage derating (80% rule)
        if component.voltage_max > 0.8 * component.voltage_rating:
            results.append(f"FAIL: {component.ref} voltage derating")
        
        # Power derating with temperature
        thermal = component.power_dissipation(conditions["temp"])
        if not thermal["safe"]:
            results.append(f"FAIL: {component.ref} thermal")
        
        # Current derating (90% rule)
        if component.current > 0.9 * component.current_rating:
            results.append(f"FAIL: {component.ref} current derating")
    
    return results
```

## Output to User

Return comprehensive results:

```markdown
## Circuit Generated: Buck Converter 12V → 3.3V @ 2A

### Block Diagram
```
VIN (12V) → [Buck IC: TPS54331] → [L: 22µH] → [C: 47µF] → VOUT (3.3V @ 2A)
              ↓ Feedback
              [R1: 10kΩ, R2: 5.1kΩ]
```

### Component Selection

**U1: TPS54331 Buck Converter**
- JLC Part: C12345
- Price: $0.87 (in stock)
- Ratings: 28V input, 3A output
- Efficiency: ~87% at this operating point
- Datasheet: [link]

**L1: 22µH Inductor**  
- JLC Part: C67890
- Price: $0.15 (in stock)
- Rating: 3A, DCR=25mΩ
- Ripple current: 0.42A (21% of Iout) ✓

**C_OUT: 47µF Ceramic**
- JLC Part: C11223
- Price: $0.08 (in stock)
- ESR: 10mΩ
- Output ripple: 4.2mV ✓

### BOM Cost: $1.47 (within $5 budget ✓)

### Simulation Results

Output voltage ripple: 4.2mV (spec: <50mV) ✓
Efficiency: 87% (spec: >85%) ✓
Junction temp: 78°C @ 25°C ambient (max 125°C) ✓

### Python Simulation Code

[Full code in Simulation tab]

### Verification

✓ All requirements met
✓ Components properly derated
✓ Thermal analysis passed
✓ In budget
✓ All parts in stock at JLC

Ready to apply to schematic.
```

## Implementation Notes

- Use Workflow tool to fan out research agents in parallel
- Cache datasheet downloads in local directory
- Use circuit-synth for KiCad generation
- Generate runnable Python simulation code
- Verify all FOMs before returning to user

## Error Handling

If requirements cannot be met:
1. Report which constraint cannot be satisfied
2. Suggest alternatives (relax budget, change specs, etc.)
3. Provide closest solution with explanation
