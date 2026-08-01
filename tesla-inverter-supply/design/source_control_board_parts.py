"""
Source all parts for Tesla Inverter Supply control board from JLCPCB.

This script searches JLCPCB's catalog for each required component and records:
- LCSC number
- Basic/Extended status
- Stock quantity
- Unit price
- Part specifications
"""

from pathlib import Path
from circuit_synth.manufacturing.sourcing import SourcingPolicy, source_and_import
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

project_dir = Path("C:/Users/pache/AnyAria/tesla-inverter-supply")
project_dir.mkdir(parents=True, exist_ok=True)

# Results storage
sourcing_results = {}
sourcing_failures = []

def search_part(description: str, role: str, policy: SourcingPolicy):
    """Search for a part and record results."""
    logger.info(f"\n{'='*80}")
    logger.info(f"Searching: {description}")
    logger.info(f"Role: {role}")
    logger.info(f"{'='*80}")

    try:
        part = source_and_import(
            description,
            role=role,
            project_dir=project_dir,
            policy=policy
        )

        result = {
            'description': description,
            'role': role,
            'lcsc': part.part.lcsc,
            'mpn': part.part.model,
            'manufacturer': part.part.manufacturer,
            'basic_extended': 'Basic' if part.part.is_basic else 'Extended',
            'stock': part.part.stock,
            'price': part.part.price,
            'symbol': part.symbol,
            'footprint': part.footprint,
            'package': getattr(part.part, 'package', 'N/A'),
        }

        sourcing_results[description] = result

        logger.info(f"✓ FOUND: {part.part.model}")
        logger.info(f"  LCSC: {part.part.lcsc}")
        logger.info(f"  Status: {'Basic' if part.part.is_basic else 'Extended'}")
        logger.info(f"  Stock: {part.part.stock:,}")
        logger.info(f"  Price: ${part.part.price:.4f}")
        logger.info(f"  Footprint: {part.footprint}")

        return result

    except Exception as e:
        logger.error(f"✗ FAILED: {description}")
        logger.error(f"  Error: {str(e)}")
        sourcing_failures.append({
            'description': description,
            'role': role,
            'error': str(e)
        })
        return None


# ============================================================================
# 1. ACTIVE COMPONENTS (Anchor parts - allow Extended, higher price)
# ============================================================================

logger.info("\n" + "="*80)
logger.info("SECTION 1: MICROCONTROLLERS AND ACTIVE ICs")
logger.info("="*80)

anchor_policy = SourcingPolicy.for_anchor()

# 1. RP2040
search_part(
    "RP2040 microcontroller QFN-56",
    role="Main control processor for current limiter and HMI",
    policy=anchor_policy
)

# 2. MCP2515 CAN controller
search_part(
    "MCP2515 CAN controller SOIC-18 SPI interface",
    role="CAN bus controller for optional Tesla inverter communication",
    policy=anchor_policy
)

# 3. CAN transceiver
search_part(
    "TJA1050 CAN transceiver SOIC-8",
    role="CAN physical layer transceiver",
    policy=anchor_policy
)

# Try alternative if TJA1050 not available
if "TJA1050 CAN transceiver SOIC-8" in [f['description'] for f in sourcing_failures]:
    search_part(
        "SN65HVD230 CAN transceiver SOIC-8",
        role="CAN physical layer transceiver (alternative to TJA1050)",
        policy=anchor_policy
    )

# 11. P-channel MOSFET for ideal diode
search_part(
    "P-channel MOSFET SOT-23 -20V Vgs 3A continuous",
    role="Ideal diode for 15V auxiliary rail reverse protection",
    policy=anchor_policy
)

# 12. N-channel MOSFET for relay drivers
search_part(
    "N-channel MOSFET SOT-23 logic level 30V 1A",
    role="Relay and contactor driver",
    policy=anchor_policy
)

# 13. Voltage reference
search_part(
    "LM4040 2.5V voltage reference SOT-23 0.1% tolerance",
    role="ADC voltage reference for precision current measurement",
    policy=anchor_policy
)

# Try 5V reference as alternative
search_part(
    "LM4040 5.0V voltage reference SOT-23 0.1% tolerance",
    role="ADC voltage reference 5V (alternative)",
    policy=anchor_policy
)

# 14. Isolated amplifier
search_part(
    "AMC1301 isolated amplifier SOIC-8 4kV isolation",
    role="HV DC bus voltage sensing with 4kV isolation",
    policy=anchor_policy
)

# Try alternative isolated amplifier
if "AMC1301 isolated amplifier SOIC-8 4kV isolation" in [f['description'] for f in sourcing_failures]:
    search_part(
        "ISO amplifier 3kV isolation SOIC-8 analog output",
        role="HV voltage sensing isolation amplifier (alternative)",
        policy=anchor_policy
    )

# ============================================================================
# 2. CONNECTORS (may need Extended, moderate price)
# ============================================================================

logger.info("\n" + "="*80)
logger.info("SECTION 2: CONNECTORS")
logger.info("="*80)

# 6. USB-C connector
search_part(
    "USB Type-C 16-pin receptacle SMT mid-mount",
    role="Configuration and data logging interface",
    policy=anchor_policy
)

# ============================================================================
# 3. DISCRETE COMPONENTS (Should be Basic, low cost)
# ============================================================================

