"""
Source all parts for PRIMARY_HALF_BRIDGE block.

Requirements:
- 2× GaN FETs (150V, 8A+, RDS(on) < 50mΩ) or fast Si MOSFETs
- 2× Gate resistors (2-10Ω for GaN)
- 2× Source-to-gate resistors (10k-100k typical)
- 1× Bootstrap capacitor (0.1-1uF, 25V+)
"""

from pathlib import Path
import json
from circuit_synth.manufacturing.sourcing import SourcingPolicy, source_and_import

# Project directory
project_dir = Path("C:/Users/pache/AnyAria/llc_48v_12v_120w")
parts = {}

# 1. GaN FET - primary switching device (try GaN first, fallback to MOSFET)
print("Sourcing GaN FETs (150V, 8A+, RDS(on) < 50mΩ)...")
try:
    gan_fet = source_and_import(
        "GaN FET N-channel 150V 8A RDS(on) <50mΩ DFN",
        role="Primary half-bridge switching FET (Q1 high-side, Q2 low-side)",
        project_dir=project_dir,
        policy=SourcingPolicy.for_anchor(),  # This is the anchor part
    )
    parts["Q_GAN_FET"] = gan_fet.to_dict()
    parts["Q_GAN_FET"]["quantity"] = 2
    print(f"✓ Found GaN FET: {gan_fet.part.model} (LCSC: {gan_fet.part.lcsc})")
except Exception as e:
    print(f"⚠ GaN FET not found: {e}")
    print("Falling back to fast Si MOSFET...")

    # Fallback to fast low-Qg Si MOSFET
    mosfet = source_and_import(
        "MOSFET N-channel 150V 10A RDS(on) <50mΩ low Qg SO-8",
        role="Primary half-bridge switching FET (GaN fallback)",
        project_dir=project_dir,
        policy=SourcingPolicy.for_anchor(),
    )
    parts["Q_MOSFET"] = mosfet.to_dict()
    parts["Q_MOSFET"]["quantity"] = 2
    parts["Q_MOSFET"]["deviation"] = "GaN FET not available in JLCPCB; using fast Si MOSFET. Efficiency may drop 1-2%."
    print(f"✓ Found MOSFET: {mosfet.part.model} (LCSC: {mosfet.part.lcsc})")

# 2. Gate resistors (5Ω typical for GaN, damping and slow down turn-on)
print("\nSourcing gate resistors (5Ω)...")
rgate = source_and_import(
    "5.1 ohm 0603 1% 0.1W resistor",
    role="Gate drive resistor, limits di/dt and reduces ringing",
    project_dir=project_dir,
    policy=SourcingPolicy.for_passive(),
)
parts["R_GATE"] = rgate.to_dict()
parts["R_GATE"]["quantity"] = 2
print(f"✓ Found gate resistor: {rgate.part.value} (LCSC: {rgate.part.lcsc})")

# 3. Source-to-gate resistors (keeps gate low when driver is floating)
print("\nSourcing source-to-gate resistors (10kΩ)...")
rsg = source_and_import(
    "10k 0603 1% 0.1W resistor",
    role="Source-to-gate pull-down, prevents floating gate",
    project_dir=project_dir,
    policy=SourcingPolicy.for_passive(),
)
parts["R_SG"] = rsg.to_dict()
parts["R_SG"]["quantity"] = 2
print(f"✓ Found S-G resistor: {rsg.part.value} (LCSC: {rsg.part.lcsc})")

# 4. Bootstrap capacitor (for high-side gate driver)
print("\nSourcing bootstrap capacitor (0.1-1uF, 25V+)...")
cboot = source_and_import(
    "0.47uF 0805 X7R 25V ceramic capacitor",
    role="Bootstrap capacitor for high-side gate driver",
    project_dir=project_dir,
    policy=SourcingPolicy.for_passive(),
)
parts["C_BOOT"] = cboot.to_dict()
parts["C_BOOT"]["quantity"] = 1
print(f"✓ Found bootstrap cap: {cboot.part.value} (LCSC: {cboot.part.lcsc})")

# 5. Optional: Snubber components (RC across drain-source for ringing suppression)
# Typically 10Ω + 1nF for GaN FETs at this power level
print("\nSourcing snubber resistor (10Ω)...")
rsnub = source_and_import(
    "10 ohm 0603 5% 0.1W resistor",
    role="Snubber resistor (optional, for ringing suppression)",
    project_dir=project_dir,
    policy=SourcingPolicy.for_passive(),
)
parts["R_SNUB"] = rsnub.to_dict()
parts["R_SNUB"]["quantity"] = 2
parts["R_SNUB"]["optional"] = True
print(f"✓ Found snubber resistor: {rsnub.part.value} (LCSC: {rsnub.part.lcsc})")

print("\nSourcing snubber capacitor (1nF, 100V)...")
csnub = source_and_import(
    "1nF 0603 C0G 100V ceramic capacitor",
    role="Snubber capacitor (optional, for ringing suppression)",
    project_dir=project_dir,
    policy=SourcingPolicy.for_passive(),
)
parts["C_SNUB"] = csnub.to_dict()
parts["C_SNUB"]["quantity"] = 2
parts["C_SNUB"]["optional"] = True
print(f"✓ Found snubber cap: {csnub.part.value} (LCSC: {csnub.part.lcsc})")

# Write parts.json
parts_json_path = project_dir / "blocks" / "PRIMARY_HALF_BRIDGE" / "parts.json"
parts_json_path.parent.mkdir(parents=True, exist_ok=True)

with open(parts_json_path, "w") as f:
    json.dump(parts, f, indent=2)

print(f"\n✓ Parts sourcing complete. Saved to {parts_json_path}")

# Print summary
print("\n" + "="*60)
print("PRIMARY_HALF_BRIDGE Parts Summary:")
print("="*60)
for part_name, part_data in parts.items():
    qty = part_data.get("quantity", 1)
    optional = part_data.get("optional", False)
    deviation = part_data.get("deviation", None)
    status = "[OPTIONAL]" if optional else ""
    if deviation:
        status += f" [DEVIATION: {deviation}]"

    print(f"{part_name} ({qty}×): {part_data.get('model', 'N/A')} - LCSC {part_data.get('lcsc', 'N/A')} {status}")
