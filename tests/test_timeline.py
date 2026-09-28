"""
اختبارات titan.timeline — الذاكرة المعمارية لـ Titan

تغطي:
- ArchiveEntry: النموذج، الحقول، الثبات
- entries(): كل الإدخالات مرتّبة
- entry(): البحث برقم
- by_status(): التصفية حسب الحالة
- latest(): آخر n إدخال
- rules(): استخراج القواعد
- اتساق البيانات الداخلية
"""

import pytest
from dataclasses import fields, FrozenInstanceError

from titan.timeline import entries, entry, by_status, latest, rules, ArchiveEntry
from titan.timeline.models import ArchiveEntry as ArchiveEntryDirect
from titan.timeline._data import ENTRIES


# ===========================================================================
# ArchiveEntry — النموذج
# ===========================================================================

class TestArchiveEntryModel:
    def _make(self, **overrides):
        base = dict(
            number="001",
            title="Example",
            status="Accepted",
            rule={"en": "Some rule.", "ar": "قاعدة ما."},
            summary="Some summary.",
            tags=("example",),
            date=None,
            path="docs/decisions/001-example.md",
        )
        base.update(overrides)
        return ArchiveEntry(**base)

    def test_is_frozen_dataclass(self):
        assert hasattr(ArchiveEntry, "__dataclass_fields__")
        e = self._make()
        with pytest.raises(FrozenInstanceError):
            e.title = "Other"  # type: ignore[misc]

    def test_required_fields(self):
        field_names = {f.name for f in fields(ArchiveEntry)}
        assert field_names == {
            "number",
            "title",
            "status",
            "rule",
            "summary",
            "tags",
            "date",
            "path",
        }

    def test_tags_is_tuple(self):
        e = self._make(tags=("a", "b"))
        assert isinstance(e.tags, tuple)

    def test_date_can_be_none(self):
        e = self._make(date=None)
        assert e.date is None

    def test_date_can_be_set(self):
        e = self._make(date="2026-07-10")
        assert e.date == "2026-07-10"

    def test_importable_from_models_directly(self):
        assert ArchiveEntryDirect is ArchiveEntry


# ===========================================================================
# entries()
# ===========================================================================

class TestEntries:
    def test_returns_list(self):
        result = entries()
        assert isinstance(result, list)
        assert all(isinstance(e, ArchiveEntry) for e in result)

    def test_matches_data_source_length(self):
        assert len(entries()) == len(ENTRIES)

    def test_sorted_by_number(self):
        numbers = [e.number for e in entries()]
        assert numbers == sorted(numbers)

    def test_first_entry_is_001(self):
        assert entries()[0].number == "001"

    def test_returns_new_list_each_call(self):
        assert entries() is not entries()


# ===========================================================================
# entry()
# ===========================================================================

class TestEntry:
    def test_finds_existing_entry(self):
        e = entry("003")
        assert e is not None
        assert e.number == "003"
        assert e.title == "Capabilities"

    def test_returns_none_for_missing_number(self):
        assert entry("999") is None

    def test_returns_none_for_empty_string(self):
        assert entry("") is None


# ===========================================================================
# by_status()
# ===========================================================================

class TestByStatus:
    def test_rejected_contains_keyboard_builder(self):
        rejected = by_status("Rejected")
        assert any(e.number == "001" for e in rejected)
        assert all(e.status == "Rejected" for e in rejected)

    def test_accepted_excludes_rejected(self):
        accepted = by_status("Accepted")
        assert all(e.status == "Accepted" for e in accepted)
        assert not any(e.number == "001" for e in accepted)

    def test_unknown_status_returns_empty_list(self):
        assert by_status("Deferred") == []
        assert by_status("nonexistent") == []

    def test_sorted_by_number(self):
        accepted = by_status("Accepted")
        numbers = [e.number for e in accepted]
        assert numbers == sorted(numbers)


# ===========================================================================
# latest()
# ===========================================================================

class TestLatest:
    def test_returns_most_recent_first(self):
        result = latest(2)
        assert result[0].number == ENTRIES[-1].number
        assert result[1].number == ENTRIES[-2].number

    def test_respects_n(self):
        assert len(latest(3)) == 3

    def test_zero_returns_empty(self):
        assert latest(0) == []

    def test_n_larger_than_total_returns_all(self):
        assert len(latest(1000)) == len(ENTRIES)


# ===========================================================================
# rules()
# ===========================================================================

class TestRules:
    def test_returns_list_of_rule_dicts(self):
        result = rules()
        assert isinstance(result, list)
        assert all(isinstance(r, dict) for r in result)

    def test_matches_entries_count(self):
        assert len(rules()) == len(entries())

    def test_order_matches_entries_order(self):
        assert rules() == [e.rule for e in entries()]

    def test_all_rules_have_en_and_ar_keys(self):
        """كل rule dict يحتوي على "en" و"ar" — اللغتان المدعومتان في v1."""
        for r in rules():
            assert "en" in r, f"rule dict missing 'en' key: {r}"
            assert "ar" in r, f"rule dict missing 'ar' key: {r}"

    def test_no_empty_rule_values(self):
        for r in rules():
            assert all(v.strip() for v in r.values())


# ===========================================================================
# اتساق البيانات الداخلية
# ===========================================================================

class TestDataConsistency:
    def test_no_duplicate_numbers(self):
        numbers = [e.number for e in ENTRIES]
        assert len(numbers) == len(set(numbers))

    def test_all_numbers_are_three_digits(self):
        assert all(len(e.number) == 3 and e.number.isdigit() for e in ENTRIES)

    def test_all_statuses_are_known(self):
        known = {"Accepted", "Rejected", "Deferred"}
        assert all(e.status in known for e in ENTRIES)

    def test_all_paths_point_to_decisions_dir(self):
        assert all(e.path.startswith("docs/decisions/") for e in ENTRIES)

    def test_all_paths_exist_on_disk(self):
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        for e in ENTRIES:
            assert (root / e.path).exists(), f"Missing file: {e.path}"

    def test_all_official_adrs_are_in_timeline(self):
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        official = sorted(
            path.relative_to(root).as_posix()
            for path in (root / "docs" / "decisions").glob("[0-9][0-9][0-9]-*.md")
        )
        expected = [
            (path.rsplit("/", 1)[-1].split("-", 1)[0], path)
            for path in official
        ]
        actual = [(entry.number, entry.path) for entry in ENTRIES]

        assert actual == expected
        assert [number for number, _ in actual] == sorted(
            number for number, _ in actual
        )

    def test_all_tags_are_non_empty_tuples(self):
        assert all(isinstance(e.tags, tuple) and len(e.tags) > 0 for e in ENTRIES)


# ===========================================================================
# __all__
# ===========================================================================

class TestPublicAPI:
    def test_expected_exports(self):
        import titan.timeline as timeline_module

        assert set(timeline_module.__all__) == {
            "ArchiveEntry",
            "entries",
            "entry",
            "by_status",
            "latest",
            "rules",
        }

    def test_not_exposed_at_root(self):
        import titan

        assert not hasattr(titan, "ArchiveEntry")
