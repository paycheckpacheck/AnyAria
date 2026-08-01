"""Writing figures of merit onto a KiCad schematic as red notes.

The purpose of a note is to let somebody check the design without running
anything. That means the notes have to be dense enough to carry the working -
a MOSFET with only a junction temperature on it invites the question of what
current and what duty cycle produced it - and they have to be attached to the
part they describe, because a table in the corner of the sheet is a thing a
reader has to cross-reference and therefore will not.

So each figure becomes one short red line, and the lines for a part stack at
that part's centre::

    Id = 4.7A
    Ploss = 1.2W
    Tj = 87C

Each line carries a ``vscode://file/...`` hyperlink to the line of Python that
computed it. KiCad puts an "Open ..." confirmation on the click and then hands
the URL to the shell, so the reader lands on the arithmetic rather than on a
document describing the arithmetic. This works on KiCad 9 and 10, which
validate a hyperlink only as a well-formed URI; KiCad 7 and 8 had a scheme
whitelist that ``vscode://`` does not pass, and there the note is still written
and still readable, only not clickable.

Two rules are enforced rather than left to the caller. A figure whose basis is
a guess is never written - see :class:`~circuit_synth.simulation.figures.Basis`
- and a note is never placed where it would sit on top of a symbol's own
reference or value text, because a number that overlaps another number is
worse than no number.
"""

import logging
import re
import uuid as uuid_module
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ..kicad.layout.sexp import (
    block_text,
    find_block,
    insert_before_end,
    iter_blocks,
    read_position,
    read_property,
)
from .figures import BlockAnalysis, Figure

logger = logging.getLogger(__name__)

# Red. KiCad stores RGB as integers and alpha as a float from 0 to 1.
NOTE_COLOUR: Tuple[int, int, int, float] = (255, 0, 0, 1)

# Small enough that half a dozen lines fit inside a symbol's footprint on the
# sheet, large enough to read at the zoom an engineer reviews at.
NOTE_TEXT_SIZE = 0.9

# Vertical pitch between stacked lines. A little more than the text height so
# the lines do not touch.
NOTE_LINE_PITCH = 1.15

# How close a note may come to a symbol's own reference or value text before
# it is treated as colliding, in mm.
TEXT_CLEARANCE = 0.5

# Horizontal advance per character as a fraction of the text height. KiCad's
# stroke font is close to this, and the estimate only has to be good enough to
# decide whether two pieces of text overlap.
CHARACTER_ADVANCE = 0.75

# The scheme used for the back-links. Notes written by this module are
# recognised by it, so re-annotating a sheet replaces them rather than
# stacking a second set on top.
LINK_SCHEME = "vscode://file/"


@dataclass(frozen=True)
class Note:
    """One line of red text placed on a schematic.

    Attributes:
        text: The line, such as ``"Id = 4.7A"``.
        at: Position in mm.
        href: The URL the note links to, or None when the figure carried no
            source location.
    """

    text: str
    at: Tuple[float, float]
    href: Optional[str] = None

    def render(self) -> str:
        """Render the note as a KiCad ``text`` element.

        Returns:
            The s-expression, indented for the top level of a sheet and
            starting with a newline.
        """
        red = (
            f"(color {NOTE_COLOUR[0]} {NOTE_COLOUR[1]} "
            f"{NOTE_COLOUR[2]} {NOTE_COLOUR[3]:g})"
        )
        escaped = self.text.replace("\\", "\\\\").replace('"', '\\"')
        # href is a child of effects, a sibling of font. Inside font it is a
        # fatal parse error, and KiCad refuses the whole sheet.
        link = f'\n\t\t\t(href "{self.href}")' if self.href else ""
        return (
            f'\n\t(text "{escaped}"'
            f"\n\t\t(exclude_from_sim yes)"
            f"\n\t\t(at {self.at[0]:g} {self.at[1]:g} 0)"
            f"\n\t\t(effects"
            f"\n\t\t\t(font"
            f"\n\t\t\t\t(size {NOTE_TEXT_SIZE:g} {NOTE_TEXT_SIZE:g})"
            f"\n\t\t\t\t{red}"
            f"\n\t\t\t)"
            f"{link}"
            f"\n\t\t)"
            f'\n\t\t(uuid "{uuid_module.uuid4()}")'
            f"\n\t)"
        )


