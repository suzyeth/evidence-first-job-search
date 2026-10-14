# -*- coding: utf-8 -*-
"""
简历 / 求职信事实核对 —— 渲染 PDF 之前跑,拦下 AI(或自己)编出来的东西。

检查项:
  FAIL  number        简历里的数字(含 % / k / x)在事实库里找不到
  FAIL  skill         Skills 行里的技能在事实库里找不到(单个词,或多词但不到一半的词有出处)
  FAIL  metric        出现事实库里没有的指标缩写(如把 paying-user rate 写成 ARPU)
  FAIL  confidential  命中保密词清单(前雇主代号、营收数字等)
  FAIL  placeholder   残留 [FILL] / TODO / TBD
  FAIL  date          任职 / 在校起止时间在事实库对不上(年份不同,或两边都写了月份但月份不同)
  FAIL  role          经历标题行里的职位 / 公司 / 学校在事实库找不到;带 Senior / Lead 等级别词的职位
                      必须出现在事实库的标题行或带日期的任职记录行,叙述句里提到不算(防职位注水)
  WARN  role          职位 / 公司 / 学校名只有一部分词对得上(多半是写法不同)
  WARN  skill         多词技能只有一部分词在事实库出现(换了说法的可能性大,人工确认)
  WARN  buzzword      passionate / driven / spearheaded 等空话
事实库中标题带 🔒 / 内部备注 / internal notes / confidential 的小节**不算证据**(那是内部备注,不能出现在对外文档里)。
被检查文件里的 HTML 注释 <!-- … --> 不参与数字 / 技能 / 指标 / 占位符检查(渲染成 PDF 后看不见,常用来放内部备注);
**保密词仍然扫注释**:pandoc 导出的 HTML 会原样保留注释,发出去就会泄露。

用法(Python 3.10+,只用标准库):
  python fact_check.py applications/acme/resume_acme.md
  python fact_check.py resume.md cover-letter.md --master master-cv-data.md --confidential confidential-terms.txt
  python fact_check.py resume.md --json
退出码:有 FAIL = 1(可以挂在渲染脚本前当闸门),否则 0。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass

NUMBER = re.compile(r"[£$€]?(?<![\w.])\d[\d,]*(?:\.\d+)?(?:\s?%|[kKmMxX](?![a-zA-Z]))?")
URL = re.compile(r"\]\([^)]*\)|https?://\S+|www\.\S+")
LIST_MARKER = re.compile(r"^\s*\d+[.)]\s+", re.M)
SKILLS_LINE = re.compile(r"^\s*[*_#\-\s]*(?:key\s+|technical\s+|core\s+)?skills?\b[*_\s]*[:：][*_\s]*(.*)$",
                         re.I)
SKILLS_HEADING = re.compile(r"^#{1,6}\s+.*\bskills?\b", re.I)
HEADING = re.compile(r"^(#{1,6})\s")
INTERNAL_HEADING = re.compile(r"🔒|内部备注|内部信息|internal[- ]only|internal notes?|\bconfidential\b|保密", re.I)
CONTACT = re.compile(r"\S+@\S+|\+\d[\d\s()-]{7,}\d|\b0\d{3,4}[\s-]?\d{3}[\s-]?\d{3,4}\b")
HUMAN_LANGUAGES = {"english", "mandarin", "chinese", "cantonese", "french", "spanish", "german", "italian",
                   "japanese", "korean", "portuguese", "arabic", "hindi", "russian", "dutch", "polish", "turkish"}
PARTIAL_SKILL_RATIO = 0.5    # 多词技能有这么多比例的实词在事实库出现,就从 FAIL 降为 WARN
STOPWORDS = {"and", "or", "the", "of", "for", "with", "in", "on", "to", "a", "an", "via", "using"}
METRIC = re.compile(r"\b(ARPPU|ARPU|DAU|MAU|WAU|LTV|CAC|ROAS|ROI|CTR|CVR|NPS|MRR|ARR|GMV|AOV|CPI|D(?:1|3|7|14|30|60|90))\b")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
PLACEHOLDER = re.compile(r"\[FILL[^\]]*\]|\bTODO\b|\bTBD\b|\bXXX\b|lorem ipsum", re.I)
BUZZWORD = re.compile(r"(?<![\w-])(passionate|driven|dedicated|hard-?working|detail-oriented|spearhead(?:ed|ing)?|"
                      r"leverag(?:ed|ing)|synerg(?:y|ies)|go-getter|rock ?star|ninja|guru|self-starter)\b", re.I)


@dataclass(frozen=True)
class Finding:
    level: str      # FAIL / WARN
    rule: str
    item: str
    detail: str


# ---------------------------------------------------------------- parsing

def public_master(master: str) -> str:
    """去掉事实库里的内部备注小节(标题含 🔒 / 内部 / internal)。"""
    kept, skip_level = [], 0
    for line in master.splitlines():
        m = HEADING.match(line)
        if m:
            level = len(m.group(1))
            if skip_level and level <= skip_level:
                skip_level = 0
            if not skip_level and INTERNAL_HEADING.search(line):
                skip_level = level
        if not skip_level:
            kept.append(line)
    return "\n".join(kept)


def _normalise_number(raw: str) -> str:
    token = raw.lstrip("£$€").replace(",", "").replace(" ", "")
    return token[:-1] + token[-1].lower() if token[-1:].isalpha() else token


def extract_numbers(text: str) -> set[str]:
    text = LIST_MARKER.sub("", CONTACT.sub(" ", URL.sub(" ", text)))
    return {_normalise_number(m.group(0)) for m in NUMBER.finditer(text)}


def canonical_number(token: str) -> str:
    """'200k' 与 '200000' 视为同一个数;% 和 x 保留,因为 8% 和 8 不是一回事。"""
    multiplier = {"k": 1_000, "m": 1_000_000}.get(token[-1:])
    if multiplier is None:
        return token
    value = float(token[:-1]) * multiplier
    return str(int(value)) if value.is_integer() else str(value)


def _split_skills(raw: str) -> list[str]:
    """按分隔符切,但不切括号里面的;只保留括号外的主体(括号里是细节说明,不逐个核对)。"""
    parts, buf, depth = [], [], 0
    for ch in raw.replace("**", ""):
        if ch == "(":
            depth += 1
        elif ch == ")" and depth:
            depth -= 1
        if depth == 0 and ch in ",·|;/•":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    items = []
    for part in parts:
        # 句末标点不是技能名的一部分("C#." -> "C#");只去尾部,".NET" 的前导点要保留
        head = re.sub(r"\([^)]*\)?", "", part).strip(" *_-\t").rstrip(" .;:。;").strip()
        if head and head.lower() not in HUMAN_LANGUAGES:
            items.append(head)
    return items


def extract_skills(text: str) -> list[str]:
    skills, in_section, section_level = [], False, 0
    for line in text.splitlines():
        heading = HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            if in_section and level <= section_level:
                in_section = False
            if SKILLS_HEADING.match(line):
                in_section, section_level = True, level
                continue
        m = SKILLS_LINE.match(line)
        if m:
            skills += _split_skills(m.group(1))
        elif in_section and line.strip().startswith(("-", "*", "•")):
            body = line.strip().lstrip("-*• ")
            body = body.split(":", 1)[1] if ":" in body else body
            skills += _split_skills(body)
    return skills


def parse_terms(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]


def _stems(text: str) -> set[str]:
    return {w[:5] for w in re.findall(r"[a-z0-9+#]+", text.lower()) if w not in STOPWORDS}


def _skill_evidenced(skill: str, evidence: str, evidence_stems: set[str]) -> bool:
    if _mentions(skill, evidence):
        return True
    words = _stems(skill)
    # 多词描述性技能:措辞可以不同,但每个实词都得在事实库出现过
    return len(words) >= 2 and words <= evidence_stems


def _mentions(term: str, text: str) -> bool:
    return re.search(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", text, re.I) is not None


def _term_pattern(term: str) -> re.Pattern:
    return re.compile(term[3:], re.I) if term.startswith("re:") else re.compile(re.escape(term), re.I)


# ---------------------------------------------------------------- checks

# ---------------------------------------------------------------- dates & roles

_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10,
           "nov": 11, "dec": 12}
_MONTH_WORD = (r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
               r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?")


def _endpoint(tag: str) -> str:
    return (rf"(?:(?P<{tag}mon>{_MONTH_WORD})\.?\s+)?(?P<{tag}y>(?:19|20)\d{{2}})"
            rf"(?:[-/.](?P<{tag}mm>1[0-2]|0?[1-9])(?!\d))?")


RANGE = re.compile(_endpoint("a") + r"\s*(?:-|–|—|~|to|至)\s*(?:(?P<present>present|current|now|today|至今|今)\b|"
                   + _endpoint("b") + r")", re.I)
SENIORITY = re.compile(r"\b(senior|sr|lead|principal|staff|head|director|manager|chief|vp|founding)\b", re.I)


def _month(match: re.Match, tag: str) -> int | None:
    word, number = match.group(f"{tag}mon"), match.group(f"{tag}mm")
    return _MONTHS[word[:3].lower()] if word else (int(number) if number else None)


def parse_ranges(text: str) -> list[tuple]:
    """'October 2024 — Present' -> [((2024, 10), ('present', None))];年-月、纯年份、至今都认。"""
    out = []
    for m in RANGE.finditer(text or ""):
        end = ("present", None) if m.group("present") else (int(m.group("by")), _month(m, "b"))
        out.append(((int(m.group("ay")), _month(m, "a")), end))
    return out


def _same_period(a: tuple, b: tuple) -> bool:
    """年份必须一致;两边都写了月份时月份也要一致,一边没写月份不算矛盾。"""
    (a_start, a_end), (b_start, b_end) = a, b
    for x, y in ((a_start, b_start), (a_end, b_end)):
        if x[0] != y[0] or (x[1] and y[1] and x[1] != y[1]):
            return False
    return True


def _date_findings(resume: str, evidence: str) -> list[Finding]:
    known = parse_ranges(evidence)
    out = []
    for m in RANGE.finditer(resume):
        claimed = parse_ranges(m.group(0))[0]
        if any(_same_period(claimed, k) for k in known):
            continue
        same_years = any(claimed[0][0] == k[0][0] and claimed[1][0] == k[1][0] for k in known)
        out.append(Finding("FAIL", "date", m.group(0).strip(),
                           "月份和事实库对不上" if same_years else "这段起止时间在事实库里找不到(任期是不是写长了?)"))
    return out


def _header_segments(line: str) -> list[str]:
    """经历标题行去掉日期、markdown、括号注释后,按 · | , @ 和带空格的破折号切成 职位 / 公司 / 地点。"""
    text = RANGE.sub(" ", line)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)          # [链接文字](url) -> 链接文字
    text = re.sub(r"<[^>]+>|\([^)]*\)|[#*_`]", " ", text)
    parts = re.split(r"\s*[·|•,@]\s*|\s+[—–-]\s+", text)
    return [p.strip() for p in parts if len(p.strip()) > 1 and not p.strip().isdigit()]


def _titles_of_record(evidence: str) -> str:
    """事实库里的"任职记录":标题行和带日期区间的行。叙述句(「scope 达到 Senior 级别」)不算。"""
    return "\n".join(l for l in evidence.splitlines() if l.lstrip().startswith("#") or RANGE.search(l))


def _role_findings(resume: str, evidence: str, evidence_stems: set[str]) -> list[Finding]:
    records = _titles_of_record(evidence)
    out = []
    for line in resume.splitlines():
        stripped = line.strip()
        if not (stripped.startswith("#") or stripped.startswith("**")) or not RANGE.search(stripped):
            continue
        for seg in _header_segments(stripped):
            # 带级别词的职位只认任职记录;公司 / 学校 / 地点全文查找即可
            if _mentions(seg, records if SENIORITY.search(seg) else evidence):
                continue
            words = _stems(seg)
            partly = len(words) >= 2 and len(words & evidence_stems) / len(words) >= PARTIAL_SKILL_RATIO
            if partly and not SENIORITY.search(seg):
                out.append(Finding("WARN", "role", seg, "只有部分词在事实库出现:确认职位 / 公司 / 学校的写法"))
            else:
                out.append(Finding("FAIL", "role", seg,
                                   "职位级别在事实库找不到(注水?)" if SENIORITY.search(seg)
                                   else "职位 / 公司 / 学校名在事实库找不到"))
    return out


def check(resume: str, master: str, confidential: list[str]) -> list[Finding]:
    full_text = resume                       # 保密词要扫全文:pandoc 导出的 HTML 会原样保留注释
    resume = HTML_COMMENT.sub(" ", resume)
    evidence = public_master(master)
    evidence_numbers = {canonical_number(n) for n in extract_numbers(evidence)}
    evidence_stems = _stems(evidence)
    findings: list[Finding] = _date_findings(resume, evidence) + _role_findings(resume, evidence, evidence_stems)

    # 日期区间已由 date 规则核对,数字规则里不再重复报年份
    missing = [n for n in extract_numbers(RANGE.sub(" ", resume)) if canonical_number(n) not in evidence_numbers]
    for num in sorted(missing, key=lambda n: resume.find(n)):
        findings.append(Finding("FAIL", "number", num, "事实库里找不到这个数字"))
    for skill in dict.fromkeys(extract_skills(resume)):
        if _skill_evidenced(skill, evidence, evidence_stems):
            continue
        words = _stems(skill)
        if len(words) >= 2 and len(words & evidence_stems) / len(words) >= PARTIAL_SKILL_RATIO:
            # 描述性长短语,一半以上实词有出处:多半是同一件事换了说法,提醒人工确认,不拦截
            findings.append(Finding("WARN", "skill", skill,
                                    "只有部分词在事实库出现:确认措辞,或把这个写法补进事实库「对外关键词」"))
        else:
            findings.append(Finding("FAIL", "skill", skill, "Skills 里的技能在事实库没有证据"))
    for metric in dict.fromkeys(METRIC.findall(resume)):
        if not re.search(r"\b" + metric + r"\b", evidence):
            findings.append(Finding("FAIL", "metric", metric, "事实库没有这个指标,检查是不是换了指标说法"))
    for term in confidential:
        pattern = _term_pattern(term)
        visible, anywhere = pattern.search(resume), pattern.search(full_text)
        if visible:
            findings.append(Finding("FAIL", "confidential", visible.group(0), "命中保密词清单"))
        elif anywhere:
            findings.append(Finding("FAIL", "confidential", anywhere.group(0),
                                    "命中保密词清单(在 HTML 注释里:PDF 看不见,但导出的 HTML 会保留)"))
    for m in dict.fromkeys(x.group(0) for x in PLACEHOLDER.finditer(resume)):
        findings.append(Finding("FAIL", "placeholder", m, "残留占位符"))
    for word in dict.fromkeys(x.group(0) for x in BUZZWORD.finditer(resume)):
        findings.append(Finding("WARN", "buzzword", word, "空话,换成具体动作或数字"))
    return findings


# ---------------------------------------------------------------- CLI

def _find_upwards(filename: str, start: str) -> str | None:
    here = os.path.abspath(start)
    for _ in range(4):
        candidate = os.path.join(here, filename)
        if os.path.exists(candidate):
            return candidate
        here = os.path.dirname(here)
    return None


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def render(path: str, findings: list[Finding]) -> str:
    fails = [f for f in findings if f.level == "FAIL"]
    head = f"== {path}  " + ("✅ 通过" if not fails else f"❌ {len(fails)} 项不通过")
    lines = [head] + [f"  {'❌' if f.level == 'FAIL' else '⚠️'} [{f.rule}] {f.item} —— {f.detail}" for f in findings]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="简历 / 求职信事实核对(对照 master-cv-data.md)")
    p.add_argument("files", nargs="+", help="要检查的简历 / 求职信 markdown")
    p.add_argument("--master", help="事实库路径(默认向上查找 master-cv-data.md)")
    p.add_argument("--confidential", help="保密词清单,一行一个,re: 开头为正则(默认向上查找 confidential-terms.txt)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    start = os.path.dirname(os.path.abspath(args.files[0]))
    master_path = args.master or _find_upwards("master-cv-data.md", start)
    if not master_path or not os.path.exists(master_path):
        print("❌ 找不到 master-cv-data.md,用 --master 指定。没有事实库就无法核对。", file=sys.stderr)
        return 2
    conf_path = args.confidential or _find_upwards("confidential-terms.txt", start)
    confidential = parse_terms(_read(conf_path)) if conf_path and os.path.exists(conf_path) else []
    if not confidential and not args.json:
        print("⚠️ 没有保密词清单(confidential-terms.txt),本次不检查保密项。\n")

    master, exit_code, report = _read(master_path), 0, {}
    for path in args.files:
        findings = check(_read(path), master, confidential)
        report[path] = [asdict(f) for f in findings]
        if any(f.level == "FAIL" for f in findings):
            exit_code = 1
        if not args.json:
            print(render(path, findings) + "\n")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif exit_code:
        print("有 ❌ 项:要么改简历,要么(确实做过的)先补进 master-cv-data.md 再派生。")
    return exit_code


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
