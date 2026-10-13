import importlib.util
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "sponsor_check.py")
FIXTURE = os.path.join(HERE, "fixtures", "register_sample.csv")

spec = importlib.util.spec_from_file_location("sponsor_check", SCRIPT)
sc = importlib.util.module_from_spec(spec)
sys.modules["sponsor_check"] = sc   # dataclasses resolve annotations via sys.modules
spec.loader.exec_module(sc)


@pytest.fixture(scope="module")
def register():
    return sc.load_register(FIXTURE)


# ---- normalisation ----

def test_core_strips_legal_suffixes_and_punctuation():
    assert sc.core_name(" NOTHING TECHNOLOGY LIMITED ") == "nothing technology"
    assert sc.core_name("Badoo Ltd.") == "badoo"
    assert sc.core_name("Smith & Jones LLP") == "smith and jones"


def test_split_trading_as_variants():
    assert sc.split_trading_as("HAH Hospitality Limited t/a Indian Affair Ancoats") == [
        "HAH Hospitality Limited", "Indian Affair Ancoats"]
    assert sc.split_trading_as("HAWTHORN MANOR LIMITED t/as Hawthorn Manor Residential Home") == [
        "HAWTHORN MANOR LIMITED", "Hawthorn Manor Residential Home"]
    assert sc.split_trading_as("Foo Ltd trading as Bar") == ["Foo Ltd", "Bar"]
    assert sc.split_trading_as("Plain Name Ltd") == ["Plain Name Ltd"]


# ---- register loading ----

def test_load_register_groups_routes_per_organisation(register):
    org = register["Anthropic Limited"]
    assert org.routes == {"Skilled Worker", "Global Business Mobility: Senior or Specialist Worker"}
    assert org.town == "London"


def test_load_register_trims_whitespace_and_handles_quoted_commas(register):
    assert "NOTHING TECHNOLOGY LIMITED" in register
    assert "Department for Science, Innovation and Technology" in register
    assert register["Sports Charity Trust"].routes == {"Charity Worker"}


def test_rating_is_captured(register):
    assert register["Monzo Bank Limited"].rating == "B"


# ---- matching ----

def kinds(result):
    return {(m.org.name, m.kind) for m in result.matches}


def test_exact_match_ignores_suffix(register):
    r = sc.lookup("Anthropic", register)
    assert ("Anthropic Limited", "exact") in kinds(r)
    assert r.status == "SKILLED_WORKER"


def test_squashed_match_for_names_written_without_spaces(register):
    r = sc.lookup("Spotlight Sports", register)
    assert ("Spotlightsportsgroup", "squashed") in kinds(r)


def test_trading_name_after_t_a_is_matched(register):
    r = sc.lookup("Resolver", register)
    assert ("Crisp Thinking Group Ltd t/a Resolver", "exact") in kinds(r)


def test_long_quoted_name_matched_by_middle_fragment(register):
    r = sc.lookup("Science, Innovation and Technology", register)
    assert ("Department for Science, Innovation and Technology", "contains") in kinds(r)


def test_alias_maps_trading_name_to_legal_name(register):
    r = sc.lookup("Bumble", register, aliases={"bumble": "Badoo Limited"})
    assert ("Badoo Limited", "exact") in kinds(r)
    assert r.via_alias == "Badoo Limited"


def test_alias_hit_suppresses_fuzzy_noise_from_trading_name(register):
    # 'Sports' alone would substring-match the charity; the alias is authoritative
    r = sc.lookup("Sports", register, aliases={"sports": "Spotlightsportsgroup"})
    assert {m.org.name for m in r.matches} == {"Spotlightsportsgroup"}


def test_common_word_name_is_flagged_noisy(register):
    r = sc.lookup("Nothing", register)
    assert r.noisy is True


def test_other_route_only_is_not_reported_as_skilled_worker(register):
    r = sc.lookup("Sports Charity Trust", register)
    assert r.status == "OTHER_ROUTE_ONLY"


def test_not_found_gives_companies_house_url(register):
    r = sc.lookup("Totally Unknown Widgets", register)
    assert r.status == "NOT_FOUND"
    assert r.companies_house_url.startswith(
        "https://find-and-update.company-information.service.gov.uk/search/companies?q=")
    assert "Totally+Unknown+Widgets" in r.companies_house_url


def test_fuzzy_match_catches_small_typos(register):
    r = sc.lookup("Extracovr", register)
    assert ("EXTRACOVER LIMITED", "similar") in kinds(r)


# ---- JD scan ----

def test_jd_scan_detects_negative_sponsorship():
    text = "Great team. Unfortunately we are unable to offer visa sponsorship for this role."
    hits = sc.scan_jd(text)
    assert [h.signal for h in hits] == ["negative"]


def test_jd_scan_detects_positive_sponsorship():
    hits = sc.scan_jd("Visa sponsorship is available for the right candidate.")
    assert [h.signal for h in hits] == ["positive"]


def test_jd_scan_flags_right_to_work_as_check():
    hits = sc.scan_jd("You must have the right to work in the UK.")
    assert [h.signal for h in hits] == ["check"]


def test_jd_scan_empty_when_silent():
    assert sc.scan_jd("We build great products in London.") == []


# ---- register link discovery ----

def test_find_csv_link_in_publication_page():
    html = ('<a href="https://assets.publishing.service.gov.uk/media/abc/'
            'SP_-_Worker_and_Temporary_Worker_Web_Register_-_2026-10-13.csv">CSV</a>')
    assert sc.find_csv_link(html).endswith("2026-10-13.csv")


def test_find_csv_link_missing_raises():
    with pytest.raises(sc.RegisterError):
        sc.find_csv_link("<html>no link</html>")
