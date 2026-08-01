"""Tests for simulation builder"""

import pytest
from anyaria.simulation.builder import SimulationBuilder


def test_generate_simulation():
    """Test simulation code generation"""
    builder = SimulationBuilder()

    class MockCircuit:
        pass

    circuit = MockCircuit()
    blocks = []

    code = builder.generate_simulation(circuit, blocks)

    assert isinstance(code, str)
    assert len(code) > 0
    assert "class" in code  # Should contain Python class
    assert "def" in code    # Should contain functions


def test_execute_simulation():
    """Test simulation execution"""
    builder = SimulationBuilder()

    code = "result = {'test': 123}"
    inputs = {}

    result = builder.execute_simulation(code, inputs)

    assert isinstance(result, dict)
