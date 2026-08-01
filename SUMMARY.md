# AnyAria - Project Summary

## What is AnyAria?

AnyAria is an **AI-powered circuit design tool** that integrates Claude directly into KiCad. It enables "vibe coding" for circuits - describe what you want, and AnyAria designs the complete circuit with component selection, simulation, and verification.

## Key Features

### 🤖 AI Circuit Design
- Describe circuit requirements in natural language
- Claude generates block diagram and architecture
- Automatic component selection from JLC PCB (with stock/pricing)

### 📚 Datasheet Intelligence
- Agents read component datasheets
- Extract typical application circuits
- Apply design equations automatically
- Tune component values to meet specifications

### 🔬 Integrated Simulation
- Python simulation code generated for each block
- Equations from datasheets
- Component derating (voltage, current, temperature)
- Interactive modification via Claude

### 🎨 Interactive Visualization
- Click nets to see signal flow
- View/edit simulation code
- Block diagram with power analysis
- BOM with real-time pricing

## Architecture

```
┌──────────────────────────────────────────┐
│  KiCad (Standard EDA Tool)               │
│  + AnyAria Plugin (Python)               │
│    └─ Toolbox UI (wxPython)              │
└───────────────┬──────────────────────────┘
                │ HTTP
┌───────────────▼──────────────────────────┐
│  MCP Server (FastAPI)                    │
│  ├─ /generate - Circuit generation       │
│  ├─ /simulate - Run simulation           │
│  └─ /jlc/search - Component search       │
└───────────────┬──────────────────────────┘
                │
┌───────────────▼──────────────────────────┐
│  Claude Agents (Parallel Research)       │
│  ├─ Datasheet Reader                     │
│  ├─ Component Finder (JLC PCB)           │
│  └─ Circuit Simulator                    │
└──────────────────────────────────────────┘
                │
┌───────────────▼──────────────────────────┐
│  Libraries                               │
│  ├─ circuit-synth (KiCad generation)     │
│  └─ kicad-sch-api (File I/O)             │
└──────────────────────────────────────────┘
```

## Example Workflow

### User Request
```
/anyaria Design a 3.3V buck converter, 2A output, from 12V input, <$5 BOM
```

### AnyAria Process

**Step 1: Parse Requirements (2 min)**
- Input: 12V
- Output: 3.3V @ 2A
- Budget: $5
- Prefer JLC stock

**Step 2: Generate Block Diagram (3 min)**
```
VIN (12V) → [Buck IC] → [Inductor] → [Cap] → VOUT (3.3V @ 2A)
              ↓ Feedback
              [Voltage Divider]
```

**Step 3: Research Components (5 min, parallel agents)**
- Agent 1: Find buck converter IC (TPS54331, $0.87, in stock)
- Agent 2: Find passives (L=22µH, C=47µF, from JLC)
- Agent 3: Read TPS54331 datasheet, extract equations

**Step 4: Generate Circuit (3 min)**
- Use circuit-synth to create KiCad schematic
- Apply typical application circuit from datasheet
- Add feedback network for 3.3V output

**Step 5: Generate Simulation (4 min)**
```python
class BuckConverter_U1:
    def __init__(self):
        self.Vin = 12.0
        self.Vout = 3.3
        self.L = 22e-6  # From datasheet equation
        self.C = 47e-6
        
    def efficiency(self):
        return 0.87  # From datasheet curves
        
    def output_ripple(self):
        # Using datasheet equation
        dI_L = (self.Vin - self.Vout) * self.Vout / (self.L * self.fs * self.Vin)
        return dI_L * ESR
```

**Step 6: Tune Values (3 min)**
- Iterate L, C values
- Verify ripple < 50mV
- Check efficiency > 85%
- Confirm thermal performance

**Step 7: Verify (2 min)**
- ✓ Voltage derating OK
- ✓ Thermal analysis passed
- ✓ All parts in stock at JLC
- ✓ BOM = $1.47 (within budget)

### Output

```markdown
## Buck Converter 12V → 3.3V @ 2A

**BOM:** $1.47
**Efficiency:** 87%
**Output Ripple:** 4.2mV

Components:
- U1: TPS54331 ($0.87, JLC C12345)
- L1: 22µH inductor ($0.15, JLC C67890)
- C_OUT: 47µF ceramic ($0.08, JLC C11223)

✓ All requirements met
✓ Ready to apply to schematic
```

## Current Status

**Phase 1 Complete:** Core infrastructure
- ✓ KiCad plugin framework
- ✓ MCP server
- ✓ Claude skill definition
- ✓ Stub implementations

**Next Phase:** Circuit generation
- Circuit templates
- circuit-synth integration
- Requirements parser with Claude

## Installation

```bash
git clone https://github.com/circuit-synth/AnyAria.git
cd AnyAria
pip install -e .
python tools/install_plugin.py
python mcp-server/server.py
```

See [QUICKSTART.md](QUICKSTART.md) for details.

## Technology Stack

- **Frontend:** KiCad plugin (Python/wxPython)
- **Backend:** FastAPI MCP server
- **AI:** Claude via MCP protocol
- **Circuit Gen:** circuit-synth library
- **Simulation:** Custom Python code generation
- **Components:** JLC PCB database integration

## Files Created

```
AnyAria/
├── README.md                  # Main documentation
├── QUICKSTART.md              # Getting started guide
├── DEVELOPMENT.md             # Development roadmap
├── LICENSE                    # MIT license
├── pyproject.toml             # Python package config
├── .gitignore                 # Git ignore rules
│
├── kicad-plugin/              # KiCad integration
│   ├── anyaria_plugin.py      # Plugin entry point
│   └── toolbox/               # UI components
│
├── mcp-server/                # FastAPI server
│   └── server.py              # Main server
│
├── skills/                    # Claude skills
│   └── circuit-design/        # Main skill definition
│
├── agents/                    # Specialized agents
│   ├── datasheet-reader/      # PDF parsing
│   ├── component-finder/      # JLC search
│   └── circuit-simulator/     # Simulation gen
│
├── src/anyaria/               # Core library
│   ├── core/
│   │   ├── circuit_generator.py
│   │   ├── component_research.py
│   │   └── plugin_interface.py
│   └── simulation/
│       └── builder.py
│
├── tests/                     # Test suite
│   ├── test_circuit_generator.py
│   ├── test_component_research.py
│   └── test_simulation_builder.py
│
└── tools/                     # Utilities
    └── install_plugin.py      # Plugin installer
```

## Vision

**"Vibe code your circuits"**

Just as Claude Code lets you describe software and get working code, AnyAria lets you describe circuits and get working hardware designs - complete with component selection, simulation, and verification.

## Next Steps

1. Implement requirements parser using Claude
2. Integrate circuit-synth for KiCad generation
3. Build JLC PCB API integration
4. Create datasheet reading agent
5. Generate working simulations

See [DEVELOPMENT.md](DEVELOPMENT.md) for full roadmap.

## License

MIT License - See [LICENSE](LICENSE)

## Contact

- GitHub: https://github.com/circuit-synth/AnyAria
- Email: pachecked@gmail.com
