"""Unit tests for stringer stagger/drop logic (pure functions in floor_common).

Run with: pytest tests/test_stringer_logic.py -v
"""

import os
from typing import Any

import pytest

pytestmark = [pytest.mark.unit]


def _load_pure_functions():
    """Load compute_stagger_positions and drop_near_parallel without importing
    the full floor_common module (avoids polluting sys.modules with Revit stubs).

    We compile and exec only the function source, injecting just `math`.
    """
    import ast
    import math

    src_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "lib", "floor_common.py")
    )
    with open(src_path, encoding="utf-8-sig") as f:
        full_source = f.read()

    tree = ast.parse(full_source)

    # Extract only the two function defs we need
    target_names = {"compute_stagger_positions", "drop_near_parallel"}
    func_sources = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and node.name in target_names:
            func_sources.append(ast.get_source_segment(full_source, node))

    assert len(func_sources) == 2, "Could not find both functions in floor_common.py"

    ns = {"math": math}
    for src in func_sources:
        exec(compile(src, src_path, "exec"), ns)  # noqa: S102

    return ns["compute_stagger_positions"], ns["drop_near_parallel"]


compute_stagger_positions: Any
drop_near_parallel: Any
compute_stagger_positions, drop_near_parallel = _load_pure_functions()


# ── compute_stagger_positions ─────────────────────────────


class TestComputeStaggerPositions:
    """Tests for stagger even/odd splitting and midpoint computation."""

    def test_basic_4_main_5_lower(self):
        """Standard case: 4 upper keys, 5 lower positions."""
        mk = [0.0, 600.0, 1200.0, 1800.0]
        lp = [0.0, 500.0, 1000.0, 1500.0, 2000.0]
        r = compute_stagger_positions(mk, lp)

        assert r["lp_even"] == [0.0, 1000.0, 2000.0]
        assert r["lp_odd"] == [500.0, 1500.0]

        # mk_mids = midpoints between consecutive main_keys
        assert r["mk_mids_even"] == pytest.approx([300.0, 1500.0])
        assert r["mk_mids_odd"] == pytest.approx([900.0])

    def test_stagger_odd_sets(self):
        """Stagger sets contain every other position (1-indexed)."""
        mk = [0.0, 600.0, 1200.0, 1800.0]
        lp = [0.0, 500.0, 1000.0, 1500.0, 2000.0]
        r = compute_stagger_positions(mk, lp)

        # odd upper = mk[1], mk[3] = 600, 1800
        assert r["stagger_odd_upper"] == {round(600.0, 6), round(1800.0, 6)}
        # odd lower = lp[1], lp[3] = 500, 1500
        assert r["stagger_odd_lower"] == {round(500.0, 6), round(1500.0, 6)}

    def test_single_lower_position(self):
        """With 1 lower position, both even and odd are the same."""
        mk = [0.0, 600.0]
        lp = [300.0]
        r = compute_stagger_positions(mk, lp)

        assert r["lp_even"] == [300.0]
        assert r["lp_odd"] == [300.0]
        assert r["stagger_odd_lower"] == set()

    def test_two_lower_positions(self):
        """With 2 lower positions, even=[p0], odd=[p1]."""
        mk = [0.0, 600.0, 1200.0]
        lp = [200.0, 800.0]
        r = compute_stagger_positions(mk, lp)

        assert r["lp_even"] == [200.0]
        assert r["lp_odd"] == [800.0]

    def test_single_main_key(self):
        """With 1 main_key, mk_mids is empty."""
        mk = [500.0]
        lp = [0.0, 600.0, 1200.0]
        r = compute_stagger_positions(mk, lp)

        assert r["mk_mids_even"] == []
        assert r["mk_mids_odd"] == []

    def test_two_main_keys(self):
        """With 2 main_keys, mk_mids has 1 midpoint → both even and odd are same."""
        mk = [0.0, 600.0]
        lp = [100.0, 400.0, 700.0]
        r = compute_stagger_positions(mk, lp)

        assert r["mk_mids_even"] == pytest.approx([300.0])
        assert r["mk_mids_odd"] == pytest.approx([300.0])

    def test_unsorted_input(self):
        """Inputs are sorted internally."""
        mk = [1200.0, 0.0, 600.0]
        lp = [1000.0, 0.0, 500.0]
        r = compute_stagger_positions(mk, lp)

        assert r["lp_even"] == [0.0, 1000.0]
        assert r["lp_odd"] == [500.0]
        # mk_mids = [300, 900] → even=[300], odd=[900]
        assert r["mk_mids_even"] == pytest.approx([300.0])
        assert r["mk_mids_odd"] == pytest.approx([900.0])

    def test_empty_lower(self):
        """Empty lower_positions → degenerate but no crash."""
        mk = [0.0, 600.0]
        lp = []
        r = compute_stagger_positions(mk, lp)
        assert r["lp_even"] == []
        assert r["lp_odd"] == []
        assert r["stagger_odd_lower"] == set()

    def test_alternation_pattern(self):
        """Verify the actual alternation: even rows use lp_even, odd rows use lp_odd."""
        mk = [0.0, 600.0, 1200.0, 1800.0, 2400.0]
        lp = [0.0, 300.0, 600.0, 900.0, 1200.0]
        r = compute_stagger_positions(mk, lp)

        # mk[0]=0 is even (index 0), mk[1]=600 is odd (index 1), etc.
        for pos in [0.0, 1200.0, 2400.0]:
            assert round(pos, 6) not in r["stagger_odd_upper"]
        for pos in [600.0, 1800.0]:
            assert round(pos, 6) in r["stagger_odd_upper"]


