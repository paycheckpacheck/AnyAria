"""KiCad integration package."""

from . import sch_api_compat  # noqa: F401  (corrects kicad-sch-api on import)
from .bom_exporter import BOMExporter
from .bom_manager import BOMPropertyManager
from .kicad_symbol_cache import SymbolLibCache

__all__ = ["BOMExporter", "BOMPropertyManager", "SymbolLibCache"]
