# OpenBeam house style

Measured from `OpenBeam/OpenBeamV1` (KiCad 10.0.3, generator version 20260306):
`OpenBeamV1.kicad_sch` (root), `MCU`, `BasebandConverter`, `LoGen`, `TxChain`,
`RxChain`. `FPGA.kicad_sch` is an empty stub, `DownConverter.kicad_sch` is an
orphan copy of `RxChain` that the root does not instantiate, and `TxChain` and
`RxChain` are one part each with no layout yet. The three sheets worth copying
are **MCU**, **LoGen** and **BasebandConverter**; the root sheet defines the
block-diagram style.

Every coordinate below is in millimetres, in KiCad sheet coordinates, and was
read out of the `.kicad_sch` files. Where a number is a range, the project is
inconsistent and the recommended value is stated.

---

## The five things that make this project read well

**Boxes with names.** Every functional group is drawn inside a grey rectangle
with a title in large dark-red bold text above it. You can stand back from the
LoGen page and read "VCO LDO", "PLL LDO", "TXCO LDO", "PLL DECOUPLING CAPS",
"PLL REFERENCE SELECT", "Dual-PLL", "Loop Filter" before you look at a single
component. The boxes carry no electrical meaning at all - they exist purely so
the page has a table of contents.

**A column grid, not free placement.** Boxes are not scattered. Each page uses
two or three columns of fixed width - 104.14mm is the workhorse, 144.78mm the
wide one - with a 6.35 to 7.62mm gutter, and boxes stack down a column with the
same gutter between them. Because every box in a column shares its left and
right edges, the page has vertical lines the eye can follow even where nothing
is drawn.

**Repeated circuits drawn identically.** The three LDOs on LoGen are the same
seven parts in the same relative positions, in identical 104.14 x 27.94 boxes,
stepped down the page by exactly 35.56mm. You read the first one and then
recognise the other two rather than re-reading them.

**Power is symbols, never wires and never labels.** There are 77 power symbols
across the project and zero ground labels. Each supply domain gets its own
named power symbol - `+3V3_VCO`, `+3V3_PLL`, `+3V3_RF`, `+3V3_XTAL`,
`+3V3_CP`, `+3V3_DIG`, `+5V` - so a reader can see which rail feeds which pin
without tracing a wire. Ground always points down; supplies always point up.

**Stubs and labels instead of long wires.** The RP2040 has fifty-odd used pins
and not one of them is wired to another part directly. Each gets a short stub
with a label on it. Across three finished sheets there are three wire crossings
in total, and only one wire longer than 50mm (the 120.65mm `+3V3_DIG` rail,
which runs in an otherwise empty horizontal channel at y=38.1).

---

## Page and frame

**Paper is A4 landscape on every sheet**, 297 x 210mm. This is a dense design
on a small page; the engineer chose to add sheets rather than grow the paper.

The KiCad drawing sheet gives:

| Feature | Extent |
|---|---|
| Outer frame | x 10 to 287, y 10 to 200 |
| Inner border (usable) | x 12 to 285, y 12 to 198 |
| Title block | x 177 to 285, y 166 to 198 |

Content actually occupies:

| Sheet | Content bbox | Fill of usable area |
|---|---|---|
| MCU | x 21.59-278.13, y 21.59-175.26 | 87% wide, 83% tall |
| LoGen | x 21.59-278.13, y 17.78-193.04 | 94% wide, 94% tall |
| BasebandConverter | x 16.51-265.43, y 21.59-194.31 | 91% wide, 95% tall |
| OpenBeamV1 (root) | x 53.34-243.84, y 43.18-152.40 | 70% wide, 59% tall |

**Rules.**

- Keep all content inside x ∈ [16.51, 278.13], y ∈ [17.78, 194.31]. That leaves
  4.5 to 7mm inside the inner border, which is what the project does.
- **Below y=166, stay left of x=177** - that is the title block. LoGen's right
  column stops at y=163.83 for exactly this reason; MCU's right box stops at
  160.02, BasebandConverter's at 156.21. Only the left columns run down to
  y=193-194.
- Fill the page. A finished sheet here uses 85-95% of the usable width and
  height. The root sheet is the exception and it is the one page that looks
  half-empty.
