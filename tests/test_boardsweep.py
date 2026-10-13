import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "scripts")

spec = importlib.util.spec_from_file_location("boardsweep", os.path.join(SCRIPTS, "boardsweep.py"))
bs = importlib.util.module_from_spec(spec)
sys.modules["boardsweep"] = bs
spec.loader.exec_module(bs)  # must not touch the network on import

with open(os.path.join(SCRIPTS, "boardsweep_config.example.json"), encoding="utf-8") as f:
    CFG = json.load(f)


def test_example_config_compiles():
    f = bs.build_filters(CFG)
    assert f.want.search("Forward Deployed Engineer")
    assert f.senior.search("Senior Product Analyst")


def test_wanted_filters_title_location_and_seniority():
    f = bs.build_filters(CFG)
    assert bs.wanted("Applied AI Engineer", "London, UK", None, f)
    assert not bs.wanted("Senior Applied AI Engineer", "London, UK", None, f)
    assert not bs.wanted("Applied AI Engineer", "San Francisco", None, f)
    assert not bs.wanted("Account Executive", "London", None, f)


def test_since_filter():
    f = bs.build_filters(CFG, "2026-09-01")
    assert bs.wanted("Product Analyst", "London", "2026-09-15T10:00:00Z", f)
    assert not bs.wanted("Product Analyst", "London", "2026-08-01T10:00:00Z", f)
    assert not bs.wanted("Product Analyst", "London", None, f)


def test_ashby_hits_skip_unlisted():
    data = {"jobs": [
        {"title": "Product Analyst", "location": "London", "isListed": True,
         "jobUrl": "https://jobs.ashbyhq.com/x/1", "publishedAt": "2026-10-01T00:00:00Z"},
        {"title": "Product Analyst II", "location": "London", "isListed": False},
    ]}
    hits = bs.ashby_hits("x", data, bs.build_filters(CFG))
    assert [h.title for h in hits] == ["Product Analyst"]
    assert hits[0].date == "2026-10-01"


def test_greenhouse_hits_read_nested_location():
    data = {"jobs": [{"title": "Solutions Engineer", "location": {"name": "London, UK"},
                      "absolute_url": "https://boards.greenhouse.io/x/jobs/1", "updated_at": "2026-10-02"}]}
    hits = bs.greenhouse_hits("x", data, bs.build_filters(CFG))
    assert [(h.kind, h.title) for h in hits] == [("gh", "Solutions Engineer")]


def test_dedupe_by_title_and_slug():
    h = bs.Hit("gh", "x", "Data Analyst", "London", "u", "")
    assert bs.dedupe([h, h, bs.Hit("gh", "y", "Data Analyst", "London", "u", "")]) == [
        h, bs.Hit("gh", "y", "Data Analyst", "London", "u", "")]
