# -*- coding: utf-8 -*-
"""把一次岗位扫描(logs/discovery-scan-*.json)存成能直接打开的表格:网页(可排序、可搜索)和 CSV(Excel 能开)。

用法:
  python report.py                 # 用 logs/ 里最新的一次扫描,生成后自动用浏览器打开
  python report.py 某次扫描.json   # 指定一次扫描
  python report.py --no-open       # 只生成文件,不打开
  python report.py --all           # 也列出标题不完全对口的岗位
"""
from __future__ import annotations

import argparse
import csv
import glob
import html
import json
import os
import sys
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from i18n import apply_lang_arg, tr  # noqa: E402

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")


def latest_log(log_dir: str | None = None) -> str | None:
    paths = sorted(glob.glob(os.path.join(log_dir or LOG_DIR, "discovery-scan-*.json")))
    return paths[-1] if paths else None


def _sponsor_text(job: dict) -> str:
    tag = job.get("sponsor")
    if isinstance(tag, dict):
        return tag.get("display") or tag.get("label") or ""
    if job.get("agency"):
        return tr("中介", "agency")
    return str(tag or "")


def rows_from_log(data: dict, include_context: bool = False) -> list[dict]:
    """Jobs worth a look: not filtered out and (unless include_context) with a title matching your search words;
    new ones first, then newest posting first."""
    rows = []
    for job in data.get("jobs", []):
        if job.get("excluded_reason"):
            continue
        if not include_context and job.get("direct_title_match") is False:
            continue
        rows.append({
            "new": bool(job.get("is_new")),
            "title": str(job.get("title", "")),
            "company": str(job.get("company", "")),
            "location": str(job.get("location", "")),
            "posted": str(job.get("date_posted", ""))[:10],
            "track": str(job.get("display_track") or ",".join(job.get("matched_title_tracks") or [])),
            "sponsor": _sponsor_text(job),
            "direct": bool(job.get("direct_title_match", True)),
            "url": str(job.get("job_url", "")),
        })
    def newest_first(r: dict) -> int:
        digits = r["posted"].replace("-", "")
        return -int(digits) if digits.isdigit() else 0

    rows.sort(key=lambda r: (not r["new"], not r["direct"], newest_first(r)))
    return rows


def write_csv(rows: list[dict], path: str) -> None:
    headers = [tr("新", "New"), tr("岗位", "Title"), tr("公司", "Company"), tr("地点", "Location"),
               tr("发布日期", "Posted"), tr("方向", "Track"), tr("担保", "Sponsor"), tr("链接", "Link")]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:  # utf-8-sig so Excel shows Chinese correctly
        writer = csv.writer(f)
        writer.writerow(headers)
        for r in rows:
            writer.writerow(["✓" if r["new"] else "", r["title"], r["company"], r["location"], r["posted"],
                             r["track"], r["sponsor"], r["url"]])


_PAGE = """<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root{{--bg:#fff;--fg:#1d1d1f;--muted:#6e6e73;--line:#e5e5ea;--accent:#0b63ce;--new:#e8f5e9}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151517;--fg:#f2f2f7;--muted:#a1a1a6;--line:#2c2c2e;--accent:#6aa9ff;--new:#1d3321}}}}
body{{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif}}
h1{{font-size:18px;margin:0 0 4px}} p{{color:var(--muted);margin:0 0 12px}}
.bar{{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-bottom:10px}}
input[type=search]{{flex:1;min-width:200px;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--fg)}}
.wrap{{overflow-x:auto}} table{{border-collapse:collapse;width:100%;min-width:720px}}
th,td{{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{cursor:pointer;user-select:none;position:sticky;top:0;background:var(--bg)}} th:hover{{color:var(--accent)}}
tr.new td:first-child{{background:var(--new)}} a{{color:var(--accent)}}
</style></head><body>
<h1>{title}</h1><p>{summary}</p>
<div class="bar"><input type="search" id="q" placeholder="{search}"><label><input type="checkbox" id="onlyNew"> {only_new}</label></div>
<div class="wrap"><table id="t"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>
<p>{rule}</p>
<script>
const q=document.getElementById('q'),n=document.getElementById('onlyNew'),rows=[...document.querySelectorAll('#t tbody tr')];
function f(){{const s=q.value.toLowerCase();rows.forEach(r=>{{r.style.display=(r.textContent.toLowerCase().includes(s)&&(!n.checked||r.classList.contains('new')))?'':'none'}})}}
q.oninput=f;n.onchange=f;
document.querySelectorAll('#t th').forEach((th,i)=>th.onclick=()=>{{const b=th.dataset.d!=='1';th.dataset.d=b?'1':'0';
const tb=document.querySelector('#t tbody');[...tb.rows].sort((x,y)=>(x.cells[i].innerText.localeCompare(y.cells[i].innerText))*(b?1:-1)).forEach(r=>tb.appendChild(r))}});
</script></body></html>
"""


