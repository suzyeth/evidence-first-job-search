"""fact_check: employment dates and job titles on experience / education header lines."""
import pytest

from conftest import load_script

fc = load_script("fact_check")

MASTER = """# Master CV
### Example Studio — Game Designer
- 任期:2024-10 ~ Present, London
- 简历写法:Game Designer · Example Studio · London · October 2024 — Present
### Previous Co — Junior Designer
- 2021-03 ~ 2022-08
### MA Game Design — University of the Arts London
- 2022 — 2023
### BE Engineering Geology — Jilin University
- 2015 — 2020
"""


def kinds(findings, rule):
    return [(f.level, f.item) for f in findings if f.rule == rule]


# ---------------------------------------------------------------- range parsing

@pytest.mark.parametrize("text, expected", [
    ("October 2024 — Present", [((2024, 10), ("present", None))]),
    ("2024-10 ~ 2026-03", [((2024, 10), (2026, 3))]),
    ("2015 - 2020", [((2015, None), (2020, None))]),
    ("2015-2020", [((2015, None), (2020, None))]),
    ("Mar 2021 to Aug 2022", [((2021, 3), (2022, 8))]),
    ("2025-12 至今", [((2025, 12), ("present", None))]),
    ("2024-Present", [((2024, None), ("present", None))]),
    ("launched 2026-05-12, see Presentations", []),
])
def test_parse_ranges(text, expected):
    assert fc.parse_ranges(text) == expected


# ---------------------------------------------------------------- dates

def test_matching_dates_pass():
    resume = "### Game Designer · Example Studio · London · October 2024 - Present\n**BE Engineering Geology · Jilin University · 2015 - 2020**"
    assert kinds(fc.check(resume, MASTER, []), "date") == []


def test_stretched_tenure_fails():
    resume = "### Game Designer · Example Studio · London · October 2023 - Present"
    assert kinds(fc.check(resume, MASTER, []), "date") == [("FAIL", "October 2023 - Present")]


def test_month_conflict_fails():
    resume = "### Junior Designer · Previous Co · Jan 2021 – Aug 2022"
    assert kinds(fc.check(resume, MASTER, []), "date") == [("FAIL", "Jan 2021 – Aug 2022")]


def test_extra_month_detail_is_fine_when_master_has_years_only():
    resume = "**MA Game Design · University of the Arts London · October 2022 — December 2023**"
    assert kinds(fc.check(resume, MASTER, []), "date") == []


def test_date_ranges_are_not_counted_as_unevidenced_numbers():
    resume = "### Game Designer · Example Studio · London · October 2024 - Present"
    assert [f for f in fc.check(resume, MASTER, []) if f.rule == "number"] == []


# ---------------------------------------------------------------- titles / companies

def test_inflated_title_fails():
    resume = "### Lead Game Designer · Example Studio · London · October 2024 - Present"
    assert kinds(fc.check(resume, MASTER, []), "role") == [("FAIL", "Lead Game Designer")]


def test_unknown_company_fails():
    resume = "### Game Designer · Mystery Games · October 2024 - Present"
    assert ("FAIL", "Mystery Games") in kinds(fc.check(resume, MASTER, []), "role")


def test_correct_header_passes():
    resume = "### Example Studio | Game Designer | London | October 2024 - Present"
    assert kinds(fc.check(resume, MASTER, []), "role") == []


def test_reworded_multiword_segment_is_a_warning():
    # every word is in the fact base, only the phrasing differs ("the" dropped)
    resume = "**MA Game Design · University of Arts London · 2022 — 2023**"
    assert kinds(fc.check(resume, MASTER, []), "role") == [("WARN", "University of Arts London")]


def test_mostly_unevidenced_segment_fails():
    resume = "**MA Game Design · University of the Arts London — London College of Communication · 2022 — 2023**"
    assert kinds(fc.check(resume, MASTER, []), "role") == [("FAIL", "London College of Communication")]


def test_seniority_title_must_be_a_title_of_record_not_a_narrative_mention():
    # live case: the fact base said "this scope is Senior Game Designer level" in a note;
    # that sentence must not make "Senior Game Designer" a valid job title
    master = MASTER + "\n- 备注:这套 scope 是 mid-level Game Designer / Senior Game Designer 级别\n"
    resume = "### Senior Game Designer · Example Studio · October 2024 - Present"
    assert kinds(fc.check(resume, master, []), "role") == [("FAIL", "Senior Game Designer")]


def test_seniority_title_in_a_heading_is_accepted():
    master = MASTER + "\n### Bigger Co — Senior Analyst\n- 2019 ~ 2021\n"
    resume = "### Senior Analyst · Bigger Co · 2019 - 2021"
    assert kinds(fc.check(resume, master, []), "role") == []


def test_seniority_word_never_downgrades_to_warning():
    # "Senior Game Designer" shares 2 of 3 words with "Game Designer" but is title inflation
    resume = "### Senior Game Designer · Example Studio · October 2024 - Present"
    assert kinds(fc.check(resume, MASTER, []), "role") == [("FAIL", "Senior Game Designer")]


def test_only_header_lines_are_checked_for_roles():
    resume = "- Presented demos to judges between 2024 - Present at London meetups"
    assert kinds(fc.check(resume, MASTER, []), "role") == []