- One page is several circuits, not one. LoGen holds seven groups, MCU four,
  BasebandConverter four. A page with one circuit on it (TxChain, RxChain) is
  unfinished work, not the style.

## Grid

**Everything electrical is on the 1.27mm grid.** Wire endpoints: 224/224 on
MCU, 84/84 on BasebandConverter, 174/186 on LoGen. Symbol origins: 48/48 on
MCU, 12/12 on BasebandConverter, 94/97 on LoGen. Pin pitch on every IC used is
2.54mm, so signal rows land on 2.54.

The handful of off-grid items are hand-nudged mistakes, and they are the ones
that look wrong: `C25`, `C29`, `C30` on LoGen sit at x=83.9816 (should be
83.82), which puts a 7.458mm wire on the sheet where every other wire in that
block is a multiple of 1.27.

**Group rectangles are on the 1.27mm grid too** - all 16 corner coordinates on
MCU, LoGen and the root are exact multiples of 1.27. The one exception is
BasebandConverter's empty "Adjustable Analog Reference" box at
(22.606, 140.208), which is off-grid on all four coordinates.

**Free text is placed on a 0.254mm sub-grid.** Every group title anchor is an
exact multiple of 0.254 but not of 1.27. Text has no connectivity so a finer
grid is harmless and lets a title be centred properly.

## Group boxes

This is the single strongest feature of the style, and it is entirely
mechanical.

### Geometry

Every group box in the project is written as:

```
(rectangle
  (start X0 Y0) (end X1 Y1)
  (radius 0.0508)
  (stroke (width 0.508) (type default) (color 105 105 105 1))
  (fill (type none)))
```

- **Stroke width 0.508mm** on all 16 boxes. That is 3.3x the project's default
  line thickness (0.1524mm), so the box reads as a frame and never as a wire.
- **Colour RGB(105, 105, 105)**, alpha 1 - dim grey. Never the default colour;
  a default-coloured rectangle would read as schematic graphics.
- **`(type default)`** - solid line, not dashed.
- **`(fill (type none))`** - always unfilled. A filled box would hide the grid
  and fight the symbol bodies.
- **`(radius 0.0508)`** on all 16. That is 2 mils and invisible at any print
  size; corners are effectively square. Copy the value for consistency but do
  not treat it as a rounded-corner style.

### Size and placement

Box widths come from a small set: **104.14mm** (11 of 16 boxes), **144.78mm**
(3), 77.47mm (1), 54.61mm (1), plus the root's 190.5mm frame. Heights are
whatever the contents need, on the 1.27 grid.

Pages are laid out as columns of boxes sharing left and right edges:

| Sheet | Column 1 | Column 2 | Gutter |
|---|---|---|---|
| LoGen | x 21.59-125.73 (104.14 wide) | x 133.35-278.13 (144.78) | 7.62 |
| MCU | x 21.59-166.37 (144.78) and x 41.91-146.05 (104.14) | x 173.99-278.13 (104.14) | 7.62 |
| BasebandConverter | x 16.51-71.12 (54.61) | x 77.47-154.94 (77.47), x 161.29-265.43 (104.14) | 6.35 |

Vertical gaps between stacked boxes: **6.35 or 7.62mm** on LoGen (four gaps),
8.89 and 11.43 on MCU, 11.938 on BasebandConverter. Use **6.35mm**.

**Recommended rule for a styler:** choose one column width per page from
{54.61, 77.47, 104.14, 144.78}, set the gutter to 7.62mm horizontally and
6.35mm vertically, and align every box in a column to the same x0 and x1.

### Margin inside the box

Measured as the clear distance from the box edge to the nearest part outline
(pin ends included), for the 12 boxes that contain parts:

