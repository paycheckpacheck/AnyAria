#!/usr/bin/env python3
"""Require the schematic layout pass after a KiCad project is generated.

Generating a schematic and laying one out are separate steps. The generator
works out what connects to what; nothing in it decides where a part goes or how
the sheet reads. Left alone, the output is electrically correct and unpleasant
to look at, which is the state every fresh project starts in.

This hook watches for a command that generates a KiCad project and reminds
Claude, in the transcript, that the layout pass still has to run. It is a
reminder rather than a block, because the generate step is legitimate on its
own - what is not legitimate is stopping there and calling the schematic done.
"""

import json
import re
import sys
from pathlib import Path

# Commands that produce a KiCad project one way or another.
GENERATES_A_PROJECT = re.compile(
    r"generate_kicad_project"          # the library call, in a script or -c
    r"|cs-new-project"                 # project scaffolding
    r"|python[^\n]*examples[/\\][^\n]*\.py",  # running a bundled example
    re.IGNORECASE,
)

REMINDER = """\
A KiCad project was just generated. Its schematic has not been laid out yet:
parts sit where the placement algorithm dropped them, which is not a layout an
engineer can read.

Run the layout pass before reporting the schematic as done. Invoke the
layout-schematic skill, which walks the loop:

    describe the sheet -> decide the placement -> apply it
    -> validate the connectivity -> render it -> look at it -> refine

Wires go around parts, never over them: route_around() works out the detour and
validate_layout() reports any crossing left as an "over" problem.

Do not describe a generated schematic as finished, or show it to the user,
until that has run and validate_layout() reports no problems.\
"""


def command_from(payload: dict) -> str:
    """Extract the shell command from a hook payload.

    Args:
        payload: The hook input as delivered by Claude Code.

    Returns:
        The command string, or an empty string when there is not one.
    """
    tool_input = payload.get("tool_input") or {}
    if isinstance(tool_input, dict):
        return str(tool_input.get("command", ""))
    return ""


def main() -> int:
    """Emit the reminder when a generating command has just run.

    Returns:
        Process exit status. Always 0, so the hook never blocks work.
    """
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    if payload.get("tool_name") != "Bash":
        return 0

    command = command_from(payload)
    if not command or not GENERATES_A_PROJECT.search(command):
        return 0

    # A run that only laid a sheet out is not itself a reason to remind.
    if "apply_placement" in command or "layout" in command.lower():
        return 0

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": REMINDER,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
