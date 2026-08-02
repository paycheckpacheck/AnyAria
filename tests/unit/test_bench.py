"""A schematic is not a testbench, and that was the last gap.

KiCad exports a board as parts with real values and nothing driving them.
ngspice loads it and has nothing to do, so "the deck loads" was as far as the
verify chain could ever get. What was missing is small, external to the
schematic, and supplied here.

The board test is the one that matters: it drives the real generated project
and reads a divider whose answer can be done by hand.
"""

import pytest

from circuit_synth.simulation.bench import (
    Load,
    Stimulus,
    Supply,
    bench,
    find_vector,
    run_bench,
    vector_name,
)
from circuit_synth.simulation.ngspice_runner import available

needs_ngspice = pytest.mark.skipif(
    not available(), reason="no ngspice this interpreter can reach"
)

DIVIDER = ".title hand check\nR1 in out 100k\nR2 out 0 10k\n.end\n"


def test_the_bench_is_composed_on_rather_than_rewritten():
    """What ran must be the exported netlist plus a bench you can read.

    Rewriting the deck would mean a surprising result could not be blamed on
    one or the other.
    """
    composed = bench(DIVIDER, supplies=[Supply("in", 12.0)], analysis=".op")

    assert "R1 in out 100k" in composed
    assert "Vbench1 in 0 DC 12" in composed
    assert composed.rstrip().endswith(".end")
    assert composed.count(".end") == 1


def test_a_deck_without_an_end_line_is_refused():
    """Appending to something that is not a netlist produces one that is not."""
    with pytest.raises(ValueError, match="no .end line"):
        bench("R1 a b 1k\n", supplies=[Supply("a", 1.0)])


def test_two_sources_on_one_net_are_caught_here():
    """ngspice calls it a voltage-source loop, several lines from the cause."""
    with pytest.raises(ValueError, match="more than one source drives"):
        bench(
            DIVIDER,
            supplies=[Supply("in", 12.0)],
            stimuli=[Stimulus("in", "SIN(0 1 1k)")],
        )


def test_a_supply_can_have_source_impedance():
    """An ideal rail is fine for a bias point and wrong for droop."""
    composed = bench(DIVIDER, supplies=[Supply("in", 5.0, series_resistance=0.5)])

    assert "Vbench1 bench_src_1 0 DC 5" in composed
    assert "Rbench1 bench_src_1 in 0.5" in composed


def test_net_names_are_spelled_the_way_ngspice_returns_them():
    """KiCad writes /VMOTOR and ngspice returns /vmotor.

    A caller who uses the schematic's spelling otherwise gets nothing back and
    reads that as a circuit fault.
    """
    assert vector_name("/VRAIL_SENSE") == "/vrail_sense"
    assert vector_name("V(/VMOTOR)") == "/vmotor"
    assert find_vector({"/vmotor": [12.0]}, "/VMOTOR") == [12.0]
    assert find_vector({"out": [1.0]}, "OUT") == [1.0]
    assert find_vector({"out": [1.0]}, "missing") is None


@needs_ngspice
def test_a_bench_makes_an_inert_deck_do_something():
    """The same deck, before and after.

    Without a bench there is no source and no analysis, so there is nothing to
    read. With one, the divider divides.
    """
    result = run_bench(
        DIVIDER, supplies=[Supply("in", 12.0)], analysis=".op", vectors=["out"]
    )

    assert result.ok, result.error
    assert result.vectors["out"][0] == pytest.approx(12.0 * 10.0 / 110.0)


@needs_ngspice
def test_a_transient_bench_drives_a_stimulus():
    """A step through an RC, checked at one time constant."""
    deck = ".title rc\nR1 in out 1k\nC1 out 0 1u\n.end\n"

    result = run_bench(
        deck,
        stimuli=[Stimulus("in", "PWL(0 0 1n 1)")],
        analysis=".tran 10u 5m",
        vectors=["time", "out"],
    )

    assert result.ok, result.error
    times, values = result.vectors["time"], result.vectors["out"]
    index = min(range(len(times)), key=lambda i: abs(times[i] - 1e-3))
    assert values[index] == pytest.approx(0.632, abs=0.01)


@needs_ngspice
def test_a_load_pulls_a_rail_down_through_its_source_impedance():
    """The reason source impedance is worth having.

    A 1 ohm source feeding a 9 ohm load sits at 90% of its open-circuit value,
    and an ideal rail would report no droop at all.
    """
    deck = ".title rail\nR1 rail 0 1meg\n.end\n"

    result = run_bench(
        deck,
        supplies=[Supply("rail", 10.0, series_resistance=1.0)],
        loads=[Load("rail", 9.0)],
        analysis=".op",
        vectors=["rail"],
    )

    assert result.ok, result.error
    assert result.vectors["rail"][0] == pytest.approx(9.0, rel=1e-3)
