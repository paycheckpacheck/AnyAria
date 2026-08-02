# -*- coding: utf-8 -*-
"""Describe a generated sheet so a layout can be reasoned about.

Placing a schematic well needs more than a netlist. It needs to know where each
pin sits on its symbol and which way it faces, because that is what decides
which way round a part should go and where a wire can leave it. This module
gathers that, per sheet, into one description.
"""

import json
import logging
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import sexp

logger = logging.getLogger(__name__)


@dataclass
class PinDescription:
    """One pin of a placed symbol.

    Attributes:
        number: Pin number as KiCad knows it.
        name: Pin name from the symbol library.
        electrical_type: KiCad pin type, such as ``"power_in"`` or ``"output"``.
        offset: Pin position relative to the symbol origin, in schematic mm,
            with the symbol unrotated.
        side: Which side of the body the pin leaves from, once rotation is
            applied: ``"left"``, ``"right"``, ``"top"`` or ``"bottom"``.
        net: The net attached to this pin, or None.
    """

    number: str
    name: str
    electrical_type: str
    offset: Tuple[float, float]
    side: str
    net: Optional[str] = None


@dataclass
class ComponentDescription:
    """One placed symbol.

    Attributes:
        reference: Reference designator.
        value: Value field.
        lib_id: Library identifier.
        position: Current ``(x, y)`` origin in mm.
        rotation: Current rotation in degrees.
        body: Symbol body size as ``(width, height)`` in mm, excluding text.
        pins: The symbol's pins.
        is_power: Whether this is a power symbol rather than a real part.
    """

    reference: str
    value: str
    lib_id: str
    position: Tuple[float, float]
    rotation: float
    body: Tuple[float, float]
    pins: List[PinDescription] = field(default_factory=list)
    is_power: bool = False


@dataclass
class SheetDescription:
    """Everything needed to lay out one sheet.

    Attributes:
        path: Path to the .kicad_sch file.
        name: Sheet name.
        paper: Paper size, such as ``"A4"``.
        extents: Usable drawing area as ``(min_x, min_y, max_x, max_y)`` in mm.
        components: The real parts on the sheet.
        power_symbols: The power symbols on the sheet.
        nets: Net name to the ``"REF.PIN"`` tokens on it.
        ports: Hierarchical port name to direction, for a sheet that is a block.
        child_sheets: Names of the sheet symbols placed on this sheet.
    """

    path: str
    name: str
    paper: str
    extents: Tuple[float, float, float, float]
    components: List[ComponentDescription] = field(default_factory=list)
    power_symbols: List[ComponentDescription] = field(default_factory=list)
    nets: Dict[str, List[str]] = field(default_factory=dict)
    ports: Dict[str, str] = field(default_factory=dict)
    child_sheets: List[str] = field(default_factory=list)

    def to_json(self, indent: int = 1) -> str:
        """Serialize the description.

        Args:
            indent: JSON indentation.

        Returns:
            The description as JSON.
        """
        return json.dumps(asdict(self), indent=indent)


# Usable area per paper size, in mm, inside KiCad's drawing frame.
PAPER_EXTENTS = {
    "A4": (12.7, 12.7, 284.0, 197.0),
    "A3": (12.7, 12.7, 407.0, 284.0),
    "A2": (12.7, 12.7, 581.0, 407.0),
}


def _pin_side(offset: Tuple[float, float], rotation: float) -> str:
    """Work out which way a pin faces once its symbol is rotated.

    Args:
        offset: The pin's offset from the symbol origin, unrotated.
        rotation: The symbol's rotation in degrees.

    Returns:
        ``"left"``, ``"right"``, ``"top"`` or ``"bottom"``.
    """
    radians = math.radians(-rotation)
    x = offset[0] * math.cos(radians) - offset[1] * math.sin(radians)
    y = offset[0] * math.sin(radians) + offset[1] * math.cos(radians)
    if abs(x) >= abs(y):
        return "right" if x > 0 else "left"
    return "bottom" if y > 0 else "top"


