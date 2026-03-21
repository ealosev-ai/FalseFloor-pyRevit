"""Unit tests for floor_utils module.

NOTE: These tests use mocks for Revit API dependencies.
Run with: pytest tests/test_floor_utils.py -v
"""

import os
import sys
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

pytestmark = [pytest.mark.integration, pytest.mark.revit]

pytest.importorskip("Autodesk.Revit.DB", reason="Revit API not available")


class TestGetStorageTypeId:
    """Tests for get_storage_type_id function."""

    def test_double_storage_type(self):
        """Test conversion of Double storage type."""
        with patch("floor_utils.SpecTypeId") as mock_spec:
            with patch("floor_utils.ParameterType", None):
                mock_spec.Length = "Length"
                from floor_utils import StorageType, get_storage_type_id

                result = get_storage_type_id(StorageType.Double)
                assert result is not None

    def test_invalid_storage_type(self):
        """Test handling of invalid storage type."""
        with patch("floor_utils.SpecTypeId", None):
            with patch("floor_utils.ParameterType", None):
                from floor_utils import get_storage_type_id

                result = get_storage_type_id("InvalidType")
                assert result is None


class TestSafeGetName:
    """Tests for safe_get_name function."""

    def test_valid_object_with_name(self):
        """Test getting name from valid object."""
        from floor_utils import safe_get_name

        mock_obj = MagicMock()
        mock_obj.Name = "TestName"
        result = safe_get_name(mock_obj)
        assert result == "TestName"

    def test_none_object(self):
        """Test handling of None object."""
        from floor_utils import safe_get_name

        result = safe_get_name(None)
        assert result is None

    def test_object_without_name(self):
        """Test handling of object without Name property."""
        from floor_utils import safe_get_name

        mock_obj = MagicMock()
        type(mock_obj).Name = PropertyMock(side_effect=AttributeError)
        result = safe_get_name(mock_obj)
        assert result is None


class TestNormalizePath:
    """Tests for normalize_path function."""

    def test_relative_path(self):
        """Test normalization of relative path."""
        from floor_utils import normalize_path

        result = normalize_path("test/path")
        assert os.path.isabs(result)

    def test_absolute_path(self):
        """Test normalization of absolute path."""
        from floor_utils import normalize_path

        test_path = os.path.abspath("test/path")
        result = normalize_path(test_path)
        assert result == os.path.normpath(test_path)


class TestParseVersionString:
    """Tests for parse_version_string function."""

    def test_standard_version(self):
        """Test parsing standard version string."""
        from floor_utils import parse_version_string

        result = parse_version_string("1.2.3")
        assert result == (1, 2, 3)

    def test_version_with_v_prefix(self):
        """Test parsing version with 'v' prefix."""
        from floor_utils import parse_version_string

        result = parse_version_string("v1.2.0")
        assert result == (1, 2, 0)

    def test_version_with_v_uppercase_prefix(self):
        """Test parsing version with 'V' prefix."""
        from floor_utils import parse_version_string

        result = parse_version_string("V2.0.1")
        assert result == (2, 0, 1)

    def test_two_part_version(self):
        """Test parsing two-part version."""
        from floor_utils import parse_version_string

        result = parse_version_string("1.2")
        assert result == (1, 2)

    def test_empty_version(self):
        """Test parsing empty version string."""
        from floor_utils import parse_version_string

        result = parse_version_string("")
        assert result == ()

    def test_invalid_version(self):
        """Test parsing invalid version string."""
        from floor_utils import parse_version_string

        result = parse_version_string("invalid")
        assert result == ()


class TestFormatErrorMessage:
    """Tests for format_error_message function."""

    def test_simple_error(self):
        """Test formatting simple error message."""
        from floor_utils import format_error_message

        error = Exception("Test error")
        result = format_error_message(error)
        assert "Test error" in result

    def test_error_with_traceback(self):
        """Test formatting error with traceback."""
        from floor_utils import format_error_message

        error = Exception("Test error")
        result = format_error_message(error, include_traceback=True)
        assert "Test error" in result
        assert "Traceback" in result or "traceback" in result.lower()

    def test_no_traceback_by_default(self):
        """Test that traceback is not included by default."""
        from floor_utils import format_error_message

        error = Exception("Test error")
        result = format_error_message(error)
        assert "Traceback" not in result


class TestCreateCategorySet:
    """Tests for create_category_set function."""

    def test_empty_categories(self):
        """Test creating category set with empty list."""
        from floor_utils import create_category_set

        mock_doc = MagicMock()
        result = create_category_set(mock_doc, [])
        assert result is not None


class TestGetExistingParameterBindings:
    """Tests for get_existing_parameter_bindings function."""

    def test_returns_dict(self):
        """Test that function returns a dictionary."""
        from floor_utils import get_existing_parameter_bindings

        mock_doc = MagicMock()
        mock_bindings = MagicMock()
        mock_iterator = MagicMock()

        mock_doc.ParameterBindings = mock_bindings
        mock_bindings.ForwardIterator.return_value = mock_iterator
        mock_iterator.MoveNext.return_value = False

        result = get_existing_parameter_bindings(mock_doc)
        assert isinstance(result, dict)
