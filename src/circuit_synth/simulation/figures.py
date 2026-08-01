"""Figures of merit, and where each one came from.

A number written onto a schematic is a claim, and an engineer reading it has to
be able to check the claim without trusting whoever wrote it. That means every
figure has to carry two things besides its value: what kind of evidence stands
behind it, and the exact line of Python that worked it out.

The evidence kind is a :class:`Basis`. It exists so that a guess cannot be
written onto a sheet by accident. :meth:`BlockAnalysis.annotatable` returns only
the figures with real evidence, and :meth:`BlockAnalysis.unverified` returns the
rest so they can be reported instead of quietly shipped. A schematic annotated
with plausible-looking numbers nobody derived is worse than one with no numbers
at all, because it invites the reader to stop checking.

The source line is captured automatically from the caller's stack frame at the
moment the figure is recorded. That is what makes a note on the schematic
clickable back to the calculation: the annotator turns the recorded file and
line into a ``vscode://file/...`` link, so the reader lands on the arithmetic
rather than on a document describing it.
"""

import inspect
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

logger = logging.getLogger(__name__)

# Units that are already absolute and must not be given an SI prefix. "120C"
# is a temperature; "120 milli-C" is nonsense, and a percentage scaled to
# "940m%" would be actively misleading.
#
# Note that "C" here means degrees Celsius, because that is what it means when
# it appears on a schematic. A charge in coulombs would be scaled wrongly by
# this table, so record charges in a unit that cannot be confused - "As" for
# amp-seconds - if one ever needs to be annotated. Datasheet parameters are
# not affected: Parameter stores a value and never formats it.
UNSCALED_UNITS = frozenset({"%", "C", "K", "dB", "deg", "ratio", ""})

# Descending, so the first prefix whose threshold the magnitude clears is the
# one that leaves a mantissa between 1 and 999.
_SI_PREFIXES: Sequence[tuple] = (
    (1e9, "G"),
    (1e6, "M"),
    (1e3, "k"),
    (1.0, ""),
    (1e-3, "m"),
    (1e-6, "u"),
    (1e-9, "n"),
    (1e-12, "p"),
)


class Basis(Enum):
    """What kind of evidence stands behind a figure.

    The ordering here is the order of trust. ``SIMULATED`` and ``DATASHEET``
    are evidence; ``DERIVED`` is arithmetic on top of evidence; ``ESTIMATED``
    is not evidence at all and never reaches a schematic.
    """

    SIMULATED = "simulated"
    """Measured from a SPICE run of this circuit's own netlist."""

    DATASHEET = "datasheet"
    """Computed from an equation quoted out of the part's datasheet."""

    DERIVED = "derived"
    """Arithmetic on other figures, or a textbook identity with no free
    parameters - an RC corner, an inductor volt-second balance."""

    ESTIMATED = "estimated"
    """A guess, a typical value, or a number carried over from a similar
    design. Recorded so it can be reported, never annotated."""


#: The bases whose figures may be written onto a schematic.
TRUSTED_BASES = frozenset({Basis.SIMULATED, Basis.DATASHEET, Basis.DERIVED})


def format_value(value: float, unit: str, digits: int = 3) -> str:
    """Render a number the way it would be written on a schematic.

    Dense notes are read at a glance, so the value is given an SI prefix and
    cut to three significant figures rather than printed at full precision.
    Units that are already absolute are left unscaled.

    Args:
        value: The magnitude, in base SI units (volts, amps, seconds).
        unit: The unit symbol, such as ``"A"`` or ``"%"``. Units listed in
            :data:`UNSCALED_UNITS` are printed without an SI prefix.
        digits: Significant figures to keep.

    Returns:
        The formatted value, such as ``"4.7A"``, ``"120C"`` or ``"1.8mV"``.
    """
    if value != value:  # NaN
        return f"?{unit}"
    if value in (float("inf"), float("-inf")):
        return f"{'-' if value < 0 else ''}inf{unit}"

    scale, prefix = 1.0, ""
    if unit not in UNSCALED_UNITS and value != 0:
        for threshold, candidate in _SI_PREFIXES:
            if abs(value) >= threshold:
                scale, prefix = threshold, candidate
                break
        else:
            # Smaller than a picounit. Show it as zero rather than as "0.001p".
            scale, prefix = 1e-12, "p"

    mantissa = value / scale
    # Three significant figures on a mantissa in 1..999 means the number of
    # decimals depends on how many digits sit in front of the point.
    integer_digits = len(str(int(abs(mantissa)))) if abs(mantissa) >= 1 else 1
    decimals = max(0, digits - integer_digits)
    text = f"{mantissa:.{decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"{text}{prefix}{unit}"


