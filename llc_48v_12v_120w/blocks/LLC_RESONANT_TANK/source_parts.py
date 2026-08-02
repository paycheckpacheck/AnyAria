#!/usr/bin/env python3
"""Source all parts for LLC_RESONANT_TANK block from JLCPCB catalog."""

from pathlib import Path
from circuit_synth.manufacturing.sourcing import SourcingPolicy, source_and_import, NoAcceptablePart
import json

PROJECT_DIR = Path(__file__).parent.parent.parent
BLOCK_DIR = Path(__file__).parent

def source_resonant_tank_parts():
    """Source resonant capacitor, inductor, and current sense components."""

    parts = {}
    deviations = []

    # 1. Resonant Capacitor Cr: Target ~50-100nF, 250V+, C0G/NP0
    # Reality: High voltage C0G in Basic parts is very rare. We'll search broadly.
    print("Sourcing resonant capacitor Cr...")

    # Start with most relaxed search - just get SOME high-voltage ceramic
    try:
        cr_ceramic = source_and_import(
            "100nF 100V X7R ceramic capacitor",
            role="LLC resonant capacitor",
            project_dir=PROJECT_DIR,
            policy=SourcingPolicy(min_stock=5000, max_unit_price=0.20, allow_extended=True),
        )
        parts["Cr"] = cr_ceramic.to_dict()
        if not cr_ceramic.part.is_basic:
            deviations.append(f"Cr: Extended part {cr_ceramic.part.lcsc} required (no Basic high-voltage ceramic)")
        print(f"  ✓ Ceramic capacitor: {cr_ceramic.part.model} @ {cr_ceramic.part.lcsc} ({cr_ceramic.part.kind})")
    except NoAcceptablePart as e:
        print(f"  ✗ Even relaxed search failed: {e}")
        parts["Cr"] = {"error": str(e), "available": False}
        deviations.append("Cr: NO suitable resonant capacitor found in JLCPCB - CRITICAL BLOCKER")

    # 2. Resonant Inductor Lr: 20-30µH, high current capability
    # Reality: Specific high-current inductors may not be in Basic. Search broadly.
    print("\nSourcing resonant inductor Lr...")
    try:
        # Very broad search - just "power inductor" in the right range
        lr_inductor = source_and_import(
            "22uH power inductor SMD",
            role="LLC resonant inductor",
            project_dir=PROJECT_DIR,
            policy=SourcingPolicy(min_stock=1000, max_unit_price=1.00, allow_extended=True),
        )
        parts["Lr"] = lr_inductor.to_dict()
        if not lr_inductor.part.is_basic:
            deviations.append(f"Lr: Extended part {lr_inductor.part.lcsc} required")
        print(f"  ✓ Inductor: {lr_inductor.part.model} @ {lr_inductor.part.lcsc} ({lr_inductor.part.kind})")
        print(f"    NOTE: Verify current rating >=8Arms in datasheet!")
    except NoAcceptablePart as e:
        print(f"  ✗ Inductor search failed: {e}")
        parts["Lr"] = {"error": str(e), "available": False}
        deviations.append("Lr: Use transformer leakage inductance - no discrete inductor needed (common LLC approach)")

    # 3. Current Sense - Shunt resistor (most likely to be available)
    print("\nSourcing current sense components...")
    try:
        # Low-value, high-power resistor for current sensing
        shunt = source_and_import(
            "10 milliohm 1W 1% resistor",
            role="Resonant current sense shunt",
            project_dir=PROJECT_DIR,
            policy=SourcingPolicy(min_stock=3000, max_unit_price=0.30, allow_extended=True),
        )
        parts["Rsense"] = shunt.to_dict()
        print(f"  ✓ Current shunt: {shunt.part.model} @ {shunt.part.lcsc}")
    except NoAcceptablePart as e:
        print(f"  ✗ Shunt resistor search failed: {e}")
        # Try even broader search
        try:
            shunt_alt = source_and_import(
                "0.01 ohm 2512 resistor",
                role="Resonant current sense shunt (alternative)",
                project_dir=PROJECT_DIR,
                policy=SourcingPolicy(min_stock=1000, max_unit_price=0.50, allow_extended=True),
            )
            parts["Rsense"] = shunt_alt.to_dict()
            print(f"  ✓ Alternative shunt: {shunt_alt.part.model} @ {shunt_alt.part.lcsc}")
        except NoAcceptablePart as e2:
            print(f"  ✗ No current sense resistor found: {e2}")
            parts["Rsense"] = {"error": str(e2), "available": False}
            deviations.append("Rsense: Current transformer required (not in JLCPCB) - hand assembly needed")

    # Write parts.json
    parts_file = BLOCK_DIR / "parts.json"
    with open(parts_file, "w") as f:
        json.dump(parts, f, indent=2)

    print(f"\n✓ Parts sourcing complete. Wrote {parts_file}")

    # Summary
    print("\n=== SOURCING SUMMARY ===")
    available = [k for k, v in parts.items() if isinstance(v, dict) and "lcsc" in v]
    unavailable = [k for k, v in parts.items() if isinstance(v, dict) and "error" in v]

    print(f"Available parts: {len(available)}")
    for part_name in available:
        print(f"  ✓ {part_name}: {parts[part_name].get('mpn', 'unknown')}")

    if unavailable:
        print(f"\nUnavailable parts: {len(unavailable)}")
        for part_name in unavailable:
            print(f"  ✗ {part_name}")

    if deviations:
        print(f"\n=== DEVIATIONS FROM IDEAL ===")
        for dev in deviations:
            print(f"  ! {dev}")

    return parts, deviations

if __name__ == "__main__":
    source_resonant_tank_parts()
