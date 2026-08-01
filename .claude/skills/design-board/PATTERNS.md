# Block shapes that keep coming back

Prompts for step 3 of decomposition - the blocks an anchor part implies but
does not draw. Not a lookup table: a board that matches nothing here is normal,
and matching one of these is not permission to skip reading the datasheet.

Each entry says what the block is, what is easy to leave out, and what has to
be calculated rather than copied.

## Any board at all

- **Input protection.** Reverse polarity, over-voltage, a fuse. Wherever the
  outside world can reach the board.
- **A rail per voltage the anchor names**, each with its own decoupling. Read
  the pin table, not the block diagram: parts often have three supply domains
  where the diagram draws one.
- **A way in.** Programming, debug, or a bootloader strap. A board that cannot
  be programmed is discovered after assembly.
- **Test points** on anything you would need to see to know why it does not
  work.

## Switching supply (buck, boost, inverting)

Blocks: input bulk and filtering, the converter, output filtering, feedback,
and often an enable or sequencing network.

Easy to leave out: the bootstrap capacitor, the soft-start capacitor, a
minimum load, the feedback divider's top-end capacitor for loop stability.

Calculate, do not copy: the inductor from ripple current, the output capacitor
from ripple voltage *and* from the load-step the design has to survive, the
feedback divider from the reference voltage, the compensation from the crossover
frequency you have chosen. Copying these from a reference design silently
adopts its input voltage, its load and its switching frequency.

## Linear regulator

Blocks: usually just the regulator, but it belongs with what it feeds.

Easy to leave out: the specific input and output capacitor types. An LDO's
stability depends on output capacitor ESR, and a ceramic where the datasheet
assumed tantalum oscillates.

Calculate: the dropout at the actual load and temperature, and the dissipation
- `(Vin - Vout) x I` becomes heat with nowhere to go on a small part.

## Microcontroller or FPGA

Blocks: the part, its supplies, its clock, its configuration memory, its debug
interface, and each peripheral interface.

Easy to leave out: series termination on fast lines, a strap resistor that
decides boot mode, the pull-up a configuration memory needs while the rails come
up, a series resistor on a crystal.

Copy verbatim: everything in the vendor's minimal or reference design. This is
exactly what `reference-circuit` is for.

## RF chain

Blocks: antenna interface, matching, filtering, amplification, mixing, the
local oscillator, and the baseband interface. Usually one block per stage,
because each stage has its own supply and its own matching.

Easy to leave out: matching at every impedance discontinuity, DC blocking
between stages at different bias points, bias tees for active parts, shielding.

**Cannot be verified from a schematic.** Impedance, matching and stackup are the
design, and a netlist shows none of them. Matching networks are placeholders
until there is an EM simulation and a chosen stackup, and the report says so.

## Motor drive

Blocks: gate drive, power stage, current sense, and position or back-EMF
sensing - one set per phase, nested inside the phase block.

Easy to leave out: the bootstrap refresh a high-side driver needs, dead time,
a gate pull-down that holds the part off while the rails come up, Kelvin
connections on the shunt.

Calculate: gate resistors from gate charge and the switching time you want, the
shunt from the full-scale current and the amplifier's input range, the bootstrap
capacitor from gate charge and the longest on-time.

## Analogue front end

Blocks: input protection, gain, anti-alias filtering, the reference, the
converter.

Easy to leave out: the reference's own decoupling, a filter before the
converter rather than only after the amplifier, input bias current paths.

Calculate: the full-scale range against the converter's input, the filter corner
against the sample rate, the noise budget - which decides the resistor values,
not the other way round.

## Connectivity

Blocks: the connector, its protection, its termination, and any PHY or
transceiver with its own supply and clock.

Easy to leave out: ESD protection on anything a person can touch, CC pulldowns
on a USB-C device, magnetics on Ethernet, a termination resistor on a bus that
needs one at exactly one end.