| Sheet, box | Left | Right | Top | Bottom |
|---|---|---|---|---|
| LoGen, PLL DECOUPLING CAPS | 8.128 | 5.588 | 3.810 | 3.810 |
| LoGen, VCO/PLL/TXCO LDO (x3) | 18.288 | 26.670 | 7.620 | 3.810 |
| LoGen, Dual-PLL | 8.128 | 37.338 | 5.080 | 3.810 |
| LoGen, Loop Filter | 80.518 | 24.638 | 6.350 | 3.810 |
| LoGen, PLL REFERENCE SELECT | 1.270 | 8.890 | 2.540 | 3.810 |
| MCU, RP2040 MCU | 3.048 | 5.588 | 5.080 | 17.780 |
| MCU, Digital Power | 8.890 | 60.198 | 5.080 | 5.080 |
| MCU, NAND FLASH | 8.128 | 11.430 | 12.700 | 6.350 |
| MCU, XTAL | 24.130 | 35.560 | 12.700 | 6.350 |
| BasebandConverter, Baseband Converter | 27.940 | 26.670 | 19.050 | 21.590 |

**Bottom margin is 3.810mm on eight of twelve boxes** - the tightest and most
consistent edge, because a row of ground symbols usually sets it. The absolute
minimum anywhere is 1.27mm (LoGen's PLL REFERENCE SELECT, which is also the
messiest block on the page).

**Rule:** leave **3.81mm** minimum clear on every side, and never less than
2.54mm. Size the box to the column width, then to contents-plus-3.81 in height,
rounded up to 1.27.

### Titles

A group box title is a `(text ...)` item with:

```
(effects (font (size 2.54 2.54) (thickness 0.762) (bold yes)
               (color 151 0 0 1)))
```

- **Size 2.54 x 2.54mm** - exactly twice the project's default text size, and
  twice every net label on the page. Used on all 16 titles including the root's
  "OpenBeam SDR v1".
- **Thickness 0.762mm, bold yes.** Heavy enough that the titles are the first
  thing you see.
- **Colour RGB(151, 0, 0)** - dark red. This colour appears nowhere else in the
  project except the root title, so "dark red 2.54mm bold" means "group title"
  and nothing else.
- **No `justify`** - KiCad's default for free text, which centres it
  horizontally and vertically on the anchor. Confirmed against the rendered PDF:
  "Loop Filter" has anchor x=201.422 and a rendered ink span of 190.32 to 212.5,
  centre 201.4.

Placement relative to the box, over all 16 titles:

- **Vertical: anchor y = box top edge − 3.048mm.** Measured offsets run 2.032 to
  4.826, median 3.175, modes 3.048 and 3.556. So the title sits fully outside
  and above the box, clear of anything inside it. Examples:
  `MCU.kicad_sch` "XTAL" at (89.662, 83.82) over a box whose top is 87.63;
  `LoGen.kicad_sch` "Loop Filter" at (201.422, 117.348) over a box top of
  120.65; root "OpenBeam SDR v1" at (141.224, 40.132) over 43.18.
- **Horizontal: anchor x = box centre x.** Hand placement drifts: measured
  deviations from the true centre run −7.874 (LoGen "Dual-PLL ", which is
  centred over the chip rather than the box) to +1.143 (BasebandConverter
  "Baseband Converter"), median −3.8. The intent is centred; centre it exactly.

