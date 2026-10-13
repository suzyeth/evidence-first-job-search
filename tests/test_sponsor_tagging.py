"""Sponsor-status tags on discovery output (sweep.py new / boardsweep.py)."""
import json
import os
import sys
import types

import pytest

from conftest import FIXTURES, SCRIPTS, load_script

sc = load_script("sponsor_check")
sw = load_script("sweep")
bs = load_script("boardsweep")

REGISTER = os.path.join(FIXTURES, "register_sample.csv")


# ---------------------------------------------------------------- SponsorTagger

@pytest.fixture(scope="module")
def tagger():
    return sc.SponsorTagger(sc.load_register(REGISTER), {"Bumble": "Badoo Limited"})


def test_tag_labels(tagger):
    assert tagger.tag("Bumble")["label"] == "担保✅"
    assert tagger.tag("Bumble")["legal"] == "Badoo Limited"
    assert tagger.tag("Bumble")["town"] == "London"
    assert tagger.tag("Bumble")["display"] == "担保✅(Badoo Limited · London)"
    assert tagger.tag("Nothing")["display"] == "担保❓"          # no legal name shown for unresolved cases
    assert tagger.tag("Nothing")["legal"] == ""
    assert tagger.tag("Nothing")["label"] == "担保❓"
    assert tagger.tag("Sports Charity Trust")["label"] == "担保⚠️"
    assert tagger.tag("Totally Unknown Widgets")["label"] == "担保❌"


def test_tag_skips_fuzzy_matching(tagger):
    # batch tagging must stay fast: no difflib pass, so a typo is simply not found
    assert tagger.tag("Extracovr")["status"] == "NOT_FOUND"


def test_tag_caches_by_normalised_name(tagger, monkeypatch):
    tagger.tag("Anthropic Ltd")
    monkeypatch.setattr(sc, "lookup", lambda *a, **k: pytest.fail("should be cached"))
    assert tagger.tag("ANTHROPIC LIMITED")["status"] == "SKILLED_WORKER"


def test_tag_blank_company(tagger):
    assert tagger.tag("")["label"] == "担保?"


def test_tagger_load_uses_register_and_aliases(tmp_path):
    aliases = tmp_path / "a.json"
    aliases.write_text(json.dumps({"Zego": "EXTRACOVER LIMITED"}), encoding="utf-8")
    t = sc.SponsorTagger.load(register_path=REGISTER, aliases_path=str(aliases))
    assert t.tag("Zego")["legal"] == "EXTRACOVER LIMITED"


# ---------------------------------------------------------------- sweep.py new()

class FakeTagger:
    def __init__(self):
        self.seen = []

    def tag(self, company):
        self.seen.append(company)
        return {"status": "SKILLED_WORKER", "legal": company.upper(), "town": "London", "label": "担保✅",
                "display": f"担保✅({company.upper()} · London)"}


@pytest.fixture
def discovery(monkeypatch, tmp_path):
    monkeypatch.setattr(sw, "STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(sw, "LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setitem(sys.modules, "jobspy", types.ModuleType("jobspy"))
    rows = [
        {"title": "Product Analyst", "company": "Acme", "location": "London",
         "job_url": "https://www.linkedin.com/jobs/view/4100000001/", "site": "linkedin"},
        {"title": "Data Analyst", "company": "Harnham", "location": "London",
         "job_url": "https://www.linkedin.com/jobs/view/4100000002/", "site": "linkedin"},
    ]
    monkeypatch.setattr(sw, "_run_task", lambda task, *a: {
        "status": "ok", "track": task[0], "term": task[1], "location": task[2], "site": task[3],
        "attempts": 1, "seconds": 0.1, "rows": rows, "error": ""})
    return tmp_path


def test_new_tags_each_direct_hit(discovery, monkeypatch, capsys):
    fake = FakeTagger()
    monkeypatch.setattr(sw, "_sponsor_tagger", lambda enabled: fake if enabled else None)
    sw.new(1, sites=("linkedin",), workers=1, queries=[("DA", "product analyst", "London")])
    out = capsys.readouterr().out
    assert "Acme 担保✅" in out
    assert "Harnham [中介·先问后投] 担保?(中介,雇主未知)" in out
    assert fake.seen == ["Acme"]                       # agencies are not looked up
    report = json.loads(next((discovery / "logs").glob("*.json")).read_text(encoding="utf-8"))
    acme = next(j for j in report["jobs"] if j["company"] == "Acme")
    assert acme["sponsor"]["status"] == "SKILLED_WORKER"
    assert "担保:✅ 1" in out


def test_new_without_sponsor_has_no_tags(discovery, monkeypatch, capsys):
    monkeypatch.setattr(sw, "_sponsor_tagger", lambda enabled: FakeTagger() if enabled else None)
    sw.new(1, sites=("linkedin",), workers=1, queries=[("DA", "product analyst", "London")], sponsor=False)
    assert "担保" not in capsys.readouterr().out


def test_sponsor_tagger_failure_degrades_gracefully(monkeypatch, capsys):
    def boom(**kwargs):
        raise sc.RegisterError("offline")
    monkeypatch.setattr(sc.SponsorTagger, "load", staticmethod(boom))
    assert sw._sponsor_tagger(True) is None
    assert "不标担保状态" in capsys.readouterr().out
    assert sw._sponsor_tagger(False) is None


def test_cli_no_sponsor_flag_reaches_new(monkeypatch):
    seen = {}
    monkeypatch.setattr(sw, "new", lambda *a, **k: seen.update(k))
    sw.main(["new", "1", "--no-sponsor"])
    assert seen["sponsor"] is False
    sw.main(["linkedin", "1"])
    assert seen["sponsor"] is True


# ---------------------------------------------------------------- boardsweep

def test_slug_to_name():
    assert bs.slug_to_name("checkout.com") == "checkout"
    assert bs.slug_to_name("iwoca.co.uk") == "iwoca"
    assert bs.slug_to_name("addepar1") == "addepar"
    assert bs.slug_to_name("skin-analytics") == "skin analytics"


def test_boardsweep_tags_hits_per_board(monkeypatch, tmp_path, capsys):
    cfg = tmp_path / "cfg.json"
    with open(os.path.join(SCRIPTS, "boardsweep_config.example.json"), encoding="utf-8") as f:
        data = json.load(f)
    data.update(ashby=["skin-analytics"], greenhouse=[])
    cfg.write_text(json.dumps(data), encoding="utf-8")
    jobs = {"jobs": [{"title": "Product Analyst", "location": "London", "jobUrl": "u", "publishedAt": None},
                     {"title": "Data Analyst", "location": "London", "jobUrl": "v", "publishedAt": None}]}
    monkeypatch.setattr(bs, "fetch_board", lambda kind, slug: jobs)
    fake = FakeTagger()
    monkeypatch.setattr(bs, "_sponsor_tagger", lambda enabled: fake if enabled else None)
    assert bs.main(["--config", str(cfg)]) == 0
    out = capsys.readouterr().out
    assert out.count("担保✅") == 2 and fake.seen == ["skin analytics"]   # looked up once per board
    assert bs.main(["--config", str(cfg), "--no-sponsor"]) == 0
    assert "担保✅" not in capsys.readouterr().out


def test_boardsweep_sponsor_tagger_failure(monkeypatch, capsys):
    monkeypatch.setattr(sc.SponsorTagger, "load", staticmethod(lambda **k: (_ for _ in ()).throw(OSError("x"))))
    assert bs._sponsor_tagger(True) is None
    assert "不标担保状态" in capsys.readouterr().out
