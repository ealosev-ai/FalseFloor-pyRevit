# -*- coding: utf-8 -*-
"""Maintenance command: migrate RF family parameters to canonical shared GUIDs.

This is a maintenance-only tool. It attempts ReplaceParameter first (safe),
and optionally falls back to Remove+Add (destructive, loses formulas/labels).
Also supports project-level GUID migration.
"""

import os
import traceback

from pyrevit import forms  # type: ignore
from revit_context import get_doc  # type: ignore
from rf_family_migration import (  # type: ignore
    TARGET_FAMILY_NAMES,
    collect_loaded_target_families,
    migrate_family_doc,
)
from rf_param_schema import collect_project_parameter_guid_mismatches  # type: ignore
from rf_project_migration import migrate_project_parameter_guids  # type: ignore
from rf_reporting import ScriptReporter  # type: ignore

TITLE = "Миграция GUID"


def _detail_note(reporter):
    labels = reporter.get_sink_labels()
    if not labels:
        return ""

    lines = ["Подробности: {}".format(", ".join(labels))]
    if reporter.log_path:
        lines.append(reporter.log_path)
    return "\n".join(lines)


def _print_family_result(reporter, result):
    """Print family migration result to output window."""
    name = result.get("family_name", "<unknown>")
    replaced = result.get("replaced", [])
    added = result.get("added", [])
    obsolete = result.get("obsolete", [])
    errors = result.get("errors", [])
    dry_run = result.get("dry_run", False)

    prefix = "[DRY-RUN] " if dry_run else ""

    reporter.write("{}{}".format(prefix, name))

    if replaced:
        reporter.write("Migrated GUIDs: {}".format(len(replaced)))
        for pname, old_g, new_g in replaced:
            reporter.write("  - {}: {} -> {}".format(pname, old_g, new_g))

    if added:
        if dry_run:
            reporter.write("Missing (would add): {}".format(len(added)))
        else:
            reporter.write("Added missing: {}".format(len(added)))
        for pname in added:
            label = pname if isinstance(pname, str) else pname[0]
            reporter.write("  + {}".format(label))

    if obsolete:
        reporter.write("Obsolete kept: {}".format(", ".join(obsolete)))

    if result.get("saved"):
        reporter.write("Saved to disk: yes")
    if result.get("reloaded"):
        reporter.write("Reloaded to project: yes")

    if errors:
        for error in errors:
            reporter.write("  error: {}".format(error), level="error")

    if not replaced and not added and not obsolete and not errors:
        reporter.write("No changes needed.")


def _print_project_result(reporter, result):
    """Print project migration result to output window."""
    dry_run = result.get("dry_run", False)
    prefix = "[DRY-RUN] " if dry_run else ""

    if result["migrated"]:
        reporter.write(
            "{}Project GUIDs migrated: {}".format(prefix, len(result["migrated"])),
        )
        for name, old_g, new_g in result["migrated"]:
            reporter.write("  - {}: {} -> {}".format(name, old_g, new_g))

    if result["skipped"]:
        reporter.write("Skipped: {}".format(len(result["skipped"])), level="warn")
        for name, reason in result["skipped"]:
            reporter.write("  - {}: {}".format(name, reason), level="warn")

    if not dry_run and (result["values_backed_up"] or result["values_restored"]):
        reporter.write(
            "Values: backed up {}, restored {}, failed {}".format(
                result["values_backed_up"],
                result["values_restored"],
                result["values_failed"],
            )
        )

    if result["errors"]:
        reporter.write("Errors:", level="error")
        for e in result["errors"]:
            reporter.write("  - {}".format(e), level="error")


def _summarize_family_result(result):
    return "{}: migrated={}, added={}, errors={}".format(
        result.get("family_name", "<unknown>"),
        len(result.get("replaced", [])),
        len(result.get("added", [])),
        len(result.get("errors", [])),
    )


def _summarize_project_result(result):
    return "project: migrated={}, skipped={}, errors={}, restored={}/{}".format(
        len(result.get("migrated", [])),
        len(result.get("skipped", [])),
        len(result.get("errors", [])),
        result.get("values_restored", 0),
        result.get("values_backed_up", 0),
    )