def symbol_centres(schematic: Path) -> Dict[str, Tuple[float, float]]:
    """Find the placement origin of every symbol on a sheet.

    The origin is what a note is centred on. For the symbols circuit-synth
    places it sits inside the body, which is what "at the centre of the
    component" means in practice and is stable under rotation, unlike a
    computed bounding-box centre.

    Args:
        schematic: The ``.kicad_sch`` to read.

    Returns:
        A mapping of reference designator to ``(x, y)`` in mm. Power symbols
        are included; they are rarely worth annotating but excluding them here
        would hide a caller's mistake.
    """
    text = schematic.read_text(encoding="utf-8")
    centres: Dict[str, Tuple[float, float]] = {}

    for extent in iter_blocks(text, "symbol"):
        block = block_text(text, extent)
        reference = read_property(block, "Reference")
        position = read_position(block)
        if reference and position:
            centres[reference] = (position[0], position[1])

    return centres


def text_extent(
    content: str,
    at: Tuple[float, float],
    size: float,
    justify: str = "",
) -> Tuple[float, float, float, float]:
    """Estimate the area a piece of schematic text covers.

    KiCad's stroke font advances a little under one text height per character.
    That is close enough to decide whether two pieces of text collide, and far
    cheaper than laying out the glyphs.

    Args:
        content: The text.
        at: Its anchor point in mm.
        size: The text height in mm.
        justify: The justification tokens from the effects block, such as
            ``"left bottom"``. Decides which side of the anchor the text sits.

    Returns:
        A ``(min_x, min_y, max_x, max_y)`` box in mm.
    """
    width = len(content) * size * CHARACTER_ADVANCE
    height = size

    if "left" in justify:
        min_x, max_x = at[0], at[0] + width
    elif "right" in justify:
        min_x, max_x = at[0] - width, at[0]
    else:
        min_x, max_x = at[0] - width / 2, at[0] + width / 2

    # KiCad's y axis grows downwards, so "bottom" justification means the
    # anchor is below the glyphs.
    if "bottom" in justify:
        min_y, max_y = at[1] - height, at[1]
    elif "top" in justify:
        min_y, max_y = at[1], at[1] + height
    else:
        min_y, max_y = at[1] - height / 2, at[1] + height / 2

    return min_x, min_y, max_x, max_y


def visible_text_extents(schematic: Path) -> List[Tuple[float, float, float, float]]:
    """Find the areas the sheet's existing text already covers.

    Only visible text counts. Hidden properties - footprint, datasheet, the
    generator's bookkeeping - are not drawn, so a note may sit on top of them.

    Args:
        schematic: The ``.kicad_sch`` to read.

    Returns:
        A box per piece of visible text, as ``(min_x, min_y, max_x, max_y)``
        in mm.
    """
    text = schematic.read_text(encoding="utf-8")
    boxes: List[Tuple[float, float, float, float]] = []

    def size_and_justify(block: str) -> Tuple[float, str]:
        """Read a text block's font size and justification.

        Args:
            block: The s-expression holding an effects block.

        Returns:
            A ``(size, justify)`` pair, defaulting to KiCad's 1.27mm.
        """
        size_match = re.search(r"\(size\s+([\d.]+)\s+([\d.]+)\)", block)
        justify_match = re.search(r"\(justify\s+([a-z ]+)\)", block)
        return (
            float(size_match.group(1)) if size_match else 1.27,
            justify_match.group(1) if justify_match else "",
        )

    for extent in iter_blocks(text, "symbol"):
        block = block_text(text, extent)
        for match in re.finditer(r"\(property\s+\"", block):
            try:
                start, end = find_block(block, match.start())
            except ValueError:
                continue
            field = block[start:end]
            if "(hide yes)" in field:
                continue
            value = re.match(r'\(property\s+"[^"]*"\s+"([^"]*)"', field)
            position = read_position(field)
            if not (value and position and value.group(1)):
                continue
            size, justify = size_and_justify(field)
            boxes.append(
                text_extent(value.group(1), (position[0], position[1]), size, justify)
            )

    for keyword in ("text", "label", "global_label", "hierarchical_label"):
        for extent in iter_blocks(text, keyword):
            block = block_text(text, extent)
            value = re.match(rf'\({keyword}\s+"([^"]*)"', block)
            position = read_position(block)
            if not (value and position):
                continue
            size, justify = size_and_justify(block)
            boxes.append(
                text_extent(value.group(1), (position[0], position[1]), size, justify)
            )

    return boxes


