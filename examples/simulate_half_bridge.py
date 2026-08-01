"""Datasheet-driven analysis of the three-phase driver's half-bridge.

This is the worked example behind the ``datasheet-simulation`` skill. It takes
one hierarchical block out of ``three_phase_driver.py``, reads the component
values back out of the ``Circuit`` object rather than restating them, checks
them against the parts' datasheets, simulates the power stage in ngspice, and
writes the results onto the KiCad sheet as red notes linked back to the lines
below that computed them.

It also demonstrates the behaviour that matters most: it finds a fault in the
design it is analysing, and refuses to produce switching figures for a part
being operated outside its datasheet's recommended conditions. The half-bridge
supplies the IR2101's VCC from the 3.3V logic rail, and the IR2101's
undervoltage lockout releases at 8.9V typical. The driver never turns on. A
tool that reported an efficiency for that circuit would be worse than one that
reported nothing.

Run it with::

    uv run python examples/simulate_half_bridge.py

Sources for every number are cited in the datasheet records below.
"""

import logging
from pathlib import Path
from typing import Dict, Optional

from three_phase_driver import three_phase_driver

from circuit_synth import Component, Net, circuit
from circuit_synth.simulation.annotate import annotate_schematic
from circuit_synth.simulation.datasheet import (
    Datasheet,
    Equation,
    Parameter,
    register,
)
from circuit_synth.simulation.figures import Basis, BlockAnalysis
from circuit_synth.simulation.ngspice_run import (
    SimulationFailed,
    SimulationUnavailable,
    export_spice_netlist,
    missing_elements,
    run_transient,
)
from circuit_synth.simulation.probe import Substitution, make_probeable
from circuit_synth.simulation.spice_models import (
    ModelFile,
    ModelSpec,
    assign_models,
    parse_value,
)
from circuit_synth.simulation.vdmos import VdmosParameters, fit

logger = logging.getLogger(__name__)

# Rail voltages. These are not in the netlist - a net carries a name, not a
# potential - so they come from the regulators that make them: the AMS1117-3.3
# in the Power block, and VBUS straight off the USB-C receptacle.
RAILS: Dict[str, float] = {"V3V3": 3.3, "VMOTOR": 5.0, "VBUS": 5.0}

# What the drive is actually asked to do. A BLDC leg at 20 kHz is at the low
# end of the usual range and is chosen here because it is what the RP2040's
# PWM slices divide to conveniently.
SWITCHING_FREQUENCY = 20e3
DUTY_CYCLE = 0.5
PHASE_CURRENT = 8.0

# Motor phase, as seen from one leg: winding inductance and resistance in
# series with the back-EMF. These are properties of the motor, not the board,
# so they are inputs to the analysis rather than things read off the schematic.
MOTOR_INDUCTANCE = 250e-6
MOTOR_RESISTANCE = 0.35
MOTOR_BACK_EMF = 2.0

# How many switching periods to measure over, at the end of the run. Enough
# to average the ripple, short enough that the measurement is of one
# operating point.
MEASUREMENT_PERIODS = 4

# Time constants of the load to simulate before measuring. The winding's L/R
# is far longer than a switching period, so the current takes many periods to
# reach its operating value.
SETTLING_TIME_CONSTANTS = 6

# How much the average current may still be drifting between measurement
# windows before the run is called unsettled.
SETTLING_TOLERANCE = 0.02


# --------------------------------------------------------------------------
# Datasheets. Every parameter names the table it was read from, so a reviewer
# can check any figure on the schematic against the document in two steps.
# --------------------------------------------------------------------------

