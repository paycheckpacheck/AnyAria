"""Running the same SPICE deck KiCad's own simulator would run.

The temptation when adding simulation to a schematic generator is to build a
second model in Python - walk the circuit, emit a PySpice netlist, simulate
that. It is easy to write and it is wrong, because there are then two circuits:
the one KiCad simulates when the user clicks Probe, and the one the tool
measured to produce the numbers written on the sheet. They agree on the day
they are written and drift apart quietly afterwards.

So the deck is not built here. It is exported from the schematic with
``kicad-cli sch export netlist --format spice`` - the same exporter the
interactive simulator uses - and that deck is handed to ngspice. A figure
annotated onto the sheet and the waveform the user sees when they probe a net
therefore come from one netlist. If the schematic is wrong, both are wrong
together and the disagreement shows up somewhere a person will notice.

ngspice is loaded from the KiCad installation, which ships it as a shared
library. That avoids asking the user to install a second copy and guarantees
the engine matching their KiCad is the one being used.
"""

import logging
import os
import platform
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

# A transient run on a switching circuit can take a while, but not this long.
SIMULATION_TIMEOUT_SECONDS = 600
NETLIST_TIMEOUT_SECONDS = 120


class SimulationUnavailable(Exception):
    """Raised when ngspice cannot be loaded on this machine.

    Distinguished from a simulation that ran and failed, because the two call
    for different responses: this one means the analysis cannot be attempted
    and the schematic must not be annotated with simulated figures.
    """


class SimulationFailed(Exception):
    """Raised when ngspice ran but did not produce a usable result."""


def find_ngspice_library() -> Optional[Path]:
    """Locate the ngspice shared library KiCad ships.

    Returns:
        Path to the library, or None when it cannot be found. The search
        covers the standard KiCad install locations on Windows, macOS and
        Linux, and the ``NGSPICE_LIBRARY_PATH`` environment variable takes
        precedence over all of them.
    """
    override = os.environ.get("NGSPICE_LIBRARY_PATH")
    if override and Path(override).exists():
        return Path(override)

    system = platform.system()
    candidates: List[Path] = []

    if system == "Windows":
        names = ["ngspice.dll"]
        roots = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "KiCad",
            Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "KiCad",
        ]
        for root in roots:
            if root.exists():
                for version in sorted(root.iterdir(), reverse=True):
                    candidates.extend((version / "bin" / name) for name in names)
    elif system == "Darwin":
        candidates.extend(
            Path(p)
            for p in (
                "/Applications/KiCad/KiCad.app/Contents/Frameworks/libngspice.0.dylib",
                "/usr/local/lib/libngspice.dylib",
                "/opt/homebrew/lib/libngspice.dylib",
            )
        )
    else:
        candidates.extend(
            Path(p)
            for p in (
                "/usr/lib/x86_64-linux-gnu/libngspice.so.0",
                "/usr/lib/libngspice.so.0",
                "/usr/local/lib/libngspice.so.0",
            )
        )

    for candidate in candidates:
        if candidate.exists():
            logger.debug("Found ngspice at %s", candidate)
            return candidate

    return None


def _kicad_cli() -> Optional[str]:
    """Locate the kicad-cli executable.

    Returns:
        The path to kicad-cli, or None when it is not installed.
    """
    from ..kicad.layout.validate import find_kicad_cli

    return find_kicad_cli()


def export_spice_netlist(schematic: Path, output: Optional[Path] = None) -> str:
    """Export a schematic's SPICE deck using KiCad's own exporter.

    This is the netlist KiCad's simulator builds when the user runs an
    analysis, so anything measured from it is what the user will see.

    Args:
        schematic: The ``.kicad_sch`` to export. For a hierarchical design
            this must be the root sheet.
        output: Where to write the deck. Defaults to a temporary file whose
            contents are returned and then discarded.

    Returns:
        The SPICE deck.

    Raises:
        SimulationUnavailable: If kicad-cli is not installed.
        SimulationFailed: If the export failed, with KiCad's own message.
    """
    cli = _kicad_cli()
    if not cli:
        raise SimulationUnavailable(
            "kicad-cli is not installed, so the SPICE netlist cannot be "
            "exported. Install KiCad, or leave the simulated figures off the "
            "schematic."
        )

    schematic = Path(schematic)
    with tempfile.TemporaryDirectory() as scratch:
        target = Path(output) if output else Path(scratch) / "deck.cir"
        finished = subprocess.run(
            [
                cli,
                "sch",
                "export",
                "netlist",
                "--format",
                "spice",
                "-o",
                str(target),
                str(schematic),
            ],
            capture_output=True,
            text=True,
            timeout=NETLIST_TIMEOUT_SECONDS,
        )

        if finished.returncode != 0 or not target.exists():
            raise SimulationFailed(
                f"kicad-cli could not export a SPICE netlist from "
                f"{schematic.name}: "
                f"{(finished.stderr or finished.stdout or '').strip()}"
            )

        deck = target.read_text(encoding="utf-8")

    logger.info(
        "Exported SPICE netlist from %s (%d lines)", schematic.name, deck.count("\n")
    )
    return deck


