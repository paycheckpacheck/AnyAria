# Simplified Architecture - No MCP Server Needed!

## The Real Workflow

```
User: "Design a BLDC motor driver"
   ↓
Claude (main agent):
  - Creates plan
  - Identifies blocks needed
  - Launches Workflow
   ↓
┌─────────────────────────────────────────────────────────┐
│ Workflow: BLDC Driver Design                            │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ Phase 1: Research Blocks (Parallel)                     │
│   Agent 1: Research gate driver requirements            │
│     - WebSearch: "3-phase BLDC gate driver"             │
│     - WebFetch: TI app note PDF                         │
│     - Returns: Specs, topology                          │
│                                                          │
│   Agent 2: Research MOSFET requirements                 │
│     - WebSearch: "motor driver MOSFET selection"        │
│     - Returns: Voltage, current, Rds specs              │
│                                                          │
│   Agent 3: Research current sensing                     │
│     - WebSearch: "motor current sensing methods"        │
│     - Returns: Shunt resistor approach                  │
│                                                          │
│ Phase 2: Find Components (Parallel)                     │
│   Agent 4: Find gate driver on JLC                      │
│     - Uses circuit_synth.jlcpcb.fast_jlc_search()       │
│     - WebFetch: IR2130 datasheet                        │
│     - Returns: Component with equations                 │
│                                                          │
│   Agent 5: Find MOSFETs on JLC                          │
│     - Uses circuit_synth.jlcpcb.fast_jlc_search()       │
│     - WebFetch: IRFB4115 datasheet                      │
│     - Returns: Component with thermal data              │
│                                                          │
│ Phase 3: Generate Circuit                               │
│   Main agent synthesizes results:                       │
│     - Uses circuit_synth.Circuit API                    │
│     - Adds components from Phase 2                      │
│     - Generates netlist from topology                   │
│     - Exports to KiCad                                  │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## What We Actually Need

### 1. Claude Skill (Just a Skill!)

```python
# .claude/skills/anyaria.md
---
name: anyaria
description: Design circuits using AI research and JLC components
---

When user asks to design a circuit:

1. Parse requirements using Claude
2. Create block diagram
3. Launch Workflow to research and find components
4. Generate circuit using circuit-synth
5. Return KiCad file + BOM
```

### 2. Workflow Script

```javascript
// Design BLDC driver with parallel agent research
export const meta = {
  name: 'design-bldc-driver',
  description: 'Research and generate BLDC driver circuit',
  phases: [
    { title: 'Research Blocks' },
    { title: 'Find Components' },
    { title: 'Generate Circuit' }
  ]
}

// Phase 1: Research what each block needs (parallel)
phase('Research Blocks')
const blockResearch = await parallel([
  () => agent('Research 3-phase gate driver requirements', {
    schema: BLOCK_REQUIREMENTS_SCHEMA
  }),
  () => agent('Research MOSFET requirements for 10A motor', {
    schema: BLOCK_REQUIREMENTS_SCHEMA
  }),
  () => agent('Research current sensing methods for motors', {
    schema: BLOCK_REQUIREMENTS_SCHEMA
  })
])

// Phase 2: Find components on JLC (parallel, each can fan out)
phase('Find Components')
const components = await parallel(
  blockResearch.map(block => () =>
    agent(`Find ${block.component_type} on JLC PCB matching: ${block.specs}`, {
      schema: COMPONENT_SCHEMA
    })
  )
)

// Phase 3: Generate circuit
phase('Generate Circuit')
const circuit = await agent('Generate KiCad circuit from components', {
  schema: CIRCUIT_SCHEMA
})

return { circuit, components, bom: calculateBOM(components) }
```

### 3. Agent Tools (Already Available!)

Each agent has access to:
- `WebSearch` - Research design guides
- `WebFetch` - Download datasheets
- `Read` - Parse local files
- `Bash` - Run circuit-synth Python scripts
- `ToolSearch` - Find MCP tools (like circuit-synth integration)

### 4. Circuit Generation (Pure Python)

```python
# agents/generate-circuit.py
from circuit_synth import Circuit
from circuit_synth.manufacturing.jlcpcb import import_jlc_component

# Read component data from agent research
with open('components.json') as f:
    components = json.load(f)

# Create circuit
circuit = Circuit("BLDC Driver")

# Import JLC components
for comp in components:
    c = import_jlc_component(comp['lcsc'], reference=comp['ref'])
    circuit.add_component(c)

# Add nets based on topology
# (learned from agent research)
circuit.add_net(...)

# Export
circuit.to_kicad("bldc_driver.kicad_sch")
```

## No HTTP Server Needed!

**Before (Overcomplicated)**:
```
User → KiCad Plugin → HTTP → MCP Server → Claude Agents
```

**After (Simple)**:
```
User → Claude Skill → Workflow → Agents → circuit-synth
```

## The Skill Implementation

```markdown
# .claude/skills/anyaria.md

When user says: "Design a [circuit type]"

Step 1: Parse requirements
  - Use Claude to understand: voltage, current, specs, budget
  
Step 2: Launch workflow to research and design
  - Workflow fans out agents to:
    - Research topology online
    - Find components on JLC
    - Read datasheets
    - Calculate values
    
Step 3: Generate circuit
  - Use circuit-synth Python API
  - Create KiCad schematic
  - Export BOM with LCSC parts
  
Step 4: Return results
  - Path to .kicad_sch file
  - BOM with pricing
  - Simulation code
```

## Example Usage

```bash
# User just talks to Claude Code CLI
claude "Design a BLDC motor driver, 12-24V input, 10A per phase"

# Claude:
# 1. Understands requirements
# 2. Launches workflow (background)
# 3. Agents research and find components
# 4. Generates circuit with circuit-synth
# 5. Returns: bldc_driver.kicad_sch + BOM + simulation
```

## What Gets Removed

❌ MCP Server (FastAPI)
❌ HTTP endpoints
❌ KiCad plugin UI (just open the generated .kicad_sch)
❌ Complex infrastructure

## What Stays

✅ Claude Skill (.claude/skills/anyaria.md)
✅ Workflow scripts (for parallel agent orchestration)
✅ Agent definitions (research, component finding)
✅ circuit-synth integration (for actual generation)
✅ Documentation (principles remain the same)

## The Beauty

It's **just Claude talking to Claude** - no servers, no HTTP, no complexity.

The entire system is:
1. A skill file
2. A workflow script
3. Python scripts that use circuit-synth
4. Agents that use WebSearch/WebFetch

That's it!
