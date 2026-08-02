# -*- coding: utf-8 -*-
"""Header, before its agent has built it.

The ports are declared and the body is empty. That is enough for the root
builder to generate a sheet symbol with the right sheet pins, so the block
diagram is complete and reviewable before a single part has been chosen.
"""

from circuit_synth import Input, Output, circuit


@circuit(name="Header")
def header(RAW_OUT: Output, VMON: Input, DRIVE_A: Output, DRIVE_B: Output):
    """Where the board meets the outside world: 5V in, monitor and drives out."""
