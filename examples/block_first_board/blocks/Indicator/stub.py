# -*- coding: utf-8 -*-
"""Indicator, before its agent has built it.

One port, because one indicator is one drive line. The block is instantiated
twice by the root builder rather than being written once with two of everything
inside it.
"""

from circuit_synth import Input, circuit


@circuit(name="Indicator")
def indicator(DRIVE: Input):
    """An LED off the 3.3V rail, lit by pulling DRIVE low."""