def _run_current_family(doc):
    app = doc.Application
    reporter = ScriptReporter.from_pyrevit(title=TITLE, log_stem="migrate_guids")

    family_name = os.path.splitext(getattr(doc, "Title", "") or "")[0]
    if family_name not in TARGET_FAMILY_NAMES:
        forms.alert(
            "Текущий family document не входит в maintenance-набор:\n{}".format(
                family_name or "<unknown>"
            ),
            title=TITLE,
        )
        return

    reporter.stage("Старт: family document")
    reporter.write("Family: {}".format(family_name))
    if reporter.log_path:
        reporter.write("Text log file: {}".format(reporter.log_path))

    # Dry-run preview first
    reporter.write("Шаг 1/3: dry-run preview")
    preview = migrate_family_doc(
        doc,
        app,
        project_doc=None,
        save_family=False,
        family_name_hint=family_name,
        dry_run=True,
    )
    reporter.stage("Предпросмотр (dry-run)")
    _print_family_result(reporter, preview)

    if not preview["replaced"] and not preview["added"]:
        reporter.write("Все GUID в порядке, миграция не требуется.")
        forms.alert(
            "Изменения не требуются.\n{}".format(_detail_note(reporter)),
            title=TITLE,
        )
        return

    confirm = forms.alert(
        "Выполнить миграцию?\n\n"
        "ReplaceParameter будет использован в первую очередь (безопасный путь).",
        title=TITLE,
        yes=True,
        no=True,
    )
    if not confirm:
        reporter.write("Пользователь отменил миграцию после dry-run.", level="warn")
        return

    # Check if user wants destructive fallback (maintenance-only)
    allow_destructive = False
    if preview["replaced"]:
        destructive_confirm = forms.alert(
            "Разрешить Remove+Add fallback если ReplaceParameter не сработает?\n\n"
            "ВНИМАНИЕ: Remove+Add теряет формулы, label-привязки и geometry-ассоциации.\n"
            "Значения параметров будут сохранены, но связи — нет.",
            title=TITLE + " (maintenance)",
            yes=True,
            no=True,
        )
        allow_destructive = bool(destructive_confirm)
        if allow_destructive:
            reporter.write("Разрешён maintenance fallback: Remove+Add.", level="warn")
        else:
            reporter.write("Выбран безопасный режим: только ReplaceParameter.")

    save_family = bool(getattr(doc, "PathName", "") or "")
    reporter.write("Шаг 2/3: выполнение миграции")
    result = migrate_family_doc(
        doc,
        app,
        project_doc=None,
        save_family=save_family,
        family_name_hint=family_name,
        allow_destructive=allow_destructive,
    )

    reporter.stage("Результат миграции")
    _print_family_result(reporter, result)
    reporter.write(_summarize_family_result(result))
    forms.alert(
        "Миграция завершена.\n{}\n{}".format(
            _summarize_family_result(result),
            _detail_note(reporter),
        ),
        title=TITLE,
    )


