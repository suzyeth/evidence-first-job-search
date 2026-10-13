"""Network / subprocess / CLI paths of sweep.py, with every external call faked."""
import json
import os
import runpy
import subprocess
import sys
import types
import urllib.error

import pytest

from conftest import EXAMPLE_SWEEP_CONFIG, SCRIPTS, load_script

sw = load_script("sweep")

LI_DEAD = "<html>No longer accepting applications <div class='closed-job'></div></html>"


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(sw.time, "sleep", lambda s: None)


def fake_fetch_factory(pages):
    def fake_fetch(url, timeout=25):
        for key, value in pages.items():
            if key in url:
                if isinstance(value, Exception):
                    raise value
                return value if isinstance(value, str) else json.dumps(value)
        raise urllib.error.HTTPError(url, 404, "not found", None, None)
    return fake_fetch


# ---------------------------------------------------------------- live()

def test_live_reports_every_channel(monkeypatch, tmp_path, capsys, no_sleep):
    pages = {
        "boards-api.greenhouse.io/v1/boards/gh": {"jobs": [{"id": 1}]},
        "posting-api/job-board/ash": {"jobs": [{"id": "u1", "title": "Data Analyst", "isListed": True}]},
        "pin.pinpointhq.com": {"data": [{"id": 7}]},
        "tt.teamtailor.com/jobs/ok-slug": "<html>job</html>",
        "accounts/wk": {"jobs": [{"shortcode": "AB12"}]},
        "hitmarker.net/jobs/game-job": "<html>job</html>",
        "bb.bamboohr.com": {"result": [{"id": 5}]},
        "api.lever.co/v0/postings/lv": [{"id": "p1"}],
        "jobs/view/111": "<html>open</html>",
        "jobs/view/222": LI_DEAD,
        "jobs/view/333": "<html>No longer accepting applications</html>",
    }
    monkeypatch.setattr(sw, "fetch", fake_fetch_factory(pages))
    monkeypatch.setattr(sw, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(sw, "TRACKED", [
        ("GH ok", "greenhouse", ("gh", 1)),
        ("GH gone", "greenhouse", ("gh", 2)),
        ("Ashby title", "ashby_title", ("ash", "Data Analyst")),
        ("Ashby id", "ashby_id", ("ash", "u1")),
        ("Pinpoint", "pinpoint", ("pin", 7)),
        ("Teamtailor", "teamtailor", ("tt", "ok-slug")),
        ("Teamtailor gone", "teamtailor", ("tt", "gone-slug")),
        ("Workable", "workable", ("wk", "AB12")),
        ("Hitmarker", "hitmarker", "game-job"),
        ("Bamboo", "bamboohr", ("bb", 5)),
        ("Lever", "lever", ("lv", "p1")),
        ("LI open", "linkedin", "111"),
        ("LI dead", "linkedin", "222"),
        ("LI half", "linkedin", "333"),
        ("Bad channel", "carrier-pigeon", "x"),
    ])
    sw.live(log=True)
    out = capsys.readouterr().out
    for label in ("GH ok", "Ashby title", "Ashby id", "Pinpoint", "Teamtailor", "Workable",
                  "Hitmarker", "Bamboo", "Lever", "LI open"):
        assert f"OK   {label}" in out
    assert "DEAD GH gone" in out
    assert "ERR  Teamtailor gone: HTTPError" in out
    assert "DEAD LI dead(双标记坐实)" in out
    assert "DEAD? LI half" in out
    assert "ERR  Bad channel: ValueError" in out
    assert "Liveness" in (tmp_path / "live-log.md").read_text(encoding="utf-8")


def test_greenhouse_falls_back_to_eu_node(monkeypatch):
    pages = {"boards-api.greenhouse.io": urllib.error.URLError("down"),
             "boards-api.eu.greenhouse.io/v1/boards/gh": {"jobs": [{"id": 9}]}}
    monkeypatch.setattr(sw, "fetch", fake_fetch_factory(pages))
    assert sw._check("greenhouse", ("gh", 9)) is True


def test_live_with_empty_queue(monkeypatch, capsys):
    monkeypatch.setattr(sw, "TRACKED", [])
    sw.live()
    assert "tracked 为空" in capsys.readouterr().out


# ---------------------------------------------------------------- _query_worker / _run_task

class FakeFrame:
    def __init__(self, rows):
        self.rows = rows

    def iterrows(self):
        for i, row in enumerate(self.rows):
            yield i, row


def test_query_worker_writes_rows(monkeypatch, tmp_path):
    fake = types.ModuleType("jobspy")
    fake.scrape_jobs = lambda **kw: FakeFrame([{"title": "Data Analyst", "company": "Acme", "min_amount": "nan"}])
    monkeypatch.setitem(sys.modules, "jobspy", fake)
    out = tmp_path / "rows.json"
    sw._query_worker("linkedin", "data analyst", "London, UK", 24, str(out))
    rows = json.loads(out.read_text(encoding="utf-8"))
    assert rows[0]["title"] == "Data Analyst" and rows[0]["min_amount"] == ""


def fake_run_factory(behaviour):
    """behaviour(attempt) -> ("ok", rows, log) | ("fail", stderr) | ("timeout",)"""
    calls = {"n": 0}

    def fake_run(cmd, **kwargs):
        calls["n"] += 1
        result = behaviour(calls["n"])
        if result[0] == "timeout":
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))
        if result[0] == "fail":
            return subprocess.CompletedProcess(cmd, 1, "", result[1])
        with open(cmd[-1], "w", encoding="utf-8") as f:
            json.dump(result[1], f)
        return subprocess.CompletedProcess(cmd, 0, result[2], "")
    return fake_run, calls


