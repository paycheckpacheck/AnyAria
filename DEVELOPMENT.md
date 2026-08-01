# AnyAria Development Guide

Development roadmap and contribution guidelines.

## Development Roadmap

### Phase 1: Core Infrastructure ✓ (Current)

- [x] Project structure
- [x] KiCad plugin framework
- [x] MCP server skeleton
- [x] Claude skill definition
- [x] Stub implementations
- [x] Installation scripts

### Phase 2: Circuit Generation (Next)

- [ ] Requirements parser (use Claude to parse natural language)
- [ ] Block diagram generator
- [ ] circuit-synth integration
- [ ] Basic circuit templates (buck, LDO, voltage divider)
- [ ] Test with simple circuits

### Phase 3: Component Research

- [ ] JLC PCB API integration
- [ ] Component search by specs
- [ ] Stock/pricing integration
- [ ] Datasheet downloading
- [ ] PDF parsing (extract text, images, tables)
- [ ] Agent for datasheet reading
- [ ] Equation extraction
- [ ] Typical application circuit extraction

### Phase 4: Simulation

- [ ] Python code generation for blocks
- [ ] Equation-based models
- [ ] Component value tuning algorithm
- [ ] Derating calculations
- [ ] Thermal analysis
- [ ] Signal flow simulation
- [ ] Interactive simulation in UI

### Phase 5: UI Enhancements

- [ ] Net signal visualization (plots)
- [ ] Interactive block diagram
- [ ] Live simulation editing
- [ ] Claude chat integration for modifications
- [ ] BOM optimization UI
- [ ] Export to various formats

### Phase 6: Advanced Features

- [ ] Multi-board designs
- [ ] PCB layout integration
- [ ] EMI/EMC analysis
- [ ] Safety review (overvoltage, overcurrent)
- [ ] Cost optimization
- [ ] Alternative component suggestions
- [ ] Design rule checking

## Development Setup

### Prerequisites

- Python 3.11+
- KiCad 8.0+
- Git

### Clone with Dependencies

```bash
git clone https://github.com/circuit-synth/AnyAria.git
cd AnyAria

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest
```

### Development Workflow

1. Create a feature branch
2. Implement feature with tests
3. Run full test suite
4. Update documentation
5. Create pull request

### Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=src/anyaria --cov-report=html

# Run specific test
pytest tests/test_circuit_generator.py -v

# Watch mode
pytest-watch
```

### Code Quality

```bash
# Format code
black src/ tests/
isort src/ tests/

# Type checking
mypy src/

# Linting
ruff check src/ tests/

# Security scan
bandit -r src/
```

### Running MCP Server in Development

```bash
# Development mode with auto-reload
python mcp-server/server.py --dev

# Or with uvicorn directly
uvicorn mcp-server.server:app --reload --port 8000
```

### Testing KiCad Plugin

```bash
# Install plugin in development mode (creates symlink)
python tools/install_plugin.py

# Reload in KiCad without restarting
# In KiCad Scripting Console:
exec(open('tools/reload_plugin.py').read())
```

## Architecture Details

### KiCad Plugin

- `anyaria_plugin.py` - Main plugin entry point (registered with KiCad)
- `plugin_interface.py` - Toolbox UI (wxPython dialog)
- Communicates with MCP server via HTTP

### MCP Server

- FastAPI application
- Endpoints for circuit generation, simulation, JLC search
- Spawns Claude agents for research
- Uses circuit-synth for KiCad generation

### Claude Agents

Located in `agents/`:
- `datasheet-reader/` - PDF parsing and equation extraction
- `component-finder/` - JLC PCB search and filtering
- `circuit-simulator/` - Simulation code generation

### Circuit Generation Pipeline

1. **Parse requirements** - Natural language → structured data
2. **Create blocks** - High-level architecture
3. **Research components** - Fan out agents
4. **Generate circuit** - circuit-synth integration
5. **Generate simulation** - Python code with equations
6. **Tune values** - Iterative optimization
7. **Verify** - Derating, thermal, requirements

## Contributing

### Issue Tracking

Use GitHub issues for:
- Bug reports
- Feature requests
- Documentation improvements
- Questions

### Pull Request Process

1. Fork repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

### Coding Standards

- Follow PEP 8
- Type hints for all functions
- Docstrings for public APIs
- Tests for new features
- Update documentation

### Commit Messages

```
type(scope): short description

Longer explanation if needed.

Fixes #123
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

## Key Design Decisions

### Why KiCad Plugin?

- Professional EDA tool
- Python scripting support
- Open source
- Industry-standard file formats

### Why circuit-synth?

- Designed for programmatic circuit generation
- Already integrates with KiCad
- Active development
- Clean Python API

### Why FastAPI for MCP Server?

- Modern async framework
- Automatic API documentation
- Fast development
- Easy deployment

### Why Python Simulation?

- Easy to generate code
- User can modify directly
- No license restrictions
- Fast iteration

## Future Directions

- Web-based version (no KiCad install needed)
- Cloud deployment of MCP server
- Collaborative design features
- Component database expansion
- Integration with more EDA tools
- Machine learning for component selection

## Questions?

Open an issue or email pachecked@gmail.com
