# -*- coding: utf-8 -*-
"""雇主板扩网 —— 直接打 Ashby / Greenhouse / Lever / Workable / Teamtailor 的公开接口,零聚合站依赖。
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
from datetime import date, datetime, timezone

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"}
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import jd_check  # noqa: E402  (same folder)
from i18n import apply_lang_arg, tr  # noqa: E402
from countries import country_name  # noqa: E402

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
        raise SystemExit(tr(f"找不到 {path}。复制 boardsweep_config.example.json 为 boardsweep_config.json 并填写。",
                            f"{path} not found. Copy boardsweep_config.example.json to boardsweep_config.json "
                            "and fill it in."))


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


def _ashby_location(job: dict) -> str:
    """'London; New York, United States' —— 次要地点是 [{location, address{postalAddress{addressCountry}}}],
    以前直接 str() 了整个列表,输出成 Python 的 [{'location': …}]。"""
    places = [job.get("location") or ""]
    for extra in job.get("secondaryLocations") or []:
        if not isinstance(extra, dict):
            continue
        country = ((extra.get("address") or {}).get("postalAddress") or {}).get("addressCountry")
        name = extra.get("location") or ""
        places.append(f"{name}, {country}" if country and country not in name else name)
    return "; ".join(dict.fromkeys(p for p in places if p))


def ashby_hits(slug: str, data: dict, f: Filters) -> list[Hit]:
    out = []
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        title = j.get("title", "")
        loc = _ashby_location(j)
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


def lever_hits(slug: str, data: list, f: Filters) -> list[Hit]:
    out = []
    for j in data or []:
        cats = j.get("categories") or {}
        places = [cats.get("location"), *(cats.get("allLocations") or [])]
        loc = "; ".join(dict.fromkeys(p for p in places if p))   # allLocations 常常重复主地点
        country = country_name(j.get("country"))                  # Lever 给的是代码(NL),地点里没写国名时补上
        if country and country.lower() not in loc.lower():
            loc = f"{loc}; {country}" if loc else country
        created = j.get("createdAt")
        stamp = datetime.fromtimestamp(created / 1000, timezone.utc).isoformat() if created else None
        title = j.get("text", "")
        if wanted(title, loc, stamp, f):
            sections = " ".join(jd_check.html_to_text(s.get("content", "")) for s in j.get("lists") or [])
            jd = " ".join(p for p in (j.get("descriptionPlain"), sections, j.get("additionalPlain")) if p)
            out.append(Hit("lever", slug, title, loc[:46], j.get("hostedUrl", ""), (stamp or "")[:10], jd=jd))
    return out


def workable_hits(slug: str, data: dict, f: Filters) -> list[Hit]:
    out = []
    for j in data.get("jobs", []):
        title = j.get("title", "")
        loc = ", ".join(p for p in (j.get("city"), j.get("state"), j.get("country")) if p)
        stamp = j.get("published_on")
        if wanted(title, loc, stamp, f):
            out.append(Hit("workable", slug, title, loc[:46], j.get("url", ""), (stamp or "")[:10],
                           company=data.get("name") or "", jd=jd_check.html_to_text(j.get("description", ""))))
    return out




def teamtailor_hits(slug: str, data: dict, f: Filters) -> list[Hit]:
    """Teamtailor 的 jobs.json 带 schema.org JobPosting;国家是代码(GB),要先转成英文名,否则英国过滤匹配不到。"""
    out = []
    for item in data.get("items", []):
        posting = item.get("_jobposting") or {}
        places = [(p.get("address") or {}) for p in posting.get("jobLocation") or []]
        loc = "; ".join(", ".join(x for x in (a.get("addressLocality"),
                                              country_name(a.get("addressCountry"))) if x)
                        for a in places)
        title, stamp = item.get("title", ""), item.get("date_published")
        if wanted(title, loc, stamp, f):
            company = (posting.get("hiringOrganization") or {}).get("name") or data.get("title") or ""
            out.append(Hit("teamtailor", slug, title, loc[:46], item.get("url", ""), (stamp or "")[:10],
                           company=company, jd=jd_check.html_to_text(item.get("content_html", ""))))
    return out


BOARD_URLS = {
    # 带上 JD 全文 / 薪资摘要,给 jd_check 用;Greenhouse / Lever 部分公司只在 EU 节点
    "ashby": ["https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"],
    "gh": ["https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true",
           "https://boards-api.eu.greenhouse.io/v1/boards/{slug}/jobs?content=true"],
    "lever": ["https://api.lever.co/v0/postings/{slug}?mode=json", "https://api.eu.lever.co/v0/postings/{slug}?mode=json"],
    "workable": ["https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true"],
    "teamtailor": ["https://{slug}.teamtailor.com/jobs.json"],
}
# 配置里的键 -> (内部 kind, 解析函数)
BOARD_KINDS = {"ashby": ("ashby", ashby_hits), "greenhouse": ("gh", greenhouse_hits), "lever": ("lever", lever_hits),
               "workable": ("workable", workable_hits), "teamtailor": ("teamtailor", teamtailor_hits)}


def fetch_board(kind: str, slug: str):
    urls = [u.format(slug=slug) for u in BOARD_URLS.get(kind, [])]
    for url in urls:
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
        print(tr(f"⚠️ 担保名册加载失败({type(exc).__name__}: {exc}),本轮不标担保状态。",
                 f"⚠️ Could not load the sponsor register ({type(exc).__name__}: {exc}); "
                 "no sponsor tags this run."))
        return None


def _company_key(h: Hit) -> str:
    return h.company or slug_to_name(h.slug)


def _sponsor_tags(hits: list[Hit], enabled: bool) -> dict[str, str]:
    """每家公司只查一次名册。"""
    tagger = _sponsor_tagger(enabled) if hits else None
    if tagger is None:
        return {}
    return {key: tagger.tag(key)["display"] for key in dict.fromkeys(_company_key(h) for h in hits)}


def _jd_summary(reports, max_years: int) -> str:
    """按体检结果字段计数,不依赖标签文字(标签会随 --lang 变)。"""
    reports = list(reports)
    counts = [
        (tr("❌不担保", "❌no sponsorship"), sum(r.sponsor == "negative" for r in reports)),
        (tr("隐藏Senior", "hidden senior"), sum(r.senior for r in reports)),
        (tr("年限超线", "too many years"), sum(r.years is not None and r.years > max_years for r in reports)),
        (tr("薪资低于门槛", "salary below threshold"), sum(r.salary_flag in ("below_standard", "below_floor")
                                                     for r in reports)),
    ]
    std, floor, day = (f"£{jd_check.STANDARD_THRESHOLD:,}", f"£{jd_check.FLOOR_THRESHOLD:,}",
                       jd_check.THRESHOLD_CHECKED)
    return (tr("JD 体检:", "JD check: ") + " · ".join(f"{k} {v}" for k, v in counts)
            + tr(f"(薪资门槛 {std} / 下限 {floor},{day} 核对 gov.uk)",
                 f" (salary thresholds {std} / floor {floor}, checked against gov.uk on {day})") + "\n")


def dedupe(hits: list[Hit]) -> list[Hit]:
    seen, out = set(), []
    for h in sorted(hits, key=lambda h: (h.slug, h.title)):
        key = (h.title.lower(), h.slug)
        if key not in seen:
            seen.add(key)
            out.append(h)
    return out


def main(argv: list[str] | None = None) -> int:
    argv = apply_lang_arg(list(sys.argv[1:] if argv is None else argv))
    p = argparse.ArgumentParser(description=tr("直扫雇主招聘板(Ashby / Greenhouse / Lever / Workable / Teamtailor)",
                                               "Scan employer job boards (Ashby / Greenhouse / Lever / Workable / "
                                               "Teamtailor)"))
    p.add_argument("--config", default=os.path.join(SCRIPT_DIR, "boardsweep_config.json"))
    p.add_argument("--since", help=tr("只看该日期(YYYY-MM-DD)之后发布/更新的岗",
                                      "only jobs published/updated on or after YYYY-MM-DD"))
    p.add_argument("--no-sponsor", action="store_true", help=tr("不标担保状态", "skip sponsor-register tags"))
    p.add_argument("--no-jd", action="store_true", help=tr("不做 JD 体检", "skip the JD check"))
    p.add_argument("--lang", choices=("zh", "en"), help=tr("输出语言", "output language"))
    args = p.parse_args(argv)
    cfg = load_config(args.config)
    try:
        filters = build_filters(cfg, args.since)
    except ValueError:
        raise SystemExit(tr("--since 格式应为 YYYY-MM-DD", "--since must be YYYY-MM-DD"))

    tasks = [(kind, slug) for key, (kind, _) in BOARD_KINDS.items() for slug in cfg.get(key, [])]
    parsers = {kind: parser for kind, parser in BOARD_KINDS.values()}
    hits, alive, unreachable = [], 0, []
    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        boards = ex.map(lambda t: (t, fetch_board(t[0], t[1])), tasks)
        for (kind, slug), data in boards:
            if data is None:
                unreachable.append(f"{kind}:{slug}")
                continue
            alive += 1
            hits += parsers[kind](slug, data, filters)

    print(tr(f"板可达 {alive} / 探测 {len(tasks)}({len(unreachable)} 个 slug 无效或不可达)",
             f"Boards reached {alive} / {len(tasks)} ({len(unreachable)} invalid or unreachable)"))
    if unreachable:
        print(tr("  不可达:", "  Unreachable:"), " ".join(unreachable))
    unique = dedupe(hits)
    print(tr(f"目标地点 × 非-Senior × 目标标题族命中:{len(unique)}\n",
             f"Matches (location × non-senior × target titles): {len(unique)}\n"))
    sponsor_tags = _sponsor_tags(unique, not args.no_sponsor)
    max_years = int(cfg.get("max_years", DEFAULT_MAX_YEARS))
    reports = {} if args.no_jd else {h: jd_check.analyze(h.jd, h.comp) for h in unique}
    jd_tags = {h: jd_check.tags(r, max_years) for h, r in reports.items()}
    if reports:
        print(_jd_summary(reports.values(), max_years))
    for h in unique:
        tag = f" {sponsor_tags[_company_key(h)]}" if _company_key(h) in sponsor_tags else ""
        # 方括号已标明是 JD,标签自带的 "JD" 前缀去掉,避免显示成 [JD:JD❌…]
        jd = f" [JD:{'·'.join(t.removeprefix('JD') for t in jd_tags[h])}]" if jd_tags.get(h) else ""
        print(f"  {h.date:<10} [{h.kind}:{h.slug}]{tag}{jd} {h.title[:52]:<52} | {h.location:<34} | {h.url[:78]}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