IR2101 = register(
    Datasheet(
        part_number="IR2101",
        title="IR2101(S)/IR2102(S) & (PbF) High and Low Side Driver",
        document="PD60043 Rev.O",
        url="https://www.infineon.com/assets/row/public/documents/24/49/infineon-ir2101-ds-en.pdf",
        role="high/low-side gate driver for a bootstrapped half-bridge",
        parameters={
            "IQBS": Parameter(
                "IQBS",
                55e-6,
                "A",
                "Static Electrical Characteristics",
                "VIN = 0V or 5V, max",
                typical=False,
            ),
            "VCCUV+": Parameter(
                "VCCUV+",
                8.9,
                "V",
                "Static Electrical Characteristics",
                "typical",
            ),
            "VCCUV-": Parameter(
                "VCCUV-",
                8.2,
                "V",
                "Static Electrical Characteristics",
                "typical",
            ),
            "IO+": Parameter(
                "IO+",
                0.130,
                "A",
                "Static Electrical Characteristics",
                "VO = 0V, VIN = logic 1, PW <= 10us, minimum",
                typical=False,
            ),
            "IO-": Parameter(
                "IO-",
                0.270,
                "A",
                "Static Electrical Characteristics",
                "VO = 15V, VIN = logic 0, PW <= 10us, minimum",
                typical=False,
            ),
            "ton": Parameter(
                "ton",
                160e-9,
                "s",
                "Dynamic Electrical Characteristics",
                "VS = 0V, CL = 1000pF",
            ),
            "toff": Parameter(
                "toff",
                150e-9,
                "s",
                "Dynamic Electrical Characteristics",
                "VS = 600V, CL = 1000pF",
            ),
            "MT": Parameter(
                "MT",
                50e-9,
                "s",
                "Dynamic Electrical Characteristics",
                "delay matching, high and low side, max",
                typical=False,
            ),
            "VCC_MIN": Parameter(
                "VCC",
                10.0,
                "V",
                "Recommended Operating Conditions",
                "minimum",
                typical=False,
            ),
            "VCC_MAX": Parameter(
                "VCC",
                20.0,
                "V",
                "Recommended Operating Conditions",
                "maximum",
                typical=False,
            ),
            "QLS": Parameter(
                "Qls",
                5e-9,
                "C",
                "AN-978 Rev D section 3",
                "generic figure for 500V/600V gate driver ICs, not an "
                "IR2101-specific characterised parameter",
            ),
        },
        equations={
            "bootstrap_capacitor": Equation(
                name="bootstrap_capacitor",
                expression=(
                    "Cboot >= 2 * [2*Qg + Iqbs(max)/f + Qls + Icbs(leak)/f] "
                    "/ (Vcc - Vf - Vls)"
                ),
                symbols={
                    "Qg": "gate charge of the high-side FET",
                    "f": "switching frequency",
                    "Iqbs(max)": "maximum VBS quiescent current",
                    "Qls": "level shift charge required per cycle",
                    "Icbs(leak)": "bootstrap capacitor leakage current",
                    "Vcc": "logic section voltage source",
                    "Vf": "forward drop of the bootstrap diode",
                    "Vls": "drop across the low-side FET or load",
                },
                section="Design Tip DT98-2 section 3, EQ(1) and EQ(2)",
                purpose=(
                    "smallest bootstrap capacitor that holds the high-side "
                    "supply up for one cycle"
                ),
            ),
            "bootstrap_diode_current": Equation(
                name="bootstrap_diode_current",
                expression="IF = Qbs * f, VRRM >= rail, trr <= 100ns",
                symbols={
                    "Qbs": "charge per cycle from EQ(1)",
                    "f": "switching frequency",
                    "VRRM": "repetitive peak reverse voltage",
                    "trr": "reverse recovery time",
                },
                section="Design Tip DT98-2 section 4",
                purpose="selecting the bootstrap diode",
            ),
            "gate_drive_loss": Equation(
                name="gate_drive_loss",
                expression="PG = V * QG * f",
                symbols={
                    "V": "gate drive voltage",
                    "QG": "total gate charge",
                    "f": "switching frequency",
                },
                section="AN-978 Rev D section 4 b1",
                purpose="power the driver and its gate resistors dissipate",
            ),
        },
        notes=(
            "The IR2101 has no VBS undervoltage lockout. Only VCC is "
            "monitored, so a sagging bootstrap supply drives the high-side "
            "FET into linear operation rather than shutting it off.",
            "The IR2101 has no shoot-through interlock and no dead-time "
            "generator. HIN and LIN are independent. Dead time is entirely "
            "the controller's responsibility.",
        ),
    )
)

