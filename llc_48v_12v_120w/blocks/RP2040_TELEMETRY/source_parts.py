#!/usr/bin/env python3
"""Source all parts for RP2040_TELEMETRY block from JLCPCB."""

from pathlib import Path
from circuit_synth.manufacturing.sourcing import SourcingPolicy, source_and_import
import json

PROJECT_DIR = Path(__file__).parent.parent.parent
BLOCK_DIR = Path(__file__).parent

def source_all_parts():
    """Source all parts needed for RP2040_TELEMETRY block."""

    sourced_parts = {}
    deviations = []

    print("=" * 80)
    print("SOURCING PARTS FOR RP2040_TELEMETRY BLOCK")
    print("=" * 80)

    # 1. RP2040 Microcontroller (anchor part)
    print("\n[1/9] Sourcing RP2040 microcontroller...")
    try:
        rp2040 = source_and_import(
            "RP2040 microcontroller QFN-56",
            role="Main microcontroller for telemetry",
            project_dir=PROJECT_DIR,
            policy=SourcingPolicy.for_anchor(),
        )
        sourced_parts['rp2040'] = rp2040.to_dict()
        print(f"✓ Found: {rp2040.part.model} ({rp2040.part.lcsc}) - ${rp2040.part.price}")
    except Exception as e:
        print(f"✗ FAILED: {e}")
        deviations.append(f"RP2040: {e}")

    # 2. 12MHz Crystal for USB
    print("\n[2/9] Sourcing 12MHz crystal...")
    try:
        crystal = source_and_import(
            "12MHz crystal 3225 SMD 20ppm 9pF load",
            role="USB clock reference",
            project_dir=PROJECT_DIR,
            policy=SourcingPolicy.for_passive(),
        )
        sourced_parts['crystal_12mhz'] = crystal.to_dict()
        print(f"✓ Found: {crystal.part.model} ({crystal.part.lcsc}) - ${crystal.part.price}")
    except Exception as e:
        print(f"✗ FAILED: {e}")
        deviations.append(f"12MHz crystal: {e}")

    # 3. 100nF decoupling capacitors (0603, X7R, 50V) - 6x needed
    print("\n[3/9] Sourcing 100nF decoupling capacitors...")
    try:
        cap_100n = source_and_import(
            "100nF 0603 X7R 50V ceramic capacitor",
            role="IOVDD/VREG_VIN/DVDD decoupling",
            project_dir=PROJECT_DIR,
            policy=SourcingPolicy.for_passive(),
        )
        sourced_parts['cap_100nf'] = cap_100n.to_dict()
        print(f"✓ Found: {cap_100n.part.model} ({cap_100n.part.lcsc}) - ${cap_100n.part.price} (need 6x)")
    except Exception as e:
        print(f"✗ FAILED: {e}")
        deviations.append(f"100nF capacitor: {e}")

    # 4. 10µF bulk capacitors (0805, X7R, 25V) - 2x needed
    print("\n[4/9] Sourcing 10µF bulk capacitors...")
    try:
        cap_10u = source_and_import(
            "10uF 0805 X7R 25V ceramic capacitor",
            role="Bulk decoupling for supplies",
            project_dir=PROJECT_DIR,
            policy=SourcingPolicy.for_passive(),
        )
        sourced_parts['cap_10uf'] = cap_10u.to_dict()
        print(f"✓ Found: {cap_10u.part.model} ({cap_10u.part.lcsc}) - ${cap_10u.part.price} (need 2x)")
    except Exception as e:
        print(f"✗ FAILED: {e}")
        deviations.append(f"10µF capacitor: {e}")

    # 5. QSPI Flash (W25Q16JV or similar, 2MB)
    print("\n[5/9] Sourcing W25Q16JV QSPI flash...")
    try:
        flash = source_and_import(
            "W25Q16JVSSIQ 16Mbit QSPI flash SOIC-8 208mil",
            role="Program storage (2MB)",
            project_dir=PROJECT_DIR,
            policy=SourcingPolicy.for_anchor(),
        )
        sourced_parts['flash'] = flash.to_dict()
        print(f"✓ Found: {flash.part.model} ({flash.part.lcsc}) - ${flash.part.price}")
    except Exception as e:
        print(f"✗ FAILED: {e}")
        deviations.append(f"QSPI flash: {e}")

    # 6. 1kΩ resistor for BOOTSEL pull-up
    print("\n[6/9] Sourcing 1kΩ resistor...")
    try:
        res_1k = source_and_import(
            "1k 0603 1% 0.1W resistor",
            role="BOOTSEL pull-up",
            project_dir=PROJECT_DIR,
            policy=SourcingPolicy.for_passive(),
        )
        sourced_parts['res_1k'] = res_1k.to_dict()
        print(f"✓ Found: {res_1k.part.model} ({res_1k.part.lcsc}) - ${res_1k.part.price}")
    except Exception as e:
        print(f"✗ FAILED: {e}")
        deviations.append(f"1kΩ resistor: {e}")

    # 7. 27Ω USB series resistors (2x needed)
    print("\n[7/9] Sourcing 27Ω USB series resistors...")
    try:
        res_27 = source_and_import(
            "27 ohm 0603 1% 0.1W resistor",
            role="USB D+/D- series termination",
            project_dir=PROJECT_DIR,
            policy=SourcingPolicy.for_passive(),
        )
        sourced_parts['res_27'] = res_27.to_dict()
        print(f"✓ Found: {res_27.part.model} ({res_27.part.lcsc}) - ${res_27.part.price} (need 2x)")
    except Exception as e:
        print(f"✗ FAILED: {e}")
        deviations.append(f"27Ω resistor: {e}")

    # 8. Tactile switch for BOOTSEL
    print("\n[8/9] Sourcing tactile switch...")
    try:
        switch = source_and_import(
            "tactile switch SMD 3x4mm 160gf SPST",
            role="BOOTSEL button",
            project_dir=PROJECT_DIR,
            policy=SourcingPolicy.for_passive(),
        )
        sourced_parts['switch_bootsel'] = switch.to_dict()
        print(f"✓ Found: {switch.part.model} ({switch.part.lcsc}) - ${switch.part.price}")
    except Exception as e:
        print(f"✗ FAILED: {e}")
        deviations.append(f"Tactile switch: {e}")

    # 9. 2x3 pin header for SWD
    print("\n[9/9] Sourcing 2x3 pin header...")
    try:
        header = source_and_import(
            "2x3 pin header 2.54mm pitch SMD vertical",
            role="SWD debug connector",
            project_dir=PROJECT_DIR,
            policy=SourcingPolicy.for_passive(),
        )
        sourced_parts['header_swd'] = header.to_dict()
        print(f"✓ Found: {header.part.model} ({header.part.lcsc}) - ${header.part.price}")
    except Exception as e:
        print(f"✗ FAILED: {e}")
        deviations.append(f"2x3 header: {e}")

    # Write parts.json
    print("\n" + "=" * 80)
    print("WRITING parts.json")
    print("=" * 80)

    parts_json = {
        "block": "RP2040_TELEMETRY",
        "parts": sourced_parts,
        "deviations": deviations,
        "part_count": {
            "rp2040": 1,
            "crystal_12mhz": 1,
            "cap_100nf": 6,
            "cap_10uf": 2,
            "flash": 1,
            "res_1k": 1,
            "res_27": 2,
            "switch_bootsel": 1,
            "header_swd": 1,
        },
        "total_parts": 16,
    }

    parts_file = BLOCK_DIR / "parts.json"
    with open(parts_file, 'w') as f:
        json.dump(parts_json, f, indent=2)

    print(f"\n✓ Wrote {parts_file}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Parts sourced: {len(sourced_parts)}/9")
    print(f"Deviations: {len(deviations)}")

    if deviations:
        print("\nDEVIATIONS:")
        for dev in deviations:
            print(f"  - {dev}")

    # Calculate cost
    total_cost = 0.0
    for part_key, part_data in sourced_parts.items():
        qty = parts_json["part_count"].get(part_key, 1)
        price = part_data.get("part", {}).get("price", 0.0)
        total_cost += price * qty

    print(f"\nEstimated part cost: ${total_cost:.2f} (for {parts_json['total_parts']} parts)")

    return sourced_parts, deviations

if __name__ == "__main__":
    source_all_parts()
