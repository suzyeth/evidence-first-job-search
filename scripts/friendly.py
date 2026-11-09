# -*- coding: utf-8 -*-
"""Helpers that keep non-programmers away from JSON syntax and regular expressions.

- explain_json_error(): turns json's "Expecting value: line 12 column 3" into a sentence that says what to fix.
- words_to_regex(): turns plain job titles ("product analyst", "live ops") into the regex the scripts need.
- clean_path(): strips the quotes a terminal adds when a file is dragged into the window.
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from i18n import tr  # noqa: E402  (same folder)


def _line_at(text: str, lineno: int) -> str:
    lines = text.splitlines()
    return lines[lineno - 1] if 1 <= lineno <= len(lines) else ""


def _prev_code_line(text: str, lineno: int) -> tuple[int, str]:
    """The nearest non-blank line above `lineno` (where a stray or missing comma usually sits)."""
    lines = text.splitlines()
    for n in range(min(lineno - 1, len(lines)), 0, -1):
        if lines[n - 1].strip():
            return n, lines[n - 1]
    return 0, ""


def _diagnose(text: str, exc: json.JSONDecodeError) -> str:
    line = _line_at(text, exc.lineno)
    stripped = line.strip()
    prev_no, prev = _prev_code_line(text, exc.lineno)
    msg = exc.msg
    if any(q in text for q in "“”‘’"):
        return tr("文件里有中文/弯引号(“ ” ‘ ’)。JSON 只认英文直引号 \",把它们改成 \" 。",
                  "The file contains curly quotes (“ ” ‘ ’). JSON only accepts straight double quotes \"; replace them.")
    before = text[:exc.pos].rstrip()
    if text[exc.pos:exc.pos + 1] in ("]", "}") and before.endswith(","):
        comma_line = before.count("\n") + 1
        return tr(f"第 {comma_line} 行多了一个逗号:列表或括号里的最后一项后面不能有逗号,删掉它。",
                  f"Line {comma_line} has an extra comma: the last item before a closing bracket can't have one. "
                  "Delete it.")
    if msg.startswith("Expecting property name") and prev.rstrip().endswith(","):
        return tr(f"第 {prev_no} 行末尾多了一个逗号:最后一项后面不能有逗号,删掉它。",
                  f"Line {prev_no} ends with an extra comma after the last item. Delete it.")
    if msg.startswith("Expecting ',' delimiter"):
        return tr(f"第 {prev_no or exc.lineno} 行和第 {exc.lineno} 行之间少了一个逗号:每一项之间要用英文逗号隔开。",
                  f"A comma is missing between line {prev_no or exc.lineno} and line {exc.lineno}: "
                  "items must be separated by commas.")
    if msg.startswith("Invalid \\escape"):
        return tr(f"第 {exc.lineno} 行有单个反斜杠 \\。JSON 里要写成两个 \\\\(例如 \\\\b)。",
                  f"Line {exc.lineno} has a single backslash \\. JSON needs it doubled (for example \\\\b).")
    if "'" in stripped and '"' not in stripped:
        return tr(f"第 {exc.lineno} 行用了单引号 '。JSON 只认双引号 \",把 ' 改成 \" 。",
                  f"Line {exc.lineno} uses single quotes '. JSON only accepts double quotes \".")
    if msg.startswith("Unterminated string"):
        return tr(f"第 {exc.lineno} 行有一个引号没有配对,检查这一行的 \" 是不是成对出现。",
                  f"Line {exc.lineno} has a quote that is never closed; check that its \" come in pairs.")
    return tr(f"第 {exc.lineno} 行第 {exc.colno} 个字符附近格式不对。",
              f"Something is wrong near line {exc.lineno}, character {exc.colno}.")


def explain_json_error(path: str, text: str, exc: json.JSONDecodeError) -> str:
    """A plain-language explanation of a JSON syntax error, with the offending line quoted."""
    line = _line_at(text, exc.lineno)
    shown = f"\n    {exc.lineno} | {line.rstrip()}" if line else ""
    hint = tr("\n改不好的话:删掉这个文件,重新运行「首次设置」(setup_wizard.py)自动生成一份。",
              "\nIf you can't fix it: delete the file and run the setup wizard (setup_wizard.py) to create a new one.")
    return tr(f"配置文件格式有误:{path}\n  {_diagnose(text, exc)}{shown}{hint}",
              f"The config file has a formatting error: {path}\n  {_diagnose(text, exc)}{shown}{hint}")


def load_json_friendly(path: str):
    """json.load with a plain-language SystemExit on syntax errors (FileNotFoundError is left to the caller)."""
    with open(path, "r", encoding="utf-8-sig") as f:
        text = f.read()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SystemExit(explain_json_error(path, text, exc))


def _phrase_pattern(phrase: str) -> str:
    words = [w for w in re.split(r"[\s\-_/]+", phrase.strip().lower()) if w]
    if not words:
        return ""
    # British/American spellings are common in titles: monetisation / monetization, optimise / optimize.
    parts = [re.sub(r"i[sz](?=ation|e[sdr]?$|ing$)", "i[sz]", re.escape(w)) for w in words]
    return r"[\s\-_/]*".join(parts)


def words_to_regex(phrases) -> str:
    """Plain titles -> one case-insensitive regex that matches any of them ("live ops" also matches "live-ops").

    Every phrase starts at a word boundary ("mi analyst" must not match "academi analyst"); single short words
    are bounded on both sides so "ai" does not match "maintenance".
    """
    out, seen = [], set()
    for phrase in phrases:
        pat = _phrase_pattern(str(phrase))
        if not pat or pat in seen:
            continue
        seen.add(pat)
        short = len(phrase.strip()) <= 3 and " " not in phrase.strip()
        out.append(rf"\b{pat}\b" if short else rf"\b{pat}")
    return "|".join(out)


def clean_path(raw: str) -> str:
    """Strip the quotes/whitespace a terminal adds around a dragged-in file path."""
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    if value.startswith("& '") and value.endswith("'"):  # PowerShell drag-and-drop
        value = value[3:-1]
    return value.strip()


def parse_choices(raw: str, count: int) -> list[int]:
    """'1,3,5-7' -> [1, 3, 5, 6, 7] (1-based, clipped to 1..count, order kept, no duplicates)."""
    picked: list[int] = []
    for part in re.split(r"[,\s，、]+", raw.strip()):
        if not part:
            continue
        m = re.fullmatch(r"(\d+)\s*[-~–]\s*(\d+)", part)
        if m:
            lo, hi = sorted((int(m.group(1)), int(m.group(2))))
            values = range(lo, hi + 1)
        elif part.isdigit():
            values = [int(part)]
        else:
            continue
        for v in values:
            if 1 <= v <= count and v not in picked:
                picked.append(v)
    return picked