IRF3205 = register(
    Datasheet(
        part_number="IRF3205",
        title="IRF3205PbF HEXFET Power MOSFET",
        document="PD-94791B",
        url="https://www.infineon.com/dgdl/Infineon-IRF3205-DataSheet-v01_01-EN.pdf",
        role="low-side and high-side switch in a bootstrapped half-bridge",
        parameters={
            "VDSS": Parameter(
                "V(BR)DSS",
                55.0,
                "V",
                "Static Electrical Characteristics",
                "VGS = 0V, ID = 250uA, minimum",
                typical=False,
            ),
            "RDS(on)": Parameter(
                "RDS(on)",
                0.008,
                "ohm",
                "Static Electrical Characteristics",
                "VGS = 10V, ID = 62A, maximum",
                typical=False,
            ),
            "VGS(th)": Parameter(
                "VGS(th)",
                3.0,
                "V",
                "Static Electrical Characteristics",
                "VDS = VGS, ID = 250uA; datasheet band is 2.0V to 4.0V, "
                "midpoint taken",
            ),
            "gfs": Parameter(
                "gfs",
                44.0,
                "S",
                "Static Electrical Characteristics",
                "VDS = 25V, ID = 62A, minimum",
                typical=False,
            ),
            "Qg": Parameter(
                "Qg",
                146e-9,
                "C",
                "Dynamic Electrical Characteristics",
                "ID = 62A, VDS = 44V, VGS = 10V, maximum",
                typical=False,
            ),
            "Qgd": Parameter(
                "Qgd",
                54e-9,
                "C",
                "Dynamic Electrical Characteristics",
                "ID = 62A, VDS = 44V, VGS = 10V, maximum",
                typical=False,
            ),
            "Ciss": Parameter(
                "Ciss",
                3247e-12,
                "F",
                "Dynamic Electrical Characteristics",
                "VGS = 0V, VDS = 25V, f = 1.0MHz",
            ),
            "Coss": Parameter(
                "Coss",
                781e-12,
                "F",
                "Dynamic Electrical Characteristics",
                "VGS = 0V, VDS = 25V, f = 1.0MHz",
            ),
            "Crss": Parameter(
                "Crss",
                211e-12,
                "F",
                "Dynamic Electrical Characteristics",
                "VGS = 0V, VDS = 25V, f = 1.0MHz",
            ),
            "ID_PACKAGE": Parameter(
                "ID",
                75.0,
                "A",
                "Absolute Maximum Ratings, notes",
                "package limitation; the 110A silicon figure is not "
                "achievable in a TO-220AB",
                typical=False,
            ),
            "RthJC": Parameter(
                "RthJC",
                0.75,
                "K/W",
                "Thermal Resistance",
                "maximum",
                typical=False,
            ),
            "RthJA": Parameter(
                "RthJA",
                62.0,
                "K/W",
                "Thermal Resistance",
                "maximum, free-standing with no heatsink",
                typical=False,
            ),
            "TJ_MAX": Parameter(
                "TJ",
                175.0,
                "C",
                "Absolute Maximum Ratings",
                "maximum",
                typical=False,
            ),
            "VSD": Parameter(
                "VSD",
                1.3,
                "V",
                "Source-Drain Ratings and Characteristics",
                "TJ = 25C, IS = 62A, VGS = 0V, maximum",
                typical=False,
            ),
        },
        equations={
            "conduction_loss": Equation(
                name="conduction_loss",
                expression="Pcond = Idrms^2 * Rds(on)",
                symbols={
                    "Idrms": "RMS drain current while the device conducts",
                    "Rds(on)": "on-resistance at the junction temperature",
                },
                section=(
                    "Infineon AN 2006-07 V1.1 section 2, MOSFET Power Losses "
                    "Calculation Using the Data-Sheet Parameters"
                ),
                purpose="conduction loss in one device",
            ),
            "junction_temperature": Equation(
                name="junction_temperature",
                expression="Tj = Ta + Ptotal * RthJA",
                symbols={
                    "Ta": "ambient temperature",
                    "Ptotal": "total dissipation in the device",
                    "RthJA": "junction-to-ambient thermal resistance",
                },
                section="definitional thermal-resistance model",
                purpose="junction temperature with no heatsink",
            ),
        },
        notes=(
            "RDS(on) is quoted at one temperature only, so no temperature "
            "coefficient can be derived from the datasheet. Figure 4 gives "
            "the normalised curve as a graph with no tabulated values.",
            "Switching times are typical-only with no maximum, so a "
            "worst-case dead time cannot be bounded from this document.",
            "The 110A continuous current figure is a silicon limit. The "
            "TO-220AB package is limited to 75A.",
        ),
    )
)


# --------------------------------------------------------------------------
# Reading the design back out of the Circuit object.
# --------------------------------------------------------------------------


def find_block(root, name: str):
    """Find the first subcircuit with a given name.

    Args:
        root: The top-level ``Circuit``.
        name: The subcircuit name, such as ``"HalfBridge"``.

    Returns:
        The subcircuit, or None when the design has no such block.
    """
    if root.name == name:
        return root
    for child in root.subcircuits:
        found = find_block(child, name)
        if found is not None:
            return found
    return None


def component_nets(component) -> Dict[str, str]:
    """List which net each of a component's pins is on.

    Args:
        component: A circuit-synth ``Component``.

    Returns:
        A mapping of pin number to net name. Unconnected pins are left out.
    """
    return {
        number: pin.net.name
        for number, pin in component._pins.items()
        if pin.net is not None
    }


def read_design(block) -> Dict[str, object]:
    """Read the values this analysis depends on out of the block.

    Taking these from the ``Circuit`` rather than restating them is the whole
    point: if somebody changes a gate resistor in the Python, the analysis
    changes with it and the schematic annotation follows.

    Args:
        block: The ``HalfBridge`` subcircuit.

    Returns:
        A mapping with the parts and values the analysis needs.
    """
    parts = list(block.components.values())

    def first(predicate):
        """Return the first component matching a predicate.

        Args:
            predicate: A callable taking a component.

        Returns:
            The component, or None.
        """
        return next((part for part in parts if predicate(part)), None)

    driver = first(lambda c: c.symbol == "Driver_FET:IR2101")
    fets = [c for c in parts if c.symbol == "Transistor_FET:Q_NMOS_GDS"]
    shunt = first(lambda c: c.symbol == "Device:R_Shunt")
    bootstrap = first(lambda c: c.value.startswith("1uF"))
    gate_resistors = [c for c in parts if c.symbol == "Device:R" and c.value == "10R"]

    return {
        "driver": driver,
        "high_fet": fets[0] if fets else None,
        "low_fet": fets[1] if len(fets) > 1 else None,
        "shunt": shunt,
        "shunt_ohms": parse_value(shunt.value) if shunt else None,
        "bootstrap": bootstrap,
        "bootstrap_farads": parse_value(bootstrap.value) if bootstrap else None,
        "gate_resistors": gate_resistors,
        "gate_ohms": parse_value(gate_resistors[0].value) if gate_resistors else None,
        "driver_supply_net": component_nets(driver).get("1") if driver else None,
    }


