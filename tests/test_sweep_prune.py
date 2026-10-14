"""sweep.py live --prune: drop confirmed-dead jobs from sweep_config.json, keep everything uncertain."""
import json
import urllib.error

import pytest

from conftest import EXAMPLE_SWEEP_CONFIG, load_script

sw = load_script("sweep")

LI_DEAD = "<html>No longer accepting applications <div class='closed-job'></div></html>"
LI_HALF = "<html>No longer accepting applications</html>"

ENTRIES = [
    {"label": "GH alive", "channel": "greenhouse", "args": ["gh", 1]},
    {"label": "GH dead", "channel": "greenhouse", "args": ["gh", 2]},
    {"label": "LI dead", "channel": "linkedin", "args": "4100000001"},
    {"label": "LI unsure", "channel": "linkedin", "args": "4100000002"},
    {"label": "Network error", "channel": "lever", "args": ["down", "p1"]},
]


@pytest.fixture
def env(monkeypatch, tmp_path):
    with open(EXAMPLE_SWEEP_CONFIG, encoding="utf-8") as f:
        data = json.load(f)
    data["tracked"] = ENTRIES
    path = tmp_path / "sweep_config.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def fetch(url, timeout=25):
        if "boards/gh/jobs" in url:
            return json.dumps({"jobs": [{"id": 1}]})
        if "jobs/view/4100000001" in url:
            return LI_DEAD
        if "jobs/view/4100000002" in url:
            return LI_HALF
        raise urllib.error.URLError("offline")
    monkeypatch.setattr(sw, "fetch", fetch)
    monkeypatch.setattr(sw.time, "sleep", lambda s: None)
    monkeypatch.setattr(sw, "TRACKED", [(e["label"], e["channel"],
                                         tuple(e["args"]) if isinstance(e["args"], list) else e["args"])
                                        for e in ENTRIES])
    monkeypatch.setattr(sw, "_config_path", lambda: str(path))
    return path


def labels(path):
    return [e["label"] for e in json.loads(path.read_text(encoding="utf-8"))["tracked"]]


def test_prune_removes_only_confirmed_dead(env, capsys):
    sw.live(prune=True)
    assert labels(env) == ["GH alive", "LI unsure", "Network error"]
    out = capsys.readouterr().out
    assert "已从 tracked 摘掉 2 条" in out and "GH dead" in out and "LI dead" in out


def test_prune_keeps_other_config_keys(env):
    before = json.loads(env.read_text(encoding="utf-8"))
    sw.live(prune=True)
    after = json.loads(env.read_text(encoding="utf-8"))
    assert {k: v for k, v in after.items() if k != "tracked"} == {k: v for k, v in before.items() if k != "tracked"}


def test_without_prune_config_is_untouched(env, capsys):
    before = env.read_text(encoding="utf-8")
    sw.live()
    assert env.read_text(encoding="utf-8") == before
    assert "--prune" in capsys.readouterr().out   # hint that pruning is available


def test_prune_with_nothing_dead(env, monkeypatch, capsys):
    monkeypatch.setattr(sw, "TRACKED", [("GH alive", "greenhouse", ("gh", 1))])
    sw.live(prune=True)
    assert len(labels(env)) == len(ENTRIES)
    assert "没有需要摘掉的" in capsys.readouterr().out


def test_cli_passes_prune_flag(monkeypatch):
    seen = {}
    monkeypatch.setattr(sw, "live", lambda log=False, prune=False: seen.update(log=log, prune=prune))
    sw.main(["live", "--log", "--prune"])
    assert seen == {"log": True, "prune": True}
