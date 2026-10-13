# -*- coding: utf-8 -*-
"""
英国签证担保核查 —— 在 gov.uk「Register of licensed sponsors: workers」里查雇主,并扫描 JD 的担保措辞。

为什么需要脚本而不是直接 grep 名册:
  · 名册登记的是**法人名**,不是商号(Bumble → Badoo Limited);
  · 名字可能连写无空格(Spotlightsportsgroup)、带 t/a(XXX Ltd t/a Brand)、含逗号被引号包住;
  · 商号是常见英文词时(Nothing / Linear / Notion)子串匹配会被噪音淹没;
  · 名册命中 ≠ 这个岗位愿意担保,还要看 JD 原文。

用法(Python 3.10+,只用标准库):
  python sponsor_check.py "Bumble" "Zego" "Anthropic"
  python sponsor_check.py --file companies.txt
  python sponsor_check.py "Monzo" --jd ../applications/monzo-analyst/JD.md
  python sponsor_check.py "Wise" --all-routes --json
  选项:--refresh 强制重新下载名册;--max-age 天数(默认 1);--register 指定本地 CSV;--aliases 别名文件
"""
from __future__ import annotations

import argparse
import csv
import difflib
import glob
import json
import os
import re
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from urllib.parse import quote_plus

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(SCRIPT_DIR, "cache")
DEFAULT_ALIASES = os.path.join(SCRIPT_DIR, "sponsor_aliases.json")
PUBLICATION_URL = "https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers"
COMPANIES_HOUSE_SEARCH = "https://find-and-update.company-information.service.gov.uk/search/companies?q="
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}
SKILLED_WORKER = "Skilled Worker"

LEGAL_SUFFIXES = {"limited", "ltd", "plc", "llp", "lp", "llc", "inc", "incorporated", "co", "company",
                  "corp", "corporation", "uk", "gb", "group", "holdings"}
# 商号是常见英文词时,子串匹配噪音极大,必须先拿法人名
COMMON_WORDS = {"nothing", "linear", "notion", "calm", "betty", "orb", "wise", "monday", "sierra", "apple",
                "amazon", "bloom", "focus", "harbour", "pulse", "spark", "summit", "zen", "atlas", "nova",
                "echo", "vertex", "beam", "cleo", "plum", "tide", "form", "peak", "huma", "writer", "eve"}
NOISY_HIT_THRESHOLD = 15
MAX_SHOWN = 12
FUZZY_CUTOFF = 0.85
KIND_RANK = {"exact": 0, "squashed": 1, "contains": 2, "similar": 3}
WEB_DOMAIN = re.compile(r"\.(?:co\.uk|com|ai|io|app|dev|net|org|gg)\b", re.I)
TRADING_AS = re.compile(r"\s+(?:t\s*/\s*as?|trading\s+as)\s+", re.I)


class RegisterError(RuntimeError):
    pass


# ---------------------------------------------------------------- normalisation

def _tokens(name: str) -> list[str]:
    text = name.lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", text).split()


def core_name(name: str) -> str:
    """去域名、标点、法人后缀:'NOTHING TECHNOLOGY LIMITED' -> 'nothing technology','Checkout.com' -> 'checkout'。"""
    tokens = _tokens(WEB_DOMAIN.sub(" ", name))
    while tokens and tokens[-1] in LEGAL_SUFFIXES:
        tokens = tokens[:-1]
    if tokens and tokens[0] == "the":
        tokens = tokens[1:]
    return " ".join(tokens)


def split_trading_as(name: str) -> list[str]:
    """'Foo Ltd t/a Bar' -> ['Foo Ltd', 'Bar'];法人名和商号都要能被查到。"""
    return [part.strip() for part in TRADING_AS.split(name.strip()) if part.strip()]


# ---------------------------------------------------------------- register

@dataclass(frozen=True)
class Org:
    name: str
    town: str
    county: str
    rating: str
    routes: frozenset


@dataclass(frozen=True)
class _Variant:
    core: str
    squashed: str
    tokens: frozenset
    org: Org


class Register(dict):
    """name -> Org,附带惰性构建的检索索引。"""

    _index: list | None = None
    _by_core: dict | None = None

    def index(self) -> tuple[list, dict]:
        if self._index is None:
            variants, by_core = [], {}
            for org in self.values():
                for part in split_trading_as(org.name):
                    core = core_name(part)
                    if not core:
                        continue
                    v = _Variant(core, core.replace(" ", ""), frozenset(core.split()), org)
                    variants.append(v)
                    by_core.setdefault(core, []).append(v)
            self._index, self._by_core = variants, by_core
        return self._index, self._by_core


