# -*- coding: utf-8 -*-
"""
JD 自动体检 —— 把 5 道 Gate 里能机器判的部分先过一遍:
  · 担保措辞:JD 明写不担保 / 可担保 / 只要求工作许可(复用 sponsor_check.scan_jd)
  · 安全审查:SC / DV clearance 通常要求在英国长期居住,持签证者基本拿不到,单独标出
  · 藏在正文里的 Senior:"We're looking for a Senior …"(标题里不一定有)
  · 年限要求:"5+ years of experience" -> 5(取所有带 experience 的要求里最低的一个)
  · 年薪 vs Skilled Worker 门槛:标准 £41,700;降低标准(新入行者等)下限 £33,400

门槛数字来自 gov.uk,会随政策调整;按职业代码的 going rate 可能更高,本脚本只比总门槛。

用法:被 boardsweep.py 调用;也可单独跑  python jd_check.py JD.txt [--max-years 3]
"""
from __future__ import annotations

import argparse
import html
import os
import re
import sys
from dataclasses import dataclass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
from sponsor_check import scan_jd  # noqa: E402  (same folder)

STANDARD_THRESHOLD = 41_700   # Skilled Worker 'standard' salary
FLOOR_THRESHOLD = 33_400      # lowest of the reduced rates (e.g. new entrants), non-health/education
THRESHOLD_SOURCE = "https://www.gov.uk/skilled-worker-visa/your-job"
THRESHOLD_CHECKED = "2026-10-13"
MIN_ANNUAL, MAX_ANNUAL = 15_000, 500_000

WORD_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
            "nine": 9, "ten": 10}
_NUM = r"(\d{1,2}|" + "|".join(WORD_NUM) + r")"
YEARS = re.compile(_NUM + r"\s*\+?\s*(?:(?:-|–|—|to)\s*" + _NUM + r"\s*\+?\s*)?years?(?:['’]s?)?"
                   r"(?=[^.;]{0,60}\bexperience)", re.I)
SENIOR = re.compile(r"\b(?:looking for|seeking|hiring|as|you(?:'ll| will) be|join us as|role of|position of)\s+"
                    r"(?:an?\s+|our\s+(?:next\s+)?|the\s+)?(senior|lead|principal|staff)\b", re.I)
_AMOUNT = r"(\d{1,3}(?:,\d{3})+|\d{2,3}(?:\.\d)?\s?[kK])"
SALARY = re.compile(r"£\s?" + _AMOUNT + r"(?![\d,])(?:\s*(?:-|–|—|to)\s*(?:£\s?)?" + _AMOUNT + r"(?![\d,]))?")
NOT_ANNUAL = re.compile(r"^\W{0,3}(?:per\s+(?:hour|day|week|month)|/\s?(?:hr|hour|day|d|week|month)|"
                        r"an hour|a day|hourly|daily|weekly|monthly|ph\b|pd\b)", re.I)
PAY_WORDS = re.compile(r"salary|compensation|\bpay\b|\bbase\b|per annum|p\.a\.|annual|ote\b", re.I)
CLEARANCE = re.compile(r"\b(?:sc|dv|ctc|security)[- ]?(?:clearance|cleared)\b|\bdeveloped vetting\b", re.I)
RIGHT_TO_WORK = re.compile(r"right to work|work(?:ing)? (?:authori[sz]ation|permit)|eligib\w* to work", re.I)
SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass(frozen=True)
class JdReport:
    sponsor: str            # negative / positive / check / ""
    years: int | None
    senior: bool
    salary_low: int | None
    salary_high: int | None
    salary_flag: str        # ok / below_standard / below_floor / ""
    clearance: bool = False  # SC / DV 安全审查


def html_to_text(raw: str) -> str:
    """Greenhouse 的 content 是转义过的 HTML:先反转义,再去标签,再反转义一次实体。"""
    text = re.sub(r"<[^>]+>", " ", html.unescape(raw or ""))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _num(token: str) -> int:
    return WORD_NUM.get(token.lower()) if token.lower() in WORD_NUM else int(token)