def write_html(rows: list[dict], data: dict, path: str) -> None:
    cols = [tr("新", "New"), tr("岗位", "Title"), tr("公司", "Company"), tr("地点", "Location"),
            tr("发布", "Posted"), tr("方向", "Track"), tr("担保", "Sponsor")]
    body = []
    for r in rows:
        title = html.escape(r["title"])
        link = f'<a href="{html.escape(r["url"])}" target="_blank" rel="noopener">{title}</a>' if r["url"] else title
        cells = ["✓" if r["new"] else "", link, html.escape(r["company"]), html.escape(r["location"]),
                 html.escape(r["posted"]), html.escape(r["track"]), html.escape(r["sponsor"])]
        body.append(f'<tr class="{"new" if r["new"] else ""}">' + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    new_count = sum(r["new"] for r in rows)
    page = _PAGE.format(
        lang="en" if tr("zh", "en") == "en" else "zh",
        title=html.escape(tr("岗位扫描结果", "Job scan results")),
        summary=html.escape(tr(f"{data.get('generated_at', '')} · 近 {data.get('days', '?')} 天 · 共 {len(rows)} 条,其中新出现 {new_count} 条。点表头排序。",
                               f"{data.get('generated_at', '')} · last {data.get('days', '?')} days · {len(rows)} jobs, "
                               f"{new_count} new. Click a column to sort.")),
        search=html.escape(tr("搜索岗位、公司、地点…", "Search title, company, location…")),
        only_new=html.escape(tr("只看新出现的", "New only")),
        head="".join(f"<th>{html.escape(c)}</th>" for c in cols),
        body="\n".join(body),
        rule=html.escape(tr("LinkedIn/Indeed 只负责发现岗位:投之前去雇主自己的招聘页确认还在招,并检查 JD 是否担保。",
                            "LinkedIn/Indeed are for discovery only: confirm each job on the employer's own site and "
                            "check the JD for sponsorship before applying.")))
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)


def build(log_path: str, include_context: bool = False) -> tuple[str, str, int]:
    """Write <log>.html and <log>.csv next to the log. Returns (html_path, csv_path, row_count)."""
    with open(log_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    rows = rows_from_log(data, include_context)
    base = os.path.splitext(log_path)[0]
    write_html(rows, data, base + ".html")
    write_csv(rows, base + ".csv")
    return base + ".html", base + ".csv", len(rows)


def open_file(path: str) -> None:
    webbrowser.open("file://" + os.path.abspath(path).replace("\\", "/"))


def main(argv: list[str] | None = None) -> int:
    argv = apply_lang_arg(list(sys.argv[1:] if argv is None else argv))
    p = argparse.ArgumentParser(description=tr("把扫描结果存成网页和 Excel 表格", "Save a scan as a web page and a CSV"))
    p.add_argument("log", nargs="?", help=tr("扫描日志(默认最新一次)", "scan log (default: the latest)"))
    p.add_argument("--all", action="store_true", help=tr("也列出标题不完全对口的岗位", "also list jobs whose title only loosely matches"))
    p.add_argument("--no-open", action="store_true", help=tr("不自动打开", "don't open it"))
    p.add_argument("--lang", choices=("zh", "en"), help=tr("输出语言", "output language"))
    args = p.parse_args(argv)
    log = args.log or latest_log()
    if not log or not os.path.exists(log):
        print(tr("还没有扫描记录。先运行一次「扫新岗位」(python sweep.py new 3)。",
                 "No scans yet. Run a scan first (python sweep.py new 3)."), file=sys.stderr)
        return 1
    html_path, csv_path, count = build(log, args.all)
    print(tr(f"✅ {count} 条岗位已存为:\n   网页:{html_path}\n   表格:{csv_path}",
             f"✅ Saved {count} jobs:\n   Web page: {html_path}\n   Spreadsheet: {csv_path}"))
    if not args.no_open:
        open_file(html_path)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
