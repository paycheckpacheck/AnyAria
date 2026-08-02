# -*- coding: utf-8 -*-
"""Run ngspice, on machines where importing it does not work.

KiCad ships ngspice as ``ngspice.dll`` and no ``ngspice.exe``, so
``shutil.which("ngspice")`` finds nothing on a normal KiCad install and every
check that depends on a real simulation quietly skips. That skip is the reason
this repository spent several sessions believing SPICE was unavailable here.

It is not, and the diagnosis that said so was wrong in an instructive way. The
DLL is ARM64. So is the machine. So, apparently, is the interpreter -
``platform.machine()`` says ARM64 and the venv's ``python.exe`` has an ARM64 PE
header. But the venv entry is a trampoline: it launches an x86-64 CPython, and
inside that emulated process ``PROCESSOR_ARCHITECTURE`` is AMD64 and an ARM64
DLL will not load. The symptom, ``WinError 193``, is the same one a genuine
architecture mismatch gives, which is what made the wrong explanation stick.

The fix does not need the caller's interpreter to change. KiCad bundles a
Python built for the same architecture as its own DLL - it has to, since that
is what KiCad's scripting console runs on - so this module finds that
interpreter and drives ngspice through it in a subprocess. The caller keeps
whatever Python it has.

    >>> from circuit_synth.simulation.ngspice_runner import run_deck
    >>> result = run_deck("divider\\nV1 in 0 DC 10\\nR1 in out 1k\\n"
    ...                   "R2 out 0 3k\\n.op\\n.end\\n", vectors=["out"])
    >>> result.vectors["out"][0]                      # doctest: +SKIP
    7.5

What this is not: a replacement for PySpice. It runs a deck and returns the
vectors asked for. Anything that wants to build a circuit programmatically
should build a deck and hand it over.
"""

import json
import logging
import os
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

__all__ = [
    "NgspiceInstall",
    "SimulationResult",
    "find_ngspice",
    "run_deck",
    "available",
]

# PE machine types, for matching a candidate interpreter to the DLL.
_MACHINE_NAMES = {0x8664: "x86-64", 0xAA64: "ARM64", 0x14C: "x86", 0xA641: "ARM64EC"}

_SEARCH_ROOTS = (
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "KiCad",
    Path(os.environ.get("PROGRAMFILES", "")) / "KiCad",
    Path("/Applications/KiCad/KiCad.app/Contents"),
    Path("/usr/lib"),
    Path("/usr/local/lib"),
)


@dataclass(frozen=True)
class NgspiceInstall:
    """An ngspice that can actually be run on this machine.

    Attributes:
        library: The shared library.
        interpreter: A Python built for the same architecture, which will be
            used to drive it. None means the current interpreter will do.
        architecture: What both of them are, for the message when they do not
            match anything available.
    """

    library: Path
    interpreter: Optional[Path]
    architecture: str

    def python(self) -> str:
        """The interpreter to run the worker with.

        Returns:
            An executable path.
        """
        return str(self.interpreter) if self.interpreter else sys.executable


@dataclass
class SimulationResult:
    """What came back from a run.

    Attributes:
        ok: Whether ngspice loaded the deck and ran it.
        vectors: Requested vector name to its values. Real parts only.
        log: Everything ngspice printed, which is where its complaints are.
        error: The first line that looks like a failure, or empty.
    """

    ok: bool
    vectors: Dict[str, List[float]] = field(default_factory=dict)
    log: str = ""
    error: str = ""


def _pe_machine(path: Path) -> Optional[int]:
    """Read a PE binary's machine type.

    Args:
        path: A ``.exe`` or ``.dll``.

    Returns:
        The machine constant, or None if the file is not PE.
    """
    try:
        head = path.open("rb").read(0x400)
        offset = struct.unpack_from("<I", head, 0x3C)[0]
        if head[offset : offset + 4] != b"PE\0\0":
            return None
        return struct.unpack_from("<H", head, offset + 4)[0]
    except (OSError, struct.error, IndexError):
        return None


def _process_architecture() -> str:
    """What this process actually runs as, not what the machine is.

    ``platform.machine()`` reports the hardware, and on Windows on ARM an
    emulated x86-64 process is told AMD64 through the environment. The
    environment is the honest answer here, because it is what the loader will
    act on.

    Returns:
        An architecture name matching :data:`_MACHINE_NAMES` values.
    """
    if sys.platform != "win32":
        import platform

        return {"AMD64": "x86-64", "x86_64": "x86-64", "arm64": "ARM64"}.get(
            platform.machine(), platform.machine()
        )
    reported = os.environ.get("PROCESSOR_ARCHITECTURE", "").upper()
    return {"AMD64": "x86-64", "ARM64": "ARM64", "X86": "x86"}.get(reported, reported)