def _rating(type_and_rating: str) -> str:
    """取最外层括号内容:'Worker (A rating)' -> 'A';'Worker (A (Premium))' -> 'A (Premium)'。"""
    start, end = type_and_rating.find("("), type_and_rating.rfind(")")
    if start == -1 or end <= start:
        return type_and_rating.strip()
    inner = type_and_rating[start + 1:end].strip()
    return re.sub(r"\s*rating$", "", inner, flags=re.I)


def load_register(path: str) -> Register:
    rows: dict[str, dict] = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = {"Organisation Name", "Route"} - set(reader.fieldnames or [])
        if missing:
            raise RegisterError(f"名册 CSV 缺少列 {missing},gov.uk 可能改了格式:{path}")
        for row in reader:
            name = (row.get("Organisation Name") or "").strip()
            if not name:
                continue
            entry = rows.setdefault(name, {"town": (row.get("Town/City") or "").strip(),
                                           "county": (row.get("County") or "").strip(),
                                           "rating": _rating(row.get("Type & Rating") or ""),
                                           "routes": set()})
            entry["routes"].add((row.get("Route") or "").strip())
    register = Register()
    for name, e in rows.items():
        register[name] = Org(name, e["town"], e["county"], e["rating"], frozenset(e["routes"]))
    return register


def find_csv_link(html: str) -> str:
    links = re.findall(r'https://assets\.publishing\.service\.gov\.uk/[^"\']+?\.csv', html)
    if not links:
        raise RegisterError("在 gov.uk 页面上没找到名册 CSV 链接,页面结构可能变了:" + PUBLICATION_URL)
    return links[0]


def _fetch(url: str, timeout: int = 60) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def _latest_cache() -> str | None:
    files = sorted(glob.glob(os.path.join(CACHE_DIR, "register-*.csv")), key=os.path.getmtime)
    return files[-1] if files else None


def ensure_register(max_age_days: float = 1.0, refresh: bool = False) -> str:
    """返回本地名册路径;缓存过期或 --refresh 时重新下载,下载失败退回旧缓存。"""
    cached = _latest_cache()
    if cached and not refresh and (time.time() - os.path.getmtime(cached)) < max_age_days * 86400:
        return cached
    try:
        link = find_csv_link(_fetch(PUBLICATION_URL).decode("utf-8", "replace"))
        data = _fetch(link, timeout=180)
    except Exception as exc:  # 网络错误:能用旧缓存就用,并明确告知
        if cached:
            print(f"⚠️ 下载名册失败({type(exc).__name__}),改用旧缓存 {os.path.basename(cached)}", file=sys.stderr)
            return cached
        raise RegisterError(f"下载名册失败且没有缓存:{exc}") from exc
    m = re.search(r"(\d{4}-\d{2}-\d{2})\.csv$", link)
    stamp = m.group(1) if m else time.strftime("%Y-%m-%d")
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"register-{stamp}.csv")
    with open(path, "wb") as f:
        f.write(data)
    return path


# ---------------------------------------------------------------- lookup

@dataclass(frozen=True)
class Match:
    org: Org
    kind: str


@dataclass
class LookupResult:
    query: str
    status: str = "NOT_FOUND"          # SKILLED_WORKER / OTHER_ROUTE_ONLY / AMBIGUOUS / POSSIBLE / NOT_FOUND
    matches: list = field(default_factory=list)
    total_hits: int = 0
    noisy: bool = False
    via_alias: str = ""
    companies_house_url: str = ""


def _search(core: str, register: Register, fuzzy: bool = True) -> dict[str, Match]:
    variants, by_core = register.index()
    found: dict[str, Match] = {}

    def add(org: Org, kind: str) -> None:
        old = found.get(org.name)
        if old is None or KIND_RANK[kind] < KIND_RANK[old.kind]:
            found[org.name] = Match(org, kind)

    if not core:
        return found
    squashed, tokens = core.replace(" ", ""), set(core.split())
    for v in by_core.get(core, []):
        add(v.org, "exact")
    for v in variants:
        if v.squashed == squashed or (len(squashed) >= 6 and v.squashed.startswith(squashed)
                                      and " " not in v.core):
            add(v.org, "squashed")
        elif tokens <= v.tokens:
            add(v.org, "contains")
    if not found and fuzzy:
        for near in difflib.get_close_matches(core, list(by_core), n=5, cutoff=FUZZY_CUTOFF):
            for v in by_core[near]:
                add(v.org, "similar")
    return found