def _collides(
    box: Tuple[float, float, float, float],
    occupied: Sequence[Tuple[float, float, float, float]],
    clearance: float,
) -> bool:
    """Report whether a box overlaps anything already on the sheet.

    Args:
        box: The area to test, as ``(min_x, min_y, max_x, max_y)`` in mm.
        occupied: Areas already taken.
        clearance: Extra separation to keep, in mm.

    Returns:
        True when the box, grown by the clearance, meets an occupied area.
    """
    min_x, min_y, max_x, max_y = box
    return any(
        min_x - clearance < other[2]
        and max_x + clearance > other[0]
        and min_y - clearance < other[3]
        and max_y + clearance > other[1]
        for other in occupied
    )


def place_notes(
    figures: Sequence[Figure],
    centre: Tuple[float, float],
    occupied: Sequence[Tuple[float, float, float, float]] = (),
    clearance: float = TEXT_CLEARANCE,
) -> List[Note]:
    """Stack a component's figures into a block of notes at its centre.

    The stack is centred on the component, so a part with one figure gets it
    on the body and a part with six gets three above and three below. If the
    stack would land on text that is already there, the block is tried at a
    series of offsets - below the part, then above, then further out - keeping
    the lines together and in order, because a set of figures split across the
    sheet is no longer readable as one part's working.

    Args:
        figures: The figures for one component, in the order they should read.
        centre: The component's origin in mm.
        occupied: Areas of the sheet already covered by text.
        clearance: Minimum separation from existing text, in mm.

    Returns:
        One note per figure, positioned.
    """
    if not figures:
        return []

    span = (len(figures) - 1) * NOTE_LINE_PITCH
    labels = [figure.label() for figure in figures]

    def boxes_at(dx: float, dy: float) -> List[Tuple[float, float, float, float]]:
        """Work out where the stack's lines would sit at a given offset.

        Args:
            dx: Horizontal displacement from the component centre, in mm.
            dy: Vertical displacement from the component centre, in mm.

        Returns:
            One box per line.
        """
        top = centre[1] - span / 2.0 + dy
        return [
            text_extent(
                label, (centre[0] + dx, top + index * NOTE_LINE_PITCH), NOTE_TEXT_SIZE
            )
            for index, label in enumerate(labels)
        ]

    # Centred first, then stepping away from the part alternately below and
    # above. A whole stack height per step, so a displaced block clears the
    # thing it collided with rather than shuffling into it.
    step = span + NOTE_LINE_PITCH * 2
    offsets = [(0.0, 0.0)]
    for multiple in range(1, 5):
        offsets.append((0.0, multiple * step))
        offsets.append((0.0, -multiple * step))

    chosen = offsets[0]
    for candidate in offsets:
        if not any(_collides(box, occupied, clearance) for box in boxes_at(*candidate)):
            chosen = candidate
            break
    else:
        logger.warning(
            "No clear space for %d notes at %s; placing them on the part anyway",
            len(figures),
            centre,
        )

    dx, dy = chosen
    top = centre[1] - span / 2.0 + dy
    return [
        Note(
            text=label,
            at=(centre[0] + dx, top + index * NOTE_LINE_PITCH),
            href=figures[index].link(),
        )
        for index, label in enumerate(labels)
    ]


