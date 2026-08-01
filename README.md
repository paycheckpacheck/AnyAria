# AnyAria - AI-Powered Circuit Design for KiCad

AnyAria extends KiCad with AI-driven circuit design capabilities powered by Claude. Design circuits by describing requirements - AnyAria handles component selection, datasheet research, circuit generation, and simulation.

## Features

- **AI Circuit Design**: Describe your requirements, get complete circuits
- **Smart Component Selection**: Auto-select components from JLC PCB with stock/pricing
- **Datasheet-Driven Design**: Agents read datasheets and apply typical application circuits
- **Python Simulation**: Each component gets simulation code, tune values automatically
- **Interactive Net Visualization**: Click nets to see signals through simulation
- **Integrated Toolbox**: Claude skill accessible directly in KiCad

## Architecture

```
AnyAria/
├── kicad-plugin/          # KiCad Action Plugin (Python)
│   ├── anyaria_plugin.py  # Main plugin entry point
│   ├── toolbox/           # Claude-integrated toolbox UI
│   └── icon.png           # Plugin icon
├── skills/                # Claude skills
│   └── circuit-design/    # AI circuit design skill
├── agents/                # Specialized agents
│   ├── datasheet-reader/  # Datasheet extraction agent
│   ├── component-finder/  # JLC PCB component search
│   └── circuit-simulator/ # Python simulation generator
├── mcp-server/            # MCP server for Claude integration
└── examples/              # Example circuits
```

## Installation

### Prerequisites
- KiCad 8.0+
- Python 3.11+
- Claude Code CLI

### Install Plugin

```bash
# Clone repository
git clone https://github.com/circuit-synth/AnyAria.git
cd AnyAria

# Install dependencies
pip install -e .

# Link plugin to KiCad
python tools/install_plugin.py
```

### Start MCP Server

```bash
# Start AnyAria MCP server for Claude integration
python mcp-server/server.py
```

## Usage

### In KiCad

1. Open KiCad PCB Editor or Schematic Editor
2. Tools → External Plugins → AnyAria Toolbox
3. Describe your circuit requirements
4. Click "Generate Circuit"
5. Review block diagram, datasheets, and simulation
6. Click "Apply to Schematic"

### With Claude Code

```bash
# Use the circuit design skill
/anyaria "Design a 3.3V buck converter, 2A output, from 12V input, <$5 BOM"
```

## Circuit Design Workflow

1. **Requirements Analysis**: Parse voltage, current, FOMs, budget constraints
2. **Block Diagram**: Generate high-level architecture
3. **Component Research**: 
   - Search JLC PCB for suitable components
   - Fan out agents to read datasheets
   - Extract equations, typical circuits, ratings
4. **Circuit Generation**: 
   - Adapt typical application circuits
   - Use circuit-synth to generate KiCad schematic
5. **Simulation**:
   - Create Python simulation for each block
   - Tune component values to meet requirements
   - Derate for temperature and power
6. **Validation**: Verify against requirements

## Component Simulation

Each component gets Python simulation code:

```python
# Automatically generated for each component
class BuckConverter_U1:
    def __init__(self):
        self.L1 = 22e-6  # 22µH inductor
        self.C1 = 47e-6  # 47µF capacitor
        self.Vin = 12.0
        self.Vout = 3.3
        self.Iout_max = 2.0
        
    def simulate(self, input_signal):
        # Equations from datasheet
        output_signal = self._switching_regulator_model(input_signal)
        return output_signal
```

## Net Visualization

Click any net in the schematic to see:
- Signal waveform at that point
- Component transfer functions
- Simulation code for that block
- Modify simulation parameters live

## Development

```bash
# Run tests
pytest tests/

# Start development MCP server
python mcp-server/server.py --dev

# Reload plugin in KiCad
Tools → Scripting Console → exec(open('reload_plugin.py').read())
```

## Dependencies

- `circuit-synth` - Circuit generation library
- `kicad-sch-api` - KiCad schematic API
- FastAPI - MCP server
- PySpice - Circuit simulation

## License

MIT License - See LICENSE file

## Contributing

See CONTRIBUTING.md for development guidelines.

---

**"Vibe code your circuits"** - Describe what you want, AnyAria designs it.