def _alias_for(query: str, aliases: dict) -> str:
    wanted = core_name(query)
    for key, legal in aliases.items():
        if core_name(key) == wanted:
            return legal
    return ""


def lookup(query: str, register: Register, aliases: dict | None = None, fuzzy: bool = True) -> LookupResult:
    result = LookupResult(query=query, companies_house_url=COMPANIES_HOUSE_SEARCH + quote_plus(query.strip()))
    found = _search(core_name(query), register, fuzzy)
    legal = _alias_for(query, aliases or {})
    alias_pinned = False
    if legal:
        result.via_alias = legal
        alias_found = _search(core_name(legal), register, fuzzy)
        alias_pinned = any(m.kind in ("exact", "squashed") for m in alias_found.values())
        if alias_pinned:
            # 别名已经精确定位到法人,商号本身的子串/近似命中只是噪音
            found = {n: m for n, m in found.items() if m.kind == "exact"}
        for name, m in alias_found.items():
            if name not in found or KIND_RANK[m.kind] < KIND_RANK[found[name].kind]:
                found[name] = m

    ranked = sorted(found.values(), key=lambda m: (KIND_RANK[m.kind], SKILLED_WORKER not in m.org.routes,
                                                   m.org.name.lower()))
    result.matches, result.total_hits = ranked, len(ranked)
    core = core_name(query)
    # 别名已精确定位法人时,常见词的噪音不再影响结论
    single_word = len(core.split()) == 1
    only_substring = not any(m.kind in ("exact", "squashed") for m in ranked)
    # 单个词只有子串命中时(Faculty -> 某医学院学部),多半是撞名,同样不能下结论
    result.noisy = not alias_pinned and (
        (single_word and (core in COMMON_WORDS or only_substring)) or len(ranked) > NOISY_HIT_THRESHOLD)

    strong = [m for m in ranked if m.kind != "similar"]
    if result.noisy and not legal and strong:
        # 常见词的子串命中多半是同名无关公司,不能据此给出"有牌照"的结论
        result.status = "AMBIGUOUS"
    elif strong:
        result.status = ("SKILLED_WORKER" if any(SKILLED_WORKER in m.org.routes for m in strong)
                         else "OTHER_ROUTE_ONLY")
    elif ranked:
        result.status = "POSSIBLE"
    return result


# ---------------------------------------------------------------- JD scan

@dataclass(frozen=True)
class JdHit:
    signal: str     # negative / positive / check
    sentence: str


JD_PATTERNS = [
    ("negative", re.compile(
        r"\b(unable|not able|cannot|can't|can not|won't|will not|do not|don't|does not|doesn't|"
        r"are not able|not in a position)\b[^.]{0,40}\b(sponsor\w*|visa)"
        r"|\bno\s+(visa\s+)?sponsorship\b"
        r"|\bsponsorship\s+(is\s+)?not\s+(available|offered|provided|possible)"
        r"|\bwithout\s+(the\s+)?(need\s+for\s+)?(visa\s+)?sponsorship", re.I)),
    ("positive", re.compile(
        r"\b(visa\s+)?sponsorship\s+(is\s+|can\s+be\s+)?(available|offered|provided|possible|considered)"
        r"|\b(we|employer)\s+(can|will|are able to)\s+(offer\s+)?(visa\s+)?sponsor"
        r"|\bskilled worker (visa|sponsorship)", re.I)),
    ("check", re.compile(
        r"\bright to work\b|\bwork(ing)? (authori[sz]ation|permit)\b|\beligib\w* to work\b"
        r"|\b(sc|dv|security) clearance\b", re.I)),
]


def scan_jd(text: str) -> list[JdHit]:
    hits = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        sentence = sentence.strip()
        for signal, pattern in JD_PATTERNS:   # 一句只取最强信号:negative > positive > check
            if sentence and pattern.search(sentence):
                hits.append(JdHit(signal, sentence[:220]))
                break
    return hits


# ---------------------------------------------------------------- output

