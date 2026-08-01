"""
Install AnyAria KiCad Plugin

Symlinks the plugin into KiCad's plugin directory.
"""

import os
import sys
from pathlib import Path
import shutil
import platform


def find_kicad_plugin_dir():
    """Find KiCad plugin directory for current platform"""
    system = platform.system()

    if system == "Windows":
        # KiCad 8.0+ on Windows
        appdata = Path(os.getenv("APPDATA"))
        plugin_dirs = [
            appdata / "kicad" / "8.0" / "scripting" / "plugins",
            appdata / "kicad" / "scripting" / "plugins",
        ]
    elif system == "Darwin":  # macOS
        home = Path.home()
        plugin_dirs = [
            home / "Library" / "Application Support" / "kicad" / "8.0" / "scripting" / "plugins",
            home / "Library" / "Preferences" / "kicad" / "scripting" / "plugins",
        ]
    else:  # Linux
        home = Path.home()
        plugin_dirs = [
            home / ".config" / "kicad" / "8.0" / "scripting" / "plugins",
            home / ".kicad" / "scripting" / "plugins",
        ]

    for plugin_dir in plugin_dirs:
        if plugin_dir.exists():
            return plugin_dir

    # If none exist, create the first one
    plugin_dirs[0].mkdir(parents=True, exist_ok=True)
    return plugin_dirs[0]


def install_plugin():
    """Install AnyAria plugin to KiCad"""
    # Get paths
    anyaria_root = Path(__file__).parent.parent
    plugin_source = anyaria_root / "kicad-plugin"

    if not plugin_source.exists():
        print(f"Error: Plugin source not found at {plugin_source}")
        sys.exit(1)

    # Find KiCad plugin directory
    kicad_plugin_dir = find_kicad_plugin_dir()
    print(f"KiCad plugin directory: {kicad_plugin_dir}")

    # Create symlink or copy
    plugin_dest = kicad_plugin_dir / "anyaria"

    if plugin_dest.exists():
        print(f"Removing existing installation at {plugin_dest}")
        if plugin_dest.is_symlink() or plugin_dest.is_file():
            plugin_dest.unlink()
        else:
            shutil.rmtree(plugin_dest)

    # Try to create symlink (preferred)
    try:
        plugin_dest.symlink_to(plugin_source, target_is_directory=True)
        print(f"✓ Plugin symlinked: {plugin_source} → {plugin_dest}")
    except OSError:
        # Symlink failed (Windows without admin), copy instead
        print("Symlink failed, copying plugin files instead...")
        shutil.copytree(plugin_source, plugin_dest)
        print(f"✓ Plugin copied to: {plugin_dest}")

    print("\n✓ AnyAria plugin installed successfully!")
    print("\nTo use:")
    print("  1. Restart KiCad")
    print("  2. Open PCB Editor or Schematic Editor")
    print("  3. Tools → External Plugins → AnyAria Toolbox")
    print("\nMake sure the MCP server is running:")
    print("  python mcp-server/server.py")


if __name__ == "__main__":
    install_plugin()
