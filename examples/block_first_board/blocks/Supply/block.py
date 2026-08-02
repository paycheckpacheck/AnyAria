# -*- coding: utf-8 -*-
"""Supply: the 3.3V rail, and the tap that measures it.

Written by the block's own agent, replacing the stub the block diagram was
generated from.
"""

from circuit_synth import Component, Input, Net, Output, circuit

# The AMS1117 datasheet asks for 10uF at the input and 22uF at the output; both
# are the tantalum figures, and ceramics of the same marking are more than the
# regulator needs to stay stable.
INPUT_CAP = "10uF"
OUTPUT_CAP = "22uF"

# Two equal resistors halve the rail, so a 3.3V rail reads 1.65V at the monitor
# and a reading is still on scale if the rail runs high.
DIVIDER = "10k"


@circuit(name="Supply")
def supply(RAW_IN: Input, VMON: Output):
    """The 3.3V rail, made from the raw input, with a tap that measures it.

    The monitor divider is here rather than in the block that reads it, because
    what it measures is this block's own output.
    """
    regulator = Component(
        symbol="Regulator_Linear:AMS1117-3.3",
        ref="U",
        value="AMS1117-3.3",
        footprint="Package_TO_SOT_SMD:SOT-223-3_TabPin2",
    )
    input_cap = Component(
        symbol="Device:C",
        ref="C",
        value=INPUT_CAP,
        footprint="Capacitor_SMD:C_0805_2012Metric",
    )
    output_cap = Component(
        symbol="Device:C",
        ref="C",
        value=OUTPUT_CAP,
        footprint="Capacitor_SMD:C_0805_2012Metric",
    )
    divider_top = Component(
        symbol="Device:R",
        ref="R",
        value=DIVIDER,
        footprint="Resistor_SMD:R_0603_1608Metric",
    )
    divider_bottom = Component(
        symbol="Device:R",
        ref="R",
        value=DIVIDER,
        footprint="Resistor_SMD:R_0603_1608Metric",
    )

    gnd = Net("GND")
    v3v3 = Net("+3V3")

    regulator[3] += RAW_IN
    regulator[2] += v3v3
    regulator[1] += gnd

    input_cap[1] += RAW_IN
    input_cap[2] += gnd
    output_cap[1] += v3v3
    output_cap[2] += gnd

    divider_top[1] += v3v3
    divider_top[2] += VMON
    divider_bottom[1] += VMON
    divider_bottom[2] += gnd
