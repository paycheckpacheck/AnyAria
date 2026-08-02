# -*- coding: utf-8 -*-
"""Header: the connector everything on the board is reached through.

Written by the block's own agent, replacing the stub the block diagram was
generated from. The ports did not change, so the root sheet's block diagram is
still correct - only the page behind the sheet symbol has been filled in.
"""

from circuit_synth import Component, Input, Net, Output, circuit


@circuit(name="Header")
def header(RAW_OUT: Output, VMON: Input, DRIVE_A: Output, DRIVE_B: Output):
    """Where the board meets the outside world: 5V in, monitor and drives out.

    Five pins in the order a ribbon lands in: supply, then its return, then the
    three signals. Ground sits next to the supply rather than at the end of the
    row so that the pair is adjacent in the cable, which keeps the loop small.
    """
    connector = Component(
        symbol="Connector_Generic:Conn_01x05",
        ref="J",
        value="Conn_01x05",
        footprint="Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical",
    )

    gnd = Net("GND")

    connector[1] += RAW_OUT
    connector[2] += gnd
    connector[3] += VMON
    connector[4] += DRIVE_A
    connector[5] += DRIVE_B
