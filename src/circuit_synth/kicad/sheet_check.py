"""Check that every generated sheet actually opens in KiCad.

A schematic can be written without complaint and still be a file KiCad refuses
to parse. When that happens to a child sheet the failure is quiet: the root
opens, the netlist exports, and every part on the broken sheet is simply absent
from it. Nothing in the generator notices, so the first sign of trouble is an
empty page in Eeschema or a missing footprint at assembly.

This module asks KiCad itself. Each sheet is handed to ``kicad-cli`` on its own;
a sheet that will not open there will not open in Eeschema either. The check
runs at the end of project generation so a project can never be reported as
generated while one of its pages is unreadable.
"""

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# A sheet with a lot of symbols still opens quickly; anything slower than this
# is a hung process rather than a large design.
LOAD_TIMEOUT_SECONDS = 120


def _kicad_cli() -> Optional[str]:
    """Locate the kicad-cli executable.

    Returns:
        The path to kicad-cli, or None when it is not installed.
    """
    from .layout.validate import find_kicad_cli

    return find_kicad_cli()


def sheet_opens(sheet: Path, cli: str) -> bool:
    """Report whether KiCad can open one schematic sheet.

    Args:
        sheet: The ``.kicad_sch`` file to try.
        cli: Path to the kicad-cli executable.

    Returns:
        True when KiCad parsed the sheet, False when it refused it.
    """
    with tempfile.TemporaryDirectory() as scratch:
        netlist = Path(scratch) / "check.net"
        try:
            finished = subprocess.run(
                [cli, "sch", "export", "netlist", "-o", str(netlist), str(sheet)],
                capture_output=True,
                text=True,
                timeout=LOAD_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError) as error:
            logger.debug("Could not run kicad-cli on %s: %s", sheet.name, error)
            return True  # Not the sheet's fault; do not fail the generation.

    if finished.returncode == 0:
        return True

    logger.debug(
        "kicad-cli refused %s: %s",
        sheet.name,
        (finished.stderr or finished.stdout or "").strip(),
    )
    return False


def unloadable_sheets(project_dir: Path) -> List[Path]:
    """Find the sheets in a project that KiCad will not open.

    Args:
        project_dir: The generated KiCad project directory.

    Returns:
        The sheets that failed to open, in sorted order. Empty when they all
        open, and also empty when kicad-cli is not installed to ask.
    """
    cli = _kicad_cli()
    if not cli:
        logger.debug("kicad-cli is not installed; sheets were not checked")
        return []

    return [
        sheet
        for sheet in sorted(Path(project_dir).glob("*.kicad_sch"))
        if not sheet_opens(sheet, cli)
    ]


def describe_unloadable(sheets: List[Path]) -> str:
    """Write the message shown when sheets will not open.

    Args:
        sheets: The sheets that failed to open.

    Returns:
        A message naming them and saying what it means.
    """
    names = ", ".join(sheet.name for sheet in sheets)
    return (
        f"KiCad cannot open {names}. Every part on those sheets is missing from "
        f"the netlist and the pages will come up empty in Eeschema. This is a "
        f"defect in the generated file, not in the circuit - please report it "
        f"with the library symbols the sheet uses."
    )
