---
name: reference-circuit
description: Copy a part's recommended application circuit verbatim from its datasheet, then check line by line that it was copied exactly. RUN THIS whenever a design uses a microcontroller, FPGA, regulator, PHY, gate driver, RF part or anything else whose datasheet publishes a typical or minimal application circuit - before writing the Python, and again after. Triggers on adding an MCU, "use an RP2040/STM32/ESP32", "design a board around", "add a regulator", "is this circuit right", "check this against the datasheet", reviewing an existing block.
---

# Copy the reference circuit, then prove you copied it

A microcontroller's supporting circuit is not a design problem. The vendor has
already solved it, tested it over temperature, and published the answer. Every
part of it that gets improvised instead is a bug waiting to be found on a
board that has already been made.

So: **find the recommended circuit, copy it verbatim, then check it item by
item.** The checking is the part people skip, and it is the part that catches
things, because a circuit copied from memory is not a copy.

## The loop

1. **Find the document.** Not a blog post, not a reference board schematic
   from a third party, not what you remember. The vendor's hardware design
   guide or the datasheet's "typical application" section. Record its document
   number and revision - `RP-008279-DS`, `SLVSCJ8`, whatever it is - because
   that number goes in the code and on the sheet.
2. **Read the whole section.** Fetch the PDF and read it. The values are not
   the whole story; the text around them says which are load-bearing. "A 1k
   series resistor is a good value to prevent the crystal being over-driven"
   and "any deviation will require extensive testing" is the difference
   between a resistor you may substitute and one you may not.
3. **Write the checklist first.** One line per component and per connection
   the document specifies, with its value and the pin it attaches to. This is
   the artifact you check against later, so write it before you write the
   circuit, while you are still reading rather than remembering.
4. **Write the Python from the checklist**, not from the datasheet and not
   from memory.
5. **Check it back, one line at a time.** Go through the checklist against the
   code and mark each item present, absent, or different. Absent and different
   both need a written reason.
6. **Write the reasons onto the sheet.** Every deviation, and every addition
   the reference does not have, gets a sentence in the block's group-box
   rationale saying what it is and why. See the `layout-schematic` skill.

## What "verbatim" covers

Copy all of it, including the parts that look like they do nothing:

- **Every decoupling capacitor, at its stated value, per the stated pin.** "One
  100nF per power pin" means one per pin, not one per rail. Where the document
  makes an exception - a regulator that wants 1uF rather than 100nF at each end
  - that exception is the point of reading it.
- **Series and damping resistors.** A resistor in series with a crystal, a
  gate, a clock or a data line is there for a reason the schematic does not
  show. These are the single most commonly dropped item.
- **Termination.** Series termination on USB, differential pairs, anything
  fast. Its absence is invisible until the board is measured.
- **Straps and boot pins.** Whatever puts the part into its programming or
  recovery mode. A board with no way into the bootloader is a board that
  cannot be programmed, and this is discovered after assembly.
- **Pull-ups and pull-downs the document draws**, including ones marked DNF -
  fit the footprint even when the part is not fitted, and say why in the note.
- **The crystal circuit exactly**: frequency, both load capacitors, the series
  resistor, and the specific part where one is named. Load capacitance is
  arithmetic - two capacitors in series plus a few pF of board parasitic - so
  state the arithmetic in the rationale.

## Checking it back

Do this as a list, in the transcript, not in your head:

```
RP2040 minimal design, RP-008279-DS ch.2
  [x] 100nF on each of IOVDD 1,10,22,33,42,49        C9-C14
  [x] 100nF on USB_VDD 48                            C15
  [x] 1uF on VREG_VIN 44                             C16     (not 100nF - s2.1.3)
  [x] 1uF on VREG_VOUT 45                            C17
  [x] DVDD 23 and 50 both to VREG_VOUT                       (symbol stacks them)
  [x] 10k pull-up on QSPI_SS                         R8
  [x] 1k BOOTSEL strap on QSPI_SS to a header        R6, J3
  [x] 12MHz crystal, 2x 15pF at its terminals        Y1, C6, C7
  [x] 1k series between XOUT and the crystal         R5
  [x] 27R series on USB_DP and USB_DM                R10, R11
  [+] 10k + 100nF on RUN                             R7, C8  ADDITION: reset button
  [+] 10R + 100nF into ADC_AVDD                      R9, C18 ADDITION: ADC noise
```

`[x]` copied, `[ ]` missing, `[~]` different with a reason, `[+]` an addition
the reference does not have. Anything that is not `[x]` needs a sentence, and
that sentence belongs on the schematic, not only in the transcript.

## Stacked pins

Some symbols draw several pins of the same net on one point - the RP2040's six
IOVDD pins, its two DVDD pins. KiCad then joins them whether or not the Python
did. If the Python connects one and not the other, the schematic and the
Python disagree and `validate_layout` reports it. Connect all of them
explicitly.

## When there is no reference circuit

Say so, and say what you used instead. A part with only a block diagram and a
parameter table needs the circuit derived from the parameter table, and the
derivation - which parameter, which equation, what margin - goes in the
rationale. That is a different and weaker claim than "copied from figure 8",
and the sheet should say which of the two it is.
