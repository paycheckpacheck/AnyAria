"""
Source parts for OUTPUT_SENSE_PROTECT block.

Requirements:
- Current sense shunt: 10-20mΩ, 1%, 2W for 0-10A sensing
- Current sense amplifier: INA180 or op-amp for shunt amplification
- Comparator: LM393 for overvoltage protection
- Optocoupler: PC817 for feedback isolation
- NTC thermistor: 10kΩ for temperature sensing
- Voltage divider resistors: 1% for 12V→3.3V ADC input
"""

from pathlib import Path
from circuit_synth.manufacturing.sourcing import SourcingPolicy, source_and_import
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).parent.parent.parent
BLOCK_DIR = PROJECT_DIR / "blocks" / "OUTPUT_SENSE_PROTECT"

sourced_parts = {}
deviations = []

def source_part_safe(query: str, role: str, policy: SourcingPolicy, fallback_queries=None):
    """Source a single part with fallback options."""
    logger.info(f"Sourcing: {query}")
    logger.info(f"Role: {role}")

    queries_to_try = [query] + (fallback_queries or [])

    for q in queries_to_try:
        try:
            part = source_and_import(
                query=q,
                role=role,
                project_dir=PROJECT_DIR,
                policy=policy
            )

            sourced_parts[role] = part.to_dict()

            logger.info(f"✓ Found: {part.part.model} (LCSC: {part.part.lcsc})")
            logger.info(f"  Price: ${part.part.price:.4f}, Stock: {part.part.stock}")

            if q != query:
                deviation = f"{role}: Used '{q}' instead of '{query}'"
                deviations.append(deviation)
                logger.warning(f"  DEVIATION: {deviation}")

            return part

        except Exception as e:
            logger.error(f"✗ Failed: {q} - {e}")
            if q == queries_to_try[-1]:
                # Last attempt failed
                deviation = f"{role}: Could not source from JLCPCB (tried: {', '.join(queries_to_try)})"
                deviations.append(deviation)
                sourced_parts[role] = {"deviation": deviation}
                return None

logger.info("=" * 80)
logger.info("Sourcing OUTPUT_SENSE_PROTECT parts from JLCPCB")
logger.info("=" * 80)

# 1. Current sense shunt resistor
logger.info("\n1. CURRENT SENSE SHUNT RESISTOR")
shunt = source_part_safe(
    query="0.01 ohm 1% 2W 2512 current sense resistor",
    role="current_shunt",
    policy=SourcingPolicy.for_passive(),
    fallback_queries=[
        "0.02 ohm 1% 2W 2512 current sense resistor",
        "10 milliohm 2512 current sensing resistor",
        "0.005 ohm 1% 3W current sense resistor"
    ]
)

# 2. Current sense amplifier
logger.info("\n2. CURRENT SENSE AMPLIFIER")
current_amp = source_part_safe(
    query="INA180 SOT-23-5 current sense amplifier",
    role="current_amp",
    policy=SourcingPolicy(min_stock=100, max_unit_price=2.0, prefer_basic=True, allow_extended=True),
    fallback_queries=[
        "INA199 SOT-23-5 current sense amplifier",
        "INA181 SOT-23-6 current sense amplifier",
        "LM358 SOIC-8 dual op-amp",
        "TL072 SOIC-8 dual op-amp"
    ]
)

# 3. Comparator for OVP
logger.info("\n3. COMPARATOR FOR OVP")
comparator = source_part_safe(
    query="LM393 SOIC-8 dual comparator",
    role="ovp_comparator",
    policy=SourcingPolicy.for_passive(),
    fallback_queries=[
        "LM393 SOP-8 comparator",
        "LM339 SOIC-14 quad comparator",
        "LM2903 SOIC-8 dual comparator"
    ]
)

# 4. Optocoupler
logger.info("\n4. OPTOCOUPLER FOR FEEDBACK ISOLATION")
opto = source_part_safe(
    query="PC817 SOP-4 optocoupler phototransistor",
    role="feedback_optocoupler",
    policy=SourcingPolicy.for_passive(),
    fallback_queries=[
        "PC817 DIP-4 optocoupler",
        "EL817 SOP-4 optocoupler",
        "LTV-817 SOP-4 optocoupler"
    ]
)

# 5. NTC Thermistor
logger.info("\n5. NTC THERMISTOR")
ntc = source_part_safe(
    query="10k ohm NTC thermistor 0805 B3950",
    role="temperature_sensor",
    policy=SourcingPolicy.for_passive(),
    fallback_queries=[
        "10k NTC 0603 thermistor B3435",
        "10k NTC 1206 thermistor temperature sensor",
        "10k NTC thermistor radial"
    ]
)

# 6. Voltage divider resistors
# For 12V → 3.3V: need ratio of 3.3/12 = 0.275
# Standard: R1=27kΩ (top), R2=10kΩ (bottom) gives 10/(10+27) = 0.270 → 3.24V from 12V
logger.info("\n6. VOLTAGE DIVIDER RESISTORS")
r_low = source_part_safe(
    query="10k ohm 1% 0.1W 0603 resistor",
    role="vdiv_low",
    policy=SourcingPolicy.for_passive(),
    fallback_queries=[
        "10k 1% 0805 resistor",
        "10k 5% 0603 resistor"
    ]
)

r_high = source_part_safe(
    query="27k ohm 1% 0.1W 0603 resistor",
    role="vdiv_high",
    policy=SourcingPolicy.for_passive(),
    fallback_queries=[
        "27k 1% 0805 resistor",
        "30k 1% 0603 resistor",
        "27k 5% 0603 resistor"
    ]
)

# 7. Additional passives for current sense amplifier circuit
logger.info("\n7. CURRENT SENSE FILTER CAPACITOR")
filter_cap = source_part_safe(
    query="100nF 50V X7R 0603 ceramic capacitor",
    role="current_sense_filter_cap",
    policy=SourcingPolicy.for_passive(),
    fallback_queries=["0.1uF 50V 0805 ceramic capacitor"]
)

# Save parts.json
parts_json_path = BLOCK_DIR / "parts.json"
logger.info(f"\nWriting parts to {parts_json_path}")

output_data = {
    "parts": sourced_parts,
    "deviations": deviations
}

with open(parts_json_path, 'w') as f:
    json.dump(output_data, f, indent=2)

logger.info(f"✓ Saved to {parts_json_path}")

# Summary
logger.info("\n" + "=" * 80)
logger.info("SOURCING SUMMARY")
logger.info("=" * 80)

sourced_count = sum(1 for v in sourced_parts.values() if "deviation" not in v)
total_count = len(sourced_parts)

logger.info(f"Successfully sourced: {sourced_count}/{total_count} parts")

if deviations:
    logger.warning(f"\nDEVIATIONS ({len(deviations)}):")
    for dev in deviations:
        logger.warning(f"  - {dev}")

for role, part_dict in sourced_parts.items():
    if "deviation" in part_dict:
        logger.error(f"{role}: NOT SOURCED - {part_dict['deviation']}")
    else:
        logger.info(f"{role}:")
        logger.info(f"  LCSC: {part_dict.get('lcsc', 'N/A')}")
        logger.info(f"  Model: {part_dict.get('model', 'N/A')}")
        logger.info(f"  Price: ${part_dict.get('price', 0):.4f}")
        logger.info(f"  Basic: {part_dict.get('basic', False)}")
