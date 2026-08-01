---
name: circuit-hierarchy
description: Decide the block hierarchy before writing a circuit in Python - what the hierarchical sheets are, what their ports are, and what nests inside what. RUN THIS FIRST whenever a new circuit or board is being designed, or a new block is being added to one, before any components are written. Triggers on designing a circuit, "make me a board", "add a driver stage", "write the Python for this circuit", planning schematic blocks, deciding subcircuits.
---

# Deciding the hierarchy first

A `@circuit` block is a class and each call is an instance. Getting that
structure wrong is the expensive mistake in this toolchain: it is not a
refactor, it is regenerating the project and laying out every sheet again.

Work the hierarchy out before writing a single `Component`.

## The question to ask about every piece of the design

**How many of these are there?**

If there is one per phase, per channel, per port, per cell, per motor - it
belongs *inside* the block that is repeated, not beside it.

## The mistake

A three-phase driver, written the wrong way round:

```python
# WRONG. BemfSense senses all three phases, so it writes out per-phase
# hardware three times inside itself - while HalfBridge, the thing that is
# actually instantiated three times, does not contain the sensing for its own
# phase.
half_bridge(a_high, a_low, phase_a, ...)   # x3
bemf_sense(bemf_a, bemf_b, bemf_c, zc_a, zc_b, zc_c)
```

```python
# RIGHT. One phase's sensing is one block, nested inside the block that
# repeats. Three half-bridges give three of everything a phase needs.
@circuit(name="HalfBridge")
def half_bridge(HI, LI, PHASE, VM, VDRV, ISENSE, NEUTRAL, ZC):
    ...
    back_emf(PHASE, NEUTRAL, VDRV, ZC)
```

## Tests that catch it

- **Numbered ports.** A port list with `BEMF_A`, `BEMF_B`, `BEMF_C` - or
  `CH1_IN`, `CH2_IN` - is one block doing the job of N. Make it one block and
  instantiate it N times.
- **A loop over channels.** A `for` loop inside a block body that walks the
  phases or channels is the same smell from the inside.
- **A block that only ever has one instance but sits next to one that has
  many.** Ask whether its contents actually belong to each instance.

## Shared nets are ports, not a reason to flatten

The thing that pushes people towards the wide block is one signal every
instance touches: a virtual neutral, a shared bus, a common reference, a fault
line. That is a **port** on the repeated block, handed the same net by the
parent.

In the driver above, each `BackEmf` feeds one resistor into `NEUTRAL`; the
three together make the star point, and no block senses more than its own
phase.

## Put a measurement with what it measures

A divider monitoring the motor rail belongs in `Power`, whose output it
measures - not in a sensing block that happens to own other dividers. Follow
the signal to its source and put the circuit there.

## Do not force nesting

Nest when the inner block is genuinely a repeated unit with its own interface.
A block invented to hold two resistors that already sit beside the part they
belong to is noise: it costs a sheet, a set of sheet pins and a page turn to
read. If it is not repeated and has no clean interface, leave it inline.

## Before writing code

State the hierarchy in one line per block: its name, its ports, and how many
instances there are.

```
ThreePhaseDriver (root)
+-- Power          VBUS -> VMOTOR, V3V3, VRAIL_SENSE          x1
+-- UsbProgramming VBUS, USB_DP, USB_DM                        x1
+-- Mcu            V3V3, USB_DP/DM, 6x gate, 3x ISENSE, 3x ZC  x1
+-- HalfBridge     HI, LI, PHASE, VM, VDRV, ISENSE, NEUTRAL, ZC x3
    +-- BackEmf    PHASE, NEUTRAL, V3V3, ZC                     x3 (one each)
```

If any line has numbered ports, fix the hierarchy before going further.

Ground and the supply rails do not appear in that list: they are drawn as
power symbols and connect by name across the whole design, so they are not
ports.

Then write the circuit, generate it, and run the `layout-schematic` skill -
which is not optional either.
