# -*- coding: utf-8 -*-
"""Keep wires off the parts they are drawn between.

A wire that runs straight through a symbol is the single thing that makes a
schematic unreadable fastest. It reads as a connection to that part when it is
not one, and it hides whatever it crosses. The convention every hand-drawn
sheet follows is that a wire goes around a body rather than over it, even when
the detour costs two extra corners.

Nothing stops the placement spec drawing such a wire, so this module does two
things about it: it finds the wires already crossing a body, and it routes a
new one around them. The obstacles come from the symbols' own graphics, which
are the shapes actually printed on the page - not the padded placement extents,
which are much larger than the part and would forbid perfectly ordinary wiring.
"""

import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from . import sexp

logger = logging.getLogger(__name__)

Point = Tuple[float, float]

GRID = 1.27

# How far a wire should stay off a body when routing around it. One grid step
# reads as deliberate clearance rather than a near miss.
CLEARANCE = 1.27

# How far past the two endpoints a detour may reach when looking for a way
# around, in grid steps. Enough to clear any symbol on a sheet.
DETOUR_REACH = 40

_XY = re.compile(r"\(xy\s+(-?[\d.]+)\s+(-?[\d.]+)\)")


@dataclass(frozen=True)
class Box:
    """An axis-aligned rectangle in schematic millimetres.

    Attributes:
        min_x: Left edge.
        min_y: Top edge, KiCad's y growing downwards.
        max_x: Right edge.
        max_y: Bottom edge.
    """

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def inflated(self, margin: float) -> "Box":
        """Grow the box on every side.

        Args:
            margin: How far to grow, in mm.

        Returns:
            The grown box.
        """
        return Box(
            self.min_x - margin,
            self.min_y - margin,
            self.max_x + margin,
            self.max_y + margin,
        )

    def contains(self, point: Point) -> bool:
        """Report whether a point lies inside the box.

        Args:
            point: The ``(x, y)`` to test.

        Returns:
            True when the point is strictly inside.
        """
        return (
            self.min_x < point[0] < self.max_x and self.min_y < point[1] < self.max_y
        )


def _rotate(x: float, y: float, rotation: float) -> Point:
    """Rotate a symbol-local offset into sheet coordinates.

    Args:
        x: Offset along the symbol's x axis.
        y: Offset along the symbol's y axis.
        rotation: The symbol's rotation in degrees.

    Returns:
        The rotated offset. KiCad's y axis grows downwards, which is why the
        angle is negated.
    """
    radians = math.radians(-rotation)
    cos, sin = math.cos(radians), math.sin(radians)
    return (x * cos - y * sin, x * sin + y * cos)


def _graphic_points(graphic: dict) -> List[Point]:
    """Collect the points that bound one graphic element.

    Args:
        graphic: One entry of a symbol's ``graphics`` list.

    Returns:
        The points to include in the body outline, empty when the element has
        no extent worth bounding.
    """
    points: List[Point] = []
    for key in ("start", "end", "mid"):
        value = graphic.get(key)
        if value:
            points.append((float(value[0]), float(value[1])))
    for value in graphic.get("points") or []:
        points.append((float(value[0]), float(value[1])))

    center, radius = graphic.get("center"), graphic.get("radius")
    if center and radius:
        cx, cy, r = float(center[0]), float(center[1]), float(radius)
        points += [(cx - r, cy - r), (cx + r, cy + r)]
    return points


def symbol_body(lib_id: str, position: Point, rotation: float) -> Optional[Box]:
    """Work out the printed outline of a placed symbol.

    Args:
        lib_id: The symbol's library identifier.
        position: Where the symbol origin sits on the sheet.
        rotation: The symbol's rotation in degrees.

    Returns:
        The body as a box in sheet coordinates, or None when the symbol draws
        nothing - a power flag, for instance, whose whole extent is its pin.
    """
    from ..kicad_symbol_cache import SymbolLibCache

    try:
        lib_data = SymbolLibCache.get_symbol_data(lib_id)
    except Exception as error:  # pragma: no cover - library lookup varies
        logger.debug("No library data for %s: %s", lib_id, error)
        return None

    points: List[Point] = []
    for graphic in (lib_data or {}).get("graphics", []):
        points += _graphic_points(graphic)
    if not points:
        return None

    rotated = [_rotate(x, y, rotation) for x, y in points]
    return Box(
        position[0] + min(x for x, _ in rotated),
        position[1] + min(y for _, y in rotated),
        position[0] + max(x for x, _ in rotated),
        position[1] + max(y for _, y in rotated),
    )


