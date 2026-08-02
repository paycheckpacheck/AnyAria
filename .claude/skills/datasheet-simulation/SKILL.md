---
name: datasheet-simulation
description: Turn a hierarchical block into a verified, simulated schematic - find the governing equations in the main component's datasheet, analyse the block's real values against them, run the circuit in ngspice, and write the figures of merit onto the KiCad sheet as red notes linked back to the calculation. Triggers on "simulate this block", "check this design", "what's the ripple/efficiency/junction temperature", "annotate the schematic with the numbers", "is this circuit right", "probe a net", "size the bootstrap capacitor", "verify against the datasheet", or any request to check a design against a part's datasheet.
---

# Turning a datasheet into a simulated, annotated block

A schematic that has been generated is not yet a design that has been checked.
The generator knows what connects to what; it does not know whether the gate
driver can charge that gate, whether the shunt puts a usable voltage into the
amplifier, or whether the part is being run inside the conditions its
manufacturer specified it for.

This skill closes that gap for one hierarchical block at a time. It ends with
figures of merit written on the sheet in red, each one linked back to the line
of Python that produced it, and a KiCad project whose own simulator will plot
any net in the block.

## The rule everything else follows from

**A number nobody can check is worse than no number.** A reader who sees
`Tj = 120C` on a MOSFET will stop wondering about the MOSFET. If that figure
was a guess, the annotation has actively made the design less likely to be
caught. So:

- Every figure carries a `Basis`: `SIMULATED`, `DATASHEET`, `DERIVED`, or
  `ESTIMATED`. Only the first three reach the sheet; `ESTIMATED` is reported
  and withheld.
- Every datasheet parameter names the table it came from. `Parameter` will not
  construct without one.
- Every substitution says what it costs. `Substitution` will not construct
  without a `limits` field.
- When the datasheet does not support a figure, **say so and move on**. Report
  it as a gap. Do not fall back on a typical value from a similar part.

If you finish and the honest answer is "the datasheet gives on-resistance at
one temperature, so I cannot compute a junction temperature", that is a
successful run.

## The loop

1. **Identify the block and its main component.** The part that defines what
   the block is: the buck controller, the gate driver, the instrumentation
   amplifier. Its role decides which equations matter.
2. **Find the datasheet.** Search for it. Fetch it. Note the document number
   and revision - parameters change between revisions and a citation without
   one is not reproducible.
3. **Extract what matters for this role.** Not the whole datasheet: the
   parameters and the typical-application procedure for the job this part is
   doing here. A gate driver in a motor drive wants bootstrap sizing, peak
   gate current and propagation delay; the same part in a class-D amplifier
   wants different ones.
4. **Read the design back out of the `Circuit`.** Real values, from the
   component objects. Never restate a value in the analysis - if somebody
   changes a gate resistor, the analysis must change with it.
5. **Check the operating conditions first.** Before simulating anything,
   check every part is inside its recommended conditions. A part outside them
   makes every downstream figure meaningless, and a simulation will produce
   plausible waveforms anyway.
6. **Build the models.** Manufacturer SPICE models where they exist, fitted
   models where they do not, and a declared `Substitution` for anything that
   has to stand in for a part with no model.
7. **Simulate.** Generate the testbench as a KiCad project, make it probeable,
   export its deck with `kicad-cli` and run *that*.
8. **Measure and record.** One `analysis.record(...)` per figure of merit.
9. **Annotate.** Write the figures onto the design sheet.
10. **Report.** Lead with what could not be established.

## The whole board: firmware in, waveforms out

Most boards cannot be simulated by SPICE at all, and it is worth being clear
about why before choosing a tool.

A gate driver, a shunt amplifier, a comparator, a PLL, a mixer, an LDO - none
of them has a netlist a solver can do anything with, and the vendor's model,
where one exists, will not run in ngspice. And the behaviour of a controller
board *is* its control loop: simulating the power stage with a fixed stimulus
leaves out the part under test.

So a board is simulated as three kinds of block over shared nets, in
`circuit_synth.simulation.cosim`:

| Block | What it is | Built from |
|---|---|---|
| `Firmware` | the excitation - Python standing in for what the MCU will run | the control algorithm under test |
| `DeviceModel` | one function per IC | its datasheet |
| `SwitchingLeg`, `StateSpaceNetwork`, `SpiceNetwork` | the passives and primitives | the components |

```python
class Commutation(Firmware):
    def control(self, t, feedback):
        """Read the sensors, decide the drive, once per control period."""
        if feedback["ZC_A"] > 1.65:
            self.step = (self.step + 1) % 6
        return self.gates()

CoSimulation([
    Commutation("firmware", inputs=["ZC_A", "ISENSE_A"], outputs=["AH", "AL"]),
    GateDriver("driver", "AH", "AL", "HGATE", "LGATE", "VDRV", datasheet=ir2101,
               propagation_delay=680e-9, uvlo_rising=8.9, uvlo_falling=8.2,
               output_high=12.0, input_threshold=2.5),
    SwitchingLeg("leg", "HGATE", "LGATE", "VMOTOR", "BEMF", "PHASE", "I", "VSHUNT",
                 inductance=250e-6, resistance=0.35, shunt=0.005),
    CurrentSenseAmplifier("isense", "VSHUNT", "ISENSE_A", datasheet=ina181,
                          gain=50.0, bandwidth=350e3, supply=3.3),
]).run(duration=0.05, control_period=20e-6, dt=200e-9)
```

Time advances in slices. **The firmware sees the feedback from the previous
slice**, which is not a simplification: a controller acts on samples it has
already taken, and modelling the loop as instantaneous hides the delay that
decides whether it is stable.

### Writing a device model

The full procedure, with a worked example that gets within 2% of published
values on four out-of-sample points, is in
[MODEL_FROM_DATASHEET.md](MODEL_FROM_DATASHEET.md). The short version:

0. **Ask whether the model already exists.** `simulation.parts.find(mpn)` takes
   an order code and returns a checked model, or nothing. Building a second one
   by hand is how two answers for one part get into a design.
1. Take the specification table first - it is text, so it can be read exactly.
2. Get the figures. **Try `page.get_drawings()` before rendering**: most
   datasheet plots are vector art, so the curve is in the file as coordinates
   and can be read exactly rather than by eye. Reading one off a 300 dpi render
   was 8% out where the vectors were right. Where there are no vectors, render,
   *look*, and record the reading accuracy with each point.
3. **Split the data before fitting.** Build from the curve, judge with the
   table, or the other way round - never both. Mark each `ReferencePoint`
   `in_sample` or not.
4. Fit the smallest form the physics justifies. When it fails, name the
   mechanism rather than adding parameters.
5. Ask the model for something it was not told. If it can only reproduce its
   own inputs it is a lookup table.
6. Where the answer depends on itself - dissipation setting a temperature that
   sets the dissipation - solve for the fixed point rather than evaluating once
   at 25C, and treat "no fixed point" as the result it is.
7. Give it a `check()` that runs in a test, so it says when it has drifted, and
   add it to `REGISTRY` so the next agent finds it instead of rebuilding it.


One class per part, from the datasheet's own table. `input_threshold` is the
part's V_IH; `propagation_delay` is its specified delay; `uvlo_rising` and
`uvlo_falling` are the lockout thresholds; `bandwidth` is the small-signal
bandwidth. Take each from the document, and record the document number and
revision in a `Datasheet`.

**Every model lists what it does not represent**, in `gaps`. A gate driver
model that says "no figure for output impedance, so edge shape is not
modelled" is useful. One that assumes 2 ohms because that is typical is a trap,
because the number it produces looks exactly as trustworthy as a real one.

### What this catches that a schematic review does not

The driver in the example above, given the 3.3V logic rail, never leaves
under-voltage lockout: the gates stay at 0V and the board does nothing. Every
connection in the schematic is correct, ERC is clean, and the netlist says
nothing at all about it. That class of fault - a part outside its operating
conditions, on a board that is wired perfectly - is what this is for.

