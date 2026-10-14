"""--lang en / JOBSEARCH_LANG=en switches every script's output to English; Chinese stays the default."""
import pytest

from conftest import load_script

i18n = load_script("i18n")


@pytest.fixture(autouse=True)
def _reset_lang(monkeypatch):
    monkeypatch.delenv(i18n.LANG_ENV, raising=False)


def test_default_is_chinese():
    assert i18n.lang() == "zh" and i18n.tr("中文", "English") == "中文"


def test_env_var_switches_to_english(monkeypatch):
    monkeypatch.setenv(i18n.LANG_ENV, "en")
    assert i18n.tr("中文", "English") == "English"


@pytest.mark.parametrize("argv", [["a", "--lang", "en", "b"], ["a", "--lang=en", "b"]])
def test_apply_lang_arg_consumes_flag(argv):
    assert i18n.apply_lang_arg(argv) == ["a", "b"]
    assert i18n.lang() == "en"


def test_apply_lang_arg_rejects_unknown():
    with pytest.raises(SystemExit, match="--lang"):
        i18n.apply_lang_arg(["--lang", "fr"])


def test_apply_lang_arg_without_flag_keeps_default():
    assert i18n.apply_lang_arg(["x"]) == ["x"] and i18n.lang() == "zh"
