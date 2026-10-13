"""v0.3: JD checks inside boardsweep, and sponsor_check --add-alias."""
import json
import os

from conftest import FIXTURES, SCRIPTS, load_script

bs = load_script("boardsweep")
sc = load_script("sponsor_check")

REGISTER = os.path.join(FIXTURES, "register_sample.csv")


# ================================================================ boardsweep + JD

def example_cfg(tmp_path, **overrides):
    with open(os.path.join(SCRIPTS, "boardsweep_config.example.json"), encoding="utf-8") as f:
        data = json.load(f)
    data.update(overrides)
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_fetch_board_requests_full_descriptions(monkeypatch):
    seen = []
    monkeypatch.setattr(bs, "_get", lambda url, timeout=20: seen.append(url) or {"jobs": []})
    bs.fetch_board("gh", "acme")
    bs.fetch_board("ashby", "acme")
    assert seen[0].endswith("/boards/acme/jobs?content=true")
    assert seen[1].endswith("/job-board/acme?includeCompensation=true")


def test_greenhouse_hits_carry_company_and_plain_text_jd():
    data = {"jobs": [{"title": "Data Analyst", "location": {"name": "London"}, "absolute_url": "u",
                      "updated_at": None, "company_name": "Acme Ltd",
                      "content": "&lt;p&gt;You have 5+ years of experience.&lt;/p&gt;"}]}
    hit = bs.greenhouse_hits("acme", data, bs.build_filters(json.load(open(
        os.path.join(SCRIPTS, "boardsweep_config.example.json"), encoding="utf-8"))))[0]
    assert hit.company == "Acme Ltd" and hit.jd == "You have 5+ years of experience."


def test_ashby_hits_carry_jd_and_compensation():
    data = {"jobs": [{"title": "Product Analyst", "location": "London", "isListed": True, "jobUrl": "u",
                      "descriptionPlain": "Salary £30,000.",
                      "compensation": {"compensationTierSummary": "£30K – £35K"}}]}
    hit = bs.ashby_hits("acme", data, bs.build_filters(json.load(open(
        os.path.join(SCRIPTS, "boardsweep_config.example.json"), encoding="utf-8"))))[0]
    assert hit.jd == "Salary £30,000." and hit.comp == "£30K – £35K"


class FakeTagger:
    def __init__(self):
        self.seen = []

    def tag(self, company):
        self.seen.append(company)
        return {"display": f"担保✅({company})", "label": "担保✅"}


def test_boardsweep_main_prints_jd_flags_and_uses_company_name(monkeypatch, tmp_path, capsys):
    board = {"jobs": [{"title": "Data Analyst", "location": {"name": "London"}, "absolute_url": "u1",
                       "updated_at": None, "company_name": "Acme Ltd",
                       "content": ("&lt;p&gt;We are looking for a Senior Data Analyst with 5+ years of experience. "
                                   "Salary £30,000. We are unable to offer visa sponsorship.&lt;/p&gt;")}]}
    monkeypatch.setattr(bs, "fetch_board", lambda kind, slug: board)
    fake = FakeTagger()
    monkeypatch.setattr(bs, "_sponsor_tagger", lambda enabled: fake if enabled else None)
    cfg = example_cfg(tmp_path, ashby=[], greenhouse=["acme"], max_years=2)
    assert bs.main(["--config", cfg]) == 0
    out = capsys.readouterr().out
    assert fake.seen == ["Acme Ltd"]                      # real company name beats the slug
    assert "[JD:❌不担保·正文Senior·要5年+·£30k<£33.4k下限]" in out
    assert "JD 体检:❌不担保 1" in out
    assert bs.main(["--config", cfg, "--no-jd", "--no-sponsor"]) == 0
    assert "[JD:" not in capsys.readouterr().out


# ================================================================ --add-alias

def write_aliases(tmp_path, data):
    path = tmp_path / "aliases.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


def test_add_alias_normalises_to_register_name_and_keeps_readme(tmp_path, capsys):
    path = write_aliases(tmp_path, {"_readme": "keep me", "Zego": "EXTRACOVER LIMITED"})
    assert sc.main(["--add-alias", "Bumble", "badoo limited", "--register", REGISTER, "--aliases", path]) == 0
    data = json.load(open(path, encoding="utf-8"))
    assert data == {"_readme": "keep me", "Zego": "EXTRACOVER LIMITED", "Bumble": "Badoo Limited"}
    assert "已加入" in capsys.readouterr().out


def test_add_alias_rejects_names_missing_from_register(tmp_path, capsys):
    path = write_aliases(tmp_path, {})
    assert sc.main(["--add-alias", "Bumble", "Badoo Ltd Typo Corp", "--register", REGISTER,
                    "--aliases", path]) == 1
    assert json.load(open(path, encoding="utf-8")) == {}
    assert "名册里没有" in capsys.readouterr().out


def test_add_alias_suggests_close_register_names(tmp_path, capsys):
    path = write_aliases(tmp_path, {})
    sc.main(["--add-alias", "X", "Badoo Limted", "--register", REGISTER, "--aliases", path])
    assert "Badoo Limited" in capsys.readouterr().out


def test_add_alias_warns_when_no_skilled_worker_route(tmp_path, capsys):
    path = write_aliases(tmp_path, {})
    assert sc.main(["--add-alias", "SCT", "Sports Charity Trust", "--register", REGISTER, "--aliases", path]) == 0
    assert "没有 Skilled Worker" in capsys.readouterr().out
