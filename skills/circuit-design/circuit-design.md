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

## Workflow

### 1. Parse Requirements

Extract from user input:
- Input voltage/current
- Output voltage/current
- Power requirements
- FOMs (efficiency, ripple, transient response, etc.)
- Budget constraints
- Environmental (temperature, power dissipation)

### 2. Generate Block Diagram

Create high-level architecture:
- Power supply blocks
- Signal conditioning blocks
- Control blocks
- Protection blocks

Each block gets:
- Input/output specifications
- Transfer function requirements
- Power budget allocation

### 3. Component Research (Fan-out Agents)

For each block, spawn research agents:

**Agent: component-finder**
- Search JLC PCB for suitable components
- Filter by: in stock, price, specifications
- Return top 3 candidates with justification

**Agent: datasheet-reader**
- Download and parse datasheet PDFs
- Extract: typical application circuit, equations, ratings
- Return: circuit topology, component values, design equations

**Agent: circuit-validator**
- Verify component selections meet requirements
- Check: voltage ratings, current capacity, temperature derating
- Return: pass/fail with reasoning

### 4. Circuit Generation

Use circuit-synth to generate KiCad schematic:

```python
from circuit_synth import Circuit, Component, Net

# Create circuit
circuit = Circuit("Generated Circuit")

# Add components (from research)
regulator = Component("U1", footprint="SOT-23-5", value="AP2112K-3.3")
cap_in = Component("C1", footprint="0805", value="10uF")
cap_out = Component("C2", footprint="0805", value="10uF")

# Connect nets
circuit.add_net(Net("VIN", [regulator.pin(1), cap_in.pin(1)]))
circuit.add_net(Net("VOUT", [regulator.pin(5), cap_out.pin(1)]))

# Generate schematic
circuit.to_kicad("output.kicad_sch")
```

### 5. Python Simulation Generation

For each block, generate simulation code:

```python
class Block_PowerSupply:
    """Simulation model for power supply block"""
    
    def __init__(self):
        # Component values from design
        self.Vin = 12.0
        self.Vout = 3.3
        self.L = 22e-6  # 22µH
        self.C = 47e-6  # 47µF
        self.R_load = 1.65  # 2A load
        
        # From datasheet equations
        self.fs = 600e3  # Switching frequency
        self.duty = self.Vout / self.Vin
        
    def transfer_function(self, s):
        """LC filter transfer function"""
        import numpy as np
        omega0 = 1 / np.sqrt(self.L * self.C)
        Q = np.sqrt(self.L / self.C) / self.R_load
        return omega0**2 / (s**2 + omega0/Q*s + omega0**2)
    
    def simulate(self, input_signal, dt=1e-6):
        """Simulate output given input"""
        # Switched-mode power supply model
        # Apply equations from datasheet
        output_signal = self._switching_model(input_signal, dt)
        return output_signal
    
    def derate_power(self, temp_ambient):
        """Derate for temperature"""
        # From datasheet thermal curves
        temp_junction = temp_ambient + self.power_dissipation * self.theta_ja
        if temp_junction > 125:
            return False, "Junction temp exceeds rating"
        return True, f"Junction temp: {temp_junction:.1f}°C"
```

### 6. Value Tuning

Use simulation to optimize component values:

```python
# Iterate on values to meet requirements
for L in [10e-6, 22e-6, 47e-6]:
    for C in [22e-6, 47e-6, 100e-6]:
        block.L = L
        block.C = C
        
        # Simulate transient response
        output = block.simulate(step_input)
        
        # Check FOM
        overshoot = max(output) - block.Vout
        settling_time = time_to_settle(output, 0.02)
        
        if overshoot < 0.1 and settling_time < 100e-6:
            # Meets requirements
            selected_L = L
            selected_C = C
            break
```

### 7. Derating Analysis

Verify all components are properly derated:

```python
def verify_derating(component, operating_conditions):
    """Check component derating"""
    
    # Voltage derating (typically 80% max)
    if component.voltage_applied > 0.8 * component.voltage_rating:
        return False, "Voltage derating insufficient"
    
    # Power derating for temperature
    temp = operating_conditions["ambient_temp"]
    power_limit = component.power_rating_at_temp(temp)
    if component.power_dissipation > power_limit:
        return False, "Power derating insufficient at temperature"
    
    # Current derating
    if component.current > 0.9 * component.current_rating:
        return False, "Current derating insufficient"
    
    return True, "Component properly derated"
```

## Output Format

Return JSON with:

```json
{
  "block_diagram": "Text representation of blocks",
  "component_research": [
    {
      "component": "U1 - AP2112K-3.3",
      "analysis": "3.3V LDO, 600mA, $0.15, in stock...",
      "datasheet_url": "https://...",
      "equations": ["Vout = 1.2V * (1 + R1/R2)", ...]
    }
  ],
  "simulation_code": "Complete Python code for all blocks",
  "nets": [
    {"name": "VIN", "type": "power", "min": 11.0, "max": 13.0},
    {"name": "VOUT", "type": "power", "min": 3.27, "max": 3.33}
  ],
  "bom": [
    {"ref": "U1", "value": "AP2112K-3.3", "price": 0.15, "stock": true}
  ],
  "total_cost": 1.47,
  "verification": {
    "meets_requirements": true,
    "derating_ok": true,
    "warnings": []
  }
}
```

## Example Usage

```
User: /anyaria Design a 3.3V buck converter, 2A output, from 12V input, <$5 BOM