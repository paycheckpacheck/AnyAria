#!/usr/bin/env python3
"""
Source all parts for DISCRETE_LLC_CONTROLLER block from JLCPCB catalog.
This is a complex analog control loop requiring precision comparators, op-amps,
VCO, logic gates, optocoupler isolation, and gate driver.
"""

import json
import logging
from pathlib import Path
from circuit_synth.manufacturing.sourcing import SourcingPolicy, source_and_import

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).parent.parent.parent
BLOCK_DIR = Path(__file__).parent

# Parts list with specific requirements
parts_to_source = [
    # Comparators - for current-mode comparator, window detection
    {
        "query": "LM393 dual comparator SOIC-8 rail-to-rail",
        "role": "current-mode comparator",
        "policy": SourcingPolicy.for_anchor(),  # Critical for control loop
    },
    {
        "query": "LM339 quad comparator SOIC-14 rail-to-rail",
        "role": "auxiliary comparators for protection",
        "policy": SourcingPolicy.for_passive(),  # Not as critical
    },

    # Op-amps - for error amplifier, current sense amp, slope compensation
    {
        "query": "TL072 dual JFET op-amp SOIC-8 low-noise",
        "role": "error amplifier for voltage feedback loop",
        "policy": SourcingPolicy.for_anchor(),  # Critical for control loop
    },
    {
        "query": "LM358 dual op-amp SOIC-8 general-purpose",
        "role": "current sense amplifier and slope compensation ramp",
        "policy": SourcingPolicy.for_passive(),  # General purpose
    },

    # VCO - voltage-controlled oscillator for frequency modulation
    {
        "query": "CD4046 PLL VCO SOIC-16 phase-locked-loop",
        "role": "voltage-controlled oscillator 100-500kHz",
        "policy": SourcingPolicy.for_anchor(),  # Core of frequency control
    },

    # Logic gates - for RS latch and dead-time generation
    {
        "query": "74HC74 dual D flip-flop SOIC-14 74HC74D",
        "role": "RS latch for PWM generation",
        "policy": SourcingPolicy.for_passive(),  # Basic logic
    },
    {
        "query": "74HC00 quad NAND gate SOIC-14 74HC00D",
        "role": "dead-time logic generation",
        "policy": SourcingPolicy.for_passive(),  # Basic logic
    },
    {
        "query": "74HC14 hex Schmitt trigger inverter SOIC-14 74HC14D",
        "role": "signal conditioning and noise immunity",
        "policy": SourcingPolicy.for_passive(),  # Basic logic
    },

    # Isolation - optocoupler for feedback from secondary to primary
    {
        "query": "PC817 optocoupler DIP-4 CTR>50%",
        "role": "isolated feedback from secondary to primary",
        "policy": SourcingPolicy.for_passive(),  # Very common part
    },

    # Gate driver - critical for GaN FET switching
    {
        "query": "IR2110 half-bridge gate driver SOIC-16 600V bootstrap",
        "role": "high-side and low-side gate driver for primary GaN FETs",
        "policy": SourcingPolicy.for_anchor(),  # Critical for power stage
    },

    # Voltage reference - for secondary-side feedback
    {
        "query": "TL431 adjustable shunt regulator SOT-23 precision",
        "role": "secondary-side voltage reference for feedback",
        "policy": SourcingPolicy.for_passive(),  # Very common part
    },
]

def main():
    sourced_parts = {}
    deviations = []

    logger.info(f"Sourcing {len(parts_to_source)} parts for DISCRETE_LLC_CONTROLLER")
    logger.info(f"Project directory: {PROJECT_DIR}")

    for item in parts_to_source:
        query = item["query"]
        role = item["role"]
        policy = item["policy"]

        logger.info(f"\n{'='*80}")
        logger.info(f"Sourcing: {query}")
        logger.info(f"Role: {role}")

        try:
            sourced = source_and_import(
                query=query,
                role=role,
                project_dir=PROJECT_DIR,
                policy=policy,
            )

            # Store the sourced part
            part_key = sourced.part.model or query.split()[0]
            sourced_parts[part_key] = sourced.to_dict()

            logger.info(f"✓ Sourced: {sourced.part.model} (LCSC: {sourced.part.lcsc})")
            logger.info(f"  Price: ${sourced.part.price:.4f} | Stock: {sourced.part.stock}")
            logger.info(f"  Category: {sourced.part.category}")
            logger.info(f"  Symbol: {sourced.symbol}")
            logger.info(f"  Footprint: {sourced.footprint}")

        except Exception as e:
            logger.error(f"✗ Failed to source: {query}")
            logger.error(f"  Error: {e}")
            deviations.append({
                "query": query,
                "role": role,
                "error": str(e),
                "impact": "BLOCKING - cannot assemble without this part"
            })

    # Write parts.json
    parts_json_path = BLOCK_DIR / "parts.json"
    with open(parts_json_path, 'w') as f:
        json.dump(sourced_parts, f, indent=2)
    logger.info(f"\n✓ Wrote {len(sourced_parts)} parts to {parts_json_path}")

    # Write deviations if any
    if deviations:
        deviations_path = BLOCK_DIR / "deviations.json"
        with open(deviations_path, 'w') as f:
            json.dump(deviations, f, indent=2)
        logger.warning(f"\n⚠ {len(deviations)} deviations recorded to {deviations_path}")
        logger.warning("These parts could not be sourced from JLCPCB.")
        logger.warning("Board cannot be assembled without resolving these.")

    # Summary
    logger.info(f"\n{'='*80}")
    logger.info("SOURCING SUMMARY")
    logger.info(f"Total parts requested: {len(parts_to_source)}")
    logger.info(f"Successfully sourced: {len(sourced_parts)}")
    logger.info(f"Deviations (failures): {len(deviations)}")

    if len(sourced_parts) == len(parts_to_source):
        logger.info("\n✓ ALL PARTS SOURCED - Block is JLCPCB-assemblable")
        return 0
    else:
        logger.error("\n✗ INCOMPLETE SOURCING - Board cannot be assembled as designed")
        return 1

if __name__ == "__main__":
    exit(main())