def netlist_elements(deck: str) -> List[str]:
    """List the circuit elements a SPICE deck actually contains.

    Used to check that the parts expected in a simulation are in it. A symbol
    missing its ``Sim.*`` properties is absent from the deck with no error
    anywhere, and this is how that gets caught.

    Args:
        deck: The SPICE netlist.

    Returns:
        The element names, such as ``["R1", "C1", "MQ1"]``, in file order.
    """
    elements = []
    for line in deck.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith((".", "*", "+")):
            continue
        elements.append(stripped.split()[0])
    return elements


@dataclass
class Waveforms:
    """The result of a transient run.

    Attributes:
        time: The time vector, in seconds.
        signals: Every vector ngspice returned, keyed by its own name. Node
            voltages appear under the net name as KiCad spelled it, such as
            ``"/PHASE"``; branch currents under names like ``"v1#branch"``.
        deck: The netlist that was run, kept so a surprising result can be
            traced back to what was actually simulated.
    """

    time: "object"
    signals: Dict[str, "object"] = field(default_factory=dict)
    deck: str = ""

    def names(self) -> List[str]:
        """List the available signal names.

        Returns:
            The names, sorted.
        """
        return sorted(self.signals)

    def signal(self, name: str):
        """Look up a signal, tolerating the spellings ngspice uses.

        ngspice lower-cases node names and KiCad prefixes hierarchical nets
        with a slash, so the name written in the Python is rarely the name in
        the result. This tries the obvious variants before giving up.

        Args:
            name: The net or vector name, such as ``"PHASE"`` or
                ``"V(/PHASE)"``.

        Returns:
            The vector as a numpy array.

        Raises:
            KeyError: If no variant of the name is present, listing what is,
                since a typo here otherwise looks like a circuit fault.
        """
        import numpy as np

        bare = name
        match = re.fullmatch(r"[VvIi]\((.*)\)", name)
        if match:
            bare = match.group(1)

        for candidate in (
            name,
            bare,
            bare.lower(),
            f"/{bare}",
            f"/{bare}".lower(),
            bare.lstrip("/"),
            bare.lstrip("/").lower(),
        ):
            if candidate in self.signals:
                return np.asarray(self.signals[candidate])

        raise KeyError(
            f"no signal named {name!r} in the result. Available: "
            f"{', '.join(self.names())}"
        )

    def window(self, start: float, end: Optional[float] = None) -> "Waveforms":
        """Restrict the result to a time window.

        Measurements are almost always wanted after the circuit has settled,
        and a startup transient otherwise dominates every peak and average.

        Args:
            start: Window start in seconds.
            end: Window end in seconds, or None for the end of the run.

        Returns:
            A new result covering only that window.

        Raises:
            SimulationFailed: If the window contains no samples.
        """
        import numpy as np

        time = np.asarray(self.time)
        mask = time >= start
        if end is not None:
            mask &= time <= end

        if not mask.any():
            raise SimulationFailed(
                f"no samples between {start}s and {end}s; the run covers "
                f"{time.min():g}s to {time.max():g}s"
            )

        return Waveforms(
            time=time[mask],
            signals={
                key: np.asarray(value)[mask] for key, value in self.signals.items()
            },
            deck=self.deck,
        )

    def peak(self, name: str) -> float:
        """Return a signal's maximum.

        Args:
            name: The signal name.

        Returns:
            The maximum value.
        """
        return float(self.signal(name).max())

    def trough(self, name: str) -> float:
        """Return a signal's minimum.

        Args:
            name: The signal name.

        Returns:
            The minimum value.
        """
        return float(self.signal(name).min())

    def ripple(self, name: str) -> float:
        """Return a signal's peak-to-peak swing.

        Args:
            name: The signal name.

        Returns:
            Maximum minus minimum.
        """
        values = self.signal(name)
        return float(values.max() - values.min())

    def mean(self, name: str) -> float:
        """Return a signal's time-weighted average.

        The samples ngspice returns are not evenly spaced - it takes short
        steps through switching edges - so a plain arithmetic mean is biased
        towards the edges. This integrates properly.

        Args:
            name: The signal name.

        Returns:
            The average over the run.
        """
        import numpy as np

        time = np.asarray(self.time)
        values = self.signal(name)
        span = time[-1] - time[0]
        if span <= 0:
            return float(values.mean())
        return float(np.trapezoid(values, time) / span)

    def rms(self, name: str) -> float:
        """Return a signal's root-mean-square value, time-weighted.

        Args:
            name: The signal name.

        Returns:
            The RMS over the run.
        """
        import numpy as np

        time = np.asarray(self.time)
        values = np.asarray(self.signal(name), dtype=float)
        span = time[-1] - time[0]
        if span <= 0:
            return float(np.sqrt((values**2).mean()))
        return float(np.sqrt(np.trapezoid(values**2, time) / span))