Titles are short noun phrases naming the function, in the engineer's own
capitalisation - which is not consistent. Title Case is used on MCU and
BasebandConverter ("Digital Power", "Baseband Converter", "Adjustable Analog
Reference", "IF Phase-Shifters", "Loop Filter"); ALL CAPS on the LoGen power
blocks ("VCO LDO (3V3)", "PLL DECOUPLING CAPS", "PLL REFERENCE SELECT") and on
MCU's "XTAL" and "NAND FLASH". **Use Title Case**, and put a qualifying value in
brackets when it disambiguates - "VCO LDO (3V3)" tells you which of the three
identical LDO blocks you are looking at.

Boxes may be drawn empty as a placeholder for work not yet done -
BasebandConverter has two ("IF Phase-Shifters", "Adjustable Analog Reference"),
LoGen has none. An empty titled box is how this engineer reserves space on a
page.

### The root sheet's box

The root has one box, (53.34, 43.18) to (243.84, 152.4), 190.5 x 109.22, same
stroke and colour, enclosing all five sheet symbols and titled with the product
name "OpenBeam SDR v1". It is a frame around the whole block diagram rather than
a functional group. It leaves 22.86mm on the left, 31.75 right, 17.78 top and
25.4 bottom of its contents - much more generous than a group box, because it is
a border, not a grouping.

## Text: sizes, weights and colours

| Item | Size | Thickness | Bold | Colour | Where |
|---|---|---|---|---|---|
| Group title / sheet title | 2.54 | 0.762 | yes | 151,0,0 dark red | all 16 `(text)` titles |
| Local net label | 1.27 | 0.254 | yes | default (black) | MCU (30), BasebandConverter (40) |
| Local net label (variant) | 1.27 | - | no | default | LoGen (13) |
| Hierarchical label | 1.27 | 0.254 | yes | default (olive) | all 27 across three sheets |
| Warning note | 1.27 | 0.254 | yes | 255,37,23 bright red | LoGen |
| Value note | 1.27 | - | no | default (blue) | LoGen |
| Symbol Reference and Value | 1.27 | - | no | default | every symbol, all sheets |
| Sheet symbol name (hand-placed) | 1.905 | 0.254-0.381 | yes | default (teal) | root, MCU/BasebandConverter/LoGenerator |
| Sheet symbol name (autoplaced) | 1.27 | - | no | default | root, TxChain/RxChain |
| Sheet symbol file name | 1.27 | - | no | default (olive) | root, all five |

There are only **three text sizes in the whole project**: 1.27 for everything
that belongs to the circuit, 1.905 for a sheet symbol's name, 2.54 for a group
or sheet title. The project's `default_text_size` is 50 mils = 1.27mm, so the
title is 2x default and the sheet name 1.5x.

**Colour carries meaning here and only these three overrides exist:**

- **RGB(151, 0, 0)** dark red - a group or page title. Nothing else.
- **RGB(255, 37, 23)** bright red - a warning the reader must not miss. Used
  once.
- **RGB(105, 105, 105)** dim grey - a group box outline.

Everything else takes KiCad's default colour for its item type, which is what
gives the pages their consistent look: local labels black, hierarchical labels
olive, bus labels navy, power symbol names teal, pin numbers red, pin names
teal, wires green, symbol bodies yellow with a dark red outline.

**Do not colour a note blue explicitly.** The one uncoloured note renders in
KiCad's default notes blue, which reads as "informational" against the two reds.

## Notes and design rationale

There are exactly two free notes in the live project, plus one pasted image.
This engineer does not annotate much - but when he does, the note is a physical
or numerical constraint that the schematic cannot express, placed against the
thing it constrains.

**Verbatim, all of them:**

> `** KEEP RETURN LOOP TIGHT **`

`LoGen.kicad_sch`, at (168.91, 160.528), size 1.27, thickness 0.254, bold,
colour RGB(255, 37, 23). Inside the "Loop Filter" box, 3.302mm above the box's
bottom edge (163.83), horizontally centred under the pasted phase-noise plot at
the same x=168.91. It is a **layout instruction to the PCB designer** carried on
the schematic, and it is shouted - all caps, bright red, wrapped in `**`
markers, which is the only emphasis convention in the project.

> `Bandwidth = 60kHz`

`LoGen.kicad_sch`, at (262.89, 160.528), size 1.27, no bold, no colour override
so it renders in the default notes blue. Sits at the bottom-right of the loop
filter's R/C network, on the **same baseline y=160.528 as the warning note**, so
the two notes form one row along the bottom of the box. It states the **design
target the component values were chosen to hit** - the one number a reader would
otherwise have to recompute from C2, C3, C4, R1, R2.

> (pasted image) ADIsimPLL phase-noise plot, `LoGen.kicad_sch`, `(image (at 168.91 140.97) (scale 0.457288))`

A screenshot of the simulation that justifies the loop filter values, placed
inside the same "Loop Filter" box, to the left of the network it describes,
scaled to 0.457 so it fits. The warning note sits directly beneath it. This is
the engineer's way of writing "here is the evidence" on the page.

**The patterns to copy:**

1. A note describes one specific thing and is placed **inside that thing's group
   box**, not in a corner of the sheet and not in a general-purpose notes block.
2. Notes align to a common baseline within a box (both LoGen notes at
   y=160.528), 3.3mm above the box's bottom edge.
3. Notes are the same size as net labels (1.27mm). They are annotations, not
   headings; a note the size of a title would compete with the group names.
4. **Two registers.** A constraint that would break the design if ignored is
   bold, ALL CAPS, RGB(255,37,23), wrapped in `**`. A stated design value is
   plain, mixed case, default colour, `Name = value` form.
5. Rationale that is genuinely a picture goes on the page as a picture.

Some rationale is also carried in names rather than notes, and a styler should
preserve it: the LDO group titles state the rail voltage - "VCO LDO (3V3)" -
and the power symbols are renamed per domain (`+3V3_VCO`, `+3V3_PLL`,
`+3V3_RF`, `+3V3_CP`, `+3V3_DIG`, `+3V3_XTAL`) so that the reason
there are three identical LDOs is visible without a note explaining it.

## Flow and orientation

**Signals run left to right on every sheet.**

- `MCU.kicad_sch`: USB-C connector `USBC1` at x=40.64 on the far left, the
  NCP1117 LDO `U6` at x=90.17 in the middle, the `+3V3_DIG` rail leaving the
  Digital Power box to the right at y=38.1 and running 120.65mm across to the
  RP2040 at x=222.25.
- `BasebandConverter.kicad_sch`: the I/O box (hierarchical labels and bus
  fan-out) at x 16.51-71.12, the converter `U1` at x=118.11, the IF
  phase-shifter box on the right at x 161.29-265.43.
- `LoGen.kicad_sch`: supplies and reference in the left column, the PLL and loop
  filter in the right column, RF outputs leaving the right edge at x=265.43.

**Inside a block, the pin sides follow the same convention:** inputs on the
left, outputs on the right, supplies on the top, ground at the bottom. `U4`
(RP2040) has QSPI, USB, XIN/XOUT and SWD entering on the left, all GPIO leaving
on the right, all six supply pins on the top edge and its single ground pin (57)
on the bottom. `U2` (MAX2871) has all six `VCC_*` on the left going up to rail
symbols, all seven `GND_*` on the left going down to one ground symbol, and
every signal on the right.

**Supplies enter at the top of a block, ground leaves at the bottom.** No
exceptions found.

## Power and ground

**Ground is always `power:GND`, never a label and never a wire across the
sheet.** 77 GND symbols across the project; zero labels named GND. A ground
symbol sits directly below the pin or passive it grounds, connected by a
vertical wire of **2.54mm** (typical) or **5.08mm** (when a row of ground
symbols is aligned to a common y - `MCU.kicad_sch` C34-C40 all ground to y=36.83
from caps at y=31.75).

**Supply rails are power symbols too, one per domain, named by domain.** All are
instances of `power:+3V3` or `power:+5V` with the Value field renamed:
`+3V3_DIG`, `+3V3_PLL`, `+3V3_VCO`, `+3V3_RF`, `+3V3_XTAL`, `+3V3_CP`, `+5V`.
A supply symbol sits **2.54mm above** the pin it feeds
(`LoGen.kicad_sch` `#PWR046` at y=129.54 feeding `C10` pin 1 at y=132.08).

**Multiple supply pins on one chip fan out as a staircase.** `LoGen.kicad_sch`
`U2` has six `VCC_*` pins at 2.54mm pitch on its left edge; each gets a
horizontal wire left to its own power symbol, and the symbols step **6.35mm left
for every 2.54mm down**: (172.72, 35.56), (167.64, 38.1), (161.29, 40.64),
(154.94, 43.18), (148.59, 45.72), (142.24, 48.26). This keeps six differently
named rails legible where a single shared rail wire would hide which pin gets
which supply.

**Multiple ground pins on one chip tie to a single symbol.** Same chip: pins 8,
27, 9, 11, 31, 21, 18 and the exposed pad 33 all connect down a single vertical
wire on the left to one `power:GND` at (173.99, 101.6), with a junction at each
pin.

**One long rail wire per page is acceptable if it runs in clear space.** The
120.65mm `+3V3_DIG` wire on MCU from (104.14, 38.1) to (224.79, 38.1) is the
only wire over 50mm on the page and crosses nothing.

## Labels, stubs and wiring

**Orthogonal only.** 108 wire segments on MCU, 93 on LoGen, 38 on
BasebandConverter, zero diagonal.

**Crossings are essentially absent.** Two on MCU (both in the XTAL block, at
(77.47, 107.95) and (99.06, 107.95)), one on LoGen, none on BasebandConverter.
When a signal would have to cross something, it becomes a label instead.

**Junctions** at every 3-way meeting: 27 on MCU, 33 on LoGen, 3 on RxChain.
BasebandConverter has zero, because it wires nothing point-to-point.

**No `no_connect` flags anywhere in the project.** Unused pins - RP2040
GPIO10-GPIO17 and GPIO26-GPIO29 - are left with their pin stub and nothing on
it. This is a real property of the style, though it will produce ERC warnings;
do not add no-connects to match this project's look unless the user asks.

**Wire lengths.** Modal segment lengths are 2.54 and 1.27 (short connections
between adjacent parts), then 6.35, 7.62, 11.43. Median 2.54 on MCU, 6.35 on
LoGen, 11.43 on BasebandConverter.

**Label stubs.** Distance from the pin to the label anchor:

| Case | Length | Example |
|---|---|---|
| Local label on a stub off a small part | 2.54 - 3.81 | LoGen `CE`, `SW`, `VTUNE`; MCU flash right-side labels at 3.81 |
| Hierarchical label off a chip pin | 5.08 - 6.35 | MCU `PLL_LD` at (250.19, 101.6) off GPIO18 at x=243.84 → 6.35; LoGen 5.08 (five of twelve) |
| Local label at the end of a fan-out row | 10.16 - 17.78 | BasebandConverter bus fan-out |
| Signal run to the block boundary | 49.53 | LoGen `RFOUTA_N`/`RFOUTA_P`/`RFOUTB_N`/`RFOUTB_P` from x=215.9 to hierarchical labels at x=265.43, y 68.58/71.12/73.66/76.2 |

**Rule:** 6.35mm for a hierarchical label off a chip pin, 2.54mm for a local
label off a small part. Where a group's outputs leave the block, run them to a
common x just inside the box's right edge (LoGen: x=265.43 against a box right
edge of 278.13) and put the hierarchical labels there in a vertical column at
2.54mm pitch, so all the block's exports line up.

