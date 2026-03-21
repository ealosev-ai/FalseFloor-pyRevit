"""Conftest - shared pytest fixtures for RaisedFloor tests."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add lib directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))


def _has_revit_api():
    try:
        __import__("Autodesk.Revit.DB")
        return True
    except Exception:
        return False


HAS_REVIT_API = _has_revit_api()


def pytest_collection_modifyitems(config, items):
    """Skip Revit-marked tests when Autodesk API runtime is unavailable."""
    run_revit = (os.environ.get("RUN_REVIT_TESTS") or "").strip() == "1"
    if HAS_REVIT_API and run_revit:
        return

    skip_reason = (
        "Revit API tests are skipped. "
        "Set RUN_REVIT_TESTS=1 and run inside Revit-compatible runtime."
    )
    skip_marker = pytest.mark.skip(reason=skip_reason)
    for item in items:
        if "revit" in item.keywords:
            item.add_marker(skip_marker)


@pytest.fixture(scope="session")
def mock_revit():
    """Create mock Revit API objects."""
    mock = MagicMock()

    # Mock Revit DB classes
    mock.DB = MagicMock()
    mock.DB.StorageType = MagicMock()
    mock.DB.StorageType.Double = "Double"
    mock.DB.StorageType.Integer = "Integer"
    mock.DB.StorageType.String = "String"

    return mock


@pytest.fixture
def mock_doc():
    """Create mock Revit document."""
    doc = MagicMock()
    doc.ParameterBindings = MagicMock()
    doc.Settings = MagicMock()
    doc.Settings.Categories = MagicMock()
    return doc


@pytest.fixture
def mock_app():
    """Create mock Revit application."""
    app = MagicMock()
    app.SharedParametersFilename = "/tmp/shared_params.txt"
    return app


@pytest.fixture(autouse=True)
def setup_pyrevit_mock():
    """Automatically mock pyrevit module for all tests."""
    with patch.dict(
        "sys.modules",
        {
            "pyrevit": MagicMock(),
            "pyrevit.revit": MagicMock(),
            "pyrevit.forms": MagicMock(),
        },
    ):
        yield


@pytest.fixture
def sample_floor_data():
    """Sample floor data for testing."""
    return {
        "step_x": 600.0,
        "step_y": 600.0,
        "base_x": 0.0,
        "base_y": 0.0,
        "offset_x": 0.0,
        "offset_y": 0.0,
        "floor_height": 500.0,
        "bbox": (0, 0, 5000, 5000, 0, 300),  # min_x, min_y, max_x, max_y, min_z, max_z
    }


@pytest.fixture
def sample_tile_data():
    """Sample tile data for testing."""
    return {
        "size_x": 600.0,
        "size_y": 600.0,
        "thickness": 40.0,
        "min_viable_cut": 100.0,
    }


@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary file and return its path."""
    file_path = tmp_path / "test_file.txt"
    file_path.write_text("test content")
    return str(file_path)


@pytest.fixture
def mock_clipper():
    """Mock Clipper2 library for testing without actual DLL."""
    mock = MagicMock()

    # Mock Clipper2 classes
    mock.Point64 = MagicMock()
    mock.Path64 = MagicMock()
    mock.Paths64 = MagicMock()
    mock.Clipper64 = MagicMock()
    mock.ClipType = MagicMock()
    mock.FillRule = MagicMock()

    return mock
