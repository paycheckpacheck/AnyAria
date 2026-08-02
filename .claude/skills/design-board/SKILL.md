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
2 ARCHITECTURE   blocks, anchor parts, availability, and the KiCad project
                 itself - generated from empty blocks, as a block diagram
    ---------- the one approval gate ----------
3 BLOCKS         one agent per block, each fanning out to two more; each one
                 writes its own sheet into that same project
4 CLOSE          spice hygiene, verify, read the renders
5 REPORT         what passed, what did not, what is not verified
```

The project exists before the agents do. That is the whole shape of this: the
user approves a real KiCad project rather than a paragraph, and every block
agent then fills in its own page of it rather than building something somebody
has to compose afterwards.

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

### Build the block diagram, as a real KiCad project

Do this before the gate, not after it. A block list written in prose hides the
mistakes that a drawing makes obvious: a port with nowhere to go, a rail
nothing produces, a block wired to itself.

Write the design directory:

```
<project>/design/
    board.py            the root builder: defines board(), wires the blocks
    layout.py           ROOT_SPEC, the block diagram's own layout
    blocks/<Name>/block.py    a stub - ports declared, body empty
```

A stub is the block's real signature with nothing in it:

```python
from circuit_synth import Input, Output, circuit

@circuit(name="Supply")
def supply(RAW_IN: Input, VMON: Output):
    """The 3.3V rail, made from the raw input, with a tap that measures it."""
```

The annotations are what make it a block rather than a blank page: a parameter
annotated `Input`, `Output` or `Bidirectional` becomes a hierarchical port, and
a block that declares at least one gets a sheet symbol with sheet pins and a
matching hierarchical label on its own page - **even with no parts in it.** A
parameter left unannotated is not a port and will vanish without saying so, and
so will a net whose name matches a power symbol, because rails are drawn as
power symbols rather than pins. Check the generated JSON's `ports` for each
block before showing anyone.

Then generate and lay out the root:

```python
from circuit_synth.board import Board, build_board

board = Board(project / "design", project / "MyBoard")
result = build_board(board, note="block diagram")
print(result.summary())          # every block listed as having no layout yet
```

`ROOT_SPEC` is the only layout you write. It is a block diagram, so wire it
like one: one sheet symbol per block arranged left to right, every sheet pin on
a short stub with a **label** on it rather than a wire run across to the block
it talks to. Six blocks wired point to point is a rat's nest; the same page in
labels reads at a glance.

### The approval gate

Show the user, and then stop:

- **the rendered root sheet**, which is the block diagram - not a description
  of one;
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

**Each agent writes its own sheet into the project you already generated.** It
replaces its stub `block.py` with the real circuit, calls `build_board`, looks
at the sheet it got, decides the placement, writes it, and calls `build_board`
again. It runs the KiCad generation and the layout pass itself. There is no
preview project, and there is nothing left over for an integrator to apply.

### Why regenerating the whole project is the right answer

`Circuit.generate_kicad_project` walks the entire hierarchy and writes every
sheet. There is no call that adds one sheet to an existing project, and the
incremental path that looks like one is broken (see below). That sounds like it
should make this impossible, and it does not, because **the root builder reads
every block from a separate `block.py` on disk.** Regenerating is not throwing
away the other agents' work; it is picking up whatever every agent has written
so far. A block nobody has filled in yet regenerates as the stub it still is.

`build_board` therefore treats a build as a pure function of the design
directory:

```
build = generate(every block.py) + apply(every layout.py) + apply(ROOT_SPEC)
```

which is what makes it safe from several agents at once. They serialise on a
lock file, and because each build reproduces the whole design from disk, the
agent that writes last does not overwrite the others - it includes them.

**When two agents finish at the same moment**, the second waits out the first's
build and then runs its own, which redoes the first agent's sheet as well. That
costs the wall time of one generation and nothing else. If the wait passes the
timeout, the build raises `BuildBusy` and writes nothing, which is deliberate:
a project written without the lock is a torn file, and KiCad reports a torn
sheet as an empty page rather than as an error.

**Reference designators move**, because a part added to one block renumbers
every block after it. Nothing is applied by reference directly. Each block
records the circuit its placement was written against - `build_board` writes
`layout_refs.json` when the agent asks for it with `capture_refs` - and
`block_renames` maps that frame onto the current one positionally.
`instance_renames` then carries it onto the block's other instances, so a block
instantiated three times still costs one layout. Both mappings are derived from
the generated circuits; neither is ever written down.

## 4. Close the board

By the time the last agent returns, the project is already generated, already
laid out and already checked sheet by sheet. What is left is the whole-board
view:

```python
from circuit_synth.kicad.session import finish_editing
from circuit_synth.kicad.spice_hygiene import make_spice_clean
from circuit_synth.verify import verify_project

make_spice_clean(board.project_dir)
report = verify_project(board.root_schematic, board.circuit_json)
finish_editing(board.project_dir)
```

Then read the renders. Actually look at them - a block's sheet was judged on
its own, and a block that looks right on its own can still be wrong for the
board it landed in.

`examples/block_first_board/` is this whole sequence, small enough to run:
three blocks, one of them instantiated twice, agents in parallel, verified at
the end.

### The incremental update path does not work - do not reach for it

`generate_kicad_project` looks as though it can update a project in place, and
it cannot. Left at its default, `force_regenerate=False` sends an **existing**
project to the synchroniser rather than regenerating it
(`sch_gen/main_generator.py`, `generate_project`), and the synchroniser raises
`TypeError: 'SheetManager' object is not iterable` the moment it has to place a
component it did not already have. Any exception there aborts the whole call
rather than falling back, so the second generation of a project fails outright.

The cause is upstream and shallow: `kicad_sch_api`'s `Schematic.sheets` returns
a `SheetManager`, which defines no `__iter__`, while the dataclass of the same
name has a plain list. `schematic/placement.py` iterates it, and so do
`schematic/synchronizer.py` and `kicad/sch_gen/instance_utils.py` - the latter
two inside `except` blocks, which is worse: child sheets are silently never
loaded, and hierarchical instance paths silently come out wrong.

So `circuit_synth.board` passes `force_regenerate=True` on every build. That is
not a preference; it is the only path that runs. It also means the generator
overwrites but never deletes, so a block removed from the design leaves its old
`.kicad_sch` behind - harmless, and worth knowing when a stale sheet appears.

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