**Label anchoring.** Local labels use `(justify left bottom)`, so the text sits
above and to the right of its anchor point, which is on the wire. Hierarchical
labels use `(justify left)` on the right of a block and `(justify right)` on the
left. All labels are 1.27mm; local labels are bold on MCU and BasebandConverter
(68 of 81) and plain on LoGen (13) - **use bold**.

**Every hierarchical label is 1.27mm bold.** Their `shape` is `input` for 25 of
27 - the project does not bother distinguishing direction, and neither do the
root's sheet pins (25 of 27 `input`). This is a real inconsistency and a styler
should **not** copy it: declare the true direction, since KiCad draws the arrow
from it.

## Buses

Used once, for the 8-bit baseband paths, and worth copying exactly.

`MCU.kicad_sch`: the RP2040's GPIO0-GPIO7 and GPIO8-GPIO15 leave on stubs to a
vertical bus at x=252.73 through sixteen `(bus_entry (size 2.54 2.54))`, then
one horizontal bus segment to a bus label at x=254 and a hierarchical label
`BBRX[0..7]` / `BBTX[0..7]` at x=264.16. `BasebandConverter.kicad_sch` mirrors
it with `(size -2.54 2.54)` entries and the bus on the left at x=46.99.

- Bus entries are always **2.54 x 2.54** (a 45-degree stub), signed to match the
  side the bus is on.