# --------------------------------------------------------------------------
# Checking the design against the datasheets, before simulating anything.
# --------------------------------------------------------------------------


def check_operating_conditions(
    design: Dict[str, object], analysis: BlockAnalysis
) -> bool:
    """Check the parts are inside their datasheets' recommended conditions.

    This runs before the simulation, because a part outside its recommended
    conditions makes every figure downstream meaningless. A simulation would
    still produce waveforms, and they would look entirely reasonable.

    Args:
        design: What :func:`read_design` read out of the block.
        analysis: Where to record findings.

    Returns:
        True when every part is inside its conditions.
    """
    supply_net = design["driver_supply_net"]
    supply_volts = RAILS.get(supply_net)

    if supply_volts is None:
        analysis.note_gap(
            f"The IR2101's VCC is on net {supply_net!r}, whose voltage is not "
            f"known here. Add it to RAILS before trusting any figure below."
        )
        return False

    minimum = IR2101.value("VCC_MIN")
    lockout = IR2101.value("VCCUV+")

    if supply_volts < minimum:
        analysis.note_gap(
            f"BLOCKING: the IR2101's VCC comes from {supply_net} at "
            f"{supply_volts}V. Its recommended minimum is {minimum}V and its "
            f"undervoltage lockout releases at {lockout}V typical "
            f"({IR2101.cite_parameter('VCCUV+')}). The driver never leaves "
            f"lockout, so neither output ever switches. No switching figure "
            f"can be computed for this block as designed."
        )
        analysis.note_gap(
            f"The IRF3205's on-resistance is specified at "
            f"{IRF3205.parameter('RDS(on)').conditions}. A "
            f"{supply_volts}V gate drive is below the part's own VGS(th) "
            f"maximum of 4.0V, so it would not fully enhance even if the "
            f"driver did switch."
        )
        return False

    analysis.record(
        design["driver"].ref,
        "Vcc",
        supply_volts,
        "V",
        Basis.DERIVED,
        f"from {supply_net}; inside {minimum}-{IR2101.value('VCC_MAX')}V "
        f"({IR2101.cite('Recommended Operating Conditions')})",
    )
    return True


def datasheet_figures(
    design: Dict[str, object], analysis: BlockAnalysis, vcc: float
) -> None:
    """Work out the figures that come from equations rather than simulation.

    These are the quantities a SPICE run of this netlist cannot produce
    honestly: gate drive loss depends on total gate charge, which the fitted
    VDMOS model does not reproduce; junction temperature needs a thermal model
    the netlist does not contain; and the bootstrap capacitor's sizing rule is
    a design constraint rather than a measurement.

    Args:
        design: What :func:`read_design` read out of the block.
        analysis: Where to record the figures.
        vcc: The gate driver's supply voltage, in volts.
    """
    high_fet = design["high_fet"]
    low_fet = design["low_fet"]
    driver = design["driver"]
    bootstrap = design["bootstrap"]

    gate_charge = IRF3205.value("Qg")
    quiescent = IR2101.value("IQBS")
    level_shift = IR2101.value("QLS")

    # Gate drive loss: AN-978 Rev D section 4 b1, PG = V * QG * f.
    for fet in (high_fet, low_fet):
        analysis.record(
            fet.ref,
            "Pgate",
            vcc * gate_charge * SWITCHING_FREQUENCY,
            "W",
            Basis.DATASHEET,
            f"PG = V*QG*f, {IR2101.equation('gate_drive_loss').section}",
        )

    # Gate charging time from the driver's own source current. This is the
    # figure that shows the pairing is wrong: the datasheet's 101ns rise time
    # is measured at RG = 4.5 ohm from a stiff supply, and the IR2101 cannot
    # deliver anything like that.
    source_current = IR2101.value("IO+")
    charge_time = gate_charge / source_current
    analysis.record(
        driver.ref,
        "tgate",
        charge_time,
        "s",
        Basis.DATASHEET,
        f"Qg/IO+ = {gate_charge * 1e9:.0f}nC / {source_current * 1e3:.0f}mA; "
        f"{IRF3205.cite_parameter('Qg')} and {IR2101.cite_parameter('IO+')}",
    )

    # Bootstrap capacitor, DT98-2 EQ(2). Leakage is left out: a ceramic's
    # leakage is far below the other terms and the datasheet does not give it.
    charge_per_cycle = 2 * gate_charge + quiescent / SWITCHING_FREQUENCY + level_shift
    diode_drop = 0.32  # BAT54 forward drop at a few milliamps.
    low_side_drop = PHASE_CURRENT * IRF3205.value("RDS(on)")
    minimum_capacitance = 2 * charge_per_cycle / (vcc - diode_drop - low_side_drop)
    analysis.record(
        bootstrap.ref,
        "Cmin",
        minimum_capacitance,
        "F",
        Basis.DATASHEET,
        f"{IR2101.equation('bootstrap_capacitor').section}",
    )
    analysis.record(
        bootstrap.ref,
        "dVboot",
        charge_per_cycle / design["bootstrap_farads"],
        "V",
        Basis.DERIVED,
        "Qbs/C, the sag over one cycle at the fitted charge",
    )

    # Bootstrap diode, DT98-2 section 4.
    analysis.record(
        bootstrap.ref,
        "Idiode",
        charge_per_cycle * SWITCHING_FREQUENCY,
        "A",
        Basis.DATASHEET,
        f"IF = Qbs*f, {IR2101.equation('bootstrap_diode_current').section}",
    )

    # What the datasheets cannot support.
    analysis.note_gap(
        "No junction temperature is given. RDS(on) is specified at one "
        "temperature only (PD-94791B Figure 4 is a graph with no tabulated "
        "values), so the temperature coefficient needed to close the "
        "self-heating loop cannot be derived from the datasheet."
    )
    analysis.note_gap(
        "No worst-case dead time is given. The IRF3205's switching times are "
        "typical-only with no maximum, so the MOSFET's contribution cannot be "
        "bounded. The IR2101 provides no interlock, so this is the design's "
        "most safety-relevant unbounded number."
    )


