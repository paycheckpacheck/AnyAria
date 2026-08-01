# Research-Driven Circuit Design

**CRITICAL PRINCIPLE: AnyAria does NOT contain circuit design knowledge.**

Instead, AnyAria RESEARCHES circuit design requirements from online sources for every request.

## Research Workflow

### Step 1: Understand User Intent (Use Claude)

```
User asks: "Design a BLDC motor driver"

Claude API call:
- Parse requirements (voltage, current, control method)
- Identify unknowns (what IS a BLDC driver?)
- Generate research questions
```

### Step 2: Web Research (Use WebSearch tool)

```
Research questions for BLDC driver:
1. "What components are needed for a BLDC motor driver?"
2. "BLDC motor driver typical schematic"
3. "3-phase motor controller design guide"
4. "Gate driver IC selection for BLDC"
5. "MOSFET selection for motor driver 10A 24V"
```

Search sources:
- TI Application Notes
- Infineon Motor Control Guides  
- ST Motor Driver Reference Designs
- EDN/EETimes motor driver articles
- Open source motor controller schematics (ODrive, VESC)

### Step 3: Extract Design Knowledge

From web search results, extract:
- **Topology**: 3-phase bridge, 6 MOSFETs, gate driver IC
- **Component types**: N-channel MOSFETs, bootstrap diodes, shunt resistors
- **Equations**: 
  - Bootstrap cap sizing: `C = Q_gate * 2 / V_ripple`
  - Gate resistor: `R_g = (V_drive - V_gs) / I_peak`
  - Shunt power: `P = I^2 * R`
- **Protection**: Overcurrent comparator, back-EMF clamping
- **Control**: Hall sensor inputs, PWM generation

### Step 4: Datasheet Research (Use DatasheetReader agent)

For each component type, research datasheets:

**Gate Driver IC Research:**
```
Web search: "3-phase gate driver IC BLDC"
Found: IR2130, DRV8301, L6234

Download datasheets:
- IR2130.pdf from Infineon
- DRV8301.pdf from TI
- L6234.pdf from ST

Extract from datasheets:
- Typical application circuit (page 12)
- Bootstrap component values (page 15)
- Design equations (page 18)
- Protection features (page 20)
```

**MOSFET Research:**
```
Web search: "N-channel MOSFET 24V 10A motor driver"
Filter by: JLC PCB stock, price < $2

Found options:
- IRFB4115: 150V, 104A, Rds=3.7mΩ ($1.20)
- PSMN4R2-40YS: 40V, 100A, Rds=4.2mΩ ($0.85)

Download datasheets, extract:
- Thermal resistance θ_ja
- Gate charge Q_g
- Switching times
- Safe operating area (SOA)
```

### Step 5: Component Selection (Use ComponentFinder agent)

Search JLC PCB database:
```
Query: "IR2130"
Filter: In stock, basic part (lower assembly cost)
Result: JLC part C123456, $2.50, 1000 in stock

Query: "IRFB4115"
Filter: In stock
Result: JLC part C234567, $1.20, 500 in stock
```

### Step 6: Apply Learned Knowledge

Using information from steps 2-5:
- Generate block diagram (from typical applications)
- Select components (from JLC search)
- Calculate values (from datasheet equations)
- Create simulation (from datasheet models)

### Step 7: Generate Circuit

Use circuit-synth with learned topology:
```python
# Topology learned from web research
circuit = Circuit("BLDC Driver")

# Components from datasheet research
gate_driver = Component("U1", "IR2130", footprint_from_datasheet)
mosfets = [Component(f"Q{i}", "IRFB4115", footprint) for i in range(1,7)]

# Values from datasheet equations
boot_cap_value = calculate_from_equation(Q_gate, V_ripple)  # Learned equation
gate_resistor = calculate_from_equation(V_drive, V_gs, I_peak)  # Learned equation
```

## No Hardcoded Knowledge

**WRONG APPROACH:**
```python
# DON'T DO THIS - hardcoded circuit knowledge
def design_bldc_driver():
    return {
        "gate_driver": "IR2130",  # ❌ Hardcoded component
        "mosfets": 6,  # ❌ Hardcoded count
        "topology": "3-phase bridge"  # ❌ Hardcoded topology
    }
```