def describe_sheet(
    sheet_path: Path,
    nets: Optional[Dict[str, List[str]]] = None,
    ports: Optional[Dict[str, str]] = None,
) -> SheetDescription:
    """Read a sheet and describe what is on it.

    Args:
        sheet_path: Path to the .kicad_sch file.
        nets: Net name to ``"REF.PIN"`` tokens for this sheet, when known.
        ports: Hierarchical port name to direction, when the sheet is a block.

    Returns:
        The sheet description.
    """
    from ..kicad_symbol_cache import SymbolLibCache
    from ..sch_gen.symbol_geometry import SymbolBoundingBoxCalculator
    from ..sch_gen.wired_layout import rotate_offset

    text = sheet_path.read_text(encoding="utf-8")
    paper = sexp.read_string(text, "paper") or "A4"

    pin_nets: Dict[str, str] = {}
    for net_name, tokens in (nets or {}).items():
        for token in tokens:
            pin_nets[token] = net_name

    components: List[ComponentDescription] = []
    power_symbols: List[ComponentDescription] = []

    for extent in sexp.iter_blocks(text, "symbol"):
        block = sexp.block_text(text, extent)
        lib_id = sexp.read_string(block, "lib_id")
        position = sexp.read_position(block)
        reference = sexp.read_property(block, "Reference")
        if not lib_id or position is None or not reference:
            continue

        value = sexp.read_property(block, "Value") or ""
        is_power = lib_id.startswith("power:")

        pins: List[PinDescription] = []
        body = (10.0, 10.0)
        try:
            lib_data = SymbolLibCache.get_symbol_data(lib_id)
        except Exception as error:  # pragma: no cover - library lookup varies
            logger.debug("No library data for %s: %s", lib_id, error)
            lib_data = None

        if lib_data:
            try:
                body = SymbolBoundingBoxCalculator.get_symbol_dimensions(
                    lib_data, include_properties=False
                )
            except Exception:  # pragma: no cover - defensive
                body = (10.0, 10.0)

            for pin_data in lib_data.get("pins", []):
                number = str(pin_data.get("number", ""))
                offset = rotate_offset(
                    float(pin_data.get("x", 0.0)), float(pin_data.get("y", 0.0)), 0.0
                )
                pins.append(
                    PinDescription(
                        number=number,
                        name=pin_data.get("name", ""),
                        electrical_type=pin_data.get("function")
                        or pin_data.get("func", "passive"),
                        offset=(round(offset[0], 3), round(offset[1], 3)),
                        side=_pin_side(offset, position[2]),
                        net=pin_nets.get(f"{reference}.{number}"),
                    )
                )

        description = ComponentDescription(
            reference=reference,
            value=value,
            lib_id=lib_id,
            position=(position[0], position[1]),
            rotation=position[2],
            body=(round(body[0], 2), round(body[1], 2)),
            pins=pins,
            is_power=is_power,
        )
        (power_symbols if is_power else components).append(description)

    child_sheets = re.findall(r'\(property "Sheetname" "([^"]+)"', text)

    return SheetDescription(
        path=str(sheet_path),
        name=sheet_path.stem,
        paper=paper,
        extents=PAPER_EXTENTS.get(paper, PAPER_EXTENTS["A4"]),
        components=components,
        power_symbols=power_symbols,
        nets=nets or {},
        ports=ports or {},
        child_sheets=child_sheets,
    )


def sheet_nets(circuit_json: Path) -> Dict[str, Dict[str, List[str]]]:
    """Read the per-sheet nets out of a generated circuit JSON.

    Args:
        circuit_json: The generated circuit JSON.

    Returns:
        Sheet name to a mapping of net name to ``"REF.PIN"`` tokens. The root
        circuit is keyed by its own name.
    """
    data = json.loads(circuit_json.read_text(encoding="utf-8"))
    result: Dict[str, Dict[str, List[str]]] = {}

    def walk(node: dict) -> None:
        name = node.get("name", "")
        nets: Dict[str, List[str]] = {}
        for net_name, info in (node.get("nets") or {}).items():
            entries = info.get("nodes", info) if isinstance(info, dict) else info
            nets[net_name] = [
                f"{entry['component']}.{entry['pin']['number']}" for entry in entries
            ]
        # Repeated instances of one block are written to separate sheets whose
        # names gain a numeric suffix, so keep every instance seen.
        candidate = name
        suffix = 2
        while candidate in result:
            candidate = f"{name}{suffix}"
            suffix += 1
        result[candidate] = nets

        for child in node.get("subcircuits") or []:
            walk(child)

    walk(data)
    return result