STATUS_TEXT = {
    "SKILLED_WORKER": "✅ 在册,有 Skilled Worker 路线",
    "OTHER_ROUTE_ONLY": "⚠️ 在册,但没有 Skilled Worker 路线",
    "AMBIGUOUS": "❓ 名字太常见,下面的命中可能都是同名的无关公司,无法判断",
    "POSSIBLE": "❓ 只有近似匹配,请人工确认是不是同一家",
    "NOT_FOUND": "❌ 名册查无",
}
JD_TEXT = {"negative": "❌ 不担保", "positive": "✅ 可担保", "check": "⚠️ 需核实"}


def _format_org(m: Match, all_routes: bool) -> str:
    routes = sorted(m.org.routes) if all_routes else (
        [SKILLED_WORKER] if SKILLED_WORKER in m.org.routes else sorted(m.org.routes))
    place = " · ".join(p for p in (m.org.town, m.org.county) if p)
    return f"    [{m.kind:<8}] {m.org.name} · {place} · {m.org.rating} 级 · {', '.join(routes)}"


def render(result: LookupResult, all_routes: bool = False) -> str:
    head = f"== {result.query}" + (f"(别名 → {result.via_alias})" if result.via_alias else "")
    lines = [head, "  " + STATUS_TEXT[result.status]]
    lines += [_format_org(m, all_routes) for m in result.matches[:MAX_SHOWN]]
    if result.total_hits > MAX_SHOWN:
        lines.append(f"    …另有 {result.total_hits - MAX_SHOWN} 条,用 --json 查看全部")
    if result.noisy:
        lines.append("  ⚠️ 名字是常见词或命中过多,子串匹配不可靠 —— 先去 Companies House 拿法人名再查:")
        lines.append("     " + result.companies_house_url)
    if result.status == "NOT_FOUND":
        lines += ["  别急着下结论:商号查不到 ≠ 没有牌照。",
                  "    1) 去 Companies House 查英国法人名:" + result.companies_house_url,
                  "    2) 用法人名重查,并把「商号 → 法人名」加进 sponsor_aliases.json",
                  "    3) Companies House 也查无 = 英国无实体,基本可判死"]
    elif result.status in ("SKILLED_WORKER", "POSSIBLE"):
        lines.append("  提醒:名册只证明雇主有牌照,这个岗位是否担保还要看 JD(加 --jd)。")
    return "\n".join(lines)


def _as_dict(result: LookupResult) -> dict:
    return {"query": result.query, "status": result.status, "via_alias": result.via_alias,
            "noisy": result.noisy, "companies_house_url": result.companies_house_url,
            "matches": [{"name": m.org.name, "kind": m.kind, "town": m.org.town, "rating": m.org.rating,
                         "routes": sorted(m.org.routes)} for m in result.matches]}


def load_aliases(path: str) -> dict:
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


# ---------------------------------------------------------------- batch tagging (used by sweep / boardsweep)

TAG_ICON = {"SKILLED_WORKER": "✅", "OTHER_ROUTE_ONLY": "⚠️", "AMBIGUOUS": "❓", "POSSIBLE": "❓",
            "NOT_FOUND": "❌"}


class SponsorTagger:
    """名册只加载一次、按公司名缓存;批量标注时关闭近似匹配,保证上百家公司也能秒出。"""

    def __init__(self, register: Register, aliases: dict | None = None):
        self.register = register
        self.aliases = aliases or {}
        self._cache: dict[str, dict] = {}

    @classmethod
    def load(cls, max_age_days: float = 1.0, refresh: bool = False, register_path: str | None = None,
             aliases_path: str = DEFAULT_ALIASES) -> "SponsorTagger":
        path = register_path or ensure_register(max_age_days, refresh)
        return cls(load_register(path), load_aliases(aliases_path))

    def tag(self, company: str) -> dict:
        key = core_name(company or "")
        if not key:
            return {"status": "UNKNOWN", "legal": "", "town": "", "label": "担保?", "display": "担保?"}
        if key not in self._cache:
            self._cache[key] = self._tag(company)
        return self._cache[key]

    def _tag(self, company: str) -> dict:
        result = lookup(company, self.register, self.aliases, fuzzy=False)
        label = "担保" + TAG_ICON[result.status]
        org = None
        if result.status in ("SKILLED_WORKER", "OTHER_ROUTE_ONLY"):
            # 附上命中的法人名和城市:同名不同家(Cursor Ltd · Lincoln ≠ Cursor 编辑器)要靠人眼一眼识别
            alias_core = core_name(result.via_alias) if result.via_alias else None
            strong = [m for m in result.matches if m.kind != "similar"]
            org = next((m.org for m in strong if alias_core and core_name(m.org.name) == alias_core), None) \
                or next((m.org for m in strong if SKILLED_WORKER in m.org.routes), None) \
                or (strong[0].org if strong else None)
        legal, town = (org.name, org.town) if org else ("", "")
        display = f"{label}({legal} · {town})" if legal else label
        return {"status": result.status, "legal": legal, "town": town, "label": label, "display": display}


