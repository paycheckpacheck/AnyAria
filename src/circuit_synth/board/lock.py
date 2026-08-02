# -*- coding: utf-8 -*-
"""An exclusive lock over one KiCad project directory.

Block agents run in parallel and each of them writes the whole project, because
circuit-synth generates a project from one root ``Circuit`` and has no way to
write a single sheet. Two of them writing at once produces a torn
``.kicad_sch``: KiCad opens the file, finds the s-expression unbalanced, and
reports the sheet as empty rather than as broken.

So the write is serialised. The lock is a file taken with ``O_CREAT | O_EXCL``,
which is atomic on every filesystem this runs on, holding the process that took
it so a lock left behind by a crash can be told from a live one.

The lock covers the *write*, not the design work. An agent researches its block,
chooses its parts and decides its placement without holding anything; it takes
the lock only for the seconds it spends regenerating and re-styling, and gives
it back.
"""

import json
import logging
import os
import socket
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

logger = logging.getLogger(__name__)

# How long to sleep between attempts. Short enough that a queue of agents does
# not idle, long enough not to hammer the filesystem.
POLL_SECONDS = 0.25

# A lock older than this whose holder is gone is broken automatically. A live
# generation of a large board takes tens of seconds, so this is generous.
STALE_SECONDS = 900.0


class BuildBusy(RuntimeError):
    """Another agent held the build lock for longer than we were willing to wait."""


@dataclass(frozen=True)
class LockHolder:
    """Who is holding the build lock.

    Attributes:
        pid: The process id that took it.
        host: The machine it took it on.
        taken: Unix time it was taken.
        note: What the holder said it was doing, usually the block name.
    """

    pid: int
    host: str
    taken: float
    note: str = ""

    def __str__(self) -> str:
        what = f" ({self.note})" if self.note else ""
        return f"pid {self.pid} on {self.host}{what}"


def _lock_path(project_dir: Path) -> Path:
    """Where the lock for a project directory lives.

    It sits beside the directory rather than inside it, so that regenerating
    the project - which rewrites everything in it - cannot delete the lock that
    is protecting the regeneration.

    Args:
        project_dir: The KiCad project directory being protected.

    Returns:
        The path of the lock file.
    """
    project_dir = Path(project_dir)
    return project_dir.parent / f".{project_dir.name}.build-lock"


def read_holder(project_dir: Path) -> Optional[LockHolder]:
    """Read who currently holds the build lock.

    Args:
        project_dir: The KiCad project directory.

    Returns:
        The holder, or None when the lock is free or unreadable.
    """
    path = _lock_path(project_dir)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    try:
        return LockHolder(
            pid=int(data["pid"]),
            host=str(data["host"]),
            taken=float(data["taken"]),
            note=str(data.get("note", "")),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _process_alive(pid: int) -> bool:
    """Whether a process id is still running on this machine.

    Args:
        pid: The process id to test.

    Returns:
        True when the process exists. True as well when we cannot tell, so an
        unreadable state never breaks a lock that might be live.
    """
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        except Exception:  # pragma: no cover - ctypes unavailable
            return True
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def _break_if_stale(project_dir: Path) -> bool:
    """Remove a lock whose holder is no longer running.

    An agent killed part-way through a generation leaves the lock behind, and
    every other agent would then wait out its timeout for nothing. A lock is
    only broken when its holder was on this machine and that process is gone,
    or when it is older than :data:`STALE_SECONDS`.

    Args:
        project_dir: The KiCad project directory.

    Returns:
        True when a stale lock was removed.
    """
    holder = read_holder(project_dir)
    if holder is None:
        return False

    same_machine = holder.host == socket.gethostname()
    dead = same_machine and not _process_alive(holder.pid)
    ancient = (time.time() - holder.taken) > STALE_SECONDS
    if not (dead or ancient):
        return False

    why = "its holder is gone" if dead else "it is older than the stale timeout"
    logger.warning("Breaking build lock on %s: %s (%s)", project_dir, why, holder)
    try:
        _lock_path(project_dir).unlink()
    except OSError:
        return False
    return True


@contextmanager
def build_lock(
    project_dir: Path, note: str = "", timeout: float = 600.0
) -> Iterator[float]:
    """Hold the exclusive right to write a project, or refuse to write at all.

    Args:
        project_dir: The KiCad project directory to protect. It need not exist
            yet; its parent must.
        note: What the caller is doing, recorded in the lock so a queue of
            agents can be diagnosed from the filesystem alone.
        timeout: How long to wait for the lock, in seconds.

    Yields:
        How long the lock was waited for, in seconds. Zero when it was free.

    Raises:
        BuildBusy: The lock was still held when the timeout expired. This is
            deliberately fatal: an agent that writes a project without the lock
            corrupts the sheets another agent is writing, and a corrupt sheet
            fails silently as an empty page.
    """
    project_dir = Path(project_dir)
    project_dir.parent.mkdir(parents=True, exist_ok=True)
    path = _lock_path(project_dir)

    payload = json.dumps(
        {
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "taken": time.time(),
            "note": note,
        }
    )

    started = time.monotonic()
    deadline = started + timeout
    while True:
        try:
            handle = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if _break_if_stale(project_dir):
                continue
            if time.monotonic() >= deadline:
                raise BuildBusy(
                    f"{project_dir.name} is being written by {read_holder(project_dir)}; "
                    f"waited {timeout:.0f}s. Nothing was written."
                )
            time.sleep(POLL_SECONDS)
            continue
        break

    waited = time.monotonic() - started
    if waited > POLL_SECONDS:
        logger.info("Waited %.1fs for the build lock on %s", waited, project_dir.name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(payload)
        yield waited
    finally:
        try:
            path.unlink()
        except OSError:  # pragma: no cover - the lock was already broken
            logger.warning("Build lock on %s had already gone", project_dir.name)
