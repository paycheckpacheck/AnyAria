"""
AnyAria Launcher

Quick launcher for AnyAria MCP server
"""

import sys
import webbrowser
from pathlib import Path
import time
import subprocess

# Add to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def main():
    """Launch AnyAria"""
    print("=" * 60)
    print("AnyAria - AI-Powered Circuit Design")
    print("=" * 60)
    print()
    print("Starting MCP server...")
    print()

    # Start MCP server
    server_path = Path(__file__).parent / "mcp-server" / "server.py"

    try:
        # Start server process
        proc = subprocess.Popen(
            [sys.executable, str(server_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # Wait for server to start
        time.sleep(2)

        print("✓ MCP Server running at http://localhost:8000")
        print()
        print("Next steps:")
        print("  1. Open KiCad")
        print("  2. Tools → External Plugins → AnyAria Toolbox")
        print()
        print("Or use Claude Code CLI:")
        print("  /anyaria Design a 3.3V LDO from 5V input")
        print()
        print("Press Ctrl+C to stop server")
        print("-" * 60)
        print()

        # Stream server output
        for line in proc.stdout:
            print(line, end="")

    except KeyboardInterrupt:
        print("\n\nStopping server...")
        proc.terminate()
        proc.wait()
        print("✓ Server stopped")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
