"""Unit tests for floor_i18n module (localization)."""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

pytestmark = [pytest.mark.unit]


class TestLanguageDetection:
    """Tests for language detection functionality."""

    def test_detect_lang_default(self):
        """Test that default language is detected."""
        # Import fresh to test detection
        if "floor_i18n" in sys.modules:
            del sys.modules["floor_i18n"]

        with patch.dict(os.environ, {}, clear=False):
            import floor_i18n

            # Should default to 'ru' if no env var and can't detect system
            assert floor_i18n.LANG in ("ru", "en")

    def test_detect_lang_env_override(self):
        """Test language override via environment variable."""
        if "floor_i18n" in sys.modules:
            del sys.modules["floor_i18n"]

        with patch.dict(os.environ, {"RAISEDFLOOR_LANG": "en"}, clear=False):
            import floor_i18n

            assert floor_i18n.LANG == "en"

    def test_detect_lang_ru_override(self):
        """Test Russian language override."""
        if "floor_i18n" in sys.modules:
            del sys.modules["floor_i18n"]

        with patch.dict(os.environ, {"RAISEDFLOOR_LANG": "ru"}, clear=False):
            import floor_i18n

            assert floor_i18n.LANG == "ru"


class TestTranslation:
    """Tests for translation functionality."""

    def test_tr_function_exists(self):
        """Test that tr function is available."""
        if "floor_i18n" in sys.modules:
            del sys.modules["floor_i18n"]

        import floor_i18n

        assert hasattr(floor_i18n, "tr")
        assert callable(floor_i18n.tr)

    def test_tr_returns_string(self):
        """Test that tr returns a string."""
        if "floor_i18n" in sys.modules:
            del sys.modules["floor_i18n"]

        import floor_i18n

        result = floor_i18n.tr("test_key")
        assert isinstance(result, str)

    def test_tr_with_formatting(self):
        """Test translation with format arguments."""
        if "floor_i18n" in sys.modules:
            del sys.modules["floor_i18n"]

        import floor_i18n

        result = floor_i18n.tr("error_fmt", error="Test")
        assert isinstance(result, str)

    def test_tr_missing_key(self):
        """Test handling of missing translation key."""
        if "floor_i18n" in sys.modules:
            del sys.modules["floor_i18n"]

        import floor_i18n

        result = floor_i18n.tr("nonexistent_key_12345")
        # Should return the key itself or a default message
        assert isinstance(result, str)


class TestTextDictionary:
    """Tests for translation dictionary structure."""

    def test_ru_dictionary_exists(self):
        """Test that Russian dictionary exists."""
        if "floor_i18n" in sys.modules:
            del sys.modules["floor_i18n"]

        import floor_i18n

        assert "ru" in floor_i18n._TEXT
        assert isinstance(floor_i18n._TEXT["ru"], dict)

    def test_en_dictionary_exists(self):
        """Test that English dictionary exists."""
        if "floor_i18n" in sys.modules:
            del sys.modules["floor_i18n"]

        import floor_i18n

        assert "en" in floor_i18n._TEXT
        assert isinstance(floor_i18n._TEXT["en"], dict)

    def test_required_keys_present_ru(self):
        """Test that required keys are present in Russian dictionary."""
        if "floor_i18n" in sys.modules:
            del sys.modules["floor_i18n"]

        import floor_i18n

        required_keys = [
            "error_fmt",
            "operation_cancelled",
            "pick_floor_prompt",
        ]

        for key in required_keys:
            assert key in floor_i18n._TEXT["ru"], f"Missing key: {key}"

    def test_required_keys_present_en(self):
        """Test that required keys are present in English dictionary."""
        if "floor_i18n" in sys.modules:
            del sys.modules["floor_i18n"]

        import floor_i18n

        required_keys = [
            "error_fmt",
            "operation_cancelled",
            "pick_floor_prompt",
        ]

        for key in required_keys:
            assert key in floor_i18n._TEXT["en"], f"Missing key: {key}"
