# -*- coding: utf-8 -*-
"""Run a board's root builder in a fresh interpreter.

The root builder imports every block's ``block.py``, and those files are being
rewritten underneath us by the agents that own them. Importing them in the
calling process would get whatever ``sys.modules`` already holds, which for the
agent that has just rewritten its own block is the version from before it did.
Reference numbering is also assigned from module-level state that a second
generation in the same process would continue rather than restart.

So the builder runs in a subprocess. It is started as
``python -m circuit_synth.board._runner <design_dir> <project_dir>`` and prints
one line of JSON on stdout describing what it generated.
"""

import importlib
import json
import sys
from pathlib import Path

# The result line is prefixed so it can be picked out of the generator's very
# chatty stdout.
RESULT_PREFIX = "CIRCUIT_SYNTH_BUILD_RESULT "


def main(argv) -> int:
    """Generate the project described by a design directory.

    Args:
        argv: ``[design_dir, project_dir]``.

    Returns:
        A process exit code: 0 when the project generated, 1 otherwise.
    """
    design_dir = Path(argv[0]).resolve()
    project_dir = Path(argv[1]).resolve()

    sys.path.insert(0, str(design_dir))
    module = importlib.import_module("board")

    if not hasattr(module, "board"):
        print(
            RESULT_PREFIX
            + json.dumps(
                {
                    "success": False,
                    "error": f"{design_dir / 'board.py'} does not define board()",
                }
            )
        )
        return 1

    circuit = module.board()
    # force_regenerate is not an optimisation choice here, it is the only path
    # that works. Left at its default, generate_kicad_project sends an existing
    # project to the incremental synchroniser, which raises
    # "'SheetManager' object is not iterable" as soon as it has to place a
    # component, and aborts rather than falling back. See
    # tests/unit/test_board_build.py for the reproduction.
    #
    # update_source_refs is off because the default would rewrite the block.py
    # files with finalized references - files other agents own and are editing.
    result = circuit.generate_kicad_project(
        str(project_dir),
        generate_pcb=False,
        force_regenerate=True,
        update_source_refs=False,
    )

    payload = {
        "success": bool(result.get("success")),
        "error": result.get("error"),
        "json_path": str(result["json_path"]) if result.get("json_path") else None,
        "project_path": (
            str(result["project_path"]) if result.get("project_path") else None
        ),
    }
    print(RESULT_PREFIX + json.dumps(payload))
    return 0 if payload["success"] else 1


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    sys.exit(main(sys.argv[1:]))
