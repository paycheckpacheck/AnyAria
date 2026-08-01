"""Making a generated block probeable in KiCad's own simulator.

The end this serves is a specific one: open the project in KiCad, choose
``Inspect -> Simulator``, click ``Probe`` and then click a net, and get the
time-domain waveform for that net. KiCad can already do all of that. What it
needs from a generated schematic is three things, and this module writes all
three.

* **SPICE properties on the symbols.** ``Sim.Device``, ``Sim.Pins`` and either
  ``Sim.Params`` or ``Sim.Library``/``Sim.Name``. A symbol without them is not
  an error - it is silently absent from the netlist, which is worse.
* **Simulation directives.** A plain ``(text ...)`` element whose content
  begins with a dot. KiCad's SPICE netlister scans schematic text for these
  and copies them into the deck; that is verified here rather than assumed,
  because it is the one part of the arrangement with no visible failure mode.
* **A workbook.** A ``.wbk`` file beside the project holding the analysis and
  the signals to plot. Without it the simulator opens empty and the user has
  to retype the analysis command; with it the plot is already on screen.

The reason to drive KiCad's simulator rather than to build a parallel PySpice
model is that a parallel model is a second circuit that has to be kept in step
with the first, and it never is. Here there is one circuit. :mod:`ngspice_run`
exports the deck with ``kicad-cli`` and runs *that*, so a figure annotated onto
the schematic and the waveform the user sees when they click Probe come from
the same netlist by construction.
"""

import json
import logging
import re
import uuid as uuid_module
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from ..kicad.layout.sexp import (
    find_block,
    insert_before_end,
    iter_blocks,
    read_property,
)
from .spice_models import Assignment, ModelFile, ModelGap

logger = logging.getLogger(__name__)

# The colours KiCad's simulator cycles through for traces. Matching them means
# a workbook written here looks like one the user saved themselves.
TRACE_COLOURS: Sequence[str] = (
    "rgb(55, 126, 184)",
    "rgb(228, 26, 28)",
    "rgb(77, 175, 74)",
    "rgb(152, 78, 163)",
    "rgb(255, 127, 0)",
    "rgb(166, 86, 40)",
)

# KiCad writes this for a voltage trace in a transient plot.
VOLTAGE_TRACE_TYPE = 257

# Workbook schema version KiCad 9 and 10 write.
WORKBOOK_VERSION = 6

# Directives KiCad's simulator adds to every run of its own accord. Repeating
# them in the workbook is what KiCad itself does.
STANDARD_COMMANDS: Sequence[str] = (".kicad adjustpaths", ".save all")

# The directives KiCad's netlister recognises in schematic text. Anything else
# beginning with a dot is drawn on the sheet and never executed, which looks
# exactly like a directive that ran and did nothing. The list is taken from
# NETLIST_EXPORTER_SPICE::ReadDirectives; the token must be followed by a
# space or end the line, so ".tran10n" does not qualify.
RECOGNISED_DIRECTIVES = frozenset(
    {
        ".AC",
        ".CONTROL",
        ".CSPARAM",
        ".DISTO",
        ".DC",
        ".ELSE",
        ".ELSEIF",
        ".END",
        ".ENDC",
        ".ENDIF",
        ".ENDS",
        ".FOUR",
        ".FUNC",
        ".GLOBAL",
        ".IC",
        ".IF",
        ".INCLUDE",
        ".LIB",
        ".MEAS",
        ".MODEL",
        ".NODESET",
        ".NOISE",
        ".OP",
        ".OPTIONS",
        ".PARAM",
        ".PLOT",
        ".PRINT",
        ".PROBE",
        ".PZ",
        ".SAVE",
        ".SENS",
        ".SP",
        ".SUBCKT",
        ".TEMP",
        ".TF",
        ".TRAN",
        ".WIDTH",
    }
)