def test_run_task_success(monkeypatch):
    fake_run, _ = fake_run_factory(lambda n: ("ok", [{"title": "A"}], ""))
    monkeypatch.setattr(sw.subprocess, "run", fake_run)
    r = sw._run_task(("DA", "analyst", "London", "linkedin"), 24, 5, 1)
    assert r["status"] == "ok" and r["rows"] == [{"title": "A"}] and r["attempts"] == 1


def test_run_task_retries_then_reports_error(monkeypatch):
    fake_run, calls = fake_run_factory(lambda n: ("fail", "boom\nlast line"))
    monkeypatch.setattr(sw.subprocess, "run", fake_run)
    r = sw._run_task(("DA", "analyst", "London", "linkedin"), 24, 5, 1)
    assert r["status"] == "error" and r["error"] == "last line" and calls["n"] == 2


def test_run_task_treats_empty_result_with_provider_error_as_failure(monkeypatch):
    fake_run, _ = fake_run_factory(lambda n: ("ok", [], "ERROR - JobSpy: blocked"))
    monkeypatch.setattr(sw.subprocess, "run", fake_run)
    r = sw._run_task(("DA", "analyst", "London", "indeed"), 24, 5, 0)
    assert r["status"] == "error" and "JobSpy" in r["error"]


def test_run_task_timeout(monkeypatch):
    fake_run, _ = fake_run_factory(lambda n: ("timeout",))
    monkeypatch.setattr(sw.subprocess, "run", fake_run)
    r = sw._run_task(("DA", "analyst", "London", "linkedin"), 24, 5, 0)
    assert r["error"] == "timeout>5s"


def test_run_task_unexpected_exception(monkeypatch):
    def explode(cmd, **kwargs):
        raise OSError("no python")
    monkeypatch.setattr(sw.subprocess, "run", explode)
    r = sw._run_task(("DA", "analyst", "London", "linkedin"), 24, 5, 0)
    assert r["error"].startswith("OSError")


# ---------------------------------------------------------------- new()

ROWS = {
    "product analyst": [
        {"title": "Product Analyst", "company": "Acme", "location": "London, UK",
         "job_url": "https://www.linkedin.com/jobs/view/4000000001/", "site": "linkedin"},
        {"title": "Senior Product Analyst", "company": "Acme", "location": "London, UK",
         "job_url": "https://www.linkedin.com/jobs/view/4000000002/", "site": "linkedin"},
        {"title": "Warehouse Operative", "company": "Boxes", "location": "London, UK",
         "job_url": "https://www.linkedin.com/jobs/view/4000000003/", "site": "linkedin"},
        {"title": "Data Analyst", "company": "Harnham", "location": "London, UK",
         "job_url": "https://www.linkedin.com/jobs/view/4000000004/", "site": "linkedin"},
        {"title": "", "company": "", "location": "", "job_url": "", "site": "linkedin"},
    ],
}