@dataclass(frozen=True)
class Figure:
    """One figure of merit, with its provenance.

    Attributes:
        name: Short label as it appears on the schematic, such as ``"Id"``.
        value: The magnitude in base SI units.
        unit: The unit symbol.
        reference: Reference designator of the component the figure describes,
            such as ``"Q1"``. The note is placed on that component.
        basis: What kind of evidence stands behind the value.
        detail: One-line explanation, shown in reports rather than on the
            sheet. For a datasheet figure this should name the equation.
        source_path: Absolute path of the Python file that recorded it.
        source_line: Line number within that file.
    """

    name: str
    value: float
    unit: str
    reference: str
    basis: Basis
    detail: str = ""
    source_path: Optional[Path] = None
    source_line: int = 0

    @property
    def trusted(self) -> bool:
        """Whether this figure may be written onto a schematic.

        Returns:
            True when the basis is evidence rather than a guess.
        """
        return self.basis in TRUSTED_BASES

    def label(self) -> str:
        """Render the figure as it appears in a schematic note.

        Returns:
            A single line, such as ``"Id = 4.7A"``.
        """
        return f"{self.name} = {format_value(self.value, self.unit)}"

    def link(self) -> Optional[str]:
        """Build the editor URL that opens the line which produced this figure.

        Returns:
            A ``vscode://file/...`` URL, or None when no source was captured.
        """
        if self.source_path is None:
            return None
        # VS Code wants a forward-slashed absolute path. On Windows that means
        # "vscode://file/C:/path/to/file.py:120", with the drive letter kept.
        location = str(self.source_path).replace("\\", "/")
        return f"vscode://file/{location}:{self.source_line}"