# ── drop_near_parallel ────────────────────────────────────


class TestDropNearParallel:
    """Tests for filtering contour segments near parallel grid segments."""

    def test_empty_contour(self):
        """Empty contour → nothing dropped."""
        kept, dropped = drop_near_parallel([], [(0, 0, 0, 10)], tol=1.0)
        assert kept == []
        assert dropped == 0

    def test_empty_grid(self):
        """Empty grid → nothing is dominated."""
        segs = [(0, 5, 10, 5)]
        kept, dropped = drop_near_parallel(segs, [], tol=1.0)
        assert kept == segs
        assert dropped == 0

    def test_horizontal_dominated(self):
        """Horizontal contour near parallel horizontal grid → dropped."""
        contour = [(0, 5.0, 10, 5.0)]  # y=5
        grid = [(0, 5.5, 10, 5.5)]  # y=5.5, distance=0.5 < tol=1.0
        kept, dropped = drop_near_parallel(contour, grid, tol=1.0)
        assert dropped == 1
        assert kept == []

    def test_horizontal_not_dominated_too_far(self):
        """Horizontal contour too far from grid → kept."""
        contour = [(0, 5.0, 10, 5.0)]
        grid = [(0, 8.0, 10, 8.0)]  # distance=3.0 > tol=1.0
        kept, dropped = drop_near_parallel(contour, grid, tol=1.0)
        assert dropped == 0
        assert kept == contour

    def test_vertical_dominated(self):
        """Vertical contour near parallel vertical grid → dropped."""
        contour = [(3.0, 0, 3.0, 10)]  # x=3
        grid = [(3.4, 0, 3.4, 10)]  # x=3.4, distance=0.4 < tol=1.0
        kept, dropped = drop_near_parallel(contour, grid, tol=1.0)
        assert dropped == 1
        assert kept == []

    def test_no_overlap_in_span(self):
        """Near parallel but spans don't overlap → kept."""
        contour = [(0, 5.0, 10, 5.0)]  # x: 0..10
        grid = [(20, 5.5, 30, 5.5)]  # x: 20..30, no overlap
        kept, dropped = drop_near_parallel(contour, grid, tol=1.0)
        assert dropped == 0
        assert kept == contour

    def test_partial_overlap(self):
        """Partially overlapping spans → dropped."""
        contour = [(0, 5.0, 10, 5.0)]  # x: 0..10
        grid = [(8, 5.3, 20, 5.3)]  # x: 8..20, overlaps 8..10
        kept, dropped = drop_near_parallel(contour, grid, tol=1.0)
        assert dropped == 1
        assert kept == []

    def test_mixed_kept_and_dropped(self):
        """Multiple contour segments: some near grid, some not."""
        contour = [
            (0, 5.0, 10, 5.0),  # near grid line at y=5.3
            (0, 20.0, 10, 20.0),  # far from grid
        ]
        grid = [(0, 5.3, 10, 5.3)]
        kept, dropped = drop_near_parallel(contour, grid, tol=1.0)
        assert dropped == 1
        assert len(kept) == 1
        assert kept[0][1] == 20.0  # the far one survives

    def test_diagonal_segments_ignored(self):
        """Diagonal segments are neither H nor V → always kept."""
        contour = [(0, 0, 10, 10)]  # 45-degree diagonal
        grid = [(0, 0.1, 10, 0.1)]  # horizontal grid nearby
        kept, dropped = drop_near_parallel(contour, grid, tol=1.0)
        assert dropped == 0
        assert kept == contour

    def test_perpendicular_not_dropped(self):
        """Perpendicular contour (V) near horizontal grid (H) → never dropped."""
        contour = [(5.0, 0, 5.0, 10)]  # vertical
        grid = [(0, 5.0, 10, 5.0)]  # horizontal
        kept, dropped = drop_near_parallel(contour, grid, tol=1.0)
        assert dropped == 0
        assert kept == contour