def sheet_bodies(sheet_path: Path) -> Dict[str, Box]:
    """Read the printed outline of every symbol on a sheet.

    Args:
        sheet_path: Path to the .kicad_sch file.

    Returns:
        Reference designator to body box. Symbols that draw nothing are left
        out, as are power symbols, which are small enough that a wire passing
        one reads as a wire passing a label.
    """
    text = sheet_path.read_text(encoding="utf-8")
    bodies: Dict[str, Box] = {}

    for extent in sexp.iter_blocks(text, "symbol"):
        block = sexp.block_text(text, extent)
        lib_id = sexp.read_string(block, "lib_id")
        position = sexp.read_position(block)
        reference = sexp.read_property(block, "Reference")
        if not lib_id or position is None or not reference:
            continue
        if lib_id.startswith("power:"):
            continue

        body = symbol_body(lib_id, (position[0], position[1]), position[2])
        if body is not None:
            bodies[reference] = body
    return bodies


def sheet_wires(sheet_path: Path) -> List[Tuple[Point, Point]]:
    """Read the wire segments drawn on a sheet.

    Args:
        sheet_path: Path to the .kicad_sch file.

    Returns:
        Each wire as a ``(start, end)`` pair.
    """
    text = sheet_path.read_text(encoding="utf-8")
    segments: List[Tuple[Point, Point]] = []

    for extent in sexp.iter_blocks(text, "wire"):
        points = [
            (float(x), float(y)) for x, y in _XY.findall(sexp.block_text(text, extent))
        ]
        if len(points) >= 2:
            segments.append((points[0], points[1]))
    return segments


def sheet_notes(sheet_path: Path) -> List[Box]:
    """Read the text boxes drawn on a sheet.

    Args:
        sheet_path: Path to the .kicad_sch file.

    Returns:
        Each text box as a rectangle, in file order.
    """
    text = sheet_path.read_text(encoding="utf-8")
    boxes: List[Box] = []

    for extent in sexp.iter_blocks(text, "text_box"):
        block = sexp.block_text(text, extent)
        position = sexp.read_position(block)
        size = re.search(r"\(size\s+(-?[\d.]+)\s+(-?[\d.]+)\s*\)", block)
        if position is None or size is None:
            continue
        width, height = float(size.group(1)), float(size.group(2))
        boxes.append(
            Box(position[0], position[1], position[0] + width, position[1] + height)
        )
    return boxes


def boxes_overlap(first: Box, second: Box) -> bool:
    """Report whether two rectangles share any area.

    Args:
        first: One rectangle.
        second: The other.

    Returns:
        True when they overlap. Rectangles that only touch do not count.
    """
    return (
        first.min_x < second.max_x
        and second.min_x < first.max_x
        and first.min_y < second.max_y
        and second.min_y < first.max_y
    )


def notes_over_components(sheet_path: Path) -> List[Tuple[str, Box]]:
    """Find the text boxes on a sheet that sit on top of a part.

    Args:
        sheet_path: Path to the .kicad_sch file.

    Returns:
        A ``(reference, box)`` pair per overlap, sorted by the part covered.
    """
    bodies = sheet_bodies(sheet_path)
    notes = sheet_notes(sheet_path)

    return sorted(
        (
            (reference, note)
            for note in notes
            for reference, body in bodies.items()
            if boxes_overlap(note, body)
        ),
        key=lambda hit: hit[0],
    )


def segment_crosses(start: Point, end: Point, box: Box) -> bool:
    """Report whether a straight segment passes through a box.

    Args:
        start: One end of the segment.
        end: The other end.
        box: The obstacle.

    Returns:
        True when any part of the segment lies strictly inside the box.
        Touching an edge does not count, so a wire may run along a body and a
        wire may end on a pin sitting on the outline.
    """
    dx, dy = end[0] - start[0], end[1] - start[1]
    low, high = 0.0, 1.0

    for delta, origin, lower, upper in (
        (dx, start[0], box.min_x, box.max_x),
        (dy, start[1], box.min_y, box.max_y),
    ):
        if abs(delta) < 1e-9:
            if not (lower < origin < upper):
                return False
            continue
        first = (lower - origin) / delta
        second = (upper - origin) / delta
        low = max(low, min(first, second))
        high = min(high, max(first, second))
        if low >= high:
            return False

    # A shared edge or a single touching corner leaves no length inside.
    return (high - low) > 1e-9


@dataclass
class WireOverComponent:
    """One wire drawn across a part.

    Attributes:
        reference: The part the wire crosses.
        start: Where the offending segment starts.
        end: Where it ends.
    """

    reference: str
    start: Point
    end: Point

    def __str__(self) -> str:
        return (
            f"wire ({self.start[0]:g},{self.start[1]:g}) -> "
            f"({self.end[0]:g},{self.end[1]:g}) runs across {self.reference}"
        )


