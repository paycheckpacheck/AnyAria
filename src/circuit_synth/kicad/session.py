# -*- coding: utf-8 -*-
"""Knowing whether KiCad has a project open, and leaving it closed.

KiCad keeps a project's schematic in memory from the moment it opens it. A tool
that rewrites the files underneath is invisible to it: the editor still shows
what it loaded, the simulator still runs the deck it built, and the person
looking at the screen sees the old design with none of the fixes in it. Worse,
saving from that editor writes the stale copy back over the new one.

The symptom is confusing rather than obvious. A crash that was fixed an hour
ago reappears, quoting reference designators that no longer exist.

So two rules, and this module is how they are kept:

* **Do not rewrite a project KiCad has open.** Check first and say so.
* **Do not leave KiCad holding a project you have finished with.** An agent that
  opened it to show somebody closes it again.

KiCad marks a project as open with lock files named ``~<file>.lck`` beside it,
holding the hostname and username that took them. A lock left behind by a crash
looks exactly like a live one, so the process list is the tie-breaker.
"""

import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# The programs that take a lock on a project.
KICAD_PROCESSES = ("kicad.exe", "eeschema.exe", "pcbnew.exe", "kicad", "eeschema", "pcbnew")


class ProjectBusy(RuntimeError):
    """KiCad has the project open, so writing to it would be lost."""


@dataclass(frozen=True)
class Lock:
    """One of KiCad's lock files.

    Attributes:
        path: The ``~<file>.lck`` itself.
        locked: The file it locks.
        hostname: Which machine took it, when readable.
        username: Which user took it, when readable.
    """

    path: Path
    locked: Path
    hostname: str = ""
    username: str = ""

    def __str__(self) -> str:
        who = f"{self.username}@{self.hostname}" if self.hostname else "someone"
        return f"{self.locked.name} is locked by {who}"


def project_locks(project_dir: Path) -> List[Lock]:
    """Find KiCad's lock files in a project.

    Args:
        project_dir: The project directory.

    Returns:
        Every lock found, with whatever it says about who holds it.
    """
    locks: List[Lock] = []
    for path in sorted(Path(project_dir).glob("~*.lck")):
        hostname = username = ""
        try:
            owner = json.loads(path.read_text(encoding="utf-8"))
            hostname = str(owner.get("hostname", ""))
            username = str(owner.get("username", ""))
        except (OSError, ValueError):
            pass
        locks.append(
            Lock(
                path=path,
                locked=path.with_name(path.name[1:].removesuffix(".lck")),
                hostname=hostname,
                username=username,
            )
        )
    return locks


def kicad_is_running() -> bool:
    """Report whether any KiCad program is running on this machine.

    A lock left behind by a crash is indistinguishable from a live one by
    reading it, so this is what tells the two apart.

    Returns:
        True when KiCad appears to be running. False when it is not, and also
        when the question cannot be answered - a lock is then treated as live,
        because removing a live one is the worse mistake.
    """
    try:
        if sys.platform == "win32":
            finished = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=30, check=False,
            )
        else:
            finished = subprocess.run(
                ["ps", "-A", "-o", "comm="],
                capture_output=True, text=True, timeout=30, check=False,
            )
    except (OSError, subprocess.SubprocessError) as error:
        logger.debug("Could not list processes: %s", error)
        return True

    listing = (finished.stdout or "").lower()
    return any(name.lower() in listing for name in KICAD_PROCESSES)


def is_open_in_kicad(project_dir: Path) -> bool:
    """Report whether KiCad currently has this project open.

    Args:
        project_dir: The project directory.

    Returns:
        True when the project is locked and KiCad is running.
    """
    return bool(project_locks(project_dir)) and kicad_is_running()


def require_closed(project_dir: Path, strict: bool = False) -> None:
    """Refuse, or warn, before rewriting a project KiCad has open.

    Args:
        project_dir: The project directory about to be written.
        strict: Raise rather than warn. Off by default, because a warning that
            can be read is more useful than a failure in the middle of a long
            run - but a pipeline that writes and then reports success should
            turn it on.

    Raises:
        ProjectBusy: When the project is open and ``strict`` is set.
    """
    if not is_open_in_kicad(project_dir):
        return

    locks = project_locks(project_dir)
    message = (
        f"KiCad has {Path(project_dir).name} open ({locks[0] if locks else 'locked'}). "
        f"It is holding its own copy in memory, so it will not show anything "
        f"written now, and saving from it would put the old version back. "
        f"Close it before continuing."
    )
    if strict:
        raise ProjectBusy(message)
    logger.warning(message)
    print(f"WARNING: {message}")


def release_stale_locks(project_dir: Path) -> List[Path]:
    """Remove lock files that no running KiCad is holding.

    A lock left by a crash makes KiCad claim the project is already open, on a
    machine where nothing has it open. That message is alarming and wrong, and
    it is the one people work around by clicking past a warning they should
    read.

    Args:
        project_dir: The project directory.

    Returns:
        The locks removed. Empty when KiCad is running, since a live lock is
        not stale and removing it would be worse than leaving it.
    """
    if kicad_is_running():
        logger.debug("KiCad is running; leaving its locks alone")
        return []

    removed: List[Path] = []
    for lock in project_locks(project_dir):
        try:
            lock.path.unlink()
            removed.append(lock.path)
        except OSError as error:  # pragma: no cover - permissions vary
            logger.debug("Could not remove %s: %s", lock.path, error)

    if removed:
        logger.info("Removed %d stale lock(s) from %s", len(removed), project_dir)
    return removed


def close_kicad(timeout: int = 30) -> bool:
    """Ask every running KiCad to close.

    This asks rather than kills, so KiCad prompts about anything unsaved. Work
    somebody has not saved is theirs, and a tool that discards it is worse than
    one that leaves a window open.

    Args:
        timeout: How long to allow, in seconds.

    Returns:
        True when nothing is left running.
    """
    if not kicad_is_running():
        return True

    for name in ("kicad.exe", "eeschema.exe", "pcbnew.exe"):
        try:
            if sys.platform == "win32":
                # No /F: this sends a close request, not a kill.
                subprocess.run(
                    ["taskkill", "/IM", name],
                    capture_output=True, text=True, timeout=timeout, check=False,
                )
            else:
                subprocess.run(
                    ["pkill", "-TERM", "-x", name.removesuffix(".exe")],
                    capture_output=True, text=True, timeout=timeout, check=False,
                )
        except (OSError, subprocess.SubprocessError) as error:  # pragma: no cover
            logger.debug("Could not ask %s to close: %s", name, error)

    return not kicad_is_running()


def finish_editing(project_dir: Path, close: bool = False) -> None:
    """Leave a project in a state the next person can open.

    Call this when a tool has finished writing to a project. It clears the
    locks a crashed session left behind, and optionally closes a KiCad that is
    still holding the project an agent opened.

    Args:
        project_dir: The project directory.
        close: Also ask KiCad to close. Use this when the agent opened KiCad
            itself. Leave it off when the person is working in KiCad, because
            closing their editor is not a tool's decision to make.
    """
    if close:
        close_kicad()
    released = release_stale_locks(project_dir)
    if released:
        print(f"Cleared {len(released)} stale KiCad lock(s) in {Path(project_dir).name}")
