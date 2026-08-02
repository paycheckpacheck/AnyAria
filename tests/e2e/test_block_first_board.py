"""A board built block by block, by agents running at the same time, comes out whole.

The block-first order puts the KiCad project before the agents: it is generated
from blocks that declare their ports and contain nothing else, so the user
approves a real block diagram, and each agent then writes its own page into that
same project. Nothing about that is safe by construction, because circuit-synth
writes a project from one root Circuit and every agent therefore rewrites all of
it. What makes it work is that a build is a pure function of the design
directory and that builds are serialised.

So this runs the example with three real threads standing in for three agents,
one of its blocks instantiated twice, and then asks the finished project the
same questions as any other board: every sheet opens, the drawing matches the
circuit, nothing is drawn over a part, ERC is clean.

The failures it guards against are the ones that leave no trace: an agent's
sheet silently overwritten by the agent that finished after it, a placement
applied to another block's parts after a renumber, and a sheet written by two
processes at once, which KiCad reports as an empty page rather than as an error.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "examples" / "block_first_board" / "run.py"

# The libraries the example's parts come from.
REQUIRED_LIBRARIES = (
    "Device.kicad_sym",
    "Regulator_Linear.kicad_sym",
    "Connector_Generic.kicad_sym",
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
    """Play the whole block-first sequence once.

    Args:
        tmp_path_factory: pytest's temporary directory factory.

    Returns:
        The project directory.
    """
    if SYMBOLS is None:
        pytest.skip("no KiCad symbol library")

    work = tmp_path_factory.mktemp("blockfirst")
    environment = dict(os.environ)
    environment["KICAD_SYMBOL_DIR"] = str(SYMBOLS)
    environment["CIRCUIT_SYNTH_CACHE_DIR"] = str(work / "symcache")

    finished = subprocess.run(
        [sys.executable, str(RUNNER), str(work / "board")],
        cwd=str(REPO),
        env=environment,
        capture_output=True,
        text=True,
        timeout=2400,
    )
    if finished.returncode != 0:
        pytest.fail(
            f"run.py failed:\n{finished.stdout[-4000:]}\n{finished.stderr[-2000:]}"
        )

    return work / "board" / "BlockFirstDemo"


@needs_kicad
def test_every_check_passes(board):
    """The whole chain, which is the definition of done."""
    from circuit_synth.verify import verify_project

    report = verify_project(
        board / "BlockFirstDemo.kicad_sch",
        board / "BlockFirstDemo.json",
        render=False,
    )
    assert report.passed, report.summary()


@needs_kicad
def test_every_block_ended_up_in_the_one_project(board):
    """An agent whose sheet was overwritten by a later one leaves no other trace."""
    circuit = json.loads((board / "BlockFirstDemo.json").read_text(encoding="utf-8"))
    names = [sub["name"] for sub in circuit["subcircuits"]]
    assert names == ["Header", "Supply", "Indicator", "Indicator"]

    # Every block has its parts, not just its sheet. A stub that was never
    # filled in, or a sheet regenerated from one, has none.
    parts = {sub["name"]: len(sub["components"]) for sub in circuit["subcircuits"]}
    assert parts == {"Header": 1, "Supply": 5, "Indicator": 2}


@needs_kicad
def test_the_repeated_block_was_laid_out_twice_from_one_layout(board):
    """One layout, written once, has to reach every instance of its block."""
    from circuit_synth.kicad.layout import describe_sheet

    first = describe_sheet(board / "Indicator.kicad_sch")
    second = describe_sheet(board / "Indicator2.kicad_sch")

    assert [c.position for c in first.components] == [
        c.position for c in second.components
    ]
    # Different parts in the same places, which is what carrying a layout onto
    # a repeated block means.
    assert {c.reference for c in first.components} != {
        c.reference for c in second.components
    }


@needs_kicad
def test_the_root_is_a_block_diagram_with_every_port_on_it(board):
    """A sheet pin left off a sheet symbol loses its connection silently."""
    root = (board / "BlockFirstDemo.kicad_sch").read_text(encoding="utf-8")
    for sheet, pins in {
        "Header": ("RAW_OUT", "VMON", "DRIVE_A", "DRIVE_B"),
        "Supply": ("RAW_IN", "VMON"),
        "Indicator": ("DRIVE",),
    }.items():
        assert f'"Sheetname" "{sheet}"' in root
        for pin in pins:
            assert f'(pin "{pin}"' in root


@needs_kicad
def test_no_wire_is_drawn_across_a_part(board):
    """A wire over a symbol reads as a connection and changes nothing electrically."""
    from circuit_synth.kicad.layout import wires_over_components

    for sheet in board.glob("*.kicad_sch"):
        assert wires_over_components(sheet) == [], sheet.name


@needs_kicad
def test_the_build_lock_was_given_back(board):
    """A lock left behind stalls every later build for its whole timeout."""
    from circuit_synth.board.lock import read_holder

    assert read_holder(board) is None
