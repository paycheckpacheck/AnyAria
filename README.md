# AnyAria

Python-defined circuits that generate production-ready KiCad projects.

AnyAria is a fork of [circuit-synth](https://github.com/circuit-synth/circuit-synth)
carrying features that have not landed upstream yet. Everything lives in this
repository, so there is nothing to wait on.

## What this fork adds

### Hierarchical blocks with declared ports

A subcircuit declares a named, directional interface by annotating its
parameters. Each port becomes a typed KiCad sheet pin on the parent and a
matching hierarchical label in the child, so one block definition can be
instantiated repeatedly with different nets attached.

```python
from circuit_synth import Bidirectional, Input, Net, Output, circuit

@circuit(name="HalfBridge")
def half_bridge(HI: Input, LI: Input, PHASE: Output, VM: Input):
    ...

half_bridge(ah, al, phase_a, v_motor)   # three instances of one block,
half_bridge(bh, bl, phase_b, v_motor)   # each on its own nets
half_bridge(ch, cl, phase_c, v_motor)
```

Ground and the supply rails are drawn as KiCad power symbols rather than sheet
pins, since a power symbol already connects by name across the whole design.

Upstream as [PR #617](https://github.com/circuit-synth/circuit-synth/pull/617).

### JLCPCB component import

Turns an LCSC part number into a ready-to-use component, with the KiCad symbol
and footprint resolved and the JLCPCB metadata attached as properties.

```python
from circuit_synth.manufacturing.jlcpcb import import_jlc_component

part = import_jlc_component("C25804", ref="R")
```

Upstream as [PR #616](https://github.com/circuit-synth/circuit-synth/pull/616).

### Schematic layout tools

Generating a schematic and laying one out well are different problems. The
generator works out what connects to what; laying it out so an engineer can
read it is a judgement call about grouping, flow and convention.

`circuit_synth.kicad.layout` provides the machinery for a person, or Claude, to
make that call:

* **describe** a generated sheet: every part, every pin with its offset,
  electrical type and net, the paper size and the usable area
* **apply** a placement back onto the sheet, moving symbols and redrawing the
  wiring, while component UUIDs, property text and hierarchical instance paths
  survive untouched
* **validate** the result against the circuit it came from, pin for pin, so a
  layout can never quietly change the connectivity
* **render** each sheet to a PNG so the result can be looked at

The skill at `.claude/skills/layout-schematic` drives the loop: generate,
describe, place, apply, validate, render, refine.

### Fixes carried here

* multi-unit parts (op-amps, comparators, logic gates) now give every unit its
  own instance with its own unit number, instead of two units claiming unit 1
  and KiCad refusing to annotate the sheet
* net connections are identified by pin number rather than pin name, so both
  ends of a resistor and all three VDD pins of an MCU stay distinct
* a net passed from a parent circuit into a subcircuit keeps its power flags,
  so a ground rail passed down a hierarchy still draws as power symbols
* symbol rotation matches KiCad's own convention, which previously swapped a
  two-pin part end for end once it was rotated

## Getting started

```bash
uv venv --python 3.12
uv pip install -e ".[dev]"
uv run python examples/three_phase_driver.py
```

## The example

`examples/three_phase_driver.py` is a sensorless three-phase BLDC driver:

```
ThreePhaseDriver (root)
+-- Power          VBUS in -> motor rail, 3.3V logic, rail sense
+-- UsbProgramming USB-C, CC resistors, D+/D- to the MCU
+-- Mcu            RP2040, QSPI flash, crystal, SWD
+-- HalfBridge x3  HI/LI in -> PHASE out, plus ISENSE and ZC out
    +-- BackEmf    that phase's divider, neutral tap and comparator
```

Everything that exists once per phase lives inside `HalfBridge`, because
`HalfBridge` is the block that is repeated. Only the virtual neutral is shared,
so it arrives as a port. The `circuit-hierarchy` skill covers how to make that
call.

Feedback into commutation:

* **current** - three low-side Kelvin shunts, one INA181 each, into ADC0..ADC2,
  for torque control and over-current shutdown
* **back-EMF** - each phase divided by 11 and compared against a virtual
  neutral by that phase's own comparator, whose output is the zero-crossing
  edge the commutation state machine advances on
* **rail** - the motor rail divided into ADC3, so the duty cycle can be
  compensated for supply droop

## Relationship to circuit-synth

The Python package is still importable as `circuit_synth`, so existing code and
documentation continue to work unchanged. Renaming the import path is a
separate piece of work.

Upstream is tracked at https://github.com/circuit-synth/circuit-synth. See
[CLAUDE.md](CLAUDE.md) for the development guide inherited from it.
