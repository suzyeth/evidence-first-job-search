# -*- coding: utf-8 -*-
"""
求职 sweep 引擎 —— 存活检查 + LinkedIn/Indeed 增量发现。
所有个人数据(跟踪的岗位、关键词、地点、过滤词)都在同目录的 sweep_config.json 里,脚本本身不用改。

用法(Python 3.10+):
  python sweep.py live [--log]              # 跟踪队列存活检查;--log 追加到 logs/live-log.md
  python sweep.py new 7                     # LinkedIn + Indeed 近 7 天增量发现
  python sweep.py linkedin 1                # 只扫 LinkedIn 近 24h
  python sweep.py linkedin 7 --resume       # 复用同日同参数已完成的任务(断点续跑)
  python sweep.py new 3 --plan              # 只打印任务矩阵,不联网
  python sweep.py new 7 --tracks GD,AI      # 只跑指定赛道
  python sweep.py new 7 --no-sponsor        # 不给命中岗位标担保状态(默认会查 gov.uk 担保名册)
  其他参数:--sites linkedin,indeed  --timeout 90  --retries 1  --workers 3  --config <path>

发现模式依赖 python-jobspy:
  python -m pip install --target vendor python-jobspy     # 装到脚本旁的 vendor/,不污染全局
"""
import sys, json, re, time, os, hashlib, subprocess, tempfile
import urllib.request
import concurrent.futures as cf
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(SCRIPT_DIR, "state")
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
VENDOR_DIR = os.path.join(SCRIPT_DIR, "vendor")
DEFAULT_SITES = ("linkedin", "indeed")

if os.path.isdir(VENDOR_DIR) and VENDOR_DIR not in sys.path:
    sys.path.insert(0, VENDOR_DIR)


# ---- 配置加载 ----
CONFIG_ENV = "SWEEP_CONFIG"


def _config_path():
    if "--config" in sys.argv:
        return os.path.abspath(sys.argv[sys.argv.index("--config") + 1])
    # 扫描子进程拿不到父进程的 --config,经环境变量传下去
    return os.environ.get(CONFIG_ENV) or os.path.join(SCRIPT_DIR, "sweep_config.json")


def _load_config():
    path = _config_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"找不到配置文件 {path}。复制 sweep_config.example.json 为 sweep_config.json 并填写。")
    except ValueError as exc:
        raise SystemExit(f"配置文件 JSON 格式错误:{path}: {exc}")


CONFIG = _load_config()
# tracked 条目:{"label": ..., "channel": ..., "args": ...};args 为列表或字符串,见 example 配置
TRACKED = [(t["label"], t["channel"], tuple(t["args"]) if isinstance(t["args"], list) else t["args"])
           for t in CONFIG.get("tracked", [])]
QUERIES = [tuple(q) for q in CONFIG.get("queries", [])]
EXCLUDE = re.compile(CONFIG.get("exclude_title_regex", r"senior|staff|lead|principal|head of|director|intern(ship)?"), re.I)
NOISE_CO = re.compile(CONFIG.get("noise_company_regex") or r"(?!x)x", re.I)
# 中介不过滤,只打标:直接 drop 会误杀(自家岗被误认为猎头的情况真实发生过)
AGENCY_CO = re.compile(CONFIG.get("agency_company_regex") or r"(?!x)x", re.I)
# LinkedIn 搜索是语义匹配,经常返回标题无关的结果。以下正则只影响终端展示清单,原始结果全部进 JSON 日志。
TITLE_RELEVANCE = {k: re.compile(v, re.I) for k, v in CONFIG.get("title_relevance", {}).items()}
DISPLAY_TRACK_PRIORITY = tuple(CONFIG.get("display_track_priority") or TITLE_RELEVANCE.keys())
INDEED_COUNTRY_DEFAULT = CONFIG.get("indeed_country_default", "UK")
INDEED_COUNTRY_BY_LOCATION = CONFIG.get("indeed_country_by_location", {})


