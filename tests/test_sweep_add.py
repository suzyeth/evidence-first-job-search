"""sweep.py add <job URL>: detect the ATS, confirm the job is live, append it to tracked."""
import json
import urllib.error

import pytest

from conftest import EXAMPLE_SWEEP_CONFIG, load_script

sw = load_script("sweep")


# ---------------------------------------------------------------- URL parsing

@pytest.mark.parametrize("url, expected", [
    ("https://boards.greenhouse.io/anthropic/jobs/5435282008", ("greenhouse", ["anthropic", 5435282008])),
    ("https://job-boards.greenhouse.io/anthropic/jobs/5435282008?gh_src=x", ("greenhouse", ["anthropic", 5435282008])),
    ("https://job-boards.eu.greenhouse.io/monzo/jobs/8098919", ("greenhouse", ["monzo", 8098919])),
    ("https://jobs.ashbyhq.com/cursor/0a82f564-de1b-4c72-9ba4-10cf2b63c483", ("ashby_id", ["cursor", "0a82f564-de1b-4c72-9ba4-10cf2b63c483"])),
    ("https://jobs.ashbyhq.com/cursor/0a82f564-de1b-4c72-9ba4-10cf2b63c483/application", ("ashby_id", ["cursor", "0a82f564-de1b-4c72-9ba4-10cf2b63c483"])),
    ("https://jobs.lever.co/palantir/ff1029bd-bb6d-4d78-a03e-5f9744d0b798", ("lever", ["palantir", "ff1029bd-bb6d-4d78-a03e-5f9744d0b798"])),
    ("https://jobs.eu.lever.co/pigment/6cbc9f93-5034-4838-84b0-13fbcd742163/apply", ("lever", ["pigment", "6cbc9f93-5034-4838-84b0-13fbcd742163"])),
    ("https://apply.workable.com/spotlightsportsgroup/j/52341B2833/", ("workable", ["spotlightsportsgroup", "52341B2833"])),
    ("https://artificiallabsltd.teamtailor.com/jobs/7155366-forward-deployed-engineer", ("teamtailor", ["artificiallabsltd", "7155366-forward-deployed-engineer"])),
    ("https://acme.bamboohr.com/careers/123", ("bamboohr", ["acme", "123"])),
    ("https://www.linkedin.com/jobs/view/4429114379/", ("linkedin", "4429114379")),
    ("https://uk.linkedin.com/jobs/view/product-analyst-at-acme-4429114379?trk=x", ("linkedin", "4429114379")),
    ("https://www.linkedin.com/jobs/search/?currentJobId=4429114379&keywords=x", ("linkedin", "4429114379")),
])
def test_parse_job_url(url, expected):
    assert sw.parse_job_url(url) == expected


@pytest.mark.parametrize("url, hint", [
    ("https://databricks.com/company/careers/open-positions/job?gh_jid=8593713002", "Greenhouse"),
    ("https://careers.example.com/jobs/123", "不认识"),
    ("not a url", "不认识"),
])
def test_parse_job_url_rejects_unsupported(url, hint):
    with pytest.raises(ValueError, match=hint):
        sw.parse_job_url(url)


# ---------------------------------------------------------------- describe (title + company)

def fake_fetch(pages):
    def fetch(url, timeout=25):
        for key, value in pages.items():
            if key in url:
                if isinstance(value, Exception):
                    raise value
                return value if isinstance(value, str) else json.dumps(value)
        raise urllib.error.HTTPError(url, 404, "nf", None, None)
    return fetch


def test_describe_greenhouse(monkeypatch):
    monkeypatch.setattr(sw, "fetch", fake_fetch({
        "boards/anthropic/jobs/5": {"id": 5, "title": "Applied AI Engineer", "company_name": "Anthropic"}}))
    assert sw.describe_job("greenhouse", ["anthropic", 5]) == ("Applied AI Engineer", "Anthropic")


def test_describe_ashby_upgrades_to_title_channel(monkeypatch):
    monkeypatch.setattr(sw, "fetch", fake_fetch({"job-board/cursor": {"jobs": [
        {"id": "u1", "title": "Forward Deployed Engineer - EMEA", "isListed": True}]}}))
    assert sw.describe_job("ashby_id", ["cursor", "u1"]) == ("Forward Deployed Engineer - EMEA", "cursor")


def test_describe_lever_and_workable(monkeypatch):
    monkeypatch.setattr(sw, "fetch", fake_fetch({
        "api.lever.co/v0/postings/palantir/p1": {"text": "FD AI Engineer"},
        "accounts/wk": {"name": "Spotlight", "jobs": [{"shortcode": "AB", "title": "Data Analyst"}]}}))
    assert sw.describe_job("lever", ["palantir", "p1"]) == ("FD AI Engineer", "palantir")
    assert sw.describe_job("workable", ["wk", "AB"]) == ("Data Analyst", "Spotlight")


