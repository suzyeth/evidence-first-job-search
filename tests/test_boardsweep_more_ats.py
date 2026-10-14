"""boardsweep: Lever, Workable and Teamtailor boards (payload shapes copied from the live public feeds)."""
import json
import os

import pytest

from conftest import SCRIPTS, load_script

bs = load_script("boardsweep")

with open(os.path.join(SCRIPTS, "boardsweep_config.example.json"), encoding="utf-8") as f:
    FILTERS = bs.build_filters(json.load(f))

LEVER = [
    {"text": "Forward Deployed AI Engineer", "hostedUrl": "https://jobs.lever.co/palantir/p1",
     "createdAt": 1786469891368, "categories": {"location": "London, United Kingdom", "allLocations": ["London, United Kingdom"]},
     "descriptionPlain": "You have 4+ years of experience.", "additionalPlain": "",
     "lists": [{"text": "What We Require", "content": "<li>Python</li>"}]},
    {"text": "Data Analyst", "hostedUrl": "https://jobs.lever.co/palantir/p2", "createdAt": 1786469891368,
     "categories": {"location": "Singapore, Singapore", "allLocations": ["Singapore, Singapore"]}},
    {"text": "Senior Data Analyst", "hostedUrl": "u", "createdAt": 1786469891368,
     "categories": {"location": "London", "allLocations": ["London"]}},
]

WORKABLE = {"name": "Spotlight Sports Group", "jobs": [
    {"title": "Data Analyst", "city": "London", "state": "England", "country": "United Kingdom",
     "published_on": "2026-10-05", "url": "https://apply.workable.com/j/AB12", "shortcode": "AB12",
     "description": "<p>Salary &pound;30,000. We are unable to offer visa sponsorship.</p>"},
    {"title": "Data Analyst", "city": "Berlin", "country": "Germany", "published_on": "2026-10-05", "url": "x"},
]}

TEAMTAILOR = {"title": "Awaze", "items": [
    {"title": "Product Analyst", "url": "https://awaze.teamtailor.com/jobs/1-product-analyst",
     "date_published": "2026-10-14T11:44:24+02:00", "content_html": "<p>We're looking for a Senior Product Analyst.</p>",
     "_jobposting": {"hiringOrganization": {"name": "Awaze Ltd"},
                     "jobLocation": [{"address": {"addressLocality": "Norwich", "addressCountry": "GB"}}]}},
    {"title": "Product Analyst", "url": "x", "date_published": "2026-10-14T11:44:24+02:00", "content_html": "",
     "_jobposting": {"jobLocation": [{"address": {"addressLocality": "Copenhagen", "addressCountry": "DK"}}]}},
]}


def test_lever_hits():
    hits = bs.lever_hits("palantir", LEVER, FILTERS)
    assert [(h.kind, h.title) for h in hits] == [("lever", "Forward Deployed AI Engineer")]
    h = hits[0]
    assert h.date == "2026-08-11" and h.url == "https://jobs.lever.co/palantir/p1"
    assert "4+ years" in h.jd and "Python" in h.jd


def test_lever_location_is_not_repeated():
    # live Palantir data repeats the main location inside allLocations
    hit = bs.lever_hits("palantir", LEVER, FILTERS)[0]
    assert hit.location == "London, United Kingdom"


def test_workable_hits_use_account_name_and_html_jd():
    hits = bs.workable_hits("spotlightsportsgroup", WORKABLE, FILTERS)
    assert [(h.kind, h.company, h.title) for h in hits] == [("workable", "Spotlight Sports Group", "Data Analyst")]
    assert "£30,000" in hits[0].jd and "<p>" not in hits[0].jd


def test_teamtailor_hits_map_country_codes_to_uk():
    hits = bs.teamtailor_hits("awaze", TEAMTAILOR, FILTERS)
    assert [(h.kind, h.company, h.title) for h in hits] == [("teamtailor", "Awaze Ltd", "Product Analyst")]
    assert "United Kingdom" in hits[0].location and hits[0].date == "2026-10-14"


def test_teamtailor_falls_back_to_feed_title_for_company():
    data = {"title": "Acme", "items": [{"title": "Data Analyst", "url": "u", "date_published": None,
                                        "content_html": "", "_jobposting": {"jobLocation": [
                                            {"address": {"addressLocality": "London", "addressCountry": "GB"}}]}}]}
    assert bs.teamtailor_hits("acme", data, FILTERS)[0].company == "Acme"


@pytest.mark.parametrize("kind, url_part", [
    ("lever", "api.lever.co/v0/postings/acme?mode=json"),
    ("workable", "apply.workable.com/api/v1/widget/accounts/acme?details=true"),
    ("teamtailor", "acme.teamtailor.com/jobs.json"),
])
def test_fetch_board_urls(monkeypatch, kind, url_part):
    seen = []
    monkeypatch.setattr(bs, "_get", lambda url, timeout=20: seen.append(url) or {"jobs": []})
    bs.fetch_board(kind, "acme")
    assert url_part in seen[0]


def test_fetch_board_lever_tries_eu_host(monkeypatch):
    seen = []

    def fake(url, timeout=20):
        seen.append(url)
        if "api.eu.lever.co" not in url:
            raise OSError("us 404")
        return []
    monkeypatch.setattr(bs, "_get", fake)
    assert bs.fetch_board("lever", "acme") == [] and "api.eu.lever.co" in seen[1]


def test_main_sweeps_all_five_ats(monkeypatch, tmp_path, capsys):
    with open(os.path.join(SCRIPTS, "boardsweep_config.example.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.update(ashby=[], greenhouse=[], lever=["palantir"], workable=["spotlightsportsgroup"], teamtailor=["awaze"])
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    boards = {"lever": LEVER, "workable": WORKABLE, "teamtailor": TEAMTAILOR}
    monkeypatch.setattr(bs, "fetch_board", lambda kind, slug: boards.get(kind))
    monkeypatch.setattr(bs, "_sponsor_tagger", lambda enabled: None)
    assert bs.main(["--config", str(path)]) == 0
    out = capsys.readouterr().out
    assert "板可达 3 / 探测 3" in out
    assert "[lever:palantir]" in out and "[workable:spotlightsportsgroup]" in out and "[teamtailor:awaze]" in out
    assert "❌不担保" in out and "正文Senior" in out
