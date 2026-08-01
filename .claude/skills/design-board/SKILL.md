---
name: design-board
description: Design a whole board from a one-line request - work out the blocks, choose the parts, then build, review, simulate and lay out every block. RUN THIS when the user asks for a board rather than for a change to one. Triggers on "make me a 2.5GHz SDR", "design a board that", "I need a PCB for", "build me an eval board for", "a high power buck converter", "can you design", or any request for hardware that does not yet exist.
---

# From a sentence to a verified schematic

The user says what they want in a line. What comes back is a hierarchical KiCad
schematic, laid out and grouped, every part a real in-stock JLCPCB part, every
value traceable to a datasheet or a calculation, and a notebook per block whose
plots are already rendered.

Five phases, and you stop for the user exactly once.

```
1 REQUIREMENTS   turn the line into a spec
2 ARCHITECTURE   blocks, anchor parts, availability
    ---------- the one approval gate ----------
3 BLOCKS         one agent per block, each fanning out to two more
4 INTEGRATE      compose, generate, lay out, verify
5 REPORT         what passed, what did not, what is not verified
```

## 1. Requirements

A one-line request leaves most of the design unstated, and the unstated parts
are where a board goes wrong. Work out, and write down:

- **Rails.** What comes in, what has to be made, how much current each needs.
- **Interfaces.** What it talks to and over what: USB, Ethernet, SPI, an
  antenna, a motor.
- **The number that decides the design.** Output power for a converter,
  frequency and bandwidth for a radio, resolution and rate for a data
  acquisition board. There is usually one.
- **Assembly.** Assume JLCPCB PCBA unless told otherwise, which is what makes
  the sourcing policy strict.
- **What it is for**, in a sentence. It settles a surprising number of later
  arguments.

Ask the user only what you genuinely cannot decide. State the rest as
assumptions - a stated assumption can be corrected at the gate; a question
cannot be answered by someone who is not there.

Write it to `<project>/design/spec.md` **before** the gate, and do not edit it
afterwards. Every later agent reads it, and a spec that moves is not a spec.

## 2. Architecture

Decomposition is research, not recall. Do not reach for a remembered block
diagram; find the part and read what its maker says.

1. **Find the anchor part** - the one part the board exists around. An AD9361
   for the SDR, a TPS40170 for the converter, the device under test for an eval
   board. Search the catalogue for it with the `source-parts` skill, because a
   part nobody stocks is not an anchor.
2. **Read its typical application circuit.** That diagram *is* the block list
   for everything immediately around the part, and the `reference-circuit`
   skill takes it from there.
3. **Add the blocks the anchor implies but does not draw.** One supply per rail
   it names. A clock for every reference input. An interface for every bus. A
   connector for every signal that leaves the board. Protection wherever the
   outside world gets in.
4. **Apply the `circuit-hierarchy` test.** Anything that exists once per phase,
   per channel or per port belongs *inside* the block that repeats, not beside
   it. Numbered ports mean the decomposition is wrong.

`PATTERNS.md` lists the block shapes that recur, as prompts for step 3. It is
not a lookup table, and a board that matches nothing in it is normal.

### The approval gate

Show the user, and then stop:

- the block diagram, one line per block with its ports and instance count;
- the anchor part for each block, with LCSC number, Basic or Extended, stock
  and unit price;
- anything that had to be sourced outside JLCPCB, flagged as unassemblable;
- what you assumed;
- roughly how many agents this will take, so the cost is a decision rather than
  a surprise.

Wait. A wrong architecture caught here costs a minute; caught in phase 4 it
costs the run.

## 3. Blocks

One `block-designer` agent per block, in parallel. Each one fans out to two
more, **in this order and not the other**:

```
block-designer
  1. writes the @circuit function, values left as placeholders
  2. block-reviewer     the connections, and only the connections
  3. block-simulator    the values, and only after the reviewer is done
```

The ordering is not advice. `block-reviewer` writes `connections_frozen: true`
into `review.json`, and `block-simulator` will not start without it. A
simulator that changes topology is re-deriving the design while measuring it,
and neither result can be trusted.

If `block-simulator` believes the topology is wrong, it says so and stops. The
designer re-runs the reviewer. Three rounds, then it comes to the user.

Every block returns the same directory, and that contract is what lets the
blocks be built independently - see `BLOCK_CONTRACT.md`.

## 4. Integrate

Compose the blocks into one root circuit from their `interface.json` files,
then:

```
generate  ->  layout-schematic  ->  make_spice_clean  ->  verify_project
```

`verify_project` runs every check the toolchain has and reports one verdict.
Read the renders it produces. Actually look at them.

## 5. Report

Say plainly:

- every check, passed or failed;
- every part, with its LCSC number and price, and the board's part cost;
- anything not sourceable from JLCPCB, and what that means for assembly;
- **what is not verified**. This matters more than the rest.

## What this cannot verify, and must say so

Every automated check compares the drawing against the Python. A schematic that
draws the wrong circuit perfectly passes all of them. `review-circuit` is what
catches a wrong circuit, and it runs on the Python, before any of this.

Some things a schematic cannot express at all:

- **RF above a few hundred MHz.** Impedance, matching and stackup *are* the
  design, and none of them is visible in a netlist. For a 2.5GHz board, say
  that matching networks are placeholders pending EM simulation and a chosen
  stackup. Do not describe such a board as verified.
- **Thermal.** A part that dissipates 3W needs copper, and the schematic does
  not know how much.
- **Layout-dependent behaviour.** Loop area, return paths, crosstalk. A note on
  the sheet is the most a schematic can do.

Saying so is the deliverable. A board reported as verified when it is not is
worse than one reported honestly as unfinished.