def instance_renames(circuit_json: Path) -> Dict[str, Dict[str, str]]:
    """Map one block instance's references onto every other instance's.

    A block instantiated three times gets three sets of reference designators,
    and they move whenever a part is added anywhere earlier in the design. A
    layout written against the first instance would have to be re-tabulated by
    hand every time, so the mapping is worked out from the generated circuit
    instead: instances of one block hold their components in the same creation
    order, so position in that order identifies the same part in each.

    Args:
        circuit_json: The generated circuit JSON.

    Returns:
        Sheet name to the mapping that turns the first instance's references
        into that sheet's. Each mapping also carries the sheet's own name, so a
        spec that places a child sheet symbol is renamed with it. The first
        instance maps to itself and is included, so every sheet can be looked
        up the same way.
    """
    data = json.loads(circuit_json.read_text(encoding="utf-8"))
    seen: Dict[str, int] = {}
    sheet_of: Dict[int, str] = {}

    def name_sheets(node: dict) -> None:
        """Give every circuit in the tree the sheet name it was written to."""
        name = node.get("name", "")
        seen[name] = seen.get(name, 0) + 1
        sheet_of[id(node)] = name if seen[name] == 1 else f"{name}{seen[name]}"
        for child in node.get("subcircuits") or []:
            name_sheets(child)

    name_sheets(data)

    def subtree(node: dict) -> Tuple[List[str], List[str]]:
        """Collect a circuit's references and child sheet names, in order."""
        refs = list((node.get("components") or {}).keys())
        sheets: List[str] = []
        for child in node.get("subcircuits") or []:
            sheets.append(sheet_of[id(child)])
            child_refs, child_sheets = subtree(child)
            refs += child_refs
            sheets += child_sheets
        return refs, sheets

    by_block: Dict[str, List[Tuple[str, List[str], List[str]]]] = {}

    def collect(node: dict) -> None:
        refs, sheets = subtree(node)
        by_block.setdefault(node.get("name", ""), []).append(
            (sheet_of[id(node)], refs, sheets)
        )
        for child in node.get("subcircuits") or []:
            collect(child)

    collect(data)

    result: Dict[str, Dict[str, str]] = {}
    for instances in by_block.values():
        first_sheet, first_refs, first_sheets = instances[0]
        for sheet, refs, sheets in instances:
            mapping = dict(zip(first_refs, refs))
            mapping.update(zip(first_sheets, sheets))
            mapping[first_sheet] = sheet
            result[sheet] = mapping
    return result


def block_renames(
    source_json: Path, source_sheet: str, target_json: Path, target_sheet: str
) -> Dict[str, str]:
    """Map one block's references from one circuit onto the same block in another.

    A block agent lays its sheet out in a project containing only that block, so
    its references start at 1: ``R1``, ``U1``, ``C1``. The same block in the
    finished board is somewhere in the middle of the numbering - ``R12``,
    ``U4``, ``C19`` - and shifts again whenever a part is added anywhere before
    it. A layout written against the preview would have to be re-tabulated by
    hand every time, which is exactly the maintenance nobody does.

    The mapping is positional, for the same reason :func:`instance_renames` is:
    the same block builds its components in the same order every time, so
    position identifies the same part in both circuits.

    Args:
        source_json: The circuit the layout was written against, usually a
            standalone preview.
        source_sheet: The block's sheet name in that circuit.
        target_json: The circuit the layout is to be applied to.
        target_sheet: The block's sheet name there.

    Returns:
        Source reference to target reference, plus the sheet name itself so a
        spec that places a child sheet symbol is renamed with it.

    Raises:
        ValueError: If either sheet is missing, or the two hold different
            numbers of components - which means they are not the same block,
            and a positional mapping would silently pair up the wrong parts.
    """
    source = _sheet_components(source_json)
    target = _sheet_components(target_json)

    for name, table in ((source_sheet, source), (target_sheet, target)):
        if name not in table:
            raise ValueError(
                f"no sheet {name!r}; that circuit has {sorted(table)}"
            )

    from_refs, to_refs = source[source_sheet], target[target_sheet]
    if len(from_refs) != len(to_refs):
        raise ValueError(
            f"{source_sheet} has {len(from_refs)} component(s) and "
            f"{target_sheet} has {len(to_refs)}; these are not the same block, "
            f"so matching them by position would pair up the wrong parts"
        )

    mapping = dict(zip(from_refs, to_refs))
    mapping[source_sheet] = target_sheet
    return mapping


def _sheet_components(circuit_json: Path) -> Dict[str, List[str]]:
    """Collect each sheet's component references, in creation order.

    Args:
        circuit_json: The generated circuit JSON.

    Returns:
        Sheet name to its references.
    """
    data = json.loads(Path(circuit_json).read_text(encoding="utf-8"))
    seen: Dict[str, int] = {}
    result: Dict[str, List[str]] = {}

    def walk(node: dict) -> None:
        name = node.get("name", "")
        seen[name] = seen.get(name, 0) + 1
        sheet = name if seen[name] == 1 else f"{name}{seen[name]}"
        result[sheet] = list((node.get("components") or {}).keys())
        for child in node.get("subcircuits") or []:
            walk(child)

    walk(data)
    return result


def sheet_ports(circuit_json: Path) -> Dict[str, Dict[str, str]]:
    """Read the declared hierarchical ports of each block from a circuit JSON.

    Args:
        circuit_json: The generated circuit JSON.

    Returns:
        Sheet name to a mapping of port name to direction.
    """
    data = json.loads(circuit_json.read_text(encoding="utf-8"))
    result: Dict[str, Dict[str, str]] = {}

    def walk(node: dict) -> None:
        name = node.get("name", "")
        candidate = name
        suffix = 2
        while candidate in result:
            candidate = f"{name}{suffix}"
            suffix += 1
        result[candidate] = {
            port["name"]: port["direction"] for port in (node.get("ports") or [])
        }
        for child in node.get("subcircuits") or []:
            walk(child)

    walk(data)
    return result
