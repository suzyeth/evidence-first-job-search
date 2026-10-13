"""Download / cache / CLI paths of sponsor_check.py, boardsweep.py and fact_check.py, all offline."""
import json
import os
import runpy
import sys
import urllib.error

import pytest

from conftest import FIXTURES, SCRIPTS, load_script

sc = load_script("sponsor_check")
bs = load_script("boardsweep")
fc = load_script("fact_check")

REGISTER = os.path.join(FIXTURES, "register_sample.csv")
CSV_URL = "https://assets.publishing.service.gov.uk/media/x/Register_-_2026-10-13.csv"


# ================================================================ sponsor_check: download + cache

@pytest.fixture
def cache(monkeypatch, tmp_path):
    monkeypatch.setattr(sc, "CACHE_DIR", str(tmp_path))
    return tmp_path


def fake_gov_uk(monkeypatch, fail=False):
    calls = []

    def fake_fetch(url, timeout=60):
        calls.append(url)
        if fail:
            raise urllib.error.URLError("offline")
        if url == sc.PUBLICATION_URL:
            return f'<a href="{CSV_URL}">CSV</a>'.encode()
        with open(REGISTER, "rb") as f:
            return f.read()
    monkeypatch.setattr(sc, "_fetch", fake_fetch)
    return calls


def test_ensure_register_downloads_then_reuses_cache(monkeypatch, cache):
    calls = fake_gov_uk(monkeypatch)
    path = sc.ensure_register()
    assert os.path.basename(path) == "register-2026-10-13.csv" and len(calls) == 2
    assert sc.ensure_register() == path and len(calls) == 2          # fresh cache, no network
    sc.ensure_register(refresh=True)
    assert len(calls) == 4


def test_ensure_register_falls_back_to_stale_cache(monkeypatch, cache, capsys):
    stale = cache / "register-2026-01-01.csv"
    stale.write_text("Organisation Name,Route\n", encoding="utf-8")
    os.utime(stale, (0, 0))
    fake_gov_uk(monkeypatch, fail=True)
    assert sc.ensure_register() == str(stale)
    assert "改用旧缓存" in capsys.readouterr().err


def test_ensure_register_without_cache_raises(monkeypatch, cache):
    fake_gov_uk(monkeypatch, fail=True)
    with pytest.raises(sc.RegisterError):
        sc.ensure_register()


def test_load_register_rejects_unexpected_columns(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("Name,City\nAcme,London\n", encoding="utf-8")
    with pytest.raises(sc.RegisterError, match="缺少列"):
        sc.load_register(str(bad))


def test_rating_handles_every_format_seen_in_the_real_register():
    assert sc._rating("Worker (A rating)") == "A"
    assert sc._rating("Temporary Worker (B rating)") == "B"
    assert sc._rating("Worker (A (Premium))") == "A (Premium)"
    assert sc._rating("Worker (A (SME+))") == "A (SME+)"
    assert sc._rating("Worker (UK Expansion Worker: Provisional )") == "UK Expansion Worker: Provisional"
    assert sc._rating("Temporary Worker") == "Temporary Worker"


# ================================================================ sponsor_check: rendering + CLI

@pytest.fixture(scope="module")
def register():
    return sc.load_register(REGISTER)


def test_render_covers_every_status(register):
    texts = {q: sc.render(sc.lookup(q, register), all_routes=True)
             for q in ("Anthropic", "Sports Charity Trust", "Extracovr", "Totally Unknown", "Nothing")}
    assert "Global Business Mobility" in texts["Anthropic"]          # --all-routes
    assert "没有 Skilled Worker" in texts["Sports Charity Trust"]
    assert "近似匹配" in texts["Extracovr"]
    assert "Companies House" in texts["Totally Unknown"]
    assert "常见词" in texts["Nothing"]


def test_render_truncates_long_match_lists(register, monkeypatch):
    monkeypatch.setattr(sc, "MAX_SHOWN", 1)
    # 'Technology' matches both NOTHING TECHNOLOGY LIMITED and DSIT
    assert "另有" in sc.render(sc.lookup("Technology", register))


def test_load_aliases_skips_meta_keys(tmp_path):
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"_readme": "x", "Bumble": "Badoo Limited"}), encoding="utf-8")
    assert sc.load_aliases(str(p)) == {"Bumble": "Badoo Limited"}
    assert sc.load_aliases(str(tmp_path / "missing.json")) == {}


def test_shipped_aliases_resolve_in_sample(register):
    aliases = sc.load_aliases(sc.DEFAULT_ALIASES)
    assert sc.lookup("Bumble", register, aliases).status == "SKILLED_WORKER"


def test_sponsor_cli_text_file_and_jd(tmp_path, capsys):
    names = tmp_path / "names.txt"
    names.write_text("# comment\nAnthropic\n\n", encoding="utf-8")
    jd = tmp_path / "jd.md"
    jd.write_text("We cannot sponsor visas.\n", encoding="utf-8")
    silent = tmp_path / "silent.md"
    silent.write_text("Great team in London.\n", encoding="utf-8")
    code = sc.main(["Bumble", "--file", str(names), "--register", REGISTER, "--jd", str(jd), str(silent)])
    out = capsys.readouterr().out
    assert code == 0 and "Badoo Limited" in out and "Anthropic Limited" in out
    assert "不担保" in out and "没有提到担保" in out