@pytest.fixture
def discovery_env(monkeypatch, tmp_path):
    monkeypatch.setattr(sw, "STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(sw, "LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setitem(sys.modules, "jobspy", types.ModuleType("jobspy"))
    calls = []

    def fake_task(task, hours, timeout, retries):
        calls.append(task)
        track, term, loc, site = task
        if term == "broken":
            return {"status": "error", "track": track, "term": term, "location": loc, "site": site,
                    "attempts": 2, "seconds": 0.1, "rows": [], "error": "timeout>90s"}
        return {"status": "ok", "track": track, "term": term, "location": loc, "site": site,
                "attempts": 1, "seconds": 0.1, "rows": ROWS.get(term, []), "error": ""}
    monkeypatch.setattr(sw, "_run_task", fake_task)
    return tmp_path, calls


def test_new_merges_filters_and_logs(discovery_env, capsys):
    tmp, calls = discovery_env
    sw.new(3, sites=("linkedin",), workers=1, queries=[("DA", "product analyst", "London, UK")])
    out = capsys.readouterr().out
    assert "覆盖率: 1/1 = 100.0%" in out
    assert "Product Analyst" in out and "[NEW|linkedin]" in out
    assert "Senior Product Analyst" not in out.split("### [DA]")[1]   # hard-filtered
    assert "中介" in out                                               # Harnham tagged as agency
    logs = list((tmp / "logs").glob("discovery-scan-*.json"))
    report = json.loads(logs[0].read_text(encoding="utf-8"))
    assert report["filtered_jobs"] == 1 and report["contextual_jobs"] == 1
    history = json.loads((tmp / "state" / "discovery-history.json").read_text(encoding="utf-8"))
    assert len(history) == 4


def test_new_resume_skips_completed_tasks_and_marks_seen(discovery_env, capsys):
    tmp, calls = discovery_env
    q = [("DA", "product analyst", "London, UK")]
    sw.new(3, sites=("linkedin",), workers=1, queries=q)
    sw.new(3, sites=("linkedin",), workers=1, queries=q, resume=True)
    out = capsys.readouterr().out
    assert len(calls) == 1                      # second run served from checkpoint
    assert "[SEEN|linkedin]" in out


def test_new_low_coverage_warns(discovery_env, capsys):
    sw.new(3, sites=("linkedin",), workers=1,
           queries=[("DA", "product analyst", "London, UK"), ("DA", "broken", "London, UK")])
    out = capsys.readouterr().out
    assert "未完成任务" in out and "低于 95%" in out


def test_new_plan_only_does_not_run(discovery_env, capsys):
    tmp, calls = discovery_env
    sw.new(3, plan=True, queries=[("DA", "product analyst", "London, UK")])
    assert calls == [] and "独立任务: 2" in capsys.readouterr().out


def test_new_without_jobspy_stops_before_spawning(monkeypatch, discovery_env):
    monkeypatch.setitem(sys.modules, "jobspy", None)   # import jobspy -> ImportError
    with pytest.raises(SystemExit) as exc:
        sw.new(3, queries=[("DA", "product analyst", "London, UK")])
    assert "python-jobspy" in str(exc.value)


def test_new_truncates_long_track_lists(discovery_env, monkeypatch, capsys):
    many = [{"title": f"Data Analyst {i}", "company": f"Co{i}", "location": "London",
             "job_url": f"https://www.linkedin.com/jobs/view/40000001{i:02d}/", "site": "linkedin"}
            for i in range(25)]
    monkeypatch.setitem(ROWS, "data analyst", many)
    sw.new(1, sites=("linkedin",), workers=1, queries=[("DA", "data analyst", "London")])
    assert "另 5 条见 JSON 日志" in capsys.readouterr().out


# ---------------------------------------------------------------- config + CLI

def test_load_config_missing_and_invalid(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["sweep.py", "--config", str(tmp_path / "nope.json")])
    with pytest.raises(SystemExit, match="找不到配置文件"):
        sw._load_config()
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["sweep.py", "--config", str(bad)])
    with pytest.raises(SystemExit, match="JSON 格式错误"):
        sw._load_config()


def test_config_path_defaults_next_to_script(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["sweep.py"])
    assert sw._config_path().endswith(os.path.join("scripts", "sweep_config.json"))


def run_cli(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["sweep.py", *args, "--config", EXAMPLE_SWEEP_CONFIG])
    runpy.run_path(os.path.join(SCRIPTS, "sweep.py"), run_name="__main__")


def test_cli_plan(monkeypatch, capsys):
    run_cli(monkeypatch, "linkedin", "1", "--tracks", "AI", "--plan", "--timeout", "30", "--retries", "0")
    assert "AI=2" in capsys.readouterr().out


def test_cli_unknown_command_prints_help(monkeypatch, capsys):
    run_cli(monkeypatch, "help-me")
    assert "用法" in capsys.readouterr().out