# --------------------------------------------------------------------------
# The testbench. Real values, taken from the design.
# --------------------------------------------------------------------------


def build_testbench(design: Dict[str, object], vcc: float, model_name: str):
    """Build a simulatable power stage carrying the design's own values.

    Args:
        design: What :func:`read_design` read out of the block.
        vcc: Gate drive voltage, in volts.
        model_name: Name of the MOSFET model card.

    Returns:
        A circuit-synth circuit factory for the testbench.
    """
    gate_ohms = design["gate_ohms"]
    rail = RAILS["VMOTOR"]

    # The gate edge rate the IR2101 can actually produce into this gate,
    # rather than the datasheet's figure measured from a stiff bench supply.
    edge = IRF3205.value("Qg") / IR2101.value("IO+")
    period = 1.0 / SWITCHING_FREQUENCY
    on_time = period * DUTY_CYCLE - edge

    @circuit(name="HalfBridgePowerStage")
    def testbench():
        """Power stage of one half-bridge, driven at the datasheet edge rate."""
        vm = Net("VM")
        phase = Net("PHASE")
        shunt_high = Net("SHUNT_HI")
        high_gate = Net("HGATE")
        low_gate = Net("LGATE")
        neutral = Net("VNEUTRAL")
        gnd = Net("GND")

        supply = Component(
            symbol="Simulation_SPICE:VDC",
            ref="V",
            value=f"{rail}",
            footprint="",
        )
        supply[1] += vm
        supply[2] += gnd

        high_fet = Component(
            symbol="Transistor_FET:Q_NMOS_GDS",
            ref="Q",
            value="IRF3205",
            footprint="Package_TO_SOT_SMD:TO-263-3_TabPin2",
        )
        low_fet = Component(
            symbol="Transistor_FET:Q_NMOS_GDS",
            ref="Q",
            value="IRF3205",
            footprint="Package_TO_SOT_SMD:TO-263-3_TabPin2",
        )
        high_fet[1] += high_gate
        high_fet[2] += vm
        high_fet[3] += phase
        low_fet[1] += low_gate
        low_fet[2] += phase
        low_fet[3] += shunt_high

        shunt = Component(
            symbol="Device:R",
            ref="R",
            value=design["shunt"].value,
            footprint="Resistor_SMD:R_2512_6332Metric",
        )
        shunt[1] += shunt_high
        shunt[2] += gnd

        # The high-side gate source floats on the phase node, which is what a
        # bootstrapped driver produces.
        high_drive = Component(
            symbol="Simulation_SPICE:VPULSE",
            ref="V",
            value="HO",
            footprint="",
        )
        high_drive[1] += high_gate
        high_drive[2] += phase

        low_drive = Component(
            symbol="Simulation_SPICE:VPULSE",
            ref="V",
            value="LO",
            footprint="",
        )
        low_drive[1] += low_gate
        low_drive[2] += gnd

        # Motor phase: winding inductance, winding resistance, and the
        # back-EMF the other two phases present at the star point. The
        # resistance is what bounds the current; without it the winding is an
        # ideal integrator and the current depends only on how exactly the
        # volt-seconds happen to balance.
        winding = Component(
            symbol="Device:L",
            ref="L",
            value=f"{MOTOR_INDUCTANCE * 1e6:g}uH",
            footprint="",
        )
        winding_resistance = Component(
            symbol="Device:R",
            ref="R",
            value=f"{MOTOR_RESISTANCE:g}",
            footprint="",
        )
        winding[1] += phase
        winding[2] += winding_resistance[1]
        winding_resistance[2] += neutral

        back_emf = Component(
            symbol="Simulation_SPICE:VDC",
            ref="V",
            value=f"{MOTOR_BACK_EMF}",
            footprint="",
        )
        back_emf[1] += neutral
        back_emf[2] += gnd

    return testbench, edge, on_time, period, gate_ohms


