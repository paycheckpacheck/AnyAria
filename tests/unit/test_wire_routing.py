"""Wires go around parts, not over them.

A wire drawn through a symbol body reads as a connection to that symbol, and
hides whatever it crosses. The connectivity is unchanged, so nothing in the
netlist comparison notices - which is exactly why it needs its own check.
"""

from circuit_synth.kicad.layout.routing import (
    Box,
    path_is_clear,
    route_around,
    segment_crosses,
    segments_of,
)

# A part sitting between two points that want joining.
BODY = Box(20.0, 20.0, 40.0, 40.0)


def test_a_segment_through_a_body_is_a_crossing():
    """A wire straight through the middle of a part is reported."""
    assert segment_crosses((10.0, 30.0), (50.0, 30.0), BODY)


def test_a_segment_beside_a_body_is_not():
    """A wire clear of the part is left alone."""
    assert not segment_crosses((10.0, 10.0), (50.0, 10.0), BODY)


def test_a_segment_along_an_edge_is_not_a_crossing():
    """Running flush against an outline is tight, not a crossing."""
    assert not segment_crosses((10.0, 20.0), (50.0, 20.0), BODY)


def test_a_segment_ending_on_an_edge_is_not_a_crossing():
    """A wire that stops at a pin on the outline has not entered the body."""
    assert not segment_crosses((10.0, 30.0), (20.0, 30.0), BODY)


def test_route_goes_around_a_blocking_part():
    """The route between two points either side of a part avoids it."""
    path = route_around((10.0, 30.0), (50.0, 30.0), [BODY])

    assert path[0] == (10.0, 30.0)
    assert path[-1] == (50.0, 30.0)
    assert path_is_clear(path, [BODY.inflated(1.27)])


def test_route_is_straight_when_nothing_is_in_the_way():
    """An unobstructed run stays a single segment; a detour would be noise."""
    assert route_around((10.0, 10.0), (50.0, 10.0), [BODY]) == [
        (10.0, 10.0),
        (50.0, 10.0),
    ]


def test_route_prefers_one_corner_over_a_detour():
    """With the part out of the way, the plain L route wins."""
    path = route_around((10.0, 10.0), (50.0, 5.0), [BODY])

    assert len(path) == 3


def test_route_stays_on_the_grid():
    """Every corner lands on KiCad's 1.27mm grid, as wire ends must."""
    path = route_around((10.16, 30.48), (50.8, 30.48), [BODY])

    for x, y in path[1:-1]:
        assert abs(x / 1.27 - round(x / 1.27)) < 1e-6
        assert abs(y / 1.27 - round(y / 1.27)) < 1e-6


def test_route_ignores_a_body_its_own_end_sits_in():
    """A pin inside an inflated outline must not make the route impossible."""
    inside = Box(9.0, 29.0, 40.0, 40.0)  # swallows the start point
    path = route_around((10.0, 30.0), (50.0, 30.0), [inside])

    assert path == [(10.0, 30.0), (50.0, 30.0)]


def test_segments_of_drops_zero_length_steps():
    """A corner that repeats a point does not become a wire of no length."""
    assert segments_of([(0.0, 0.0), (0.0, 0.0), (10.0, 0.0)]) == [
        ((0.0, 0.0), (10.0, 0.0))
    ]
