"""--lang en: every script's user-facing output is English, with no Chinese characters left over."""
import json
import os
import re
import sys
import types
import urllib.error

import pytest

from conftest import EXAMPLE_SWEEP_CONFIG, FIXTURES, SCRIPTS, load_script

sc = load_script("sponsor_check")
jd = load_script("jd_check")
fc = load_script("fact_check")
bs = load_script("boardsweep")
sw = load_script("sweep")

REGISTER = os.path.join(FIXTURES, "register_sample.csv")
CJK = re.compile(r"[　-〿一-鿿＀-￯]")


@pytest.fixture
def english(monkeypatch):
    monkeypatch.setenv("JOBSEARCH_LANG", "en")


def assert_no_chinese(text):
    leftovers = sorted({line for line in text.splitlines() if CJK.search(line)})
    assert not leftovers, "untranslated output:\n" + "\n".join(leftovers)


def test_leftover_detector_really_catches_chinese(capsys):
    with pytest.raises(AssertionError, match="untranslated"):
        assert_no_chinese("Boards reached 1 / 1\n名册查无")
    # and the default (Chinese) output would fail it, proving these tests exercise translated paths
    sc.main(["Zzyzx Unknown", "--register", REGISTER])
    with pytest.raises(AssertionError):
        assert_no_chinese(capsys.readouterr().out)


# ---------------------------------------------------------------- sponsor_check

def test_sponsor_check_english(english, tmp_path, capsys):
    jd_file = tmp_path / "jd.md"
    jd_file.write_text("We cannot sponsor visas.\n", encoding="utf-8")
    silent = tmp_path / "silent.md"
    silent.write_text("Great team.\n", encoding="utf-8")
    aliases = tmp_path / "a.json"
    aliases.write_text(json.dumps({"Bumble": "Badoo Limited"}), encoding="utf-8")
    sc.main(["Bumble", "Sports Charity Trust", "Nothing", "Extracovr", "Zzyzx Unknown", "--register", REGISTER,
             "--aliases", str(aliases), "--jd", str(jd_file), str(silent)])
    out = capsys.readouterr().out
    assert "On the register with a Skilled Worker route" in out and "Not on the register" in out
    assert "(alias → Badoo Limited)" in out and "rating A" in out and "❌ no sponsorship" in out
    assert_no_chinese(out)


def test_sponsor_watch_and_add_alias_english(english, tmp_path, capsys):
    state = tmp_path / "w.json"
    sc.main(["--watch", "Anthropic", "Nothing", "--register", REGISTER, "--state", str(state)])
    sc.main(["--watch", "Anthropic", "Bumble", "--register", REGISTER, "--state", str(state)])
    aliases = tmp_path / "a.json"
    aliases.write_text("{}", encoding="utf-8")
    sc.main(["--add-alias", "SCT", "Sports Charity Trust", "--register", REGISTER, "--aliases", str(aliases)])
    sc.main(["--add-alias", "X", "Badoo Limted", "--register", REGISTER, "--aliases", str(aliases)])
    out = capsys.readouterr().out
    assert "Baseline recorded" in out and "now watched" in out and "Added: SCT" in out and "Did you mean" in out
    assert_no_chinese(out)


def test_sponsor_tagger_labels_english(english):
    tagger = sc.SponsorTagger(sc.load_register(REGISTER), {"Bumble": "Badoo Limited"})
    assert tagger.tag("Bumble")["display"] == "sponsor✅(Badoo Limited · London)"
    assert tagger.tag("")["label"] == "sponsor?"


# ---------------------------------------------------------------- jd_check

def test_jd_check_english(english, tmp_path, capsys):
    bad = tmp_path / "bad.txt"
    bad.write_text("We're looking for a Lead Analyst with 6+ years of experience. Salary £30,000. "
                   "Unfortunately we are unable to offer visa sponsorship. SC clearance required.", encoding="utf-8")
    ok = tmp_path / "ok.txt"
    ok.write_text("A friendly team. Salary £38,000.", encoding="utf-8")
    jd.main([str(bad), str(ok), "--max-years", "2"])
    out = capsys.readouterr().out
    assert "JD❌no sponsorship" in out and "JD⚠️SC/DV clearance" in out and "senior in body" in out
    assert "needs 6+ yrs" in out and "£30k<£33.4k floor" in out and "£38k<£41.7k standard" in out
    assert_no_chinese(out)


# ---------------------------------------------------------------- fact_check

def test_fact_check_english(english, tmp_path, capsys):
    (tmp_path / "master-cv-data.md").write_text(
        "### Example Studio — Game Designer\n- 2024-10 ~ Present, London\nRan a power analysis on sample size.\n",
        encoding="utf-8")
    (tmp_path / "confidential-terms.txt").write_text("Falcon\n", encoding="utf-8")
    resume = tmp_path / "r.md"
    resume.write_text("### Senior Game Designer · Mystery Co · October 2023 - Present\n"
                      "**Skills:** Kubernetes, power-based sample estimates\n"
                      "Lifted ARPU by 55%. Passionate. [FILL]\n<!-- Falcon -->\n", encoding="utf-8")
    assert fc.main([str(resume)]) == 1
    out = capsys.readouterr().out
    assert "failed" in out and "number not in the fact base" in out and "inflated?" in out
    assert "inside an HTML comment" in out and "tenure stretched?" in out
    assert_no_chinese(out)


