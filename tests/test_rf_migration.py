"""Tests for RF family and project GUID migration logic."""

from contextlib import contextmanager
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit]


# --- Helpers to mock Revit API for rf_family_migration import ---


def _make_revit_db_mock():
    """Create a mock Autodesk.Revit.DB module with needed types."""
    db = ModuleType("Autodesk.Revit.DB")
    db.Family = type("Family", (), {})
    db.FamilySource = MagicMock()
    db.FilteredElementCollector = MagicMock()
    db.IFamilyLoadOptions = type("IFamilyLoadOptions", (), {})
    db.StorageType = MagicMock()
    db.StorageType.Double = "Double"
    db.StorageType.Integer = "Integer"
    db.StorageType.String = "String"
    db.StorageType.ElementId = "ElementId"
    db.SubTransaction = MagicMock()
    db.Transaction = MagicMock()
    db.SharedParameterElement = type("SharedParameterElement", (), {})
    db.TransactionGroup = MagicMock()
    db.InstanceBinding = type("InstanceBinding", (), {})
    db.TypeBinding = type("TypeBinding", (), {})
    db.ElementId = MagicMock()
    db.ExternalDefinition = type("ExternalDefinition", (), {})
    db.FamilyParameter = type("FamilyParameter", (), {})
    # Types needed by floor_utils
    db.Category = MagicMock()
    db.CategorySet = MagicMock()
    db.Document = type("Document", (), {})
    # Version-conditional types
    db.GroupTypeId = MagicMock()
    db.BuiltInParameterGroup = MagicMock()
    db.SpecTypeId = MagicMock()
    db.ParameterType = MagicMock()
    db.ExternalDefinitionCreationOptions = MagicMock()
    return db


@pytest.fixture(autouse=True)
def _mock_revit_modules():
    """Mock Revit and pyrevit modules for all tests in this file."""
    db_mod = _make_revit_db_mock()
    revit_mod = ModuleType("Autodesk.Revit")
    autodesk_mod = ModuleType("Autodesk")

    mocks = {
        "Autodesk": autodesk_mod,
        "Autodesk.Revit": revit_mod,
        "Autodesk.Revit.DB": db_mod,
        "pyrevit": MagicMock(),
        "pyrevit.forms": MagicMock(),
        "pyrevit.revit": MagicMock(),
        "pyrevit.script": MagicMock(),
        "revit_context": MagicMock(),
        "floor_i18n": MagicMock(),
    }
    with patch.dict("sys.modules", mocks):
        # Force re-import so modules pick up mocks
        for mod_name in [
            "floor_utils",
            "rf_param_schema",
            "rf_family_migration",
            "rf_project_migration",
        ]:
            if mod_name in sys.modules:
                del sys.modules[mod_name]
        yield db_mod


# === Tests for _try_replace_parameter ===


class TestTryReplaceParameter:
    def test_strategy_a_direct_call_succeeds(self, _mock_revit_modules):
        import rf_family_migration as mod

        fam_mgr = MagicMock()
        fam_mgr.ReplaceParameter = MagicMock()  # direct call works

        old_param = MagicMock()
        ext_def = MagicMock()
        group_id = MagicMock()

        success, strategy, err = mod._try_replace_parameter(
            fam_mgr, old_param, ext_def, group_id, True
        )
        assert success is True
        assert strategy == "direct_call"
        assert err == ""

    def test_all_strategies_fail_returns_error(self, _mock_revit_modules):
        import rf_family_migration as mod

        fam_mgr = MagicMock()
        fam_mgr.ReplaceParameter = MagicMock(side_effect=Exception("overload fail"))
        fam_mgr.ReplaceParameter.Overloads = MagicMock(
            __getitem__=MagicMock(
                return_value=MagicMock(side_effect=Exception("Overloads fail"))
            )
        )
        fam_mgr.ReplaceParameter.__overloads__ = MagicMock(
            __getitem__=MagicMock(
                return_value=MagicMock(side_effect=Exception("__overloads__ fail"))
            )
        )

        # Mock clr for reflection strategy
        clr_mock = MagicMock()
        clr_mock.GetClrType = MagicMock(return_value=MagicMock())
        sys_mock = MagicMock()
        sys_mock.Array = MagicMock()
        sys_mock.Type = MagicMock()
        sys_mock.Boolean = MagicMock()
        sys_mock.Object = MagicMock()

        with patch.dict("sys.modules", {"clr": clr_mock, "System": sys_mock}):
            # Make reflection fail too
            mock_type = MagicMock()
            mock_type.GetMethod = MagicMock(return_value=None)
            clr_mock.GetClrType.return_value = mock_type

            success, strategy, err = mod._try_replace_parameter(
                fam_mgr, MagicMock(), MagicMock(), MagicMock(), True
            )
            assert success is False
            assert "All ReplaceParameter strategies failed" in err


