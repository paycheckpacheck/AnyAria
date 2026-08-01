"""
AnyAria KiCad Action Plugin

AI-powered circuit design toolbox for KiCad.
Integrates Claude for intelligent circuit generation.
"""

import pcbnew
import wx
from pathlib import Path
import sys

# Add AnyAria to path
ANYARIA_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ANYARIA_ROOT / "src"))

from anyaria.core.plugin_interface import AnyAriaToolbox


class AnyAriaPlugin(pcbnew.ActionPlugin):
    """KiCad Action Plugin for AnyAria"""

    def defaults(self):
        """Plugin metadata"""
        self.name = "AnyAria Toolbox"
        self.category = "AI Circuit Design"
        self.description = "AI-powered circuit design with Claude"
        self.show_toolbar_button = True
        self.icon_file_name = str(Path(__file__).parent / "icons" / "anyaria.png")

    def Run(self):
        """Launch AnyAria toolbox"""
        try:
            # Get current board
            board = pcbnew.GetBoard()

            # Launch toolbox dialog
            toolbox = AnyAriaToolbox(board)
            toolbox.ShowModal()
            toolbox.Destroy()

        except Exception as e:
            wx.MessageBox(
                f"Error launching AnyAria: {str(e)}",
                "AnyAria Error",
                wx.OK | wx.ICON_ERROR
            )


# Register plugin
AnyAriaPlugin().register()
