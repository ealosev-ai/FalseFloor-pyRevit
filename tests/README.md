# RaisedFloor.extension - Testing Guide

## 🧪 Запуск тестов

### Внутри Revit (через pyRevit)

1. Откройте Revit с загруженным проектом
2. В панели **Фальшпол** нажмите **🧪 Тесты** → **Запустить тесты**
3. Проверьте лог输出 в окне pyRevit

Тесты проверяют:

- ✅ Локализацию (RU/EN)
- ✅ Утилиты (floor_utils)
- ✅ Базовые функции (floor_common)
- ✅ Константы сетки (floor_grid)
- ✅ UI форматирование (floor_ui)
- ✅ Интеграцию с Revit

### Вне Revit (pytest)

```bash
# Установка зависимостей
py -3.11 -m venv .venv
.venv\\Scripts\\python -m pip install -U pip
.venv\\Scripts\\pip install -r requirements-dev.txt

# Запуск тестов
.venv\\Scripts\\python -m pytest tests/ -m "not revit" -v --cov

# Только unit-тесты (без Revit API)
.venv\\Scripts\\python -m pytest tests/ -m unit -v

# Интеграционные Revit-тесты (только в Revit-совместимом окружении)
set RUN_REVIT_TESTS=1
.venv\\Scripts\\python -m pytest tests/ -m revit -v

# Только тесты локализации
.venv\\Scripts\\python -m pytest tests/test_floor_i18n.py -v

# Только чистые функции
.venv\\Scripts\\python -m pytest tests/test_floor_utils_pure.py -v

# С отчётом о покрытии
.venv\\Scripts\\python -m pytest tests/ -v --cov=lib --cov-report=html
```

## 📊 Покрытие кода

После запуска тестов откройте `htmlcov/index.html` для просмотра отчёта.

## 📝 Структура тестов

```
tests/
├── conftest.py              # Фикстуры pytest
├── test_floor_i18n.py       # Тесты локализации
├── test_floor_utils.py      # Тесты утилит (требуют моков)
├── test_floor_utils_pure.py # Тесты чистых функций
└── test_floor_common.py     # Тесты базовых функций (требуют моков)
```

## 🔧 Добавление новых тестов

1. Создайте файл `test_*.py` в папке `tests/`
2. Используйте префикс `test_` для функций
3. Добавляйте_assert для проверок

Пример:

```python
def test_my_function():
    from floor_utils import my_function
    result = my_function("input")
    assert result == "expected"
```

## 🐛 Устранение проблем

### Тесты не запускаются в Revit

**Решение:**

1. Проверьте, что pyRevit загружен
2. Перезапустите Revit
3. Выполните `Reload pyRevit`

### Ошибки импорта

**Решение:**

```bash
# Проверьте пути
python -c "import sys; print('\\n'.join(sys.path))"

# Добавьте пути вручную если нужно
sys.path.insert(0, 'path/to/lib')
```

### Тесты падают с "No module named 'Autodesk'"

Это ожидаемо вне Revit для `-m revit` тестов.

Для обычной среды запускайте:

- `pytest tests/ -m "not revit"`
- `pytest tests/test_floor_i18n.py`
- `pytest tests/test_floor_utils_pure.py`

## 📈 CI/CD

Тесты автоматически запускаются в GitHub Actions при:

- Push в main/develop
- Pull requests
- Ручном запуске workflow

См. `.github/workflows/ci-cd.yml`

---

**Версия:** v1.3.0
**Последнее обновление:** 2026-03-20
