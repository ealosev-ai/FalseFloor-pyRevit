# -*- coding: utf-8 -*-
"""Переключение языка runtime UI (Auto/RU/EN) для FalseFloor.

Сохраняет выбор в переменную пользователя FALSEFLOOR_LANG.
Auto: удаляет override и включает автоопределение по CurrentUICulture.
"""

import os

from floor_i18n import tr  # type: ignore
from pyrevit import forms  # type: ignore

ENV_NAME = "FALSEFLOOR_LANG"


def _get_current_mode():
    val = (os.environ.get(ENV_NAME) or "").strip().lower()
    if val in ("ru", "en"):
        return val
    try:
        import System  # type: ignore

        val = System.Environment.GetEnvironmentVariable(
            ENV_NAME, System.EnvironmentVariableTarget.User
        )
        val = (val or "").strip().lower()
        if val in ("ru", "en"):
            return val
    except Exception:
        pass
    return "auto"


def _set_user_env(value):
    import System  # type: ignore

    target = System.EnvironmentVariableTarget.User
    if value is None:
        System.Environment.SetEnvironmentVariable(ENV_NAME, None, target)
        os.environ.pop(ENV_NAME, None)
    else:
        System.Environment.SetEnvironmentVariable(ENV_NAME, value, target)
        os.environ[ENV_NAME] = value


def main():
    title = tr("ui_lang_title")
    current = _get_current_mode()
    options = ["Auto", "RU", "EN"]

    selected = forms.CommandSwitchWindow.show(
        options,
        message=tr("ui_lang_current", mode=current),
    )
    if not selected:
        return

    if selected == "Auto":
        _set_user_env(None)
        result = "auto"
    elif selected == "RU":
        _set_user_env("ru")
        result = "ru"
    else:
        _set_user_env("en")
        result = "en"

    mode_help = {
        "auto": tr("ui_lang_auto_desc"),
        "ru": tr("ui_lang_ru_desc"),
        "en": tr("ui_lang_en_desc"),
    }

    forms.alert(
        tr("ui_lang_saved", mode=result, desc=mode_help.get(result, "")),
        title=title,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        forms.alert(tr("error_inline_fmt", error=str(ex)), title=tr("ui_lang_title"))