def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def _check(chan, arg):
    """返回 True(在架)/ False(下架);网络错误抛异常由调用方记 ERR。"""
    if chan == "greenhouse":
        # 部分板只挂在 EU 节点,两个都试
        board, jid = arg
        try:
            d = json.loads(fetch(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"))
        except Exception:
            d = json.loads(fetch(f"https://boards-api.eu.greenhouse.io/v1/boards/{board}/jobs"))
        return any(j["id"] == int(jid) for j in d["jobs"])
    if chan == "ashby_title":
        # 优先用这个:精确匹配标题 + isListed,能抓到"同 req 改题升格"
        co, title = arg
        d = json.loads(fetch(f"https://api.ashbyhq.com/posting-api/job-board/{co}"))
        return any(j["title"].strip() == title and j.get("isListed") for j in d["jobs"])
    if chan == "ashby_id":
        co, jid = arg
        d = json.loads(fetch(f"https://api.ashbyhq.com/posting-api/job-board/{co}"))
        return any(j["id"] == jid for j in d["jobs"])
    if chan == "pinpoint":
        co, jid = arg
        d = json.loads(fetch(f"https://{co}.pinpointhq.com/postings.json"))
        return any(str(j["id"]) == str(jid) for j in d["data"])
    if chan == "teamtailor":
        # 在架 200,下架 410 Gone(抛 HTTPError)
        co, slug = arg
        fetch(f"https://{co}.teamtailor.com/jobs/{slug}")
        return True
    if chan == "workable":
        co, shortcode = arg
        d = json.loads(fetch(f"https://apply.workable.com/api/v1/widget/accounts/{co}?details=true"))
        return any(j.get("shortcode") == shortcode for j in d.get("jobs", []))
    if chan == "hitmarker":
        # 列表页是 JS 空壳,但详情页服务端真返回 404/200
        fetch(f"https://hitmarker.net/jobs/{arg}")
        return True
    if chan == "bamboohr":
        co, jid = arg
        d = json.loads(fetch(f"https://{co}.bamboohr.com/careers/list"))
        return any(str(j.get("id")) == str(jid) for j in d.get("result", []))
    if chan == "lever":
        co, pid = arg
        d = json.loads(fetch(f"https://api.lever.co/v0/postings/{co}?mode=json"))
        return any(j.get("id") == pid for j in d)
    raise ValueError(f"未知渠道 {chan}")


def live(log=False):
    lines = ["## Liveness — " + time.strftime("%Y-%m-%d %H:%M")]
    if not TRACKED:
        lines.append("  (sweep_config.json 的 tracked 为空)")
    for label, chan, arg in TRACKED:
        try:
            if chan == "linkedin":
                # 只能用 jobs/view 页面判死:jobs-guest/.../jobPosting/<id> 对已下架岗也返回 200
                h = fetch(f"https://www.linkedin.com/jobs/view/{arg}")
                ok = "No longer accepting applications" not in h
                time.sleep(2)
                if not ok:
                    # 死信双标记复核:文本标记 + closed-job 组件都中才坐实
                    time.sleep(3)
                    h2 = fetch(f"https://www.linkedin.com/jobs/view/{arg}")
                    marker = "No longer accepting applications" in h2
                    component = "closed-job" in h2
                    if marker and component:
                        lines.append(f"  DEAD {label}(双标记坐实)")
                    else:
                        lines.append(f"  DEAD? {label}(复核仅中 {int(marker)+int(component)}/2 标记,待人工核)")
                    continue
            else:
                ok = _check(chan, arg)
            lines.append(("  OK   " if ok else "  DEAD ") + label)
        except Exception as e:
            lines.append(f"  ERR  {label}: {type(e).__name__}")  # 网络错 ≠ 死,人工复核
    lines.append("\n规则:DEAD → 划掉 SUBMIT-QUEUE + applications.md 并从 tracked 摘掉;ERR → 换渠道人工核。"
                 "\n提醒:linkedin 渠道 OK 只代表镜像在,投前仍须到雇主 ATS 确认。")
    out = "\n".join(lines)
    print(out)
    if log:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(os.path.join(LOG_DIR, "live-log.md"), "a", encoding="utf-8") as f:
            f.write(out + "\n\n---\n\n")


def _text(value):
    """Convert pandas/numpy values to compact JSON-safe text."""
    if value is None:
        return ""
    value = str(value)
    return "" if value.lower() in ("nan", "nat", "none") else value


def _indeed_country(location):
    """JobSpy requires an explicit Indeed country; LinkedIn ignores this value."""
    for pattern, country in INDEED_COUNTRY_BY_LOCATION.items():
        if re.search(pattern, location, re.I):
            return country
    return INDEED_COUNTRY_DEFAULT


def _query_worker(site, term, loc, hours, output_path):
    """Run one source/query in an isolated process so a hung provider can be killed."""
    from jobspy import scrape_jobs
    df = scrape_jobs(
        site_name=[site], search_term=term, location=loc, results_wanted=25,
        hours_old=hours, country_indeed=_indeed_country(loc)
    )
    fields = (
        "title", "company", "location", "job_url", "date_posted", "site",
        "is_remote", "min_amount", "max_amount", "currency", "job_type"
    )
    rows = []
    for _, row in df.iterrows():
        rows.append({field: _text(row.get(field, "")) for field in fields})
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)


def _task_id(track, term, loc, site):
    return " | ".join((track, term, loc, site))


def _run_task(task, hours, timeout, retries):
    track, term, loc, site = task
    started = time.monotonic()
    error = ""
    for attempt in range(1, retries + 2):
        with tempfile.TemporaryDirectory(prefix="job-sweep-") as tmp:
            output = os.path.join(tmp, "result.json")
            cmd = [sys.executable, os.path.abspath(__file__), "_query_worker",
                   site, term, loc, str(hours), output]
            try:
                completed = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    env={**os.environ, CONFIG_ENV: _config_path()},
                    text=True, encoding="utf-8", errors="replace", timeout=timeout
                )
                if completed.returncode != 0:
                    tail = (completed.stderr or completed.stdout or "worker failed").strip().splitlines()
                    error = tail[-1][:240] if tail else "worker failed"
                    continue
                with open(output, "r", encoding="utf-8") as f:
                    rows = json.load(f)
                # JobSpy logs provider/network failures but can still exit 0 with an empty
                # DataFrame. Treat that combination as incomplete coverage, not a valid 0-hit.
                worker_log = "\n".join((completed.stdout or "", completed.stderr or ""))
                if not rows and re.search(r"\bERROR\s+-\s+JobSpy|Failed to establish a new connection|Max retries exceeded", worker_log, re.I):
                    tail = [line for line in worker_log.strip().splitlines() if line.strip()]
                    error = (tail[-1] if tail else "provider returned an error")[:240]
                    continue
                return {
                    "status": "ok", "track": track, "term": term, "location": loc,
                    "site": site, "attempts": attempt, "seconds": round(time.monotonic() - started, 1),
                    "rows": rows, "error": ""
                }
            except subprocess.TimeoutExpired:
                error = f"timeout>{timeout}s"
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"[:240]
    return {
        "status": "error", "track": track, "term": term, "location": loc,
        "site": site, "attempts": retries + 1, "seconds": round(time.monotonic() - started, 1),
        "rows": [], "error": error
    }


