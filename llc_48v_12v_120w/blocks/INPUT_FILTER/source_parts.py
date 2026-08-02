"""Source all parts for INPUT_FILTER block from JLCPCB catalog."""
from pathlib import Path
from circuit_synth.manufacturing.sourcing import SourcingPolicy, source_and_import
import json

project_dir = Path(__file__).parent.parent.parent
parts_sourced = {}

print("=" * 80)
print("INPUT_FILTER Block - Part Sourcing")
print("=" * 80)

# 1. TVS Diode - 58V breakdown for 48V input protection
print("\n1. TVS Diode (58V breakdown, overvoltage protection)")
try:
    tvs = source_and_import(
        "SMBJ58",
        role="Input overvoltage protection",
        project_dir=project_dir,
        policy=SourcingPolicy.for_anchor()
    )
    parts_sourced['TVS'] = tvs.to_dict()
    print(f"   ✓ {tvs.part.model} - {tvs.part.lcsc}")
    print(f"     Price: ${tvs.part.price:.4f} | Stock: {tvs.part.stock} | {tvs.part.kind}")
except Exception as e:
    print(f"   ✗ Failed: {e}")

# 2. Bulk Electrolytic Capacitor - SMD aluminum electrolytic
# Note: For 120W @ 48V (2.5A), radial through-hole may not be in basic parts
# Try SMD electrolytic first
print("\n2. Bulk Electrolytic Capacitor (SMD aluminum electrolytic, 63V+)")
try:
    # Relax policy for electrolytic - may need Extended parts
    bulk_policy = SourcingPolicy(min_stock=1000, max_unit_price=0.50, prefer_basic=True)
    bulk_cap = source_and_import(
        "100uF 63V SMD electrolytic capacitor",
        role="Input bulk energy storage",
        project_dir=project_dir,
        policy=bulk_policy
    )
    parts_sourced['BULK_CAP'] = bulk_cap.to_dict()
    parts_sourced['BULK_CAP']['quantity'] = 2  # Use 2× in parallel
    print(f"   ✓ {bulk_cap.part.model} - {bulk_cap.part.lcsc}")
    print(f"     Price: ${bulk_cap.part.price:.4f} | Stock: {bulk_cap.part.stock} | {bulk_cap.part.kind}")
    print(f"     Note: Using 2× 100µF in parallel for 200µF total")
except Exception as e:
    print(f"   ✗ Failed: {e}")

# 3. Ceramic Capacitor 10µF 100V X7R
print("\n3. Ceramic Capacitor 10µF 100V (high-frequency bypass)")
try:
    ceramic_10u = source_and_import(
        "10uF 100V 1206 X7R",
        role="Input high-frequency filtering",
        project_dir=project_dir,
        policy=SourcingPolicy.for_passive()
    )
    parts_sourced['CERAMIC_10U'] = ceramic_10u.to_dict()
    parts_sourced['CERAMIC_10U']['quantity'] = 2  # Use 2× for better ripple handling
    print(f"   ✓ {ceramic_10u.part.model} - {ceramic_10u.part.lcsc}")
    print(f"     Price: ${ceramic_10u.part.price:.4f} | Stock: {ceramic_10u.part.stock} | {ceramic_10u.part.kind}")
except Exception as e:
    print(f"   ✗ Failed: {e}")

# 4. Ceramic Capacitor 1µF 100V X7R
print("\n4. Ceramic Capacitor 1µF 100V (high-frequency bypass)")
try:
    ceramic_1u = source_and_import(
        "1uF 100V 0805 X7R",
        role="Input high-frequency filtering",
        project_dir=project_dir,
        policy=SourcingPolicy.for_passive()
    )
    parts_sourced['CERAMIC_1U'] = ceramic_1u.to_dict()
    parts_sourced['CERAMIC_1U']['quantity'] = 2
    print(f"   ✓ {ceramic_1u.part.model} - {ceramic_1u.part.lcsc}")
    print(f"     Price: ${ceramic_1u.part.price:.4f} | Stock: {ceramic_1u.part.stock} | {ceramic_1u.part.kind}")
except Exception as e:
    print(f"   ✗ Failed: {e}")

# 5. Voltage Divider Resistor - High Side (47k for 48V → 3.3V ADC)
# 48V × (3.3k / (47k + 3.3k)) = 3.14V (safe for 3.3V ADC)
print("\n5. Voltage Divider Resistor - High Side (47k 1% 0603)")
try:
    r_high = source_and_import(
        "47k 0603 1%",
        role="Input voltage sensing - high side",
        project_dir=project_dir,
        policy=SourcingPolicy.for_passive()
    )
    parts_sourced['R_SENSE_HIGH'] = r_high.to_dict()
    print(f"   ✓ {r_high.part.model} - {r_high.part.lcsc}")
    print(f"     Price: ${r_high.part.price:.4f} | Stock: {r_high.part.stock} | {r_high.part.kind}")
except Exception as e:
    print(f"   ✗ Failed: {e}")

# 6. Voltage Divider Resistor - Low Side (3.3k for 48V → 3.3V ADC)
print("\n6. Voltage Divider Resistor - Low Side (3.3k 1% 0603)")
try:
    r_low = source_and_import(
        "3.3k 0603 1%",
        role="Input voltage sensing - low side",
        project_dir=project_dir,
        policy=SourcingPolicy.for_passive()
    )
    parts_sourced['R_SENSE_LOW'] = r_low.to_dict()
    print(f"   ✓ {r_low.part.model} - {r_low.part.lcsc}")
    print(f"     Price: ${r_low.part.price:.4f} | Stock: {r_low.part.stock} | {r_low.part.kind}")
except Exception as e:
    print(f"   ✗ Failed: {e}")

# 7. ADC Filter Capacitor (100nF on ADC input)
print("\n7. ADC Filter Capacitor (100nF 0603 X7R)")
try:
    adc_filter = source_and_import(
        "100nF 0603 X7R 50V",
        role="ADC input filtering",
        project_dir=project_dir,
        policy=SourcingPolicy.for_passive()
    )
    parts_sourced['C_ADC_FILTER'] = adc_filter.to_dict()
    print(f"   ✓ {adc_filter.part.model} - {adc_filter.part.lcsc}")
    print(f"     Price: ${adc_filter.part.price:.4f} | Stock: {adc_filter.part.stock} | {adc_filter.part.kind}")
except Exception as e:
    print(f"   ✗ Failed: {e}")

# 8. Screw Terminal - 2-pin 5mm pitch 10A+ (WJ127 series)
print("\n8. Screw Terminal (2-pin 5mm pitch 15A)")
try:
    terminal = source_and_import(
        "WJ127",
        role="48V power input connector",
        project_dir=project_dir,
        policy=SourcingPolicy.for_anchor()
    )
    parts_sourced['INPUT_TERMINAL'] = terminal.to_dict()
    print(f"   ✓ {terminal.part.model} - {terminal.part.lcsc}")
    print(f"     Price: ${terminal.part.price:.4f} | Stock: {terminal.part.stock} | {terminal.part.kind}")
except Exception as e:
    print(f"   ✗ Failed: {e}")

# Save parts list to JSON
parts_file = Path(__file__).parent / "parts.json"
with open(parts_file, 'w') as f:
    json.dump(parts_sourced, f, indent=2)

print("\n" + "=" * 80)
print(f"Sourced {len(parts_sourced)} parts")
print(f"Parts list saved to: {parts_file}")
print("=" * 80)
