"""Country codes from job feeds are expanded so location filters written as words still match."""
import json
import os

import pytest

from conftest import SCRIPTS, load_script

countries = load_script("countries")
bs = load_script("boardsweep")


def test_iso_table_is_complete_and_well_formed():
    codes = [c for c in countries.ISO_COUNTRIES if c != "UK"]
    assert len(codes) == 249                                  # every ISO 3166-1 alpha-2 code
    assert all(len(c) == 2 and c.isalpha() and c.isupper() for c in codes)


@pytest.mark.parametrize("value, name", [
    ("DE", "Germany"), ("nl", "Netherlands"), ("GB", "United Kingdom"), ("UK", "United Kingdom"),
    ("US", "United States"), ("Germany", "Germany"), ("", ""), (None, ""), ("ZZ", "ZZ"),
])
def test_country_name(value, name):
    assert countries.country_name(value) == name


def filters(location_regex):
    with open(os.path.join(SCRIPTS, "boardsweep_config.example.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    return bs.build_filters({**cfg, "location_regex": location_regex})


def test_teamtailor_non_uk_codes_match_word_filters():
    data = {"title": "Acme", "items": [
        {"title": "Data Analyst", "url": "u1", "date_published": None, "content_html": "",
         "_jobposting": {"jobLocation": [{"address": {"addressLocality": "Berlin", "addressCountry": "DE"}}]}},
        {"title": "Data Analyst", "url": "u2", "date_published": None, "content_html": "",
         "_jobposting": {"jobLocation": [{"address": {"addressLocality": "Amsterdam", "addressCountry": "NL"}}]}},
    ]}
    hits = bs.teamtailor_hits("acme", data, filters("germany"))
    assert [h.location for h in hits] == ["Berlin, Germany"]


def test_lever_country_code_is_expanded_into_location():
    data = [{"text": "Data Analyst", "hostedUrl": "u", "createdAt": None, "country": "NL",
             "categories": {"location": "Amsterdam", "allLocations": ["Amsterdam"]}}]
    hits = bs.lever_hits("acme", data, filters("netherlands"))
    assert [h.location for h in hits] == ["Amsterdam; Netherlands"]


def test_example_sweep_config_maps_common_countries_for_indeed():
    sw = load_script("sweep")
    for location, country in [("Berlin, Germany", "Germany"), ("Amsterdam, Netherlands", "Netherlands"),
                              ("Dublin, Ireland", "Ireland"), ("Toronto, Canada", "Canada"),
                              ("Singapore", "Singapore"), ("London, UK", "UK"), ("New York, USA", "USA")]:
        assert sw._indeed_country(location) == country