def clear_notes(schematic: Path) -> int:
    """Remove notes previously written by this module.

    Notes are recognised by their back-link scheme, so hand-written text and
    text linking to anything else is left alone. Called before writing so that
    re-running an analysis replaces the notes rather than stacking a second
    set on top of the first.

    Args:
        schematic: The ``.kicad_sch`` to edit, in place.

    Returns:
        How many notes were removed.
    """
    text = schematic.read_text(encoding="utf-8")
    removed = 0

    for start, end in reversed(list(iter_blocks(text, "text"))):
        block = text[start:end]
        if f'(href "{LINK_SCHEME}' not in block:
            continue
        line_start = text.rfind("\n", 0, start)
        text = text[:line_start] + text[end:]
        removed += 1

    if removed:
        schematic.write_text(text, encoding="utf-8")
        logger.info("Removed %d existing notes from %s", removed, schematic.name)
    return removed


def annotate_schematic(
    schematic: Path,
    analysis: BlockAnalysis,
    replace: bool = True,
    require_all: bool = False,
) -> List[Note]:
    """Write an analysis's figures onto a schematic as red notes.

    Only figures with real evidence behind them are written; anything
    estimated stays in :meth:`BlockAnalysis.unverified` and is reported
    instead. Figures naming a component the sheet does not have are skipped
    with a warning, so one analysis can be applied across the sheets of a
    hierarchy.

    Args:
        schematic: The ``.kicad_sch`` to annotate, in place.
        analysis: The figures to write.
        replace: Remove notes from a previous run first. Leaving this off
            stacks a second set on top of the first.
        require_all: Raise if any figure names a component that is not on the
            sheet. Useful when annotating a single block, wrong when
            annotating one sheet of several.

    Returns:
        The notes that were written.

    Raises:
        ValueError: If ``require_all`` is set and a figure names a component
            the sheet does not have.
    """
    schematic = Path(schematic)
    if replace:
        clear_notes(schematic)

    centres = symbol_centres(schematic)
    occupied = list(visible_text_extents(schematic))
    notes: List[Note] = []
    missing: List[str] = []

    for reference, figures in sorted(analysis.by_reference().items()):
        centre = centres.get(reference)
        if centre is None:
            missing.append(reference)
            continue

        placed = place_notes(figures, centre, occupied)
        notes.extend(placed)
        # Later components must not be placed on top of these.
        occupied.extend(
            text_extent(note.text, note.at, NOTE_TEXT_SIZE) for note in placed
        )

    if missing:
        message = (
            f"{schematic.name} has no symbol for: {', '.join(sorted(missing))}. "
            f"Those figures were not written."
        )
        if require_all:
            raise ValueError(message)
        logger.warning(message)

    if notes:
        text = schematic.read_text(encoding="utf-8")
        addition = "".join(note.render() for note in notes)
        schematic.write_text(insert_before_end(text, addition), encoding="utf-8")

    unlinked = sum(1 for note in notes if note.href is None)
    logger.info(
        "Wrote %d notes to %s (%d without a back-link)",
        len(notes),
        schematic.name,
        unlinked,
    )
    return notes


def annotate_project(
    project_dir: Path,
    analyses: Iterable[BlockAnalysis],
    replace: bool = True,
) -> Dict[str, List[Note]]:
    """Annotate every sheet of a project from a set of block analyses.

    Reference designators are unique across a circuit-synth hierarchy, so a
    figure lands on whichever sheet carries its component and is skipped on
    the others. That means the caller does not have to work out which of
    ``HalfBridge.kicad_sch``, ``HalfBridge2.kicad_sch`` and
    ``HalfBridge3.kicad_sch`` a given analysis belongs to.

    Args:
        project_dir: The generated project directory.
        analyses: The analyses to write.
        replace: Remove notes from a previous run first.

    Returns:
        A mapping of sheet file name to the notes written on it. Sheets that
        got no notes are left out.
    """
    project_dir = Path(project_dir)
    combined = BlockAnalysis(block="project")
    for analysis in analyses:
        combined.figures.extend(analysis.figures)
        combined.gaps.extend(analysis.gaps)

    written: Dict[str, List[Note]] = {}
    for sheet in sorted(project_dir.glob("*.kicad_sch")):
        notes = annotate_schematic(sheet, combined, replace=replace)
        if notes:
            written[sheet.name] = notes

    return written