def test_sponsor_cli_json(capsys):
    assert sc.main(["Anthropic", "--register", REGISTER, "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["companies"][0]["status"] == "SKILLED_WORKER"


def test_sponsor_cli_no_input_and_register_error(monkeypatch, capsys):
    assert sc.main([]) == 2
    monkeypatch.setattr(sc, "ensure_register", lambda *a: (_ for _ in ()).throw(sc.RegisterError("down")))
    assert sc.main(["Anthropic"]) == 1
    assert "down" in capsys.readouterr().err


def test_sponsor_module_entrypoint(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["sponsor_check.py", "Anthropic", "--register", REGISTER])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(os.path.join(SCRIPTS, "sponsor_check.py"), run_name="__main__")
    assert exc.value.code == 0 and "Anthropic Limited" in capsys.readouterr().out


# ================================================================ boardsweep: network + CLI

def test_fetch_board_tries_eu_greenhouse_node(monkeypatch):
    seen = []

    def fake_get(url, timeout=20):
        seen.append(url)
        if "eu.greenhouse" not in url:
            raise urllib.error.URLError("us node 404")
        return {"jobs": []}
    monkeypatch.setattr(bs, "_get", fake_get)
    assert bs.fetch_board("gh", "acme") == {"jobs": []} and len(seen) == 2


def test_fetch_board_returns_none_when_unreachable(monkeypatch):
    monkeypatch.setattr(bs, "_get", lambda url, timeout=20: (_ for _ in ()).throw(OSError("x")))
    assert bs.fetch_board("ashby", "acme") is None


def test_boardsweep_main(monkeypatch, tmp_path, capsys):
    cfg = tmp_path / "cfg.json"
    with open(os.path.join(SCRIPTS, "boardsweep_config.example.json"), encoding="utf-8") as f:
        data = json.load(f)
    data.update(ashby=["good"], greenhouse=["gone"])
    cfg.write_text(json.dumps(data), encoding="utf-8")
    boards = {("ashby", "good"): {"jobs": [{"title": "Product Analyst", "location": "London",
                                            "jobUrl": "u", "publishedAt": "2026-10-01T00:00:00Z"}]}}
    monkeypatch.setattr(bs, "fetch_board", lambda kind, slug: boards.get((kind, slug)))
    assert bs.main(["--config", str(cfg), "--since", "2026-09-01"]) == 0
    out = capsys.readouterr().out
    assert "板可达 1 / 探测 2" in out and "gh:gone" in out and "Product Analyst" in out


def test_boardsweep_bad_inputs(tmp_path):
    with pytest.raises(SystemExit, match="找不到"):
        bs.main(["--config", str(tmp_path / "missing.json")])
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"want_title_regex": "x", "senior_title_regex": "y", "location_regex": "z"}),
                   encoding="utf-8")
    with pytest.raises(SystemExit, match="YYYY-MM-DD"):
        bs.main(["--config", str(cfg), "--since", "13/10/2026"])


# ================================================================ fact_check: CLI branches

def test_fact_check_finds_master_and_confidential_upwards(tmp_path, capsys):
    (tmp_path / "master-cv-data.md").write_text("Shipped 3 games.", encoding="utf-8")
    (tmp_path / "confidential-terms.txt").write_text("Falcon\n", encoding="utf-8")
    pkg = tmp_path / "applications" / "acme"
    pkg.mkdir(parents=True)
    resume = pkg / "resume.md"
    resume.write_text("Shipped 3 games incl. Falcon.", encoding="utf-8")
    assert fc.main([str(resume)]) == 1
    assert "[confidential] Falcon" in capsys.readouterr().out


def test_fact_check_json_and_missing_master(tmp_path, capsys):
    resume = tmp_path / "resume.md"
    resume.write_text("Shipped 3 games.", encoding="utf-8")
    assert fc.main([str(resume)]) == 2                                  # no master anywhere above
    master = tmp_path / "m.md"
    master.write_text("Shipped 3 games.", encoding="utf-8")
    capsys.readouterr()
    assert fc.main([str(resume), "--master", str(master), "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {str(resume): []}


def test_fact_check_skills_heading_section():
    text = "## Skills\n- Tools: Python, Figma\n## Experience\n- Python everywhere\n"
    assert fc.extract_skills(text) == ["Python", "Figma"]


def test_fact_check_module_entrypoint(monkeypatch, tmp_path, capsys):
    resume = tmp_path / "r.md"
    resume.write_text("Shipped 3 games.", encoding="utf-8")
    master = tmp_path / "m.md"
    master.write_text("Shipped 3 games.", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["fact_check.py", str(resume), "--master", str(master)])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(os.path.join(SCRIPTS, "fact_check.py"), run_name="__main__")
    assert exc.value.code == 0 and "通过" in capsys.readouterr().out
