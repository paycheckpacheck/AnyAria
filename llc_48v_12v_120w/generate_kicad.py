#!/usr/bin/env python
"""Generate KiCad project from LLC converter circuit."""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Change to project directory so relative imports work
os.chdir(Path(__file__).parent)

from design.llc_converter import llc_converter

def main():
    project_dir = Path(__file__).parent
    project_name = "LLC_48V_12V_120W"

    print(f"Generating KiCad project: {project_name}")
    print(f"Location: {project_dir}")
    print()

    try:
        # Call the circuit function to get the circuit object
        print("Creating circuit...")
        circuit = llc_converter()
        print(f"✓ Circuit created: {circuit.name}")
        print(f"  Blocks: {len(circuit.blocks)}")
        print(f"  Components: {len(circuit.components)}")
        print(f"  Nets: {len(circuit.nets)}")
        print()

        # Generate KiCad files (method on circuit object)
        print("Generating KiCad project files...")
        result = circuit.generate_kicad_project(
            project_name=project_name,
            generate_pcb=True,
            force_regenerate=True
        )

        print(f"\n✓ KiCad project generated successfully!")
        print(f"\nFiles created:")
        print(f"  - {project_name}.kicad_pro (project file)")
        print(f"  - {project_name}.kicad_sch (root schematic)")
        print(f"  - {project_name}.kicad_pcb (PCB file)")
        for block_name in circuit.blocks.keys():
            print(f"  - {block_name}.kicad_sch (hierarchical sheet)")

        print(f"\nOpen with:")
        print(f"  kicad {project_dir / project_name}.kicad_pro")

        return 0

    except Exception as e:
        print(f"\n✗ Error generating project: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
