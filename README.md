# AnyAria

Circuit design tooling built on top of [circuit-synth](https://github.com/circuit-synth/circuit-synth).

This repository is the base to build on. It pins circuit-synth to a branch that
already carries the two features AnyAria depends on, and leaves the schematic
layout work on a separate branch until it has been reviewed.

## What is integrated

| Feature | Upstream PR | Where it lives | Status |
| --- | --- | --- | --- |
| JLCPCB component import | [#616](https://github.com/circuit-synth/circuit-synth/pull/616) | `anyaria-base` branch | merged in |
| Hierarchical blocks with declared ports | [#617](https://github.com/circuit-synth/circuit-synth/pull/617) | `anyaria-base` branch | merged in |
| Schematic layout tools | part of #617's branch | `schematic-styler` branch | held for review |

The dependency is pinned in `pyproject.toml`:

```
circuit-synth @ git+https://github.com/paycheckpacheck/circuit-synth@anyaria-base
```

### JLCPCB component import

Turns an LCSC part number into a ready-to-use component, with the KiCad symbol
and footprint resolved and the JLCPCB metadata attached as properties.

```python
from circuit_synth.manufacturing.jlcpcb import import_jlc_component

part = import_jlc_component("C25804", ref="R")
```

### Hierarchical blocks

A subcircuit declares a named, directional interface by annotating its
parameters. Each port becomes a KiCad sheet pin on the parent and a matching
hierarchical label in the child, so a block can be instantiated repeatedly with
different nets attached.

```python
from circuit_synth import Bidirectional, Input, Net, Output, circuit

@circuit(name="PhaseDriver")
def phase_driver(HI: Input, LI: Input, PHASE: Output, VM: Input):
    ...

phase_driver(ah, al, phase_a, v30)   # three instances of one block,
phase_driver(bh, bl, phase_b, v30)   # each on its own nets
phase_driver(ch, cl, phase_c, v30)
```

Ground and the supply rails are drawn as KiCad power symbols rather than sheet
pins, since a power symbol already connects by name across the whole design.

## Getting started

```bash
uv venv --python 3.12
uv pip install -e ".[dev]"
uv run python examples/three_phase_driver.py
```

The example generates a KiCad project using both features and prints where it
was written.

## Layout of this repository

```
src/anyaria/      the AnyAria package
examples/         runnable circuits built on the integrated features
tests/            tests for what this repository adds
```

## The schematic layout tools

circuit-synth decides what connects to what. Laying a sheet out so an engineer
can read it is a judgement call, and the tools on the `schematic-styler` branch
exist for a person, or Claude, to make it:

* describe a generated sheet - every part, every pin with its offset,
  electrical type and net
* apply a placement back onto the sheet, moving the symbols and redrawing the
  wiring while component UUIDs and hierarchical instance paths survive
* check the result against the circuit it came from, pin for pin, so a layout
  can never quietly change the connectivity
* render each sheet to a PNG so the result can be looked at

That branch is not merged here yet. Review it, then point the dependency at it
or merge it upstream.