def _normal(value):
    return re.sub(r"[^a-z0-9]+", " ", _text(value).lower()).strip()


def _source_id(url, site):
    if site == "linkedin":
        match = re.search(r"(?:-|/)(\d{7,})(?:[/?]|$)", url)
        return match.group(1) if match else ""
    if site == "indeed":
        return parse_qs(urlparse(url).query).get("jk", [""])[0]
    return ""


def _job_key(row):
    # Normalized title/company/location deliberately joins LinkedIn and Indeed mirrors and
    # recognizes LinkedIn reposts with a new id. Source ids are retained as evidence below.
    return "::".join((_normal(row.get("title")), _normal(row.get("company")),
                      _normal(row.get("location"))))


def _matching_title_tracks(item):
    title = item.get("title", "")
    tracks = set(item.get("tracks", []))
    return [track for track in DISPLAY_TRACK_PRIORITY
            if track in tracks and TITLE_RELEVANCE.get(track) and TITLE_RELEVANCE[track].search(title)]


def _load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _run_key(days, sites, queries):
    payload = json.dumps({"date": time.strftime("%Y-%m-%d"), "days": int(days),
                          "sites": list(sites), "queries": queries}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def discovery_plan(days, sites, queries):
    tasks = [(track, term, loc, site) for track, term, loc in queries for site in sites]
    print(f"窗口: {days}d | 查询族: {len(queries)} | 来源: {', '.join(sites)} | 独立任务: {len(tasks)}")
    counts = {}
    for track, _, _ in queries:
        counts[track] = counts.get(track, 0) + 1
    print("赛道矩阵:", " · ".join(f"{k}={v}" for k, v in counts.items()))
    return tasks


def new(days=14, sites=DEFAULT_SITES, timeout=90, retries=1, resume=False,
        plan=False, workers=3, queries=None, route_name="all", sponsor=True):
    days = int(days)
    hours = days * 24
    sites = tuple(sites)
    queries = list(queries or QUERIES)
    tasks = discovery_plan(days, sites, queries)
    if plan:
        return
    try:
        import jobspy  # noqa: F401 - preflight before spawning dozens of isolated workers
    except ImportError:
        raise SystemExit(
            "缺少 python-jobspy。请先运行：\n"
            f"  {sys.executable} -m pip install --target \"{VENDOR_DIR}\" python-jobspy\n"
            "依赖未安装时不会启动扫描任务。"
        )

    os.makedirs(STATE_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    run_key = _run_key(days, sites, queries)
    # Keep 1d LinkedIn, 7d LinkedIn and all-source runs independently resumable.
    checkpoint_path = os.path.join(STATE_DIR, f"discovery-checkpoint-{run_key}.json")
    checkpoint = _load_json(checkpoint_path, {}) if resume else {}
    if checkpoint.get("run_key") != run_key:
        checkpoint = {"run_key": run_key, "created_at": datetime.now(timezone.utc).isoformat(),
                      "results": {}}
    completed = checkpoint["results"]
    pending = [task for task in tasks if _task_id(*task) not in completed]

    print(f"## 增量发现 [{route_name}] — 窗口 {days}d — {time.strftime('%Y-%m-%d %H:%M')}")
    print(f"任务 {len(tasks)}；断点命中 {len(tasks) - len(pending)}；待跑 {len(pending)}；并发 {workers}")
    if pending:
        with cf.ThreadPoolExecutor(max_workers=max(1, int(workers))) as executor:
            futures = {executor.submit(_run_task, task, hours, timeout, retries): task for task in pending}
            for future in cf.as_completed(futures):
                result = future.result()
                task_id = _task_id(result["track"], result["term"], result["location"], result["site"])
                completed[task_id] = result
                _save_json(checkpoint_path, checkpoint)
                marker = "OK" if result["status"] == "ok" else "ERR"
                detail = f"{len(result['rows'])} rows" if result["status"] == "ok" else result["error"]
                print(f"  {marker:<3} [{result['site']}] [{result['track']}] {result['term']} — {detail} ({result['seconds']}s)")

    results = [completed.get(_task_id(*task), {}) for task in tasks]
    successes = [r for r in results if r.get("status") == "ok"]
    failures = [r for r in results if r.get("status") != "ok"]
    coverage = (100.0 * len(successes) / len(tasks)) if tasks else 100.0

    merged = {}
    raw_count = 0
    for result in successes:
        for row in result.get("rows", []):
            raw_count += 1
            key = _job_key(row)
            if not key.strip(":"):
                continue
            item = merged.setdefault(key, dict(row, tracks=[], terms=[], sites=[], source_ids=[]))
            for field, value in (("tracks", result["track"]), ("terms", result["term"]),
                                 ("sites", result["site"])):
                if value not in item[field]:
                    item[field].append(value)
            sid = _source_id(row.get("job_url", ""), result["site"])
            if sid and sid not in item["source_ids"]:
                item["source_ids"].append(sid)

    history_path = os.path.join(STATE_DIR, "discovery-history.json")
    history = _load_json(history_path, {})
    now = datetime.now(timezone.utc).isoformat()
    for key, item in merged.items():
        item["is_new"] = key not in history
        old = history.get(key, {})
        history[key] = {
            "first_seen": old.get("first_seen", now), "last_seen": now,
            "seen_count": int(old.get("seen_count", 0)) + 1,
            "title": item.get("title", ""), "company": item.get("company", ""),
            "location": item.get("location", ""), "sites": item.get("sites", []),
            "source_ids": sorted(set(old.get("source_ids", []) + item.get("source_ids", [])))
        }
    _save_json(history_path, history)

    relevant = []
    contextual = []
    excluded = 0
    for item in merged.values():
        title, company = item.get("title", ""), item.get("company", "")
        item["agency"] = bool(AGENCY_CO.search(company))
        item["excluded_reason"] = "title" if EXCLUDE.search(title) else ("noise_company" if NOISE_CO.search(company) else "")
        item["matched_title_tracks"] = _matching_title_tracks(item)
        item["direct_title_match"] = bool(item["matched_title_tracks"])
        item["display_track"] = item["matched_title_tracks"][0] if item["matched_title_tracks"] else ""
        if item["excluded_reason"]:
            excluded += 1
        elif not item["direct_title_match"]:
            contextual.append(item)
        else:
            relevant.append(item)
    relevant.sort(key=lambda j: (not j["is_new"], j.get("tracks", [""])[0],
                                 _normal(j.get("company")), _normal(j.get("title"))))
    sponsor_summary = _tag_sponsors(relevant, sponsor)

    print(f"\n覆盖率: {len(successes)}/{len(tasks)} = {coverage:.1f}% | 失败 {len(failures)}")
    print(f"原始 {raw_count} | 跨来源/重挂去重 {len(merged)} | 硬过滤 {excluded} | "
          f"contextual 留档 {len(contextual)} | 标题直达待核 {len(relevant)}")
    if sponsor_summary:
        print(sponsor_summary + "(✅ 在册有 SW 路线 · ❓ 名字常见待查 · ⚠️ 无 SW 路线 · ❌ 查无,先查法人名)")
    if failures:
        print("\n### 未完成任务")
        for r in failures:
            print(f"  * [{r.get('site','?')}] [{r.get('track','?')}] {r.get('term','?')} — {r.get('error','unknown')}")

    by_track = {}
    for item in relevant:
        by_track.setdefault(item.get("display_track") or "OTHER", []).append(item)
    printed = set()
    for track in dict.fromkeys(track for track, _, _ in queries):
        candidates = by_track.get(track, [])
        if not candidates:
            continue
        print(f"\n### [{track}] 待核 {len(candidates)}")
        shown = 0
        for item in candidates:
            key = _job_key(item)
            if key in printed:
                continue
            printed.add(key)
            freshness = "NEW" if item["is_new"] else "SEEN"
            agency = " [中介·先问后投]" if item["agency"] else ""
            tag = f" {item['sponsor']['display']}" if "sponsor" in item else ""
            sources = "+".join(item.get("sites", []))
            print(f"  * [{freshness}|{sources}] {item.get('title','')[:62]} || "
                  f"{item.get('company','')[:30]}{agency}{tag} || {item.get('job_url','')[:100]}")
            shown += 1
            if shown >= 20:
                print(f"  ... 另 {len(candidates) - shown} 条见 JSON 日志")
                break

    stamp = time.strftime("%Y-%m-%d-%H%M%S")
    report = {
        "generated_at": now, "route": route_name, "days": days, "sites": sites,
        "query_families": len(queries),
        "tasks": len(tasks), "succeeded": len(successes), "failed": len(failures),
        "coverage_percent": round(coverage, 1), "raw_jobs": raw_count,
        "unique_jobs": len(merged), "filtered_jobs": excluded, "contextual_jobs": len(contextual),
        "review_jobs": len(relevant), "task_results": results, "jobs": list(merged.values())
    }
    log_path = os.path.join(LOG_DIR, f"discovery-scan-{stamp}.json")
    _save_json(log_path, report)
    print(f"\n机器日志: {log_path}")
    print("规则:LinkedIn/Indeed 只负责高召回发现；命中仍须过 5 道 Gate 并到雇主官网核活。")
    if coverage < 95:
        print("⚠️ 本轮覆盖率低于 95%，不得表述为‘全量日跑完成’；用 --resume 补失败任务。")


AGENCY_SPONSOR_TAG = {"status": "AGENCY", "legal": "", "town": "", "label": "担保?",
                      "display": "担保?(中介,雇主未知)"}
SPONSOR_ORDER = ("✅", "❓", "⚠️", "❌", "?", "中介")


def _sponsor_tagger(enabled):
    """加载担保名册;失败只告警,绝不拖垮扫描本身。"""
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


def _tag_sponsors(items, enabled):
    """给每个待核岗位挂 sponsor 字段,返回一行汇总;中介岗不查(公司名不是真雇主)。"""
    if not items:
        return ""
    tagger = _sponsor_tagger(enabled)
    if tagger is None:
        return ""
    counts = {}
    for item in items:
        tag = dict(AGENCY_SPONSOR_TAG) if item.get("agency") else dict(tagger.tag(item.get("company", "")))
        item["sponsor"] = tag
        key = "中介" if item.get("agency") else tag["label"].replace("担保", "")
        counts[key] = counts.get(key, 0) + 1
    return "担保:" + " · ".join(f"{k} {counts[k]}" for k in SPONSOR_ORDER if k in counts)


def _parse_discovery_args(args, forced_sites=None):
    days = 14
    if args and not args[0].startswith("--"):
        days = int(args.pop(0))
    sites = tuple(forced_sites or DEFAULT_SITES)
    timeout, retries, workers = 90, 1, 3
    resume = "--resume" in args
    plan = "--plan" in args
    if "--sites" in args:
        i = args.index("--sites")
        sites = tuple(s.strip() for s in args[i + 1].split(",") if s.strip())
    if "--timeout" in args:
        i = args.index("--timeout"); timeout = int(args[i + 1])
    if "--retries" in args:
        i = args.index("--retries"); retries = int(args[i + 1])
    if "--workers" in args:
        i = args.index("--workers"); workers = int(args[i + 1])
    return days, sites, timeout, retries, resume, plan, workers



def _filter_tracks(args, queries):
    if "--tracks" not in args:
        return queries, "all"
    wanted = {t.strip() for t in args[args.index("--tracks") + 1].split(",") if t.strip()}
    picked = [q for q in queries if q[0] in wanted]
    if not picked:
        raise SystemExit(f"--tracks {','.join(sorted(wanted))} 在 queries 里没有匹配的赛道")
    return picked, ",".join(sorted(wanted))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "live"
    if cmd == "live":
        live(log="--log" in argv)
    elif cmd == "_query_worker":
        _query_worker(argv[1], argv[2], argv[3], int(argv[4]), argv[5])
    elif cmd in ("new", "linkedin"):
        rest = argv[1:]
        queries, route = _filter_tracks(rest, QUERIES)
        forced_sites = ("linkedin",) if cmd == "linkedin" else None
        sponsor = "--no-sponsor" not in rest
        parsed = _parse_discovery_args(rest, forced_sites)
        new(*parsed, queries=queries, route_name=f"{cmd}:{route}", sponsor=sponsor)
    else:
        print(__doc__)


if __name__ == "__main__":
    # Windows 控制台默认编码遇到岗位名里的 ™ / emoji 会中断整轮扫描,强制 UTF-8 输出
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass
    main()