@dataclass(frozen=True)
class Substitution:
    """A part that was replaced by something simulatable, and the cost of it.

    Every substitution narrows what the simulation is evidence for. Recording
    the narrowing next to the substitution is what stops a waveform being read
    as saying more than it does.

    Attributes:
        reference: The part that was replaced, such as ``"U4"``.
        replaced_by: What stands in for it, such as ``"two PULSE sources with
            the IR2101's propagation delay and dead time"``.
        justification: Why the stand-in is defensible for this measurement.
        limits: What the simulation therefore cannot tell you. This field is
            required, because a substitution that costs nothing does not
            exist.
    """

    reference: str
    replaced_by: str
    justification: str
    limits: str

    def __post_init__(self) -> None:
        """Reject a substitution that claims to cost nothing.

        Raises:
            ValueError: If the limits are blank.
        """
        if not self.limits.strip():
            raise ValueError(
                f"substitution for {self.reference} does not say what it "
                f"costs; every stand-in narrows what the simulation proves"
            )


@dataclass
class ProbeProject:
    """A generated KiCad project that its own simulator can run.

    Attributes:
        directory: The project directory.
        schematic: The root ``.kicad_sch``.
        workbook: The ``.wbk`` holding the analysis and the traces.
        directives: The SPICE directives written into the schematic.
        traces: The signals the workbook plots, such as ``"V(/PHASE)"``.
        substitutions: Parts replaced to make the block simulatable.
        gaps: Parts that got no model at all.
    """

    directory: Path
    schematic: Path
    workbook: Path
    directives: List[str] = field(default_factory=list)
    traces: List[str] = field(default_factory=list)
    substitutions: List[Substitution] = field(default_factory=list)
    gaps: List[ModelGap] = field(default_factory=list)

    def summary(self) -> str:
        """Write the report shown after the project is built.

        Returns:
            A multi-line report leading with what the simulation does not
            cover.
        """
        lines = [f"Probe project: {self.directory}"]
        lines.append(f"  open {self.schematic.name}, then Inspect -> Simulator")

        if self.gaps:
            lines.append("")
            lines.append("Parts with no SPICE model, absent from the netlist:")
            lines.extend(f"  - {gap}" for gap in self.gaps)

        if self.substitutions:
            lines.append("")
            lines.append("Substitutions, and what they cost:")
            for item in self.substitutions:
                lines.append(f"  - {item.reference} -> {item.replaced_by}")
                lines.append(f"      why:   {item.justification}")
                lines.append(f"      limit: {item.limits}")

        lines.append("")
        lines.append(f"Directives: {'; '.join(self.directives)}")
        lines.append(f"Traces:     {', '.join(self.traces)}")
        return "\n".join(lines)


