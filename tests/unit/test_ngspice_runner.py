"""A simulator that is present but unreachable is worse than an absent one.

KiCad ships ngspice as a library and no program, so ``shutil.which("ngspice")``
finds nothing and every check that wanted a real simulation skipped silently.
The skip looked exactly like a pass. These tests are what stops that returning:
if ngspice can be reached on this machine, they run a real deck through it and
check the answer against arithmetic anyone can do by hand.
"""

import pytest

from circuit_synth.simulation.ngspice_runner import (
    available,
    find_ngspice,
    run_deck,
)

needs_ngspice = pytest.mark.skipif(
    not available(), reason="no ngspice this interpreter can reach"
)


def test_an_absent_simulator_is_reported_rather_than_assumed_away():
    """When nothing can be found, say so instead of returning an empty pass."""
    result = run_deck("x\n.end\n", install=None) if not available() else None

    if result is not None:
        assert not result.ok
        assert "no ngspice" in result.error


@needs_ngspice
def test_the_library_is_paired_with_an_interpreter_that_can_load_it():
    """The pairing is the whole point.

    On Windows on ARM the venv's python.exe has an ARM64 PE header and still
    runs as emulated x86-64, so matching the interpreter by its own header - or
    by platform.machine() - finds a pairing that then fails to load.
    """
    install = find_ngspice()

    assert install is not None
    assert install.library.exists()
    if install.interpreter is not None:
        assert install.interpreter.exists()


@needs_ngspice
def test_a_resistive_divider_gives_the_answer_you_can_do_in_your_head():
    """10V across 1k and 3k puts 7.5V on the junction.

    Anything else means the deck was not the deck, or the vectors came back
    from somewhere else.
    """
    deck = (
        "divider\n"
        "V1 in 0 DC 10\n"
        "R1 in out 1k\n"
        "R2 out 0 3k\n"
        ".op\n"
        ".end\n"
    )

    result = run_deck(deck, vectors=["out", "in"])

    assert result.ok, result.error or result.log
    assert result.vectors["in"][0] == pytest.approx(10.0)
    assert result.vectors["out"][0] == pytest.approx(7.5)


@needs_ngspice
def test_a_transient_run_returns_a_waveform_not_a_point():
    """An RC charging to 63.2% in one time constant, read off the sweep."""
    deck = (
        "rc step\n"
        "V1 in 0 PWL(0 0 1n 1)\n"
        "R1 in out 1k\n"
        "C1 out 0 1u\n"
        ".tran 10u 5m\n"
        ".end\n"
    )

    result = run_deck(deck, vectors=["out", "time"])

    assert result.ok, result.error or result.log
    times = result.vectors["time"]
    values = result.vectors["out"]
    assert len(values) > 50

    # One time constant is 1ms. Find the sample nearest it.
    index = min(range(len(times)), key=lambda i: abs(times[i] - 1e-3))
    assert values[index] == pytest.approx(0.632, abs=0.01)


@needs_ngspice
def test_a_deck_ngspice_cannot_read_comes_back_as_a_failure():
    """The failure this whole chain exists to catch.

    A value an engineer writes - 220uF/50V - is not a value ngspice reads, and
    a fuse called F1 is a current-controlled source as far as SPICE is
    concerned. Both produce a deck that loads nothing, and ngspice does not
    always signal that through its exit status, so the log is what is read.
    """
    deck = (
        "broken\n"
        "V1 in 0 DC 10\n"
        "R1 in out 220uF/50V\n"
        ".op\n"
        ".end\n"
    )

    result = run_deck(deck, vectors=["out"])

    assert not result.ok
    assert result.error


@needs_ngspice
def test_the_title_line_is_a_title_and_not_a_component():
    """ngspice discards the first line, and a deck written without one loses a
    part with no error at all.

    Worth a test because it is the kind of thing that produces a plausible
    wrong answer rather than a failure.
    """
    with_title = run_deck(
        "title\nV1 in 0 DC 5\nR1 in 0 1k\n.op\n.end\n", vectors=["in"]
    )
    without_title = run_deck(
        "V1 in 0 DC 5\nR1 in 0 1k\n.op\n.end\n", vectors=["in"]
    )

    assert with_title.ok
    assert with_title.vectors["in"][0] == pytest.approx(5.0)

    # The source became the title, so the circuit is a lone resistor to ground.
    # Note what comes back: ok, no error, no warning - and 0V where the deck's
    # author expected 5V. Nothing downstream can tell this from a real result,
    # which is why the title line is worth a test of its own.
    assert without_title.ok
    assert not without_title.error
    assert without_title.vectors["in"][0] == pytest.approx(0.0)
