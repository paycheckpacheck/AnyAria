"""Datasheet parameters and equations, with the citation attached.

The point of this module is to make an uncited number impossible to use by
accident. A :class:`Parameter` cannot be constructed without saying which
document and which table it came from, and :func:`require` raises rather than
returning a default when a part has not been researched. Everything downstream
that turns numbers into schematic annotations goes through here, so the only
way to annotate a sheet with a fabricated figure is to write the fabrication
down as a citation first - which is a thing a person will not do by mistake.

The part records are not shipped as a fixed library. A datasheet is found and
read at the time a block is analysed, because the equations that matter depend
on the role the part plays: the same gate driver in a motor drive and in a
class-D amplifier wants a different bootstrap calculation, and a fixed table
would quietly answer the wrong question. :attr:`Datasheet.role` records which
question was being asked, so a cached record can be rejected when it does not
match.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional, Tuple

logger = logging.getLogger(__name__)


class DatasheetNotFound(Exception):
    """Raised when a part's datasheet could not be found or read.

    This is deliberately an exception rather than a fallback to typical
    values. A block that cannot be analysed should report that it cannot be
    analysed; it should not annotate a schematic with the properties of a
    part somebody else built.
    """


@dataclass(frozen=True)
class Parameter:
    """One number lifted out of a datasheet, with where it was found.

    Attributes:
        symbol: The datasheet's own symbol, such as ``"Qg"`` or ``"RDS(on)"``.
            Using the datasheet's spelling makes the citation checkable.
        value: The magnitude in base SI units.
        unit: The unit symbol.
        section: The table, figure or section it was read from, such as
            ``"Table 2, Dynamic Characteristics"``. Required.
        conditions: Test conditions the value is quoted under, such as
            ``"VGS=10V, VDS=25V, ID=17A"``. A gate charge without its test
            conditions is not a usable number.
        typical: True when this is a typical value rather than a limit. A
            design checked against typicals is not checked.
    """

    symbol: str
    value: float
    unit: str
    section: str
    conditions: str = ""
    typical: bool = True

    def __post_init__(self) -> None:
        """Reject a parameter that does not say where it came from.

        Raises:
            ValueError: If the section is blank.
        """
        if not self.section.strip():
            raise ValueError(
                f"parameter {self.symbol!r} has no section citation; a number "
                f"without a source cannot be used to annotate a schematic"
            )


@dataclass(frozen=True)
class Equation:
    """A design equation quoted from a datasheet or application note.

    Attributes:
        name: Short identifier used to look the equation up, such as
            ``"bootstrap_capacitor"``.
        expression: The equation as written in the source, in plain text.
            This is what gets shown to a reviewer, so keep the source's own
            symbols rather than renaming them.
        symbols: Meaning of each symbol in the expression.
        section: Where in the document the equation appears.
        purpose: What the equation decides, in one line. This is the field
            that catches an equation being used for the wrong thing.
    """

    name: str
    expression: str
    symbols: Mapping[str, str]
    section: str
    purpose: str = ""

    def __post_init__(self) -> None:
        """Reject an equation with no stated source.

        Raises:
            ValueError: If the section is blank.
        """
        if not self.section.strip():
            raise ValueError(
                f"equation {self.name!r} has no section citation; an equation "
                f"nobody can look up is not evidence"
            )


@dataclass(frozen=True)
class Datasheet:
    """What was read out of one part's datasheet for one role.

    Attributes:
        part_number: The part as ordered, such as ``"IR2101"``.
        title: Document title.
        document: Document number and revision, such as ``"PD60046 rev P"``.
            This is what makes the citation reproducible; datasheets are
            revised and parameters change between revisions.
        url: Where the document was fetched from.
        role: What the part does in the architecture being analysed, such as
            ``"high/low-side gate driver for a bootstrapped half-bridge"``.
        parameters: Parameters read out, keyed by symbol.
        equations: Design equations, keyed by name.
        notes: Anything a reviewer should know, such as a parameter that is
            only given as a curve rather than a table.
    """

    part_number: str
    title: str
    document: str
    url: str
    role: str
    parameters: Mapping[str, Parameter] = field(default_factory=dict)
    equations: Mapping[str, Equation] = field(default_factory=dict)
    notes: Tuple[str, ...] = ()

    def parameter(self, symbol: str) -> Parameter:
        """Look up a parameter, or say plainly that it is not there.

        Args:
            symbol: The datasheet symbol, such as ``"Qg"``.

        Returns:
            The parameter.

        Raises:
            DatasheetNotFound: If the parameter was not read out of the
                datasheet. Callers must not substitute a typical value.
        """
        try:
            return self.parameters[symbol]
        except KeyError:
            raise DatasheetNotFound(
                f"{self.part_number}: no value for {symbol!r} was read from "
                f"{self.document}. Read it from the datasheet or leave the "
                f"figure that depends on it off the schematic."
            ) from None

    def value(self, symbol: str) -> float:
        """Return a parameter's magnitude in base SI units.

        Args:
            symbol: The datasheet symbol.

        Returns:
            The value.

        Raises:
            DatasheetNotFound: If the parameter was not read out.
        """
        return self.parameter(symbol).value

    def equation(self, name: str) -> Equation:
        """Look up a design equation.

        Args:
            name: The equation's identifier.

        Returns:
            The equation.

        Raises:
            DatasheetNotFound: If the equation was not extracted.
        """
        try:
            return self.equations[name]
        except KeyError:
            raise DatasheetNotFound(
                f"{self.part_number}: no equation named {name!r} was extracted "
                f"from {self.document}."
            ) from None

    def cite(self, section: str = "") -> str:
        """Write the citation that goes in a figure's detail line.

        Args:
            section: A specific section to name, or blank for the document
                as a whole.

        Returns:
            A citation such as ``"IR2101 PD60046 rev P, Table 2"``.
        """
        head = f"{self.part_number} {self.document}"
        return f"{head}, {section}" if section else head

    def cite_parameter(self, symbol: str) -> str:
        """Write the citation for one parameter.

        Args:
            symbol: The datasheet symbol.

        Returns:
            A citation naming the document and the table the value is in.

        Raises:
            DatasheetNotFound: If the parameter was not read out.
        """
        return self.cite(self.parameter(symbol).section)


# Datasheets researched during this session, keyed by upper-case part number.
# Deliberately not pre-populated: a record is only trustworthy when somebody
# has just read the document for the role in question.
_REGISTRY: Dict[str, Datasheet] = {}


def register(datasheet: Datasheet) -> Datasheet:
    """Add a researched datasheet to the session registry.

    Args:
        datasheet: The record to register.

    Returns:
        The same record, so this can wrap a constructor call.
    """
    _REGISTRY[datasheet.part_number.upper()] = datasheet
    logger.info(
        "Registered datasheet %s (%s) for role: %s",
        datasheet.part_number,
        datasheet.document,
        datasheet.role,
    )
    return datasheet


def lookup(part_number: str) -> Optional[Datasheet]:
    """Find a registered datasheet.

    Args:
        part_number: The part as ordered. Case-insensitive.

    Returns:
        The record, or None when the part has not been researched.
    """
    return _REGISTRY.get(part_number.upper())


def require(part_number: str, role: str = "") -> Datasheet:
    """Find a registered datasheet, or refuse to continue without it.

    Args:
        part_number: The part as ordered.
        role: The role the part is expected to play. When given, a record
            researched for a different role is rejected, because the
            equations that matter would be the wrong ones.

    Returns:
        The record.

    Raises:
        DatasheetNotFound: When the part has not been researched, or was
            researched for a different role.
    """
    found = lookup(part_number)
    if found is None:
        raise DatasheetNotFound(
            f"No datasheet has been read for {part_number}. Find it, extract "
            f"the parameters and equations that matter for its role, and "
            f"register it. Do not annotate the schematic until then."
        )
    if role and found.role != role:
        raise DatasheetNotFound(
            f"{part_number} was researched as {found.role!r}, but is being "
            f"used as {role!r}. The equations that matter differ between "
            f"roles; re-read the datasheet for this one."
        )
    return found


def clear() -> None:
    """Empty the session registry.

    Provided for tests, which must not inherit records from each other.
    """
    _REGISTRY.clear()