def _property_block(name: str, value: str, x: float, y: float) -> str:
    """Render one hidden symbol property.

    Args:
        name: The property name, such as ``"Sim.Device"``.
        value: The property value.
        x: X position, which for a hidden property only has to be inside the
            sheet.
        y: Y position.

    Returns:
        The property s-expression, indented for a symbol block and starting
        with a newline.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return (
        f'\n\t\t(property "{name}" "{escaped}"'
        f"\n\t\t\t(at {x:g} {y:g} 0)"
        f"\n\t\t\t(effects"
        f"\n\t\t\t\t(font"
        f"\n\t\t\t\t\t(size 1.27 1.27)"
        f"\n\t\t\t\t)"
        f"\n\t\t\t\t(hide yes)"
        f"\n\t\t\t)"
        f"\n\t\t)"
    )


def _last_property_end(block: str) -> int:
    """Find where the last property in a symbol block ends.

    New properties are inserted there so they sit with the existing ones
    rather than after the pin list, which is where KiCad writes them.

    Args:
        block: The symbol block text.

    Returns:
        An offset into the block, one past the last property's closing
        parenthesis. Falls back to just before the block's own closing
        parenthesis when the symbol has no properties.
    """
    end = -1
    for match in re.finditer(r"\(property\s", block):
        try:
            _, block_end = find_block(block, match.start())
        except ValueError:
            continue
        end = max(end, block_end)

    if end < 0:
        return block.rstrip().rfind(")")
    return end


def _symbol_position(block: str) -> tuple:
    """Read a placed symbol's own position.

    Args:
        block: The symbol block text.

    Returns:
        An ``(x, y)`` pair, defaulting to the origin when the block has no
        position of its own.
    """
    match = re.search(r"\(at\s+(-?[\d.]+)\s+(-?[\d.]+)", block)
    if not match:
        return 0.0, 0.0
    return float(match.group(1)), float(match.group(2))


def apply_assignments(
    schematic: Path,
    assignments: Iterable[Assignment],
    excluded: Iterable[str] = (),
) -> Dict[str, int]:
    """Write SPICE properties onto the symbols of one sheet.

    Args:
        schematic: The ``.kicad_sch`` to edit, in place.
        assignments: The properties to write, keyed to symbols by reference
            designator. Assignments naming a reference the sheet does not have
            are skipped, so one set may be applied across several sheets.
        excluded: References to mark ``exclude_from_sim``, so KiCad leaves
            them out of the netlist instead of failing on them.

    Returns:
        A count of what changed, with keys ``"symbols"``, ``"properties"``
        and ``"excluded"``.
    """
    by_reference = {item.reference: item for item in assignments}
    excluded = set(excluded)
    text = schematic.read_text(encoding="utf-8")

    counts = {"symbols": 0, "properties": 0, "excluded": 0}

    # Back to front, so each edit leaves the offsets of the earlier blocks
    # untouched.
    for start, end in reversed(list(iter_blocks(text, "symbol"))):
        block = text[start:end]
        reference = read_property(block, "Reference")
        if reference is None:
            continue

        if reference in excluded:
            updated = block.replace(
                "(exclude_from_sim no)", "(exclude_from_sim yes)", 1
            )
            if updated != block:
                text = text[:start] + updated + text[end:]
                counts["excluded"] += 1
            continue

        assignment = by_reference.get(reference)
        if assignment is None:
            continue

        x, y = _symbol_position(block)
        additions = "".join(
            _property_block(name, value, x, y)
            for name, value in assignment.properties.items()
            # Do not write a property the symbol already carries twice.
            if read_property(block, name) is None
        )

        updated = block
        if assignment.value_field is not None:
            updated = re.sub(
                r'(\(property\s+"Value"\s+)"[^"]*"',
                lambda m: m.group(1) + '"' + assignment.value_field + '"',
                updated,
                count=1,
            )

        if additions:
            insert_at = _last_property_end(updated)
            updated = updated[:insert_at] + additions + updated[insert_at:]

        if updated != block:
            text = text[:start] + updated + text[end:]
            counts["symbols"] += 1
            counts["properties"] += len(assignment.properties)

    schematic.write_text(text, encoding="utf-8")
    logger.info(
        "Wrote SPICE properties to %s: %d symbols, %d properties, %d excluded",
        schematic.name,
        counts["symbols"],
        counts["properties"],
        counts["excluded"],
    )
    return counts


def add_directives(
    schematic: Path,
    directives: Sequence[str],
    at: tuple = (25.4, 25.4),
) -> None:
    """Write SPICE directives into a schematic as a text element.

    KiCad's SPICE netlister scans schematic text for lines beginning with one
    of the directives it recognises and copies the whole text element into the
    deck. That is how ``.tran``, ``.model``, ``.include`` and ``.ic`` reach the
    simulator. Only ``text`` and ``text_box`` items are scanned - a directive
    put on a label of any kind is silently ignored.

    One asymmetry is worth knowing, because it looks like a bug from either
    side. ``kicad-cli`` emits the ``.tran`` from here into the exported deck,
    but the interactive simulator suppresses analysis commands found in
    schematic text and uses the analysis tab's own command instead. So the
    directive written here is what makes the exported netlist runnable, and
    the workbook written by :func:`write_workbook` is what makes the GUI open
    with the same analysis. Both are needed; neither alone covers both paths.

    Args:
        schematic: The ``.kicad_sch`` to edit, in place.
        directives: The directive lines, such as ``[".tran 20n 2m 0 20n uic"]``.
            Written into one text element, one per line.
        at: Where to put the text block on the sheet, in mm.

    Raises:
        ValueError: If any directive is not one KiCad recognises, since it
            would then be drawn on the sheet and never executed - which is
            indistinguishable from a directive that ran and did nothing.
    """
    for directive in directives:
        token = directive.split(" ", 1)[0].upper()
        if token not in RECOGNISED_DIRECTIVES:
            raise ValueError(
                f"directive {directive!r} is not one KiCad's netlister "
                f"recognises, so it would be drawn on the sheet and never "
                f"executed. Recognised directives are: "
                f"{', '.join(sorted(RECOGNISED_DIRECTIVES))}"
            )

    # An .include names a file in quotes, so the directive text almost always
    # contains quotes of its own. Each line is escaped on its own and the
    # lines are then joined with the newline escape KiCad reads back, so the
    # separator cannot be mangled by the escaping. Unescaped quotes close the
    # s-expression string early and KiCad refuses the whole sheet.
    escaped = [
        directive.replace("\\", "\\\\").replace('"', '\\"') for directive in directives
    ]
    body = "\\n".join(escaped)
    element = (
        f'\n\t(text "{body}"'
        f"\n\t\t(exclude_from_sim no)"
        f"\n\t\t(at {at[0]:g} {at[1]:g} 0)"
        f"\n\t\t(effects"
        f"\n\t\t\t(font"
        f"\n\t\t\t\t(size 1.27 1.27)"
        f"\n\t\t\t)"
        f"\n\t\t\t(justify left bottom)"
        f"\n\t\t)"
        f'\n\t\t(uuid "{uuid_module.uuid4()}")'
        f"\n\t)"
    )

    text = schematic.read_text(encoding="utf-8")
    schematic.write_text(insert_before_end(text, element), encoding="utf-8")
    logger.info("Wrote %d SPICE directives into %s", len(directives), schematic.name)


def write_workbook(
    path: Path,
    analysis_command: str,
    traces: Sequence[str],
    analysis: str = "TRAN",
) -> None:
    """Write the simulator workbook so the plot is on screen at first open.

    Args:
        path: The ``.wbk`` file to write, beside the project.
        analysis_command: The analysis directive, such as
            ``".tran 20n 2m 0 20n uic"``.
        traces: Signals to plot, in KiCad's spelling - ``"V(/PHASE)"`` for a
            net voltage, ``"I(R5)"`` for a device current.
        analysis: The analysis type KiCad tabs the plot under.

    Raises:
        ValueError: If no traces are given, since an empty workbook is worse
            than none - it opens a blank plot that looks like a failed run.
    """
    if not traces:
        raise ValueError(
            "a workbook with no traces opens as an empty plot, which reads as "
            "a simulation that ran and found nothing; name the signals to plot"
        )

    workbook = {
        "last_sch_text_sim_command": analysis_command,
        "tabs": [
            {
                "analysis": analysis,
                "commands": [analysis_command, *STANDARD_COMMANDS],
                "dottedSecondary": False,
                "margins": {"bottom": 45, "left": 70, "right": 140, "top": 30},
                "measurements": [],
                "showGrid": True,
                "traces": [
                    {
                        "color": TRACE_COLOURS[index % len(TRACE_COLOURS)],
                        "signal": signal,
                        "trace_type": VOLTAGE_TRACE_TYPE,
                    }
                    for index, signal in enumerate(traces)
                ],
            }
        ],
        "user_defined_signals": [],
        "version": WORKBOOK_VERSION,
    }

    path.write_text(json.dumps(workbook, indent=2), encoding="utf-8")
    logger.info("Wrote workbook %s with %d traces", path.name, len(traces))


def link_workbook(project_file: Path, workbook: Path) -> bool:
    """Point a KiCad project at its simulator workbook.

    Writing the workbook is not enough on its own. KiCad only loads one when
    the project file names it, so without this the simulator opens empty and
    the analysis and traces have to be retyped - which is exactly the friction
    the workbook exists to remove.

    Args:
        project_file: The ``.kicad_pro`` to edit, in place.
        workbook: The ``.wbk`` to point it at. Stored relative to the project.

    Returns:
        True when the project file was updated, False when there is no project
        file to update.
    """
    if not project_file.exists():
        logger.warning(
            "No %s, so the workbook will not load automatically", project_file.name
        )
        return False

    project = json.loads(project_file.read_text(encoding="utf-8"))
    schematic = project.setdefault("schematic", {})
    ngspice = schematic.setdefault("ngspice", {})
    ngspice["workbook_filename"] = workbook.name
    # Model files are written beside the schematic and referenced by name, so
    # KiCad has to resolve them against the project directory.
    ngspice.setdefault("fix_include_paths", True)

    project_file.write_text(json.dumps(project, indent=2), encoding="utf-8")
    logger.info("Pointed %s at workbook %s", project_file.name, workbook.name)
    return True


def make_probeable(
    project_dir: Path,
    assignments: Iterable[Assignment],
    directives: Sequence[str],
    traces: Sequence[str],
    schematic: Optional[Path] = None,
    excluded: Iterable[str] = (),
    model_files: Sequence[ModelFile] = (),
    substitutions: Sequence[Substitution] = (),
    gaps: Sequence[ModelGap] = (),
) -> ProbeProject:
    """Turn a generated KiCad project into one its simulator can run.

    Args:
        project_dir: The generated project directory.
        assignments: SPICE properties to write onto the symbols.
        directives: SPICE directives, the first of which should be the
            analysis command.
        traces: Signals for the workbook to plot.
        schematic: The root schematic. Defaults to the only ``.kicad_sch`` in
            the directory, or the one matching the directory name.
        excluded: References to leave out of the simulation.
        model_files: Model card files to write beside the schematic. An
            ``.include`` directive for each is added automatically.
        substitutions: Parts replaced to make the block simulatable.
        gaps: Parts that got no model, for the report.

    Returns:
        The assembled project, whose :meth:`ProbeProject.summary` says what
        the simulation does and does not cover.

    Raises:
        FileNotFoundError: If the root schematic cannot be found.
        ValueError: If no analysis directive was given.
    """
    project_dir = Path(project_dir)
    if schematic is None:
        schematic = _find_root_schematic(project_dir)
    schematic = Path(schematic)
    if not schematic.exists():
        raise FileNotFoundError(f"no schematic at {schematic}")

    if not directives:
        raise ValueError("no SPICE directives given; the simulator needs an analysis")

    for model_file in model_files:
        (project_dir / model_file.name).write_text(model_file.content, encoding="utf-8")
        logger.info("Wrote model file %s", model_file.name)

    # No .include is emitted for these. A symbol carrying Sim.Library already
    # makes KiCad write one, with the path resolved, and a second include of
    # the same file redefines every model card in it. A model file that no
    # symbol references needs an explicit .include in `directives`.
    all_directives = list(directives)

    apply_assignments(schematic, assignments, excluded=excluded)
    add_directives(schematic, all_directives)

    workbook = schematic.with_suffix(".wbk")
    write_workbook(workbook, directives[0], traces)
    link_workbook(schematic.with_suffix(".kicad_pro"), workbook)

    project = ProbeProject(
        directory=project_dir,
        schematic=schematic,
        workbook=workbook,
        directives=list(all_directives),
        traces=list(traces),
        substitutions=list(substitutions),
        gaps=list(gaps),
    )
    logger.info("Built probe project at %s", project_dir)
    return project


def _find_root_schematic(project_dir: Path) -> Path:
    """Find a project's root schematic.

    Args:
        project_dir: The project directory.

    Returns:
        The root ``.kicad_sch``.

    Raises:
        FileNotFoundError: If the directory holds no schematic.
    """
    sheets = sorted(project_dir.glob("*.kicad_sch"))
    if not sheets:
        raise FileNotFoundError(f"no .kicad_sch in {project_dir}")

    # A project generated by circuit-synth names its root after the project.
    named = project_dir / f"{project_dir.name}.kicad_sch"
    if named in sheets:
        return named

    project_files = sorted(project_dir.glob("*.kicad_pro"))
    if project_files:
        candidate = project_files[0].with_suffix(".kicad_sch")
        if candidate in sheets:
            return candidate

    return sheets[0]