def test_fact_check_english_missing_files(english, tmp_path, capsys):
    resume = tmp_path / "r.md"
    resume.write_text("Shipped 3 games.", encoding="utf-8")
    assert fc.main([str(resume)]) == 2
    master = tmp_path / "m.md"
    master.write_text("Shipped 3 games.", encoding="utf-8")
    fc.main([str(resume), "--master", str(master)])
    captured = capsys.readouterr()
    assert "✅ pass" in captured.out
    assert_no_chinese(captured.out + captured.err)


# ---------------------------------------------------------------- boardsweep

def test_boardsweep_english(english, monkeypatch, tmp_path, capsys):
    with open(os.path.join(SCRIPTS, "boardsweep_config.example.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.update(ashby=[], greenhouse=["acme", "gone"], max_years=2)
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    board = {"jobs": [{"title": "Data Analyst", "location": {"name": "London"}, "absolute_url": "u",
                       "updated_at": None, "company_name": "Acme",
                       "content": "We're looking for a Senior Data Analyst, 5+ years of experience. "
                                  "Salary £30,000. We are unable to offer visa sponsorship."}]}
    monkeypatch.setattr(bs, "fetch_board", lambda kind, slug: board if slug == "acme" else None)
    monkeypatch.setattr(sc.SponsorTagger, "load", staticmethod(lambda **k: (_ for _ in ()).throw(OSError("x"))))
    bs.main(["--config", str(path)])
    out = capsys.readouterr().out
    assert "JD check: ❌no sponsorship 1" in out and "[JD:❌no sponsorship·senior in body·needs 5+ yrs" in out
    assert "Could not load the sponsor register" in out
    assert_no_chinese(out)


# ---------------------------------------------------------------- sweep

def test_sweep_live_and_add_english(english, monkeypatch, tmp_path, capsys):
    data = json.load(open(EXAMPLE_SWEEP_CONFIG, encoding="utf-8"))
    data["tracked"] = [{"label": "GH dead", "channel": "greenhouse", "args": ["gh", 2]},
                       {"label": "LI half", "channel": "linkedin", "args": "4100000002"}]
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps(data), encoding="utf-8")

    def fetch(url, timeout=25):
        if "boards/gh/jobs" in url:
            return json.dumps({"jobs": [{"id": 1}]})
        if "jobs/view/4100000002" in url:
            return "No longer accepting applications"
        raise urllib.error.URLError("offline")
    monkeypatch.setattr(sw, "fetch", fetch)
    monkeypatch.setattr(sw.time, "sleep", lambda s: None)
    monkeypatch.setattr(sw, "TRACKED", [("GH dead", "greenhouse", ("gh", 2)), ("LI half", "linkedin", "4100000002")])
    monkeypatch.setattr(sw, "_config_path", lambda: str(cfg))
    sw.main(["live", "--prune"])
    sw.main(["live"])
    sw.main(["add", "https://careers.example.com/1"])
    sw.main(["add", "https://boards.greenhouse.io/gh/jobs/5"])
    sw.main(["add", "https://boards.greenhouse.io/x/jobs/5"])
    sw.main(["add", "https://www.linkedin.com/jobs/view/4100000003/", "--force"])
    sw.main(["add"])
    out = capsys.readouterr().out
    assert "Removed 1 confirmed-dead jobs" in out and "only 1/2 dead markers" in out
    assert "Unrecognised link" in out and "job is closed" in out and "Couldn't confirm" in out
    assert "Usage: python sweep.py add" in out
    assert_no_chinese(out)


def test_sweep_discovery_english(english, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sw, "STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(sw, "LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setitem(sys.modules, "jobspy", types.ModuleType("jobspy"))
    rows = [{"title": "Product Analyst", "company": "Acme", "location": "London",
             "job_url": "https://www.linkedin.com/jobs/view/4100000001/", "site": "linkedin"},
            {"title": "Data Analyst", "company": "Harnham", "location": "London",
             "job_url": "https://www.linkedin.com/jobs/view/4100000002/", "site": "linkedin"}]

    def task(t, *a):
        if t[1] == "broken":
            return {"status": "error", "track": t[0], "term": t[1], "location": t[2], "site": t[3],
                    "attempts": 1, "seconds": 0.1, "rows": [], "error": "timeout"}
        return {"status": "ok", "track": t[0], "term": t[1], "location": t[2], "site": t[3],
                "attempts": 1, "seconds": 0.1, "rows": rows, "error": ""}
    monkeypatch.setattr(sw, "_run_task", task)

    class Tagger:
        def tag(self, company):
            return {"status": "SKILLED_WORKER", "label": "sponsor✅", "display": "sponsor✅(ACME · London)"}
    monkeypatch.setattr(sw, "_sponsor_tagger", lambda enabled: Tagger())
    sw.new(1, sites=("linkedin",), workers=1, queries=[("DA", "product analyst", "London"), ("DA", "broken", "London")])
    sw.main(["new", "1", "--plan", "--lang", "en"])
    out = capsys.readouterr().out
    assert "Sponsor: ✅ 1 · agency 1" in out and "[agency: ask before sending a CV]" in out
    assert "Coverage below 95%" in out and "Failed tasks" in out
    assert_no_chinese(out)