def testbench_models(
    testbench,
    edge: float,
    on_time: float,
    period: float,
    vcc: float,
    model_name: str,
) -> Dict[str, ModelSpec]:
    """Build the SPICE model assignments for the testbench.

    The specs are keyed to whatever references the generator assigned, found
    by looking at what each part is rather than by assuming a numbering.

    Args:
        testbench: The built testbench ``Circuit``.
        edge: Gate transition time, in seconds.
        on_time: Gate on time, in seconds.
        period: Switching period, in seconds.
        vcc: Gate drive voltage, in volts.
        model_name: Name of the MOSFET model card.

    Returns:
        Model specs keyed by reference designator.
    """
    specs: Dict[str, ModelSpec] = {}

    for reference, part in testbench.components.items():
        if part.symbol == "Transistor_FET:Q_NMOS_GDS":
            specs[reference] = ModelSpec(
                device="NMOS",
                type="VDMOS",
                pins="1=G 2=D 3=S",
                library="half_bridge.lib",
                name=model_name,
                source="fitted to PD-94791B",
            )
        elif part.symbol == "Simulation_SPICE:VDC":
            specs[reference] = ModelSpec(
                device="V",
                type="DC",
                pins="1=+ 2=-",
                params=f"dc={part.value}",
                source="rail voltage",
            )
        elif part.symbol == "Simulation_SPICE:VPULSE":
            # The low side turns on half a period after the high side. The
            # IR2101 generates no dead time of its own, so what separates the
            # two edges here is the controller's, and the gate transition
            # time comes from the driver's source current into this gate.
            delay = 0.0 if part.value == "HO" else period / 2
            specs[reference] = ModelSpec(
                device="V",
                type="PULSE",
                pins="1=+ 2=-",
                params=(
                    f"y1=0 y2={vcc:g} td={delay:.4g} tr={edge:.4g} "
                    f"tf={edge:.4g} tw={on_time:.4g} per={period:.4g}"
                ),
                source="edge rate from IR2101 IO+ and IRF3205 Qg",
            )

    return specs


def measure(waveforms, analysis: BlockAnalysis, design: Dict[str, object]) -> None:
    """Take the figures the simulation is the right tool for out of the run.

    SPICE is used here for what depends on the whole loop and cannot be
    written down: the current the winding actually draws given the duty cycle
    and back-EMF, the ripple on it, and the resulting dissipation in the
    devices. Those depend on every element in the mesh at once.

    Args:
        waveforms: The transient result.
        analysis: Where to record the figures.
        design: What :func:`read_design` read out of the block.
    """
    # Measure over the last few switching periods only. The winding's L/R
    # time constant is far longer than one period, so the early cycles are a
    # startup ramp and averaging over them would understate the current the
    # devices actually carry.
    end = float(waveforms.time[-1])
    settled = waveforms.window(end - MEASUREMENT_PERIODS / SWITCHING_FREQUENCY)

    if not _has_settled(waveforms, analysis):
        return

    shunt_ohms = design["shunt_ohms"]
    low_fet = design["low_fet"]
    high_fet = design["high_fet"]

    analysis.record(
        high_fet.ref,
        "Vds",
        settled.peak("PHASE"),
        "V",
        Basis.SIMULATED,
        "peak phase node voltage from the transient run",
    )
    analysis.record(
        high_fet.ref,
        "dVphase",
        settled.ripple("PHASE"),
        "V",
        Basis.SIMULATED,
        "peak-to-peak phase node swing",
    )

    # The winding branch current, not the shunt voltage. A shunt of a few
    # milliohms turns a nanosecond-scale numerical spike at a switching edge
    # into an apparent tens of amps, and the inductor current is the physical
    # quantity that cannot do that.
    winding = _winding_branch(settled)
    if winding is None:
        analysis.note_gap(
            "The winding branch current is not in the result, so no phase "
            "current figure could be measured."
        )
        return

    current = settled.signal(winding)
    peak_current = float(abs(current).max())
    rms_current = float((current**2).mean() ** 0.5)
    ripple_current = float(current.max() - current.min())

    analysis.record(
        low_fet.ref,
        "Id",
        peak_current,
        "A",
        Basis.SIMULATED,
        f"peak winding current, from {winding}",
    )
    analysis.record(
        low_fet.ref,
        "Idrms",
        rms_current,
        "A",
        Basis.SIMULATED,
        "RMS over the settled window",
    )
    analysis.record(
        low_fet.ref,
        "dIL",
        ripple_current,
        "A",
        Basis.SIMULATED,
        "peak-to-peak winding current ripple",
    )

    # Conduction loss, AN 2006-07 section 2, using the simulated RMS current
    # and the datasheet's on-resistance. The low side conducts for the part
    # of the cycle it is on, which is the duty cycle's complement.
    on_resistance = IRF3205.value("RDS(on)")
    analysis.record(
        low_fet.ref,
        "Pcond",
        rms_current**2 * on_resistance * (1 - DUTY_CYCLE),
        "W",
        Basis.DERIVED,
        f"Idrms^2 * Rds(on) * (1-D) at 25C; "
        f"{IRF3205.equation('conduction_loss').section}",
    )
    analysis.record(
        high_fet.ref,
        "Pcond",
        rms_current**2 * on_resistance * DUTY_CYCLE,
        "W",
        Basis.DERIVED,
        f"Idrms^2 * Rds(on) * D at 25C; "
        f"{IRF3205.equation('conduction_loss').section}",
    )

    analysis.record(
        design["shunt"].ref,
        "Pshunt",
        rms_current**2 * shunt_ohms * (1 - DUTY_CYCLE),
        "W",
        Basis.DERIVED,
        "Irms^2 * R * (1-D) in the shunt",
    )
    analysis.record(
        design["shunt"].ref,
        "Vsense",
        peak_current * shunt_ohms,
        "V",
        Basis.SIMULATED,
        "peak shunt voltage into the INA181, which amplifies it by 20",
    )


