# -*- coding: utf-8 -*-
"""Output language for every script: Chinese by default, English with --lang en or JOBSEARCH_LANG=en.

The choice is kept in an environment variable so that modules imported by a script (jd_check inside
boardsweep, sponsor_check inside sweep) and sweep.py's worker subprocesses all follow it.
"""
from __future__ import annotations

import os

LANG_ENV = "JOBSEARCH_LANG"
SUPPORTED = ("zh", "en")


def lang() -> str:
    return "en" if os.environ.get(LANG_ENV, "").lower().startswith("en") else "zh"


def tr(zh: str, en: str) -> str:
    """Pick the string for the current output language."""
    return en if lang() == "en" else zh


def apply_lang_arg(argv: list[str]) -> list[str]:
    """Consume `--lang xx` / `--lang=xx` from argv, set the language, and return the remaining arguments."""
    out, i = [], 0
    while i < len(argv):
        arg = argv[i]
        value = None
        if arg == "--lang" and i + 1 < len(argv):
            value, i = argv[i + 1], i + 2
        elif arg.startswith("--lang="):
            value, i = arg.split("=", 1)[1], i + 1
        else:
            out.append(arg)
            i += 1
            continue
        if value.lower() not in SUPPORTED:
            raise SystemExit(f"--lang must be one of {', '.join(SUPPORTED)} (got {value!r})")
        os.environ[LANG_ENV] = value.lower()
    return out
