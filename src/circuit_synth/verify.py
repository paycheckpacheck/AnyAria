# -*- coding: utf-8 -*-
"""Run every check a generated project can be given, and report once.

The checks all existed before this module and none of them ran together. A
person had to remember that `validate_layout` compares the drawing against the
Python, that `run_erc` is a separate call, that the SPICE deck has its own
failure mode, and to look at the renders afterwards. Anything remembered is
sometimes forgotten, and the checks that get forgotten are the ones that catch
the expensive mistakes.

So they are sequenced here, in the order of how expensive the mistake is to
find later, and the result is one verdict with everything that failed.

What this cannot do is tell you the circuit is right. Every check here compares
the drawing against the Python. A schematic that draws the wrong circuit
perfectly passes all of them. That is what the `review-circuit` skill is for,
and it runs before any of this.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    """The outcome of one check.

    Attributes:
        name: What was checked.
        passed: Whether it passed.
        detail: What went wrong, or a summary when it passed.
        skipped: True when the check could not run - a missing tool, say -
            which is not the same as passing and is reported differently.
    """

    name: str
    passed: bool
    detail: str = ""
    skipped: bool = False

    def __str__(self) -> str:
        mark = "skip" if self.skipped else ("pass" if self.passed else "FAIL")
        return f"[{mark}] {self.name}" + (f": {self.detail}" if self.detail else "")


@dataclass
class VerificationReport:
    """Everything that was checked about a project.

    Attributes:
        project: The project directory.
        checks: Each check's result, in the order they ran.
        images: Rendered sheet images, for a human or Claude to look at.
    """

    project: Path
    checks: List[CheckResult] = field(default_factory=list)
    images: List[Path] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Whether every check that ran passed.

        Returns:
            True when nothing failed. A skipped check does not fail the report,
            but it is listed, because a check that did not run has not passed.
        """
        return all(check.passed for check in self.checks if not check.skipped)

    @property
    def failures(self) -> List[CheckResult]:
        """The checks that failed.

        Returns:
            The failing checks.
        """
        return [check for check in self.checks if not check.passed and not check.skipped]

    def summary(self) -> str:
        """Render the report for a person to read.

        Returns:
            One line per check, then a verdict.
        """
        lines = [str(check) for check in self.checks]
        skipped = sum(1 for check in self.checks if check.skipped)
        verdict = "verified" if self.passed else f"{len(self.failures)} check(s) failed"
        if skipped:
            verdict += f", {skipped} skipped"
        lines.append(f"-> {verdict}")
        return "\n".join(lines)


def verify_project(
    root_schematic: Path,
    circuit_json: Path,
    circuit: Optional[Any] = None,
    render: bool = True,
) -> VerificationReport:
    """Check a generated project every way the toolchain can.

    Args:
        root_schematic: The project's root ``.kicad_sch``.
        circuit_json: The generated circuit JSON, which is what the drawing is
            compared against.
        circuit: The in-memory ``Circuit``, when it is to hand. Enables the
            property and manufacturing checks, which need the object rather
            than the files.
        render: Whether to render the sheets to images at the end.

    Returns:
        The report. Read ``passed``, then ``summary()``.
    """
    root_schematic = Path(root_schematic)
    circuit_json = Path(circuit_json)
    project = root_schematic.parent
    report = VerificationReport(project=project)

    report.checks.append(_check_circuit_rules(circuit))
    report.checks.append(_check_sheets_open(project))
    report.checks.append(_check_layout(root_schematic, circuit_json))
    report.checks.append(_check_erc(root_schematic))
    report.checks.append(_check_spice(root_schematic))

    if render:
        images, result = _render(root_schematic, project / "img")
        report.images = images
        report.checks.append(result)

    logger.info("Verification of %s: %s", project.name, report.summary())
    return report


