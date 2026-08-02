# -*- coding: utf-8 -*-
"""The root builder: how the blocks are wired to each other, and nothing else.

This file is written once, at the architecture stage, before any block has been
built. It says what the blocks are, how many of each there are and what runs
between them - which is exactly the block diagram the user approves.

It imports each block from its own ``block.py``, so it is equally happy with a
block that is still an empty stub and one an agent has filled in. That is what
makes it safe to run it again every time any block changes: the project it
generates is whatever every block currently on disk adds up to.

``circuit_synth.board.build`` runs this in a subprocess and calls ``board()``.
"""

from pathlib import Path

from circuit_synth import Net, circuit
from circuit_synth.board import load_block

BLOCKS = Path(__file__).resolve().parent / "blocks"

header = load_block(BLOCKS, "Header").header
supply = load_block(BLOCKS, "Supply").supply
indicator = load_block(BLOCKS, "Indicator").indicator


@circuit(name="BlockFirstDemo")
def board():
    """A 5V inlet, a 3.3V rail and two indicators.

    The board exists to demonstrate the block-first build order rather than to
    do anything: it is small enough that every sheet can be read at a glance,
    and Indicator is instantiated twice so that carrying one layout onto a
    repeated block is exercised.
    """
    vraw = Net("VRAW")
    vmon = Net("VMON")
    led_a = Net("LED_A")
    led_b = Net("LED_B")

    # Left to right, which is the order the root sheet reads in.
    header(vraw, vmon, led_a, led_b)
    supply(vraw, vmon)
    indicator(led_a)
    indicator(led_b)