## Which tool for which question

This is the decision that most affects whether the numbers are worth
anything, so make it deliberately rather than by habit.

**Use SPICE when the answer depends on the whole mesh at once** and cannot be
written down: the current a winding actually draws given the duty cycle and
back-EMF, ripple, the shape of a switching node, how a compensation network
behaves in the loop it is in, what happens during dead time. These are
questions where the interactions are the answer.

**Use the datasheet's closed form when the equation is the better evidence:**

- The manufacturer's own design procedure. Bootstrap capacitor sizing is a
  rule from an application note, not a measurement - simulating it would only
  measure your model of it.
- Anything the model does not represent. Gate drive loss is `Qg * V * f`
  straight from the datasheet; a fitted VDMOS model does not reproduce total
  gate charge, so measuring it from the simulation would be measuring the fit.
- Anything the netlist has no physics for. Junction temperature needs a
  thermal model. If there is no thermal network in the deck, `Tj` cannot come
  out of it.

**Use neither, and report a gap, when the datasheet does not support the
question.** This happens more than it looks like it should. A datasheet that
quotes on-resistance at one temperature contains no temperature coefficient.
A datasheet with typical-only switching times cannot bound a worst-case dead
time.

## Running it

```python
from circuit_synth.simulation.datasheet import Datasheet, Parameter, Equation, register
from circuit_synth.simulation.figures import BlockAnalysis, Basis
from circuit_synth.simulation.spice_models import ModelSpec, ModelFile, assign_models
from circuit_synth.simulation.probe import Substitution, make_probeable
from circuit_synth.simulation.ngspice_run import export_spice_netlist, run_transient
from circuit_synth.simulation.annotate import annotate_schematic
from circuit_synth.simulation.vdmos import VdmosParameters, fit

# 2-3. What the datasheet says, with the table each number is in.
part = register(Datasheet(
    part_number="IR2101", title="...", document="PD60043 Rev.O", url="...",
    role="high/low-side gate driver for a bootstrapped half-bridge",
    parameters={"IQBS": Parameter("IQBS", 55e-6, "A",
                                  "Static Electrical Characteristics",
                                  "max", typical=False)},
    equations={"bootstrap_capacitor": Equation(
        name="bootstrap_capacitor",
        expression="Cboot >= 2*[2*Qg + Iqbs/f + Qls + Icbs/f] / (Vcc - Vf - Vls)",
        symbols={"Qg": "gate charge of the high-side FET", ...},
        section="Design Tip DT98-2 section 3, EQ(1) and EQ(2)")},
))

# 4-5. Real values, checked against the datasheet before anything else.
analysis = BlockAnalysis(block="HalfBridge")
if supply_volts < part.value("VCC_MIN"):
    analysis.note_gap(f"BLOCKING: VCC is {supply_volts}V, minimum is ...")

# 6. A model, fitted to the datasheet and checked against it.
model = fit(VdmosParameters(name="IRF3205", rds_on=0.008, ...))

# 7. Generate, make probeable, export the deck KiCad would run, run it.
testbench.generate_kicad_project(str(output), force_regenerate=True, generate_pcb=False)
assignments, gaps = assign_models(testbench.components.values(), specs)
project = make_probeable(output, assignments,
                         directives=[".tran 100n 5m 0 100n uic"],
                         traces=["V(/PHASE)"],
                         model_files=[ModelFile("block.lib", model.card)],
                         substitutions=[...], gaps=gaps)
waveforms = run_transient(export_spice_netlist(project.schematic), working_dir=output)

# 8-9. Record, then write onto the design sheet.
analysis.record("Q2", "Idrms", waveforms.rms("l1#branch"), "A", Basis.SIMULATED,
                "RMS over the settled window")
annotate_schematic(design_dir / "HalfBridge.kicad_sch", analysis)
print(analysis.summary())
```

`examples/simulate_half_bridge.py` is the worked version of all of this.

## Rules that are not negotiable

