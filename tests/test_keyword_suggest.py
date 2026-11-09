import json
import os

import pytest

from conftest import SCRIPTS, load_script

ks = load_script("keyword_suggest")

TAXONOMY = json.load(open(os.path.join(SCRIPTS, "role_taxonomy.json"), encoding="utf-8"))

# A fictional, deliberately data-heavy fact base.
MASTER = """# Master CV Data

## Work
### Analyst · Example Retail Ltd · 2023 — 2025
- Wrote SQL queries in BigQuery for weekly sales reporting.
- Built a Power BI dashboard tracking conversion funnel and retention by cohort.
- Reconciled KPI definitions across three reports before analysis.
- Ran an A/B test on checkout copy and checked significance.
- Automated the monthly report with a Python script (pandas).
- Presented findings to stakeholders in the weekly review.
- Analysed pricing and promotions, modelled revenue impact per price point.
- Wrote SQL to segment customers; dashboard in Tableau.
- More SQL work on retention cohorts; Python notebooks.
- ❌ Never built an LLM agent or used Claude (do not write).

## Skills
- Excel pivot tables
"""


def test_negative_lines_are_not_evidence():
    signals = ks.find_signals(MASTER, TAXONOMY)
    assert signals["sql"].found and signals["sql"].hits >= 3
    assert not signals["llm"].found  # only mentioned on a ❌ line
    assert not signals["agents"].found
    assert all("❌" not in line for line in signals["sql"].evidence)


def test_short_alternatives_need_word_boundaries():
    signals = ks.find_signals("- Built rapid prototypes for clients in a cinema chain.\n", TAXONOMY)
    assert not signals["web_backend"].found  # "rapid" must not count as "api"
    assert not signals["ci"].found           # "cinema" must not count as "ci"
    assert signals["customer"].found         # "clients"


def test_tiers_follow_the_evidence():
    out = ks.suggest(MASTER, TAXONOMY)
    by_family = {s.family: s.tier for s in out}
    assert by_family["产品 / 数据分析"] == "core"
    assert "应用 AI 工程" not in by_family or by_family["应用 AI 工程"] == "stretch"
    first = out[0]
    assert first.tier == "core" and first.evidence and first.matched
    # entry-level titles come first inside a family
    family = [s for s in out if s.family == "产品 / 数据分析"]
    assert family[0].level == "entry"


def test_empty_fact_base_gives_nothing_and_a_hint():
    assert ks.suggest("# nothing here\n", TAXONOMY) == []
    assert "master-cv-data.md" in ks.render([])


def test_already_searched_flag():
    out = ks.suggest(MASTER, TAXONOMY, {"queries": [["DA", "Data Analyst", "London"]]})
    assert next(s for s in out if s.title == "data analyst").already_searched


def test_count_in_logs(tmp_path):
    jobs = [{"title": "Data Analyst", "company": "A", "job_url": "u1"},
            {"title": "Senior Data Analyst", "company": "B", "job_url": "u2"},
            {"title": "Data Analyst", "company": "A", "job_url": "u1"},  # same job in a second scan
            {"title": "Barista", "company": "C", "job_url": "u3"}]
    (tmp_path / "discovery-scan-2026-01-01-000000.json").write_text(json.dumps({"jobs": jobs[:2]}), encoding="utf-8")
    (tmp_path / "discovery-scan-2026-01-02-000000.json").write_text(json.dumps({"jobs": jobs[2:]}), encoding="utf-8")
    (tmp_path / "discovery-scan-broken.json").write_text("{", encoding="utf-8")
    out = ks.suggest(MASTER, TAXONOMY)
    assert ks.count_in_logs(out, str(tmp_path)) == 3
    assert next(s for s in out if s.title == "data analyst").seen_in_logs == 2
    assert next(s for s in out if s.title == "crm analyst").seen_in_logs == 0
    text = ks.render(out, 3)
    assert "历史扫描见过 2 条" in text and "历史扫描未见过" in text and "3 份历史扫描" in text


