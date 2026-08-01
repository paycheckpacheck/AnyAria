"""
AnyAria Toolbox UI for KiCad

Main dialog interface for AI circuit design.
"""

import wx
import wx.stc
from typing import Optional
from pathlib import Path
import httpx
import json


class AnyAriaToolbox(wx.Dialog):
    """Main AnyAria toolbox dialog"""

    def __init__(self, board):
        super().__init__(
            None,
            title="AnyAria - AI Circuit Design",
            size=(1200, 800),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX
        )

        self.board = board
        self.mcp_client = MCPClient()

        self._create_ui()
        self._setup_layout()

    def _create_ui(self):
        """Create UI elements"""
        panel = wx.Panel(self)

        # Splitter for main content
        splitter = wx.SplitterWindow(panel, style=wx.SP_LIVE_UPDATE)

        # Left panel: Requirements and controls
        left_panel = wx.Panel(splitter)

        # Requirements input
        req_label = wx.StaticText(left_panel, label="Circuit Requirements:")
        self.requirements_text = wx.TextCtrl(
            left_panel,
            style=wx.TE_MULTILINE,
            size=(400, 150)
        )
        self.requirements_text.SetHint(
            "Example:\n"
            "Design a 3.3V buck converter\n"
            "Input: 12V\n"
            "Output: 2A max\n"
            "Budget: <$5\n"
            "Use JLC PCB components in stock"
        )

        # Constraints
        constraint_label = wx.StaticText(left_panel, label="Constraints:")

        # Budget
        budget_sizer = wx.BoxSizer(wx.HORIZONTAL)
        budget_label = wx.StaticText(left_panel, label="Max BOM Cost:")
        self.budget_ctrl = wx.TextCtrl(left_panel, value="10.00", size=(80, -1))
        budget_currency = wx.StaticText(left_panel, label="USD")
        budget_sizer.Add(budget_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        budget_sizer.Add(self.budget_ctrl, 0, wx.RIGHT, 5)
        budget_sizer.Add(budget_currency, 0, wx.ALIGN_CENTER_VERTICAL)

        # JLC preference
        self.jlc_stock_cb = wx.CheckBox(left_panel, label="Prefer JLC PCB components in stock")
        self.jlc_stock_cb.SetValue(True)

        # Generate button
        self.generate_btn = wx.Button(left_panel, label="Generate Circuit")
        self.generate_btn.Bind(wx.EVT_BUTTON, self._on_generate)

        # Progress
        self.progress = wx.Gauge(left_panel, range=100)
        self.status_text = wx.StaticText(left_panel, label="Ready")

        # Layout left panel
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        left_sizer.Add(req_label, 0, wx.ALL, 5)
        left_sizer.Add(self.requirements_text, 1, wx.ALL | wx.EXPAND, 5)
        left_sizer.Add(constraint_label, 0, wx.ALL, 5)
        left_sizer.Add(budget_sizer, 0, wx.ALL, 5)
        left_sizer.Add(self.jlc_stock_cb, 0, wx.ALL, 5)
        left_sizer.Add(self.generate_btn, 0, wx.ALL | wx.EXPAND, 5)
        left_sizer.Add(self.progress, 0, wx.ALL | wx.EXPAND, 5)
        left_sizer.Add(self.status_text, 0, wx.ALL, 5)
        left_panel.SetSizer(left_sizer)

        # Right panel: Notebook with tabs
        self.notebook = wx.Notebook(splitter)

        # Tab 1: Block Diagram
        self.diagram_panel = wx.Panel(self.notebook)
        self.diagram_text = wx.TextCtrl(
            self.diagram_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY,
            size=(-1, -1)
        )
        diagram_sizer = wx.BoxSizer(wx.VERTICAL)
        diagram_sizer.Add(self.diagram_text, 1, wx.ALL | wx.EXPAND, 5)
        self.diagram_panel.SetSizer(diagram_sizer)
        self.notebook.AddPage(self.diagram_panel, "Block Diagram")

        # Tab 2: Component Research
        self.research_panel = wx.Panel(self.notebook)
        self.research_text = wx.TextCtrl(
            self.research_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2
        )
        research_sizer = wx.BoxSizer(wx.VERTICAL)
        research_sizer.Add(self.research_text, 1, wx.ALL | wx.EXPAND, 5)
        self.research_panel.SetSizer(research_sizer)
        self.notebook.AddPage(self.research_panel, "Component Research")

        # Tab 3: Simulation Code
        self.sim_panel = wx.Panel(self.notebook)
        self.sim_editor = wx.stc.StyledTextCtrl(self.sim_panel)
        self._setup_code_editor(self.sim_editor)

        sim_toolbar = wx.BoxSizer(wx.HORIZONTAL)
        run_sim_btn = wx.Button(self.sim_panel, label="Run Simulation")
        run_sim_btn.Bind(wx.EVT_BUTTON, self._on_run_simulation)
        ask_claude_btn = wx.Button(self.sim_panel, label="Ask Claude to Modify")
        ask_claude_btn.Bind(wx.EVT_BUTTON, self._on_ask_claude_modify)
        sim_toolbar.Add(run_sim_btn, 0, wx.ALL, 2)
        sim_toolbar.Add(ask_claude_btn, 0, wx.ALL, 2)

        sim_sizer = wx.BoxSizer(wx.VERTICAL)
        sim_sizer.Add(sim_toolbar, 0, wx.ALL, 5)
        sim_sizer.Add(self.sim_editor, 1, wx.ALL | wx.EXPAND, 5)
        self.sim_panel.SetSizer(sim_sizer)
        self.notebook.AddPage(self.sim_panel, "Simulation Code")

        # Tab 4: Net Signals
        self.signals_panel = wx.Panel(self.notebook)
        self.signals_list = wx.ListCtrl(
            self.signals_panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL
        )
        self.signals_list.InsertColumn(0, "Net", width=150)
        self.signals_list.InsertColumn(1, "Signal Type", width=150)
        self.signals_list.InsertColumn(2, "Min/Max", width=150)
        self.signals_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_net_selected)

        signals_sizer = wx.BoxSizer(wx.VERTICAL)
        signals_sizer.Add(self.signals_list, 1, wx.ALL | wx.EXPAND, 5)
        self.signals_panel.SetSizer(signals_sizer)
        self.notebook.AddPage(self.signals_panel, "Net Signals")

        # Split window
        splitter.SplitVertically(left_panel, self.notebook)
        splitter.SetSashPosition(450)

        self.splitter = splitter
        self.panel = panel

    def _setup_layout(self):
        """Setup main layout"""
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.splitter, 1, wx.EXPAND)

        # Bottom buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        apply_btn = wx.Button(self.panel, label="Apply to Schematic")
        apply_btn.Bind(wx.EVT_BUTTON, self._on_apply)
        close_btn = wx.Button(self.panel, wx.ID_CLOSE, label="Close")
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.Close())

        btn_sizer.AddStretchSpacer()
        btn_sizer.Add(apply_btn, 0, wx.ALL, 5)
        btn_sizer.Add(close_btn, 0, wx.ALL, 5)

        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.panel.SetSizer(sizer)

    def _setup_code_editor(self, editor):
        """Setup syntax highlighting for Python code"""
        editor.SetLexer(wx.stc.STC_LEX_PYTHON)
        editor.StyleSetSpec(wx.stc.STC_P_DEFAULT, "fore:#000000")
        editor.StyleSetSpec(wx.stc.STC_P_COMMENTLINE, "fore:#008000")
        editor.StyleSetSpec(wx.stc.STC_P_NUMBER, "fore:#0000FF")
        editor.StyleSetSpec(wx.stc.STC_P_STRING, "fore:#800000")
        editor.StyleSetSpec(wx.stc.STC_P_CHARACTER, "fore:#800000")
        editor.StyleSetSpec(wx.stc.STC_P_WORD, "fore:#0000FF,bold")
        editor.StyleSetSpec(wx.stc.STC_P_TRIPLE, "fore:#800000")
        editor.StyleSetSpec(wx.stc.STC_P_TRIPLEDOUBLE, "fore:#800000")
        editor.StyleSetSpec(wx.stc.STC_P_CLASSNAME, "fore:#0000FF,bold")
        editor.StyleSetSpec(wx.stc.STC_P_DEFNAME, "fore:#007F7F,bold")
        editor.StyleSetSpec(wx.stc.STC_P_OPERATOR, "fore:#000000,bold")
        editor.SetKeyWords(0, "def class if else elif while for return import from as")

    def _on_generate(self, event):
        """Handle generate circuit button"""
        requirements = self.requirements_text.GetValue().strip()
        if not requirements:
            wx.MessageBox("Please enter circuit requirements", "Error", wx.OK | wx.ICON_ERROR)
            return

        self.generate_btn.Enable(False)
        self.progress.SetValue(0)
        self.status_text.SetLabel("Analyzing requirements...")

        # Call MCP server to generate circuit
        wx.CallAfter(self._generate_circuit_async, requirements)

    def _generate_circuit_async(self, requirements):
        """Async circuit generation"""
        try:
            # Get constraints
            budget = float(self.budget_ctrl.GetValue())
            prefer_jlc = self.jlc_stock_cb.GetValue()

            # Call MCP server
            result = self.mcp_client.generate_circuit({
                "requirements": requirements,
                "budget": budget,
                "prefer_jlc_stock": prefer_jlc
            })

            # Update UI with results
            wx.CallAfter(self._update_results, result)

        except Exception as e:
            wx.CallAfter(self._show_error, f"Generation failed: {str(e)}")
        finally:
            wx.CallAfter(self.generate_btn.Enable, True)
            wx.CallAfter(self.progress.SetValue, 100)

    def _update_results(self, result):
        """Update UI with generation results"""
        # Update block diagram
        self.diagram_text.SetValue(result.get("block_diagram", ""))

        # Update research
        research = result.get("component_research", [])
        research_text = "\n\n".join([
            f"=== {r['component']} ===\n{r['analysis']}"
            for r in research
        ])
        self.research_text.SetValue(research_text)

        # Update simulation code
        sim_code = result.get("simulation_code", "")
        self.sim_editor.SetText(sim_code)

        # Update signals
        self.signals_list.DeleteAllItems()
        for net in result.get("nets", []):
            idx = self.signals_list.InsertItem(self.signals_list.GetItemCount(), net["name"])
            self.signals_list.SetItem(idx, 1, net["type"])
            self.signals_list.SetItem(idx, 2, f"{net['min']:.2f}V - {net['max']:.2f}V")

        self.status_text.SetLabel("Circuit generated successfully")

    def _show_error(self, message):
        """Show error message"""
        wx.MessageBox(message, "Error", wx.OK | wx.ICON_ERROR)
        self.status_text.SetLabel("Error")

    def _on_run_simulation(self, event):
        """Run simulation code"""
        code = self.sim_editor.GetText()
        # TODO: Execute simulation and show results
        wx.MessageBox("Simulation execution not yet implemented", "Info", wx.OK | wx.ICON_INFORMATION)

    def _on_ask_claude_modify(self, event):
        """Ask Claude to modify simulation"""
        modification = wx.GetTextFromUser(
            "What would you like to change?",
            "Modify Simulation",
            parent=self
        )
        if modification:
            # TODO: Send to Claude via MCP
            wx.MessageBox("Claude modification not yet implemented", "Info", wx.OK | wx.ICON_INFORMATION)

    def _on_net_selected(self, event):
        """Handle net selection - show signal visualization"""
        idx = event.GetIndex()
        net_name = self.signals_list.GetItemText(idx)
        # TODO: Show signal plot for this net

    def _on_apply(self, event):
        """Apply generated circuit to schematic"""
        # TODO: Use circuit-synth to apply to KiCad schematic
        wx.MessageBox("Apply to schematic not yet implemented", "Info", wx.OK | wx.ICON_INFORMATION)


class MCPClient:
    """Client for AnyAria MCP server"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.Client(timeout=300.0)  # 5 min timeout

    def generate_circuit(self, request: dict) -> dict:
        """Generate circuit via MCP server"""
        response = self.client.post(
            f"{self.base_url}/generate",
            json=request
        )
        response.raise_for_status()
        return response.json()