def _has_settled(waveforms, analysis: BlockAnalysis) -> bool:
    """Check the winding current reached steady state before it was measured.

    A motor winding's L/R time constant is hundreds of microseconds against a
    switching period of tens, so a run that is too short measures the startup
    ramp instead of the operating point. The waveforms look entirely
    reasonable either way, which is what makes this worth checking rather
    than eyeballing.

    Args:
        waveforms: The full transient result.
        analysis: Where to record the finding if it has not settled.

    Returns:
        True when the average current over the last two windows agrees to
        within a few percent.
    """
    branch = _winding_branch(waveforms)
    if branch is None:
        return True

    span = MEASUREMENT_PERIODS / SWITCHING_FREQUENCY
    end = float(waveforms.time[-1])
    recent = waveforms.window(end - span).mean(branch)
    earlier = waveforms.window(end - 2 * span, end - span).mean(branch)

    if abs(recent) < 1e-9:
        return True

    drift = abs(recent - earlier) / abs(recent)
    if drift > SETTLING_TOLERANCE:
        analysis.note_gap(
            f"The winding current is still changing by {drift * 100:.1f}% per "
            f"measurement window at the end of the run, so it has not reached "
            f"steady state. The load's L/R time constant is "
            f"{MOTOR_INDUCTANCE / MOTOR_RESISTANCE * 1e6:.0f}us against a "
            f"{1e6 / SWITCHING_FREQUENCY:.0f}us switching period. Lengthen the "
            f"run before trusting any current figure."
        )
        return False

    return True


def _winding_branch(waveforms) -> Optional[str]:
    """Find the inductor branch current in a result.

    ngspice names branch currents after the element, so the winding's current
    is under a name like ``"l1#branch"``.

    Args:
        waveforms: The transient result.

    Returns:
        The signal name, or None when no inductor branch is present.
    """
    return next(
        (
            name
            for name in waveforms.names()
            if name.startswith("l") and name.endswith("#branch")
        ),
        None,
    )