def _check_circuit_rules(circuit: Optional[Any]) -> CheckResult:
    """Check the circuit object's own rules.

    Args:
        circuit: The circuit, or None.

    Returns:
        The result.
    """
    name = "circuit rules (properties, footprints, naming)"
    if circuit is None:
        return CheckResult(name, True, "no circuit object supplied", skipped=True)

    try:
        from .quality_assurance.validation import validate

        issues = validate(circuit, checks="all")
        errors = [issue for issue in issues if getattr(issue, "severity", "") == "error"]
        if errors:
            return CheckResult(name, False, "; ".join(str(item) for item in errors[:3]))
        return CheckResult(name, True, f"{len(issues)} warning(s)")
    except Exception as error:  # pragma: no cover - optional module
        return CheckResult(name, True, f"could not run: {error}", skipped=True)


def _check_sheets_open(project: Path) -> CheckResult:
    """Check every sheet is a file KiCad will open.

    Args:
        project: The project directory.

    Returns:
        The result.
    """
    from .kicad.sheet_check import _kicad_cli, describe_unloadable, unloadable_sheets

    name = "every sheet opens in KiCad"
    if _kicad_cli() is None:
        return CheckResult(name, True, "kicad-cli not installed", skipped=True)

    broken = unloadable_sheets(project)
    if broken:
        return CheckResult(name, False, describe_unloadable(broken))
    return CheckResult(name, True)


def _check_layout(root_schematic: Path, circuit_json: Path) -> CheckResult:
    """Check the drawing still draws the circuit the Python described.

    Args:
        root_schematic: The root sheet.
        circuit_json: The generated circuit JSON.

    Returns:
        The result.
    """
    from .kicad.layout.validate import find_kicad_cli, validate_layout

    name = "drawing matches the circuit, nothing drawn over a part"
    if find_kicad_cli() is None:
        return CheckResult(name, True, "kicad-cli not installed", skipped=True)
    if not circuit_json.exists():
        return CheckResult(name, True, f"{circuit_json.name} is missing", skipped=True)

    problems = validate_layout(root_schematic, circuit_json)
    if problems:
        shown = "; ".join(str(problem) for problem in problems[:3])
        return CheckResult(name, False, f"{len(problems)} problem(s): {shown}")
    return CheckResult(name, True)


def _check_erc(root_schematic: Path) -> CheckResult:
    """Run KiCad's own electrical rules check.

    Args:
        root_schematic: The root sheet.

    Returns:
        The result.
    """
    from .kicad.layout.validate import erc_violations, find_kicad_cli

    name = "ERC reports no errors"
    if find_kicad_cli() is None:
        return CheckResult(name, True, "kicad-cli not installed", skipped=True)

    violations = erc_violations(root_schematic)
    if violations:
        counts: Dict[str, int] = {}
        for violation in violations:
            counts[violation] = counts.get(violation, 0) + 1
        listed = ", ".join(f"{kind} x{count}" for kind, count in sorted(counts.items()))
        return CheckResult(name, False, listed)
    return CheckResult(name, True)


def _check_spice(root_schematic: Path) -> CheckResult:
    """Check the exported SPICE deck is one a simulator will load.

    Args:
        root_schematic: The root sheet.

    Returns:
        The result.
    """
    from .kicad.spice_hygiene import deck_loads

    name = "SPICE deck loads"
    loaded, detail = deck_loads(root_schematic)
    return CheckResult(name, loaded, detail)


def _render(root_schematic: Path, out_dir: Path) -> tuple:
    """Render every sheet so the result can be looked at.

    Args:
        root_schematic: The root sheet.
        out_dir: Where to write the images.

    Returns:
        An ``(images, result)`` pair.
    """
    from .kicad.layout.render import render_sheets
    from .kicad.layout.validate import find_kicad_cli

    name = "sheets rendered for review"
    if find_kicad_cli() is None:
        return [], CheckResult(name, True, "kicad-cli not installed", skipped=True)

    try:
        images = render_sheets(root_schematic, out_dir)
    except Exception as error:
        return [], CheckResult(name, False, str(error))

    return images, CheckResult(
        name, True, f"{len(images)} image(s) in {out_dir} - now look at them"
    )
