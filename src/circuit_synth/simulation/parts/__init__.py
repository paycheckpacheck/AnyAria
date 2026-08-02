# -*- coding: utf-8 -*-
"""Device models for specific parts, each checked against its datasheet.

A model in here is not just code that runs. It carries the published values it
has to reproduce, and ``check()`` says how close it gets - so a model that has
drifted, or was wrong from the start, says so rather than being believed.

This module is also the way in. A block simulator holding a part number needs
to know whether somebody has already built and checked a model for it, and
building a second one by hand when a validated one exists is how two different
answers for the same part get into one design.

    >>> from circuit_synth.simulation.parts import find
    >>> match = find("TPS7A4901DGNR")
    >>> match.model.module.predict_dropout(0.150)   # doctest: +SKIP
    0.3384...

Matching is by family prefix, because a real order code carries a package and a
reel suffix the model knows nothing about. That is useful and it is also the
way this gets a wrong answer, so a match says whether it is the exact device
the model was validated against - see :attr:`Match.exact`. A family match is a
starting point, not a citation.
"""

import logging
from dataclasses import dataclass, field
from types import ModuleType
from typing import Callable, Dict, List, Optional, Tuple

from ..validation import ValidationReport
from . import irf3205, tl072, tps7a49, tps62130

logger = logging.getLogger(__name__)

__all__ = [
    "PartModel",
    "Match",
    "REGISTRY",
    "find",
    "check_all",
    "catalogue",
]


@dataclass(frozen=True)
class PartModel:
    """A behavioural model of one part, and what is known about its accuracy.

    Attributes:
        prefix: The family prefix an order code is matched against, uppercase
            and without punctuation.
        validated_part: The exact device ``check`` was run against. A part that
            shares the prefix but not this string is a family match, and the
            model's conditions have to be read before it is trusted.
        document: The datasheet the model was built from, with its revision
            where the module records one.
        summary: What the model predicts, in one line.
        module: The module itself, for everything the registry does not wrap.
        check: Runs the model against every published value.
        gaps: What the model does not represent.
        fitted: True when any coefficient was fitted rather than published.
            Worth surfacing: a fitted model is only as good as the condition it
            was validated at.
        exact_prefixes: Order-code prefixes that are the validated device
            despite not starting with ``validated_part``. Needed where a single
            letter changes the package rather than the reel: IRF3205S is the
            IRF3205 die in a D2PAK, so it shares every electrical number and
            not the thermal ones - which for that model is the whole subject.
            Empty means ``validated_part`` is the only exact match.
    """

    prefix: str
    validated_part: str
    document: str
    summary: str
    module: ModuleType
    check: Callable[[], ValidationReport]
    gaps: Callable[[], List[str]]
    fitted: bool = False
    exact_prefixes: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Match:
    """The result of looking a part number up.

    Attributes:
        model: The model found.
        exact: True when the requested part is the device the model was
            validated against, rather than another member of its family.
        requested: The part number as asked for.
    """

    model: PartModel
    exact: bool
    requested: str

    def caveat(self) -> Optional[str]:
        """What has to be said about this match when it is used.

        Returns:
            The caveat, or None when the match is exact.
        """
        if self.exact:
            return None
        return (
            f"{self.requested} is not {self.model.validated_part}, which is the "
            f"device this model was checked against. They share a family, so "
            f"the mechanisms are the same and the numbers may not be. Read "
            f"{self.model.document} for the requested part and confirm every "
            f"value the model uses before citing a result."
        )


def _normalise(part_number: str) -> str:
    """Reduce an order code to something comparable.

    Args:
        part_number: An MPN, order code or catalogue description.

    Returns:
        Uppercase alphanumerics only.
    """
    return "".join(char for char in part_number.upper() if char.isalnum())


