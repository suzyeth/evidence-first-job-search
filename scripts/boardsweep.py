# -*- coding: utf-8 -*-
"""雇主板扩网 —— 直接打 Ashby / Greenhouse 公开 posting API,零聚合站依赖。
雇主自家板 != 聚合站镜像;聚合站漏掉的岗主要靠这一步补。

用法:
  python boardsweep.py                      # 用同目录 boardsweep_config.json
  python boardsweep.py --since 2026-01-01   # 只看该日期之后发布/更新的岗
  python boardsweep.py --config <path>
  python boardsweep.py --no-sponsor         # 不标担保状态(默认查 gov.uk 担保名册)
  python boardsweep.py --no-jd              # 不做 JD 体检(默认读 JD 全文,标不担保 / 隐藏 Senior / 年限 / 薪资低于签证门槛)
配置格式见 boardsweep_config.example.json。slug 不确定时:打开公司 careers 页,看跳转到的 ATS 域名。
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import sys
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"}
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import jd_check  # noqa: E402  (same folder)

DEFAULT_MAX_YEARS = 3


@dataclass(frozen=True)
class Filters:
    want: re.Pattern
    senior: re.Pattern
    location: re.Pattern
    since: date | None = None


@dataclass(frozen=True)
class Hit:
    kind: str
    slug: str
    title: str
    location: str
    url: str
    date: str
    company: str = ""     # Greenhouse 给真实公司名,比 slug 更适合查名册
    jd: str = ""          # JD 纯文本
    comp: str = ""        # Ashby 的薪资摘要(多数岗位为空)


def load_config(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"找不到 {path}。复制 boardsweep_config.example.json 为 boardsweep_config.json 并填写。")


def build_filters(cfg: dict, since: str | None = None) -> Filters:
    return Filters(re.compile(cfg["want_title_regex"], re.I), re.compile(cfg["senior_title_regex"], re.I),
                   re.compile(cfg["location_regex"], re.I),
                   datetime.fromisoformat(since).date() if since else None)


def on_or_after(value: str | None, since: date | None) -> bool:
    if not since:
        return True
    if not value:
        return False
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date() >= since


def wanted(title: str, location: str, stamp: str | None, f: Filters) -> bool:
    return bool(f.want.search(title) and f.location.search(location) and not f.senior.search(title)
                and on_or_after(stamp, f.since))


def ashby_hits(slug: str, data: dict, f: Filters) -> list[Hit]:
    out = []
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        title = j.get("title", "")
        loc = (str(j.get("location", "")) + " " + str(j.get("secondaryLocations", ""))).strip()
        stamp = j.get("publishedAt")
        if wanted(title, loc, stamp, f):
            comp = (j.get("compensation") or {}).get("compensationTierSummary") or ""
            out.append(Hit("ashby", slug, title, loc[:46], j.get("jobUrl") or "", (stamp or "")[:10],
                           jd=j.get("descriptionPlain") or "", comp=comp))
    return out


def greenhouse_hits(slug: str, data: dict, f: Filters) -> list[Hit]:
    out = []
    for j in data.get("jobs", []):
        title, loc = j.get("title", ""), (j.get("location") or {}).get("name", "")
        stamp = j.get("updated_at")
        if wanted(title, loc, stamp, f):
            out.append(Hit("gh", slug, title, loc[:46], j.get("absolute_url", ""), (stamp or "")[:10],
                           company=j.get("company_name") or "", jd=jd_check.html_to_text(j.get("content", ""))))
    return out


def _get(url: str, timeout: int = 20) -> dict:
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout))


def fetch_board(kind: str, slug: str) -> dict | None:
    # 带上 JD 全文 / 薪资摘要,给 jd_check 用
    urls = ([f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"] if kind == "ashby" else
            [f"https://{h}/v1/boards/{slug}/jobs?content=true"
             for h in ("boards-api.greenhouse.io", "boards-api.eu.greenhouse.io")])
    for url in urls:   # Greenhouse 部分板只在 EU 节点
        try:
            return _get(url)
        except Exception:
            continue
    return None


def slug_to_name(slug: str) -> str:
    """招聘板 slug 转成可查名册的公司名:'checkout.com' -> 'checkout','skin-analytics' -> 'skin analytics'。
    slug 和真名差太多时,把 slug 当键加进 sponsor_aliases.json 即可。"""
    name = re.sub(r"\.(co\.uk|com|ai|io|co|org|net|dev|app)$", "", slug.lower())
    name = re.sub(r"[-_.]+", " ", name)
    return re.sub(r"\d+$", "", name).strip()


def _sponsor_tagger(enabled: bool):
    """加载担保名册;失败只告警,不影响扫板。"""
    if not enabled:
        return None
    try:
        if SCRIPT_DIR not in sys.path:
            sys.path.insert(0, SCRIPT_DIR)
        import sponsor_check
        return sponsor_check.SponsorTagger.load()
    except Exception as exc:
        print(f"⚠️ 担保名册加载失败({type(exc).__name__}: {exc}),本轮不标担保状态。")
        return None


def _company_key(h: Hit) -> str:
    return h.company or slug_to_name(h.slug)


def _sponsor_tags(hits: list[Hit], enabled: bool) -> dict[str, str]:
    """每家公司只查一次名册。"""
    tagger = _sponsor_tagger(enabled) if hits else None
    if tagger is None:
        return {}
    return {key: tagger.tag(key)["display"] for key in dict.fromkeys(_company_key(h) for h in hits)}


def _jd_summary(all_tags) -> str:
    counts = {"❌不担保": 0, "隐藏Senior": 0, "年限超线": 0, "薪资低于门槛": 0}
    for found in all_tags:
        counts["❌不担保"] += any(t == "JD❌不担保" for t in found)
        counts["隐藏Senior"] += any(t == "正文Senior" for t in found)
        counts["年限超线"] += any(t.startswith("要") for t in found)
        counts["薪资低于门槛"] += any(t.startswith("£") for t in found)
    return ("JD 体检:" + " · ".join(f"{k} {v}" for k, v in counts.items())
            + f"(薪资门槛 £{jd_check.STANDARD_THRESHOLD:,} / 下限 £{jd_check.FLOOR_THRESHOLD:,},"
            f"{jd_check.THRESHOLD_CHECKED} 核对 gov.uk)\n")


def dedupe(hits: list[Hit]) -> list[Hit]:
    seen, out = set(), []
    for h in sorted(hits, key=lambda h: (h.slug, h.title)):
        key = (h.title.lower(), h.slug)
        if key not in seen:
            seen.add(key)
            out.append(h)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="直扫雇主 Ashby / Greenhouse 招聘板")
    p.add_argument("--config", default=os.path.join(SCRIPT_DIR, "boardsweep_config.json"))
    p.add_argument("--since", help="只看该日期(YYYY-MM-DD)之后发布/更新的岗")
    p.add_argument("--no-sponsor", action="store_true", help="不标担保状态")
    p.add_argument("--no-jd", action="store_true", help="不做 JD 体检")
    args = p.parse_args(argv)
    cfg = load_config(args.config)
    try:
        filters = build_filters(cfg, args.since)
    except ValueError:
        raise SystemExit("--since 格式应为 YYYY-MM-DD")

    tasks = [("ashby", s) for s in cfg.get("ashby", [])] + [("gh", s) for s in cfg.get("greenhouse", [])]
    hits, alive, unreachable = [], 0, []
    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        boards = ex.map(lambda t: (t, fetch_board("ashby" if t[0] == "ashby" else "gh", t[1])), tasks)
        for (kind, slug), data in boards:
            if data is None:
                unreachable.append(f"{kind}:{slug}")
                continue
            alive += 1
            hits += (ashby_hits if kind == "ashby" else greenhouse_hits)(slug, data, filters)

    print(f"板可达 {alive} / 探测 {len(tasks)}({len(unreachable)} 个 slug 无效或不可达)")
    if unreachable:
        print("  不可达:", " ".join(unreachable))
    unique = dedupe(hits)
    print(f"目标地点 × 非-Senior × 目标标题族命中:{len(unique)}\n")
    sponsor_tags = _sponsor_tags(unique, not args.no_sponsor)
    jd_tags = {} if args.no_jd else {h: jd_check.tags(jd_check.analyze(h.jd, h.comp),
                                                      int(cfg.get("max_years", DEFAULT_MAX_YEARS)))
                                     for h in unique}
    if jd_tags:
        print(_jd_summary(jd_tags.values()))
    for h in unique:
        tag = f" {sponsor_tags[_company_key(h)]}" if _company_key(h) in sponsor_tags else ""
        jd = f" [JD:{'·'.join(jd_tags[h])}]" if jd_tags.get(h) else ""
        print(f"  {h.date:<10} [{h.kind}:{h.slug}]{tag}{jd} {h.title[:52]:<52} | {h.location:<34} | {h.url[:78]}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
