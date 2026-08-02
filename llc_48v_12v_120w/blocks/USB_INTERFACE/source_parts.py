"""Source parts for USB_INTERFACE block from JLCPCB."""

from pathlib import Path
from circuit_synth.manufacturing.sourcing import SourcingPolicy, source_and_import
import json

PROJECT_DIR = Path(__file__).parent.parent.parent

sourced_parts = {}

print("=" * 80)
print("USB_INTERFACE Block - Part Sourcing")
print("=" * 80)

# 1. USB Type-C receptacle (16-pin, power + data)
# Try known JLCPCB part numbers
print("\n1. USB Type-C Receptacle (16-pin SMT)")
try:
    usb_conn = source_and_import(
        "TYPE-C-31-M-12",  # Common USB-C part in JLCPCB
        role="USB data connector",
        project_dir=PROJECT_DIR,
        policy=SourcingPolicy.for_anchor(),  # Connector, allow Extended
    )
    sourced_parts["USB_CONNECTOR"] = usb_conn.to_dict()
    print(f"   ✓ {usb_conn.part.model} - {usb_conn.part.lcsc}")
    print(f"     Price: ${usb_conn.part.price:.4f} | Stock: {usb_conn.part.stock} | {usb_conn.part.kind}")
except Exception as e:
    print(f"   ✗ Failed: {e}")

# 2. USB ESD protection (SOT-23-6, bi-directional)
# USBLC6-2SC6 is the industry standard
print("\n2. USB ESD Protection (USBLC6-2SC6 equivalent)")
try:
    esd_prot = source_and_import(
        "USBLC6",  # Search for USBLC6 family
        role="USB D+/D- ESD protection",
        project_dir=PROJECT_DIR,
        policy=SourcingPolicy.for_anchor(),  # May be Extended
    )
    sourced_parts["ESD_PROTECTION"] = esd_prot.to_dict()
    print(f"   ✓ {esd_prot.part.model} - {esd_prot.part.lcsc}")
    print(f"     Price: ${esd_prot.part.price:.4f} | Stock: {esd_prot.part.stock} | {esd_prot.part.kind}")
except Exception as e:
    print(f"   ✗ Failed: {e}")

# 3. Ferrite bead (0805, for shield ground connection)
print("\n3. Ferrite Bead (0805, 600Ω @ 100MHz)")
try:
    ferrite = source_and_import(
        "BLM21PG",  # Common TDK ferrite bead series
        role="USB shield ground filtering",
        project_dir=PROJECT_DIR,
        policy=SourcingPolicy.for_passive(),
    )
    sourced_parts["FERRITE_BEAD"] = ferrite.to_dict()
    print(f"   ✓ {ferrite.part.model} - {ferrite.part.lcsc}")
    print(f"     Price: ${ferrite.part.price:.4f} | Stock: {ferrite.part.stock} | {ferrite.part.kind}")
except Exception as e:
    print(f"   ✗ Failed: {e}")

# 4. Series resistors for D+/D- (27Ω typical, but 33Ω is acceptable)
# RP2040 datasheet shows 27Ω or 33Ω for series termination
print("\n4. USB Series Resistors (33Ω 0603 1% - RP2040 recommended range)")
try:
    usb_resistor = source_and_import(
        "33 0603 1%",  # 33Ω is within RP2040 spec (27-33Ω)
        role="USB D+/D- series termination",
        project_dir=PROJECT_DIR,
        policy=SourcingPolicy.for_passive(),
    )
    sourced_parts["USB_SERIES_R"] = usb_resistor.to_dict()
    sourced_parts["USB_SERIES_R"]["quantity"] = 2  # Need 2× (one for D+, one for D-)
    print(f"   ✓ {usb_resistor.part.model} - {usb_resistor.part.lcsc}")
    print(f"     Price: ${usb_resistor.part.price:.4f} | Stock: {usb_resistor.part.stock} | {usb_resistor.part.kind}")
except Exception as e:
    print(f"   ✗ Failed: {e}")

# 5. Shield ground resistor (1M, optional for discharge)
print("\n5. Shield Ground Resistor (1MΩ 0603 1%)")
try:
    shield_r = source_and_import(
        "1M 0603 1%",  # Simplified search
        role="USB shield discharge to ground",
        project_dir=PROJECT_DIR,
        policy=SourcingPolicy.for_passive(),
    )
    sourced_parts["SHIELD_R"] = shield_r.to_dict()
    print(f"   ✓ {shield_r.part.model} - {shield_r.part.lcsc}")
    print(f"     Price: ${shield_r.part.price:.4f} | Stock: {shield_r.part.stock} | {shield_r.part.kind}")
except Exception as e:
    print(f"   ✗ Failed: {e}")

# Save parts list to JSON
parts_file = Path(__file__).parent / "parts.json"
with open(parts_file, 'w') as f:
    json.dump(sourced_parts, f, indent=2)

print("\n" + "=" * 80)
print(f"Sourced {len(sourced_parts)} parts")
print(f"Parts list saved to: {parts_file}")
print("=" * 80)
