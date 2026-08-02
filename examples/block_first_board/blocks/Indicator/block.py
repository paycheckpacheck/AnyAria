# -*- coding: utf-8 -*-
"""Indicator: one LED, lit by pulling its drive line low.

Written by the block's own agent, replacing the stub the block diagram was
generated from. The root builder instantiates this twice, so whatever layout
this block's agent decides is carried onto both instances.
"""

from circuit_synth import Component, Input, Net, circuit

# 1k8 off 3.3V gives about 1mA through a red LED at 1.9V forward, which is
# visible indoors and small enough that two of them cost the rail nothing.
SERIES = "1k8"


@circuit(name="Indicator")
def indicator(DRIVE: Input):
    """An LED off the 3.3V rail, lit by pulling DRIVE low.

    The series resistor is on the rail side of the LED so that the drive line
    sees the cathode. A drive line left floating leaves the LED dark, which is
    the safe state for a pin that has not been configured yet.
    """
    series = Component(
        symbol="Device:R",
        ref="R",
        value=SERIES,
        footprint="Resistor_SMD:R_0603_1608Metric",
    )
    led = Component(
        symbol="Device:LED",
        ref="D",
        value="RED",
        footprint="LED_SMD:LED_0603_1608Metric",
    )

    v3v3 = Net("+3V3")
    anode = Net("LED_ANODE")

    series[1] += v3v3
    series[2] += anode
    led[2] += anode
    led[1] += DRIVE