def run_transient(
    deck: str,
    library: Optional[Path] = None,
    working_dir: Optional[Path] = None,
) -> Waveforms:
    """Run a SPICE deck's transient analysis and return the waveforms.

    The deck must already carry its own ``.tran`` directive, which it will if
    it came from :func:`export_spice_netlist` on a schematic prepared by
    :mod:`circuit_synth.simulation.probe`.

    Args:
        deck: The SPICE netlist to run.
        library: Path to the ngspice shared library, or None to find KiCad's.
        working_dir: Directory to resolve relative ``.include`` paths against.
            KiCad writes absolute paths, so this is rarely needed.

    Returns:
        The waveforms.

    Raises:
        SimulationUnavailable: If ngspice or PySpice cannot be loaded. On a
            machine where the Python interpreter and the KiCad build are
            different architectures - an x86-64 Python against an ARM64
            KiCad, for instance - the library will not load and this is
            raised with that as the likely cause.
        SimulationFailed: If ngspice ran but produced no usable vectors.
    """
    if ".tran" not in deck.lower():
        raise SimulationFailed(
            "the deck has no .tran directive, so there is no transient "
            "analysis to run. Add one as schematic text before exporting."
        )

    library = Path(library) if library else find_ngspice_library()
    if library is None:
        raise SimulationUnavailable(
            "ngspice could not be found. KiCad ships it; set "
            "NGSPICE_LIBRARY_PATH to the shared library if it is installed "
            "somewhere unusual."
        )

    try:
        from PySpice.Spice.NgSpice.Shared import NgSpiceShared
    except Exception as error:  # noqa: BLE001 - it fails in several ways
        # Not only ImportError. PySpice declares ngspice's C interface through
        # cffi at import time, and against a newer cffi that raises
        # CDefError("duplicate declaration of struct ngcomplex") - a broken
        # dependency rather than an absent one, and just as fatal to this
        # route. Any failure to import means the in-process path is closed.
        logger.debug("PySpice unusable (%s); running out of process", error)
        return _run_transient_out_of_process(deck)

    # ngspice looks for its init file under SPICE_LIB_DIR and warns if it is
    # missing. Nothing here needs it, but leaving the variable unset makes
    # PySpice fail before it gets as far as loading anything.
    os.environ.setdefault("SPICE_LIB_DIR", str(library.parent))

    NgSpiceShared.LIBRARY_PATH = str(library)
    try:
        shared = NgSpiceShared.new_instance()
    except Exception as error:  # noqa: BLE001 - it fails in several ways
        # No usable in-process ngspice. Three different causes seen on one
        # machine, all reaching here, none of them OSError-only:
        #
        #   OSError            the library will not load into this process. On
        #                      Windows on ARM the interpreter is often an
        #                      emulated x86-64 one behind an ARM64 trampoline,
        #                      so it cannot load KiCad's ARM64 DLL however
        #                      native it looks.
        #   cffi.CDefError     PySpice declares ngspice's C interface here, and
        #                      against a newer cffi that fails with "duplicate
        #                      declaration of struct ngcomplex".
        #   anything else      PySpice reports several ways.
        #
        # All of them mean the same thing, and none of them means the simulator
        # is absent. Raising here is what made this path look unusable for as
        # long as it did.
        logger.debug("in-process ngspice unusable (%s); out of process", error)
        return _run_transient_out_of_process(deck)

    previous = Path.cwd()
    try:
        if working_dir:
            os.chdir(working_dir)
        shared.load_circuit(deck)
        shared.run()
        plot = shared.plot(None, shared.last_plot)
    except Exception as error:  # noqa: BLE001 - ngspice reports many ways
        raise SimulationFailed(f"ngspice did not complete: {error}") from error
    finally:
        os.chdir(previous)

    if "time" not in plot:
        raise SimulationFailed(
            f"the run produced no time vector; it may not have been a "
            f"transient analysis. Vectors returned: {', '.join(sorted(plot))}"
        )

    signals = {}
    for name, vector in plot.items():
        try:
            signals[name] = vector.to_waveform()
        except Exception:  # noqa: BLE001 - a vector that will not convert is
            # not worth failing the whole run over.
            logger.debug("Could not convert vector %s", name)

    time = signals.pop("time")
    logger.info(
        "Transient run complete: %d points, %d signals", len(time), len(signals)
    )
    return Waveforms(time=time, signals=signals, deck=deck)