- **Check operating conditions before simulating.** A part outside its
  recommended conditions invalidates everything downstream, and the simulation
  will not tell you - it will produce clean waveforms of a circuit that cannot
  work.
- **Export the deck from the schematic; never hand-build a parallel netlist.**
  `kicad-cli sch export netlist --format spice` is the same exporter the
  interactive simulator uses. Running that deck is what guarantees the number
  on the sheet and the waveform the user probes are the same simulation. A
  separately-built PySpice model is a second circuit that will drift.
- **Check the parts are in the deck.** A symbol missing its `Sim.*` properties
  is absent from the netlist with no error anywhere. `missing_elements(deck,
  expected)` is the only thing that catches it.
- **Check the run settled.** A load whose time constant is longer than the
  simulated window gives a startup ramp that looks exactly like an operating
  point. Compare the average over the last two windows before believing any
  figure.
- **Sanity-check one figure by hand.** Work out one number analytically and
  compare. In the worked example the RMS winding current should be
  `(D*Vrail - Vbemf)/R`; it comes out within 2%, and that is what says the
  netlist is wired the way it was meant to be.
- **Never annotate an `ESTIMATED` figure.** The API will not let you, but do
  not work around it by relabelling a guess as `DERIVED`.

## Writing the notes

Notes are short, dense and sit at the component's centre:

```
Id = 1.53A
Idrms = 1.41A
Pcond = 7.9mW
```

Leave enough that an engineer can check the design without rerunning anything.
That means the inputs as well as the outputs: a junction temperature with no
current and no dissipation beside it cannot be checked, only believed.

`annotate_schematic` handles the placement - it stacks the lines on the part,
moves the block clear of the symbol's own reference and value text, and
removes the previous run's notes so re-running replaces rather than
accumulates.

## Clicking a note back to the calculation

Every figure captures the file and line that recorded it, and each note gets a
`vscode://file/<path>:<line>` hyperlink. In KiCad, clicking the text offers
"Open vscode://..." and then hands it to the shell.

What is verified: the link is written into the `.kicad_sch` correctly, KiCad
parses it, and KiCad's own writer preserves it on save. KiCad 9 and 10 accept
any well-formed URI scheme. **KiCad 7 and 8 will not** - they had a scheme
whitelist that `vscode://` does not pass, and there the note is still written
and readable, just not clickable.

For this to do anything the machine needs `vscode://` registered as a URL
protocol handler, which VS Code does on install.

## Probing a net for a waveform

`make_probeable` writes three things into the generated project:

- **`Sim.*` properties** on each symbol - `Sim.Device`, `Sim.Pins`, and either
  `Sim.Params` or `Sim.Library`/`Sim.Name`.
- **A `.tran` directive** as a schematic text element. Only `text` and
  `text_box` items are scanned, and the first token must be one KiCad
  recognises; `add_directives` rejects anything else, because an unrecognised
  directive is drawn on the sheet and silently never executed.
- **A `.wbk` workbook** naming the analysis and the traces, so the simulator
  opens with the plot already on screen instead of an empty window.

Both the directive and the workbook are needed. `kicad-cli` reads the analysis
command out of the schematic text; the interactive simulator ignores it and
uses the analysis tab's own command, which is what the workbook sets.

Then in KiCad: open the project, **Inspect -> Simulator**, **Run**, then
**Probe** and click a net. Note that Probe needs the simulator window already
open and an analysis tab already present, and it shows nothing until a run has
finished.

Values are written into `Sim.Params` as plain numbers, never as the value
string. SPICE reads `M` as milli and `MEG` as mega, so a component marked
`4M7` would come out a million times too small, and a `220uF/50V` would not
parse at all.

## When you cannot build a trustworthy model

Say so, specifically. "No SPICE model is available for the IR2101, so the gate
drive is represented by ideal sources at the edge rate its datasheet implies;
nothing here says anything about bootstrap droop" is useful. Silently
substituting an ideal buffer and reporting an efficiency is not.

If the main component has no model and no published equations for its role,
the honest output is a report and no annotation at all.