# === Tests for migrate_family_doc dry_run ===


class TestMigrateFamilyDocDryRun:
    def test_dry_run_returns_mismatches_without_transaction(self, _mock_revit_modules):
        import rf_family_migration as mod

        # Mock the family document
        fam_doc = MagicMock()
        fam_doc.IsFamilyDocument = True

        # Mock FamilyManager with parameters
        param_def = MagicMock()
        param_def.Name = "RF_Column"
        param = MagicMock()
        param.Definition = param_def
        param.IsShared = True
        param.GUID = "WRONG-GUID"

        fam_mgr = MagicMock()
        fam_mgr.GetParameters.return_value = [param]
        fam_doc.FamilyManager = fam_mgr
        fam_doc.OwnerFamily.Name = "RF_Support"

        app = MagicMock()

        # Mock ensure_schema_definitions to return ext_defs
        with patch.object(
            mod,
            "_load_canonical_defs",
            return_value={
                "RF_Column": (MagicMock(), True),
                "RF_Row": (MagicMock(), True),
                "RF_Mark": (MagicMock(), True),
                "RF_Support_Height": (MagicMock(), True),
                "RF_Base_Size": (MagicMock(), False),
                "RF_Head_Size": (MagicMock(), False),
            },
        ):
            result = mod.migrate_family_doc(
                fam_doc, app, dry_run=True, family_name_hint="RF_Support"
            )

        assert result["dry_run"] is True
        # Should detect the mismatch
        assert len(result["replaced"]) >= 1
        # Transaction should NOT have been created
        db_mod = sys.modules["Autodesk.Revit.DB"]
        db_mod.Transaction.assert_not_called()


# === Tests for _replace_mismatched_params_no_tx with allow_destructive ===


class TestReplaceMismatchedParams:
    def test_default_mode_hard_fails_on_replace_failure(self, _mock_revit_modules):
        import rf_family_migration as mod

        fam_doc = MagicMock()
        fam_mgr = MagicMock()
        fam_doc.FamilyManager = fam_mgr

        param_def = MagicMock()
        param_def.Name = "RF_Column"
        param = MagicMock()
        param.Definition = param_def
        fam_mgr.GetParameters.return_value = [param]

        # Setup SubTransaction mock
        subtx_mock = MagicMock()
        db_mod = sys.modules["Autodesk.Revit.DB"]
        db_mod.SubTransaction = MagicMock(return_value=subtx_mock)

        ext_defs = {"RF_Column": (MagicMock(), True)}
        replaced = []
        errors = []

        # Mock _try_replace_parameter to fail
        with patch.object(mod, "_get_group_type_id", return_value=MagicMock()):
            with patch.object(
                mod,
                "collect_family_parameter_guid_mismatches",
                return_value=[("RF_Column", "OLD", "NEW")],
            ):
                with patch.object(
                    mod,
                    "_collect_family_param_by_name",
                    return_value={"RF_Column": param},
                ):
                    with patch.object(
                        mod,
                        "_try_replace_parameter",
                        return_value=(False, "", "All strategies failed"),
                    ):
                        mod._replace_mismatched_params_no_tx(
                            fam_doc,
                            ext_defs,
                            {"RF_Column"},
                            replaced,
                            errors,
                            allow_destructive=False,
                        )

        # Should NOT have replaced (hard fail)
        assert len(replaced) == 0
        # Should have error mentioning ReplaceParameter failed
        assert len(errors) >= 1
        assert "ReplaceParameter failed" in errors[0]


# === Tests for get_full_parameter_binding_info ===


