# -*- coding: utf-8 -*-
"""Building one KiCad project block by block, from parallel agents.

A board is decomposed into blocks and one agent is given each block. The
project exists from the start: before any agent is dispatched, the root builder
is run over blocks that declare their ports and contain nothing else, which
generates the real KiCad project as a block diagram - a sheet symbol per block,
sheet pins on it, and an empty page behind it. That is what the user approves.

Each agent then fills in its own block and writes it into that same project.

The obstacle is that circuit-synth writes a project from one root ``Circuit``
and walks the whole hierarchy doing it. There is no call that adds one sheet to
an existing project. What makes that acceptable is that the root builder reads
every block from a separate ``block.py`` on disk, so regenerating from the root
is not "throw away the other agents' work" - it is "pick up whatever every
agent has written so far". A block nobody has filled in yet regenerates as the
empty stub it still is.

Layouts are treated the same way. Each block's placement lives in its own
``layout.py``, and a build re-applies every layout it can find rather than only
the one the caller just wrote. So a build is a pure function of the design
directory:

    build = generate(every block.py) + apply(every layout.py) + apply(root layout)

which is what makes it safe to run from several agents at once. They serialise
on :func:`circuit_synth.board.lock.build_lock` so no two of them write a sheet
at the same moment, and because each build reproduces the whole design from
disk, the last writer does not overwrite the others - it includes them.

The failure modes worth naming:

* **Two agents finish together.** The second waits out the first's build, then
  runs its own, which redoes the first agent's sheet as well. That costs the
  wall time of one extra generation and nothing else. If the wait exceeds the
  timeout the build raises :class:`~circuit_synth.board.lock.BuildBusy` rather
  than writing, because a project written without the lock is a torn file that
  KiCad reports as an empty page.
* **An agent's render goes stale.** Rendering happens inside the lock, so the
  images an agent looks at are of the project as it left it. Another agent
  building afterwards can change the page the images came from. The images are
  evidence about the block's own sheet, which only its own agent changes, so
  this matters for the root diagram and not for a block.
* **Reference designators move.** Adding a part to one block renumbers every
  block after it. A placement is therefore never applied by reference directly:
  each block records the circuit its placement was written against, and
  :func:`~circuit_synth.kicad.layout.extract.block_renames` maps that frame onto
  the current one positionally.
"""

import json
import logging
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Dict, List, Optional, Sequence, Tuple

from ..kicad.layout import apply_placement, render_sheets, validate_layout
from ..kicad.layout.extract import block_renames, instance_renames
from ..kicad.layout.spec import PlacementSpec
from ..kicad.layout.validate import LayoutProblem
from ..kicad.session import require_closed
from ._runner import RESULT_PREFIX
from .lock import build_lock

logger = logging.getLogger(__name__)

# What a block's directory is expected to hold. The names match BLOCK_CONTRACT.md.
BLOCK_MODULE = "block.py"
LAYOUT_MODULE = "layout.py"
LAYOUT_REFS = "layout_refs.json"

# The module-level name a layout file must bind its placement to.
SPEC_NAME = "SPEC"
ROOT_SPEC_NAME = "ROOT_SPEC"


class BuildFailed(RuntimeError):
    """The root builder did not produce a project."""