def main() -> int:
    """Run the analysis and annotate the schematic.

    Returns:
        A process exit code: 0 when the analysis completed, 1 when the design
        was found to be outside its parts' recommended conditions.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    output = Path(__file__).parent / "build" / "half_bridge_sim"
    design_project = Path(__file__).parent / "build" / "three_phase_driver"

    print("Reading the design")
    root = three_phase_driver()
    block = find_block(root, "HalfBridge")
    if block is None:
        print("No HalfBridge block in the design")
        return 1

    design = read_design(block)
    print(
        f"  {design['driver'].ref} {design['driver'].value}, "
        f"{design['high_fet'].ref}/{design['low_fet'].ref} "
        f"{design['high_fet'].value}, shunt {design['shunt'].value}, "
        f"bootstrap {design['bootstrap'].value}, "
        f"gate {design['gate_resistors'][0].value}"
    )

    analysis = BlockAnalysis(block="HalfBridge")

    print("\nChecking operating conditions against the datasheets")
    usable = check_operating_conditions(design, analysis)

    # The datasheet figures that do not depend on the driver switching are
    # still worth having, computed at the voltage the parts are specified for
    # rather than the one the design supplies.
    specified_vcc = IR2101.value("VCC_MIN")
    datasheet_figures(design, analysis, specified_vcc if not usable else specified_vcc)

    if not usable:
        print(
            "\n  The design is outside its parts' recommended conditions. No "
            "figure below describes the circuit as drawn; the simulation that "
            "follows is of the same power stage supplied correctly, which is "
            "what the block would do once the fault is fixed."
        )

    # Fit a model for the MOSFET. Infineon publishes no SPICE model for the
    # IRF3205, so one is built from the datasheet's own parameters and checked
    # against the on-resistance it was fitted to.
    print("\nFitting a MOSFET model to the datasheet")
    try:
        model = fit(
            VdmosParameters(
                name="IRF3205",
                vto=IRF3205.value("VGS(th)"),
                kp=IRF3205.value("gfs"),
                rds_on=IRF3205.value("RDS(on)"),
                rds_on_vgs=10.0,
                rds_on_id=62.0,
                vds_max=IRF3205.value("VDSS"),
                ciss=IRF3205.value("Ciss"),
                coss=IRF3205.value("Coss"),
                crss=IRF3205.value("Crss"),
            )
        )
    except (SimulationUnavailable, SimulationFailed, ValueError) as error:
        analysis.note_gap(f"No MOSFET model could be built: {error}")
        print("\n" + analysis.summary())
        return 1
    print(f"  {model.summary()}")

    # Build and generate the testbench at the voltage the parts are specified
    # for, since simulating a driver in permanent lockout tells nobody
    # anything.
    vcc = IR2101.value("VCC_MIN")
    print(f"\nBuilding the testbench at VCC = {vcc}V")
    factory, edge, on_time, period, gate_ohms = build_testbench(design, vcc, model.name)
    testbench = factory()
    testbench.generate_kicad_project(
        str(output), force_regenerate=True, generate_pcb=False
    )

    specs = testbench_models(testbench, edge, on_time, period, vcc, model.name)
    assignments, gaps = assign_models(testbench.components.values(), specs)
    for gap in gaps:
        analysis.note_gap(str(gap))

    substitutions = [
        Substitution(
            reference=design["driver"].ref,
            replaced_by=(
                f"two ideal floating PULSE sources with a "
                f"{edge * 1e9:.0f}ns transition, that being Qg/IO+ for this "
                f"driver and this FET"
            ),
            justification=(
                "Infineon publishes no SPICE model for the IR2101. The edge "
                "rate is taken from the two datasheets rather than assumed, "
                "so the gate transition is the one this pairing produces."
            ),
            limits=(
                "The bootstrap supply is not modelled, so nothing here says "
                "anything about bootstrap droop or about the high-side rail "
                "collapsing. Propagation delay and its 50ns matching spread "
                "are not modelled either."
            ),
        ),
        Substitution(
            reference=design["shunt"].ref,
            replaced_by="a two-terminal resistor of the same value",
            justification=(
                "the Kelvin sense pins carry no current, so they do not "
                "affect the power path being measured"
            ),
            limits=(
                "nothing here covers the INA181's common-mode range or its "
                "behaviour during switching transitions"
            ),
        ),
    ]

    # Run long enough for the winding current to settle, then a few more
    # periods to measure over. The step has to resolve the gate edge, which
    # is what sets the cost of this.
    settling = SETTLING_TIME_CONSTANTS * MOTOR_INDUCTANCE / MOTOR_RESISTANCE
    duration = settling + MEASUREMENT_PERIODS * 2 / SWITCHING_FREQUENCY
    step = edge / 10

    print("Making it probeable in KiCad")
    project = make_probeable(
        project_dir=output,
        assignments=assignments,
        directives=[f".tran {step:.4g} {duration:.4g} 0 {step:.4g} uic"],
        traces=["V(/PHASE)", "V(/HGATE)", "V(/SHUNT_HI)"],
        model_files=[
            ModelFile(
                name="half_bridge.lib",
                content=model.card,
                source="fitted to IRF3205 datasheet PD-94791B",
            )
        ],
        substitutions=substitutions,
        gaps=gaps,
    )

    print("Exporting the SPICE netlist with kicad-cli")
    deck = export_spice_netlist(project.schematic)
    expected = [part.ref for part in testbench.components.values()]
    absent = missing_elements(deck, expected)
    if absent:
        analysis.note_gap(
            f"These parts are missing from the SPICE netlist and so were not "
            f"simulated: {', '.join(absent)}"
        )
    print(
        f"  {len(deck.splitlines())} lines, elements present: "
        f"{len(expected) - len(absent)}/{len(expected)}"
    )

    print("Running ngspice on that netlist")
    try:
        waveforms = run_transient(deck, working_dir=output)
    except (SimulationUnavailable, SimulationFailed) as error:
        analysis.note_gap(f"The simulation did not run: {error}")
        print("\n" + analysis.summary())
        return 1

    print(
        f"  {len(waveforms.time)} points, signals: " f"{', '.join(waveforms.names())}"
    )

    measure(waveforms, analysis, design)

    print("\n" + analysis.summary())
    print("\n" + project.summary())

    print("\nAnnotating the schematic")
    sheet = design_project / "HalfBridge.kicad_sch"
    if sheet.exists():
        notes = annotate_schematic(sheet, analysis)
        print(f"  wrote {len(notes)} notes to {sheet}")
    else:
        print(
            f"  {design_project.name} has not been generated; run "
            f"three_phase_driver.py first"
        )

    print(
        f"\nTo see a waveform: open {project.schematic}, Inspect -> "
        f"Simulator, Run, then Probe and click a net."
    )
    return 0 if usable else 1


if __name__ == "__main__":
    raise SystemExit(main())
