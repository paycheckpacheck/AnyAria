# -*- coding: utf-8 -*-
"""Building one board from many agents working on it at once.

A board is split into blocks and an agent is given each block. This package is
what lets those agents share a single KiCad project instead of each producing a
throwaway one that somebody has to compose afterwards.

The order it supports:

1. Every block starts as a stub - its ports declared, its body empty. The root
   builder is run over those stubs, which produces the real project as a block
   diagram: a sheet symbol per block with its sheet pins, and an empty page
   behind each. That is what the user approves.
2. The agents fan out, one per block.
3. Each agent, when its research is done, writes its own ``block.py`` and
   ``layout.py`` and calls :func:`build_board`, which regenerates the project
   and re-applies every layout on disk. It runs the generation and the layout
   pass itself; nothing is left for an integrator.

See :mod:`circuit_synth.board.build` for why regenerating the whole project is
the right answer rather than a workaround, and what happens when two agents
finish at the same moment.
"""

from .build import Board, BuildFailed, BuildResult, build_board, load_block
from .lock import BuildBusy, LockHolder, build_lock, read_holder

__all__ = [
    "Board",
    "BuildFailed",
    "BuildResult",
    "build_board",
    "load_block",
    "BuildBusy",
    "LockHolder",
    "build_lock",
    "read_holder",
]