@dataclass(frozen=True)
class Board:
    """Where a block-first board keeps its files.

    Attributes:
        design_dir: Holds ``board.py`` (which must define ``board()`` returning
            the root circuit), the root's ``layout.py``, and ``blocks/``.
        project_dir: The KiCad project. Its directory name is the project's
            base name, so it should match the root circuit's name.
    """

    design_dir: Path
    project_dir: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "design_dir", Path(self.design_dir).resolve())
        object.__setattr__(self, "project_dir", Path(self.project_dir).resolve())

    @property
    def blocks_dir(self) -> Path:
        """The directory holding one subdirectory per block."""
        return self.design_dir / "blocks"

    @property
    def name(self) -> str:
        """The project's base name, which every generated file is named after."""
        return self.project_dir.name

    @property
    def root_schematic(self) -> Path:
        """The project's root ``.kicad_sch``."""
        return self.project_dir / f"{self.name}.kicad_sch"

    @property
    def circuit_json(self) -> Path:
        """The generated circuit JSON, which every check compares against."""
        return self.project_dir / f"{self.name}.json"

    def sheet(self, sheet_name: str) -> Path:
        """The ``.kicad_sch`` of one sheet.

        Args:
            sheet_name: The sheet's name, as it appears in the circuit JSON.
                A repeated block's later instances carry a numeric suffix.

        Returns:
            The path of that sheet's file.
        """
        return self.project_dir / f"{sheet_name}.kicad_sch"

    def block_dir(self, block: str) -> Path:
        """One block's directory.

        Args:
            block: The block's name, which is also its sheet name.

        Returns:
            The path of that block's directory.
        """
        return self.blocks_dir / block

    def blocks(self) -> List[str]:
        """Every block the design declares, in name order.

        Returns:
            The block names, taken from the subdirectories that hold a
            ``block.py``.
        """
        if not self.blocks_dir.is_dir():
            return []
        return sorted(
            entry.name
            for entry in self.blocks_dir.iterdir()
            if (entry / BLOCK_MODULE).is_file()
        )


@dataclass
class BuildResult:
    """What one build of the project did.

    Attributes:
        board: The board that was built.
        styled: Sheet names a placement was applied to, in the order applied.
        unstyled: Blocks with no ``layout.py`` yet, so still drawn as the
            generator left them. On a partly finished board this is the list of
            blocks whose agents have not got there.
        problems: What :func:`validate_layout` found. Empty means the drawing
            matches the circuit and no wire is drawn over a part.
        images: The rendered sheets, in page order.
        waited: Seconds spent waiting for another agent's build.
    """

    board: Board
    styled: List[str] = field(default_factory=list)
    unstyled: List[str] = field(default_factory=list)
    problems: List[LayoutProblem] = field(default_factory=list)
    images: List[Path] = field(default_factory=list)
    waited: float = 0.0

    def summary(self) -> str:
        """One paragraph a block agent can paste into its report.

        Returns:
            The lines describing this build.
        """
        lines = [f"{self.board.name}: {len(self.styled)} sheet(s) styled"]
        if self.styled:
            lines.append("  styled:   " + ", ".join(self.styled))
        if self.unstyled:
            lines.append("  no layout yet: " + ", ".join(self.unstyled))
        if self.waited > 1.0:
            lines.append(f"  waited {self.waited:.1f}s for another agent's build")
        if self.problems:
            lines.append(f"  {len(self.problems)} layout problem(s):")
            lines.extend("    " + str(problem) for problem in self.problems)
        else:
            lines.append("  drawing matches the circuit")
        return "\n".join(lines)


def load_block(blocks_dir: Path, block: str):
    """Import one block's ``block.py`` by path.

    Blocks are separate files rather than a package so that each agent owns
    exactly one of them and can rewrite it without touching anything else. That
    means the root builder has to import them by path, which is what this does.

    Args:
        blocks_dir: The directory holding one subdirectory per block.
        block: The block's name, which is its subdirectory's name.

    Returns:
        The imported module. The circuit function is an attribute of it.

    Raises:
        BuildFailed: There is no ``block.py`` there, or it does not import.
    """
    path = Path(blocks_dir) / block / BLOCK_MODULE
    if not path.is_file():
        raise BuildFailed(f"{path} does not exist")
    module = _execute(path, f"_cs_block_{block}")
    # Registered so a block imported twice in one process is the same object.
    sys.modules[module.__name__] = module
    return module