REGISTRY: Dict[str, PartModel] = {
    "TPS7A49": PartModel(
        prefix="TPS7A49",
        validated_part="TPS7A4901",
        document="SBVS121E",
        summary="low-noise LDO: rejection against frequency, dropout against "
        "load, and integrated output noise",
        module=tps7a49,
        check=tps7a49.check,
        gaps=tps7a49.gaps,
    ),
    "TL072": PartModel(
        prefix="TL072",
        validated_part="TL072H",
        document="SLOS080AA",
        summary="JFET-input op-amp: small-signal and slew-limited step "
        "response, and settling to a given band",
        module=tl072,
        check=tl072.check,
        gaps=tl072.gaps,
    ),
    "IRF3205": PartModel(
        prefix="IRF3205",
        validated_part="IRF3205",
        document="PD-94791B",
        summary="55V power MOSFET: on-resistance against junction "
        "temperature, and the junction temperature a current settles at",
        module=irf3205,
        check=irf3205.check,
        gaps=irf3205.gaps,
        # IRF3205PbF is the same TO-220 part, lead-free. IRF3205S and IRF3205L
        # are the same die in D2PAK and TO-262, and are deliberately left out:
        # this model's subject is the thermal path, and that is precisely what
        # the package changes.
        exact_prefixes=("IRF3205P",),
    ),
    # The family prefix is deliberately one digit short of the validated part:
    # TPS62130/1/2/3 are the same silicon with different feedback arrangements,
    # so the mechanisms carry across and the numbers have to be re-read. A
    # TPS62133 therefore matches, inexactly, with the caveat that says so.
    "TPS6213": PartModel(
        prefix="TPS6213",
        validated_part="TPS62130",
        document="SLVSAG7F",
        summary="3A synchronous buck: efficiency against load and switching "
        "frequency, and where continuous conduction ends",
        module=tps62130,
        check=tps62130.check,
        gaps=tps62130.gaps,
        fitted=True,
    ),
}


def find(part_number: str) -> Optional[Match]:
    """Look for a checked model for a part.

    Args:
        part_number: An MPN or order code. Package and reel suffixes are
            ignored, so ``TPS7A4901DGNR`` finds the TPS7A49 model.

    Returns:
        The match, or None when nothing in the registry covers the part.
    """
    wanted = _normalise(part_number)
    if not wanted:
        return None

    # Longest prefix wins, so a model for a specific device beats one for its
    # family if both are ever registered.
    candidates = [
        model
        for model in REGISTRY.values()
        if wanted.startswith(_normalise(model.prefix))
    ]
    if not candidates:
        logger.debug("no checked model for %s", part_number)
        return None

    model = max(candidates, key=lambda item: len(_normalise(item.prefix)))
    if model.exact_prefixes:
        # Prefix matching cannot say "this code and these suffixes but not that
        # one", so where a letter changes the package the bare part number has
        # to match outright and every acceptable suffix be named.
        exact = wanted == _normalise(model.validated_part) or any(
            wanted.startswith(_normalise(item)) for item in model.exact_prefixes
        )
    else:
        exact = wanted.startswith(_normalise(model.validated_part))
    if not exact:
        logger.info(
            "%s matched the %s model by family, not exactly",
            part_number,
            model.validated_part,
        )
    return Match(model=model, exact=exact, requested=part_number)


def check_all() -> Dict[str, ValidationReport]:
    """Run every registered model against its datasheet.

    This is what stops a model rotting quietly. A model is a claim about a real
    part, and a claim nobody re-checks is a claim that was true once.

    Returns:
        One report per registered part, keyed by prefix.
    """
    reports: Dict[str, ValidationReport] = {}
    for prefix, model in REGISTRY.items():
        report = model.check()
        reports[prefix] = report
        if not report.passed:
            logger.warning("%s no longer matches %s", prefix, model.document)
    return reports


def catalogue() -> str:
    """Describe every checked model, for an agent deciding whether to build one.

    Returns:
        One block per part: what it predicts, how well it was last checked, how
        much of that check was out of sample, and what it does not cover.
    """
    lines: List[str] = []
    for prefix, model in sorted(REGISTRY.items()):
        report = model.check()
        out_of_sample = len(report.out_of_sample)
        worst = report.worst
        accuracy = (
            f"worst {worst.error * 100:.1f}% on {worst.point.quantity} "
            f"against a claimed {worst.point.tolerance * 100:.0f}%"
            if worst
            else "no comparisons"
        )
        lines.append(f"{model.validated_part} ({model.document})")
        lines.append(f"  predicts   {model.summary}")
        lines.append(
            f"  checked    {'matches' if report.passed else 'DOES NOT MATCH'}, "
            f"{accuracy}, {out_of_sample} of {len(report.comparisons)} point(s) "
            f"out of sample"
        )
        if model.fitted:
            lines.append(
                "  fitted     one coefficient was fitted, not published - "
                "check the condition it was validated at"
            )
        for gap in model.gaps():
            lines.append(f"  gap        {gap}")
        lines.append("")
    return "\n".join(lines).rstrip()
