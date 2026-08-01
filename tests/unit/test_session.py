"""Knowing whether KiCad is holding its own copy of a project.

This guards against the most confusing failure in the toolchain. KiCad reads a
project once and keeps it in memory, so a tool that rewrites the files
underneath changes nothing the editor shows. A crash that was fixed an hour ago
comes back, quoting reference designators the design no longer has, and the
files on disk are correct the whole time.

The other half is the lock a crashed session leaves behind. It looks exactly
like a live one, so KiCad insists the project is already open on a machine
where nothing has it open - and that is the warning people learn to click past.
"""

import json
from pathlib import Path

import pytest

from circuit_synth.kicad import session
from circuit_synth.kicad.session import (
    ProjectBusy,
    is_open_in_kicad,
    project_locks,
    release_stale_locks,
    require_closed,
)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A project directory with a lock file in it.

    Args:
        tmp_path: A temporary directory.

    Returns:
        The project directory.
    """
    (tmp_path / "Board.kicad_pro").write_text("{}", encoding="utf-8")
    (tmp_path / "~Board.kicad_pro.lck").write_text(
        json.dumps({"hostname": "PALAPTOP", "username": "pache"}), encoding="utf-8"
    )
    return tmp_path


def running(monkeypatch, is_running: bool) -> None:
    """Pretend KiCad is or is not running.

    Args:
        monkeypatch: pytest's patcher.
        is_running: What to pretend.
    """
    monkeypatch.setattr(session, "kicad_is_running", lambda: is_running)


def test_a_lock_says_who_holds_it(project):
    """The message is only useful if it names the session holding the project."""
    locks = project_locks(project)

    assert len(locks) == 1
    assert locks[0].hostname == "PALAPTOP"
    assert "Board.kicad_pro" in str(locks[0])


def test_a_lock_with_kicad_running_means_the_project_is_open(project, monkeypatch):
    """This is the case where writing is pointless: KiCad will not see it."""
    running(monkeypatch, True)

    assert is_open_in_kicad(project) is True


def test_a_lock_with_nothing_running_is_stale(project, monkeypatch):
    """A crashed session leaves a lock that looks exactly like a live one."""
    running(monkeypatch, False)

    assert is_open_in_kicad(project) is False


def test_a_stale_lock_is_cleared(project, monkeypatch):
    """Otherwise KiCad claims the project is open on a machine where it is not."""
    running(monkeypatch, False)

    removed = release_stale_locks(project)

    assert len(removed) == 1
    assert project_locks(project) == []


def test_a_live_lock_is_left_alone(project, monkeypatch):
    """Removing a lock somebody is holding is worse than leaving it."""
    running(monkeypatch, True)

    assert release_stale_locks(project) == []
    assert len(project_locks(project)) == 1


def test_writing_to_an_open_project_can_be_refused(project, monkeypatch):
    """A pipeline that writes and then reports success needs this to be fatal."""
    running(monkeypatch, True)

    with pytest.raises(ProjectBusy, match="open"):
        require_closed(project, strict=True)


def test_writing_to_a_closed_project_is_fine(project, monkeypatch):
    """A stale lock must not stop work on a project nobody has open."""
    running(monkeypatch, False)

    require_closed(project, strict=True)


def test_a_project_with_no_locks_is_not_open(tmp_path, monkeypatch):
    """The ordinary case, and it must not depend on the process list."""
    running(monkeypatch, True)

    assert is_open_in_kicad(tmp_path) is False


def test_an_unreadable_lock_still_counts(tmp_path, monkeypatch):
    """A truncated lock is still a lock; failing to parse it is not permission."""
    (tmp_path / "~Board.kicad_sch.lck").write_text("not json", encoding="utf-8")
    running(monkeypatch, True)

    assert is_open_in_kicad(tmp_path) is True