def _run_transient_out_of_process(deck: str) -> Waveforms:
    """Run a transient through an interpreter that can load ngspice.

    The in-process route needs PySpice and needs the library to load into this
    interpreter. When either is missing the simulator is still there - KiCad
    ships it, and KiCad bundles a Python built to match it. This runs the same
    deck through that.

    Args:
        deck: The SPICE netlist, carrying its own ``.tran`` directive.

    Returns:
        The waveforms.

    Raises:
        SimulationUnavailable: If no reachable ngspice exists at all.
        SimulationFailed: If it ran but produced no time vector.
    """
    import numpy as np

    from .ngspice_runner import run_deck

    result = run_deck(deck, commands=("run",), vectors=("*",))
    if not result.ok and not result.vectors:
        if "no ngspice this process can load" in result.error:
            raise SimulationUnavailable(result.error)
        raise SimulationFailed(f"ngspice did not complete: {result.error}")

    signals = {name: np.asarray(values) for name, values in result.vectors.items()}
    if "time" not in signals:
        raise SimulationFailed(
            f"the run produced no time vector; it may not have been a "
            f"transient analysis. Vectors returned: {', '.join(sorted(signals))}"
        )

    time = signals.pop("time")
    logger.info(
        "Transient run complete out of process: %d points, %d signals",
        len(time),
        len(signals),
    )
    return Waveforms(time=time, signals=signals, deck=deck)


def simulate_schematic(
    schematic: Path,
    library: Optional[Path] = None,
) -> Waveforms:
    """Export a schematic's SPICE deck and run it.

    Args:
        schematic: The root ``.kicad_sch`` of a project prepared for
            simulation.
        library: Path to the ngspice shared library, or None to find KiCad's.

    Returns:
        The waveforms.

    Raises:
        SimulationUnavailable: If the toolchain is not available.
        SimulationFailed: If the export or the run failed.
    """
    schematic = Path(schematic)
    deck = export_spice_netlist(schematic)
    return run_transient(deck, library=library, working_dir=schematic.parent)


def missing_elements(deck: str, expected: Iterable[str]) -> List[str]:
    """Report which expected parts are absent from a SPICE deck.

    A symbol without ``Sim.*`` properties does not appear in the netlist and
    nothing reports it, so the simulation runs on a circuit quietly missing a
    part. This is the check that catches it.

    Args:
        deck: The SPICE netlist.
        expected: Reference designators that should be in it.

    Returns:
        The references that are absent, sorted.
    """
    # SPICE prefixes some elements with their type letter: a KiCad symbol
    # "Q1" with a MOSFET model becomes "MQ1" in the deck.
    present = set()
    for element in netlist_elements(deck):
        present.add(element)
        present.add(element.lstrip("MQXDVIRCLK"))
        if len(element) > 1:
            present.add(element[1:])

    return sorted(set(expected) - present)