- The bus stub, its `[0..7]` bus label and the matching hierarchical label are
  all present; the label names the range, the entries name the members.
- Individual member labels (`BBRX0` … `BBRX7`) sit on the far side of the
  entries at **2.54mm** vertical pitch, in one column - BasebandConverter's are
  all at x=50.8, y=30.48 to 48.26 and y=57.15 to 74.93. MCU has none: its bus
  goes straight from the GPIO pins into the entries, because the member names
  are already on the pins.
- A bus is worth it at eight members. Below that the project uses individual
  labels.

## Big parts: MCU and PLL pages

**Draw a big IC as a single tall body with stubs and labels, never with wires to
other parts.** `U4` (RP2040) sits at (222.25, 93.98) inside a 104.14 x 138.43
box and spans 43.18mm between its left and right pin ends (x 200.66 to 243.84)
and about 82mm top to bottom, and every one of its used pins terminates
in a label, a bus entry or a power symbol. Same for `U1` (MAX5865) on
BasebandConverter and `U2` (MAX2871) on LoGen.

**Group the pins by function on the symbol's edges** (this usually means editing
or choosing the library symbol): all supplies on the top edge, ground on the
bottom, buses and GPIO on one side, control and clocks on the other. The RP2040
symbol used here does exactly that and it is why the page works.

