# -*- coding: utf-8 -*-
"""Build this board the way design-board does: block diagram first, then agents.

This plays the whole sequence, with a thread standing in for each block agent so
that the parallelism is real rather than described:

    1. Every block is a stub - ports declared, body empty. The root builder is
       run over those stubs, which produces the KiCad project as a block
       diagram: a sheet symbol per block with its sheet pins, an empty page
       behind each, and the root laid out. That is the approval gate.

    2. One agent per block, all at once.

    3. Each agent writes its own block.py, generates, looks at the sheet it got,
       decides the placement, writes its layout, and applies it. It runs the
       KiCad generation and the layout pass itself; nothing is deferred to an
       integrator.

    4. Once every agent is done: SPICE hygiene and the full verification.

Run it:

    uv run python examples/block_first_board/run.py

The design directory is copied into examples/build so that the stub-then-fill
sequence can be played without editing the files in the repository.
"""

import logging
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from circuit_synth.board import Board, build_board
from circuit_synth.kicad.layout import describe_sheet
from circuit_synth.kicad.layout.extract import sheet_nets, sheet_ports
from circuit_synth.kicad.session import finish_editing
from circuit_synth.kicad.spice_hygiene import make_spice_clean
from circuit_synth.verify import verify_project

logging.disable(logging.CRITICAL)

SOURCE = Path(__file__).resolve().parent
BUILD = Path(sys.argv[1] if len(sys.argv) > 1 else "examples/build/block_first_board")
DESIGN = BUILD / "design"
PROJECT = BUILD / "BlockFirstDemo"

BLOCKS = ("Header", "Supply", "Indicator")


def _write_atomically(path: Path, text: str) -> None:
    """Replace a file in one step.

    Another agent's build may be importing this file at the moment it is
    written. A partial write would be a syntax error in somebody else's
    subprocess, so the new content goes to a temporary file that is then moved
    over the old one, which is atomic within a directory.

    Args:
        path: The file to replace.
        text: Its new content.
    """
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def stage_the_design() -> Board:
    """Copy the design into the build directory with every block still a stub.

    Returns:
        The board, ready for its first build.
    """
    if BUILD.exists():
        shutil.rmtree(BUILD)
    (DESIGN / "blocks").mkdir(parents=True)

    shutil.copy(SOURCE / "board.py", DESIGN / "board.py")
    shutil.copy(SOURCE / "layout.py", DESIGN / "layout.py")
    for block in BLOCKS:
        (DESIGN / "blocks" / block).mkdir()
        shutil.copy(
            SOURCE / "blocks" / block / "stub.py",
            DESIGN / "blocks" / block / "block.py",
        )
    return Board(DESIGN, PROJECT)


def build_one_block(board: Board, block: str) -> str:
    """Everything one block agent does after its research is finished.

    Args:
        board: The shared board.
        block: Which block this agent owns.

    Returns:
        A line describing what it did.
    """
    started = time.monotonic()

    # 1. Write the circuit. Until this moment the block was the empty stub the
    #    block diagram was generated from.
    _write_atomically(
        board.block_dir(block) / "block.py",
        (SOURCE / "blocks" / block / "block.py").read_text(encoding="utf-8"),
    )

    # 2. Generate. capture_refs records the reference designators this block
    #    came out with, so the placement written next can be mapped forward when
    #    a later block renumbers the board.
    build_board(board, note=block, capture_refs=[block], render=False, validate=False)

    # 3. Look at what landed, and decide where it goes. This is the part only
    #    the block's own agent can do.
    sheet = describe_sheet(
        board.sheet(block),
        sheet_nets(board.circuit_json)[block],
        sheet_ports(board.circuit_json)[block],
    )
    placement = _import_placement(block)(sheet)
    placement.write_json(board.block_dir(block) / "layout.json")

    # 4. Apply it, and render so the agent can look at its own sheet.
    result = build_board(board, note=block, render=True)

    took = time.monotonic() - started
    waited = f", waited {result.waited:.1f}s" if result.waited > 1.0 else ""
    return (
        f"{block}: {len(sheet.components)} part(s), "
        f"{len(result.problems)} layout problem(s), {took:.0f}s{waited}"
    )


def _import_placement(block: str):
    """Load one block's placement decision.

    Args:
        block: The block's name.

    Returns:
        Its ``place(sheet)`` function.
    """
    import importlib.util

    path = SOURCE / "blocks" / block / "place.py"
    spec = importlib.util.spec_from_file_location(f"_place_{block}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.place


def main() -> int:
    """Play the whole sequence.

    Returns:
        A process exit code.
    """
    board = stage_the_design()

    print("1. The block diagram, before any block has been built")
    diagram = build_board(board, note="block diagram")
    print(diagram.summary())
    print(f"   root render: {diagram.images[0]}")
    print()

    print("2. Three agents, in parallel, each filling in its own block")
    with ThreadPoolExecutor(max_workers=len(BLOCKS)) as pool:
        for line in pool.map(lambda block: build_one_block(board, block), BLOCKS):
            print("   " + line)
    print()

    print("3. The finished board")
    print(make_spice_clean(PROJECT).summary())
    report = verify_project(board.root_schematic, board.circuit_json)
    print(report.summary())
    finish_editing(PROJECT)
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
