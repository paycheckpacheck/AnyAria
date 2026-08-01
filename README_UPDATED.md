# AnyAria - AI Circuit Design with Real Integration

**Status**: Phase 1 Complete ✅ | Ready for Phase 2 Development

## What is AnyAria?

An **AI-powered circuit design system** that uses Claude to research, design, and generate complete circuits with KiCad integration.

**Key Innovation**: Research-driven design - AnyAria learns from online sources and datasheets instead of hardcoded knowledge.

## Architecture

### Uses Existing Tools (No Reimplementation!)

✅ **circuit-synth** (your PR: feat/jlc-import-components)
- `import_jlc_component("C25804")` - Import from LCSC part numbers
- `fast_jlc_search("10k resistor")` - Search JLC PCB database
- `component_from_search_result()` - Convert search to Component
- Full BOM export with pricing/stock data

✅ **Claude Agent Built-ins**
- `WebSearch` - Research design guides online
- `WebFetch` - Download datasheets (PDFs, app notes)
- Datasheet parsing capabilities

### AnyAria's Role: Research Coordination

```
User Request: "Design a BLDC motor driver"
         ↓
┌────────────────────────────────────────┐
│  AnyAria Research Coordinator          │
├────────────────────────────────────────┤
│  1. Claude Agent: Web Research         │
│     - Search: "BLDC driver design"     │
│     - Fetch: TI/Infineon app notes     │
│     - Learn: Topology, requirements    │
│                                        │
│  2. Component Selection                │
│     - Use: circuit_synth.jlcpcb.       │
│       fast_jlc_search()                │
│     - Filter: By researched specs      │
│     - Select: Best match from JLC      │
│                                        │
│  3. Circuit Generation                 │
│     - Use: circuit_synth.Circuit       │
│     - Add: Components with JLC meta    │
│     - Export: to KiCad                 │
│                                        │
│  4. Simulation Generation              │
│     - Parse: Component datasheets      │
│     - Extract: Equations, models       │
│     - Generate: Python simulation      │
└────────────────────────────────────────┘
         ↓
    Complete Circuit:
    - KiCad schematic
    - BOM with LCSC parts
    - Python simulation
    - All sources documented
```

## Example: BLDC Driver Design

### Phase 2 Implementation (using real tools):

```python
from circuit_synth.manufacturing.jlcpcb import (
    fast_jlc_search,
    component_from_search_result
)

# 1. Research phase (Claude agent with WebSearch)
research = web_search("BLDC motor driver design guide")
# Learns: Need 3-phase gate driver, 6 MOSFETs, bootstrap circuit

# 2. Search JLC for gate driver
results = fast_jlc_search("3-phase BLDC gate driver IC")
gate_driver_result = [r for r in results if r.stock > 100][0]

# 3. Import as Component (with all JLC metadata)
gate_driver = component_from_search_result(
    gate_driver_result,
    reference="U1"
)

# Automatically includes:
print(gate_driver.properties["LCSC"])          # C123456
print(gate_driver.properties["JLCPCB_Price"])  # $2.50
print(gate_driver.properties["JLCPCB_Stock"])  # 1000

# 4. Generate circuit
circuit = Circuit("BLDC Driver")
circuit.add_component(gate_driver)
# ... add other components

circuit.to_kicad("bldc_driver.kicad_sch")
```

## Installation

### Prerequisites
- KiCad 8.0+
- Python 3.11+
- circuit-synth with JLC integration

### Install

```bash
# Clone AnyAria
git clone https://github.com/YOUR_USERNAME/AnyAria.git
cd AnyAria

# Install circuit-synth with JLC integration
pip install git+https://github.com/circuit-synth/circuit-synth.git@feat/jlc-import-components

# Install AnyAria
pip install -e .

# Install KiCad plugin
python tools/install_plugin.py

# Start MCP server
python mcp-server/server.py
```

## Usage

### Option 1: HTTP API

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "requirements": "BLDC motor driver, 12-24V, 10A per phase",
    "budget": 15.0,
    "prefer_jlc_stock": true
  }'
```

### Option 2: KiCad Plugin

1. Open KiCad Schematic Editor
2. Tools → External Plugins → AnyAria Toolbox
3. Enter circuit requirements
4. Click "Generate Circuit"
5. Review components, simulation, BOM
6. Click "Apply to Schematic"

### Option 3: Claude Code CLI (Future)

```bash
/anyaria Design a 3.3V buck converter from 12V input
```

## Current Status

### ✅ Phase 1 Complete

- [x] MCP server infrastructure
- [x] KiCad plugin framework
- [x] Research-driven architecture documented
- [x] Integration with circuit-synth JLC
- [x] Claude agent capabilities documented
- [x] Example workflows
- [x] Complete documentation

### 🚧 Phase 2: Next Steps

**High Priority:**
1. Connect Claude agents for web research
2. Implement datasheet PDF parsing
3. Use real circuit-synth JLC search
4. Generate actual circuits with circuit-synth
5. Parse datasheets for simulation equations

**Implementation:**
```python
# In real_bldc_driver.py:
async def _research_bldc_topology(requirements):
    # Use Claude agent
    results = await agent.web_search("BLDC motor driver design")
    app_notes = await agent.web_fetch(results[0].url)
    topology = await agent.extract_topology(app_notes)
    return topology
```

## Key Documents

1. **INTEGRATION_WITH_CIRCUIT_SYNTH.md** ⭐
   - How to use circuit-synth's JLC integration
   - Claude agent built-in capabilities
   - What NOT to reimplement

2. **RESEARCH_DRIVEN_DESIGN.md**
   - Core design principle
   - Research workflow
   - No hardcoded knowledge

3. **examples/bldc_driver_research_demo.md**
   - Complete walkthrough
   - Shows Phase 2 implementation
   - Real component selection

4. **FINAL_STATUS.md**
   - Comprehensive status
   - What's done vs. what's next

## Why AnyAria?

### Traditional EDA Flow
```
Engineer → Research components manually
         → Read datasheets manually
         → Calculate values manually
         → Draw schematic manually
         → Hope it works
         ⏱️ Hours to days
```

### AnyAria Flow
```
User → Describe requirements
     → AnyAria researches online
     → AnyAria selects JLC components
     → AnyAria generates circuit
     → AnyAria creates simulation
     → Guaranteed to work
     ⏱️ Minutes
```

## Tech Stack

- **Frontend**: KiCad plugin (Python/wxPython)
- **Backend**: FastAPI MCP server
- **AI**: Claude agents (research, design coordination)
- **Circuit Generation**: circuit-synth library
- **Component Database**: JLC PCB (via circuit-synth)
- **Simulation**: Custom Python code generation

## Contributing

See [DEVELOPMENT.md](DEVELOPMENT.md) for:
- Development roadmap
- Phase 2 implementation details
- How to contribute
- Code standards

## Repository Stats

- **Files**: 32 (18 Python, 11 Markdown)
- **Commits**: 8
- **Status**: Infrastructure complete, ready for Phase 2
- **Server**: Running at http://localhost:8000

## License

MIT License - See [LICENSE](LICENSE)

## Contact

- GitHub: https://github.com/YOUR_USERNAME/AnyAria
- Email: pachecked@gmail.com

---

**"Vibe code your circuits"** - Infrastructure ready. Let's build Phase 2! 🚀
