"""A generated sheet has to be a file KiCad will open.

The failure this guards against is a quiet one. A symbol whose library
definition carries a bare flag on a property - ``MCU_RaspberryPi:RP2040`` is
the one that found it - used to be written out with its property value
unquoted, which is not a valid s-expression. KiCad refused the whole sheet, so
the page came up empty in Eeschema and every part on it was missing from the
netlist, with nothing anywhere reporting a problem.

Two things are checked here: that such a property is written back in a shape
KiCad accepts, and that project generation asks KiCad whether its sheets open
rather than assuming they do.
"""

from pathlib import Path

import pytest
import sexpdata

from circuit_synth.kicad import sch_api_compat  # noqa: F401  (installs the patch)
from circuit_synth.kicad.sheet_check import describe_unloadable, unloadable_sheets

# A property as KiCad's own libraries write it: a bare flag, then the quoted
# name, then the quoted value.
FLAGGED_PROPERTY = (
    '(property private "KLC_S4.2_DVDD" "Not a standalone power converter; '
    "internal on-chip voltage regulator for digital core supply.\" "
    "(at 0 -2.54 0) (effects (font (size 1.27 1.27)) hide))"
)

PLAIN_PROPERTY = '(property "Reference" "U" (at 0 2.54 0))'


def format_property(source: str) -> str:
    """Round-trip a property through kicad-sch-api's formatter.

    Args:
        source: The property as it appears in a library file.

    Returns:
        The property as the formatter would write it into a schematic.
    """
    formatter = pytest.importorskip("kicad_sch_api.core.formatter")
    parsed = sexpdata.loads(source)
    return formatter.ExactFormatter()._format_property(parsed, 0)


def test_bare_flag_stays_a_flag():
    """A flag ahead of the name is written back as a flag, not as the name."""
    written = format_property(FLAGGED_PROPERTY)

    assert "(property private " in written
    assert '"private"' not in written


def test_flagged_property_keeps_its_value_quoted():
    """The value keeps its quotes, which is what KiCad rejected the sheet over."""
    written = format_property(FLAGGED_PROPERTY)

    assert '"KLC_S4.2_DVDD"' in written
    assert '"Not a standalone power converter' in written
    # An unquoted value would leave these words loose in the s-expression.
    assert " Not a standalone" not in written


def test_flagged_property_reparses():
    """What the formatter writes can be read back as an s-expression."""
    reparsed = sexpdata.loads(format_property(FLAGGED_PROPERTY))

    assert str(reparsed[0]) == "property"
    assert str(reparsed[1]) == "private"
    assert reparsed[2] == "KLC_S4.2_DVDD"


def test_ordinary_property_is_unchanged():
    """A property with no flag is still written name-then-value."""
    written = format_property(PLAIN_PROPERTY)

    assert written.startswith('(property "Reference" "U"')


def test_unloadable_sheets_reports_a_broken_sheet(tmp_path: Path):
    """A sheet KiCad cannot parse is named, not passed over."""
    pytest.importorskip("circuit_synth.kicad.layout.validate")
    from circuit_synth.kicad.sheet_check import _kicad_cli

    if not _kicad_cli():
        pytest.skip("kicad-cli is not installed")

    broken = tmp_path / "Broken.kicad_sch"
    broken.write_text("(kicad_sch (version 20250114) (generator \"nonsense\"", "utf-8")

    assert unloadable_sheets(tmp_path) == [broken]
    assert "Broken.kicad_sch" in describe_unloadable([broken])


def test_unloadable_sheets_passes_a_good_sheet(tmp_path: Path):
    """An empty but well-formed sheet is not reported as broken."""
    from circuit_synth.kicad.sheet_check import _kicad_cli

    if not _kicad_cli():
        pytest.skip("kicad-cli is not installed")

    good = tmp_path / "Good.kicad_sch"
    good.write_text(
        '(kicad_sch (version 20250114) (generator "circuit_synth")\n'
        '  (uuid "00000000-0000-0000-0000-000000000001")\n'
        '  (paper "A4")\n'
        "  (lib_symbols)\n"
        "  (symbol_instances)\n"
        ")\n",
        "utf-8",
    )

    assert unloadable_sheets(tmp_path) == []
