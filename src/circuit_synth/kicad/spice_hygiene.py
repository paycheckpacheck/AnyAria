# -*- coding: utf-8 -*-
"""Make a generated project something ngspice will load.

KiCad builds its SPICE deck from the schematic by taking each symbol's
reference prefix as the device letter and its Value as the device's parameter.
That works for a resistor marked ``10k`` and fails in two ways that between
them stop the deck loading at all:

* **A value that is not a number.** ``220uF/50V`` is what an engineer wants to
  read on the sheet, and ngspice reads it as the name of a model that does not
  exist: ``can't find model '220uf/50v'``. The part is dropped.
* **A part whose prefix means something in SPICE.** A fuse is ``F1``, and ``F``
  is a current-controlled current source, which needs two nodes and a
  controlling source. ``F1 __F1`` is a syntax error, and a syntax error stops
  the whole deck: ``No circuit loaded!``. The same applies to connectors, which
  come out as ``J``, a JFET.

So every symbol gets one of two treatments. Anything with a value SPICE can use
gets an explicit simulation model built from that value, with the human-readable
value left alone on the sheet. Everything else is excluded from simulation, which
is honest: a fuse has no small-signal behaviour, and a part with no model
contributes nothing but an error.

Excluding a part is not the same as pretending it is not there. What was
excluded, and why, is reported, so a block that needs a behavioural model for
its main part finds out rather than quietly simulating without it.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .layout import sexp

logger = logging.getLogger(__name__)

# Reference prefix to SPICE device, for the parts whose behaviour is entirely
# described by one number.
PASSIVE_DEVICES = {"R": "R", "C": "C", "L": "L"}

# SPICE reads M as milli, so a megohm written the way an engineer writes it
# needs spelling out or it comes out a billion times too small.
SI_SUFFIXES = {
    "p": "p",
    "n": "n",
    "u": "u",
    "µ": "u",
    "m": "m",
    "k": "k",
    "K": "k",
    "M": "Meg",
    "G": "G",
    "meg": "Meg",
}

_VALUE = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*(p|n|u|µ|m|k|K|M|G|meg|Meg|MEG)?\s*"
    r"(?:[FfHhΩR]|ohm|Ohm|OHM)?\s*$"
)

# A value written with the multiplier standing in for the decimal point:
# 4k7, 1R5, 2u2.
_EMBEDDED = re.compile(r"^\s*(\d+)(p|n|u|µ|m|k|K|M|G|R|r)(\d+)\s*$")


def spice_value(value: str) -> Optional[str]:
    """Convert a component value into something SPICE can read.

    Args:
        value: The value as written on the schematic, such as ``"220uF/50V"``,
            ``"4k7"`` or ``"10R"``.

    Returns:
        The value as SPICE wants it, such as ``"220u"``, ``"4.7k"`` or
        ``"10"``. None when the value is not a number at all - a part number
        like ``"IRF3205"``, or a frequency like ``"12MHz"``, which describes a
        crystal rather than sizing one.
    """
    if not value:
        return None

    # A voltage or tolerance qualifier belongs to the part, not to the model.
    head = value.split("/")[0].split()[0] if value.split() else value

    embedded = _EMBEDDED.match(head)
    if embedded:
        whole, suffix, fraction = embedded.groups()
        multiplier = SI_SUFFIXES.get(suffix, "")
        if suffix in ("R", "r"):
            multiplier = ""
        return f"{whole}.{fraction}{multiplier}"

    match = _VALUE.match(head)
    if not match:
        return None

    number, suffix = match.groups()
    return f"{number}{SI_SUFFIXES.get(suffix, '') if suffix else ''}"


@dataclass
class SpiceHygieneReport:
    """What was done to a project to make its deck load.

    Attributes:
        modelled: ``reference -> spice value`` for the parts given a model.
        excluded: ``reference -> why`` for the parts taken out of the
            simulation. A part here is not simulated; if the block's behaviour
            depends on it, it needs a behavioural model.
        sheets: How many sheets were rewritten.
    """

    modelled: Dict[str, str] = field(default_factory=dict)
    excluded: Dict[str, str] = field(default_factory=dict)
    sheets: int = 0

    def summary(self) -> str:
        """Describe the outcome in one line.

        Returns:
            A one-line summary.
        """
        return (
            f"{len(self.modelled)} part(s) modelled, "
            f"{len(self.excluded)} excluded, across {self.sheets} sheet(s)"
        )


def _classify(reference: str, value: str) -> Tuple[Optional[str], Optional[str], str]:
    """Decide what to do with one symbol.

    Args:
        reference: Its reference designator.
        value: Its value field.

    Returns:
        A ``(device, spice_value, reason)`` triple. ``device`` and
        ``spice_value`` are None when the part should be excluded, and
        ``reason`` then says why.
    """
    prefix = re.match(r"^([A-Za-z]+)", reference)
    letter = (prefix.group(1) if prefix else "").upper()

    if letter.startswith("#"):  # power symbols never reach here
        return None, None, "power symbol"

    device = PASSIVE_DEVICES.get(letter)
    if device is None:
        return None, None, f"no SPICE model for a {letter or '?'} part ({value})"

    converted = spice_value(value)
    if converted is None:
        return None, None, f"value {value!r} is not a number SPICE can use"

    return device, converted, ""


def _set_property(block: str, name: str, value: str) -> str:
    """Set a property on a symbol block, adding it when it is absent.

    Args:
        block: The symbol block text.
        name: Property name.
        value: Property value.

    Returns:
        The updated block.
    """
    pattern = re.compile(rf'(\(property\s+"{re.escape(name)}"\s+)"[^"]*"')
    if pattern.search(block):
        return pattern.sub(rf'\g<1>"{value}"', block, count=1)

    # Add it next to the last existing property, so it lands inside the symbol.
    last = None
    for match in re.finditer(r"\n(\t+)\(property\s", block):
        last = match
    if last is None:
        return block

    indent = last.group(1)
    start = last.start() + 1
    _, end = sexp.find_block(block, start + len(indent))
    addition = (
        f'\n{indent}(property "{name}" "{value}"'
        f"\n{indent}\t(at 0 0 0)"
        f"\n{indent}\t(effects\n{indent}\t\t(font\n{indent}\t\t\t(size 1.27 1.27)"
        f"\n{indent}\t\t)\n{indent}\t\t(hide yes)\n{indent}\t)\n{indent})"
    )
    return block[:end] + addition + block[end:]


def _exclude(block: str) -> str:
    """Mark a symbol as taking no part in simulation.

    Args:
        block: The symbol block text.

    Returns:
        The updated block.
    """
    if "(exclude_from_sim " in block:
        return re.sub(r"\(exclude_from_sim\s+\w+\)", "(exclude_from_sim yes)", block, count=1)
    return block.replace("(unit ", "(exclude_from_sim yes)\n\t\t(unit ", 1)


def make_spice_clean(project_dir: Path) -> SpiceHygieneReport:
    """Give every symbol in a project a model or an exemption.

    Args:
        project_dir: The KiCad project directory.

    Returns:
        What was modelled and what was excluded.
    """
    report = SpiceHygieneReport()

    for sheet in sorted(Path(project_dir).glob("*.kicad_sch")):
        text = sheet.read_text(encoding="utf-8")
        changed = False

        # Back to front, so the offsets in front of each edit stay valid.
        for extent in sorted(sexp.iter_blocks(text, "symbol"), reverse=True):
            block = sexp.block_text(text, extent)
            lib_id = sexp.read_string(block, "lib_id") or ""
            reference = sexp.read_property(block, "Reference") or ""
            if not reference or lib_id.startswith("power:"):
                continue

            value = sexp.read_property(block, "Value") or ""
            device, converted, reason = _classify(reference, value)

            if device is None:
                updated = _exclude(block)
                report.excluded[reference] = reason
            else:
                updated = _set_property(block, "Sim.Device", device)
                updated = _set_property(
                    updated, "Sim.Params", f"{device.lower()}={converted}"
                )
                updated = re.sub(
                    r"\(exclude_from_sim\s+\w+\)", "(exclude_from_sim no)", updated, count=1
                )
                report.modelled[reference] = converted

            text = text[: extent[0]] + updated + text[extent[1] :]
            changed = True

        if changed:
            sheet.write_text(text, encoding="utf-8")
            report.sheets += 1

    logger.info("SPICE hygiene: %s", report.summary())
    return report


def deck_problems(deck: str) -> List[str]:
    """Find the lines of a SPICE deck ngspice would refuse.

    KiCad bundles ngspice as a library rather than as a program, so on a normal
    install there is nothing to run the deck through. This reproduces the two
    checks that matter without needing the binary: an element needs nodes, and
    a passive needs a number.

    Args:
        deck: The exported deck.

    Returns:
        One message per bad line, empty when the deck is well formed.
    """
    problems: List[str] = []

    for number, line in enumerate(deck.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith((".", "*", "+")):
            continue

        fields = stripped.split()
        name = fields[0]

        # "F1 __F1" - a device with a placeholder where its nodes should be.
        if len(fields) < 3 or any(field.startswith("__") for field in fields[1:]):
            problems.append(
                f"line {number}: {stripped!r} has no nodes, so ngspice stops "
                f"reading the deck here"
            )
            continue

        if name[:1].upper() in PASSIVE_DEVICES:
            value = fields[3] if len(fields) > 3 else ""
            if value and not _is_spice_number(value):
                problems.append(
                    f"line {number}: {value!r} is not a value ngspice can read, "
                    f"so {name} is dropped"
                )

    return problems


def _is_spice_number(token: str) -> bool:
    """Report whether a deck token is a number ngspice will accept.

    Deliberately stricter than :func:`spice_value`, which exists to *convert* a
    schematic value and so forgives things a deck cannot. ``220uF/50V``
    converts to ``220u`` happily; written into a deck it is read as the name of
    a model, and the part is silently dropped. ngspice does ignore trailing
    letters after a scale factor, so ``10uF`` is fine and only the qualifier
    is fatal.

    Args:
        token: The value field as it appears in the deck.

    Returns:
        True when ngspice would read it as a number.
    """
    return bool(re.match(r"^[+-]?(\d+\.?\d*|\.\d+)([A-Za-z]*)$", token))


def deck_loads(root_schematic: Path, work_dir: Optional[Path] = None) -> Tuple[bool, str]:
    """Export the project's SPICE deck and check ngspice will load it.

    Args:
        root_schematic: The project's root ``.kicad_sch``.
        work_dir: Where to write the deck. Defaults to the project directory.

    Returns:
        A ``(loaded, detail)`` pair. ``detail`` carries the first error when it
        did not load, and is empty when it did. Returns ``(True, "")`` when
        neither tool is installed, since an absent tool is not a defect in the
        schematic.
    """
    import shutil
    import subprocess

    from .layout.validate import find_kicad_cli

    cli = find_kicad_cli()
    if cli is None:
        return True, ""

    deck = (work_dir or root_schematic.parent) / "spice_check.cir"
    export = subprocess.run(
        [cli, "sch", "export", "netlist", "--format", "spice", "-o", str(deck),
         str(root_schematic)],
        capture_output=True, text=True, timeout=900, check=False,
    )
    if not deck.exists():
        return False, f"the deck would not export: {export.stderr[-300:]}"

    # Read the deck before running anything: this catches the failures we know
    # about even where ngspice is only present as a library.
    static = deck_problems(deck.read_text(encoding="utf-8"))
    if static:
        return False, static[0]

    ngspice = shutil.which("ngspice")
    if ngspice is None:
        return True, ""

    run = subprocess.run(
        [ngspice, "-b", "-n", str(deck)],
        capture_output=True, text=True, timeout=900, check=False,
    )
    output = (run.stdout or "") + (run.stderr or "")
    for marker in ("No circuit loaded", "bad syntax", "Error:"):
        if marker in output:
            line = next(
                (item for item in output.splitlines() if marker in item), marker
            )
            return False, line.strip()
    return True, ""