class TestGetFullParameterBindingInfo:
    def test_returns_binding_info_with_all_fields(self, _mock_revit_modules):
        import floor_utils

        db_mod = sys.modules["Autodesk.Revit.DB"]

        # Create mock binding map iterator
        definition = MagicMock()
        definition.Name = "RF_Step_X"
        definition.GetGroupTypeId.return_value = "GroupTypeId.Data"

        InstanceBindingType = db_mod.InstanceBinding
        binding = MagicMock(spec=InstanceBindingType)
        # Make isinstance check work
        binding.__class__ = InstanceBindingType
        cat = MagicMock()
        cat.BuiltInCategory = "OST_Floors"
        binding.Categories = [cat]

        iterator = MagicMock()
        iterator.MoveNext = MagicMock(side_effect=[True, False])
        iterator.Key = definition
        iterator.Current = binding

        doc = MagicMock()
        doc.ParameterBindings.ForwardIterator.return_value = iterator

        result = floor_utils.get_full_parameter_binding_info(doc)

        assert "RF_Step_X" in result
        info = result["RF_Step_X"]
        assert info["definition"] is definition
        assert info["binding"] is binding
        assert info["group_id"] == "GroupTypeId.Data"
        assert len(info["categories"]) == 1


# === Tests for rf_project_migration helpers ===


class TestProjectMigrationHelpers:
    def test_find_shared_param_element_by_guid(self, _mock_revit_modules):
        import rf_project_migration as mod

        spe1 = MagicMock()
        spe1.GuidValue = "aa5ed481-5cf0-5933-b251-3a290396bb12"

        spe2 = MagicMock()
        spe2.GuidValue = "WRONG-GUID"

        collector_instance = MagicMock()
        collector_instance.OfClass.return_value = [spe1, spe2]

        doc = MagicMock()
        with patch.object(
            mod, "FilteredElementCollector", return_value=collector_instance
        ):
            found = mod._find_shared_param_element_by_guid(
                doc, "aa5ed481-5cf0-5933-b251-3a290396bb12"
            )
            assert found is spe1

            not_found = mod._find_shared_param_element_by_guid(doc, "NONEXISTENT")
            assert not_found is None

    def test_read_param_value_handles_storage_types(self, _mock_revit_modules):
        import rf_project_migration as mod

        db_mod = sys.modules["Autodesk.Revit.DB"]

        # Double param
        param = MagicMock()
        param.IsReadOnly = False
        param.HasValue = True
        param.StorageType = db_mod.StorageType.Double
        param.AsDouble.return_value = 3.14

        value, ok = mod._read_param_value(param)
        assert ok is True
        assert value == 3.14

        # None param
        value, ok = mod._read_param_value(None)
        assert ok is False

    def test_unresolvable_guid_is_skipped(self, _mock_revit_modules):
        import rf_project_migration as mod

        doc = MagicMock()
        app = MagicMock()

        with patch.object(
            mod,
            "get_full_parameter_binding_info",
            return_value={"RF_Step_X": {"definition": MagicMock()}},
        ):
            with patch.object(
                mod,
                "collect_project_parameter_guid_mismatches",
                return_value=[
                    ("RF_Step_X", "<not-shared-or-unresolved>", "expected-guid")
                ],
            ):
                result = mod.migrate_project_parameter_guids(doc, app, dry_run=True)

        assert len(result["skipped"]) == 1
        assert result["skipped"][0] == ("RF_Step_X", "unresolvable-guid")
        assert len(result["migrated"]) == 0


# === Tests for restore-phase rollback (Fix: tg.Assimilate after restore failure) ===