def _library_names() -> Sequence[str]:
    """Shared-library names to look for, by platform.

    Returns:
        File names.
    """
    if sys.platform == "win32":
        return ("ngspice.dll",)
    if sys.platform == "darwin":
        return ("libngspice.dylib", "libngspice.0.dylib")
    return ("libngspice.so", "libngspice.so.0")


def find_ngspice() -> Optional[NgspiceInstall]:
    """Find an ngspice library and an interpreter that can load it.

    Returns:
        The install, or None when there is no usable pairing. A library that
        exists but cannot be loaded by anything here counts as no install:
        reporting it and then failing later is worse than reporting nothing.
    """
    names = _library_names()
    for root in _SEARCH_ROOTS:
        if not root or not root.exists():
            continue
        for name in names:
            for library in sorted(root.glob(f"**/{name}")):
                install = _pair(library)
                if install:
                    logger.debug("using ngspice at %s", library)
                    return install
    logger.debug("no usable ngspice found")
    return None


def _pair(library: Path) -> Optional[NgspiceInstall]:
    """Match a library against an interpreter that can load it.

    Args:
        library: The shared library.

    Returns:
        The pairing, or None when nothing available can load it.
    """
    machine = _pe_machine(library) if sys.platform == "win32" else None
    architecture = _MACHINE_NAMES.get(machine, "unknown") if machine else "native"

    # The current interpreter first: on any platform without the emulation
    # problem this is the whole answer.
    if architecture in ("native", _process_architecture()):
        return NgspiceInstall(library=library, interpreter=None, architecture=architecture)

    # Otherwise look beside the library. KiCad bundles an interpreter built for
    # the same architecture as its own DLL, because its scripting console runs
    # on it.
    for candidate in (
        library.parent / "python.exe",
        library.parent / "python3.exe",
        library.parent / "python3",
        library.parent / "python",
    ):
        if not candidate.exists():
            continue
        if sys.platform == "win32" and _pe_machine(candidate) != machine:
            continue
        return NgspiceInstall(
            library=library, interpreter=candidate, architecture=architecture
        )

    logger.debug(
        "%s is %s but this process is %s, and no matching interpreter sits "
        "beside it",
        library,
        architecture,
        _process_architecture(),
    )
    return None


def available() -> bool:
    """Whether a deck can actually be simulated here.

    Returns:
        True when :func:`find_ngspice` finds a usable pairing.
    """
    return find_ngspice() is not None


_WORKER = r'''
import ctypes, json, os, sys

library, deck_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
commands = json.loads(sys.argv[4])
wanted = json.loads(sys.argv[5])

os.add_dll_directory(os.path.dirname(library)) if hasattr(os, "add_dll_directory") else None
lib = ctypes.CDLL(library, winmode=0) if sys.platform == "win32" else ctypes.CDLL(library)


class VectorInfo(ctypes.Structure):
    _fields_ = [
        ("v_name", ctypes.c_char_p),
        ("v_type", ctypes.c_int),
        ("v_flags", ctypes.c_short),
        ("v_realdata", ctypes.POINTER(ctypes.c_double)),
        ("v_compdata", ctypes.c_void_p),
        ("v_length", ctypes.c_int),
    ]


SendChar = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
SendStat = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
Exit = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_bool, ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)
Data = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p)
Init = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p)
Bg = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)

log = []


@SendChar
def send_char(text, ident, user):
    log.append(text.decode("utf-8", "replace"))
    return 0


@SendStat
def send_stat(text, ident, user):
    return 0


@Exit
def controlled_exit(status, immediate, quitexit, ident, user):
    log.append("ngspice asked to exit with status %d" % status)
    return 0


@Data
def send_data(values, count, ident, user):
    return 0


@Init
def send_init(values, ident, user):
    return 0


@Bg
def background(noruns, ident, user):
    return 0


lib.ngSpice_Init(send_char, send_stat, controlled_exit, send_data, send_init, background, None)
lib.ngGet_Vec_Info.restype = ctypes.POINTER(VectorInfo)
lib.ngSpice_CurPlot.restype = ctypes.c_char_p
lib.ngSpice_AllVecs.restype = ctypes.POINTER(ctypes.c_char_p)


def every_vector():
    """Names of every vector in the plot the run left behind."""
    plot = lib.ngSpice_CurPlot()
    if not plot:
        return []
    names, index = [], 0
    array = lib.ngSpice_AllVecs(plot)
    if not array:
        return []
    while array[index]:
        names.append(array[index].decode("utf-8", "replace"))
        index += 1
    return names

with open(deck_path, "rb") as handle:
    lines = [line.rstrip(b"\r\n") for line in handle if line.strip()]

array = (ctypes.c_char_p * (len(lines) + 1))(*(lines + [None]))
loaded = lib.ngSpice_Circ(array)

vectors = {}
if loaded == 0:
    for command in commands:
        lib.ngSpice_Command(command.encode())
    if wanted == ["*"]:
        wanted = every_vector()
    for name in wanted:
        pointer = lib.ngGet_Vec_Info(name.encode())
        if not pointer:
            continue
        info = pointer.contents
        if not info.v_realdata:
            continue
        vectors[name] = [info.v_realdata[i] for i in range(info.v_length)]

with open(out_path, "w", encoding="utf-8") as handle:
    json.dump({"loaded": loaded, "vectors": vectors, "log": "".join(log)}, handle)
'''

