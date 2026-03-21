# -*- coding: utf-8 -*-
"""Test Runner for RaisedFloor.extension.

Запуск тестов внутри Revit через pyRevit.
Использование:
    1. Открыть Revit
    2. Запустить этот скрипт через pyRevit: Run Script
"""

import sys
import os
from pyrevit import script

# Добавляем пути к тестам
TESTS_DIR = os.path.dirname(__file__)
LIB_DIR = os.path.join(TESTS_DIR, 'lib')
TESTS_DIR = os.path.join(TESTS_DIR, 'tests')

sys.path.insert(0, LIB_DIR)
sys.path.insert(0, TESTS_DIR)

# Логгер
logger = script.get_logger()

def run_tests():
    """Запускает тестовый набор."""
    results = {
        'passed': 0,
        'failed': 0,
        'errors': [],
    }
    
    logger.info('=' * 60)
    logger.info('RaisedFloor.extension - Test Suite')
    logger.info('=' * 60)
    
    # ─── Тест 1: floor_i18n (локализация) ────────────────────────────────────
    logger.info('\n[TEST 1/6] Testing floor_i18n (localization)...')
    try:
        from floor_i18n import tr, LANG, _TEXT
        
        # Проверка наличия языков
        assert 'ru' in _TEXT, "Russian dictionary missing"
        assert 'en' in _TEXT, "English dictionary missing"
        
        # Проверка перевода
        test_key = "error_fmt"
        ru_text = _TEXT['ru'].get(test_key)
        en_text = _TEXT['en'].get(test_key)
        assert ru_text is not None, f"Key '{test_key}' missing in RU"
        assert en_text is not None, f"Key '{test_key}' missing in EN"
        
        # Проверка функции tr()
        result = tr("pick_floor_prompt")
        assert isinstance(result, str), "tr() should return string"
        assert len(result) > 0, "tr() should return non-empty string"
        
        # Проверка автоопределения языка
        assert LANG in ('ru', 'en'), f"Invalid LANG: {LANG}"
        
        results['passed'] += 1
        logger.info('  ✅ PASSED: floor_i18n tests')
        
    except Exception as ex:
        results['failed'] += 1
        results['errors'].append(('floor_i18n', str(ex)))
        logger.error('  ❌ FAILED: floor_i18n tests - {}'.format(str(ex)))
    
    # ─── Тест 2: floor_utils (утилиты) ───────────────────────────────────────
    logger.info('\n[TEST 2/6] Testing floor_utils (utilities)...')
    try:
        from floor_utils import (
            safe_get_name,
            normalize_path,
            parse_version_string,
            format_error_message,
        )
        
        # Test safe_get_name
        class MockObj:
            Name = "TestName"
        assert safe_get_name(MockObj()) == "TestName"
        assert safe_get_name(None) is None
        
        # Test normalize_path
        path = normalize_path("test/path")
        assert os.path.isabs(path), "Path should be absolute"
        
        # Test parse_version_string
        assert parse_version_string("1.2.3") == (1, 2, 3)
        assert parse_version_string("v1.2.0") == (1, 2, 0)
        assert parse_version_string("") == ()
        
        # Test format_error_message
        error = Exception("Test")
        msg = format_error_message(error)
        assert "Test" in msg
        
        results['passed'] += 1
        logger.info('  ✅ PASSED: floor_utils tests')
        
    except Exception as ex:
        results['failed'] += 1
        results['errors'].append(('floor_utils', str(ex)))
        logger.error('  ❌ FAILED: floor_utils tests - {}'.format(str(ex)))
    
    # ─── Тест 3: floor_common (базовые функции) ──────────────────────────────
    logger.info('\n[TEST 3/6] Testing floor_common (base functions)...')
    try:
        from floor_common import (
            build_positions,
            parse_ids_from_string,
            cut_equal_1d,
            cut_at_positions_1d,
        )
        
        # Test build_positions
        positions = build_positions(0, 100, 0, 10)
        assert len(positions) > 0
        assert positions[0] <= 0
        assert positions[-1] >= 100
        
        # Test parse_ids_from_string
        ids = parse_ids_from_string("1;2;3;4;5")
        assert ids == [1, 2, 3, 4, 5]
        assert parse_ids_from_string("") == []
        
        # Test cut_equal_1d
        segments = cut_equal_1d(0, 10, 5)
        assert len(segments) == 2
        assert segments[0] == (0, 5)
        
        # Test cut_at_positions_1d
        segments = cut_at_positions_1d(0, 10, 5, [3, 5, 7])
        assert len(segments) >= 2
        
        results['passed'] += 1
        logger.info('  ✅ PASSED: floor_common tests')
        
    except Exception as ex:
        results['failed'] += 1
        results['errors'].append(('floor_common', str(ex)))
        logger.error('  ❌ FAILED: floor_common tests - {}'.format(str(ex)))
    
    # ─── Тест 4: floor_grid (сетка) ──────────────────────────────────────────
    logger.info('\n[TEST 4/6] Testing floor_grid (grid functions)...')
    try:
        from floor_grid import (
            GRID_LINE_STYLE_NAME,
            GRID_COLOR,
            CONTOUR_STYLE_NAME,
            CONTOUR_COLOR,
        )
        
        # Проверка констант
        assert GRID_LINE_STYLE_NAME == "RF_Grid"
        assert CONTOUR_STYLE_NAME == "RF_Contour"
        
        # Проверка цветов (должны быть Color объектами)
        assert GRID_COLOR is not None
        assert CONTOUR_COLOR is not None
        
        results['passed'] += 1
        logger.info('  ✅ PASSED: floor_grid constants tests')
        
    except Exception as ex:
        results['failed'] += 1
        results['errors'].append(('floor_grid', str(ex)))
        logger.error('  ❌ FAILED: floor_grid tests - {}'.format(str(ex)))
    
    # ─── Тест 5: floor_ui (UI форматирование) ────────────────────────────────
    logger.info('\n[TEST 5/6] Testing floor_ui (UI formatting)...')
    try:
        from floor_ui import (
            TITLE_PREPARE,
            TITLE_GRID,
            TITLE_CONTOUR,
            TITLE_SHIFT,
            get_shift_quality_status,
        )
        
        # Проверка заголовков
        assert isinstance(TITLE_PREPARE, str)
        assert isinstance(TITLE_GRID, str)
        assert isinstance(TITLE_CONTOUR, str)
        assert isinstance(TITLE_SHIFT, str)
        
        # Проверка функции качества смещения
        test_result = {
            "non_viable_count": 0,
            "unwanted_count": 0,
            "complex_count": 0,
            "acceptable_count": 5,
        }
        status = get_shift_quality_status(test_result)
        assert isinstance(status, str)
        
        results['passed'] += 1
        logger.info('  ✅ PASSED: floor_ui tests')
        
    except Exception as ex:
        results['failed'] += 1
        results['errors'].append(('floor_ui', str(ex)))
        logger.error('  ❌ FAILED: floor_ui tests - {}'.format(str(ex)))
    
    # ─── Тест 6: Интеграция (документ Revit) ─────────────────────────────────
    logger.info('\n[TEST 6/6] Testing Revit integration...')
    try:
        from pyrevit import revit
        
        doc = revit.doc
        
        # Проверка доступа к документу
        assert doc is not None, "Revit document is None"
        assert hasattr(doc, 'Title'), "Document should have Title"
        
        # Проверка, что мы в проекте (не семейство)
        is_project = not doc.IsFamilyDocument
        logger.info('  Document: {} (Project: {})'.format(doc.Title, is_project))
        
        results['passed'] += 1
        logger.info('  ✅ PASSED: Revit integration tests')
        
    except Exception as ex:
        results['failed'] += 1
        results['errors'].append(('revit_integration', str(ex)))
        logger.error('  ❌ FAILED: Revit integration tests - {}'.format(str(ex)))
    
    # ─── Итоги ───────────────────────────────────────────────────────────────
    logger.info('\n' + '=' * 60)
    logger.info('TEST RESULTS')
    logger.info('=' * 60)
    logger.info('Passed: {}'.format(results['passed']))
    logger.info('Failed: {}'.format(results['failed']))
    logger.info('Total:  {}'.format(results['passed'] + results['failed']))
    
    if results['errors']:
        logger.info('\nErrors:')
        for test_name, error in results['errors']:
            logger.error('  - {}: {}'.format(test_name, error))
    
    logger.info('=' * 60)
    
    if results['failed'] == 0:
        logger.info('\n✅ ALL TESTS PASSED!')
    else:
        logger.warning('\n⚠️  {} TEST(S) FAILED'.format(results['failed']))
    
    return results


# Запуск
if __name__ == '__main__':
    try:
        run_tests()
    except Exception as ex:
        logger.error('Test runner crashed: {}'.format(str(ex)))
        import traceback
        logger.error(traceback.format_exc())
