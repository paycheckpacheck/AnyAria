"""A generated project has to be something a simulator will load.

The failure this guards against was reported from KiCad's simulator, and it
took the whole deck down::

    warning, can't find model '220uf/50v' from line c8 /vmotor gnd 220uf/50v
    Error: bad syntax of line f1 __f1
    No circuit loaded!

Two separate causes. A value written the way an engineer wants to read it is
not a value ngspice can parse, so the part is dropped. And a fuse is ``F1``,
which SPICE reads as a current-controlled current source; that one is a syntax
error, and a syntax error stops the deck being read at all.
"""

from pathlib import Path

import pytest

from circuit_synth.kicad.spice_hygiene import (
    _classify,
    deck_problems,
    make_spice_clean,
    spice_value,
)

SHEET = """(kicad_sch
\t(version 20250114)
\t(generator "circuit_synth")
\t(uuid "00000000-0000-0000-0000-000000000001")
\t(paper "A4")
\t(lib_symbols)
\t(symbol
\t\t(lib_id "Device:C")
\t\t(at 50.8 50.8 0)
\t\t(exclude_from_sim no)
\t\t(unit 1)
\t\t(uuid "00000000-0000-0000-0000-000000000002")
\t\t(property "Reference" "C2"
\t\t\t(at 50.8 45.72 0)
\t\t)
\t\t(property "Value" "220uF/50V"
\t\t\t(at 50.8 55.88 0)
\t\t)
\t)
\t(symbol
\t\t(lib_id "Device:Fuse")
\t\t(at 76.2 50.8 0)
\t\t(exclude_from_sim no)
\t\t(unit 1)
\t\t(uuid "00000000-0000-0000-0000-000000000003")
\t\t(property "Reference" "F1"
\t\t\t(at 76.2 45.72 0)
\t\t)
\t\t(property "Value" "10A"
\t\t\t(at 76.2 55.88 0)
\t\t)
\t)
)
"""


@pytest.mark.parametrize(
    "written,expected",
    [
        ("100nF", "100n"),
        ("220uF/50V", "220u"),  # the qualifier belongs to the part, not the model
        ("1uF/25V", "1u"),
        ("10R", "10"),
        ("5.1k", "5.1k"),
        ("22u", "22u"),
        ("4k7", "4.7k"),  # the multiplier standing in for the decimal point
        ("1R5", "1.5"),
        ("5mR", "5m"),
    ],
)
def test_values_an_engineer_writes_become_values_spice_reads(written, expected):
    """Each of these reaches ngspice as a model name today, and is dropped."""
    assert spice_value(written) == expected


def test_a_megohm_does_not_become_a_milliohm():
    """SPICE reads M as milli, so a megohm has to be spelled out.

    Getting this wrong is a factor of a billion, and it looks right.
    """
    assert spice_value("1M") == "1Meg"


@pytest.mark.parametrize("written", ["IRF3205", "12MHz", "BAT54", "", "USB_C"])
def test_a_part_number_is_not_a_value(written):
    """A part number describes a device; it does not size one."""
    assert spice_value(written) is None


def test_a_passive_with_a_number_gets_a_model():
    """A capacitor is entirely described by one number, so it can be simulated."""
    device, value, _ = _classify("C2", "220uF/50V")

    assert device == "C"
    assert value == "220u"


def test_a_fuse_is_excluded_rather_than_modelled():
    """F is a controlled source in SPICE, and a fuse is not one."""
    device, _, reason = _classify("F1", "10A")

    assert device is None
    assert "F part" in reason


def test_a_connector_is_excluded():
    """J is a JFET in SPICE, and a connector has no small-signal behaviour."""
    device, _, _ = _classify("J1", "USB_C")

    assert device is None


def test_the_pass_models_what_it_can_and_excludes_the_rest(tmp_path: Path):
    """One sheet, one capacitor, one fuse: one of each outcome."""
    sheet = tmp_path / "Power.kicad_sch"
    sheet.write_text(SHEET, encoding="utf-8")

    report = make_spice_clean(tmp_path)
    written = sheet.read_text(encoding="utf-8")

    assert report.modelled == {"C2": "220u"}
    assert "F1" in report.excluded
    assert '(property "Sim.Device" "C"' in written
    assert '(property "Sim.Params" "c=220u"' in written
    assert written.count("(exclude_from_sim yes)") == 1


def test_the_human_readable_value_is_left_alone(tmp_path: Path):
    """220uF/50V is what belongs on the sheet; the model goes beside it."""
    sheet = tmp_path / "Power.kicad_sch"
    sheet.write_text(SHEET, encoding="utf-8")

    make_spice_clean(tmp_path)

    assert '(property "Value" "220uF/50V"' in sheet.read_text(encoding="utf-8")


def test_a_deck_with_a_nodeless_device_is_reported():
    """This is the line that took the reported crash down."""
    problems = deck_problems(".title x\nF1 __F1\nC3 VBUS GND 10u\n")

    assert len(problems) == 1
    assert "F1 __F1" in problems[0]


def test_a_deck_with_an_unparseable_value_is_reported():
    """The other half of the crash: the value ngspice reads as a model name."""
    problems = deck_problems(".title x\nC2 /VMOTOR GND 220uF/50V\n")

    assert len(problems) == 1
    assert "220uF/50V" in problems[0]


def test_a_clean_deck_has_no_problems():
    """Directives and comments are not devices and must not be flagged."""
    deck = ".title x\n.tran 1u 1m\n* a comment\nC3 VBUS GND 10u\nR1 A B 4.7k\n"

    assert deck_problems(deck) == []
