"""JD analysis: sponsorship wording, hidden seniority, required years, salary vs visa thresholds."""
import pytest

from conftest import load_script

jd = load_script("jd_check")


# ---------------------------------------------------------------- text extraction

def test_html_to_text_handles_greenhouse_double_escaping():
    raw = "&lt;p&gt;We offer &lt;strong&gt;visa sponsorship&lt;/strong&gt; &amp;amp; more&lt;/p&gt;"
    assert jd.html_to_text(raw) == "We offer visa sponsorship & more"


# ---------------------------------------------------------------- years of experience

@pytest.mark.parametrize("text, years", [
    ("You have 5+ years of experience building APIs.", 5),
    ("3-5 years' professional experience in data analysis", 3),
    ("At least two years of industry experience.", 2),
    ("Minimum of 4 years experience with Python.", 4),
    ("2+ years experience required; 5+ years preferred.", 2),
    ("You will grow over the next 3 years.", None),          # not about experience
    ("No prior experience needed.", None),
])
def test_required_years(text, years):
    assert jd.required_years(text) == years


# ---------------------------------------------------------------- hidden seniority

@pytest.mark.parametrize("text, senior", [
    ("We're looking for a Senior Data Analyst to join us.", True),
    ("As a Lead Engineer you will own the roadmap.", True),
    ("You'll report to our senior leadership team.", False),
    ("Join a team of senior engineers as an associate.", False),
])
def test_senior_in_body(text, senior):
    assert jd.senior_in_body(text) is senior


# ---------------------------------------------------------------- salary

@pytest.mark.parametrize("text, low, high", [
    ("Salary: £45,000 - £55,000 per annum", 45000, 55000),
    ("Compensation £50k–£65k + equity", 50000, 65000),
    ("Base salary of £38,000", 38000, 38000),
    ("£40K to £48K depending on experience", 40000, 48000),
])
def test_salary_parsing(text, low, high):
    assert jd.annual_gbp_salary(text) == (low, high)


@pytest.mark.parametrize("text", [
    "£250 per day outside IR35",
    "£18.50 per hour",
    "£1,000 annual learning budget",       # benefit, not salary
    "$120,000 - $150,000",                  # not GBP
    "Competitive salary",
])
def test_salary_ignores_non_annual_or_non_gbp(text):
    assert jd.annual_gbp_salary(text) is None


def test_salary_prefers_the_sentence_that_talks_about_pay():
    text = "We have a £2,000,000 fund. The salary for this role is £42,000 - £48,000."
    assert jd.annual_gbp_salary(text) == (42000, 48000)


@pytest.mark.parametrize("low, flag", [
    (45000, "ok"), (41700, "ok"), (38000, "below_standard"), (33400, "below_standard"), (30000, "below_floor"),
])
def test_salary_flag_against_skilled_worker_thresholds(low, flag):
    assert jd.salary_flag(low) == flag


# ---------------------------------------------------------------- analyze + tags

def test_analyze_and_tags_combined():
    text = ("We're looking for a Senior Product Analyst. You have 5+ years of experience. "
            "Salary £35,000 - £40,000. Unfortunately we are unable to offer visa sponsorship.")
    r = jd.analyze(text)
    assert (r.sponsor, r.years, r.senior, r.salary_low, r.salary_flag) == (
        "negative", 5, True, 35000, "below_standard")
    assert jd.tags(r, max_years=3) == ["JD❌不担保", "正文Senior", "要5年+", "£35k<£41.7k标准"]


def test_tags_quiet_when_nothing_to_report():
    r = jd.analyze("Great team in London. 1+ years of experience. £50,000 salary.")
    assert jd.tags(r, max_years=3) == []


def test_tags_positive_sponsorship_and_floor():
    r = jd.analyze("Visa sponsorship is available. Salary: £30,000.")
    assert jd.tags(r, max_years=3) == ["JD✅可担保", "£30k<£33.4k下限"]


def test_tags_right_to_work_is_a_check():
    r = jd.analyze("You must have the right to work in the UK.")
    assert jd.tags(r, max_years=3) == ["JD⚠️需工作许可"]


def test_security_clearance_is_its_own_tag():
    # seen on a real Cohere JD: "Active DV clearance is highly preferred" is not a right-to-work question
    r = jd.analyze("Active DV clearance is highly preferred.")
    assert r.clearance is True
    assert jd.tags(r, max_years=3) == ["JD⚠️要安全审查(SC/DV)"]


def test_clearance_and_right_to_work_both_reported():
    r = jd.analyze("You must have the right to work in the UK. SC clearance required.")
    assert jd.tags(r, max_years=3) == ["JD⚠️需工作许可", "JD⚠️要安全审查(SC/DV)"]


def test_compensation_summary_is_used_when_body_has_no_salary():
    r = jd.analyze("Great role.", compensation="£60K – £80K • Offers Equity")
    assert r.salary_low == 60000 and r.salary_flag == "ok"


def test_cli_reports_findings_and_salary(tmp_path, capsys):
    bad = tmp_path / "bad.txt"
    bad.write_text("We're looking for a Lead Analyst, 6+ years of experience. Salary £36,000.", encoding="utf-8")
    clean = tmp_path / "clean.txt"
    clean.write_text("A friendly team.", encoding="utf-8")
    assert jd.main([str(bad), str(clean), "--max-years", "2"]) == 0
    out = capsys.readouterr().out
    assert "正文Senior · 要6年+ · £36k<£41.7k标准" in out and "£36,000–£36,000" in out
    assert "没发现问题" in out


def test_module_entrypoint(monkeypatch, tmp_path, capsys):
    import os
    import runpy
    import sys
    from conftest import SCRIPTS
    f = tmp_path / "jd.txt"
    f.write_text("Visa sponsorship is available.", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["jd_check.py", str(f)])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(os.path.join(SCRIPTS, "jd_check.py"), run_name="__main__")
    assert exc.value.code == 0 and "JD✅可担保" in capsys.readouterr().out


def test_thresholds_are_documented_with_source_and_date():
    assert "gov.uk" in jd.THRESHOLD_SOURCE and jd.THRESHOLD_CHECKED == "2026-10-13"
    assert (jd.STANDARD_THRESHOLD, jd.FLOOR_THRESHOLD) == (41700, 33400)