class TestProjectMigrationRestoreRollback:
    def test_restore_failure_rolls_back_transaction_group(self, _mock_revit_modules):
        """If restore phase raises, the whole TransactionGroup should be rolled back,
        NOT assimilated (which would commit delete+recreate without values)."""
        import rf_project_migration as mod

        db_mod = sys.modules["Autodesk.Revit.DB"]

        doc = MagicMock()
        app = MagicMock()

        spe = MagicMock()
        spe.GuidValue = "old-guid"
        internal_def = MagicMock()
        internal_def.StorageType = db_mod.StorageType.Double
        spe.GetDefinition.return_value = internal_def

        binding_info = {
            "RF_Step_X": {
                "definition": MagicMock(),
                "binding": MagicMock(),
                "is_instance": True,
                "categories": [],
                "group_id": MagicMock(),
            }
        }

        tg_mock = MagicMock()
        t1_mock = MagicMock()
        t2_mock = MagicMock()
        t3_mock = MagicMock()
        # t3 (restore) raises on Start
        t3_mock.Start.side_effect = Exception("Restore exploded")
        t3_mock.HasStarted.return_value = True

        # Mock Insert to succeed (t2 phase)
        doc.ParameterBindings.Insert.return_value = True

        # Patch at module level — rf_project_migration imports these at top
        with patch.object(mod, "TransactionGroup", return_value=tg_mock):
            with patch.object(
                mod, "Transaction", side_effect=[t1_mock, t2_mock, t3_mock]
            ):
                with patch.object(
                    mod,
                    "get_full_parameter_binding_info",
                    return_value=binding_info,
                ):
                    with patch.object(
                        mod,
                        "collect_project_parameter_guid_mismatches",
                        return_value=[("RF_Step_X", "old-guid", "new-guid")],
                    ):
                        with patch.object(
                            mod,
                            "_find_shared_param_element_by_guid",
                            return_value=spe,
                        ):
                            with patch.object(
                                mod,
                                "_backup_element_values",
                                return_value=(
                                    db_mod.StorageType.Double,
                                    {100: 3.14},
                                    1,
                                ),
                            ):
                                with patch.object(
                                    mod,
                                    "ensure_schema_definitions",
                                    return_value={"RF_Step_X": MagicMock()},
                                ):
                                    result = mod.migrate_project_parameter_guids(
                                        doc, app
                                    )

        # TransactionGroup should be rolled back, not assimilated
        tg_mock.RollBack.assert_called()
        tg_mock.Assimilate.assert_not_called()
        assert result["errors"], "Expected errors from restore failure"


# === Tests for storage type resolution (Fix: no String fallback) ===


class TestStorageTypeFromSPE:
    def test_get_storage_type_from_spe_returns_internal_def_type(
        self, _mock_revit_modules
    ):
        import rf_project_migration as mod

        db_mod = sys.modules["Autodesk.Revit.DB"]
        spe = MagicMock()
        internal_def = MagicMock()
        internal_def.StorageType = db_mod.StorageType.Double
        spe.GetDefinition.return_value = internal_def

        result = mod._get_storage_type_from_spe(spe)
        assert result == db_mod.StorageType.Double

    def test_get_storage_type_from_spe_returns_none_on_failure(
        self, _mock_revit_modules
    ):
        import rf_project_migration as mod

        spe = MagicMock()
        spe.GetDefinition.side_effect = Exception("no definition")

        result = mod._get_storage_type_from_spe(spe)
        assert result is None

    def test_get_storage_type_from_spe_none_input(self, _mock_revit_modules):
        import rf_project_migration as mod

        assert mod._get_storage_type_from_spe(None) is None

    def test_get_expected_storage_type_uses_schema_map(self, _mock_revit_modules):
        import rf_project_migration as mod

        db_mod = sys.modules["Autodesk.Revit.DB"]

        assert (
            mod._get_expected_storage_type("RF_Tiles_ID") == db_mod.StorageType.String
        )
        assert mod._get_expected_storage_type("RF_Step_X") == db_mod.StorageType.Double
        assert mod._get_expected_storage_type("RF_Column") == db_mod.StorageType.Integer


# === Tests for dry-run purity (Fix: dry_run should not call ensure_schema_definitions) ===


class TestDryRunPurity:
    def test_family_dry_run_does_not_call_ensure_schema_definitions(
        self, _mock_revit_modules
    ):
        """dry_run=True must not create definitions in the shared param file."""
        import rf_family_migration as mod

        fam_doc = MagicMock()
        fam_doc.IsFamilyDocument = True

        param_def = MagicMock()
        param_def.Name = "RF_Column"
        param = MagicMock()
        param.Definition = param_def
        param.IsShared = True
        param.GUID = "WRONG-GUID"

        fam_mgr = MagicMock()
        fam_mgr.GetParameters.return_value = [param]
        fam_doc.FamilyManager = fam_mgr
        fam_doc.OwnerFamily.Name = "RF_Support"

        app = MagicMock()

        with patch.object(mod, "ensure_schema_definitions") as mock_ensure:
            result = mod.migrate_family_doc(
                fam_doc, app, dry_run=True, family_name_hint="RF_Support"
            )

        # ensure_schema_definitions should NOT have been called during dry-run
        mock_ensure.assert_not_called()
        assert result["dry_run"] is True


# === Tests for _restore_family_param_values return value ===


