import importlib.util
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "scripts")

# sweep.py reads its config at import time; point it at the shipped example config.
_saved_argv = sys.argv
sys.argv = ["sweep.py", "--config", os.path.join(SCRIPTS, "sweep_config.example.json")]
spec = importlib.util.spec_from_file_location("sweep", os.path.join(SCRIPTS, "sweep.py"))
sw = importlib.util.module_from_spec(spec)
sys.modules["sweep"] = sw
spec.loader.exec_module(sw)
sys.argv = _saved_argv


def test_example_config_loads():
    assert sw.QUERIES and all(len(q) == 3 for q in sw.QUERIES)
    assert sw.TRACKED and all(len(t) == 3 for t in sw.TRACKED)
    assert set(sw.DISPLAY_TRACK_PRIORITY) <= set(sw.TITLE_RELEVANCE)


def test_exclude_regex_drops_senior_titles():
    assert sw.EXCLUDE.search("Senior Data Analyst")
    assert not sw.EXCLUDE.search("Data Analyst")


def test_indeed_country_mapping():
    assert sw._indeed_country("London, UK") == "UK"
    assert sw._indeed_country("Shanghai, China") == "China"
    assert sw._indeed_country("New York, USA") == "USA"


def test_source_id_extraction():
    assert sw._source_id("https://www.linkedin.com/jobs/view/4429114379/", "linkedin") == "4429114379"
    assert sw._source_id("https://uk.indeed.com/viewjob?jk=abc123&from=x", "indeed") == "abc123"
    assert sw._source_id("https://example.com", "other") == ""


def test_job_key_joins_mirrors_across_sites():
    a = {"title": "Product Analyst", "company": "Acme Ltd.", "location": "London, UK"}
    b = {"title": "product analyst", "company": "ACME LTD", "location": "London UK"}
    assert sw._job_key(a) == sw._job_key(b)


def test_text_treats_nan_as_empty():
    assert sw._text(None) == "" and sw._text("nan") == "" and sw._text("x") == "x"


def test_matching_title_tracks_uses_priority_order():
    item = {"title": "Applied AI Engineer", "tracks": ["AI", "FDE"]}
    assert sw._matching_title_tracks(item) == ["AI"]


def test_filter_tracks():
    picked, route = sw._filter_tracks(["--tracks", "GD"], sw.QUERIES)
    assert route == "GD" and all(q[0] == "GD" for q in picked)
    with pytest.raises(SystemExit):
        sw._filter_tracks(["--tracks", "NOPE"], sw.QUERIES)


def test_parse_discovery_args_defaults_and_flags():
    days, sites, timeout, retries, resume, plan, workers = sw._parse_discovery_args(
        ["7", "--resume", "--sites", "linkedin", "--workers", "5"])
    assert (days, sites, resume, plan, workers) == (7, ("linkedin",), True, False, 5)


def test_run_key_is_stable_for_same_inputs():
    assert sw._run_key(3, ("linkedin",), [("GD", "x", "UK")]) == sw._run_key(3, ("linkedin",), [("GD", "x", "UK")])
    assert sw._run_key(3, ("linkedin",), []) != sw._run_key(7, ("linkedin",), [])
