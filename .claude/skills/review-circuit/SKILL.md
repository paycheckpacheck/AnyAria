---
name: review-circuit
description: Review the Python that describes a circuit, repeatedly, until nothing new is found - before generating anything. RUN THIS EVERY TIME a circuit is written or changed, without being asked. Triggers on writing or editing a circuit script, adding a block, changing component values, "generate the schematic", "is this right", "review this circuit", finishing a design, before generate_kicad_project.
---

# Review the circuit until the review stops finding things

Generating a schematic from a circuit that is wrong produces a wrong
schematic, laid out beautifully, that validates clean. Every check further
down the toolchain - `validate_layout`, ERC, the render - compares the
schematic against the Python. None of them can tell you the Python is wrong.

So the Python gets reviewed first, and it gets reviewed until a pass finds
nothing new. Not once. One pass reliably finds the obvious things and reliably
misses the rest.

## The loop

```
review the circuit against the passes below
  -> fix what was found
  -> review again, from the top
  -> stop when a full pass finds nothing new
```

Two consecutive clean passes is the exit condition. If a pass finds something,
the count restarts - a fix can break something a previous pass cleared.

Say in the transcript what each pass found, including "nothing". A silent
review is indistinguishable from no review.

## The passes

Run all of them each time. They are ordered by how expensive the mistake is to
find later.

**1. Against the reference circuits.** For every part with a published
application circuit, walk the checklist from the `reference-circuit` skill.
This is the pass that catches missing series resistors, missing straps and
wrong decoupling values.

**2. Pin by pin, against the datasheet pinout.** Every pin number the code
names, checked against the part's pinout. A pin number is a silent failure: it
generates, it lays out, it validates, and it is wrong. Pay attention to parts
whose symbol stacks several pins on one point.

**3. Every supply pin connected.** List the part's power and ground pins from
the datasheet and check each appears in the code. Thermal pads count. A part
missing a ground is a part that mostly works.

**4. Voltage compatibility, rail by rail.** For each net, what drives it and
what receives it, and are those compatible? Check every part's supply against
its datasheet minimum and maximum, and every logic input against its
threshold. *This is the pass that catches the mistake nobody catches by
reading the schematic*: a gate driver whose UVLO is above the rail it is
given, a 5V output into a 3.3V-tolerant input, a MOSFET driven below its
V_GS(th) maximum.

**5. Current and power.** Every series element carries a current: check the
resistor sizes, the fuse rating, the regulator's output against the sum of
what it feeds, the capacitor voltage ratings against the rail plus margin.

**6. Direction and role.** Every declared port's direction matches what the
block does with it. Every output has exactly one driver. Nothing declared an
input is driven from inside.

**7. Hierarchy.** Run the `circuit-hierarchy` test: numbered ports or a loop
over channels means the blocks are wrong, and that is much cheaper to fix now
than after two layout passes.

**8. Values against their purpose.** For each passive, what is it for and does
its value do that? A divider ratio against the ADC range, a filter corner
against the switching frequency, a pull-up against the bus capacitance, a
bootstrap capacitor against the gate charge. Compute it; do not eyeball it.

**9. What is missing entirely.** Not "is what is here correct" but "what does
this design need that nobody has written". Reverse protection, a bleed
resistor, a way into the bootloader, a test point, an enable that is floating.
Missing things do not appear in any diff.

## Confidence, honestly

At the end, state what you are confident about and what you are not, in one
short list. "Confident: supply topology, RP2040 support circuit against
RP-008279-DS, port directions. Not confident: the IR2101 gate rail, because
its UVLO is above the 3.3V it is given - flagged, not fixed."

Do not report high confidence in a pass you did not run. If a datasheet could
not be fetched, that is a pass you did not run, and it goes in the not-confident
list.

## What comes after

Only when the review is quiet: generate the project, then run
`layout-schematic`, which has its own loop and its own validation. Those check
the drawing against the Python. This one checks the Python against reality,
and nothing downstream can do it for you.
