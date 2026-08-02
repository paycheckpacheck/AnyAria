# What a block agent returns

Blocks are built in parallel by agents that cannot see each other's work, so
what a block leaves behind has to be enough to rebuild the board without asking
any of them anything. This is that interface.

Everything goes in `<project>/design/blocks/<Name>/`, and the whole directory is
read by every build: `board.py` imports each block's `block.py`, and
`build_board` applies each block's `layout.py`. A build is therefore a pure
function of these directories, which is exactly what makes it safe for several
agents to run one at a time against the same project.

## `block.py`

The `@circuit` function, importable on its own. Ports declared with `Input`,
`Output`, `Bidirectional`. No side effects at import time.

This file starts life as a **stub** - the same signature with an empty body -
written at the architecture stage so that the block diagram can be generated
and approved before any block is built. A block agent replaces the body and
keeps the signature. Changing a port changes the root sheet the user approved,
so it is something to raise rather than something to do.

Replace it in one step (write a temporary file, then `os.replace`). Another
agent's build may be importing it at the moment you save.

Ground and the supply rails are **not** ports - they are drawn as power symbols
and connect by name across the design. A block that declares `GND` as a port
has misread `circuit-hierarchy`.

## `interface.json`

What the integrator composes against, and the only file it has to read.

```json
{
  "name": "BuckStage",
  "instances": 1,
  "ports": [
    {"name": "VIN",  "direction": "input",  "meaning": "8-36V input rail"},
    {"name": "SW",   "direction": "output", "meaning": "switch node to the inductor"},
    {"name": "FB",   "direction": "input",  "meaning": "feedback tap, 0.8V nominal"}
  ],
  "rails_consumed": ["V3V3"],
  "rails_produced": ["V1V8"]
}
```

`meaning` is not decoration. It is what stops two blocks being wired together
because their port names happened to match.

## `parts.json`

One entry per part, from `SourcedPart.to_dict()`. LCSC number, Basic or
Extended, price, stock, symbol, footprint, the query that found it, what was
passed over, and any deviation.

A part without an LCSC number has not been sourced, and the board cannot be
assembled as drawn.

## `reference.md`

The `reference-circuit` checklist, with the document number and revision it was
taken from.

```
TPS40170, SLUSAC0G, figure 41
  [x] 10uF ceramic input, close to VIN                     C1
  [x] 0.1uF bypass on VDD                                  C2
  [~] bootstrap 0.1uF -> 0.22uF   the switching frequency is half the figure's
  [+] 100k pulldown on EN                                  ADDITION: defined start-up
```

`[x]` copied, `[ ]` missing, `[~]` different, `[+]` an addition. Anything that
is not `[x]` needs a sentence, and that sentence belongs in `rationale.md` too.

A bare `[ ]` fails acceptance.

## `values.json`

Every value, and where it came from. This is what stops a plausible number
passing every automated check.

```json
{
  "L1": {
    "value": "10uH",
    "provenance": "first_principles",
    "derivation": "L = Vout(Vin-Vout) / (Vin * fsw * dIL); 3.3(12-3.3)/(12*500k*0.6) = 8.0uH, nearest E12 10uH",
    "inputs": {"Vin": "12V", "Vout": "3.3V", "fsw": "500kHz", "ripple": "30% of 2A"},
    "margin": "ripple falls to 24% at 10uH"
  },
  "C7": {
    "value": "0.1uF",
    "provenance": "datasheet",
    "reference": "SLUSAC0G section 8.2.2.4, bootstrap capacitor",
    "margin": ""
  }
}
```

`provenance` is one of `datasheet`, `first_principles`, `research`, or
`unsourced`. **An `unsourced` value fails acceptance.** If a number cannot be
justified, leave the placeholder and report the gap - a placeholder is honest,
a guess is not.

Where two sources disagree, take the more conservative value and record both.

## `rationale.md`

One paragraph per group box, ready for the layout spec. Say which document the
circuit came from, what the values were chosen against, and which parts are
deliberate departures. A reviewer should be able to check the sheet without the
datasheets open.

## `review.json`

Written by `block-reviewer` and read by `block-simulator`, which will not start
until `connections_frozen` is true.

```json
{
  "verdict": "clean",
  "passes_run": 3,
  "findings": [
    {"severity": "fixed", "what": "U1 pin 7 (PGND) was not connected"},
    {"severity": "note",  "what": "EN left floating; a pulldown was added"}
  ],
  "connections_frozen": true
}
```

`connections_frozen` goes true only when two consecutive passes found nothing
new. `block-simulator` may then change **values only** - it may not add, remove
or rewire anything except decoupling.

## `layout.py`

The block's own sheet layout, as a module-level `SPEC = PlacementSpec(...)`.

The block agent writes this **and applies it**, and the reason is that the
information needed to lay a sheet out well is the information the block agent
has and nobody else does. Which figure the circuit was copied from decides how
it should be drawn. The rationale text is already written, so the group boxes
are already written. The parts list says which capacitor decouples which pin,
which is the same thing as saying where it goes.

By the time anyone else sees the block it has a netlist and no reasons, and a
netlist alone produces exactly the layout the generator produces.

```python
from circuit_synth.kicad.layout import PlacementSpec
from circuit_synth.kicad.layout.spec import ComponentPlacement as C
from circuit_synth.kicad.layout.spec import GroupPlacement as G

SPEC = PlacementSpec(
    paper="A3",
    components=[C("U1", (88.9, 101.6), 0), ...],
    groups=[G("GATE DRIVE", (45.72, 60.96), (190.5, 76.2),
              "IR2101 from PD60147 figure 3, bootstrap sized for ...")],
    wires=[...], labels=[...], power=[...],
)
```

Write it against the reference designators your sheet has *now*, read out of
`describe_sheet`. **Do not maintain a rename table**, and do not copy references
from an earlier run: another block's agent adding a part renumbers everything
after it, at any moment, without telling you.

What keeps the spec valid is `layout_refs.json` below. Every build derives two
mappings and chains them: `block_renames()` carries the layout from the circuit
it was written against onto the same block in the circuit as it now is, and
`instance_renames()` carries it onto the block's other instances. A spec written
once therefore transfers to every instance and survives a part being added
anywhere earlier in the design.

A spec worked out in code rather than written by hand can be written as
`layout.json` instead, with `PlacementSpec.write_json()`. The build reads
whichever is there, preferring `layout.py`.

The layout must apply with no problems reported before you hand it over: your
last `build_board` result must list nothing naming your sheet.

## `layout_refs.json`

The circuit `layout.py` was written against - the reference frame its reference
designators mean something in. `build_board` writes it for you when you pass
`capture_refs=["<YourBlock>"]`, which you do on the build immediately before you
write or rewrite the layout.

Without it, a layout written when your resistors were `R3` and `R4` would be
applied to whatever is called `R3` and `R4` after another block grew by two
parts, which is a different circuit drawn in your block's shape. Nothing else in
the toolchain would notice: the netlist still matches, because the placement
moved real symbols to real coordinates. It would simply be wrong.

## `sheet.png`

A render of the laid-out sheet. Not decoration - it is the evidence the layout
was looked at rather than merely applied, and it is what the person reviewing
the board sees without opening KiCad.

## `notebook.ipynb`

This block's section, pre-executed, structured as the `simulate-block` skill
describes.
