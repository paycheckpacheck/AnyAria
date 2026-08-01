"""Check that the circuit-synth features this repository pins are present.

These are integration guards rather than tests of AnyAria's own behaviour: if
the pinned branch moves and loses one of the two features, these fail loudly
rather than the examples breaking in a confusing way.
"""

import re
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_hierarchical_port_api_is_available():
    """PR #617: the port markers and Port type are exported."""
    from circuit_synth import (
        Bidirectional,
        Input,
        Output,
        PassivePort,
        Port,
        PortDirection,
        TriState,
    )

    assert PortDirection.INPUT.value == "input"
    assert Input.direction is PortDirection.INPUT
    assert Output.direction is PortDirection.OUTPUT
    assert Bidirectional.direction is PortDirection.BIDIRECTIONAL
    assert TriState.direction is PortDirection.TRI_STATE
    assert PassivePort.direction is PortDirection.PASSIVE
    assert Port("HI", PortDirection.INPUT, "AH").to_dict() == {
        "name": "HI",
        "direction": "input",
        "net": "AH",
    }


def test_jlc_component_import_is_available():
    """PR #616: the JLCPCB import entry points are exported."""
    from circuit_synth.manufacturing.jlcpcb import (
        JlcPartNotFoundError,
        import_jlc_component,
        lookup_lcsc_part,
    )

    assert callable(import_jlc_component)
    assert callable(lookup_lcsc_part)
    assert issubclass(JlcPartNotFoundError, Exception)


def test_a_block_declares_its_ports():
    """A block's annotated parameters become its interface."""
    from circuit_synth import Component, Input, Net, Output, PortDirection, circuit

    @circuit(name="Block")
    def block(SIG_IN: Input, SIG_OUT: Output):
        resistor = Component(symbol="Device:R", ref="R", value="1k")
        resistor[1] += SIG_IN
        resistor[2] += SIG_OUT

    @circuit(name="Top")
    def top():
        block(Net("SRC"), Net("DST"))

    ports = top().subcircuits[0].ports
    assert [(port.name, port.direction) for port in ports] == [
        ("SIG_IN", PortDirection.INPUT),
        ("SIG_OUT", PortDirection.OUTPUT),
    ]


def test_repeated_blocks_get_their_own_sheets():
    """Instantiating one block three times gives three schematics."""
    from circuit_synth import Component, Input, Net, Output, circuit

    @circuit(name="Stage")
    def stage(IN: Input, OUT: Output):
        resistor = Component(
            symbol="Device:R", ref="R", value="1k",
            footprint="Resistor_SMD:R_0603_1608Metric",
        )
        resistor[1] += IN
        resistor[2] += OUT

    @circuit(name="Chain")
    def chain():
        nets = [Net(f"N{index}") for index in range(4)]
        for first, second in zip(nets, nets[1:]):
            stage(first, second)

    directory = Path(tempfile.mkdtemp())
    try:
        project = directory / "chain"
        chain().generate_kicad_project(
            str(project), force_regenerate=True, generate_pcb=False
        )
        assert (project / "Stage.kicad_sch").exists()
        assert (project / "Stage2.kicad_sch").exists()
        assert (project / "Stage3.kicad_sch").exists()

        # The parent carries one typed sheet pin per declared port.
        root = (project / "Chain.kicad_sch").read_text(encoding="utf-8")
        pins = re.findall(r'\(pin "([^"]+)" (\w+)\n', root)
        assert pins == [("IN", "input"), ("OUT", "output")] * 3
    finally:
        shutil.rmtree(directory, ignore_errors=True)


@pytest.mark.skipif(
    not (EXAMPLES / "three_phase_driver.py").exists(), reason="example is missing"
)
def test_the_example_builds_three_half_bridges():
    """The bundled example generates one sheet per phase."""
    sys.path.insert(0, str(EXAMPLES))
    try:
        from three_phase_driver import three_phase_driver
    finally:
        sys.path.pop(0)

    directory = Path(tempfile.mkdtemp())
    try:
        project = directory / "three_phase"
        three_phase_driver().generate_kicad_project(
            str(project), force_regenerate=True, generate_pcb=False
        )
        for name in ("HalfBridge", "HalfBridge2", "HalfBridge3"):
            assert (project / f"{name}.kicad_sch").exists(), f"missing {name}"
    finally:
        shutil.rmtree(directory, ignore_errors=True)
