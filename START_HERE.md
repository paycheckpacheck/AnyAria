# Start Using AnyAria

AnyAria is now running! Here's how to use it:

## ✅ Server is Running

The MCP server is running at: **http://localhost:8000**

Test it:
```bash
curl http://localhost:8000/
```

Should return:
```json
{"status":"running","service":"AnyAria MCP Server","version":"0.1.0"}
```

## 🚀 Quick Start

### Option 1: API (Working Now)

Generate a circuit via HTTP:

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "requirements": "Design a 3.3V LDO from 5V input, 500mA output",
    "budget": 5.0,
    "prefer_jlc_stock": true
  }'
```

Returns:
- Block diagram
- Component research (with JLC parts)
- Python simulation code
- BOM with pricing
- Verification results

### Option 2: KiCad Plugin (Setup Required)

1. Install the plugin:
   ```bash
   python tools/install_plugin.py
   ```

2. Restart KiCad

3. Open KiCad Schematic Editor

4. Tools → External Plugins → AnyAria Toolbox

5. Enter requirements and click "Generate Circuit"

### Option 3: Claude Code CLI (Coming Soon)

```bash
/anyaria Design a 3.3V buck converter from 12V
```

## 📋 What Works Now (Alpha)

✅ **MCP Server Running**
- FastAPI server on port 8000
- Circuit generation endpoint
- Simulation endpoint
- JLC search endpoint (stub)

✅ **Stub Circuit Generation**
- Parses requirements
- Creates block diagram
- Returns component suggestions
- Generates Python simulation code

✅ **KiCad Plugin Framework**
- UI built (wxPython)
- HTTP client for MCP server
- Simulation code editor
- Net signal viewer

## 🚧 What's Coming Next

The current implementation uses **stub data** - it returns example circuits, not real designs.

**Phase 2** will implement:
1. Real requirements parsing (using Claude)
2. JLC PCB API integration
3. Datasheet reading agents
4. circuit-synth integration for KiCad generation
5. Real component value tuning

See [DEVELOPMENT.md](DEVELOPMENT.md) for full roadmap.

## 🧪 Try the API

### Example 1: Buck Converter

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "requirements": "12V to 3.3V buck converter, 2A output, <$5 BOM",
    "budget": 5.0,
    "prefer_jlc_stock": true
  }' | json_pp
```

### Example 2: LDO Regulator

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "requirements": "5V to 3.3V LDO, 500mA, low dropout",
    "budget": 2.0,
    "prefer_jlc_stock": true
  }' | json_pp
```

## 📝 Response Format

The API returns:

```json
{
  "block_diagram": "[Buck IC] → [Inductor] → [Cap] → VOUT",
  "component_research": [
    {
      "component": "Buck Converter IC - TPS54331",
      "analysis": "Suitable for 12V to 3.3V @ 2A",
      "datasheet_url": "https://...",
      "equations": ["L = (Vout * (Vin - Vout)) / (fs * dI_L * Vin)"],
      "jlc_part": "C12345",
      "price": 0.87,
      "in_stock": true
    }
  ],
  "simulation_code": "class BuckConverter:\n    def __init__(self):\n    ...",
  "nets": [],
  "bom": [],
  "total_cost": 0.0,
  "verification": {
    "meets_requirements": true,
    "derating_ok": true,
    "thermal_ok": true
  }
}
```

## 🛠️ Development

To work on AnyAria:

```bash
# Make changes to code
vim src/anyaria/core/circuit_generator.py

# Restart server (Ctrl+C and rerun)
python -m uvicorn mcp-server.server:app --reload

# Test changes
curl -X POST http://localhost:8000/generate ...
```

## 📚 Documentation

- [README.md](README.md) - Overview and architecture
- [QUICKSTART.md](QUICKSTART.md) - Installation guide
- [DEVELOPMENT.md](DEVELOPMENT.md) - Development roadmap
- [SUMMARY.md](SUMMARY.md) - Project summary

## 🐛 Troubleshooting

**Server won't start**
- Check port 8000 is not in use: `netstat -an | grep 8000`
- Check Python version: `python --version` (need 3.11+)
- Reinstall dependencies: `pip install -e .`

**Plugin doesn't appear in KiCad**
- Run `python tools/install_plugin.py` again
- Check the path it reports
- Restart KiCad completely

**API returns errors**
- Check server logs
- Current implementation uses stubs - some features not implemented yet

## 💡 Next Steps

1. **Try the API** - Generate some example circuits
2. **Install KiCad plugin** - Use the graphical interface
3. **Read DEVELOPMENT.md** - See what's coming next
4. **Contribute** - Help implement Phase 2 features!

---

**"Vibe code your circuits"** - Describe what you want, AnyAria designs it.
