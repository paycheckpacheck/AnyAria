# Integration with circuit-synth

**AnyAria uses circuit-synth's existing JLC integration - no reimplementation needed!**

## What circuit-synth Already Provides

Your PR **feat/jlc-import-components** (commit f4d4de2) adds complete JLC PCB integration:

### 1. Component Import from LCSC Part Numbers

```python
from circuit_synth.manufacturing.jlcpcb import import_jlc_component

# Direct LCSC part import
r1 = import_jlc_component("C25804")
# Returns: Component(symbol="Device:R", value="10K",
#          footprint="Resistor_SMD:R_0603_1608Metric",
#          LCSC="C25804", MPN="...", Stock=1000, ...)
```

### 2. Fast Component Search

```python
from circuit_synth.manufacturing.jlcpcb import fast_jlc_search, find_cheapest_jlc

# Search for components
results = fast_jlc_search("10k resistor 0603")

# Find cheapest option
cheapest = find_cheapest_jlc(results)

# Convert search result to Component
from circuit_synth.manufacturing.jlcpcb import component_from_search_result
component = component_from_search_result(cheapest)
```

### 3. Smart Component Finder

```python
from circuit_synth.manufacturing.jlcpcb import find_component, find_components

# Find best component match
recommendations = find_component("resistor", "10k", package="0603")

# Multiple options with ranking
options = find_components("capacitor", "10uF", voltage_min=16)
```

### 4. Component Properties Automatically Attached

Every imported component includes:
- `LCSC`: Part number
- `MPN`: Manufacturer part number
- `Manufacturer`: Company name
- `JLCPCB_Package`: Package type (e.g., "0603", "SOIC-8")
- `JLCPCB_Price`: Current price
- `JLCPCB_Stock`: Stock quantity
- `JLCPCB_Part_Type`: "Basic" or "Extended"

## How AnyAria Should Use This

### Research-Driven Component Selection

Instead of reimplementing JLC search, AnyAria agents should:

**Step 1: Research what component type is needed**
```python
# Claude agent researches online:
# "What type of gate driver IC for BLDC motor?"
# Learns: "3-phase gate driver IC"
component_type = "3-phase gate driver"
```

**Step 2: Search JLC using circuit-synth**
```python
from circuit_synth.manufacturing.jlcpcb import fast_jlc_search, find_cheapest_jlc

# Search with learned requirements
results = fast_jlc_search(f"{component_type} BLDC motor")

# Filter by learned criteria (from datasheet research)
suitable = [r for r in results 
            if r.stock > 100  # In stock
            and r.basic_part  # Lower assembly cost
            and "3-phase" in r.description.lower()]

# Select best option
selected = find_cheapest_jlc(suitable)
```

**Step 3: Import as Component**
```python
from circuit_synth.manufacturing.jlcpcb import component_from_search_result

gate_driver = component_from_search_result(
    selected,
    reference="U1",
    symbol_override="Custom:GateDriver_3Phase"  # If needed
)

# Automatically includes all JLC metadata
print(gate_driver.properties["LCSC"])  # e.g., "C123456"
print(gate_driver.properties["JLCPCB_Price"])  # e.g., "$2.50"
```

### Example: BLDC Driver with Real JLC Integration

```python
from circuit_synth import Circuit, Component
from circuit_synth.manufacturing.jlcpcb import (
    fast_jlc_search, 
    find_cheapest_jlc,
    component_from_search_result,
    import_jlc_component
)

# Create circuit
circuit = Circuit("BLDC Motor Driver")

# Method 1: Direct LCSC part number (if we know it)
gate_driver = import_jlc_component("C123456", reference="U1")

# Method 2: Search and select
mosfet_results = fast_jlc_search("N-channel MOSFET 150V 100A TO-220")
mosfet_result = find_cheapest_jlc([r for r in mosfet_results if r.stock > 100])
mosfet = component_from_search_result(mosfet_result, reference="Q1")

# Method 3: Known part numbers from research
# Agent researched online and found "IRFB4115" is commonly used
# Search for it specifically
irfb_results = fast_jlc_search("IRFB4115")
if irfb_results:
    q1 = component_from_search_result(irfb_results[0], reference="Q1")

# Add to circuit
circuit.add_component(gate_driver)
circuit.add_component(mosfet)

# Generate with BOM metadata
circuit.to_kicad("bldc_driver.kicad_sch")
```

