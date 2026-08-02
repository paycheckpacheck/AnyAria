# -*- coding: utf-8 -*-
"""Turn a board's exported deck into something that can actually be run.

A schematic is not a testbench, and the difference is the last gap between "the
SPICE deck loads" and "the simulation works". KiCad exports a board as a flat
list of parts with real values and *nothing driving them*: no sources, no
analysis directive, no loads. ngspice loads it happily and then has nothing to
do, which is why the verify chain reports it as well formed and unsimulatable
in the same breath.

What is missing is small and entirely external to the schematic. Rails have to
be driven, inputs have to be excited, outputs have to be loaded, and something
has to say what analysis to run. None of that belongs on the sheet - a board is
not built with its bench soldered to it - so it is supplied here and composed
onto the exported deck.

    >>> deck = Path("spice_check.cir").read_text()
    >>> result = run_bench(
    ...     deck,
    ...     supplies=[Supply("/VMOTOR", 12.0)],
    ...     analysis=".op",
    ...     vectors=["/VRAIL_SENSE"],
    ... )
    >>> result.vectors["/vrail_sense"][0]           # doctest: +SKIP
    1.0909090809906448

That number is the board's own rail-sense divider - 100k over 10k from 12V -
and it comes out of the generated project rather than out of a model of it.

**The deck is composed onto, never rewritten.** Everything added is appended
before ``.end``, so what ran is the exported netlist plus a bench you can read,
and a surprising result can be blamed on one or the other.
"""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from .ngspice_runner import SimulationResult, run_deck

logger = logging.getLogger(__name__)

__all__ = [
    "Supply",
    "Stimulus",
    "Load",
    "bench",
    "run_bench",
    "vector_name",
    "find_vector",
]


@dataclass(frozen=True)
class Supply:
    """A DC rail driven from outside the board.

    Attributes:
        node: The net, as KiCad spells it - ``/VMOTOR``, ``VBUS``.
        volts: The voltage.
        series_resistance: Source impedance in ohms. Zero is an ideal supply,
            which is usually wrong for anything asking about droop and is fine
            for a bias point.
    """

    node: str
    volts: float
    series_resistance: float = 0.0


@dataclass(frozen=True)
class Stimulus:
    """A time-varying source, written the way SPICE wants it.

    The source expression is passed through rather than modelled, because
    ngspice's own syntax is the least surprising thing to read here and every
    wrapper over it loses a case.

    Attributes:
        node: The net to drive.
        expression: A SPICE source expression, such as
            ``"PULSE(0 3.3 0 1n 1n 5u 10u)"`` or ``"SIN(0 1 1k)"``.
    """

    node: str
    expression: str


@dataclass(frozen=True)
class Load:
    """A resistive load hung on a net.

    Attributes:
        node: The net to load.
        ohms: The resistance.
    """

    node: str
    ohms: float


def vector_name(node: str) -> str:
    """Spell a net the way ngspice returns it.

    ngspice lower-cases node names, so a caller who writes the net as KiCad
    spells it gets nothing back and reads that as a circuit fault.

    Args:
        node: The net name.

    Returns:
        The vector name.
    """
    match = re.fullmatch(r"[VvIi]\((.*)\)", node)
    return (match.group(1) if match else node).lower()


def find_vector(vectors: Dict[str, List[float]], node: str) -> Optional[List[float]]:
    """Look a net up in a result, tolerating the spellings in play.

    KiCad prefixes hierarchical nets with a slash and ngspice lower-cases
    everything, so the name written in the Python is rarely the name in the
    result.

    Args:
        vectors: The result's vectors.
        node: The net name as written anywhere.

    Returns:
        The values, or None when no spelling of the name is present.
    """
    wanted = vector_name(node)
    for candidate in (wanted, f"/{wanted}", wanted.lstrip("/")):
        if candidate in vectors:
            return vectors[candidate]
    return None


def bench(
    deck: str,
    supplies: Sequence[Supply] = (),
    stimuli: Sequence[Stimulus] = (),
    loads: Sequence[Load] = (),
    analysis: str = ".op",
) -> str:
    """Compose a runnable deck from an exported one and a bench.

    Args:
        deck: The exported netlist, ending in ``.end``.
        supplies: DC rails to drive.
        stimuli: Time-varying sources.
        loads: Resistive loads.
        analysis: The analysis directive, such as ``".op"`` or
            ``".tran 1u 1m"``. Without one ngspice loads the deck and does
            nothing, which is the state this module exists to leave behind.

    Returns:
        The composed deck.

    Raises:
        ValueError: If the deck has no ``.end``, which means it is not a deck,
            or if two sources would drive the same net - which ngspice reports
            as a voltage-source loop several lines away from the cause.
    """
    if ".end" not in deck:
        raise ValueError("the deck has no .end line, so it is not a netlist")

    driven = [supply.node for supply in supplies] + [item.node for item in stimuli]
    duplicates = {name for name in driven if driven.count(name) > 1}
    if duplicates:
        raise ValueError(
            f"more than one source drives {', '.join(sorted(duplicates))}. "
            f"ngspice reports that as a voltage-source loop, and not near the "
            f"line that caused it."
        )

    lines: List[str] = ["* --- bench, added by circuit_synth.simulation.bench ---"]
    for index, supply in enumerate(supplies, start=1):
        if supply.series_resistance > 0:
            rail = f"bench_src_{index}"
            lines.append(f"Vbench{index} {rail} 0 DC {supply.volts:g}")
            lines.append(
                f"Rbench{index} {rail} {supply.node} {supply.series_resistance:g}"
            )
        else:
            lines.append(f"Vbench{index} {supply.node} 0 DC {supply.volts:g}")

    for index, item in enumerate(stimuli, start=1):
        lines.append(f"Vstim{index} {item.node} 0 {item.expression}")

    for index, item in enumerate(loads, start=1):
        lines.append(f"Rload{index} {item.node} 0 {item.ohms:g}")

    lines.append(analysis)

    body, _, tail = deck.rpartition(".end")
    return body + "\n".join(lines) + "\n.end" + tail


def run_bench(
    deck: str,
    supplies: Sequence[Supply] = (),
    stimuli: Sequence[Stimulus] = (),
    loads: Sequence[Load] = (),
    analysis: str = ".op",
    vectors: Sequence[str] = ("*",),
    timeout: float = 300.0,
) -> SimulationResult:
    """Compose a bench onto a deck and run it.

    Args:
        deck: The exported netlist.
        supplies: DC rails to drive.
        stimuli: Time-varying sources.
        loads: Resistive loads.
        analysis: The analysis directive.
        vectors: Vectors to read back. The default asks for everything, which
            is usually right for a board whose node names came from KiCad.
        timeout: Seconds before the run is abandoned.

    Returns:
        The result.
    """
    composed = bench(deck, supplies, stimuli, loads, analysis)
    logger.debug("running a bench of %d line(s)", composed.count("\n"))
    return run_deck(composed, commands=("run",), vectors=vectors, timeout=timeout)