@dataclass
class BlockAnalysis:
    """Every figure worked out for one hierarchical block.

    Attributes:
        block: Name of the circuit-synth subcircuit, such as ``"HalfBridge"``.
        figures: The figures recorded so far, in the order they were recorded.
        gaps: Plain-language notes about what could not be established, such
            as a part with no SPICE model or a datasheet that was not found.
    """

    block: str
    figures: List[Figure] = field(default_factory=list)
    gaps: List[str] = field(default_factory=list)

    def record(
        self,
        reference: str,
        name: str,
        value: float,
        unit: str,
        basis: Basis,
        detail: str = "",
        stacklevel: int = 1,
    ) -> Figure:
        """Record one figure, capturing the caller's source location.

        Args:
            reference: Reference designator the figure belongs to, such as
                ``"Q1"``. This decides which symbol the note lands on.
            name: Short label, such as ``"Id"``.
            value: The magnitude in base SI units.
            unit: The unit symbol.
            basis: What kind of evidence stands behind the value.
            detail: One-line explanation for the report. Name the datasheet
                equation here when the basis is :attr:`Basis.DATASHEET`.
            stacklevel: How many frames above this call the interesting line
                is. Pass 2 when recording from inside a helper, so the link
                points at the caller's arithmetic rather than at the helper.

        Returns:
            The recorded figure.
        """
        source_path, source_line = _caller_location(stacklevel + 1)
        figure = Figure(
            name=name,
            value=value,
            unit=unit,
            reference=reference,
            basis=basis,
            detail=detail,
            source_path=source_path,
            source_line=source_line,
        )
        self.figures.append(figure)
        logger.debug(
            "Recorded %s.%s = %s (%s) from %s:%d",
            reference,
            name,
            figure.label(),
            basis.value,
            source_path,
            source_line,
        )
        return figure

    def note_gap(self, message: str) -> None:
        """Record something that could not be established.

        A gap is the honest alternative to a figure. It is reported to the
        user and keeps the corresponding number off the schematic.

        Args:
            message: Plain-language description of what is missing and why it
                matters.
        """
        logger.info("%s: %s", self.block, message)
        self.gaps.append(message)

    def annotatable(self) -> List[Figure]:
        """Return the figures that may be written onto the schematic.

        Returns:
            The figures whose basis is evidence rather than a guess.
        """
        return [figure for figure in self.figures if figure.trusted]

    def unverified(self) -> List[Figure]:
        """Return the figures that were guessed rather than established.

        Returns:
            The figures with :attr:`Basis.ESTIMATED`.
        """
        return [figure for figure in self.figures if not figure.trusted]

    def by_reference(self) -> Dict[str, List[Figure]]:
        """Group the annotatable figures by the component they describe.

        Returns:
            A mapping of reference designator to its figures, in recording
            order. Only figures that may be annotated are included.
        """
        grouped: Dict[str, List[Figure]] = {}
        for figure in self.annotatable():
            grouped.setdefault(figure.reference, []).append(figure)
        return grouped

    def summary(self) -> str:
        """Write the report shown to the user after an analysis.

        The report leads with what could not be established, because that is
        the part a reader needs to see and the part a confident-sounding tool
        tends to bury.

        Returns:
            A multi-line report.
        """
        lines = [f"{self.block}: {len(self.annotatable())} figures established"]

        if self.gaps:
            lines.append("")
            lines.append("Not established:")
            lines.extend(f"  - {gap}" for gap in self.gaps)

        unverified = self.unverified()
        if unverified:
            lines.append("")
            lines.append("Estimated, and therefore NOT written to the schematic:")
            lines.extend(
                f"  - {figure.reference} {figure.label()}"
                f"{' (' + figure.detail + ')' if figure.detail else ''}"
                for figure in unverified
            )

        for reference, figures in sorted(self.by_reference().items()):
            lines.append("")
            lines.append(f"{reference}:")
            lines.extend(
                f"  {figure.label():<16} {figure.basis.value:<10} {figure.detail}".rstrip()
                for figure in figures
            )

        return "\n".join(lines)


def _caller_location(stacklevel: int) -> tuple:
    """Find the file and line of a frame above this one.

    Args:
        stacklevel: How many frames above :func:`_caller_location` to look.

    Returns:
        An ``(absolute path or None, line number)`` pair. The path is None when
        the stack is shallower than requested, which happens when a figure is
        recorded from an interactive session.
    """
    frame = inspect.currentframe()
    try:
        for _ in range(stacklevel):
            if frame is None:
                return None, 0
            frame = frame.f_back
        if frame is None:
            return None, 0
        return Path(frame.f_code.co_filename).resolve(), frame.f_lineno
    finally:
        # Break the reference cycle CPython warns about for frame objects.
        del frame


def merge(analyses: Iterable[BlockAnalysis], block: str) -> BlockAnalysis:
    """Combine several analyses of the same block into one.

    Useful when the datasheet equations and the SPICE run are worked out by
    separate functions and then annotated together.

    Args:
        analyses: The analyses to combine.
        block: Name for the combined analysis.

    Returns:
        A new analysis holding every figure and gap from the inputs.
    """
    combined = BlockAnalysis(block=block)
    for analysis in analyses:
        combined.figures.extend(analysis.figures)
        combined.gaps.extend(analysis.gaps)
    return combined