# ---------------------------------------------------------------- --add-alias

def add_alias(trading: str, legal: str, register: Register, aliases_path: str) -> int:
    """确认法人名确实在名册里,再写进别名文件;写入的是名册里的原样写法。"""
    wanted = core_name(legal)
    org = next((o for name, o in register.items() if name.strip().lower() == legal.strip().lower()), None) \
        or next((o for o in register.values() if core_name(o.name) == wanted), None)
    if org is None:
        print(f"❌ 名册里没有「{legal}」,没有写入。")
        close = difflib.get_close_matches(legal, list(register), n=3, cutoff=0.8)
        if close:
            print("   你要找的是不是:" + " / ".join(close))
        return 1
    current = {}
    if os.path.exists(aliases_path):
        with open(aliases_path, "r", encoding="utf-8") as f:
            current = json.load(f)
    updated = {**current, trading.strip(): org.name}
    with open(aliases_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(updated, ensure_ascii=False, indent=2) + "\n")
    print(f"✅ 已加入:{trading.strip()} → {org.name}({org.town} · {org.rating} 级)")
    if SKILLED_WORKER not in org.routes:
        print(f"⚠️ 注意:这家机构在名册里没有 Skilled Worker 路线(只有 {', '.join(sorted(org.routes))})。")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="英国签证担保名册核查 + JD 担保措辞扫描")
    p.add_argument("companies", nargs="*", help="公司名(商号或法人名均可)")
    p.add_argument("--file", help="每行一个公司名的文本文件")
    p.add_argument("--jd", nargs="*", default=[], help="要扫描担保措辞的 JD 文件")
    p.add_argument("--register", help="使用本地名册 CSV,不联网")
    p.add_argument("--refresh", action="store_true", help="强制重新下载名册")
    p.add_argument("--max-age", type=float, default=1.0, help="缓存有效天数(默认 1)")
    p.add_argument("--aliases", default=DEFAULT_ALIASES, help="商号 → 法人名 别名文件")
    p.add_argument("--all-routes", action="store_true", help="显示全部签证路线")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.add_argument("--add-alias", nargs=2, metavar=("商号", "法人名"),
                   help="核实法人名在名册里后,把「商号 → 法人名」写进别名文件")
    args = p.parse_args(argv)

    if args.add_alias:
        try:
            register = load_register(args.register or ensure_register(args.max_age, args.refresh))
        except (RegisterError, OSError) as exc:
            print(f"❌ {exc}", file=sys.stderr)
            return 1
        return add_alias(args.add_alias[0], args.add_alias[1], register, args.aliases)

    names = [c for c in args.companies if c.strip()]
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            names += [line.strip() for line in f if line.strip() and not line.startswith("#")]
    if not names and not args.jd:
        p.print_help()
        return 2

    output: dict = {"companies": [], "jd": {}}
    if names:
        try:
            path = args.register or ensure_register(args.max_age, args.refresh)
            register = load_register(path)
        except (RegisterError, OSError) as exc:
            print(f"❌ {exc}", file=sys.stderr)
            return 1
        aliases = load_aliases(args.aliases)
        if not args.json:
            print(f"名册:{os.path.basename(path)} · {len(register)} 家机构\n")
        for name in names:
            result = lookup(name, register, aliases)
            output["companies"].append(_as_dict(result))
            if not args.json:
                print(render(result, args.all_routes) + "\n")

    for jd_path in args.jd:
        with open(jd_path, "r", encoding="utf-8") as f:
            hits = scan_jd(f.read())
        output["jd"][jd_path] = [{"signal": h.signal, "sentence": h.sentence} for h in hits]
        if not args.json:
            print(f"== JD:{jd_path}")
            if not hits:
                print("  JD 没有提到担保或工作许可 —— 不代表能担保,首轮沟通时直接问。")
            for h in hits:
                print(f"  {JD_TEXT[h.signal]}  {h.sentence}")
            print()

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
