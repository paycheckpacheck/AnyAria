"""A hierarchical page can be laid out as well as a page of parts.

Before this, a placement could move symbols but not the sheet symbols beside
them, so the one page in a hierarchy that is nothing but blocks - the top page -
could never be tidied. Two things are checked: that a sheet symbol moves with
its pins redrawn on the right edges, and that the text box the generator writes
onto every sheet can be moved off the parts it lands on.
"""

from pathlib import Path

from circuit_synth.kicad.layout.spec import (
    NotePlacement,
    PlacementSpec,
    SheetPinPlacement,
    SheetPlacement,
    apply_placement,
)

SHEET = """(kicad_sch
\t(version 20250114)
\t(generator "circuit_synth")
\t(uuid "00000000-0000-0000-0000-000000000001")
\t(paper "A4")
\t(lib_symbols)
\t(sheet
\t\t(at 20 30)
\t\t(size 25 20)
\t\t(uuid "00000000-0000-0000-0000-000000000002")
\t\t(property "Sheetname" "Child"
\t\t\t(at 20 29 0)
\t\t)
\t\t(property "Sheetfile" "Child.kicad_sch"
\t\t\t(at 20 51 0)
\t\t)
\t\t(pin "IN" input
\t\t\t(at 20 35 180)
\t\t\t(effects
\t\t\t\t(justify left)
\t\t\t)
\t\t)
\t\t(instances
\t\t\t(project "p"
\t\t\t\t(path "/00000000-0000-0000-0000-000000000001"
\t\t\t\t\t(page "2")
\t\t\t\t)
\t\t\t)
\t\t)
\t)
\t(text_box "a note"
\t\t(at 30 40 0)
\t\t(size 20 10)
\t)
)
"""

PLACEMENT = SheetPlacement(
    name="Child",
    at=(50.8, 25.4),
    size=(38.1, 25.4),
    pins=[
        SheetPinPlacement("IN", "left", 7.62),
        SheetPinPlacement("OUT", "right", 7.62),
    ],
)


def written(tmp_path: Path, spec: PlacementSpec) -> str:
    """Apply a spec to a copy of the sample sheet and read the result.

    Args:
        tmp_path: A temporary directory.
        spec: The placement to apply.

    Returns:
        The rewritten file contents.
    """
    sheet = tmp_path / "Parent.kicad_sch"
    sheet.write_text(SHEET, encoding="utf-8")
    apply_placement(sheet, spec)
    return sheet.read_text(encoding="utf-8")


def test_sheet_symbol_moves_and_resizes(tmp_path: Path):
    """The body lands where the spec puts it, at the size it asks for."""
    text = written(tmp_path, PlacementSpec(sheets=[PLACEMENT]))

    assert "(at 50.8 25.4)" in text
    assert "(size 38.1 25.4)" in text


def test_pins_land_on_the_edge_they_were_given(tmp_path: Path):
    """A left pin sits on the left edge at angle 180, a right pin at angle 0.

    KiCad relocates a pin whose angle disagrees with its edge, which silently
    disconnects it, so the two have to be written consistently.
    """
    text = written(tmp_path, PlacementSpec(sheets=[PLACEMENT]))

    assert '(pin "IN" bidirectional' in text
    assert "(at 50.8 33.02 180)" in text
    assert '(pin "OUT" bidirectional' in text
    assert "(at 88.9 33.02 0)" in text


def test_pins_come_before_the_instance_paths(tmp_path: Path):
    """Pins go back where KiCad writes them, not appended after everything."""
    text = written(tmp_path, PlacementSpec(sheets=[PLACEMENT]))

    assert text.index('(pin "IN"') < text.index("(instances")


def test_the_sheet_name_and_file_follow_the_body(tmp_path: Path):
    """Both properties sit against the new body, not the old one's corners."""
    text = written(tmp_path, PlacementSpec(sheets=[PLACEMENT]))

    assert "(at 50.8 24.13 0)" in text  # name, just above the box
    assert "(at 50.8 52.07 0)" in text  # file, just below it


def test_an_unknown_sheet_is_an_error(tmp_path: Path):
    """Naming a sheet the page does not have fails rather than passing quietly."""
    import pytest

    spec = PlacementSpec(sheets=[SheetPlacement("Missing", (25.4, 25.4), (25.4, 25.4))])
    with pytest.raises(ValueError, match="Missing"):
        written(tmp_path, spec)


def test_a_note_moves_to_where_the_spec_puts_it(tmp_path: Path):
    """The docstring box goes where it is told, at the size it is given."""
    text = written(
        tmp_path, PlacementSpec(notes=[NotePlacement((76.2, 152.4), (101.6, 25.4))])
    )

    assert "(at 76.2 152.4 0)" in text
    assert "(size 101.6 25.4)" in text


def test_a_sheet_rename_carries_to_the_sheet_name(tmp_path: Path):
    """Reusing a block's layout for another instance finds that instance's sheet."""
    spec = PlacementSpec(sheets=[PLACEMENT]).renamed({"Child": "Child2"})

    assert spec.sheets[0].name == "Child2"