logger.info("\n" + "="*80)
logger.info("SECTION 3: DISCRETE COMPONENTS")
logger.info("="*80)

passive_policy = SourcingPolicy.for_passive()

# 10. Schottky diode
search_part(
    "Schottky diode DO-201AD 10A 40V",
    role="Reverse polarity protection for HV output",
    policy=passive_policy
)

# Try SMT version if through-hole not Basic
search_part(
    "Schottky diode SMA 5A 40V",
    role="Reverse polarity protection SMT version",
    policy=passive_policy
)

# 15. NTC thermistor
search_part(
    "NTC thermistor 10k 1% 3950K 0805",
    role="Temperature sensing for thermal shutdown",
    policy=passive_policy
)

# ============================================================================
# 4. HIGH VOLTAGE COMPONENTS
# ============================================================================

logger.info("\n" + "="*80)
logger.info("SECTION 4: HIGH VOLTAGE COMPONENTS")
logger.info("="*80)

# 8. High voltage resistors for divider
search_part(
    "1M 0805 1% 1/4W thick film resistor 500V",
    role="HV voltage divider upper leg (high voltage rated)",
    policy=passive_policy
)

search_part(
    "10k 0805 1% 1/8W thick film resistor",
    role="HV voltage divider lower leg",
    policy=passive_policy
)

# ============================================================================
# 5. MODULES (Not expected in JLCPCB - document as external)
# ============================================================================

logger.info("\n" + "="*80)
logger.info("SECTION 5: MODULES (External sourcing expected)")
logger.info("="*80)

# These are not expected to be in JLCPCB catalog - document as external parts

external_parts = [
    {
        'description': '128x64 OLED display module I2C SSD1306',
        'role': 'User interface display',
        'source': 'External (Adafruit, Waveshare, or similar)',
        'reason': 'Complete assembled display modules not in JLCPCB PCBA catalog',
        'typical_price': '$5-10',
        'interface': '4-pin I2C (VCC, GND, SCL, SDA)'
    },
    {
        'description': 'Hall effect current sensor ±50A closed-loop',
        'role': 'Isolated current sensing for programmable trip',
        'source': 'External (LEM HASS 50-S, ACS770, or similar)',
        'reason': 'High-current Hall sensors are modules, not SMT parts',
        'typical_price': '$15-30',
        'interface': 'Analog output 0-5V proportional to current'
    },
    {
        'description': 'Rotary encoder with switch',
        'role': 'Current limit adjustment',
        'source': 'External (Bourns PEC11, Alps EC11, or similar)',
        'reason': 'Mechanical encoders typically through-hole, hand-soldered',
        'typical_price': '$2-5',
        'interface': 'Quadrature A/B outputs + push switch'
    },
    {
        'description': 'Isolated DC-DC 400V to 5V/15V',
        'role': 'Control board power from HV bus',
        'source': 'External (MORNSUN, RECOM, MuRata)',
        'reason': 'HV input DC-DC converters are modules',
        'typical_price': '$20-40',
        'interface': 'Through-hole or wire leads'
    }
]

logger.info("\nExternal parts (not in JLCPCB PCBA catalog):")
for ext_part in external_parts:
    logger.info(f"\n  • {ext_part['description']}")
    logger.info(f"    Role: {ext_part['role']}")
    logger.info(f"    Source: {ext_part['source']}")
    logger.info(f"    Reason: {ext_part['reason']}")
    logger.info(f"    Typical Price: {ext_part['typical_price']}")

# ============================================================================
# SAVE RESULTS
# ============================================================================

output = {
    'sourced_from_jlcpcb': sourcing_results,
    'external_parts': external_parts,
    'failures': sourcing_failures,
    'summary': {
        'jlcpcb_parts_found': len(sourcing_results),
        'external_parts_required': len(external_parts),
        'search_failures': len(sourcing_failures)
    }
}

output_file = project_dir / 'design' / 'control_board_parts.json'
output_file.parent.mkdir(parents=True, exist_ok=True)

with open(output_file, 'w') as f:
    json.dump(output, f, indent=2)

logger.info(f"\n{'='*80}")
logger.info("SOURCING COMPLETE")
logger.info(f"{'='*80}")
logger.info(f"Results saved to: {output_file}")
logger.info(f"  JLCPCB parts found: {len(sourcing_results)}")
logger.info(f"  External parts required: {len(external_parts)}")
logger.info(f"  Search failures: {len(sourcing_failures)}")

# Print summary table
logger.info(f"\n{'='*80}")
logger.info("JLCPCB PARTS SUMMARY")
logger.info(f"{'='*80}")
logger.info(f"{'Description':<50} {'LCSC':<12} {'Status':<10} {'Stock':<10} {'Price':<10}")
logger.info("-" * 92)

for desc, part in sourcing_results.items():
    logger.info(f"{desc[:48]:<50} {part['lcsc']:<12} {part['basic_extended']:<10} {part['stock']:>8,}  ${part['price']:>7.4f}")

if sourcing_failures:
    logger.info(f"\n{'='*80}")
    logger.info("SEARCH FAILURES")
    logger.info(f"{'='*80}")
    for failure in sourcing_failures:
        logger.info(f"  ✗ {failure['description']}")
        logger.info(f"    {failure['error']}")
