---
name: layout-schematic
description: Lay out a generated KiCad schematic so it reads like one an engineer drew - grouped by function, wired orthogonally, power symbols on the rails, nothing overlapping. RUN THIS EVERY TIME a KiCad project is generated, without being asked: a generated schematic is not finished until it has been laid out. Triggers on generating a circuit or schematic, converting Python to KiCad, running a circuit script or example, generate_kicad_project, cs-new-project, "the schematic looks bad", "lay out the schematic", "tidy the schematic".
---

# Laying out a generated schematic

circuit-synth works out what connects to what. It does not know that a
half-bridge is drawn as a totem pole, that decoupling capacitors belong beside
the pin they decouple, or that signals should flow left to right. That is a
judgement call, and it is yours to make here.

You place the parts and draw the wires. The library gives you the geometry to
do it with and checks that you have not changed the circuit.

## The loop

1. **Generate** the project from the Python script.
2. **Describe** each sheet: parts, pin positions, pin types, nets.
3. **Place** - decide where everything goes and how it is wired. This is the
   part only you can do.
4. **Apply** the placement.
5. **Validate** that the connectivity is unchanged. This is not optional.
6. **Render** the sheet to a PNG and *look at it*.
7. **Refine** and repeat from 3 until it reads well. Two or three passes is
   normal; the first pass gets the topology right, later passes fix text that
   collides and space that is used badly.

## Running it

```python
from pathlib import Path
from circuit_synth.kicad.layout import (
    describe_sheet, PlacementSpec, apply_placement, validate_layout, render_sheets,
)
from circuit_synth.kicad.layout.extract import sheet_nets, sheet_ports

project = Path("bldc_motor_driver")
root = project / "BLDC_Motor_Driver.kicad_sch"
circuit_json = project / "BLDC_Motor_Driver.json"

# 2. Describe the sheet you are about to lay out.
nets, ports = sheet_nets(circuit_json), sheet_ports(circuit_json)
sheet = describe_sheet(project / "PhaseDriver.kicad_sch",
                       nets["PhaseDriver"], ports["PhaseDriver"])
print(sheet.to_json())

# 4. Apply the placement you wrote.
apply_placement(project / "PhaseDriver.kicad_sch",
                PlacementSpec.from_json(Path("phasedriver.json")))

# 5. Validate. Must be empty.
problems = validate_layout(root, circuit_json)
assert not problems, problems

# 6. Look at it.
render_sheets(root, project / "img")
```

Then Read the PNG. Judge it. Fix what is wrong.

## What the description gives you

For every part: reference, value, library id, body size, and every pin with its
number, name, electrical type, offset from the symbol origin and which net it is
on. The offsets are what you place against - a pin ends up at the symbol
position plus its offset, rotated.

Rotation moves a pin the opposite way round from the naive sign convention. At
90 degrees a two-pin part has pin 1 on the **left**. Check the offsets in the
description rather than assuming.

## The placement spec

```json
{
  "components": [{"ref": "U3", "at": [76.2, 88.9], "rotation": 0}],
  "sheets": [
    {"name": "BackEmf", "at": [241.3, 91.44], "size": [50.8, 33.02],
     "pins": [{"name": "PHASE", "side": "left", "offset": 7.62},
              {"name": "ZC", "side": "right", "offset": 7.62}]}
  ],
  "notes": [{"at": [55.88, 175.26], "size": [152.4, 25.4]}],
  "wires": [[[83.82, 81.28], [102.87, 81.28]]],
  "junctions": [[102.87, 81.28]],
  "labels": [
    {"text": "HI", "at": [58.42, 88.9], "rotation": 180,
     "kind": "hierarchical", "shape": "input"},
    {"text": "BOOT", "at": [102.87, 78.74], "rotation": 0, "kind": "local"}
  ],
  "power": [{"lib_id": "power:GND", "at": [76.2, 106.68], "rotation": 0}],
  "no_connects": []
}
```

Applying a spec moves the symbols and redraws all of the wiring. Component
UUIDs, properties and hierarchical instance paths are left alone, so the sheet
stays the same design.

## Close KiCad before you write, and leave it closed

KiCad holds a project in memory from the moment it opens it. Rewriting the
files underneath is invisible to it: the editor still shows what it loaded, the
simulator still runs the deck it built, and anyone looking at the screen sees
the old design with none of the fixes in it. Saving from that editor puts the
stale copy back over the new one.

The symptom is confusing rather than obvious - a problem fixed an hour ago
reappears, quoting reference designators that no longer exist.

So:

- **If you opened KiCad to show somebody, close it before writing again.**
  `circuit_synth.kicad.session.close_kicad()` asks rather than kills, so
  anything unsaved is still theirs to keep.
- **When you have finished writing, call `finish_editing(project_dir)`.** It
  clears the lock files a crashed session leaves behind, which are what make
  KiCad insist a project is already open on a machine where it is not.
- `apply_placement` warns when it is about to write to a project KiCad has
  open, and `verify_project` fails on it. Read those rather than working past
  them: the layout you are about to look at is not the one on screen.

## Rules that are not negotiable

- **Everything on the 1.27mm grid.** A wire that misses a pin by a fraction
  looks connected and is not. `apply_placement` rejects off-grid coordinates.
- **Validate every time.** `validate_layout` compares the schematic KiCad reads
  back against the circuit JSON, pin for pin. If it reports anything, your
  wiring is wrong - fix it, do not ship it.