**Decoupling capacitors.** Three distinct patterns, all in use:

1. **Bulk row above the supply pins.** `MCU.kicad_sch` C34-C40, seven 100nF at
   **6.35mm pitch** in a horizontal row at y=31.75, a shared rail wire 2.54mm
   above them at y=26.67, and a row of ground symbols 5.08mm below at a common
   y=36.83. The row sits above the chip's supply pin row (y=52.07), inside the
   same group box.
2. **One cap right against the pin it decouples.** `MCU.kicad_sch` C41 (1uF) at
   (224.79, 43.18), its lower pin **6.35mm** above the VREG_VOUT/DVDD pin row;
   C43/C44 (100nF) at x=179.07 and 194.31, **6.35mm** to the left of the
   USB_VDD/ADC_AVDD pin column; C31 (100nF) directly below `U10`'s VCC pin at
   (62.23, 161.29) with ground under it. This is the one to prefer.
3. **A dedicated decoupling box** when a chip has many separately-named rails.
   `LoGen.kicad_sch` "PLL DECOUPLING CAPS", a 104.14 x 22.86 box holding six
   rail/cap-pair columns: a named power symbol at y=129.54, a 10nF and a 100pF
   standing vertically at y=134.62, a ground symbol each at y=139.7. **6.35mm
   between the two caps of a pair, 8.89-10.16mm between pairs** (columns at x =
   31.75/38.1, 48.26/54.61, 63.5/69.85, 80.01/86.36, 95.25/101.6,
   111.76/118.11). Use 6.35 within a pair and 10.16 between.

**Repeated blocks are stepped by a constant pitch.** `LoGen.kicad_sch`'s three
LDOs: `U16` at (68.58, 30.48), `U15` at (68.58, 66.04), `U14` at (68.58,
101.6) - **35.56mm apart**, in boxes at y0 = 17.78, 53.34, 88.9, all 104.14 x
27.94, with every passive at the same relative offset (input cap 26.67mm to the
left of the regulator, output caps to the right). Draw the block once and
translate it.

**Series passives** lie in line at **10.16mm centre pitch** with 5.08mm of wire
between them - `LoGen.kicad_sch` R1 at (236.22, 142.24) and R2 at (236.22,
152.4), with the `SW` tap junction between them at y=147.32.

**Minimum clear space between parts** is 2.54mm; the median nearest-neighbour
gap (outline to outline, pin ends included) is 2.286mm on MCU and 3.394mm on
LoGen. Use 2.54mm as the floor and 3.81mm as the target.

## Hierarchy and the root sheet

**The root is a block diagram, not a wiring diagram.** Five sheet symbols in a
grey box, mostly unwired: three wires and two buses in total, all 15.24mm long,
all between the two adjacent symbols MCU and BasebandConverter. The RF blocks
(TxChain, LoGenerator, RxChain) are placed but not yet connected.

Sheet symbols, from `OpenBeamV1.kicad_sch`:

| Name | `at` | `size` | Column |
|---|---|---|---|
| MCU | (76.2, 69.85) | 25.4 x 44.45 | 1 |
| BasebandConverter | (116.84, 60.96) | 33.02 x 66.04 | 2 |
| TxChain | (161.29, 60.96) | 30.48 x 15.24 | 3 |
| LoGenerator | (161.29, 87.63) | 50.8 x 15.24 | 3 |
| RxChain | (161.29, 111.76) | 30.48 x 15.24 | 3 |