### BOM Export with JLC Data

```python
from circuit_synth.exporters import export_bom

# Export BOM with LCSC part numbers
export_bom(circuit, "bldc_bom.csv", include_jlc=True)

# CSV includes:
# Reference, Value, Footprint, LCSC, MPN, Manufacturer, Stock, Price
```

## What AnyAria Adds on Top

AnyAria's value is **research coordination**, not reimplementing JLC integration:

### 1. Research Phase
```python
# AnyAria agent researches:
# - "What components are needed for BLDC driver?"
# - "What are typical MOSFET specs for 10A motor?"
# - "Best gate driver IC for BLDC?"

# Outputs research findings:
research = {
    "topology": "3-phase bridge with gate driver",
    "components_needed": [
        {"type": "gate_driver", "specs": "3-phase, 600V, bootstrap"},
        {"type": "mosfet", "specs": "N-channel, >30V, >15A, low Rds(on)"},
        {"type": "diode", "specs": "Fast recovery, for bootstrap"}
    ]
}
```

### 2. Component Search Phase
```python
# For each component type, use circuit-synth JLC search
for component_spec in research["components_needed"]:
    # Build search query from research
    query = f"{component_spec['type']} {component_spec['specs']}"
    
    # Search using circuit-synth
    results = fast_jlc_search(query)
    
    # Filter and select
    best = find_best_match(results, component_spec)
    
    # Import as Component
    component = component_from_search_result(best)
```

### 3. Circuit Generation Phase
```python
# Use standard circuit-synth API
circuit = Circuit("Generated from Research")
circuit.add_component(gate_driver)
circuit.add_component(mosfet)
# ... etc

circuit.to_kicad("output.kicad_sch")
```

## Claude Agent Capabilities

Claude agents in AnyAria already have these tools available:

### WebSearch
```python
# Built into Claude Code
results = web_search("BLDC motor driver design guide")
# Returns: URLs, snippets, sources
```

### WebFetch
```python
# Download web pages and PDFs
content = web_fetch("https://ti.com/lit/an/slua063.pdf")
# Returns: PDF content for parsing
```

### ToolSearch
```python
# Claude agents can search for and use MCP tools
# Including datasheet readers, component databases, etc.
```

## Updated AnyAria Architecture

```
User: "Design a BLDC motor driver"
   ↓
Claude Agent (Research):
   - WebSearch: "BLDC motor driver design"
   - WebFetch: Download TI app notes
   - Extract: Component requirements
   ↓
Claude Agent (Component Selection):
   - Use circuit_synth.manufacturing.jlcpcb.fast_jlc_search()
   - Filter results by specs from research
   - Use component_from_search_result()
   ↓
Claude Agent (Circuit Generation):
   - Use circuit_synth.Circuit API
   - Add components with JLC metadata
   - circuit.to_kicad()
   ↓
Result: KiCad schematic with complete BOM
```

## Installation for Development

AnyAria should depend on circuit-synth's JLC branch:

```toml
# pyproject.toml
[project]
dependencies = [
    "circuit-synth @ git+https://github.com/circuit-synth/circuit-synth.git@feat/jlc-import-components",
    # ... other deps
]
```

Or for local development:

```bash
# Install circuit-synth from your local branch
cd /path/to/circuit-synth
git checkout feat/jlc-import-components
pip install -e .

# Install AnyAria
cd /path/to/AnyAria
pip install -e .
```

## Summary

**Don't reimplement what circuit-synth already has:**

✅ **Use circuit-synth's JLC integration**:
- `import_jlc_component()`
- `fast_jlc_search()`
- `component_from_search_result()`

✅ **Claude agents already have**:
- WebSearch
- WebFetch
- Datasheet reading capabilities

❌ **Don't reimplement**:
- JLC PCB API
- Component database
- Search functionality

**AnyAria's role**: Research coordination and workflow orchestration, not low-level integration.
