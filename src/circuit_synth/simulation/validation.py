# -*- coding: utf-8 -*-
"""Checking a model against what the silicon actually does.

A behavioural model is a claim about a real part, and a claim nobody checked is
just a plausible-looking number. Every model in this package therefore comes
with the published values it has to reproduce, and a report saying how close it
got.

Two rules make the check worth running.

**Validate out of sample.** A model built from the PSRR curve will reproduce
the PSRR curve, and that proves only that the arithmetic works. The useful test
is whether a model built from one set of published numbers predicts a
*different* published number: build it from the rejection curve and the
regulation specs, then see whether it gets the output noise right. Each
reference point records whether it was used to build the model, and a report
made entirely of in-sample points says so rather than looking like a pass.

**A tolerance is a claim too.** "Within 10%" against a typical value from a
datasheet is a reasonable claim about a typical part. The same 10% against a
limit is not, because a limit is not what a part does. Reference points carry
which they are.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReferencePoint:
    """One published number a model has to reproduce.

    Attributes:
        quantity: What it is, matching the key the model predicts under.
        expected: The published value, in base SI units.
        unit: The unit symbol, for the report.
        source: Where it was published - document number, revision and the
            table or figure. Required, for the same reason a parameter's
            citation is required.
        tolerance: How far off is acceptable, as a fraction. Choose it from
            what the number is: a typical value read off a log plot by eye
            deserves more room than one printed in a table.
        conditions: The test conditions the value is quoted under. A dropout
            voltage without its load current is not a number.
        in_sample: True when this value was used to build the model. An
            in-sample point checks the arithmetic; only an out-of-sample point
            checks the model.
        limit: True when the published value is a limit rather than a typical.
            A model is not expected to reproduce a limit, only to stay inside
            it.
    """

    quantity: str
    expected: float
    unit: str
    source: str
    tolerance: float = 0.10
    conditions: str = ""
    in_sample: bool = False
    limit: bool = False

    def __post_init__(self) -> None:
        """Reject a reference point that cannot be looked up.

        Raises:
            ValueError: If the source is blank.
        """
        if not self.source.strip():
            raise ValueError(
                f"reference point {self.quantity!r} has no source; a number "
                f"nobody can check is not evidence that a model is right"
            )


@dataclass
class Comparison:
    """What the model said against what the datasheet says.

    Attributes:
        point: The published value.
        predicted: What the model produced.
    """

    point: ReferencePoint
    predicted: float

    @property
    def error(self) -> float:
        """How far off the model is, as a fraction of the published value.

        Returns:
            The relative error. Infinite when the published value is zero and
            the model disagrees, which is a real failure rather than a
            division to be swept up.
        """
        if self.point.expected == 0:
            return 0.0 if self.predicted == 0 else float("inf")
        return abs(self.predicted - self.point.expected) / abs(self.point.expected)

    @property
    def passed(self) -> bool:
        """Whether the model is close enough.

        Returns:
            True when within tolerance. For a limit, being on the right side
            of it is enough - a part that draws less than its maximum has not
            failed to match.
        """
        if self.point.limit:
            return self.predicted <= self.point.expected
        return self.error <= self.point.tolerance

    def __str__(self) -> str:
        mark = "pass" if self.passed else "FAIL"
        kind = " (in sample)" if self.point.in_sample else ""
        return (
            f"[{mark}] {self.point.quantity}{kind}: "
            f"model {self.predicted:.4g}{self.point.unit}, "
            f"datasheet {self.point.expected:.4g}{self.point.unit}, "
            f"off by {self.error * 100:.1f}%"
        )


@dataclass
class ValidationReport:
    """How well a model matches the part it claims to be.

    Attributes:
        part: The part number.
        comparisons: One per reference point.
        missing: Reference points the model made no prediction for. These are
            listed rather than skipped: a model that does not predict a
            published behaviour has a gap, and the gap is the useful finding.
    """

    part: str
    comparisons: List[Comparison] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Whether every comparison is within tolerance.

        Returns:
            True when nothing failed.
        """
        return all(comparison.passed for comparison in self.comparisons)

    @property
    def out_of_sample(self) -> List[Comparison]:
        """The comparisons that actually test the model.

        Returns:
            Comparisons against values the model was not built from.
        """
        return [item for item in self.comparisons if not item.point.in_sample]

    @property
    def worst(self) -> Optional[Comparison]:
        """The comparison that is furthest off.

        Returns:
            The worst comparison, or None when there are none.
        """
        return max(self.comparisons, key=lambda item: item.error, default=None)

    def summary(self) -> str:
        """Render the report for a person to read.

        Returns:
            One line per comparison, then a verdict that says how much of the
            check was out of sample.
        """
        lines = [f"{self.part} against its datasheet:"]
        lines += [f"  {comparison}" for comparison in sorted(
            self.comparisons, key=lambda item: (item.passed, -item.error)
        )]
        for quantity in self.missing:
            lines.append(f"  [gap ] {quantity}: the model does not predict this")

        checked = len(self.out_of_sample)
        if not checked:
            lines.append(
                "-> every point was used to build the model, so this checks the "
                "arithmetic and not the model"
            )
        else:
            failed = sum(1 for item in self.comparisons if not item.passed)
            verdict = "matches" if not failed else f"{failed} point(s) off"
            lines.append(
                f"-> {verdict}; {checked} of {len(self.comparisons)} point(s) "
                f"were out of sample"
            )
        return "\n".join(lines)


def validate(
    part: str, predictions: Dict[str, float], points: Sequence[ReferencePoint]
) -> ValidationReport:
    """Compare a model's predictions against published values.

    Args:
        part: The part number, for the report.
        predictions: What the model says, keyed by the reference point's
            ``quantity``.
        points: The published values to check against.

    Returns:
        The report. Read ``passed``, then ``summary()``.
    """
    report = ValidationReport(part=part)

    for point in points:
        if point.quantity not in predictions:
            report.missing.append(point.quantity)
            continue
        report.comparisons.append(
            Comparison(point=point, predicted=predictions[point.quantity])
        )

    logger.info(
        "Validated %s: %d compared, %d not predicted",
        part,
        len(report.comparisons),
        len(report.missing),
    )
    return report