- **Three columns at x = 76.2, 116.84, 161.29**, with the signal chain running
  left to right: controller, converter, RF. The three RF blocks stack in the
  right column.
- **15.24mm horizontal gap** between adjacent symbols, which is exactly the
  length of the wires between them.
- Sizes are on the 1.27 grid and sized to their pins: height ≈ 2.54 x (pins on
  the tallest edge) + margin.
- **Fill `(color 148 148 148 1)`, stroke `(width 0.1524) (type solid)`** on all
  five - a mid grey that separates a sheet symbol from a component body.

**Pin placement on a sheet symbol follows the signal, not the alphabet:**

- LoGenerator: control inputs on the **left** edge at 2.54 pitch (CE 92.71,
  SEL_EXT 95.25, PLL_LD 97.79, RF_EN 100.33); the SPI bus down from the **top**
  edge (SPI_MOSI 175.26, SPI_CLK 177.8, SPI_CS 180.34, SPI_MISO 182.88); the RF
  outputs on the **right** edge with the differential pairs adjacent and P
  before N (LOA_P 91.44, LOA_N 93.98, LOB_P 96.52, LOB_N 99.06).
- MCU: SPI and the baseband buses on the **right** edge facing the converter it
  talks to; the LO control signals on the **top** edge facing the LO block.

**Pin pitch is 2.54mm**, with 3.81-5.08mm of extra space before a bus pin
(MCU right edge: SPI at 85.09/87.63/90.17/92.71, then BBTX at 97.79 and BBRX at
101.6).

**Sheet name text: 1.905mm bold, placed inside the box near its top-left**, with
`(justify left bottom)` - MCU's name at (85.344, 83.058), BasebandConverter's at
(119.634, 66.294), LoGenerator's at (185.674, 95.758). The offsets are not
consistent because they were dragged by hand; **use 2.794mm right of the left
edge and 5.334mm below the top edge**, which is what BasebandConverter uses.
TxChain and RxChain still have KiCad's autoplaced 1.27mm name above the box -
that is the unstyled default, not the house style.

**Sheet file name: 1.27mm, `(justify left top)`, below the bottom-left corner**
of the box - KiCad's autoplacement, left alone everywhere.

## Where the project is inconsistent

State these so a styler picks one variant and applies it everywhere:

- **Local label boldness.** Bold on MCU and BasebandConverter (68 labels), plain
  on LoGen (13). Use bold.
- **Title capitalisation.** Title Case on MCU and BasebandConverter, ALL CAPS on
  LoGen's power blocks and MCU's "XTAL"/"NAND FLASH". Use Title Case.
- **Title vertical offset.** 2.032 to 4.826mm above the box. Use 3.048.
- **Trailing whitespace in titles.** Several titles carry a stray `\n` or `\n\n`
  ("RP2040 MCU\n", "Baseband Converter\n\n") or a trailing space ("Dual-PLL ").
  These do not shift the rendered position but they do skew the centring. Emit
  clean strings.
- **Hierarchical label and sheet pin direction.** 25 of 27 are `input`
  regardless of actual direction. Emit the true direction.
- **Sheet symbol name text thickness.** 0.381 on MCU and BasebandConverter,
  0.254 on LoGenerator. Use 0.381.
- **Off-grid parts.** `C25`, `C29`, `C30` on LoGen at x=83.9816, and the
  "Adjustable Analog Reference" box on BasebandConverter at (22.606, 140.208).
  Snap everything to 1.27 (graphics may use 0.254).
- **Collisions the engineer left in.** LoGen's "PLL REFERENCE SELECT" title
  overlaps a GND symbol's text from the box above it, `RF1`'s designator
  overlaps the SMA symbol body, and `U7`'s designator overlaps a GND label.
  These are the only text collisions in the project and they are a mistake, not
  a style. Check the render.
- **Boxes that are far larger than their contents.** MCU's "Digital Power" box
  leaves 60.198mm of empty space on the right; "XTAL" leaves 35.56. The box was
  sized to the column, not to the circuit. That is acceptable when it keeps the
  column edges aligned, but do not leave more than about half the box empty
  unless something is planned for the space.
