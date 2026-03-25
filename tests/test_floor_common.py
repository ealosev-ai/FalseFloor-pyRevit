"""Unit tests for floor_common module."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

pytestmark = [pytest.mark.integration, pytest.mark.revit]

pytest.importorskip("Autodesk.Revit.DB", reason="Revit API not available")

# Mock revit module before importing floor_common
from unittest.mock import MagicMock  # noqa: E402

sys.modules["pyrevit"] = MagicMock()
sys.modules["pyrevit.revit"] = MagicMock()

from floor_common import (  # noqa: E402
    build_positions,
    build_support_nodes,
    cut_at_positions_1d,
    cut_equal_1d,
    parse_ids_from_string,
    split_orthogonal_segments,
)


class TestBuildPositions:
    """Tests for build_positions function."""

    def test_basic_positions(self):
        """Test basic position generation."""
        positions = build_positions(
            min_val=0,
            max_val=100,
            base_val=0,
            step_val=10,
        )
        assert len(positions) > 0
        assert positions[0] <= 0
        assert positions[-1] >= 100

    def test_zero_step(self):
        """Test handling of zero step value."""
        with pytest.raises(ValueError):
            build_positions(
                min_val=0,
                max_val=100,
                base_val=0,
                step_val=0,
            )

    def test_negative_step(self):
        """Test handling of negative step value."""
        with pytest.raises(ValueError):
            build_positions(
                min_val=0,
                max_val=100,
                base_val=0,
                step_val=-10,
            )

    def test_with_padding(self):
        """Test position generation with padding."""
        positions = build_positions(
            min_val=0,
            max_val=100,
            base_val=0,
            step_val=25,
            end_padding_steps=1.0,
        )
        assert len(positions) > 4  # Should have extra positions from padding

    def test_with_tolerance(self):
        """Test position generation with tolerance."""
        positions = build_positions(
            min_val=0,
            max_val=100,
            base_val=0,
            step_val=30,
            end_tolerance=5.0,
        )
        assert positions[-1] >= 100


class TestParseIdsFromString:
    """Tests for parse_ids_from_string function."""

    def test_valid_ids(self):
        """Test parsing valid ID string."""
        result = parse_ids_from_string("1;2;3;4;5")
        assert result == [1, 2, 3, 4, 5]

    def test_empty_string(self):
        """Test parsing empty string."""
        result = parse_ids_from_string("")
        assert result == []

    def test_none_string(self):
        """Test parsing None string."""
        result = parse_ids_from_string(None)
        assert result == []

    def test_whitespace(self):
        """Test parsing string with whitespace."""
        result = parse_ids_from_string(" 1 ; 2 ; 3 ")
        assert result == [1, 2, 3]

    def test_invalid_ids(self):
        """Test parsing string with invalid IDs."""
        result = parse_ids_from_string("1;abc;3;def;5")
        assert result == [1, 3, 5]

    def test_semicolon_only(self):
        """Test parsing string with only semicolons."""
        result = parse_ids_from_string(";;;")
        assert result == []


class TestCutEqual1d:
    """Tests for cut_equal_1d function."""

    def test_no_cut_needed(self):
        """Test when segment fits within max length."""
        segments = cut_equal_1d(0, 5, 10)
        assert segments == [(0, 5)]

    def test_equal_cut(self):
        """Test cutting into equal segments."""
        segments = cut_equal_1d(0, 10, 5)
        assert len(segments) == 2
        assert segments[0] == (0, 5)
        assert segments[1] == (5, 10)

    def test_unequal_cut(self):
        """Test cutting when not evenly divisible."""
        segments = cut_equal_1d(0, 12, 5)
        assert len(segments) == 3
        total_length = sum(end - start for start, end in segments)
        assert abs(total_length - 12) < 1e-6


class TestCutAtPositions1d:
    """Tests for cut_at_positions_1d function."""

    def test_no_cut_needed(self):
        """Test when segment fits within max length."""
        segments = cut_at_positions_1d(0, 5, 10, [2, 4, 6])
        assert segments == [(0, 5)]

    def test_cut_at_positions(self):
        """Test cutting at specified positions."""
        segments = cut_at_positions_1d(0, 10, 5, [3, 5, 7])
        assert len(segments) >= 2

    def test_no_positions_fallback(self):
        """Test fallback to equal cut when positions don't help."""
        segments = cut_at_positions_1d(0, 20, 5, [100])  # Position outside segment
        assert len(segments) == 4  # Should fall back to equal cuts


class TestSplitOrthogonalSegments:
    """Tests for split_orthogonal_segments function."""

    def test_horizontal_segments(self):
        """Test splitting horizontal segments."""
        segments = [(0, 0, 10, 0)]  # Horizontal line from (0,0) to (10,0)
        result = split_orthogonal_segments(segments, max_len=5)
        assert len(result) == 2

    def test_vertical_segments(self):
        """Test splitting vertical segments."""
        segments = [(0, 0, 0, 10)]  # Vertical line from (0,0) to (0,10)
        result = split_orthogonal_segments(segments, max_len=5)
        assert len(result) == 2

    def test_diagonal_segments(self):
        """Test that diagonal segments are not split."""
        segments = [(0, 0, 5, 5)]  # Diagonal line
        result = split_orthogonal_segments(segments, max_len=1)
        assert result == [(0, 0, 5, 5)]  # Should remain unchanged

    def test_with_positions(self):
        """Test splitting with position hints."""
        segments = [(0, 0, 20, 0)]  # Long horizontal line
        positions = [5, 10, 15]
        result = split_orthogonal_segments(segments, max_len=10, positions=positions)
        assert len(result) >= 2


class TestBuildSupportNodes:
    """Tests for build_support_nodes function."""

    def test_single_segment(self):
        """Test support nodes for single segment."""
        segments = [(0, 0, 10, 0)]
        nodes = build_support_nodes(segments, max_spacing=20)
        assert len(nodes) >= 2  # At least endpoints

    def test_multiple_segments(self):
        """Test support nodes for multiple segments."""
        segments = [(0, 0, 10, 0), (10, 0, 20, 0)]
        nodes = build_support_nodes(segments, max_spacing=20)
        # Should have nodes at endpoints and potentially intermediate points
        assert len(nodes) >= 2

    def test_with_intermediate_supports(self):
        """Test that intermediate supports are added for long segments."""
        segments = [(0, 0, 30, 0)]
        nodes = build_support_nodes(segments, max_spacing=10)
        # Should have intermediate supports
        assert len(nodes) >= 4

    def test_deduplication(self):
        """Test that duplicate nodes are removed."""
        segments = [(0, 0, 10, 0), (10, 0, 20, 0)]
        nodes = build_support_nodes(segments, max_spacing=20)
        # Shared endpoint should only appear once
        unique_nodes = set(nodes)
        assert len(unique_nodes) == len(nodes)
