export const meta = {
  name: 'build-llc-converter-48v-12v',
  description: 'Design discrete current-mode LLC converter: 11 blocks → review → simulate → integrate → generate KiCad',
  phases: [
    { title: 'Design Blocks', detail: '11 blocks in parallel, each → reviewer → simulator' },
    { title: 'Integrate', detail: 'Compose blocks, generate KiCad project, layout schematics' },
    { title: 'Verify', detail: 'Run all project checks, render schematics' },
  ],
}

// Phase 1: Design all blocks in parallel
phase('Design Blocks')

const spec = `
48V → 12V LLC resonant converter, 120W (10A output)
Discrete current-mode control (comparators, op-amps, VCO, slope compensation)
GaN FETs if available, else fast Si MOSFETs
All parts from JLCPCB catalog (except custom LLC transformer)
RP2040 for telemetry only (not control loop)
Target 95% efficiency (realistic 92-93%)
Business card size (may relax to 100mm × 80mm)

See: llc_48v_12v_120w/design/spec.md
     llc_48v_12v_120w/design/architecture.md
`

const blocks = [
  {
    name: 'INPUT_FILTER',
    prompt: `Design INPUT_FILTER block for LLC converter.
${spec}

Block requirements:
- Input: 48V DC (36-60V range)
- TVS protection (58V breakdown)
- Bulk input capacitors (low ESR electrolytic + ceramic)
- Input voltage sensing divider for RP2040 ADC
- EMI filtering if space allows
- Connector: 2-pin screw terminal or high-current header

Source ALL parts from JLCPCB using source-parts skill.
Then run block-reviewer, then block-simulator.
Return block contract (interface.json, parts.json, circuit Python).`
  },
  {
    name: 'PRIMARY_HALF_BRIDGE',
    prompt: `Design PRIMARY_HALF_BRIDGE block for LLC converter.
${spec}

Block requirements:
- 2× GaN FETs in half-bridge (Q1 high-side, Q2 low-side)
- Search JLCPCB for: "GaN FET 150V 8A" or fallback to "MOSFET 150V low Qg"
- Bootstrap capacitor for high-side gate drive
- Gate resistors (2-10Ω for GaN)
- Source-to-gate resistors (prevents floating gates)
- Snubber (optional, if needed for ringing)
- Connect to gate driver outputs (HO, LO, VS, VB, VCC, COM)

Source ALL parts from JLCPCB.
Then run block-reviewer, then block-simulator.
Return block contract.`
  },
  {
    name: 'LLC_RESONANT_TANK',
    prompt: `Design LLC_RESONANT_TANK block for LLC converter.
${spec}

Block requirements:
- Resonant capacitor Cr (film or C0G ceramic, ~50-100nF, 250V+)
- Resonant inductor Lr (~20-30µH, integrate with transformer leakage if possible)
- Current sense point (for current transformer or shunt)
- Connect to: half-bridge midpoint, transformer primary

Calculate resonant frequency: fr = 1/(2π√(Lr×Cr)) ≈ 250kHz
Quality factor Q ≈ 0.3-0.5 for good regulation range

Source ALL parts from JLCPCB. Film caps may be difficult - use C0G ceramic array if needed.
Then run block-reviewer, then block-simulator.
Return block contract.`
  },
  {
    name: 'LLC_TRANSFORMER_SPEC',
    prompt: `Specify LLC_TRANSFORMER for LLC converter (EXTERNAL SOURCING - NOT JLCPCB).
${spec}

Transformer specification:
- Turns ratio: 4:1 (48V primary → 12V secondary center-tap)
- Topology: Center-tapped secondary for synchronous rectification
- Resonant frequency: ~250kHz
- Magnetizing inductance Lm: ~100-150µH
- Leakage inductance: ~20-30µH (contributes to Lr)
- Power rating: 150W minimum
- Core: ETD29, E32, or PQ32 (ferrite N87, N97, or 3F3)
- Isolation: 1500V minimum
- Winding: Litz wire or foil for high frequency

DO NOT source from JLCPCB - this is a custom component.
Instead:
1. Calculate exact requirements (turns, wire gauge, core)
2. Write transformer specification document
3. Note in parts.json: "EXTERNAL - Coilcraft, Würth, or custom winder"
4. Create schematic symbol (generic transformer with specs in fields)

Run block-reviewer (verify calculations), then block-simulator (verify inductance values, turns ratio).
Return block contract with DEVIATION noted.`
  },
  {
    name: 'SECONDARY_RECTIFIER',
    prompt: `Design SECONDARY_RECTIFIER block for LLC converter.
${spec}

Block requirements:
- 2× Synchronous rectifier MOSFETs (center-tap configuration)
- Search JLCPCB for: "MOSFET N-channel 40V RDS(on) < 5mΩ high current"
- Gate drive: either dedicated SR controller OR driven from transformer sense
- Body diode protection (MOSFETs conduct during dead time)
- Source resistors for current sensing (optional)
- Connect to: transformer secondary center-tap, output filter

Calculate:
- RMS current per FET: ~7A (50% duty cycle)
- Conduction loss: I²RMS × RDS(on)
- Choose RDS(on) < 5mΩ for <0.25W loss per FET

Source ALL parts from JLCPCB.
Then run block-reviewer, then block-simulator.
Return block contract.`
  },
  {
    name: 'OUTPUT_FILTER',
    prompt: `Design OUTPUT_FILTER block for LLC converter.
${spec}

Block requirements:
- Output capacitors: low ESR electrolytics + ceramics in parallel
- Total capacitance: ~500-1000µF for 12V rail (minimize ripple)
- Output inductor (optional, if needed for ripple reduction)
- Output connector: 2-pin screw terminal or high-current header
- Calculate output ripple: ΔV = Iload/(f×C) < 100mV

Search JLCPCB for:
- Electrolytic: "aluminum electrolytic 1000µF 25V low ESR"
- Ceramic: "ceramic capacitor 47µF 25V X5R/X7R" (parallel several)

Source ALL parts from JLCPCB.
Then run block-reviewer, then block-simulator.
Return block contract.`
  },
  {
    name: 'OUTPUT_SENSE_PROTECT',
    prompt: `Design OUTPUT_SENSE_PROTECT block for LLC converter.
${spec}

Block requirements:
- Output voltage sensing divider (12V → 3.3V for RP2040 ADC)
- Output current sensing (shunt + op-amp, 0-10A → 0-3.3V)
- Overvoltage protection (comparator + crowbar or shutdown)
- Feedback to optocoupler (for current-mode control loop)
- Temperature sensing (thermistor near power components)

Search JLCPCB for:
- Shunt resistor: "current sense resistor 10mΩ 1% 2W"
- Op-amp: LM358 or INA180 current sense amp
- Comparator: LM393 for OVP

Source ALL parts from JLCPCB.
Then run block-reviewer, then block-simulator.
Return block contract.`
  },
  {
    name: 'DISCRETE_LLC_CONTROLLER',
    prompt: `Design DISCRETE_LLC_CONTROLLER block - FULLY DISCRETE CURRENT-MODE CONTROL.
${spec}

THIS IS THE MOST COMPLEX BLOCK. Contains 7 sub-circuits:

1. CURRENT_SENSE: Current transformer (CT) or shunt + amp in primary resonant path
   - CT preferred for isolation, OR shunt + differential amp
   - Output: 0-3V proportional to resonant current

2. VOLTAGE_FEEDBACK: Error amplifier + optocoupler isolation
   - TL431 reference on secondary side
   - PC817 optocoupler to primary side
   - Error amp (TL072 op-amp) generates control voltage

3. SLOPE_COMPENSATION: Ramp generator for stability
   - Sawtooth ramp synchronized to switching frequency
   - Prevents sub-harmonic oscillation in current-mode control
   - Op-amp integrator + reset switch

4. CURRENT_MODE_COMPARATOR: Trips when (Isense + ramp) > Verror
   - LM393 comparator
   - Resets RS latch when current limit reached
   - Provides cycle-by-cycle current limiting

5. VCO: Voltage-controlled oscillator (100-500kHz)
   - CD4046 PLL IC (built-in VCO) OR discrete op-amp relaxation oscillator
   - Frequency modulated by error voltage
   - Sets RS latch at start of each cycle

6. RS_LATCH + DEAD_TIME: Logic for non-overlapping gate signals
   - 74HC74 D flip-flop as RS latch
   - SET by VCO clock, RESET by current comparator
   - Dead-time generation: RC delays + 74HC00 NAND gates
   - Ensures HI and LO never conduct simultaneously

7. PRIMARY_GATE_DRIVER: IR2110 half-bridge driver
   - Drives high-side (HO) and low-side (LO) GaN FETs
   - Bootstrap supply (VB, VS)
   - Inputs from dead-time logic

Search JLCPCB for:
- LM393, LM339 (comparators) - Basic parts
- TL072, LM358 (op-amps) - Basic parts
- CD4046 (VCO) - Basic part
- 74HC74, 74HC00, 74HC14 (logic) - Basic parts
- PC817 (optocoupler) - Basic part
- IR2110 (gate driver) - Extended part
- TL431 (voltage reference) - Basic part

This is an ANALOG CONTROL LOOP. Requires careful stability analysis.
Loop compensation: Type 2 or Type 3 error amplifier.

Run block-reviewer TWICE (this block is complex).
Then run block-simulator (verify loop stability, frequency range).
Return block contract.`
  },
  {
    name: 'AUX_SUPPLY',
    prompt: `Design AUX_SUPPLY block - THREE sub-regulators.
${spec}

Block requirements:
1. 12V → 5V buck converter (500mA for analog control, gate drivers)
   - Search JLCPCB: "buck converter IC 12V input 5V output" (MP1584, MP2359)
   - Inductor: 22µH
   - Output cap: 100µF

2. 5V → 3.3V LDO (300mA for RP2040 I/O)
   - Search JLCPCB: "LDO 3.3V 500mA SOT-223" (AMS1117-3.3, XC6206)
   - Input cap: 10µF, output cap: 22µF

3. 3.3V → 1.1V buck converter (100mA for RP2040 core)
   - Search JLCPCB: "buck converter 1.1V 1.0V adjustable" (TPS62xxx series)
   - Inductor: 4.7µH
   - Output cap: 22µF

Source ALL parts from JLCPCB.
Then run block-reviewer, then block-simulator.
Return block contract.`
  },
  {
    name: 'RP2040_TELEMETRY',
    prompt: `Design RP2040_TELEMETRY block - MONITORING ONLY, NOT CONTROL.
${spec}

Block requirements:
- RP2040 microcontroller (QFN-56 package)
- Search JLCPCB: "RP2040" (LCSC C2040 or equivalent)
- Crystal: 12MHz (for USB)
- Decoupling caps: 100nF × 6 (one per supply pin), 10µF × 2 (bulk)
- Flash: W25Q16JV (2MB QSPI) or similar
- USB connection: routed to USB_INTERFACE block
- ADC inputs (8 channels):
  1. Input voltage (48V sensed)
  2. Output voltage (12V sensed)
  3. Output current (0-10A sensed)
  4. Primary FET temperature
  5. Secondary FET temperature
  6. Transformer temperature
  7. Efficiency measurement (Pin vs Pout)
  8. Spare

- Boot select button (BOOTSEL)
- Debug header (SWD)

Source ALL parts from JLCPCB.
Then run block-reviewer, then block-simulator.
Return block contract.`
  },
  {
    name: 'USB_INTERFACE',
    prompt: `Design USB_INTERFACE block for RP2040.
${spec}

Block requirements:
- USB-C connector (receptacle, power + data)
- ESD protection (USBLC6-2SC6 or equivalent)
- Series resistors on D+ and D- (27Ω typical)
- USB enumeration: RP2040 appears as CDC serial device
- No USB power delivery (PD) - data only
- Shield ground connection (ferrite bead or resistor)

Search JLCPCB for:
- USB-C connector: "USB Type-C receptacle 16-pin"
- ESD protection: "USB ESD protection SOT-23-6"

Source ALL parts from JLCPCB.
Then run block-reviewer, then block-simulator.
Return block contract.`
  },
]