**RIGHT APPROACH:**
```python
# DO THIS - research-driven design
def design_bldc_driver(requirements):
    # Research what BLDC needs
    research = web_search("BLDC motor driver design guide")
    topology = extract_topology_from(research)
    
    # Research components
    gate_drivers = web_search("3-phase gate driver IC")
    datasheets = download_datasheets(gate_drivers)
    equations = extract_equations(datasheets)
    
    # Apply learned knowledge
    circuit = generate_from_research(topology, datasheets, equations)
    return circuit
```

## Tools for Research

### WebSearch
```python
results = web_search("BLDC motor driver schematic reference design")
# Returns: URLs, PDFs, app notes
```

### WebFetch
```python
content = web_fetch("https://ti.com/lit/an/slua063/slua063.pdf")
# Returns: PDF content for parsing
```

### DatasheetReader (Agent)
```python
agent = spawn_agent("datasheet-reader", {
    "url": "https://infineon.com/dgdl/ir2130.pdf",
    "extract": ["typical_application", "equations", "component_values"]
})
# Returns: Structured data from datasheet
```

### ComponentFinder (Agent)
```python
agent = spawn_agent("component-finder", {
    "query": "3-phase gate driver IC",
    "filters": {"voltage": ">30V", "phases": 3, "in_stock": True},
    "database": "jlcpcb"
})
# Returns: Matching components with specs and pricing
```

## Information Sources Priority

1. **Manufacturer App Notes** (highest priority)
   - TI, Infineon, ST, Microchip
   - Contain proven reference designs
   - Include design equations

2. **Datasheets**
   - Typical application circuits
   - Design equations
   - Component ratings and characteristics

3. **Reference Designs**
   - Open source projects (ODrive, VESC, SimonK)
   - GitHub repositories with schematics
   - EEVblog, Hackaday projects

4. **Academic/Industry Papers**
   - IEEE papers on motor control
   - Technical articles

5. **Forums/Community** (lowest priority)
   - Only for clarification
   - Must verify against datasheets

## Example: Full BLDC Research Flow

```
User: "Design a BLDC motor driver, 12-24V input, 10A per phase"

Step 1: Research "What is a BLDC motor driver?"
→ Web search returns: 3-phase motor, requires commutation, 6 MOSFETs
→ Learn: Need gate driver, current sensing, hall sensor inputs

Step 2: Research gate driver ICs
→ Search: "3-phase BLDC gate driver IC"
→ Find: IR2130, DRV8301, L6234
→ Download datasheets
→ Extract: Typical applications, equations, component values

Step 3: Research MOSFETs
→ Search: "N-MOSFET 30V 20A low Rds(on)"
→ Filter by JLC stock
→ Find: IRFB4115
→ Download datasheet
→ Extract: Thermal data, gate charge, SOA

Step 4: Research current sensing
→ Search: "motor current sensing shunt amplifier"
→ Find: INA240, INA186
→ Learn: Shunt value = V_sense_max / I_max

Step 5: Synthesize circuit
→ Use learned topology
→ Apply learned equations
→ Select researched components
→ Generate simulation from datasheet models

Step 6: Generate KiCad schematic
→ circuit-synth with learned design
```

## Documentation in Code

Every component selection must document its source:

```python
{
    "component": "IR2130",
    "rationale": "Selected from web search 'BLDC gate driver IC'",
    "source": "https://infineon.com/ir2130",
    "learned_from": [
        "TI app note SLUA063: recommends 3-phase gate drivers",
        "IR2130 datasheet page 12: typical BLDC application",
        "JLC PCB: In stock, $2.50"
    ],
    "equations_used": [
        "Bootstrap cap (from datasheet page 15): C = 100nF * N_phases",
        "Source: IR2130.pdf equation 3"
    ]
}
```

## Summary

**AnyAria contains ZERO hardcoded circuit knowledge.**

Every circuit design:
1. Researches requirements online
2. Downloads relevant datasheets
3. Extracts equations and topologies
4. Selects components from databases
5. Applies learned knowledge
6. Documents all sources

This makes AnyAria:
- **Universal**: Works for ANY circuit type
- **Current**: Always uses latest datasheets
- **Traceable**: Every decision has a source
- **Educational**: Shows users where knowledge came from
