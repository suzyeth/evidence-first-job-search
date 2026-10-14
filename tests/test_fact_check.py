import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
SCRIPT = os.path.join(HERE, "..", "scripts", "fact_check.py")

spec = importlib.util.spec_from_file_location("fact_check", SCRIPT)
fc = importlib.util.module_from_spec(spec)
sys.modules["fact_check"] = fc
spec.loader.exec_module(fc)


def read(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


MASTER = read("master_sample.md")
CONFIDENTIAL = fc.parse_terms(read("confidential_sample.txt"))


def run(resume_name):
    return fc.check(read(resume_name), MASTER, CONFIDENTIAL)


def by_rule(findings, rule):
    return [f for f in findings if f.rule == rule]


# ---- numbers ----

def test_extract_numbers_normalises_commas_and_ignores_urls():
    nums = fc.extract_numbers("1,200 players, 8% rate [link](https://x.io/game-2025) and £50k")
    assert nums == {"1200", "8%", "50k"}


def test_good_resume_has_no_failures():
    findings = run("resume_good.md")
    assert [f for f in findings if f.level == "FAIL"] == []


def test_number_not_in_master_fails():
    numbers = by_rule(run("resume_bad.md"), "number")
    assert [f.item for f in numbers] == ["55%"]
    assert numbers[0].level == "FAIL"


# ---- skills ----

def test_skill_not_in_master_fails():
    skills = by_rule(run("resume_bad.md"), "skill")
    assert [f.item for f in skills] == ["Kubernetes"]


def test_skills_line_parsing():
    assert fc.extract_skills("**Skills:** Python · Unity, C# | SQL") == ["Python", "Unity", "C#", "SQL"]


# ---- metrics ----

def test_metric_acronym_not_in_master_fails():
    metrics = by_rule(run("resume_bad.md"), "metric")
    assert [f.item for f in metrics] == ["ARPU"]


# ---- confidential / placeholders / buzzwords ----

def test_confidential_term_fails():
    conf = by_rule(run("resume_bad.md"), "confidential")
    assert [f.item for f in conf] == ["Project Falcon"]
    assert conf[0].level == "FAIL"


def test_parse_terms_skips_comments_and_blanks():
    assert fc.parse_terms("# c\n\nfoo\n  bar  \n") == ["foo", "bar"]


def test_placeholder_fails():
    assert [f.item for f in by_rule(run("resume_bad.md"), "placeholder")] == ["[FILL]"]


def test_buzzwords_warn_not_fail():
    buzz = by_rule(run("resume_bad.md"), "buzzword")
    assert {f.item.lower() for f in buzz} == {"passionate", "driven", "spearheaded"}
    assert all(f.level == "WARN" for f in buzz)


def test_internal_notes_section_is_not_evidence():
    # facts that only live under the 🔒 internal-notes heading must not count as evidence
    resume = "Grew monthly revenue strongly."
    findings = fc.check(resume, MASTER, [])
    assert fc.public_master(MASTER).find("monthly revenue") == -1
    assert findings == []  # no number/skill claims here; confidential list is empty


# ---- regressions found on a real resume ----

def test_heading_mentioning_internal_codename_is_still_evidence():
    master = "#### Project 2 (内部代号 X, internal codename)\n- Welch's t-test (α=0.05, power=0.8)\n"
    assert fc.check("α = 0.05 and power = 0.8", master, []) == []


def test_k_suffix_matches_full_number():
    assert fc.check("a 200,000-run simulation", "a 200k-run simulation", []) == []
    assert fc.check("a 200k-run simulation", "a 200,000-run simulation", []) == []


def test_phone_numbers_and_emails_are_ignored():
    assert fc.check("+44 7700 900123 · jane2025@example.com", "nothing here", []) == []


def test_skill_list_split_respects_parentheses():
    assert fc.extract_skills("- **Languages**: Python (NumPy, pandas), SQL (CTEs), C#") == []  # not in a skills section
    text = "## Skills\n- **Languages**: Python (NumPy, pandas), SQL (window functions, CTEs), C#\n"
    assert fc.extract_skills(text) == ["Python", "SQL", "C#"]


def test_multiword_skill_passes_when_its_words_are_evidenced():
    master = "Ran cohort analysis and corrected for selection bias in the funnel."
    assert fc.check("**Skills:** cohort and selection-bias correction", master, []) == []


def test_multiword_skill_with_unevidenced_words_fails():
    findings = fc.check("**Skills:** Kubernetes cluster autoscaling", "Python scripts only.", [])
    assert [f.rule for f in findings] == ["skill"]


def test_human_languages_are_not_checked_as_skills():
    assert fc.check("**Skills:** Python, English, Mandarin", "Python", []) == []


def test_html_comments_are_not_checked():
    resume = read("resume_good.md") + (
        "\n<!--\ninternal note: drafted from line 744, 99 tests\n"
        "- **Skills**: Kubernetes, Rust\nTODO: ask about ARPU\n-->\n"
    )
    assert not [f for f in fc.check(resume, MASTER, CONFIDENTIAL) if f.level == "FAIL"]


def test_text_after_html_comment_is_still_checked():
    findings = fc.check("<!-- note -->\nGrew retention by 999%", MASTER, CONFIDENTIAL)
    assert "999%" in [f.item for f in by_rule(findings, "number")]


# ---- CLI ----

def test_main_exit_codes(tmp_path):
    good = os.path.join(FIX, "resume_good.md")
    bad = os.path.join(FIX, "resume_bad.md")
    master = os.path.join(FIX, "master_sample.md")
    conf = os.path.join(FIX, "confidential_sample.txt")
    assert fc.main([good, "--master", master, "--confidential", conf]) == 0
    assert fc.main([bad, "--master", master, "--confidential", conf]) == 1