def test_pick():
    out = ks.suggest(MASTER, TAXONOMY)
    assert {s.tier for s in ks.pick(out, "core")} == {"core"}
    assert ks.pick(out, "核心") == ks.pick(out, "core")
    assert ks.pick(out, "1,2") == out[:2]
    assert len(ks.pick(out, "all")) == len(out)


def test_apply_to_config_adds_queries_and_relevance(tmp_path):
    cfg = tmp_path / "sweep_config.json"
    cfg.write_text(json.dumps({"queries": [["DA", "data analyst", "Leeds, UK"]], "tracked": [{"x": 1}],
                               "title_relevance": {"DA": "data analyst"}}), encoding="utf-8")
    out = ks.suggest(MASTER, TAXONOMY)
    picks = [s for s in out if s.title in ("data analyst", "insight analyst", "pricing analyst")]
    added, backup = ks.apply_to_config(str(cfg), picks)
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert added == 2 and backup and os.path.exists(backup)
    assert ["DA", "insight analyst", "Leeds, UK"] in data["queries"]  # location reused from the config
    assert data["tracked"] == [{"x": 1}]
    assert "insight" in data["title_relevance"]["DA"]
    added_again, _ = ks.apply_to_config(str(cfg), picks)
    assert added_again == 0


def test_apply_creates_config_when_missing(tmp_path):
    cfg = tmp_path / "sweep_config.json"
    out = ks.suggest(MASTER, TAXONOMY)
    added, backup = ks.apply_to_config(str(cfg), out[:1], "Berlin, Germany")
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert added == 1 and backup is None
    assert data["queries"] == [[out[0].track, out[0].title, "Berlin, Germany"]]
    assert data["tracked"] == []


def _write_master(tmp_path):
    path = tmp_path / "master-cv-data.md"
    path.write_text(MASTER, encoding="utf-8")
    return path


def test_main_prints_and_json(tmp_path, capsys):
    master = _write_master(tmp_path)
    assert ks.main(["--master", str(master), "--config", str(tmp_path / "none.json")]) == 0
    text = capsys.readouterr().out
    assert "【核心】" in text and "出处:" in text and "--apply" in text
    assert ks.main(["--master", str(master), "--json", "--config", str(tmp_path / "none.json")]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data[0]["tier"] == "core"


def test_main_english(tmp_path, capsys):
    master = _write_master(tmp_path)
    ks.main(["--master", str(master), "--lang", "en", "--config", str(tmp_path / "none.json"),
             "--from-logs", "--log-dir", str(tmp_path)])
    text = capsys.readouterr().out
    assert "[Core]" in text and "Product & data analytics" in text and "never seen in past scans" in text


def test_main_apply(tmp_path, capsys):
    master = _write_master(tmp_path)
    cfg = tmp_path / "sweep_config.json"
    assert ks.main(["--master", str(master), "--config", str(cfg), "--apply", "1-2", "--location", "York, UK"]) == 0
    assert "新增 2 条" in capsys.readouterr().out
    assert ks.main(["--master", str(master), "--config", str(cfg), "--apply", "999"]) == 1


def test_main_without_master(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ks, "find_master", lambda start=None: None)
    assert ks.main(["--config", str(tmp_path / "x.json")]) == 1
    assert "templates/master-cv-data.md" in capsys.readouterr().err


def test_find_master_looks_upwards_and_in_shared(tmp_path):
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared" / "master-cv-data.md").write_text("x", encoding="utf-8")
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    assert ks.find_master(str(deep)).endswith(os.path.join("shared", "master-cv-data.md"))


def test_taxonomy_is_well_formed():
    signals = set(TAXONOMY["signals"])
    for fam in TAXONOMY["families"]:
        assert set(fam["needs"]) <= signals, fam["id"]
        assert set(fam["key"]) <= set(fam["needs"]), fam["id"]
        assert fam["titles"] and all(t["t"] == t["t"].lower() for t in fam["titles"])
