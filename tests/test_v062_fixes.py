"""v0.6.2: fixes found by an end-to-end trial run of the v0.6.1 release."""
import json
import os
import re
import sys
import types

import pytest

from conftest import FIXTURES, SCRIPTS, load_script

sc = load_script("sponsor_check")
bs = load_script("boardsweep")
fc = load_script("fact_check")
sw = load_script("sweep")

REGISTER = os.path.join(FIXTURES, "register_sample.csv")


# 1. alias lookups no longer list unrelated same-name entities ------------------------------------

def test_alias_result_only_lists_the_aliased_entity():
    # trial run: "Cursor" (alias Anysphere UK Ltd) also printed an unrelated "Cursor Ltd · Lincoln"
    r = sc.lookup("Sports Charity Trust", sc.load_register(REGISTER), {"Sports Charity Trust": "Spotlightsportsgroup"})
    assert [m.org.name for m in r.matches] == ["Spotlightsportsgroup"]
    assert r.hidden_namesakes == 1
    out = sc.render(r)
    assert "Sports Charity Trust · Bristol" not in out and "另有 1 个同名机构" in out


def test_alias_status_comes_from_the_aliased_entity_only():
    # the unrelated namesake has only a Charity Worker route; the aliased entity decides the verdict
    r = sc.lookup("Sports Charity Trust", sc.load_register(REGISTER), {"Sports Charity Trust": "Spotlightsportsgroup"})
    assert r.status == "SKILLED_WORKER"


def test_alias_without_namesakes_prints_no_note():
    r = sc.lookup("Bumble", sc.load_register(REGISTER), {"Bumble": "Badoo Limited"})
    assert r.hidden_namesakes == 0 and "同名机构" not in sc.render(r)


# 2. "Sr" is excluded like "Senior" -------------------------------------------------------------

@pytest.mark.parametrize("title", ["Sr Forward Deployed Engineer", "Sr. Data Analyst", "SR Product Analyst"])
def test_example_config_excludes_sr(title):
    assert sw.EXCLUDE.search(title)


def test_example_config_does_not_exclude_words_containing_sr():
    assert not sw.EXCLUDE.search("SRE Data Analyst") and not sw.EXCLUDE.search("Data Analyst (SRS team)")


# 3. Ashby locations are readable --------------------------------------------------------------

def test_ashby_location_lists_names_not_python_reprs():
    data = {"jobs": [{"title": "Forward Deployed Engineer", "location": "London", "isListed": True, "jobUrl": "u",
                      "secondaryLocations": [{"location": "New York", "address": {"postalAddress": {
                          "addressCountry": "United States"}}}]}]}
    filters = bs.build_filters({**json.load(open(os.path.join(SCRIPTS, "boardsweep_config.example.json"),
                                                 encoding="utf-8")), "location_regex": "london|new york"})
    hit = bs.ashby_hits("x", data, filters)[0]
    assert hit.location == "London; New York, United States"
    assert "[" not in hit.location and "{" not in hit.location


def test_ashby_location_without_secondaries():
    data = {"jobs": [{"title": "Forward Deployed Engineer", "location": "London", "isListed": True, "jobUrl": "u",
                      "secondaryLocations": []}]}
    filters = bs.build_filters(json.load(open(os.path.join(SCRIPTS, "boardsweep_config.example.json"),
                                              encoding="utf-8")))
    assert bs.ashby_hits("x", data, filters)[0].location == "London"


# 4. English output uses English punctuation ----------------------------------------------------

def test_fact_check_english_separator(monkeypatch):
    monkeypatch.setenv("JOBSEARCH_LANG", "en")
    text = fc.render("r.md", [fc.Finding("FAIL", "number", "55%", "number not in the fact base")])
    assert "——" not in text and " — number not in the fact base" in text


def test_fact_check_chinese_separator_unchanged():
    text = fc.render("r.md", [fc.Finding("FAIL", "number", "55%", "事实库里找不到这个数字")])
    assert " —— 事实库里找不到这个数字" in text


