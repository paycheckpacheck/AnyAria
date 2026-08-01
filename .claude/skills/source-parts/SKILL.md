---
name: source-parts
description: Choose every part on a board from JLCPCB's catalogue, in stock and at a sensible price, and import its real symbol and footprint. RUN THIS whenever a component is added to a circuit, before writing the Component() call. Triggers on adding any part, "what capacitor should I use", "find me a part for", picking an MCU or regulator, building a BOM, "can this be assembled", "is this part available".
---

# Every part is one that can be bought and assembled

A schematic full of parts nobody stocks is a drawing, not a design. The board
is going to be assembled, so every part on it - the microcontroller and the
100nF capacitor equally - has to be orderable now, at a price that does not
make the board pointless, and preferably from the assembler's own shelf.

Passives get waved through most often and are most of the bill of materials, so
they get the same treatment as everything else.

## Never write a symbol from memory

A `Component(symbol=...)` written from memory is wrong often enough to matter,
and a wrong footprint used to survive all the way to the board house. Import the
part instead and the symbol, the footprint and the 3D model all come from the
part itself, so they exist and they match each other.

```python
from pathlib import Path
from circuit_synth import Component
from circuit_synth.manufacturing.sourcing import SourcingPolicy, source_and_import

part = source_and_import(
    "100nF 0603 X7R 50V ceramic capacitor",   # be specific, see below
    role="IOVDD decoupling",                  # recorded, so the choice is reviewable
    project_dir=Path("build/my_board"),
    policy=SourcingPolicy.for_passive(),
)

cap = Component(
    symbol=part.symbol,          # a real symbol, in the project's own library
    footprint=part.footprint,    # the footprint that part actually has
    ref="C", value="100nF",
    LCSC=part.part.lcsc, MPN=part.part.model,
)
```

The library is written into the project, so the project carries its own parts
and opens on a machine that has never seen them. Nothing has to be added to
`KICAD_SYMBOL_DIR` by hand.

## Search specifically

A search is only as good as its query, and the catalogue is large.

| Bad | Good | Why |
|---|---|---|
| `100nF` | `100nF 0603 X7R 50V ceramic capacitor` | a 0402 X5R 6.3V is not a substitute |
| `10k resistor` | `10k 0603 1% 0.1W resistor` | tolerance and power rating are part of the choice |
| `LDO` | `LDO 3.3V 500mA SOT-223 fixed output` | package and current decide the part |
| `RP2040` | `RP2040` | a specific part number is already specific |

## The policy

`SourcingPolicy` is the rule, and there are two ready-made ones:

- `SourcingPolicy.for_passive()` - stock above 10,000, under 10 cents. There is
  no reason to fit an unusual passive.
- `SourcingPolicy.for_anchor()` - stock above 100, no price ceiling. The part a
  block exists for is worth paying for and is rarely Basic.

**Basic beats Extended even when Extended is cheaper per unit**, because an
Extended part carries a per-reel loading fee that is not in the unit price. A
board with four Extended parts costs meaningfully more to build than the same
board with one.

## When nothing fits

`choose()` raises rather than substituting. That is deliberate: a silent
substitution is how a board ends up with a part that does not do the job. The
options, in order:

1. **Loosen the query.** A different package or a nearby value is often fine
   and is a design decision worth making explicitly.
2. **Loosen the policy.** Allowing an Extended part, or a higher price, for a
   part that genuinely needs it.
3. **Go elsewhere.** DigiKey, through
   `circuit_synth.manufacturing.digikey.api_client`, is the last resort and
   needs credentials. A part sourced this way **cannot be assembled by JLCPCB**,
   so it is recorded as a deviation and reported to the user rather than being
   quietly used.

Say which of the three happened, and why. A board that cannot be assembled as
drawn is a thing the person paying for it needs to know before it is ordered.

## What gets recorded

Every choice goes into the block's `parts.json` through `SourcedPart.to_dict()`:
the LCSC number, Basic or Extended, price, stock, the manufacturer part number,
the symbol and footprint, **the query that found it**, the parts that were
considered and passed over, and any deviation. That is what makes the choice
reviewable a month later, and what proves the board is buildable.

## Checking a board is buildable

Every part on the board needs an `LCSC` property. A part without one has not
been sourced, however real its symbol is - that is the check, and it is worth
running before ordering anything.
