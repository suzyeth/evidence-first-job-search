import json
import os
import re
import subprocess
import sys

import pytest

from conftest import SCRIPTS, load_script

fr = load_script("friendly")


def _explain(text):
    with pytest.raises(json.JSONDecodeError) as info:
        json.loads(text)
    return fr.explain_json_error("cfg.json", text, info.value)


def test_trailing_comma_before_bracket_names_the_line():
    msg = _explain('{\n  "queries": [\n    ["DA", "data analyst", "UK"],\n  ]\n}')
    assert "第 3 行" in msg and "逗号" in msg and "删掉" in msg
    assert "4 |" in msg  # the offending line is quoted


def test_trailing_comma_before_brace():
    assert "多了一个逗号" in _explain('{\n  "a": 1,\n}')


def test_missing_comma():
    assert "少了一个逗号" in _explain('{\n  "a": 1\n  "b": 2\n}')


def test_single_backslash():
    assert "反斜杠" in _explain('{"re": "\\b(a)"}'.replace("\\b", "\\q"))


def test_single_quotes():
    assert "单引号" in _explain("{'a': 1}")


def test_curly_quotes():
    assert "弯引号" in _explain('{“a”: 1}')


def test_unterminated_string():
    assert "没有配对" in _explain('{"a": "abc}')


def test_generic_fallback_and_english(monkeypatch):
    monkeypatch.setenv("JOBSEARCH_LANG", "en")
    msg = _explain("{\n  \"a\": tru\n}")
    assert "formatting error" in msg and "setup wizard" in msg


def test_load_json_friendly_raises_plain_message(tmp_path):
    bad = tmp_path / "c.json"
    bad.write_text('{\n "a": [1, 2,]\n}', encoding="utf-8")
    with pytest.raises(SystemExit) as info:
        fr.load_json_friendly(str(bad))
    assert "逗号" in str(info.value)
    good = tmp_path / "ok.json"
    good.write_text('\ufeff{"a": 1}', encoding="utf-8")  # a BOM from Notepad must not break loading
    assert fr.load_json_friendly(str(good)) == {"a": 1}


@pytest.mark.parametrize("title,phrase", [
    ("Live-Ops Designer", "live ops"),
    ("Senior Product Analyst", "product analyst"),
    ("Monetization Designer", "monetisation designer"),
    ("monetisation designer", "monetization designer"),
    ("AI Engineer", "ai"),
])
def test_words_to_regex_matches_variants(title, phrase):
    assert re.search(fr.words_to_regex([phrase]), title, re.I)


def test_words_to_regex_bounds_short_words_and_dedupes():
    pattern = fr.words_to_regex(["ai", "AI", "", "data analyst"])
    assert pattern.count("ai") == 1
    assert not re.search(pattern, "Maintenance Planner", re.I)
    assert fr.words_to_regex([]) == ""


def test_clean_path_strips_drag_and_drop_quotes():
    assert fr.clean_path('  "C:\\a b\\jd.txt" ') == "C:\\a b\\jd.txt"
    assert fr.clean_path("'/Users/x/jd.txt'") == "/Users/x/jd.txt"
    assert fr.clean_path("& 'C:\\a b\\cv.md'") == "C:\\a b\\cv.md"
    assert fr.clean_path("plain.txt") == "plain.txt"


def test_parse_choices():
    assert fr.parse_choices("1,3,5-7", 10) == [1, 3, 5, 6, 7]
    assert fr.parse_choices("7-5，2、2 x 99", 8) == [5, 6, 7, 2]
    assert fr.parse_choices("", 5) == []


def _run(script, *args, cwd=None):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    env.pop("JOBSEARCH_LANG", None)
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args], capture_output=True,
                          text=True, encoding="utf-8", env=env, cwd=cwd)


def test_sweep_explains_broken_config(tmp_path):
    cfg = tmp_path / "sweep_config.json"
    cfg.write_text('{\n  "queries": [\n    ["DA", "data analyst", "UK"],\n  ]\n}', encoding="utf-8")
    result = _run("sweep.py", "live", "--config", str(cfg))
    assert result.returncode != 0
    assert "多了一个逗号" in result.stderr


def test_sweep_missing_config_points_to_wizard(tmp_path):
    result = _run("sweep.py", "live", "--config", str(tmp_path / "nope.json"))
    assert "setup_wizard.py" in result.stderr


def test_no_argument_hints():
    jd = _run("jd_check.py")
    fc = _run("fact_check.py")
    assert jd.returncode == 2 and "jd_check.py JD.txt" in jd.stdout
    assert fc.returncode == 2 and "fact_check.py" in fc.stdout and "master-cv-data.md" in fc.stdout


def test_words_to_regex_starts_at_word_boundary():
    pattern = fr.words_to_regex(["mi analyst"])
    assert re.search(pattern, "MI Analyst", re.I)
    assert not re.search(pattern, "Academi Analyst", re.I)
