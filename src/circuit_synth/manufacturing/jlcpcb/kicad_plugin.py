# -*- coding: utf-8 -*-
"""Search and import real JLCPCB parts, through KiCad's JLCImport plugin.

The plugin at ``com_github_jvanderberg_kicad-jlcimport`` already talks to
JLCPCB's search API and already converts an LCSC part into a real KiCad symbol,
footprint and 3D model. That is the hard part, it is maintained, and it is
installed alongside KiCad, so this module wraps it rather than reimplementing
any of it.

Wrapping it, rather than the package in this repo that claims to do the same
job, is deliberate. ``jlc_web_scraper`` returns a hardcoded table of about
eight search strings and a synthetic ``C000000`` row for everything else, so
every real part number fails against it. Its tests pass because they are
mocked.

Importing a part through the plugin also removes a whole class of error. The
symbol and footprint come from the part itself, so they exist, they match each
other, and they match what will be assembled. A symbol invented from memory
fails at ``Component`` construction; an invented footprint used to survive as
far as the board house.
"""

import importlib.util
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PACKAGE_NAME = "kicad_jlcimport"
PLUGIN_DIRNAME = "com_github_jvanderberg_kicad-jlcimport"

# Where KiCad keeps third-party plugins. The user's documents directory moves
# when OneDrive is in the picture, so several places are tried.
PLUGIN_SEARCH_ROOTS = (
    Path.home() / "OneDrive" / "Documents" / "KiCad",
    Path.home() / "Documents" / "KiCad",
    Path(os.environ.get("APPDATA", "")) / "kicad" if os.environ.get("APPDATA") else None,
    Path.home() / ".local" / "share" / "kicad",
    Path.home() / "Library" / "Preferences" / "kicad",
)


class PluginNotInstalled(RuntimeError):
    """The JLCImport plugin could not be found or loaded."""


def find_plugin() -> Optional[Path]:
    """Locate the installed JLCImport plugin.

    Returns:
        The plugin's package directory, or None when it is not installed.
        The newest KiCad version directory wins, since that is the one the
        user is running.
    """
    override = os.environ.get("JLCIMPORT_PLUGIN_DIR")
    if override:
        candidate = Path(override)
        return candidate if (candidate / "__init__.py").exists() else None

    found: List[Path] = []
    for root in PLUGIN_SEARCH_ROOTS:
        if root is None or not root.exists():
            continue
        found.extend(
            path
            for path in root.glob(f"*/3rdparty/plugins/{PLUGIN_DIRNAME}")
            if (path / "__init__.py").exists()
        )
    if not found:
        return None
    # Sort by the KiCad version directory, so 10.0 beats 9.0.
    return sorted(found, key=lambda path: path.parents[2].name)[-1]


def load_plugin() -> Any:
    """Import the plugin's package and return it.

    The plugin's own modules import each other as ``kicad_jlcimport``, but the
    directory KiCad installs it into is named after its repository, so the
    package has to be registered under the name its imports expect before any
    of it will load.

    Returns:
        The imported ``kicad_jlcimport`` package.

    Raises:
        PluginNotInstalled: If the plugin is absent or will not import.
    """
    if PACKAGE_NAME in sys.modules:
        return sys.modules[PACKAGE_NAME]

    root = find_plugin()
    if root is None:
        raise PluginNotInstalled(
            "KiCad's JLCImport plugin is not installed, and part sourcing needs "
            "it. Install it from KiCad's Plugin and Content Manager, or set "
            "JLCIMPORT_PLUGIN_DIR to its directory."
        )

    spec = importlib.util.spec_from_file_location(
        PACKAGE_NAME, root / "__init__.py", submodule_search_locations=[str(root)]
    )
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise PluginNotInstalled(f"{root} is not an importable package")

    module = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except Exception as error:  # pragma: no cover - depends on the install
        del sys.modules[PACKAGE_NAME]
        raise PluginNotInstalled(f"JLCImport is installed but will not load: {error}")

    logger.debug("Loaded JLCImport from %s", root)
    return module


