"""A circuit on a sheet gets a box, a title and the reason it is correct.

A sheet holding several circuits reads as one undifferentiated mess without
them, and a schematic that does not say why its values were chosen cannot be
reviewed without the datasheets open beside it. The conventions checked here
are the ones measured out of the OpenBeam project - see OPENBEAM_STYLE.md.

Also checked: that a layout written for one instance of a repeated block can
be applied to the others without a reference table maintained by hand, since
those tables go stale the moment a part is added anywhere earlier.
"""

import json
from pathlib import Path

import pytest

from circuit_synth.kicad.layout.extract import instance_renames
from circuit_synth.kicad.layout.spec import (
    GROUP_STROKE,
    GROUP_TITLE_SIZE,
    GroupPlacement,
    PlacementSpec,
    _group_sexp,
    apply_placement,
)

GROUP = GroupPlacement(
    title="12MHZ CRYSTAL",
    at=(50.8, 76.2),
    size=(101.6, 63.5),
    rationale="Two 15pF loads and a 1k series resistor.\nCopied from RP-008279-DS s2.3.",
)

SHEET = """(kicad_sch
\t(version 20250114)
\t(generator "circuit_synth")
\t(uuid "00000000-0000-0000-0000-000000000001")
\t(paper "A4")
\t(lib_symbols)
)
"""


def test_the_box_is_a_rounded_rectangle():
    """KiCad rectangles carry a radius, so the box is one rather than four lines."""
    written = _group_sexp(GROUP)

    assert "(rectangle" in written
    assert "(start 50.8 76.2)" in written
    assert "(end 152.4 139.7)" in written
    assert f"(radius {GROUP.radius:g})" in written
    assert f"(width {GROUP_STROKE:g})" in written


def test_the_title_sits_above_the_box_and_centred():
    """A title inside the box would take space the circuit needs."""
    written = _group_sexp(GROUP)

    assert '(text "12MHZ CRYSTAL"' in written
    # Centred on the box in x, above its top edge in y.
    assert "(at 101.6 73.152 0)" in written
    assert f"(size {GROUP_TITLE_SIZE:g} {GROUP_TITLE_SIZE:g})" in written
    assert "(bold yes)" in written


def test_the_rationale_is_written_inside_the_box():
    """The reason lives on the sheet, not only in the commit message."""
    written = _group_sexp(GROUP)

    assert "Copied from RP-008279-DS s2.3." in written
    # Anchored inside the left edge, above the bottom edge.
    assert "(at 54.61 " in written


def test_a_multiline_rationale_keeps_its_newlines_escaped():
    """A raw newline inside a string would not survive as an s-expression."""
    written = _group_sexp(GROUP)

    assert "resistor.\\nCopied" in written


def test_a_radius_too_large_for_the_box_is_rejected():
    """A radius wider than the box would draw a shape KiCad cannot make."""
    with pytest.raises(ValueError, match="12MHZ"):
        _group_sexp(GroupPlacement("12MHZ", (0.0, 0.0), (10.0, 10.0), radius=8.0))


def test_applying_twice_does_not_stack_the_boxes(tmp_path: Path):
    """Re-running the styler replaces its own drawing rather than adding to it."""
    sheet = tmp_path / "Sheet.kicad_sch"
    sheet.write_text(SHEET, encoding="utf-8")
    spec = PlacementSpec(groups=[GROUP])

    apply_placement(sheet, spec)
    once = sheet.read_text(encoding="utf-8")
    apply_placement(sheet, spec)
    twice = sheet.read_text(encoding="utf-8")

    assert once.count("(rectangle") == 1
    assert twice.count("(rectangle") == 1
    assert twice.count('(text "12MHZ CRYSTAL"') == 1


def circuit(tmp_path: Path) -> Path:
    """Write a circuit JSON with one block instantiated twice.

    Args:
        tmp_path: A temporary directory.

    Returns:
        Path to the JSON file.
    """
    data = {
        "name": "Root",
        "components": {"J1": {}},
        "subcircuits": [
            {
                "name": "Leg",
                "components": {"R1": {}, "C1": {}},
                "subcircuits": [{"name": "Sense", "components": {"U1": {}}}],
            },
            {
                "name": "Leg",
                "components": {"R5": {}, "C4": {}},
                "subcircuits": [{"name": "Sense", "components": {"U2": {}}}],
            },
        ],
    }
    path = tmp_path / "Root.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_a_repeated_block_maps_onto_its_other_instances(tmp_path: Path):
    """Position in creation order identifies the same part in each instance."""
    renames = instance_renames(circuit(tmp_path))

    assert renames["Leg2"]["R1"] == "R5"
    assert renames["Leg2"]["C1"] == "C4"


def test_the_mapping_reaches_into_nested_blocks(tmp_path: Path):
    """A block's own child sheets are renamed with it, or its layout breaks."""
    renames = instance_renames(circuit(tmp_path))

    assert renames["Leg2"]["U1"] == "U2"
    assert renames["Leg2"]["Sense"] == "Sense2"
    assert renames["Leg2"]["Leg"] == "Leg2"


def test_the_first_instance_maps_to_itself(tmp_path: Path):
    """Every sheet can be looked up the same way, with no special case."""
    renames = instance_renames(circuit(tmp_path))

    assert renames["Leg"]["R1"] == "R1"
    assert renames["Root"]["J1"] == "J1"
