"""Tests for component research"""

import pytest
from anyaria.core.component_research import ComponentResearcher, ComponentCandidate


def test_research_components():
    """Test component research"""
    researcher = ComponentResearcher()

    class MockBlock:
        pass

    blocks = [MockBlock()]

    components = researcher.research_components(blocks, prefer_jlc=True, budget=10.0)

    assert len(components) > 0
    assert all(isinstance(c, ComponentCandidate) for c in components)


def test_search_jlc_pcb():
    """Test JLC PCB search"""
    researcher = ComponentResearcher()

    results = researcher.search_jlc_pcb("buck converter")

    assert isinstance(results, list)


def test_read_datasheet():
    """Test datasheet reading"""
    researcher = ComponentResearcher()

    result = researcher.read_datasheet("https://example.com/datasheet.pdf")

    assert "equations" in result
    assert "typical_circuit" in result
    assert "design_guidelines" in result