def _execute(path: Path, name: str) -> ModuleType:
    """Run a Python file as a module, reading the source every time.

    The obvious ``importlib.util.spec_from_file_location`` is wrong here.
    CPython's source loader caches bytecode against the source file's
    modification time and size, and it only records the time to the second. A
    block agent that rewrites its layout moments after the last build, to the
    same length - which changing one reference designator does - gets the
    previous version back from ``__pycache__``. Compiling the text that is
    actually on disk cannot go stale.

    Args:
        path: The file to run.
        name: The module name to give it.

    Returns:
        The executed module.

    Raises:
        BuildFailed: The file does not compile or run.
    """
    module = ModuleType(name)
    module.__file__ = str(path)
    try:
        source = path.read_text(encoding="utf-8")
        exec(compile(source, str(path), "exec"), module.__dict__)
    except Exception as error:
        raise BuildFailed(f"{path} did not import: {error}") from error
    return module


def _load_spec(path: Path, attribute: str) -> Optional[PlacementSpec]:
    """Read a placement out of a layout module.

    The file is executed under a fresh module name every time. A build reads
    layout files that another agent wrote seconds ago, and a cached import
    would hand back the version from before it was written.

    A ``.json`` file beside it is read instead when the ``.py`` is absent, for
    placements worked out in code rather than written by hand.

    Args:
        path: The ``layout.py`` to read.
        attribute: The module-level name the placement is bound to.

    Returns:
        The placement, or None when neither file exists, or the module does not
        define that name.

    Raises:
        BuildFailed: The file exists but does not import.
    """
    if not path.is_file():
        as_json = path.with_suffix(".json")
        if as_json.is_file():
            return PlacementSpec.from_json(as_json)
        return None

    module = _execute(path, f"_cs_layout_{uuid.uuid4().hex}")
    placement = getattr(module, attribute, None)
    if placement is None:
        logger.warning("%s defines no %s, so nothing was styled from it", path, attribute)
        return None
    if not isinstance(placement, PlacementSpec):
        raise BuildFailed(f"{path}: {attribute} is {type(placement).__name__}, not a PlacementSpec")
    return placement


def _instances_of(block: str, instances: Dict[str, Dict[str, str]]) -> List[str]:
    """Every sheet that is an instance of one block.

    Args:
        block: The block's name.
        instances: The output of
            :func:`~circuit_synth.kicad.layout.extract.instance_renames`.

    Returns:
        The sheet names, first instance first.
    """
    return [sheet for sheet, mapping in instances.items() if mapping.get(block) == sheet]


def _generate(board: Board, timeout: float) -> None:
    """Run the design's root builder and write the whole project.

    Args:
        board: The board to generate.
        timeout: How long to allow the builder, in seconds. A builder that
            never returns would otherwise hold the lock for the rest of the
            run and stall every other agent behind it, so this is a deadline
            rather than a formality.

    Raises:
        BuildFailed: The builder crashed, timed out, or reported failure.
    """
    builder = board.design_dir / "board.py"
    if not builder.is_file():
        raise BuildFailed(f"{builder} does not exist, so there is no board to build")

    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "circuit_synth.board._runner",
                str(board.design_dir),
                str(board.project_dir),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise BuildFailed(
            f"the root builder did not finish within {timeout:.0f}s and was stopped; "
            f"{board.project_dir.name} is now half written"
        ) from error

    payload = None
    for line in completed.stdout.splitlines():
        if line.startswith(RESULT_PREFIX):
            payload = json.loads(line[len(RESULT_PREFIX) :])

    if payload is None:
        tail = "\n".join((completed.stdout + completed.stderr).splitlines()[-25:])
        raise BuildFailed(f"the root builder did not finish:\n{tail}")
    if not payload["success"]:
        raise BuildFailed(f"the root builder failed: {payload.get('error')}")