log(`Launching ${blocks.length} block designers in parallel...`)

const blockResults = await parallel(
  blocks.map(block => () =>
    agent(block.prompt, {
      label: `design:${block.name}`,
      phase: 'Design Blocks',
      agentType: 'block-designer',
    })
  )
)

log(`${blockResults.filter(Boolean).length}/${blocks.length} blocks completed`)

// Phase 2: Integrate
phase('Integrate')

const integrationPrompt = `
Integrate all blocks into complete LLC converter schematic.

Blocks designed: ${blocks.map(b => b.name).join(', ')}

Tasks:
1. Read all block contracts (interface.json, parts.json from each block)
2. Create root circuit that instantiates all blocks
3. Connect blocks according to architecture:
   - INPUT_FILTER → PRIMARY_HALF_BRIDGE → LLC_RESONANT_TANK → LLC_TRANSFORMER
   - LLC_TRANSFORMER → SECONDARY_RECTIFIER → OUTPUT_FILTER → OUTPUT_SENSE_PROTECT
   - DISCRETE_LLC_CONTROLLER controls PRIMARY_HALF_BRIDGE
   - OUTPUT_SENSE_PROTECT feeds back to DISCRETE_LLC_CONTROLLER
   - AUX_SUPPLY provides power to all control circuits
   - RP2040_TELEMETRY monitors all sense points
   - USB_INTERFACE connects to RP2040

4. Generate KiCad project: generate_kicad_project()
5. Layout ALL schematics using layout-schematic skill
6. Run make_spice_clean() to prepare simulation decks
7. Validate layout (no crossed wires, components grouped, readable)

Project directory: llc_48v_12v_120w/
`