def wires_over_components(
    sheet_path: Path, clearance: float = 0.0
) -> List[WireOverComponent]:
    """Find the wires on a sheet that are drawn over a symbol body.

    Args:
        sheet_path: Path to the .kicad_sch file.
        clearance: How far off a body a wire must stay. Zero reports only wires
            actually crossing a part; a positive value also reports wires
            skimming one.

    Returns:
        One entry per crossing, sorted by the part crossed.
    """
    bodies = sheet_bodies(sheet_path)
    segments = sheet_wires(sheet_path)

    found = [
        WireOverComponent(reference, start, end)
        for start, end in segments
        for reference, body in bodies.items()
        if segment_crosses(start, end, body.inflated(clearance))
    ]
    return sorted(found, key=lambda hit: (hit.reference, hit.start, hit.end))


def path_is_clear(points: Sequence[Point], boxes: Iterable[Box]) -> bool:
    """Report whether a multi-segment path avoids every obstacle.

    Args:
        points: The path's corners, start to end.
        boxes: The obstacles to avoid.

    Returns:
        True when no segment of the path passes through any box.
    """
    boxes = list(boxes)
    return not any(
        segment_crosses(points[index], points[index + 1], box)
        for index in range(len(points) - 1)
        for box in boxes
    )


def _snap(value: float) -> float:
    """Put a coordinate on the schematic grid.

    Args:
        value: The coordinate in mm.

    Returns:
        The nearest grid coordinate.
    """
    return round(value / GRID) * GRID


def _candidates(start: Point, end: Point) -> List[List[Point]]:
    """Propose orthogonal paths between two points, simplest first.

    Args:
        start: Where the wire begins.
        end: Where it ends.

    Returns:
        Candidate paths: the straight run when the points line up, then the two
        single-corner routes, then two-corner routes whose middle line is swept
        outwards from between the points to well beyond them.
    """
    paths: List[List[Point]] = []

    if abs(start[0] - end[0]) < 1e-9 or abs(start[1] - end[1]) < 1e-9:
        paths.append([start, end])

    paths.append([start, (end[0], start[1]), end])
    paths.append([start, (start[0], end[1]), end])

    # Sweep a middle line outwards, so the nearest way around is tried before
    # the long way round.
    for step in range(1, DETOUR_REACH + 1):
        offset = step * GRID
        for low, high, vertical in (
            (min(start[0], end[0]), max(start[0], end[0]), True),
            (min(start[1], end[1]), max(start[1], end[1]), False),
        ):
            span = high - low
            inside = [low + offset, high - offset] if offset * 2 < span else []
            for line in inside + [low - offset, high + offset]:
                line = _snap(line)
                if vertical:
                    paths.append([start, (line, start[1]), (line, end[1]), end])
                else:
                    paths.append([start, (start[0], line), (end[0], line), end])
    return paths


def route_around(
    start: Point,
    end: Point,
    boxes: Iterable[Box],
    clearance: float = CLEARANCE,
) -> List[Point]:
    """Draw an orthogonal wire from one point to another, avoiding bodies.

    Args:
        start: Where the wire begins, typically a pin end.
        end: Where it ends.
        boxes: The symbol bodies to route around.
        clearance: How far the wire should stay off a body.

    Returns:
        The wire's corners, start to end, with as few bends as the obstacles
        allow. When no route avoids everything, the plain single-corner route
        is returned so the caller still gets a connection; check it with
        :func:`path_is_clear` when that matters.
    """
    obstacles = [box.inflated(clearance) for box in boxes]

    # A pin sitting inside an inflated body would make every route fail, so
    # ignore the obstacles the wire is required to touch.
    obstacles = [
        box for box in obstacles if not (box.contains(start) or box.contains(end))
    ]

    for path in _candidates(start, end):
        trimmed = [
            point
            for index, point in enumerate(path)
            if index == 0 or point != path[index - 1]
        ]
        if path_is_clear(trimmed, obstacles):
            return trimmed

    logger.debug("No clear route from %s to %s; falling back to one corner", start, end)
    return [start, (end[0], start[1]), end]


def segments_of(points: Sequence[Point]) -> List[Tuple[Point, Point]]:
    """Turn a path's corners into the wire segments that draw it.

    Args:
        points: The path's corners, start to end.

    Returns:
        Consecutive point pairs, skipping any zero-length step.
    """
    return [
        (points[index], points[index + 1])
        for index in range(len(points) - 1)
        if points[index] != points[index + 1]
    ]
