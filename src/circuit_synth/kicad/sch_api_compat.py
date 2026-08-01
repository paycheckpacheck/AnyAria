"""Corrections applied to kicad-sch-api's s-expression formatter.

kicad-sch-api writes the ``lib_symbols`` section by formatting the symbol
definition it read out of a ``.kicad_sym`` library. Its property formatter
assumes a property is always ``(property "Name" "Value" ...)``, so it quotes
the second and third elements and copies everything after them out verbatim.

KiCad's own libraries do not always match that shape. A property may carry a
bare flag before its name::

    (property private "KLC_S4.2_DVDD" "Not a standalone power converter; ..."

There the name and value sit one place further along, so the flag gets quoted
as if it were the name, the name is written as the value, and the real value -
a string full of spaces and semicolons - is copied out with no quotes at all.
The result is not a valid s-expression, and KiCad refuses to open the sheet:
every part on it disappears from the netlist. Symbols carrying such a property
include ``MCU_RaspberryPi:RP2040``.

This module reinstates the flags as flags and quotes the name and value
wherever they actually are. It patches the dependency in place rather than
waiting for a release, and is idempotent, so importing it repeatedly is safe.
"""

import logging
from typing import Any, List

logger = logging.getLogger(__name__)

_PATCHED_FLAG = "_circuit_synth_property_flags_patch"


def _split_property(elements: List[Any]) -> tuple:
    """Separate a property's leading bare flags from its name and value.

    Args:
        elements: A property's elements with the ``property`` tag removed.

    Returns:
        A ``(flags, name, value, trailing)`` tuple. ``name`` and ``value`` are
        the quoted strings KiCad expects, each empty when the property does not
        carry one. ``flags`` are the bare tokens that preceded them and
        ``trailing`` is everything that followed.
    """
    import sexpdata

    flags: List[Any] = []
    index = 0
    while index < len(elements) and isinstance(elements[index], sexpdata.Symbol):
        flags.append(elements[index])
        index += 1

    name = elements[index] if index < len(elements) else ""
    value = elements[index + 1] if index + 1 < len(elements) else ""
    return flags, name, value, elements[index + 2 :]


def _install_property_formatter() -> bool:
    """Replace kicad-sch-api's property formatter with a flag-aware one.

    Returns:
        True when the patch is in place, False when kicad-sch-api is not
        installed or does not have the formatter this patches.
    """
    try:
        from kicad_sch_api.core import formatter as sch_formatter
    except ImportError:
        logger.debug("kicad-sch-api is not installed; no formatter to correct")
        return False

    exact = getattr(sch_formatter, "ExactFormatter", None)
    if exact is None or not hasattr(exact, "_format_property"):
        logger.debug("kicad-sch-api has no property formatter to correct")
        return False

    if getattr(exact, _PATCHED_FLAG, False):
        return True

    def _format_property(self, lst: List[Any], indent_level: int) -> str:
        """Format a property, keeping any bare flags ahead of its name."""
        flags, name, value, trailing = _split_property(list(lst[1:]))

        indent = "\t" * indent_level
        next_indent = "\t" * (indent_level + 1)

        opening = f"({lst[0]}"
        for flag in flags:
            opening += f" {flag}"
        opening += f' "{self._escape_string(str(name))}"'
        opening += f' "{self._escape_string(str(value))}"'

        if not trailing:
            return opening + ")"

        result = opening
        for element in trailing:
            if isinstance(element, list):
                rendered = self._format_element(element, indent_level + 1)
                result += f"\n{next_indent}{rendered}"
            else:
                result += f" {element}"
        return result + f"\n{indent})"

    exact._format_property = _format_property
    setattr(exact, _PATCHED_FLAG, True)
    logger.debug("Corrected kicad-sch-api's property formatter")
    return True


_install_property_formatter()
