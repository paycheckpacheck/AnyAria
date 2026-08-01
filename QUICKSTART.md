# AnyAria Quick Start

Get started with AI-powered circuit design in 5 minutes.

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/circuit-synth/AnyAria.git
cd AnyAria
```

### 2. Install Python Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install AnyAria
pip install -e .
```

### 3. Install KiCad Plugin

```bash
python tools/install_plugin.py
```

This will symlink (or copy) the plugin into your KiCad plugins directory.

### 4. Start MCP Server

```bash
python mcp-server/server.py
```

Leave this running in a terminal.

## Usage

### Option 1: KiCad Plugin (GUI)

1. Open KiCad (restart if it was already running)
2. Open PCB Editor or Schematic Editor
3. Tools → External Plugins → AnyAria Toolbox
4. Enter circuit requirements in the text box:
   ```
   Design a 3.3V buck converter
   Input: 12V
   Output: 2A max
   Budget: <$5
   Use JLC PCB components in stock
   ```
5. Click "Generate Circuit"
6. Review block diagram, component research, and simulation
7. Click "Apply to Schematic"

### Option 2: Claude Code CLI

If you have Claude Code CLI installed:

```bash
# Use the circuit design skill
claude "/anyaria Design a 3.3V buck converter, 2A output, from 12V input, <$5 BOM"
```

## Project Status

AnyAria is currently in **early alpha**. Current status:

✓ Project structure
✓ KiCad plugin framework  
✓ MCP server framework
✓ Claude skill definition
⚠️ Circuit generation (stub)
⚠️ Component research (stub)
⚠️ JLC PCB integration (stub)
⚠️ Datasheet reading (stub)
⚠️ Simulation generation (stub)

## Next Steps

See [DEVELOPMENT.md](DEVELOPMENT.md) for development roadmap.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      KiCad (with AnyAria Plugin)             │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ Toolbox UI │  │ Net Viz      │  │ Sim Editor   │        │
│  └─────┬──────┘  └──────────────┘  └──────────────┘        │
└────────┼───────────────────────────────────────────────────┘
         │ HTTP
         ▼
┌─────────────────────────────────────────────────────────────┐
│                      MCP Server (FastAPI)                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  /generate - Main circuit generation endpoint          │ │
│  │  /simulate - Run Python simulation                     │ │
│  │  /jlc/search - Search JLC PCB database                 │ │
│  └────────────────────────────────────────────────────────┘ │
└────────┬──────────────────────────┬─────────────────────────┘
         │                          │
         ▼                          ▼
┌──────────────────────┐   ┌──────────────────────┐
│  Claude Agents       │   │  Libraries           │
│  ┌────────────────┐  │   │  ┌────────────────┐  │
│  │ Datasheet      │  │   │  │ circuit-synth  │  │
│  │ Reader         │  │   │  │ (KiCad gen)    │  │
│  ├────────────────┤  │   │  ├────────────────┤  │
│  │ Component      │  │   │  │ kicad-sch-api  │  │
│  │ Finder         │  │   │  │ (File I/O)     │  │
│  ├────────────────┤  │   │  └────────────────┘  │
│  │ Circuit        │  │   │                      │
│  │ Simulator      │  │   └──────────────────────┘
│  └────────────────┘  │
└──────────────────────┘
```

## Example Output

When you ask AnyAria to design a circuit, you get:

1. **Block Diagram**: High-level architecture
2. **Component Research**: Datasheets, equations, JLC parts
3. **Python Simulation**: Runnable code with tuned values
4. **Net Signals**: Voltage/current for each net
5. **BOM**: Complete bill of materials with prices
6. **Verification**: Derating, thermal, requirements met

## Troubleshooting

**Plugin doesn't appear in KiCad**
- Make sure you restarted KiCad after installation
- Check Tools → External Plugins menu
- Verify plugin directory: `python tools/install_plugin.py` shows the path

**MCP server won't start**
- Check that port 8000 is not in use
- Install dependencies: `pip install -e .`
- Check logs for errors

**Circuit generation fails**
- Ensure MCP server is running (http://localhost:8000)
- Check server logs for errors
- Stub implementations are expected in alpha - see Project Status

## Get Help

- GitHub Issues: https://github.com/circuit-synth/AnyAria/issues
- Email: pachecked@gmail.com
