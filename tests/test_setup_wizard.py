import json
import re

import pytest

from conftest import load_script
from test_keyword_suggest import MASTER

wz = load_script("setup_wizard")


@pytest.fixture
def paths(tmp_path, monkeypatch):
    sweep, board = tmp_path / "sweep_config.json", tmp_path / "boardsweep_config.json"
    monkeypatch.setattr(wz, "SWEEP_CONFIG", str(sweep))
    monkeypatch.setattr(wz, "BOARD_CONFIG", str(board))
    monkeypatch.setattr(wz.ks, "LOG_DIR", str(tmp_path / "no-logs"))
    monkeypatch.setattr(wz.ks, "find_master", lambda start=None: None)
    return tmp_path, sweep, board


def scripted(*answers):
    queue = list(answers)
    asked = []

    def ask(prompt):
        asked.append(prompt)
        return queue.pop(0) if queue else ""
    return ask, asked


def test_wizard_with_fact_base(paths):
    tmp_path, sweep, board = paths
    master = tmp_path / "master-cv-data.md"
    master.write_text(MASTER, encoding="utf-8")
    said = []
    # location, years, filter senior, directions (default = core), titles per direction, extra titles
    ask, _ = scripted("", "", "", "", "2", "ux researcher")
    assert wz.run(ask, said.append, str(master)) == 0
    cfg = json.loads(sweep.read_text(encoding="utf-8"))
    titles = [q[1] for q in cfg["queries"]]
    assert "ux researcher" in titles and len(titles) >= 3
    assert all(q[2] == "London, UK" for q in cfg["queries"])
    assert cfg["exclude_title_regex"] == wz.SENIOR_REGEX
    for track, pattern in cfg["title_relevance"].items():
        assert any(re.search(pattern, q[1], re.I) for q in cfg["queries"] if q[0] == track)
    b = json.loads(board.read_text(encoding="utf-8"))
    assert b["max_years"] == 3 and "london" in b["location_regex"] and re.search(b["want_title_regex"], "UX Researcher", re.I)
    text = "\n".join(said)
    assert "核心" in text and "设置完成" in text


def test_wizard_without_fact_base_uses_typed_titles(paths):
    tmp_path, sweep, board = paths
    ask, _ = scripted("Berlin, Germany", "5", "n", "data analyst, Data Analyst，bi analyst")
    assert wz.run(ask, lambda s: None) == 0
    cfg = json.loads(sweep.read_text(encoding="utf-8"))
    assert cfg["queries"] == [["MY", "data analyst", "Berlin, Germany"], ["MY", "bi analyst", "Berlin, Germany"]]
    assert cfg["exclude_title_regex"] == wz.JUNIOR_ONLY_REGEX
    b = json.loads(board.read_text(encoding="utf-8"))
    assert b["max_years"] == 5 and "germany" in b["location_regex"]


def test_wizard_keeps_tracked_jobs_and_backs_up(paths):
    tmp_path, sweep, board = paths
    sweep.write_text(json.dumps({"queries": [["X", "old", "UK"]], "tracked": [{"label": "keep me"}]}), encoding="utf-8")
    board.write_text(json.dumps({"ashby": ["acme"], "max_years": 2}), encoding="utf-8")
    ask, _ = scripted("y", "", "", "", "qa engineer")
    assert wz.run(ask, lambda s: None) == 0
    cfg = json.loads(sweep.read_text(encoding="utf-8"))
    assert cfg["tracked"] == [{"label": "keep me"}]
    assert json.loads(board.read_text(encoding="utf-8"))["ashby"] == ["acme"]
    assert (tmp_path / "sweep_config.json.bak").exists()


def test_wizard_declining_changes_nothing(paths):
    tmp_path, sweep, _ = paths
    sweep.write_text(json.dumps({"queries": [], "tracked": []}), encoding="utf-8")
    ask, _ = scripted("n")
    assert wz.run(ask, lambda s: None) == 0
    assert not (tmp_path / "sweep_config.json.bak").exists()


def test_wizard_replaces_unreadable_config(paths):
    tmp_path, sweep, _ = paths
    sweep.write_text("{ broken", encoding="utf-8")
    said = []
    ask, _ = scripted("", "", "", "product analyst")
    assert wz.run(ask, said.append) == 0
    assert "读不出来" in "\n".join(said)
    assert json.loads(sweep.read_text(encoding="utf-8"))["queries"][0][1] == "product analyst"


def test_wizard_with_no_titles_writes_nothing(paths):
    _, sweep, _ = paths
    ask, _ = scripted("", "", "", "")
    assert wz.run(ask, lambda s: None) == 1
    assert not sweep.exists()


def test_ask_int_retries_until_valid():
    said = []
    ask, _ = scripted("abc", "99", "4")
    assert wz.ask_int(ask, said.append, "q", 3, 0, 30) == 4
    assert len(said) == 2


def test_ask_yes_and_split():
    assert wz.ask_yes(lambda p: "", "q") is True
    assert wz.ask_yes(lambda p: "no", "q") is False
    assert wz.ask_yes(lambda p: "是", "q", default=False) is True
    assert wz.split_titles("A, b；c、 ,") == ["a", "b", "c"]


def test_location_regex():
    assert re.search(wz.location_regex("London, UK"), "Manchester, England, United Kingdom", re.I)
    assert re.search(wz.location_regex("Berlin, Germany"), "Remote - EMEA", re.I)
    assert wz.location_regex("") == "remote"


def test_choose_titles_prefers_titles_seen_in_scans():
    ks = wz.ks
    a = ks.Suggestion("a", "DA", "f", "mid", "core", 1.0, seen_in_logs=1)
    b = ks.Suggestion("b", "DA", "f", "entry", "core", 1.0, seen_in_logs=9)
    c = ks.Suggestion("c", "DA", "f", "entry", "core", 1.0, seen_in_logs=0)
    assert [s.title for s in wz.choose_titles({"titles": [a, c, b]}, 2)] == ["b", "a"]
    plain = [ks.Suggestion(t, "DA", "f", "entry", "core", 1.0) for t in "xyz"]
    assert [s.title for s in wz.choose_titles({"titles": plain}, 2)] == ["x", "y"]


def test_main_cancel(monkeypatch, capsys):
    def boom(*a, **k):
        raise KeyboardInterrupt
    monkeypatch.setattr(wz, "run", boom)
    assert wz.main([]) == 1
    assert "已取消" in capsys.readouterr().out