const integration = await agent(integrationPrompt, {
  label: 'integrate-and-generate',
  phase: 'Integrate',
})

log('Integration complete, KiCad project generated')

// Phase 3: Verify
phase('Verify')

const verifyPrompt = `
Run comprehensive verification on LLC converter project.

Tasks:
1. Run verify_project() - checks:
   - All schematics open without errors
   - ERC passes (electrical rules check)
   - Drawing matches Python circuit description
   - SPICE decks load
   - All parts have LCSC numbers (except transformer)

2. Render all schematics to PNG
3. Check for missing parts or incorrect connections
4. Verify transformer is marked as EXTERNAL source
5. Generate BOM (bill of materials)
6. Report any issues

Project directory: llc_48v_12v_120w/
`

const verification = await agent(verifyPrompt, {
  label: 'verify-project',
  phase: 'Verify',
})

log('Verification complete')

// Return summary
return {
  blocks_designed: blockResults.filter(Boolean).length,
  blocks_total: blocks.length,
  integration_status: integration ? 'success' : 'failed',
  verification_status: verification ? 'success' : 'failed',
  project_path: 'llc_48v_12v_120w/',
  next_steps: [
    'Open project in KiCad: llc_48v_12v_120w/*.kicad_pro',
    'Review schematics (renders in project directory)',
    'Source custom LLC transformer',
    'Check JLCPCB part availability',
    'Order PCB and parts',
  ]
}
