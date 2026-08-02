"""A board can be built by several agents at once without them losing each other's work.

Blocks are built in parallel and every one of them regenerates the whole KiCad
project, because circuit-synth writes a project from one root Circuit and has no
call that adds a single sheet to an existing one. Three things have to hold for
that to be safe, and each is a way the fan-out silently produced a wrong board
before:

* two builds must not overlap, or one writes a half-finished sheet over the
  other's and KiCad reports the page as empty rather than as broken;
* a build must reproduce the whole design from disk - every block.py and every
  layout.py - so that the agent who finishes last includes the others rather
  than overwriting them;
* an abandoned lock must not stop the rest of the fan-out for its full timeout.

The generation itself is exercised end to end by
``tests/e2e/test_block_first_board.py``; these tests are the parts that can be
checked without KiCad.
"""

import json
import os
import socket
import threading
import time
from pathlib import Path

import pytest

from circuit_synth.board import BuildBusy, LockHolder, build_lock, read_holder
from circuit_synth.board.build import Board, BuildFailed, _instances_of, _load_spec
from circuit_synth.board.lock import _lock_path
from circuit_synth.kicad.layout.spec import ComponentPlacement, PlacementSpec


def test_two_builds_of_one_project_cannot_overlap(tmp_path):
    project = tmp_path / "Demo"
    inside = []

    def hold():
        with build_lock(project, note="first"):
            inside.append("first in")
            time.sleep(0.4)
            inside.append("first out")

    thread = threading.Thread(target=hold)
    thread.start()
    time.sleep(0.1)
    with build_lock(project, note="second", timeout=5.0):
        inside.append("second in")
    thread.join()

    assert inside == ["first in", "first out", "second in"]


def test_a_build_that_cannot_take_the_lock_refuses_rather_than_writing(tmp_path):
    project = tmp_path / "Demo"
    with build_lock(project, note="holder"):
        with pytest.raises(BuildBusy) as raised:
            with build_lock(project, note="waiter", timeout=0.5):
                pytest.fail("the second build should never have started")
    assert "Nothing was written" in str(raised.value)


def test_the_lock_says_who_is_holding_it_and_why(tmp_path):
    project = tmp_path / "Demo"
    assert read_holder(project) is None
    with build_lock(project, note="Indicator"):
        holder = read_holder(project)
        assert holder.pid == os.getpid()
        assert holder.host == socket.gethostname()
        assert holder.note == "Indicator"
        assert "Indicator" in str(holder)
    assert read_holder(project) is None


def test_a_lock_left_by_a_dead_agent_is_broken_rather_than_waited_out(tmp_path):
    project = tmp_path / "Demo"
    project.parent.mkdir(parents=True, exist_ok=True)
    # A process id that cannot be running, written as this machine's.
    _lock_path(project).write_text(
        json.dumps(
            {
                "pid": 2**31 - 1,
                "host": socket.gethostname(),
                "taken": time.time(),
                "note": "an agent that was killed",
            }
        ),
        encoding="utf-8",
    )

    started = time.monotonic()
    with build_lock(project, note="the next agent", timeout=30.0):
        pass
    assert time.monotonic() - started < 5.0


def test_a_lock_held_by_another_machine_is_not_broken(tmp_path):
    project = tmp_path / "Demo"
    project.parent.mkdir(parents=True, exist_ok=True)
    _lock_path(project).write_text(
        json.dumps(
            {"pid": 1, "host": "some-other-machine", "taken": time.time(), "note": ""}
        ),
        encoding="utf-8",
    )
    with pytest.raises(BuildBusy):
        with build_lock(project, timeout=0.3):
            pytest.fail("a live lock on another machine must be respected")


def test_the_lock_lives_outside_the_directory_it_protects(tmp_path):
    # A build rewrites everything in the project directory. A lock kept inside
    # it would be deleted by the very generation it is protecting.
    project = tmp_path / "Demo"
    assert _lock_path(project).parent == project.parent


def test_a_board_finds_the_blocks_that_have_a_circuit_file(tmp_path):
    design = tmp_path / "design"
    for name in ("Supply", "Indicator"):
        (design / "blocks" / name).mkdir(parents=True)
        (design / "blocks" / name / "block.py").write_text("", encoding="utf-8")
    # A directory without a block.py is not a block.
    (design / "blocks" / "notes").mkdir()

    board = Board(design, tmp_path / "Demo")
    assert board.blocks() == ["Indicator", "Supply"]
    assert board.root_schematic.name == "Demo.kicad_sch"
    assert board.circuit_json.name == "Demo.json"
    assert board.sheet("Indicator2").name == "Indicator2.kicad_sch"


def test_a_repeated_block_is_recognised_in_every_instance_it_has():
    instances = {
        "Supply": {"U1": "U1", "Supply": "Supply"},
        "Indicator": {"R3": "R3", "Indicator": "Indicator"},
        "Indicator2": {"R3": "R4", "Indicator": "Indicator2"},
    }
    assert _instances_of("Indicator", instances) == ["Indicator", "Indicator2"]
    assert _instances_of("Supply", instances) == ["Supply"]
    assert _instances_of("Header", instances) == []


def test_a_layout_written_moments_ago_is_read_rather_than_a_cached_import(tmp_path):
    # Every agent's build reads layout files another agent wrote seconds
    # earlier. A normal import would hand back the first version for the rest
    # of the process's life.
    layout = tmp_path / "layout.py"
    layout.write_text(
        "from circuit_synth.kicad.layout.spec import PlacementSpec, ComponentPlacement\n"
        "SPEC = PlacementSpec(components=[ComponentPlacement('R1', (10.16, 10.16), 0)])\n",
        encoding="utf-8",
    )
    assert _load_spec(layout, "SPEC").components[0].reference == "R1"

    layout.write_text(
        "from circuit_synth.kicad.layout.spec import PlacementSpec, ComponentPlacement\n"
        "SPEC = PlacementSpec(components=[ComponentPlacement('R2', (10.16, 10.16), 0)])\n",
        encoding="utf-8",
    )
    assert _load_spec(layout, "SPEC").components[0].reference == "R2"


def test_a_layout_worked_out_in_code_can_be_written_and_read_back(tmp_path):
    # A block agent that computes its placement rather than writing it by hand
    # needs somewhere to put it that the next build will pick up.
    layout = tmp_path / "layout.json"
    PlacementSpec(
        components=[ComponentPlacement("D1", (127.0, 96.52), 90)], paper="A4"
    ).write_json(layout)

    loaded = _load_spec(tmp_path / "layout.py", "SPEC")
    assert loaded.paper == "A4"
    assert loaded.components[0].reference == "D1"
    assert loaded.components[0].at == (127.0, 96.52)
    assert loaded.components[0].rotation == 90


def test_a_block_with_no_layout_yet_is_reported_rather_than_guessed_at(tmp_path):
    assert _load_spec(tmp_path / "layout.py", "SPEC") is None


def test_a_layout_that_does_not_import_stops_the_build(tmp_path):
    layout = tmp_path / "layout.py"
    layout.write_text("this is not python\n", encoding="utf-8")
    with pytest.raises(BuildFailed):
        _load_spec(layout, "SPEC")


def test_a_layout_bound_to_the_wrong_kind_of_object_stops_the_build(tmp_path):
    layout = tmp_path / "layout.py"
    layout.write_text("SPEC = {'components': []}\n", encoding="utf-8")
    with pytest.raises(BuildFailed) as raised:
        _load_spec(layout, "SPEC")
    assert "PlacementSpec" in str(raised.value)
