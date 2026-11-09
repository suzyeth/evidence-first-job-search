# -*- coding: utf-8 -*-
"""根据你的事实库(master-cv-data.md)推荐更宽的岗位搜索词,每个推荐都附上事实库里的出处。

用法(Python 3.10+,只用标准库):
  python keyword_suggest.py                      # 自动向上查找 master-cv-data.md,打印三档推荐
  python keyword_suggest.py --master 路径/master-cv-data.md
  python keyword_suggest.py --from-logs          # 再用 logs/ 里的历史扫描统计每个词实际搜到过多少岗位
  python keyword_suggest.py --apply core         # 把「核心」档写进 sweep_config.json(先备份为 .bak)
  python keyword_suggest.py --apply 1,3,5-8      # 按编号挑选写入
  python keyword_suggest.py --json               # 机器可读输出

原则:只推荐事实库里有证据的方向;写在 ❌ / "没做过" / "不写" 行里的内容不算证据。
族谱在 role_taxonomy.json,可以自己增删标题。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from friendly import load_json_friendly, parse_choices, words_to_regex  # noqa: E402
from i18n import apply_lang_arg, lang, tr  # noqa: E402

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TAXONOMY_PATH = os.path.join(SCRIPT_DIR, "role_taxonomy.json")
CONFIG_PATH = os.path.join(SCRIPT_DIR, "sweep_config.json")
EXAMPLE_CONFIG_PATH = os.path.join(SCRIPT_DIR, "sweep_config.example.json")
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")

TIERS = ("core", "adjacent", "stretch")
TIER_NAMES = {"core": ("核心", "Core"), "adjacent": ("相邻", "Adjacent"), "stretch": ("拉伸", "Stretch")}
CORE_SCORE, ADJACENT_SCORE, STRETCH_SCORE = 0.6, 0.35, 0.15

# A line that records what you have NOT done is not evidence for it.
NEGATIVE_LINE = re.compile(r"❌|没做过|没有做过|不要写|不写|不得写|不能写|no evidence|never used|did not|didn't|not done", re.I)


@dataclass(frozen=True)
class Signal:
    sid: str
    label: str
    hits: int                 # how many evidence lines mention it
    strength: float           # 0..1: hits relative to how long the fact base is
    evidence: tuple[str, ...]

    @property
    def found(self) -> bool:
        return self.hits > 0


@dataclass
class Suggestion:
    title: str
    track: str
    family: str
    level: str
    tier: str
    score: float
    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    already_searched: bool = False
    seen_in_logs: int | None = None


# ---------------------------------------------------------------- evidence

def _alt_pattern(alt: str) -> re.Pattern:
    """ASCII alternatives get a left word boundary (and a right one when short); CJK ones match anywhere."""
    if re.search(r"[^\x00-\x7f]", alt):
        return re.compile(re.escape(alt))
    left = r"(?<![a-z0-9])"
    right = r"(?![a-z0-9])" if len(alt) <= 4 else ""
    return re.compile(left + re.escape(alt.lower()) + right)


def evidence_lines(master: str) -> list[str]:
    lines = []
    for raw in master.splitlines():
        line = raw.strip()
        if not line or line.startswith(">") or NEGATIVE_LINE.search(line):
            continue
        lines.append(line)
    return lines


def _trim(line: str, limit: int = 110) -> str:
    line = re.sub(r"[*_`#]+", "", line).strip(" -")
    return line if len(line) <= limit else line[: limit - 1] + "…"


def full_strength_hits(line_count: int) -> float:
    """Mentions needed for a signal to count fully: 3 in a short fact base, more in a long one."""
    return max(3.0, line_count / 100)


def find_signals(master: str, taxonomy: dict) -> dict[str, Signal]:
    lines = evidence_lines(master)
    lowered = [line.lower() for line in lines]
    full = full_strength_hits(len(lines))
    out = {}
    for sid, spec in taxonomy["signals"].items():
        pats = [_alt_pattern(a) for a in spec["any"]]
        hits = [lines[i] for i, low in enumerate(lowered) if any(p.search(low) for p in pats)]
        label = spec["en"] if lang() == "en" else spec["zh"]
        out[sid] = Signal(sid, label, len(hits), round(min(1.0, len(hits) / full), 3),
                          tuple(_trim(h) for h in hits[:2]))
    return out


# ---------------------------------------------------------------- scoring

def _tier(score: float, keys_strong: int, keys_hit: int, keys_total: int) -> str | None:
    """core: strong overall and every key signal well evidenced; adjacent: half-way; stretch: some evidence."""
    if score >= CORE_SCORE and keys_strong == keys_total:
        return "core"
    if score >= ADJACENT_SCORE and (keys_hit or score >= 0.5):
        return "adjacent"
    if score >= STRETCH_SCORE:
        return "stretch"
    return None


def suggest(master: str, taxonomy: dict, config: dict | None = None) -> list[Suggestion]:
    signals = find_signals(master, taxonomy)
    searched = {str(q[1]).strip().lower() for q in (config or {}).get("queries", []) if len(q) > 1}
    results: list[Suggestion] = []
    for fam in taxonomy["families"]:
        keys = set(fam.get("key", []))
        weights = {sid: (2 if sid in keys else 1) for sid in fam["needs"]}
        got = [sid for sid in fam["needs"] if signals[sid].found]
        score = sum(weights[s] * signals[s].strength for s in fam["needs"]) / sum(weights.values())
        keys_strong = sum(1 for s in keys if signals[s].strength >= 0.5)
        tier = _tier(score, keys_strong, len(keys & set(got)), len(keys))
        if tier is None:
            continue
        evidence: list[str] = []
        for sid in sorted(got, key=lambda s: -weights[s]):
            for line in signals[sid].evidence[:1]:
                if line not in evidence:
                    evidence.append(line)
        family_name = fam["en"] if lang() == "en" else fam["zh"]
        for t in sorted(fam["titles"], key=lambda t: t.get("level") != "entry"):
            results.append(Suggestion(
                title=t["t"], track=fam["track"], family=family_name, level=t.get("level", "mid"), tier=tier,
                score=round(score, 2), matched=[signals[s].label for s in got],
                missing=[signals[s].label for s in fam["needs"] if s not in got], evidence=evidence[:3],
                already_searched=t["t"].lower() in searched))
    order = {t: i for i, t in enumerate(TIERS)}
    results.sort(key=lambda s: (order[s.tier], -s.score))
    return results


def count_in_logs(suggestions: list[Suggestion], log_dir: str | None = None) -> int:
    """Fill seen_in_logs with how many distinct jobs in past discovery scans had a matching title."""
    paths = sorted(glob.glob(os.path.join(log_dir or LOG_DIR, "discovery-scan-*.json")))
    titles: dict[str, str] = {}
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        for job in data.get("jobs", []):
            key = job.get("job_url") or f"{job.get('title')}|{job.get('company')}"
            titles[key] = str(job.get("title", "")).lower()
    for s in suggestions:
        pat = re.compile(words_to_regex([s.title]), re.I)
        s.seen_in_logs = sum(1 for t in titles.values() if pat.search(t))
    return len(paths)


# ---------------------------------------------------------------- config

def _default_location(config: dict) -> str:
    locs = [q[2] for q in config.get("queries", []) if len(q) > 2 and q[2]]
    return max(set(locs), key=locs.count) if locs else "United Kingdom"


def apply_to_config(config_path: str, picks: list[Suggestion], location: str | None = None) -> tuple[int, str | None]:
    """Add picked titles as queries and widen title_relevance; back up the old file first. Returns (added, backup)."""
    backup = None
    if os.path.exists(config_path):
        config = load_json_friendly(config_path)
        backup = config_path + ".bak"
        shutil.copyfile(config_path, backup)
    else:
        config = load_json_friendly(EXAMPLE_CONFIG_PATH)
        config["queries"], config["tracked"] = [], []
    where = location or _default_location(config)
    existing = {(str(q[1]).lower(), str(q[2]).lower() if len(q) > 2 else "") for q in config.get("queries", [])}
    relevance = config.setdefault("title_relevance", {})
    added = 0
    for s in picks:
        if (s.title.lower(), where.lower()) not in existing:
            config.setdefault("queries", []).append([s.track, s.title, where])
            existing.add((s.title.lower(), where.lower()))
            added += 1
        pattern = words_to_regex([s.title])
        current = relevance.get(s.track, "")
        if not current:
            relevance[s.track] = pattern
        elif not re.search(current, s.title, re.I):
            relevance[s.track] = f"{current}|{pattern}"
    priority = config.setdefault("display_track_priority", [])
    for s in picks:
        if s.track not in priority:
            priority.append(s.track)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return added, backup


def pick(suggestions: list[Suggestion], spec: str) -> list[Suggestion]:
    spec = spec.strip().lower()
    if spec in TIERS or spec in ("核心", "相邻", "拉伸"):
        tier = {"核心": "core", "相邻": "adjacent", "拉伸": "stretch"}.get(spec, spec)
        return [s for s in suggestions if s.tier == tier]
    if spec in ("all", "全部"):
        return list(suggestions)
    return [suggestions[i - 1] for i in parse_choices(spec, len(suggestions))]


# ---------------------------------------------------------------- output

def find_master(start: str | None = None) -> str | None:
    for base in [start or os.getcwd(), SCRIPT_DIR]:
        here = os.path.abspath(base)
        for _ in range(4):
            for name in ("master-cv-data.md", os.path.join("shared", "master-cv-data.md")):
                candidate = os.path.join(here, name)
                if os.path.exists(candidate):
                    return candidate
            here = os.path.dirname(here)
    return None


def render(suggestions: list[Suggestion], logs_scanned: int | None = None) -> str:
    if not suggestions:
        return tr("事实库里找不到足够的证据来推荐方向。先把经历、项目、技能写进 master-cv-data.md 再试。",
                  "Not enough evidence in the fact base to suggest anything. Fill in master-cv-data.md first.")
    out, n, last_family = [], 0, None
    for tier in TIERS:
        group = [s for s in suggestions if s.tier == tier]
        if not group:
            continue
        zh, en = TIER_NAMES[tier]
        out.append("\n" + tr(f"【{zh}】", f"[{en}]") + " " + {
            "core": tr("大部分要求你都有证据", "you have evidence for most of what these roles need"),
            "adjacent": tr("有一半左右的证据,值得一起搜", "about half covered; worth searching too"),
            "stretch": tr("证据较少,投之前要看 JD 具体要什么", "thin evidence; read each JD before applying")}[tier])
        for s in group:
            n += 1
            if s.family != last_family:
                out.append(tr(f"  ▸ {s.family}(证据覆盖 {round(s.score * 100)}%)",
                              f"  ▸ {s.family} (evidence coverage {round(s.score * 100)}%)"))
                out.append(tr("    有证据:", "    Evidence for: ") + ", ".join(s.matched))
                if s.missing:
                    out.append(tr("    缺:", "    Missing: ") + ", ".join(s.missing))
                for line in s.evidence:
                    out.append(tr("    出处:", "    Source: ") + line)
                last_family = s.family
            notes = []
            if s.level == "entry":
                notes.append(tr("入门", "entry"))
            if s.already_searched:
                notes.append(tr("已在搜", "already searched"))
            if s.seen_in_logs is not None:
                notes.append(tr(f"历史扫描见过 {s.seen_in_logs} 条", f"seen {s.seen_in_logs}× in past scans")
                             if s.seen_in_logs else tr("历史扫描未见过", "never seen in past scans"))
            out.append(f"    {n:>2}. {s.title}" + (f"  ({' · '.join(notes)})" if notes else ""))
        last_family = None
    if logs_scanned is not None:
        out.append("\n" + tr(f"已读取 {logs_scanned} 份历史扫描日志。", f"Read {logs_scanned} past scan logs."))
    out.append("\n" + tr("下一步:python keyword_suggest.py --apply core(或 --apply 1,3,5-8)把选中的词写进搜索配置。",
                         "Next: python keyword_suggest.py --apply core (or --apply 1,3,5-8) to add them to your search config."))
    return "\n".join(out).lstrip("\n")


def main(argv: list[str] | None = None) -> int:
    argv = apply_lang_arg(list(sys.argv[1:] if argv is None else argv))
    p = argparse.ArgumentParser(description=tr("根据事实库推荐岗位搜索词", "Suggest job-search titles from your fact base"))
    p.add_argument("--master", help=tr("事实库路径(默认向上查找 master-cv-data.md)",
                                       "fact base path (default: search upwards for master-cv-data.md)"))
    p.add_argument("--taxonomy", default=TAXONOMY_PATH, help=tr("岗位族谱文件", "role taxonomy file"))
    p.add_argument("--config", default=CONFIG_PATH, help=tr("搜索配置 sweep_config.json", "search config file"))
    p.add_argument("--from-logs", action="store_true", help=tr("统计历史扫描里每个词搜到过多少岗位",
                                                               "count how often each title appeared in past scans"))
    p.add_argument("--log-dir", default=None, help=argparse.SUPPRESS)
    p.add_argument("--apply", metavar="WHICH", help=tr("写进配置:core / adjacent / stretch / all 或编号如 1,3,5-8",
                                                      "add to config: core / adjacent / stretch / all, or numbers like 1,3,5-8"))
    p.add_argument("--location", help=tr("写入时用的地点(默认沿用配置里最常用的)", "location for added queries"))
    p.add_argument("--json", action="store_true", help=tr("输出 JSON", "print JSON"))
    p.add_argument("--lang", choices=("zh", "en"), help=tr("输出语言", "output language"))
    args = p.parse_args(argv)

    master_path = args.master or find_master()
    if not master_path or not os.path.exists(master_path):
        print(tr("❌ 找不到 master-cv-data.md(你的事实库)。\n"
                 "   新建方法:复制 templates/master-cv-data.md,填上你的经历、项目和技能,放在求职文件夹里;\n"
                 "   或者用 --master 指定位置。",
                 "❌ master-cv-data.md (your fact base) not found.\n"
                 "   Copy templates/master-cv-data.md, fill in your experience, projects and skills, "
                 "or pass --master."), file=sys.stderr)
        return 1
    with open(master_path, "r", encoding="utf-8-sig") as f:
        master = f.read()
    taxonomy = load_json_friendly(args.taxonomy)
    config = load_json_friendly(args.config) if os.path.exists(args.config) else None
    suggestions = suggest(master, taxonomy, config)
    logs = count_in_logs(suggestions, args.log_dir) if args.from_logs else None

    if args.apply:
        chosen = pick(suggestions, args.apply)
        if not chosen:
            print(tr("没有选中任何岗位名,配置没有改动。", "Nothing selected; config unchanged."), file=sys.stderr)
            return 1
        added, backup = apply_to_config(args.config, chosen, args.location)
        print(tr(f"✅ 已写入 {args.config}:新增 {added} 条搜索词(共选中 {len(chosen)} 个)。",
                 f"✅ Updated {args.config}: {added} new queries ({len(chosen)} selected)."))
        if backup:
            print(tr(f"   原配置备份在 {backup}", f"   Previous config saved as {backup}"))
        return 0
    if args.json:
        print(json.dumps([s.__dict__ for s in suggestions], ensure_ascii=False, indent=2))
        return 0
    print(tr(f"事实库:{master_path}", f"Fact base: {master_path}"))
    print(render(suggestions, logs))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