def test_describe_html_pages_use_title_tag(monkeypatch):
    monkeypatch.setattr(sw, "fetch", fake_fetch({
        "jobs/view/42": "<html><title>Acme hiring Product Analyst in London | LinkedIn</title></html>",
        "tt.teamtailor.com": "<title>Forward Deployed Engineer - Artificial Labs</title>"}))
    assert sw.describe_job("linkedin", "42") == ("Acme hiring Product Analyst in London", "")
    assert sw.describe_job("teamtailor", ["tt", "1-x"]) == ("Forward Deployed Engineer - Artificial Labs", "")


def test_describe_failure_returns_empty(monkeypatch):
    monkeypatch.setattr(sw, "fetch", fake_fetch({}))
    assert sw.describe_job("lever", ["x", "y"]) == ("", "")


# ---------------------------------------------------------------- add command

@pytest.fixture
def config(tmp_path):
    with open(EXAMPLE_SWEEP_CONFIG, encoding="utf-8") as f:
        data = json.load(f)
    data["tracked"] = [{"label": "Existing", "channel": "greenhouse", "args": ["anthropic", 1]}]
    path = tmp_path / "sweep_config.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def tracked(path):
    return json.loads(path.read_text(encoding="utf-8"))["tracked"]


def test_add_greenhouse_job(monkeypatch, config, capsys):
    monkeypatch.setattr(sw, "fetch", fake_fetch({
        "boards/anthropic/jobs/5435282008": {"title": "Applied AI Engineer, DNB", "company_name": "Anthropic"},
        "boards/anthropic/jobs": {"jobs": [{"id": 5435282008}]}}))
    assert sw.add_job("https://job-boards.greenhouse.io/anthropic/jobs/5435282008", str(config)) == 0
    assert tracked(config)[-1] == {"label": "Anthropic · Applied AI Engineer, DNB", "channel": "greenhouse",
                                   "args": ["anthropic", 5435282008]}
    assert "已加入" in capsys.readouterr().out


def test_add_ashby_stores_title_channel(monkeypatch, config):
    monkeypatch.setattr(sw, "fetch", fake_fetch({"job-board/cursor": {"jobs": [
        {"id": "0a82f564-de1b-4c72-9ba4-10cf2b63c483", "title": "Forward Deployed Engineer - EMEA", "isListed": True}]}}))
    assert sw.add_job("https://jobs.ashbyhq.com/cursor/0a82f564-de1b-4c72-9ba4-10cf2b63c483", str(config)) == 0
    assert tracked(config)[-1]["channel"] == "ashby_title"
    assert tracked(config)[-1]["args"] == ["cursor", "Forward Deployed Engineer - EMEA"]


def test_add_refuses_duplicates(monkeypatch, config, capsys):
    monkeypatch.setattr(sw, "fetch", fake_fetch({"boards/anthropic/jobs": {"jobs": [{"id": 1}]}}))
    assert sw.add_job("https://boards.greenhouse.io/anthropic/jobs/1", str(config)) == 0
    assert len(tracked(config)) == 1 and "已经在跟踪" in capsys.readouterr().out


def test_add_refuses_dead_job_unless_forced(monkeypatch, config, capsys):
    monkeypatch.setattr(sw, "fetch", fake_fetch({"boards/anthropic/jobs": {"jobs": [{"id": 999}]}}))
    url = "https://boards.greenhouse.io/anthropic/jobs/5"
    assert sw.add_job(url, str(config)) == 1
    assert len(tracked(config)) == 1 and "已下架" in capsys.readouterr().out
    assert sw.add_job(url, str(config), force=True) == 0
    assert len(tracked(config)) == 2


def test_add_linkedin_warns_about_mirrors(monkeypatch, config, capsys):
    monkeypatch.setattr(sw.time, "sleep", lambda s: None)
    monkeypatch.setattr(sw, "fetch", fake_fetch({"jobs/view/4200000001": "<title>Acme hiring Analyst | LinkedIn</title>"}))
    assert sw.add_job("https://www.linkedin.com/jobs/view/4200000001/", str(config), label="Acme Analyst") == 0
    assert tracked(config)[-1] == {"label": "Acme Analyst", "channel": "linkedin", "args": "4200000001"}
    assert "镜像" in capsys.readouterr().out


def test_add_unsupported_url_and_network_error(monkeypatch, config, capsys):
    assert sw.add_job("https://careers.example.com/jobs/1", str(config)) == 1
    monkeypatch.setattr(sw, "fetch", fake_fetch({"boards/x/jobs": urllib.error.URLError("offline")}))
    assert sw.add_job("https://boards.greenhouse.io/x/jobs/5", str(config)) == 1
    out = capsys.readouterr().out
    assert "不认识" in out and "没法确认" in out
    assert len(tracked(config)) == 1


def test_cli_add_dispatch(monkeypatch):
    seen = {}
    monkeypatch.setattr(sw, "add_job", lambda url, path, label=None, force=False: seen.update(
        url=url, label=label, force=force) or 0)
    assert sw.main(["add", "https://x", "--label", "My job", "--force"]) == 0
    assert seen == {"url": "https://x", "label": "My job", "force": True}
    assert sw.main(["add"]) == 2