def _apply_block_layouts(
    board: Board, instances: Dict[str, Dict[str, str]]
) -> Tuple[List[str], List[str]]:
    """Apply every block layout on disk to every instance of its block.

    Args:
        board: The board being built.
        instances: The output of
            :func:`~circuit_synth.kicad.layout.extract.instance_renames`.

    Returns:
        ``(styled, unstyled)`` - the sheet names a placement was applied to, and
        the blocks that have no placement yet.
    """
    styled: List[str] = []
    unstyled: List[str] = []

    for block in board.blocks():
        placement = _load_spec(board.block_dir(block) / LAYOUT_MODULE, SPEC_NAME)
        if placement is None:
            unstyled.append(block)
            continue

        sheets = _instances_of(block, instances)
        if not sheets:
            logger.warning(
                "%s has a layout but no sheet in the generated project", block
            )
            unstyled.append(block)
            continue

        # The placement was written against the references the block had when
        # its agent looked at the sheet. Parts added to earlier blocks since
        # then have renumbered it, so map that frame onto the current one
        # positionally rather than trusting the reference strings.
        refs = board.block_dir(block) / LAYOUT_REFS
        to_first: Dict[str, str] = {}
        if refs.is_file():
            to_first = block_renames(refs, block, board.circuit_json, block)

        for sheet in sheets:
            per_instance = instances[sheet]
            mapping = {
                source: per_instance.get(target, target)
                for source, target in to_first.items()
            }
            for source, target in per_instance.items():
                mapping.setdefault(source, target)
            apply_placement(board.sheet(sheet), placement.renamed(mapping))
            styled.append(sheet)

    return styled, unstyled


def build_board(
    board: Board,
    *,
    note: str = "",
    capture_refs: Sequence[str] = (),
    render: bool = True,
    validate: bool = True,
    timeout: float = 600.0,
    generate_timeout: float = 900.0,
) -> BuildResult:
    """Regenerate the whole project from what is on disk, and re-style it.

    This is the one call a block agent makes after writing its ``block.py`` or
    its ``layout.py``. It runs the KiCad generation and the layout pass, under
    a lock that keeps it from colliding with the other agents' builds. It is
    idempotent: running it twice with nothing changed produces the same project.

    Args:
        board: Which board to build.
        note: What this build is for, usually the block name. It is recorded in
            the lock so a queue of waiting agents can be read off the
            filesystem.
        capture_refs: Blocks whose reference frame should be recorded from this
            build. An agent passes its own block name whenever it is about to
            write or rewrite that block's ``layout.py``, so that the placement
            it writes can be mapped forward when later blocks renumber the
            board. A block that has no recorded frame at all is captured
            regardless.
        render: Whether to render the sheets before releasing the lock.
        validate: Whether to check the drawing against the circuit.
        timeout: How long to wait for another agent's build, in seconds.
        generate_timeout: How long to allow the root builder itself, in
            seconds. It runs while the lock is held, so a builder that hangs
            stalls every other agent until this expires.

    Returns:
        What was generated, styled and found.

    Raises:
        BuildFailed: The root builder did not produce a project.
        circuit_synth.board.lock.BuildBusy: Another agent held the lock for
            longer than ``timeout``. Nothing was written.
    """
    result = BuildResult(board=board)

    with build_lock(board.project_dir, note=note, timeout=timeout) as waited:
        result.waited = waited

        # A project KiCad has open is showing the version it loaded, and saving
        # from that editor would put it back over what we are about to write.
        require_closed(board.project_dir)

        _generate(board, generate_timeout)

        instances = instance_renames(board.circuit_json)

        # Record the reference frame before anything is restyled, so that a
        # block agent describing the sheet next sees exactly what was recorded.
        for block in board.blocks():
            refs = board.block_dir(block) / LAYOUT_REFS
            if block in capture_refs or not refs.is_file():
                refs.write_text(board.circuit_json.read_text(encoding="utf-8"), encoding="utf-8")

        result.styled, result.unstyled = _apply_block_layouts(board, instances)

        root_spec = _load_spec(board.design_dir / LAYOUT_MODULE, ROOT_SPEC_NAME)
        if root_spec is not None:
            apply_placement(board.root_schematic, root_spec)
            result.styled.append(board.name)

        if validate:
            result.problems = validate_layout(board.root_schematic, board.circuit_json)
        if render:
            result.images = render_sheets(board.root_schematic, board.project_dir / "img")

    return result
