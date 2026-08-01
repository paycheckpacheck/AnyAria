# -*- coding: utf-8 -*-
"""Choosing parts that can actually be bought and assembled.

A schematic full of parts nobody stocks is a drawing, not a design. Every part
on a board that is going to be assembled has to be orderable now, at a price
that does not make the board pointless, and preferably from the assembler's own
shelf so it does not have to be loaded specially.

That makes part choice a policy question rather than a search question, and the
policy lives here so it is applied the same way to a microcontroller and to a
100nF capacitor. Passives are the ones most often waved through, and passives
are most of the bill of materials.

The order of preference:

1. **A JLCPCB Basic part.** Already on the assembler's shelf, so no per-reel
   loading fee. Cheapest to build even when the unit price matches.
2. **A JLCPCB Extended part.** Stocked, but attracts a loading fee per distinct
   part, so it is worth a moment's thought before adding a fourth one.
3. **Somewhere else entirely.** Only when JLCPCB has nothing that does the job.
   This is a decision the person building the board needs told about, so it is
   recorded as a deviation rather than quietly substituted.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .jlcpcb.kicad_plugin import ImportedPart, JlcPart, import_part, search

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourcingPolicy:
    """What counts as an acceptable part.

    Attributes:
        min_stock: Least stock that counts as available. A few hundred is not
            availability for a board that might be built twice.
        max_unit_price: Most this part may cost, in the catalogue's currency.
            None for no ceiling, which is reasonable for the one part the board
            exists to carry and unreasonable for a resistor.
        prefer_basic: Choose a Basic part over an Extended one even when the
            Extended part is cheaper per unit, because the loading fee is not
            in the unit price.
        allow_extended: Whether Extended parts may be used at all.
        region: Which JLCPCB catalogue to search.
    """

    min_stock: int = 1000
    max_unit_price: Optional[float] = None
    prefer_basic: bool = True
    allow_extended: bool = True
    region: str = "global"

    @staticmethod
    def for_passive() -> "SourcingPolicy":
        """Policy for a resistor, capacitor or inductor.

        Returns:
            A strict policy. There is no reason to fit an unusual passive, so
            the stock floor is high and the price ceiling is low.
        """
        return SourcingPolicy(min_stock=10_000, max_unit_price=0.10)

    @staticmethod
    def for_anchor() -> "SourcingPolicy":
        """Policy for the part a block is built around.

        Returns:
            A permissive policy. The part that defines the block is worth
            paying for, and is unlikely to be Basic.
        """
        return SourcingPolicy(min_stock=100, max_unit_price=None)


@dataclass
class SourcedPart:
    """A chosen part, with everything needed to justify the choice later.

    Attributes:
        part: What the catalogue says about it.
        role: What it is for in the circuit, in a few words.
        query: The search that found it, so the choice can be repeated.
        symbol: The ``"Library:Name"`` symbol reference, once imported.
        footprint: The footprint reference, once imported.
        rejected: Parts that were considered and passed over, with the reason.
        deviation: Set when the policy could not be met, saying what was
            accepted instead and why.
    """

    part: JlcPart
    role: str
    query: str
    symbol: str = ""
    footprint: str = ""
    rejected: List[str] = field(default_factory=list)
    deviation: str = ""

    def to_dict(self) -> dict:
        """Serialize for a block's ``parts.json``.

        Returns:
            The part as plain data.
        """
        return {
            "role": self.role,
            "lcsc": self.part.lcsc,
            "type": self.part.kind,
            "mpn": self.part.model,
            "brand": self.part.brand,
            "package": self.part.package,
            "price": self.part.price,
            "currency": self.part.currency,
            "stock": self.part.stock,
            "datasheet": self.part.datasheet,
            "symbol": self.symbol,
            "footprint": self.footprint,
            "query": self.query,
            "rejected": self.rejected,
            "deviation": self.deviation,
        }


class NoAcceptablePart(RuntimeError):
    """Nothing in the catalogue met the policy."""


def choose(
    query: str, role: str, policy: Optional[SourcingPolicy] = None, limit: int = 60
) -> SourcedPart:
    """Find the best catalogue part for one role.

    Args:
        query: What to search for. Be specific - a capacitor search wants the
            value, the package, the dielectric and the voltage rating, because
            a 100nF 0402 X5R 6.3V is not a substitute for a 100nF 0603 X7R 50V.
        role: What the part is for, recorded so the choice can be reviewed.
        policy: What counts as acceptable. Defaults to the general policy.
        limit: How many candidates to consider.

    Returns:
        The chosen part, with the runners-up and the reasons they lost.

    Raises:
        NoAcceptablePart: If nothing met the policy. The caller decides whether
            to loosen the query, loosen the policy, or record a deviation -
            none of which should happen silently.
    """
    policy = policy or SourcingPolicy()
    candidates = search(
        query, limit=limit, min_stock=policy.min_stock, region=policy.region
    )

    rejected: List[str] = []
    acceptable: List[JlcPart] = []
    for candidate in candidates:
        if not candidate.is_basic and not policy.allow_extended:
            rejected.append(f"{candidate.lcsc}: Extended, and the policy forbids it")
            continue
        if policy.max_unit_price is not None and candidate.price is not None:
            if candidate.price > policy.max_unit_price:
                rejected.append(
                    f"{candidate.lcsc}: {candidate.currency}{candidate.price} is over "
                    f"the {policy.max_unit_price} ceiling"
                )
                continue
        acceptable.append(candidate)

    if not acceptable:
        raise NoAcceptablePart(
            f"nothing for {role!r} (searched {query!r}, stock >= {policy.min_stock}). "
            f"Considered {len(candidates)}; {len(rejected)} failed on price or type."
        )

    def rank(candidate: JlcPart) -> tuple:
        """Order candidates: Basic first if preferred, then price, then stock."""
        basic_first = 0 if (policy.prefer_basic and candidate.is_basic) else 1
        price = candidate.price if candidate.price is not None else float("inf")
        return (basic_first, price, -(candidate.stock or 0))

    acceptable.sort(key=rank)
    chosen = acceptable[0]

    for runner_up in acceptable[1:4]:
        rejected.append(
            f"{runner_up.lcsc}: {runner_up.kind}, "
            f"{runner_up.currency}{runner_up.price}, not the best on the policy"
        )

    logger.info(
        "Chose %s (%s, %s%s, stock %s) for %s",
        chosen.lcsc,
        chosen.kind,
        chosen.currency,
        chosen.price,
        chosen.stock,
        role,
    )
    return SourcedPart(part=chosen, role=role, query=query, rejected=rejected)


def source_and_import(
    query: str,
    role: str,
    project_dir: Path,
    policy: Optional[SourcingPolicy] = None,
    library_name: str = "JLCImport",
) -> SourcedPart:
    """Choose a part and write its symbol and footprint into the project.

    Args:
        query: What to search for.
        role: What the part is for.
        project_dir: The KiCad project directory to import into.
        policy: What counts as acceptable.
        library_name: Library to import into.

    Returns:
        The chosen part, with ``symbol`` and ``footprint`` filled in ready for
        ``Component``.

    Raises:
        NoAcceptablePart: If nothing met the policy.
        ValueError: If the import itself failed.
    """
    sourced = choose(query, role, policy)
    imported: ImportedPart = import_part(
        sourced.part.lcsc, project_dir, library_name=library_name
    )
    sourced.symbol = imported.symbol
    sourced.footprint = imported.footprint
    return sourced