@dataclass(frozen=True)
class JlcPart:
    """One part as JLCPCB's catalogue describes it.

    Attributes:
        lcsc: LCSC part number, such as ``"C14663"``.
        kind: ``"Basic"`` or ``"Extended"``. Extended parts carry a per-reel
            loading fee, so a Basic part is cheaper to assemble even when the
            unit price is the same.
        price: Unit price at the quoted break, or None when unpriced.
        currency: Currency symbol for ``price``.
        stock: Units in stock, or None when unknown.
        model: The manufacturer's part number.
        package: Package as JLCPCB names it, such as ``"0603"``.
        brand: Manufacturer.
        description: Catalogue description.
        datasheet: Datasheet URL, when the catalogue has one.
    """

    lcsc: str
    kind: str
    price: Optional[float]
    currency: str
    stock: Optional[int]
    model: str
    package: str
    brand: str
    description: str
    datasheet: str

    @staticmethod
    def from_result(result: Dict[str, Any]) -> "JlcPart":
        """Build a part from a plugin search result.

        Args:
            result: One entry of the plugin's search results.

        Returns:
            The part.
        """
        return JlcPart(
            lcsc=str(result.get("lcsc") or ""),
            kind=str(result.get("type") or ""),
            price=result.get("price"),
            currency=str(result.get("currency") or "$"),
            stock=result.get("stock"),
            model=str(result.get("model") or result.get("name") or ""),
            package=str(result.get("package") or ""),
            brand=str(result.get("brand") or ""),
            description=str(result.get("description") or ""),
            datasheet=str(result.get("datasheet") or ""),
        )

    @property
    def is_basic(self) -> bool:
        """Whether this is a Basic part.

        Returns:
            True for a Basic part.
        """
        return self.kind.lower() == "basic"


def search(
    keyword: str,
    limit: int = 50,
    basic_only: bool = False,
    min_stock: int = 1,
    region: str = "global",
) -> List[JlcPart]:
    """Search JLCPCB's catalogue.

    Args:
        keyword: What to search for. Specific beats short: a value, a package,
            a dielectric and a voltage rating narrow a passive down far better
            than the value alone.
        limit: How many results to ask the catalogue for.
        basic_only: Return only Basic parts.
        min_stock: Discard parts with less stock than this.
        region: ``"global"`` or ``"cn"``; the two catalogues differ.

    Returns:
        The matching parts, most stock first.

    Raises:
        PluginNotInstalled: If the JLCImport plugin is unavailable.
    """
    load_plugin()
    from kicad_jlcimport.easyeda.api import (  # noqa: PLC0415
        filter_by_min_stock,
        filter_by_type,
        search_components,
        search_components_cn,
    )

    finder = search_components_cn if region == "cn" else search_components
    results = finder(keyword, page_size=limit).get("results", [])
    results = filter_by_type(results, "Basic" if basic_only else "")
    results = filter_by_min_stock(results, min_stock)
    results.sort(key=lambda item: item.get("stock") or 0, reverse=True)
    return [JlcPart.from_result(item) for item in results]


def is_valid_lcsc(lcsc: str) -> bool:
    """Report whether a string is a well-formed LCSC part number.

    Args:
        lcsc: The candidate part number.

    Returns:
        True when the catalogue would accept it.
    """
    load_plugin()
    from kicad_jlcimport.easyeda.api import validate_lcsc_id  # noqa: PLC0415

    try:
        return bool(validate_lcsc_id(lcsc))
    except Exception:
        return False


@dataclass(frozen=True)
class ImportedPart:
    """A part after its symbol and footprint have been written into a library.

    Attributes:
        lcsc: The LCSC part number that was imported.
        symbol: The ``"Library:Name"`` reference, ready for ``Component``.
        footprint: The ``"Library:Name"`` footprint reference.
        library_path: Where the symbol library was written.
    """

    lcsc: str
    symbol: str
    footprint: str
    library_path: Path


