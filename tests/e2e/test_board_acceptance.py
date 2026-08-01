"""What "finished" means for a generated board.

Every check here is automated because every one of them has been got wrong at
least once, silently. A sheet that will not open takes its parts out of the
netlist with no error anywhere. A wire drawn across a symbol changes nothing
electrically and so passes the netlist comparison. A deck that will not load
crashes the simulator with a message about a model name.

What none of them can tell you is that the circuit is right. Every check
compares the drawing against the Python, and a schematic that draws the wrong
circuit perfectly passes all of them. That is what the review skills are for,
and they run before any of this.

The project is generated once, in a subprocess, because the symbol cache is
per-process and the rest of the suite points at a small fixture library.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
EXAMPLE = REPO / "examples" / "three_phase_driver.py"
LAYOUT = REPO / "examples" / "layout_three_phase_driver.py"

# The libraries the example needs. Without them there is nothing to test.
REQUIRED_LIBRARIES = (
    "MCU_RaspberryPi.kicad_sym",
    "Driver_FET.kicad_sym",
    "Amplifier_Current.kicad_sym",
    "power.kicad_sym",
)

SYMBOL_DIRS = (
    Path(r"C:\Users\pache\AppData\Local\Programs\KiCad\10.0\share\kicad\symbols"),
    Path(r"C:\Program Files\KiCad\10.0\share\kicad\symbols"),
    Path("/usr/share/kicad/symbols"),
    Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols"),
)


def symbol_directory():
    """Find a KiCad symbol directory holding everything the example needs.

    Returns:
        The directory, or None when no complete one is installed.
    """
    for candidate in SYMBOL_DIRS:
        if candidate.exists() and all(
            (candidate / name).exists() for name in REQUIRED_LIBRARIES
        ):
            return candidate
    return None


SYMBOLS = symbol_directory()
needs_kicad = pytest.mark.skipif(
    SYMBOLS is None, reason="no complete KiCad symbol library installed"
)


@pytest.fixture(scope="module")
def board(tmp_path_factory):
    """Generate and lay out the example board once.

    Args:
        tmp_path_factory: pytest's temporary directory factory.

    Returns:
        The project directory.
    """
    if SYMBOLS is None:
        pytest.skip("no KiCad symbol library")

    work = tmp_path_factory.mktemp("board")
    environment = dict(os.environ)
    environment["KICAD_SYMBOL_DIR"] = str(SYMBOLS)
    environment["CIRCUIT_SYNTH_CACHE_DIR"] = str(work / "symcache")

    for script in (EXAMPLE, LAYOUT):
        finished = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(REPO),
            env=environment,
            capture_output=True,
            text=True,
            timeout=2400,
        )
        if finished.returncode != 0:
            pytest.fail(
                f"{script.name} failed:\n{finished.stdout[-2000:]}\n{finished.stderr[-2000:]}"
            )

    return REPO / "examples" / "build" / "three_phase_driver"


@needs_kicad
def test_every_check_passes(board):
    """The whole chain, which is the definition of done."""
    from circuit_synth.verify import verify_project

    report = verify_project(
        board / "ThreePhaseDriver.kicad_sch",
        board / "ThreePhaseDriver.json",
        render=False,
    )

    assert report.passed, report.summary()


@needs_kicad
def test_every_sheet_opens_in_kicad(board):
    """A sheet KiCad refuses takes every part on it out of the netlist."""
    from circuit_synth.kicad.sheet_check import unloadable_sheets

    assert unloadable_sheets(board) == []


@needs_kicad
def test_the_drawing_still_draws_the_circuit(board):
    """A placement decides where wires run, so it can change the circuit."""
    from circuit_synth.kicad.layout.validate import validate_layout

    problems = validate_layout(
        board / "ThreePhaseDriver.kicad_sch", board / "ThreePhaseDriver.json"
    )

    assert problems == [], "; ".join(str(problem) for problem in problems[:5])


@needs_kicad
def test_nothing_is_drawn_across_a_part(board):
    """A wire over a symbol reads as a connection and changes no netlist."""
    from circuit_synth.kicad.layout.routing import (
        notes_over_components,
        wires_over_components,
    )

    for sheet in sorted(board.glob("*.kicad_sch")):
        assert wires_over_components(sheet) == [], sheet.name
        assert notes_over_components(sheet) == [], sheet.name


@needs_kicad
def test_erc_reports_no_errors(board):
    """An unmarked floating pin and a forgotten pin look identical to ERC."""
    from circuit_synth.kicad.layout.validate import erc_violations

    assert erc_violations(board / "ThreePhaseDriver.kicad_sch") == []


@needs_kicad
def test_the_spice_deck_loads(board):
    """The reported crash: one bad line stops the whole deck being read."""
    from circuit_synth.kicad.spice_hygiene import deck_loads

    loaded, detail = deck_loads(board / "ThreePhaseDriver.kicad_sch")

    assert loaded, detail


@needs_kicad
def test_every_circuit_has_a_group_box_with_a_reason(board):
    """A sheet that does not say why its values were chosen cannot be reviewed."""
    for sheet in sorted(board.glob("*.kicad_sch")):
        if sheet.stem == "ThreePhaseDriver":
            continue  # the root is a block diagram, not a circuit
        text = sheet.read_text(encoding="utf-8")
        assert "(rectangle" in text, f"{sheet.name} has no group box"


@needs_kicad
def test_repeated_blocks_hold_distinct_parts(board):
    """Three instances of a block are three sets of parts, not one drawn thrice."""
    data = json.loads((board / "ThreePhaseDriver.json").read_text(encoding="utf-8"))

    seen = set()
    def walk(node):
        for reference in (node.get("components") or {}):
            assert reference not in seen, f"{reference} appears twice"
            seen.add(reference)
        for child in node.get("subcircuits") or []:
            walk(child)

    walk(data)
    assert len(seen) > 50
