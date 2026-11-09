# -*- coding: utf-8 -*-
"""数字菜单:不用记命令。双击仓库根目录的「开始使用」文件就会打开它,也可以 python menu.py。

每一项都会一步步问你要输入什么;文件可以直接拖进窗口。做完按回车回到菜单。
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys
import tempfile
from typing import Callable

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from friendly import clean_path  # noqa: E402
from i18n import LANG_ENV, apply_lang_arg, lang, tr  # noqa: E402

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(SCRIPT_DIR)
VENDOR_DIR = os.path.join(SCRIPT_DIR, "vendor")
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
GUIDE_ZH = os.path.join(REPO_DIR, "使用说明.md")
GUIDE_EN = os.path.join(REPO_DIR, "GETTING-STARTED.md")

Ask = Callable[[str], str]
Say = Callable[[str], None]
Runner = Callable[[list[str]], int]


def run_script(args: list[str]) -> int:
    """Run one of the scripts in a child process, in the current language, and return its exit code."""
    env = {**os.environ, LANG_ENV: lang(), "PYTHONIOENCODING": "utf-8"}
    return subprocess.call([sys.executable, *args], cwd=SCRIPT_DIR, env=env)


def open_path(path: str) -> None:
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.call(["open", path])
    else:
        subprocess.call(["xdg-open", path])


def jobspy_installed() -> bool:
    if os.path.isdir(VENDOR_DIR) and VENDOR_DIR not in sys.path:
        sys.path.insert(0, VENDOR_DIR)
    try:
        import jobspy  # noqa: F401
    except ImportError:
        return False
    return True


def split_names(raw: str) -> list[str]:
    import re
    return [n.strip() for n in re.split(r"[,，、;；\n]+", raw) if n.strip()]


def read_pasted(ask: Ask, say: Say) -> str:
    say(tr("把 JD 全文粘贴进来,结束时连按两次回车(留两个空行):",
           "Paste the full JD, then press Enter twice (two empty lines) to finish:"))
    lines, blanks = [], 0
    while blanks < 2:
        line = ask("")
        blanks = blanks + 1 if not line.strip() else 0
        lines.append(line)
    return "\n".join(lines).strip()


# ---------------------------------------------------------------- menu actions

def do_sponsor(ask: Ask, say: Say, run: Runner) -> None:
    raw = ask(tr("公司名(可以一次输入多个,用逗号隔开):", "Company names (several allowed, separated by commas): "))
    names = split_names(raw)
    if not names:
        say(tr("没有输入公司名。", "No company entered."))
        return
    run(["sponsor_check.py", *names])
    say(tr("\n提示:❌ 只说明「这个名字」不在名册上。品牌名和登记的法人名常常不同,结果里给了 Companies House 链接可以反查。",
           "\nTip: ❌ only means this *name* isn't on the register. Brand names often differ from the registered "
           "legal name; use the Companies House link in the result."))


def do_keywords(ask: Ask, say: Say, run: Runner) -> None:
    args = ["keyword_suggest.py"]
    if glob.glob(os.path.join(LOG_DIR, "discovery-scan-*.json")):
        args.append("--from-logs")
    if run(args) != 0:
        return
    which = ask(tr("\n要把哪些写进搜索配置?输入 core(核心档)、编号如 1,3,5-8,或直接回车跳过:",
                   "\nAdd which ones to your search config? Type core, numbers like 1,3,5-8, or press Enter to skip: "))
    if which.strip():
        run(["keyword_suggest.py", "--apply", which.strip()])


def run_setup(ask: Ask, say: Say) -> int:
    """Run the setup wizard in this process so it reads answers from the same window (and the same input)."""
    import setup_wizard
    try:
        return setup_wizard.run(ask, say)
    except SystemExit as exc:
        say(str(exc))
        return 1


def do_scan(ask: Ask, say: Say, run: Runner) -> None:
    if not os.path.exists(os.path.join(SCRIPT_DIR, "sweep_config.json")):
        say(tr("还没有搜索配置,先做「首次设置」。", "There is no search config yet; let's run the setup first."))
        if run_setup(ask, say) != 0:
            return
    if not jobspy_installed():
        say(tr("扫描 LinkedIn / Indeed 需要先装一个免费组件 python-jobspy(只装在本文件夹里,约 1 分钟)。",
               "Scanning LinkedIn / Indeed needs a free add-on, python-jobspy (installed inside this folder only, "
               "about a minute)."))
        if ask(tr("现在安装吗?[Y/n]: ", "Install it now? [Y/n]: ")).strip().lower()[:1] in ("", "y", "是"):
            code = subprocess.call([sys.executable, "-m", "pip", "install", "--target", VENDOR_DIR, "python-jobspy"])
            if code != 0:
                say(tr("安装失败。检查网络后再试;或者把上面的报错发给你用的 AI 助手。",
                       "Install failed. Check your connection and try again, or show the error to your AI assistant."))
                return
        else:
            return
    days = ask(tr("扫最近几天发布的岗位?[3]: ", "Scan jobs posted in the last how many days? [3]: ")).strip() or "3"
    if not days.isdigit():
        days = "3"
    run(["sweep.py", "new", days])
    run(["report.py"])


def do_track(ask: Ask, say: Say, run: Runner) -> None:
    url = clean_path(ask(tr("粘贴岗位链接开始跟踪(直接回车 = 检查所有在跟踪的岗位是否还在招):",
                            "Paste a job link to track it (press Enter to check all tracked jobs instead): ")))
    if url:
        run(["sweep.py", "add", url])
    else:
        run(["sweep.py", "live", "--log"])


def do_jd(ask: Ask, say: Say, run: Runner) -> None:
    raw = clean_path(ask(tr("把 JD 文件拖进窗口后回车(或直接回车改为粘贴文字):",
                            "Drag the JD file into this window and press Enter (or just Enter to paste text): ")))
    if raw:
        if not os.path.exists(raw):
            say(tr(f"找不到文件:{raw}", f"File not found: {raw}"))
            return
        run(["jd_check.py", raw])
        return
    text = read_pasted(ask, say)
    if not text:
        say(tr("没有收到内容。", "Nothing was pasted."))
        return
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(text)
        path = f.name
    try:
        run(["jd_check.py", path])
    finally:
        os.unlink(path)


def do_factcheck(ask: Ask, say: Say, run: Runner) -> None:
    raw = clean_path(ask(tr("把要核对的简历或求职信文件(.md / .txt)拖进窗口后回车:",
                            "Drag the CV or cover letter (.md / .txt) into this window and press Enter: ")))
    if not raw or not os.path.exists(raw):
        say(tr("找不到这个文件。", "File not found."))
        return
    args = ["fact_check.py", raw]
    from fact_check import _find_upwards  # local import keeps the menu fast to start
    if not _find_upwards("master-cv-data.md", os.path.dirname(os.path.abspath(raw))):
        master = clean_path(ask(tr("没在附近找到事实库 master-cv-data.md,把它拖进窗口后回车:",
                                   "No master-cv-data.md found nearby; drag your fact base into this window: ")))
        if not master or not os.path.exists(master):
            say(tr("没有事实库就无法核对。新建方法见「使用说明」第 4 步。",
                   "Nothing can be checked without a fact base. See step 4 of the guide."))
            return
        args += ["--master", master]
    run(args)


def do_setup(ask: Ask, say: Say, run: Runner) -> None:
    run_setup(ask, say)


def do_guide(ask: Ask, say: Say, run: Runner) -> None:
    path = GUIDE_EN if lang() == "en" else GUIDE_ZH
    say(tr(f"正在打开 {path}", f"Opening {path}"))
    try:
        open_path(path)
    except OSError:
        say(tr("打不开,请手动用记事本打开这个文件。", "Couldn't open it; open the file yourself with a text editor."))


def toggle_lang(ask: Ask, say: Say, run: Runner) -> None:
    os.environ[LANG_ENV] = "zh" if lang() == "en" else "en"


ACTIONS: list[tuple[str, tuple[str, str], Callable[[Ask, Say, Runner], None]]] = [
    ("1", ("查签证担保(公司在不在担保名册上)", "Check visa sponsorship (is the company on the register)"), do_sponsor),
    ("2", ("推荐岗位关键词(根据你的事实库)", "Suggest job titles (from your fact base)"), do_keywords),
    ("3", ("扫新岗位(LinkedIn + Indeed),结果存成表格", "Scan for new jobs (LinkedIn + Indeed), saved as a table"), do_scan),
    ("4", ("跟踪岗位:加一个链接 / 检查是否还在招", "Track jobs: add a link / check they're still open"), do_track),
    ("5", ("体检一份 JD(担保、Senior、年限、薪资)", "Check a job description (sponsorship, seniority, years, pay)"), do_jd),
    ("6", ("核对简历(每句都要在事实库里有出处)", "Fact-check a CV against your fact base"), do_factcheck),
    ("7", ("首次设置 / 修改搜索设置", "Setup / change search settings"), do_setup),
    ("8", ("打开使用说明", "Open the guide"), do_guide),
    ("L", ("English", "中文"), toggle_lang),
]


def render_menu() -> str:
    lines = ["", "=" * 46, tr("  证据优先求职工具 · 菜单", "  Evidence-first job search · Menu"), "=" * 46]
    for key, (zh, en), _ in ACTIONS:
        lines.append(f"  {key}. {tr(zh, en)}")
    lines.append("  0. " + tr("退出", "Quit"))
    return "\n".join(lines)


def loop(ask: Ask = input, say: Say = print, run: Runner = run_script) -> int:
    actions = {key.lower(): fn for key, _, fn in ACTIONS}
    while True:
        say(render_menu())
        choice = ask(tr("输入编号后回车:", "Type a number and press Enter: ")).strip().lstrip("﻿").strip().lower()
        if choice in ("0", "q", "quit", "exit", "退出"):
            say(tr("再见。", "Bye."))
            return 0
        action = actions.get(choice)
        if action is None:
            say(tr("没有这个选项,请输入菜单里的编号。", "That's not an option; type one of the numbers."))
            continue
        try:
            action(ask, say, run)
        except KeyboardInterrupt:
            say(tr("\n已中断。", "\nStopped."))
        if action is not toggle_lang:
            ask(tr("\n按回车回到菜单…", "\nPress Enter to return to the menu…"))


def main(argv: list[str] | None = None) -> int:
    apply_lang_arg(list(sys.argv[1:] if argv is None else argv))
    try:
        return loop()
    except (KeyboardInterrupt, EOFError):
        return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
