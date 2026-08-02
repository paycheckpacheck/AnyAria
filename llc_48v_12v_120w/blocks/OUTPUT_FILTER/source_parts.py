"""
Source parts for OUTPUT_FILTER block.

Requirements:
- Bulk electrolytic: 1000µF 25V low ESR for output bulk capacitance
- Ceramic caps: 47µF 25V X5R/X7R (4-6 in parallel for high-frequency filtering)
- Output connector: 2-pin screw terminal rated 10A+ at 12V
"""

from pathlib import Path
from circuit_synth.manufacturing.sourcing import SourcingPolicy, source_and_import
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).parent.parent.parent
BLOCK_DIR = PROJECT_DIR / "blocks" / "OUTPUT_FILTER"

sourced_parts = {}

def source_part(query: str, role: str, policy: SourcingPolicy):
    """Source a single part and record it."""
    logger.info(f"Sourcing: {query}")
    logger.info(f"Role: {role}")

    try:
        part = source_and_import(
            query=query,
            role=role,
            project_dir=PROJECT_DIR,
            policy=policy
        )

        sourced_parts[role] = part.to_dict()

        logger.info(f"✓ Found: {part.part.model} (LCSC: {part.part.lcsc})")
        logger.info(f"  Price: ${part.part.price:.4f}, Stock: {part.part.stock}")
        logger.info(f"  Category: {part.part.category}")
        logger.info(f"  Symbol: {part.symbol}, Footprint: {part.footprint}")

        return part

    except Exception as e:
        logger.error(f"✗ Failed to source: {query}")
        logger.error(f"  Error: {e}")
        raise

# Source all parts
logger.info("=" * 80)
logger.info("Sourcing OUTPUT_FILTER parts from JLCPCB")
logger.info("=" * 80)

# 1. Bulk electrolytic capacitor
logger.info("\n1. BULK ELECTROLYTIC CAPACITOR")
electrolytic = source_part(
    query="1000uF 25V aluminum electrolytic low ESR radial",
    role="output_bulk_cap",
    policy=SourcingPolicy.for_passive()
)

# 2. High-frequency ceramic capacitor
logger.info("\n2. HIGH-FREQUENCY CERAMIC CAPACITOR")
ceramic = source_part(
    query="47uF 25V X7R 1206 ceramic capacitor",
    role="output_hf_filter_cap",
    policy=SourcingPolicy.for_passive()
)

# 3. Output connector
logger.info("\n3. OUTPUT CONNECTOR")
# Screw terminals typically need Extended policy due to variety
connector = source_part(
    query="screw terminal 2 pin 5.08mm 10A wire-to-board",
    role="output_connector",
    policy=SourcingPolicy(
        min_stock=100,
        max_unit_price=1.0,
        prefer_basic=True,
        allow_extended=True
    )
)

# Save parts.json
parts_json_path = BLOCK_DIR / "parts.json"
logger.info(f"\nWriting parts to {parts_json_path}")

with open(parts_json_path, 'w') as f:
    json.dump(sourced_parts, f, indent=2)

logger.info("✓ All parts sourced successfully")
logger.info(f"✓ Saved to {parts_json_path}")

# Summary
logger.info("\n" + "=" * 80)
logger.info("SOURCING SUMMARY")
logger.info("=" * 80)
for role, part_dict in sourced_parts.items():
    logger.info(f"{role}:")
    logger.info(f"  LCSC: {part_dict['lcsc']}")
    logger.info(f"  Model: {part_dict['model']}")
    logger.info(f"  Price: ${part_dict['price']:.4f}")
    logger.info(f"  Stock: {part_dict['stock']}")
    logger.info(f"  Basic: {part_dict['basic']}")