def _run_project(doc):
    app = doc.Application
    reporter = ScriptReporter.from_pyrevit(title=TITLE, log_stem="migrate_guids")
    reporter.stage("Старт: project document")
    if reporter.log_path:
        reporter.write("Text log file: {}".format(reporter.log_path))

    # === Phase 1: Family migration ===
    families = collect_loaded_target_families(doc)
    reporter.write("Фаза 1/2: loaded families -> {}".format(len(families)))

    if families:
        lines = [
            "Будет выполнена maintenance-миграция GUID для loaded families.",
            "",
            "Семейства:",
        ]
        for family in sorted(families, key=lambda item: item.Name):
            lines.append("  - {}".format(family.Name))

        confirm = forms.alert(
            "\n".join(lines) + "\n\nВыполнить миграцию семейств?",
            title=TITLE,
            yes=True,
            no=True,
        )
        if not confirm:
            reporter.write("Миграция семейств пропущена пользователем.", level="warn")
        else:
            # Dry-run preview
            reporter.stage("Семейства — предпросмотр")
            for family in sorted(families, key=lambda item: item.Name):
                fam_doc = None
                try:
                    reporter.write("Открытие семейства: {}".format(family.Name))
                    fam_doc = doc.EditFamily(family)
                    preview = migrate_family_doc(
                        fam_doc,
                        app,
                        family_name_hint=family.Name,
                        dry_run=True,
                    )
                    _print_family_result(reporter, preview)
                except Exception as ex:
                    reporter.write(
                        "{} - error: {}".format(family.Name, str(ex)),
                        level="error",
                    )
                finally:
                    if fam_doc is not None:
                        try:
                            fam_doc.Close(False)
                        except Exception:
                            pass

            # Ask for destructive fallback
            allow_destructive = False
            destructive_confirm = forms.alert(
                "Разрешить Remove+Add fallback если ReplaceParameter не сработает?\n\n"
                "ВНИМАНИЕ: теряет формулы и geometry-ассоциации.\n"
                "Рекомендуется: Нет (только безопасный ReplaceParameter).",
                title=TITLE + " (maintenance)",
                yes=True,
                no=True,
            )
            allow_destructive = bool(destructive_confirm)
            if allow_destructive:
                reporter.write(
                    "Разрешён maintenance fallback: Remove+Add.", level="warn"
                )
            else:
                reporter.write("Выбран безопасный режим: только ReplaceParameter.")

            # Execute
            reporter.stage("Семейства — результат")
            for family in sorted(families, key=lambda item: item.Name):
                fam_doc = None
                try:
                    reporter.write("Миграция семейства: {}".format(family.Name))
                    fam_doc = doc.EditFamily(family)
                    save_family = bool(getattr(fam_doc, "PathName", "") or "")
                    result = migrate_family_doc(
                        fam_doc,
                        app,
                        project_doc=doc,
                        save_family=save_family,
                        family_name_hint=family.Name,
                        allow_destructive=allow_destructive,
                    )
                    _print_family_result(reporter, result)
                    reporter.write(_summarize_family_result(result))
                except Exception as ex:
                    reporter.write(
                        "{} - error: {}".format(family.Name, str(ex)),
                        level="error",
                    )
                finally:
                    if fam_doc is not None:
                        try:
                            fam_doc.Close(False)
                        except Exception:
                            pass
    else:
        reporter.write(
            "В проекте не найдены загруженные editable семейства: {}".format(
                ", ".join(TARGET_FAMILY_NAMES)
            )
        )

    # === Phase 2: Project parameter GUID migration ===
    reporter.write("Фаза 2/2: project parameter GUID migration")
    existing_bindings = {}
    try:
        from floor_utils import get_existing_parameter_bindings  # type: ignore

        existing_bindings = get_existing_parameter_bindings(doc)
    except Exception:
        pass

    rf_bound = {n for n in existing_bindings if n.startswith("RF_")}
    project_mismatches = collect_project_parameter_guid_mismatches(
        doc, allowed_names=rf_bound, bound_names=rf_bound
    )

    if project_mismatches:
        reporter.stage("Проектные параметры — предпросмотр")
        reporter.write("GUID mismatch count: {}".format(len(project_mismatches)))

        # Dry-run preview
        preview = migrate_project_parameter_guids(doc, app, dry_run=True)
        _print_project_result(reporter, preview)

        confirm = forms.alert(
            "Мигрировать проектные GUID ({} параметров)?\n\n"
            "ВНИМАНИЕ: может сломать спецификации, фильтры видов и теги.\n"
            "Делайте только на копии проекта.".format(len(project_mismatches)),
            title=TITLE,
            yes=True,
            no=True,
        )
        if confirm:
            reporter.write("Запуск реальной миграции project GUIDs.")
            proj_result = migrate_project_parameter_guids(doc, app)
            reporter.stage("Проектные параметры — результат")
            _print_project_result(reporter, proj_result)
            reporter.write(_summarize_project_result(proj_result))
            forms.alert(
                "Миграция завершена.\n{}\n{}".format(
                    _summarize_project_result(proj_result),
                    _detail_note(reporter),
                ),
                title=TITLE,
            )
        else:
            reporter.write(
                "Миграция project GUIDs отменена пользователем.", level="warn"
            )
    else:
        reporter.stage("Проектные параметры")
        reporter.write("Проектные GUID в порядке — миграция не требуется.")
        forms.alert(
            "Изменения не требуются.\n{}".format(_detail_note(reporter)),
            title=TITLE,
        )


try:
    doc = get_doc()
    if not doc:
        raise Exception("No active document")

    if doc.IsFamilyDocument:
        _run_current_family(doc)
    else:
        _run_project(doc)

except Exception as ex:
    if str(ex) != "cancel":
        detail_note = ""
        try:
            reporter = ScriptReporter.from_pyrevit(
                title=TITLE, log_stem="migrate_guids"
            )
            reporter.write("Unhandled error: {}".format(str(ex)), level="error")
            reporter.write(traceback.format_exc(), level="error")
            detail_note = _detail_note(reporter)
        except Exception:
            detail_note = ""
        forms.alert(
            "{}\n\n{}\n\n{}".format(str(ex), traceback.format_exc(), detail_note),
            title=TITLE,
        )