def required_years(text: str) -> int | None:
    found = [_num(m.group(1)) for m in YEARS.finditer(text or "")]
    return min(found) if found else None


def senior_in_body(text: str) -> bool:
    return SENIOR.search(text or "") is not None


def _amount(token: str) -> int:
    token = token.replace(",", "").replace(" ", "")
    return int(float(token[:-1]) * 1000) if token[-1:] in "kK" else int(token)


def _salaries_in(sentence: str) -> list[tuple[int, int]]:
    out = []
    for m in SALARY.finditer(sentence):
        if NOT_ANNUAL.match(sentence[m.end():m.end() + 20]):
            continue
        low = _amount(m.group(1))
        high = _amount(m.group(2)) if m.group(2) else low
        if MIN_ANNUAL <= low <= MAX_ANNUAL and MIN_ANNUAL <= high <= MAX_ANNUAL:
            out.append((low, high))
    return out


def annual_gbp_salary(text: str) -> tuple[int, int] | None:
    """返回 (下限, 上限) 年薪;优先取提到 salary / compensation 的那句。"""
    sentences = [s for s in SENTENCE.split(text or "") if "£" in s]
    for wanted in (True, False):
        for s in sentences:
            if bool(PAY_WORDS.search(s)) == wanted or not wanted:
                hits = _salaries_in(s)
                if hits:
                    return hits[0]
    return None


def salary_flag(low: int | None) -> str:
    if low is None:
        return ""
    if low >= STANDARD_THRESHOLD:
        return "ok"
    return "below_standard" if low >= FLOOR_THRESHOLD else "below_floor"


def analyze(text: str, compensation: str = "") -> JdReport:
    # "check" 只算真正讲工作许可的句子;只讲安全审查的句子单独记为 clearance
    signals = {h.signal for h in scan_jd(text or "")
               if h.signal != "check" or RIGHT_TO_WORK.search(h.sentence)}
    sponsor = next((s for s in ("negative", "positive", "check") if s in signals), "")
    salary = annual_gbp_salary(text) or annual_gbp_salary(compensation)
    low, high = salary if salary else (None, None)
    return JdReport(sponsor, required_years(text), senior_in_body(text), low, high, salary_flag(low),
                    clearance=CLEARANCE.search(text or "") is not None)


def _k(value: int) -> str:
    return f"{value / 1000:g}k"


def tags(report: JdReport, max_years: int = 3) -> list[str]:
    out = []
    out += {"negative": ["JD❌不担保"], "positive": ["JD✅可担保"], "check": ["JD⚠️需工作许可"]}.get(report.sponsor, [])
    if report.clearance:
        out.append("JD⚠️要安全审查(SC/DV)")
    if report.senior:
        out.append("正文Senior")
    if report.years is not None and report.years > max_years:
        out.append(f"要{report.years}年+")
    if report.salary_flag == "below_standard":
        out.append(f"£{_k(report.salary_low)}<£{_k(STANDARD_THRESHOLD)}标准")
    elif report.salary_flag == "below_floor":
        out.append(f"£{_k(report.salary_low)}<£{_k(FLOOR_THRESHOLD)}下限")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="JD 体检:担保措辞 / 隐藏 Senior / 年限 / 年薪 vs 签证门槛")
    p.add_argument("files", nargs="+", help="JD 文本或 markdown 文件")
    p.add_argument("--max-years", type=int, default=3, help="超过这个年限就标出来(默认 3)")
    args = p.parse_args(argv)
    for path in args.files:
        with open(path, "r", encoding="utf-8") as f:
            report = analyze(f.read())
        found = tags(report, args.max_years)
        print(f"== {path}")
        print("  " + (" · ".join(found) if found else "没发现问题(JD 没提担保也不代表能办,首轮沟通时直接问)"))
        if report.salary_low:
            print(f"  年薪 £{report.salary_low:,}–£{report.salary_high:,}"
                  f"(门槛:标准 £{STANDARD_THRESHOLD:,} / 降低标准下限 £{FLOOR_THRESHOLD:,},{THRESHOLD_CHECKED} 核对 gov.uk;"
                  "按职业代码的 going rate 可能更高)")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
