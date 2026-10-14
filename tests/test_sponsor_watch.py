"""sponsor_check --watch: baseline the employers you care about, then report register changes."""
import json
import os

from conftest import FIXTURES, load_script

sc = load_script("sponsor_check")

BASE = os.path.join(FIXTURES, "register_sample.csv")
ALIASES = {"Bumble": "Badoo Limited"}


def changed_register(tmp_path):
    """Same sample register, but: Anthropic gone, Badoo downgraded to B,
    EXTRACOVER lost its Skilled Worker route, and a new 'Acme Widgets Ltd' appears."""
    lines = open(BASE, encoding="utf-8").read().splitlines()
    out = []
    for line in lines:
        if line.startswith("Anthropic Limited"):
            continue
        if line.startswith("Badoo Limited"):
            line = line.replace("(A rating)", "(B rating)")
        if line.startswith("EXTRACOVER LIMITED"):
            line = line.replace("Skilled Worker", "Global Business Mobility: Senior or Specialist Worker")
        out.append(line)
    out.append("Acme Widgets Ltd,Leeds,,Worker (A rating),Skilled Worker")
    path = tmp_path / "register_changed.csv"
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return str(path)


def run_watch(names, register_path, state, capsys):
    code = sc.watch(names, sc.load_register(register_path), ALIASES, str(state), os.path.basename(register_path))
    return code, capsys.readouterr().out


def test_first_run_records_a_baseline(tmp_path, capsys):
    state = tmp_path / "state" / "watch.json"
    code, out = run_watch(["Anthropic", "Bumble"], BASE, state, capsys)
    assert code == 0 and "基线" in out
    data = json.loads(state.read_text(encoding="utf-8"))
    assert data["companies"]["Bumble"]["orgs"]["Badoo Limited"]["rating"] == "A"
    assert data["register"] == "register_sample.csv"


def test_second_run_reports_every_kind_of_change(tmp_path, capsys):
    state = tmp_path / "watch.json"
    names = ["Anthropic", "Bumble", "EXTRACOVER", "Acme Widgets", "Spotlight Sports"]
    run_watch(names, BASE, state, capsys)
    code, out = run_watch(names, changed_register(tmp_path), state, capsys)
    assert code == 0
    assert "🔴 Anthropic:Anthropic Limited 已从名册消失" in out
    assert "🟠 Bumble:Badoo Limited 评级 A → B" in out
    assert "🟠 EXTRACOVER:EXTRACOVER LIMITED 失去 Skilled Worker 路线" in out
    assert "🟢 Acme Widgets:现在在名册上了(Acme Widgets Ltd · Leeds · A 级)" in out
    assert "Spotlight Sports" in out and "无变化" in out
    assert "5 家里 4 家有变化" in out


def test_no_changes(tmp_path, capsys):
    state = tmp_path / "watch.json"
    run_watch(["Anthropic"], BASE, state, capsys)
    code, out = run_watch(["Anthropic"], BASE, state, capsys)
    assert "没有变化" in out


def test_company_added_later_gets_its_own_baseline(tmp_path, capsys):
    state = tmp_path / "watch.json"
    run_watch(["Anthropic"], BASE, state, capsys)
    _, out = run_watch(["Anthropic", "Bumble"], BASE, state, capsys)
    assert "Bumble:新加入监控" in out


def test_alias_restricts_the_baseline_to_the_aliased_entity():
    # live case: "Cursor" exactly matches an unrelated "Cursor Ltd" (Lincoln) as well as the
    # aliased Anysphere UK Ltd; only the aliased entity may be watched, or the other one causes false alarms
    register = sc.load_register(BASE)
    result = sc.lookup("Sports Charity Trust", register, {"Sports Charity Trust": "Spotlightsportsgroup"}, fuzzy=False)
    assert {m.org.name for m in result.matches} >= {"Sports Charity Trust", "Spotlightsportsgroup"}
    assert set(sc._snapshot(result)["orgs"]) == {"Spotlightsportsgroup"}


def test_alias_with_trading_as_name_is_still_watched():
    # the shipped alias "Resolver" -> "Crisp Thinking Group Ltd t/a Resolver" must keep its entity
    register = sc.load_register(BASE)
    result = sc.lookup("Resolver", register, {"Resolver": "Crisp Thinking Group Ltd t/a Resolver"}, fuzzy=False)
    assert set(sc._snapshot(result)["orgs"]) == {"Crisp Thinking Group Ltd t/a Resolver"}


def test_ambiguous_names_are_not_watched(tmp_path, capsys):
    state = tmp_path / "watch.json"
    _, out = run_watch(["Nothing"], BASE, state, capsys)
    assert "名字太常见" in out and "--add-alias" in out
    assert "Nothing" not in json.loads(state.read_text(encoding="utf-8"))["companies"]


def test_cli_watch(tmp_path, capsys, monkeypatch):
    state = tmp_path / "w.json"
    assert sc.main(["--watch", "Anthropic", "--register", BASE, "--state", str(state)]) == 0
    assert "基线" in capsys.readouterr().out and state.exists()
    assert sc.main(["--watch", "--register", BASE, "--state", str(state)]) == 2   # no names given
