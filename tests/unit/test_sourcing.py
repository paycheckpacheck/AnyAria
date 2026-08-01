"""Every part on the board has to be one that can actually be bought.

A schematic full of parts nobody stocks is a drawing. The rules that make it a
design - in stock, priced, Basic before Extended so there is no per-reel
loading fee - apply to a microcontroller and to a 100nF capacitor alike, and
passives are most of the bill of materials, so they are the ones that matter.

These tests use a fixed catalogue rather than the live one. What is being
checked is the policy, and a policy that depends on today's stock levels is
not testable.
"""

import pytest

from circuit_synth.manufacturing import sourcing
from circuit_synth.manufacturing.jlcpcb.kicad_plugin import JlcPart
from circuit_synth.manufacturing.sourcing import (
    NoAcceptablePart,
    SourcingPolicy,
    choose,
)


def part(lcsc, kind="Basic", price=0.01, stock=100_000, model="X") -> JlcPart:
    """Build a catalogue entry.

    Args:
        lcsc: Part number.
        kind: Basic or Extended.
        price: Unit price.
        stock: Units in stock.
        model: Manufacturer part number.

    Returns:
        The part.
    """
    return JlcPart(
        lcsc=lcsc,
        kind=kind,
        price=price,
        currency="$",
        stock=stock,
        model=model,
        package="0603",
        brand="Someone",
        description="a part",
        datasheet="",
    )


@pytest.fixture
def catalogue(monkeypatch):
    """Replace the live catalogue with one whose answers are fixed.

    Args:
        monkeypatch: pytest's patcher.

    Returns:
        A function that installs a given list of parts as the catalogue.
    """

    def install(parts):
        def fake_search(keyword, limit=50, basic_only=False, min_stock=1, region="global"):
            return [item for item in parts if (item.stock or 0) >= min_stock]

        monkeypatch.setattr(sourcing, "search", fake_search)

    return install


def test_a_basic_part_beats_a_cheaper_extended_one(catalogue):
    """The loading fee for an Extended part is not in its unit price."""
    catalogue([part("C_EXT", "Extended", price=0.001), part("C_BAS", "Basic", price=0.02)])

    assert choose("100nF 0603", "decoupling").part.lcsc == "C_BAS"


def test_the_cheapest_wins_among_equals(catalogue):
    """With nothing else to separate them, price decides."""
    catalogue([part("C_DEAR", price=0.05), part("C_CHEAP", price=0.01)])

    assert choose("100nF 0603", "decoupling").part.lcsc == "C_CHEAP"


def test_a_part_that_is_out_of_stock_is_not_offered(catalogue):
    """A part with no stock is not available, whatever the catalogue lists."""
    catalogue([part("C_EMPTY", stock=0), part("C_STOCKED", stock=50_000)])

    assert choose("100nF 0603", "decoupling").part.lcsc == "C_STOCKED"


def test_an_expensive_passive_is_refused(catalogue):
    """A resistor at a dollar is a mistake, not a design decision."""
    catalogue([part("C_GOLD", price=1.00)])

    with pytest.raises(NoAcceptablePart, match="decoupling"):
        choose("100nF 0603", "decoupling", SourcingPolicy.for_passive())


def test_the_anchor_policy_allows_an_expensive_part(catalogue):
    """The part a block exists for is worth paying for."""
    catalogue([part("C_MCU", "Extended", price=12.50, stock=5_000)])

    assert choose("RP2040", "MCU", SourcingPolicy.for_anchor()).part.lcsc == "C_MCU"


def test_extended_parts_can_be_forbidden_outright(catalogue):
    """Some boards are only worth building out of the assembler's own stock."""
    catalogue([part("C_EXT", "Extended")])

    with pytest.raises(NoAcceptablePart):
        choose("100nF", "decoupling", SourcingPolicy(allow_extended=False, min_stock=1))


def test_an_empty_catalogue_fails_loudly(catalogue):
    """Nothing found is a decision for the caller, never a silent substitution."""
    catalogue([])

    with pytest.raises(NoAcceptablePart):
        choose("unobtanium", "the impossible part")


def test_the_runners_up_are_recorded(catalogue):
    """A part choice has to be reviewable, so what lost and why is kept."""
    catalogue([part("C_A"), part("C_B", price=0.02), part("C_C", price=0.03)])

    chosen = choose("100nF 0603", "decoupling")

    assert chosen.part.lcsc == "C_A"
    assert any("C_B" in reason for reason in chosen.rejected)


def test_the_record_carries_what_a_reviewer_needs(catalogue):
    """parts.json is the evidence the board is buildable, so it is complete."""
    catalogue([part("C14663", price=0.0241, stock=100_661_525, model="CC0603KRX7R9BB104")])

    record = choose("100nF 0603 X7R 50V", "decoupling").to_dict()

    assert record["lcsc"] == "C14663"
    assert record["type"] == "Basic"
    assert record["stock"] == 100_661_525
    assert record["price"] == 0.0241
    assert record["query"] == "100nF 0603 X7R 50V"
    assert record["role"] == "decoupling"
