# circuit-synth Integration

AnyAria depends on two feature branches from circuit-synth that add critical functionality:

## Required circuit-synth PRs

### 1. feat/jlc-import-components (Primary)

**Commit**: f4d4de2  
**PR**: JLCPCB component import for LCSC part numbers  
**Author**: paycheckpacheck

**What it provides**:
- `import_jlc_component("C25804")` - Direct LCSC part import
- `fast_jlc_search("resistor 10k")` - Search JLC PCB database
- `component_from_search_result()` - Convert search to Component
- Automatic BOM properties (LCSC, MPN, price, stock)
- Smart component finder with symbol/footprint mapping

**AnyAria uses**:
```python
from circuit_synth.manufacturing.jlcpcb import (
    import_jlc_component,
    fast_jlc_search,
    component_from_search_result,
    find_cheapest_jlc,
    find_most_available_jlc
)

# Search JLC for components
results = fast_jlc_search("N-MOSFET 150V 100A")
best = find_most_available_jlc(results)

# Import as Component with all metadata
mosfet = component_from_search_result(best, reference="Q1")
```

### 2. feat/circuit-generation-agents (Secondary)

**Commit**: 885454c  
**PR**: Generate hierarchical blocks with declared input and output ports  
**Author**: paycheckpacheck

**What it provides**:
- Hierarchical block generation
- Declared input/output ports
- Schematic layout tools driven by Claude

**AnyAria will use** (Phase 2):
```python
from circuit_synth import Circuit, HierarchicalBlock

# Create block-based circuits
power_block = HierarchicalBlock("Power Supply")
power_block.add_input("VIN")
power_block.add_output("VOUT")

circuit.add_block(power_block)
```

## Installation

### For Development (Recommended)

If you're developing AnyAria and have local circuit-synth checkout:

```bash
# Install circuit-synth from local branch
cd /path/to/circuit-synth
git checkout feat/jlc-import-components
pip install -e .

# Install AnyAria
cd /path/to/AnyAria
pip install -e .
```

### For Users (From GitHub)

```bash
# Install AnyAria with circuit-synth JLC integration
pip install "anyaria[circuit-synth] @ git+https://github.com/YOUR_USERNAME/AnyAria.git"

# This will automatically install:
# circuit-synth @ git+...@feat/jlc-import-components
```

## Dependency Graph

```
AnyAria
  ├── FastAPI (MCP server)
  ├── wxPython (KiCad plugin UI)
  └── circuit-synth @ feat/jlc-import-components [optional]
        ├── JLC PCB component database
        ├── LCSC part number import
        ├── Fast search with filtering
        └── kicad-sch-api (KiCad file I/O)
```

## Why Optional Dependency?

circuit-synth requires Python 3.12+, but KiCad ships with Python 3.11.

**Solution**:
- AnyAria core: Python 3.11+ compatible
- circuit-synth integration: Optional feature
- Graceful degradation: Stub implementation if not available

**Usage**:
```python
try:
    from circuit_synth.manufacturing.jlcpcb import fast_jlc_search
    CIRCUIT_SYNTH_AVAILABLE = True
except ImportError:
    CIRCUIT_SYNTH_AVAILABLE = False
    # Use stub implementation
```

## Future: When PRs Merge

When these PRs merge to circuit-synth main:

```toml
[project.optional-dependencies]
circuit-synth = [
    "circuit-synth>=0.13.0",  # Version with JLC integration
]
```

## Status Check

Verify circuit-synth JLC integration is working:

```python
from circuit_synth.manufacturing.jlcpcb import import_jlc_component

# Test import
r1 = import_jlc_component("C25804")
print(f"Component: {r1.value}")
print(f"LCSC: {r1.properties.get('LCSC')}")
print(f"Stock: {r1.properties.get('JLCPCB_Stock')}")
```

Expected output:
```
Component: 10K
LCSC: C25804
Stock: 5000
```

## Links

- circuit-synth repo: https://github.com/circuit-synth/circuit-synth
- JLC PR: https://github.com/circuit-synth/circuit-synth/tree/feat/jlc-import-components
- Hierarchical PR: https://github.com/circuit-synth/circuit-synth/tree/feat/circuit-generation-agents