class TestRestoreFamilyParamValues:
    def test_returns_counts(self, _mock_revit_modules):
        import rf_family_migration as mod

        db_mod = sys.modules["Autodesk.Revit.DB"]

        fam_mgr = MagicMock()

        type1 = MagicMock()
        type1.Id.IntegerValue = 1
        type2 = MagicMock()
        type2.Id.IntegerValue = 2

        fam_mgr.Types = [type1, type2]
        fam_mgr.CurrentType = type1
        # First Set succeeds, second raises
        fam_mgr.Set = MagicMock(side_effect=[None, Exception("Set failed")])

        param = MagicMock()
        values = {1: 3.14, 2: 2.71}

        restored, failed = mod._restore_family_param_values(
            fam_mgr, param, db_mod.StorageType.Double, values
        )
        assert restored == 1
        assert failed == 1

    def test_empty_values_returns_zero(self, _mock_revit_modules):
        import rf_family_migration as mod

        restored, failed = mod._restore_family_param_values(
            MagicMock(), MagicMock(), None, {}
        )
        assert restored == 0
        assert failed == 0


class TestMigrateFamilyDocExecution:
    def test_adds_missing_params_even_when_safe_replace_fails(
        self, _mock_revit_modules
    ):
        import rf_family_migration as mod

        fam_doc = MagicMock()
        fam_doc.OwnerFamily.Name = "RF_Tile"
        app = MagicMock()

        replace_tx = MagicMock()
        add_tx = MagicMock()
        entered = []

        @contextmanager
        def _fake_context(_app):
            entered.append(True)
            yield "canonical"

        with patch.object(mod, "Transaction", side_effect=[replace_tx, add_tx]):
            with patch.object(
                mod, "use_canonical_shared_parameter_file", _fake_context
            ):
                with patch.object(
                    mod,
                    "_load_canonical_defs",
                    return_value={"RF_Tile_Size_X": (MagicMock(), True)},
                ):
                    with patch.object(mod, "_find_obsolete_params", return_value=[]):
                        with patch.object(
                            mod,
                            "_replace_mismatched_params_no_tx",
                            side_effect=lambda *args, **kwargs: args[4].append(
                                "RF_Mark: ReplaceParameter failed"
                            ),
                        ):
                            with patch.object(
                                mod,
                                "_add_missing_params_no_tx",
                                side_effect=lambda *args, **kwargs: args[3].append(
                                    "RF_Tile_Size_X"
                                ),
                            ):
                                result = mod.migrate_family_doc(
                                    fam_doc,
                                    app,
                                    project_doc=None,
                                    save_family=False,
                                    family_name_hint="RF_Tile",
                                    dry_run=False,
                                    allow_destructive=False,
                                )

        replace_tx.RollBack.assert_called_once()
        add_tx.Commit.assert_called_once()
        assert entered == [True]
        assert result["replaced"] == []
        assert result["added"] == ["RF_Tile_Size_X"]
        assert any("ReplaceParameter failed" in err for err in result["errors"])

    def test_non_dry_run_keeps_canonical_shared_param_file_active(
        self, _mock_revit_modules
    ):
        import rf_family_migration as mod

        fam_doc = MagicMock()
        fam_doc.OwnerFamily.Name = "RF_Tile"
        app = MagicMock()

        replace_tx = MagicMock()
        add_tx = MagicMock()
        entered = []

        @contextmanager
        def _fake_context(_app):
            entered.append(True)
            yield "canonical"

        with patch.object(mod, "Transaction", side_effect=[replace_tx, add_tx]):
            with patch.object(
                mod, "use_canonical_shared_parameter_file", _fake_context
            ):
                with patch.object(
                    mod,
                    "_load_canonical_defs",
                    return_value={"RF_Tile_Size_X": (MagicMock(), True)},
                ):
                    with patch.object(mod, "_find_obsolete_params", return_value=[]):
                        with patch.object(
                            mod,
                            "_replace_mismatched_params_no_tx",
                            return_value=None,
                        ):
                            with patch.object(
                                mod,
                                "_add_missing_params_no_tx",
                                return_value=None,
                            ):
                                mod.migrate_family_doc(
                                    fam_doc,
                                    app,
                                    project_doc=None,
                                    save_family=False,
                                    family_name_hint="RF_Tile",
                                    dry_run=False,
                                )

        assert entered == [True]
