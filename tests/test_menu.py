import os

import pytest

from conftest import load_script

mn = load_script("menu")


class Harness:
    def __init__(self, *answers, codes=None):
        self.answers = list(answers)
        self.said, self.calls = [], []
        self.codes = codes or {}

    def ask(self, prompt):
        return self.answers.pop(0) if self.answers else "0"

    def say(self, text):
        self.said.append(text)

    def run(self, args):
        self.calls.append(args)
        return self.codes.get(args[0], 0)

    def go(self):
        return mn.loop(self.ask, self.say, self.run)

    @property
    def text(self):
        return "\n".join(self.said)


def test_quit_and_bad_option():
    h = Harness("﻿9", "x", "0")
    assert h.go() == 0
    assert "没有这个选项" in h.text and "再见" in h.text and h.calls == []


def test_sponsor_check_splits_names():
    h = Harness("1", "Monzo, Wise、Bumble", "", "0")
    h.go()
    assert h.calls == [["sponsor_check.py", "Monzo", "Wise", "Bumble"]]
    h2 = Harness("1", "  ", "", "0")
    h2.go()
    assert h2.calls == [] and "没有输入公司名" in h2.text


def test_keywords_then_apply(monkeypatch, tmp_path):
    monkeypatch.setattr(mn, "LOG_DIR", str(tmp_path))
    (tmp_path / "discovery-scan-1.json").write_text("{}", encoding="utf-8")
    h = Harness("2", "core", "", "0")
    h.go()
    assert h.calls == [["keyword_suggest.py", "--from-logs"], ["keyword_suggest.py", "--apply", "core"]]
    h2 = Harness("2", "", "0", codes={"keyword_suggest.py": 1})
    h2.go()
    assert h2.calls == [["keyword_suggest.py"]] or h2.calls == [["keyword_suggest.py", "--from-logs"]]


def test_scan_runs_setup_first_then_scan_and_report(monkeypatch, tmp_path):
    monkeypatch.setattr(mn, "SCRIPT_DIR", str(tmp_path))
    monkeypatch.setattr(mn, "jobspy_installed", lambda: True)
    setups = []
    monkeypatch.setattr(mn, "run_setup", lambda ask, say: setups.append(1) or 0)
    h = Harness("3", "7", "", "0")
    h.go()
    assert setups == [1] and h.calls == [["sweep.py", "new", "7"], ["report.py"]]


def test_scan_stops_if_setup_cancelled(monkeypatch, tmp_path):
    monkeypatch.setattr(mn, "SCRIPT_DIR", str(tmp_path))
    monkeypatch.setattr(mn, "run_setup", lambda ask, say: 1)
    h = Harness("3", "", "0")
    h.go()
    assert h.calls == []


def test_run_setup_uses_the_menu_input(monkeypatch):
    import setup_wizard
    got = []
    monkeypatch.setattr(setup_wizard, "run", lambda ask, say: got.append(ask("q")) or 0)
    assert mn.run_setup(lambda p: "answer", lambda s: None) == 0 and got == ["answer"]

    def broken(ask, say):
        raise SystemExit("bad config")
    monkeypatch.setattr(setup_wizard, "run", broken)
    said = []
    assert mn.run_setup(lambda p: "", said.append) == 1 and said == ["bad config"]


