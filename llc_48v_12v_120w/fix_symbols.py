#!/usr/bin/env python
"""Fix symbol references to use JLC-sourced parts where available."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Change to project directory
import os
os.chdir(Path(__file__).parent)

from design.llc_converter import llc_converter

# Import the circuit to trigger symbol loading
# This will show us which symbols are missing

if __name__ == "__main__":
    print("Testing circuit loading...")
    print("If this fails, we know which symbols need to be fixed.\n")

    try:
        circuit = llc_converter()
        print("✓ Circuit loaded successfully!")
        print(f"  Components: {len(circuit.components)}")
        print(f"  Nets: {len(circuit.nets)}")
    except Exception as e:
        print(f"✗ Circuit loading failed: {e}")
        print("\nThe issue is that some blocks use generic KiCad symbols")
        print("instead of the JLC-imported symbols from parts.json")
        print("\nFix: Use symbols from JLCImport library that were imported during part sourcing.")
        sys.exit(1)
