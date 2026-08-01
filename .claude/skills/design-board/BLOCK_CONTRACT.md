# What a block agent returns

Blocks are built in parallel by agents that cannot see each other's work, so
what a block returns has to be enough to compose it without asking. This is
that interface.

Everything goes in `<project>/blocks/<Name>/`.

## `block.py`

The `@circuit` function, importable on its own. Ports declared with `Input`,
`Output`, `Bidirectional`. No side effects at import time.

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

## `notebook.ipynb`

This block's section, pre-executed, structured as the `simulate-block` skill
describes.