def test_scan_offers_install(monkeypatch, tmp_path):
    (tmp_path / "sweep_config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(mn, "SCRIPT_DIR", str(tmp_path))
    monkeypatch.setattr(mn, "jobspy_installed", lambda: False)
    installs = []
    monkeypatch.setattr(mn.subprocess, "call", lambda cmd, **k: installs.append(cmd) or 0)
    h = Harness("3", "y", "x", "", "0")
    h.go()
    assert installs and "python-jobspy" in installs[0]
    assert h.calls == [["sweep.py", "new", "3"], ["report.py"]]  # bad day count falls back to 3

    failed = Harness("3", "", "", "0")
    monkeypatch.setattr(mn.subprocess, "call", lambda cmd, **k: 1)
    failed.go()
    assert failed.calls == [] and "安装失败" in failed.text

    declined = Harness("3", "n", "", "0")
    declined.go()
    assert declined.calls == []


def test_track_add_or_check():
    h = Harness("4", '"https://jobs.ashbyhq.com/acme/123"', "", "4", "", "", "0")
    h.go()
    assert h.calls == [["sweep.py", "add", "https://jobs.ashbyhq.com/acme/123"], ["sweep.py", "live", "--log"]]


def test_jd_from_file_and_from_paste(tmp_path):
    jd = tmp_path / "jd.txt"
    jd.write_text("We sponsor visas.", encoding="utf-8")
    h = Harness("5", f'"{jd}"', "", "5", str(tmp_path / "missing.txt"), "", "0")
    h.go()
    assert h.calls == [["jd_check.py", str(jd)]] and "找不到文件" in h.text

    seen = {}

    class Paste(Harness):
        def run(self, args):
            seen["text"] = open(args[1], encoding="utf-8").read()
            return super().run(args)
    p = Paste("5", "", "Line one", "", "Line two", "", "", "", "0")
    p.go()
    assert seen["text"] == "Line one\n\nLine two"
    assert not os.path.exists(p.calls[0][1])  # temp file cleaned up

    empty = Harness("5", "", "", "", "", "0")
    empty.go()
    assert empty.calls == [] and "没有收到内容" in empty.text


def test_factcheck_finds_or_asks_for_master(tmp_path):
    folder = tmp_path / "apps" / "acme"
    folder.mkdir(parents=True)
    cv = folder / "resume.md"
    cv.write_text("x", encoding="utf-8")
    master = tmp_path / "elsewhere.md"
    master.write_text("x", encoding="utf-8")
    h = Harness("6", str(cv), str(master), "", "0")
    h.go()
    assert h.calls == [["fact_check.py", str(cv), "--master", str(master)]]

    (tmp_path / "master-cv-data.md").write_text("x", encoding="utf-8")
    h2 = Harness("6", str(cv), "", "0")
    h2.go()
    assert h2.calls == [["fact_check.py", str(cv)]]

    h3 = Harness("6", "nope.md", "", "0")
    h3.go()
    assert h3.calls == [] and "找不到这个文件" in h3.text


def test_factcheck_without_master_stops(tmp_path):
    cv = tmp_path / "cv.md"
    cv.write_text("x", encoding="utf-8")
    h = Harness("6", str(cv), "", "", "0")
    h.go()
    assert h.calls == [] and "使用说明" in h.text


def test_setup_guide_and_language(monkeypatch):
    opened = []
    monkeypatch.setattr(mn, "open_path", opened.append)
    setups = []
    monkeypatch.setattr(mn, "run_setup", lambda ask, say: setups.append(1) or 0)
    h = Harness("7", "", "8", "", "L", "0")
    h.go()
    assert setups == [1] and h.calls == []
    assert opened == [mn.GUIDE_ZH]
    assert "Quit" in h.said[-2]  # menu re-drawn in English after L


def test_guide_open_failure(monkeypatch):
    def fail(path):
        raise OSError
    monkeypatch.setattr(mn, "open_path", fail)
    h = Harness("8", "", "0")
    h.go()
    assert "打不开" in h.text


def test_interrupt_inside_an_action_returns_to_menu():
    class Boom(Harness):
        def run(self, args):
            raise KeyboardInterrupt
    h = Boom("1", "Monzo", "", "0")
    assert h.go() == 0 and "已中断" in h.text


def test_main_exits_cleanly_on_eof(monkeypatch):
    def eof(*a):
        raise EOFError
    monkeypatch.setattr(mn, "loop", eof)
    assert mn.main([]) == 0


def test_helpers(monkeypatch):
    assert mn.split_names("a, b，c") == ["a", "b", "c"]
    assert mn.render_menu().count("\n") > 8
    calls = []
    monkeypatch.setattr(mn.subprocess, "call", lambda cmd, **k: calls.append((cmd, k)) or 0)
    assert mn.run_script(["x.py", "1"]) == 0
    assert calls[0][0][1:] == ["x.py", "1"] and calls[0][1]["cwd"] == mn.SCRIPT_DIR
    monkeypatch.setattr(mn.sys, "platform", "linux")
    mn.open_path("guide.md")
    assert calls[-1][0] == ["xdg-open", "guide.md"]
    monkeypatch.setattr(mn.sys, "platform", "darwin")
    mn.open_path("guide.md")
    assert calls[-1][0] == ["open", "guide.md"]


def test_jobspy_installed_checks_import(monkeypatch):
    import builtins
    real = builtins.__import__

    def fake(name, *a, **k):
        if name == "jobspy":
            raise ImportError
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", fake)
    assert mn.jobspy_installed() is False