- **Orthogonal wires only.** Horizontal and vertical segments, never diagonal.
- **Never route a wire over a component.** A wire crossing a symbol body reads
  as a connection to that part and hides what it crosses. Take it around, even
  when that costs two more corners. `route_around` works the detour out for
  you and `validate_layout` reports every crossing left on the sheet.
- **A junction wherever three or more connections meet.** Two wires that merely
  cross are separate nets in KiCad; three that meet without a junction are not
  connected at all.
- **Ground and the supply rails use power symbols**, never a wire dragged
  across the sheet and never a label.
- **A hierarchical label for every declared port**, with the direction the
  block declared, or the sheet pin above it will not match.

## Conventions to follow

**Flow.** Signals go left to right, inputs on the left edge, outputs on the
right. Power comes in at the top, ground goes out at the bottom. If a signal
has to go backwards, it is usually a sign the parts are in the wrong order.

**Grouping.** Draw each functional block as a unit, separated from the next by
clear space. A reader should be able to point at the bootstrap supply, the gate
drive and the half-bridge as three distinct things.

**Anchors first.** Place the IC that defines the block, then arrange the parts
around it on the side their pins face. Do not put a part on the left of a chip
if it wires to a pin on the right.

**Passives.** Series parts lie horizontally in line at a constant pitch.
Anything to a rail stands vertically, with the rail above or the ground symbol
below. Decoupling capacitors sit next to the pin they decouple, not in a row at
the bottom of the sheet.

**Standard shapes.** Draw the circuits that have a conventional appearance the
conventional way: a half-bridge as a vertical totem pole with the phase node
between the two devices, a divider as a vertical stack with the tap on the
right, an op-amp with the feedback over the top.

**Spacing.** 2.54mm minimum between anything and anything. Leave a wire long
enough to read as a wire - 5mm or more. Fill the sheet rather than crowding the
top-left corner, but do not spread a small circuit over a whole page either;
pick the paper size to suit.

**Text.** Nothing may overlap. Net labels sit on a short stub off the pin, not
over the symbol body. Check the render, since symbol reference and value text
moves with the symbol and collides in ways the coordinates do not show.

**Wires around parts, not through them.** Leave a channel between blocks for
wires that have to get past. A wire that must cross the sheet goes above or
below the parts in its way, not through them:

```python
from circuit_synth.kicad.layout import route_around, segments_of, sheet_bodies

bodies = sheet_bodies(sheet_path)              # every printed outline
detour = route_around(start, end, bodies.values())
spec.wires += segments_of(detour)              # the corners, as wire segments
```

`route_around` returns the fewest-corner orthogonal path that keeps 1.27mm off
every body, and falls back to a plain L route when the sheet is too crowded to
avoid everything - which is a sign to move a part, not to accept the crossing.
Check what is left with `wires_over_components(sheet_path)`.

## Sheets of hierarchical blocks

A sheet whose parts are all sheet symbols is laid out the same way, using the
same flow: source blocks on the left, consumers to the right, one sheet symbol
per block with its pins on the side the signal travels. Give each sheet symbol
room for its pin names.

`sheets` places them: `at` is the body's top-left corner, `size` its width and
height, and each pin gives its name, the edge it sits on and how far down that
edge it goes. **Every port of the child sheet must appear** - a port left out
of the list loses its connection, and nothing else will notice.

A page of sheet symbols is a block diagram, so wire it like one: give every
sheet pin a short stub with a **label** on it rather than running wires from
block to block. Point-to-point wiring between six blocks with eight pins each
is a rat's nest; the same page in labels reads at a glance. The same goes for a
dense part - an MCU with fifty pins gets stubs and labels, not fifty wires.

## Group boxes: one per circuit, titled, with the reason written on it

A sheet usually holds several circuits that happen to share a page. Box each
one and title it, so a reader knows what they are looking at before they have
traced a wire.

```json
{"groups": [
  {"title": "12MHZ CRYSTAL", "at": [165.1, 278.13], "size": [177.8, 77.47],
   "rationale": "The circuit from RP-008279-DS section 2.3, copied rather\nthan reworked: ..."}
]}
```

The box is drawn to the conventions measured out of the OpenBeam project -
see [OPENBEAM_STYLE.md](OPENBEAM_STYLE.md), which is the reference for what
"reads well" means here. A 0.508mm dim-grey rounded rectangle; the title above
it, centred, 2.54mm bold dark red; the reasoning inside along the bottom at
label size.

**The rationale is the point, not the box.** Write why the circuit is correct:
which datasheet figure it was copied from and its document number, what the
values were chosen against, and which parts are deliberate departures from the
reference. A reviewer should be able to check the page without opening the
datasheets. "Decoupling capacitors" says nothing; "one 100nF per power pin as
RP-008279-DS section 2.1.2 asks for, except C16, which is the 1uF the internal
regulator wants at its input" is a sentence someone can check.

Leave room for it. The note sits inside the bottom of the box and grows
upward, about 2mm per line plus 3.3mm of margin, so a six-line reason wants
16mm of clear space below the circuit. Boxes may be different heights; make
them fit their contents rather than making the contents fit a grid.

## Text boxes

The generator writes each block's docstring onto its sheet as a text box, and
puts it wherever there was room in the file - which is usually straight over
the parts. `notes` moves it: one entry per box, in file order, each with the
`at` of its top-left corner and its `size`. Put it in clear space below or
beside the drawing. `validate_layout` reports a box left sitting on a part.

## When you cannot make something clean

Say so. A sheet with thirty parts and no structure may genuinely need a
different sheet size or a split into sub-blocks. Suggest that rather than
producing a dense layout and calling it done.