# 5. labels for slug-only ATSs read like company names ------------------------------------------

@pytest.mark.parametrize("slug, name", [
    ("cursor", "Cursor"), ("skin-analytics", "Skin Analytics"), ("checkout.com", "Checkout"),
    ("iwoca.co.uk", "Iwoca"), ("addepar1", "Addepar"),
])
def test_pretty_slug(slug, name):
    assert sw.pretty_slug(slug) == name


def test_describe_ashby_uses_pretty_company(monkeypatch):
    monkeypatch.setattr(sw, "fetch", lambda url, timeout=25: json.dumps(
        {"jobs": [{"id": "u1", "title": "FDE"}]}))
    assert sw.describe_job("ashby_id", ["skin-analytics", "u1"]) == ("FDE", "Skin Analytics")


# 6. the ❌ legend says "not found under this name", not "can't sponsor" -------------------------

def test_sponsor_legend_explains_not_found(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sw, "STATE_DIR", str(tmp_path / "s"))
    monkeypatch.setattr(sw, "LOG_DIR", str(tmp_path / "l"))
    monkeypatch.setitem(sys.modules, "jobspy", types.ModuleType("jobspy"))
    row = {"title": "Data Analyst", "company": "Acme", "location": "London",
           "job_url": "https://www.linkedin.com/jobs/view/4100000001/", "site": "linkedin"}
    monkeypatch.setattr(sw, "_run_task", lambda t, *a: {"status": "ok", "track": t[0], "term": t[1],
                                                        "location": t[2], "site": t[3], "attempts": 1,
                                                        "seconds": 0.1, "rows": [row], "error": ""})

    class Tagger:
        def tag(self, company):
            return {"status": "NOT_FOUND", "label": "担保❌", "display": "担保❌"}
    monkeypatch.setattr(sw, "_sponsor_tagger", lambda enabled: Tagger())
    sw.new(1, sites=("linkedin",), workers=1, queries=[("DA", "data analyst", "London")])
    out = capsys.readouterr().out
    assert "❌ 名册里没找到这个名字(不等于不能担保" in out


# 7. a LinkedIn 429 gets a concrete fallback hint ----------------------------------------------

def test_linkedin_rate_limit_hint(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sw, "STATE_DIR", str(tmp_path / "s"))
    monkeypatch.setattr(sw, "LOG_DIR", str(tmp_path / "l"))
    monkeypatch.setitem(sys.modules, "jobspy", types.ModuleType("jobspy"))
    monkeypatch.setattr(sw, "_run_task", lambda t, *a: {
        "status": "error", "track": t[0], "term": t[1], "location": t[2], "site": t[3], "attempts": 2,
        "seconds": 0.1, "rows": [], "error": "ERROR - JobSpy:LinkedIn - LinkedIn response status code 429"})
    monkeypatch.setattr(sw, "_sponsor_tagger", lambda enabled: None)
    sw.new(1, sites=("linkedin",), workers=1, queries=[("DA", "data analyst", "London")])
    out = capsys.readouterr().out
    assert "LinkedIn 限流" in out and "--sites indeed" in out and "--resume" in out


def test_no_rate_limit_hint_for_other_errors(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sw, "STATE_DIR", str(tmp_path / "s"))
    monkeypatch.setattr(sw, "LOG_DIR", str(tmp_path / "l"))
    monkeypatch.setitem(sys.modules, "jobspy", types.ModuleType("jobspy"))
    monkeypatch.setattr(sw, "_run_task", lambda t, *a: {
        "status": "error", "track": t[0], "term": t[1], "location": t[2], "site": t[3], "attempts": 2,
        "seconds": 0.1, "rows": [], "error": "timeout>90s"})
    monkeypatch.setattr(sw, "_sponsor_tagger", lambda enabled: None)
    sw.new(1, sites=("linkedin",), workers=1, queries=[("DA", "data analyst", "London")])
    assert "LinkedIn 限流" not in capsys.readouterr().out