_FAILURE_MARKERS = (
    "No circuit loaded",
    "bad syntax",
    "Error:",
    "error on line",
    "unknown subckt",
    "simulation interrupted",
)


def run_deck(
    deck: str,
    commands: Sequence[str] = ("run",),
    vectors: Sequence[str] = (),
    timeout: float = 300.0,
    install: Optional[NgspiceInstall] = None,
) -> SimulationResult:
    """Run a SPICE deck and read vectors out of it.

    Args:
        deck: The deck, including its title line and ``.end``. ngspice treats
            the first line as a title and will silently discard a component
            written there.
        commands: ngspice commands to issue after loading, in order.
        vectors: Vector names to read back, such as ``out`` or ``v(out)``. The
            single name ``"*"`` means every vector the run left behind, which
            is what a caller wants when it does not know the node names in
            advance - an exported KiCad deck, for instance.
        timeout: Seconds before the run is abandoned.
        install: Which ngspice to use. Found automatically when omitted.

    Returns:
        The result. ``ok`` is False when no ngspice is available, when the deck
        would not load, or when ngspice printed something that reads like a
        failure - ngspice returns success in several cases where it has plainly
        not simulated anything, so its output is the signal, not its status.
    """
    install = install or find_ngspice()
    if install is None:
        return SimulationResult(
            ok=False,
            error=(
                "no ngspice this process can load. KiCad ships it as a library "
                "rather than a program, so an interpreter matching its "
                "architecture is needed and none was found."
            ),
        )

    with tempfile.TemporaryDirectory(prefix="ngspice-") as scratch:
        area = Path(scratch)
        deck_path = area / "deck.cir"
        deck_path.write_text(deck, encoding="utf-8")
        worker = area / "worker.py"
        worker.write_text(_WORKER, encoding="utf-8")
        result_path = area / "result.json"

        completed = subprocess.run(
            [
                install.python(),
                str(worker),
                str(install.library),
                str(deck_path),
                str(result_path),
                json.dumps(list(commands)),
                json.dumps(list(vectors)),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        if not result_path.exists():
            detail = (completed.stderr or completed.stdout or "").strip()
            return SimulationResult(
                ok=False,
                log=detail,
                error=f"ngspice did not run: {detail[-300:]}",
            )

        payload = json.loads(result_path.read_text(encoding="utf-8"))

    log = payload.get("log", "")
    if payload.get("loaded") != 0:
        return SimulationResult(
            ok=False, log=log, error=_first_complaint(log) or "the deck would not load"
        )

    complaint = _first_complaint(log)
    return SimulationResult(
        ok=not complaint,
        vectors=payload.get("vectors", {}),
        log=log,
        error=complaint,
    )


def _first_complaint(log: str) -> str:
    """Find the first line of a log that reads like a failure.

    Args:
        log: Everything ngspice printed.

    Returns:
        The line, or an empty string.
    """
    for line in log.splitlines():
        if any(marker in line for marker in _FAILURE_MARKERS):
            return line.strip()
    return ""
