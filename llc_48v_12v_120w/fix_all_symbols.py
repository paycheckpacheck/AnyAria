#!/usr/bin/env python
"""Automated fix for symbol library mismatches in all blocks.

Reads parts.json from each block and updates block.py to use the correct
JLC-imported symbols instead of generic KiCad symbols.
"""

import json
import re
from pathlib import Path

def fix_block_symbols(block_dir):
    """Fix symbol references in one block's block.py file."""

    block_py = block_dir / "block.py"
    parts_json = block_dir / "parts.json"

    if not block_py.exists():
        print(f"  ⚠️  {block_dir.name}: block.py not found")
        return 0

    if not parts_json.exists():
        print(f"  ⚠️  {block_dir.name}: parts.json not found")
        return 0

    # Load parts.json to get correct symbols
    with open(parts_json, 'r') as f:
        parts_data = json.load(f)

    # Build mapping of MPN -> (symbol, footprint)
    symbol_map = {}
    for part in parts_data.get('parts', []):
        mpn = part.get('mpn') or part.get('MPN')
        lcsc = part.get('lcsc') or part.get('LCSC')
        symbol = part.get('symbol')
        footprint = part.get('footprint')

        if mpn and symbol and footprint:
            symbol_map[mpn] = {
                'symbol': symbol,
                'footprint': footprint,
                'lcsc': lcsc
            }

    if not symbol_map:
        print(f"  ℹ️  {block_dir.name}: No symbols to fix (no parts in parts.json)")
        return 0

    # Read block.py
    with open(block_py, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    fixes_made = 0

    # Find all Component() declarations and fix symbols
    # Pattern: symbol="Library:Symbol"
    for mpn, part_info in symbol_map.items():
        # Look for MPN="..." to find the Component() call
        mpn_pattern = rf'MPN\s*=\s*["\']({re.escape(mpn)})["\']'

        for match in re.finditer(mpn_pattern, content, re.IGNORECASE):
            # Find the Component() call containing this MPN
            # Work backwards to find "Component("
            start = content.rfind("Component(", 0, match.start())
            if start == -1:
                continue

            # Find the closing parenthesis
            end = content.find(")", match.end())
            if end == -1:
                continue

            component_block = content[start:end+1]

            # Check if this needs fixing (has wrong symbol)
            if 'symbol=' in component_block and 'JLCImport:' not in component_block:
                # Extract current symbol
                symbol_match = re.search(r'symbol\s*=\s*["\']([^"\']+)["\']', component_block)
                if symbol_match:
                    old_symbol = symbol_match.group(1)
                    new_symbol = part_info['symbol']

                    # Replace symbol
                    new_component_block = component_block.replace(
                        f'symbol="{old_symbol}"',
                        f'symbol="{new_symbol}"'
                    ).replace(
                        f"symbol='{old_symbol}'",
                        f'symbol="{new_symbol}"'
                    )

                    # Replace footprint if needed
                    footprint_match = re.search(r'footprint\s*=\s*["\']([^"\']+)["\']', component_block)
                    if footprint_match:
                        old_footprint = footprint_match.group(1)
                        new_footprint = part_info['footprint']
                        new_component_block = new_component_block.replace(
                            f'footprint="{old_footprint}"',
                            f'footprint="{new_footprint}"'
                        ).replace(
                            f"footprint='{old_footprint}'",
                            f'footprint="{new_footprint}"'
                        )

                    content = content.replace(component_block, new_component_block)
                    fixes_made += 1
                    print(f"    ✓ {mpn}: {old_symbol} → {new_symbol}")

    if fixes_made > 0:
        # Write back
        with open(block_py, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  ✅ {block_dir.name}: Fixed {fixes_made} symbol(s)")
    else:
        print(f"  ✓  {block_dir.name}: No fixes needed")

    return fixes_made

def main():
    blocks_dir = Path("blocks")

    if not blocks_dir.exists():
        print("❌ blocks/ directory not found")
        print("   Run this script from the llc_48v_12v_120w directory")
        return 1

    print("🔧 Automated Symbol Fix")
    print("=" * 60)
    print()

    total_fixes = 0
    blocks_fixed = 0

    for block_dir in sorted(blocks_dir.iterdir()):
        if block_dir.is_dir():
            print(f"📦 {block_dir.name}")
            fixes = fix_block_symbols(block_dir)
            if fixes > 0:
                blocks_fixed += 1
                total_fixes += fixes
            print()

    print("=" * 60)
    print(f"✅ Complete: {total_fixes} symbols fixed in {blocks_fixed} blocks")
    print()
    print("Next step: Run generate_kicad.py")

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
