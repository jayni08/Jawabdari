"""Every language must have the same keys and the same {placeholders}."""

import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from i18n import LABELS, t  # noqa: E402


def placeholders(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_all_languages_have_same_keys():
    for lang in ("hi", "gu"):
        assert set(LABELS[lang]) == set(LABELS["en"]), lang


def test_placeholders_match():
    for key, text in LABELS["en"].items():
        for lang in ("hi", "gu"):
            assert placeholders(LABELS[lang][key]) == placeholders(text), (lang, key)


def test_fallbacks():
    assert t("title", "xx") == "Report a problem"   # unknown language -> English
    assert t("no_such_key", "gu") == "no_such_key"  # unknown key -> key itself
    assert "D-0001" in t("city_repair", "gu", dlp_end="2026-01-01", defect_id="D-0001")
