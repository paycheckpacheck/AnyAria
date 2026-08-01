"""Tests for circuit generator"""

import pytest
from anyaria.core.circuit_generator import CircuitGenerator, Block


def test_parse_requirements():
    """Test requirements parsing"""
    generator = CircuitGenerator()

    requirements = "Design a 3.3V buck converter from 12V input"
    parsed = generator.parse_requirements(requirements, budget=10.0)

    assert "input_voltage" in parsed
    assert "output_voltage" in parsed
    assert parsed["budget"] == 10.0


def test_create_block_diagram():
    """Test block diagram generation"""
    generator = CircuitGenerator()

    requirements = {
        "input_voltage": 12.0,
        "output_voltage": 3.3,
        "output_current": 2.0,
        "budget": 10.0
    }

    blocks = generator.create_block_diagram(requirements)

    assert len(blocks) > 0
    assert all(isinstance(b, Block) for b in blocks)


def test_format_block_diagram():
    """Test block diagram formatting"""
    generator = CircuitGenerator()

    blocks = [
        Block("Input", "power", {}, {}, 1.0),
        Block("Converter", "power", {}, {}, 5.0),
        Block("Output", "power", {}, {}, 1.0),
    ]

    formatted = generator.format_block_diagram(blocks)

    assert "Input" in formatted
    assert "Converter" in formatted
    assert "Output" in formatted
    assert "→" in formatted


def test_verify_design():
    """Test design verification"""
    generator = CircuitGenerator()

    class MockCircuit:
        pass

    circuit = MockCircuit()
    requirements = {"input_voltage": 12.0}

    result = generator.verify_design(circuit, requirements, ambient_temp=25.0)

    assert "meets_requirements" in result
    assert "derating_ok" in result
    assert "thermal_ok" in result
