# -*- coding: utf-8 -*-
"""Supply, before its agent has built it.

The ports are declared and the body is empty. +3V3 is a rail, so it is a power
symbol rather than a port and does not appear here.
"""

from circuit_synth import Input, Output, circuit


@circuit(name="Supply")
def supply(RAW_IN: Input, VMON: Output):
    """The 3.3V rail, made from the raw input, with a tap that measures it."""