def import_part(
    lcsc: str,
    project_dir: Path,
    library_name: str = "JLCImport",
    overwrite: bool = False,
    kicad_version: int = 10,
) -> ImportedPart:
    """Import a part's symbol, footprint and 3D model into a project library.

    The library goes in the project rather than in KiCad's global library, so
    the project carries its own parts and opens on a machine that has never
    seen them.

    Args:
        lcsc: LCSC part number.
        project_dir: The KiCad project directory to write the library into.
        library_name: Name for the library, and its file stem.
        overwrite: Replace an existing entry rather than keeping it.
        kicad_version: Target KiCad major version.

    Returns:
        The imported part, with the references ``Component`` needs.

    Raises:
        PluginNotInstalled: If the JLCImport plugin is unavailable.
        ValueError: If the part number is malformed or the import fails.
    """
    load_plugin()
    from kicad_jlcimport.importer import import_component  # noqa: PLC0415

    if not is_valid_lcsc(lcsc):
        raise ValueError(f"{lcsc!r} is not an LCSC part number")

    project_dir = Path(project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)

    messages: List[str] = []
    result = import_component(
        lcsc_id=lcsc,
        lib_dir=str(project_dir),
        lib_name=library_name,
        overwrite=overwrite,
        use_global=False,
        log=messages.append,
        kicad_version=kicad_version,
    )
    if not result:
        detail = "; ".join(messages[-3:]) or "no reason given"
        raise ValueError(f"importing {lcsc} failed: {detail}")

    name = result.get("name") or lcsc
    library_path = project_dir / f"{library_name}.kicad_sym"
    register_library_dir(project_dir)
    footprint = _footprint_of(library_path, name) or f"{library_name}:{name}"
    logger.info("Imported %s as %s:%s", lcsc, library_name, name)

    return ImportedPart(
        lcsc=lcsc,
        symbol=f"{library_name}:{name}",
        footprint=footprint,
        library_path=library_path,
    )


def register_library_dir(directory: Path) -> None:
    """Make a directory of symbol libraries visible to the symbol cache.

    An imported part is worthless if ``Component`` cannot find its symbol, and
    the cache resolves libraries from ``KICAD_SYMBOL_DIR``. Putting the project
    directory on that path here means the caller does not have to know, and
    cannot forget.

    Args:
        directory: The directory holding the ``.kicad_sym`` files.
    """
    from ...kicad.kicad_symbol_cache import SymbolLibCache  # noqa: PLC0415

    separator = ";" if os.name == "nt" else ":"
    existing = os.environ.get("KICAD_SYMBOL_DIR", "")
    wanted = str(Path(directory).resolve())

    parts = [item for item in existing.split(separator) if item.strip()]
    if any(Path(item).resolve() == Path(wanted) for item in parts if item.strip()):
        return

    os.environ["KICAD_SYMBOL_DIR"] = separator.join(parts + [wanted])

    # The cache indexes libraries once; a library added afterwards is invisible
    # until the index is rebuilt.
    SymbolLibCache._index_built = False
    SymbolLibCache._library_index = {}
    SymbolLibCache._symbol_index = {}
    logger.debug("Registered %s with the symbol cache", wanted)


def _footprint_of(library_path: Path, symbol_name: str) -> str:
    """Read the footprint a written symbol points at.

    The plugin puts the footprint reference in the symbol's own ``Footprint``
    property, which is the authoritative answer - reconstructing it from the
    library and symbol names would be a guess that happens to be right.

    Args:
        library_path: The written ``.kicad_sym``.
        symbol_name: The symbol to look up.

    Returns:
        The ``"Library:Name"`` footprint reference, or an empty string when it
        cannot be read.
    """
    if not library_path.exists():
        return ""

    text = library_path.read_text(encoding="utf-8")
    start = text.find(f'(symbol "{symbol_name}"')
    if start < 0:
        return ""

    match = re.search(r'\(property\s+"Footprint"\s+"([^"]*)"', text[start:])
    return match.group(1) if match else ""
