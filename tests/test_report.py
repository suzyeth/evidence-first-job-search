import csv
import json

from conftest import load_script

rp = load_script("report")

LOG = {
    "generated_at": "2026-01-02T10:00:00Z", "days": 3,
    "jobs": [
        {"title": "Old Analyst", "company": "A", "location": "London", "date_posted": "2026-01-01",
         "is_new": False, "direct_title_match": True, "job_url": "https://x/1", "display_track": "DA"},
        {"title": "New Analyst <b>", "company": "B & Co", "location": "Leeds", "date_posted": "2026-01-02",
         "is_new": True, "direct_title_match": True, "job_url": "https://x/2", "display_track": "DA",
         "sponsor": {"display": "担保✅(B Ltd · Leeds)"}},
        {"title": "Senior Analyst", "company": "C", "excluded_reason": "senior", "job_url": "https://x/3"},
        {"title": "Barista", "company": "D", "is_new": True, "direct_title_match": False, "job_url": "https://x/4"},
        {"title": "Agency Analyst", "company": "E", "is_new": True, "agency": True, "date_posted": "",
         "job_url": "https://x/5", "matched_title_tracks": ["DA", "AI"]},
    ],
}


def test_rows_filter_and_order():
    rows = rp.rows_from_log(LOG)
    assert [r["title"] for r in rows] == ["New Analyst <b>", "Agency Analyst", "Old Analyst"]
    assert rows[0]["sponsor"].startswith("担保✅") and rows[1]["sponsor"] == "中介" and rows[1]["track"] == "DA,AI"
    assert len(rp.rows_from_log(LOG, include_context=True)) == 4


def test_build_writes_html_and_excel_friendly_csv(tmp_path):
    log = tmp_path / "discovery-scan-2026-01-02-100000.json"
    log.write_text(json.dumps(LOG), encoding="utf-8")
    html_path, csv_path, count = rp.build(str(log))
    assert count == 3
    page = open(html_path, encoding="utf-8").read()
    assert "New Analyst &lt;b&gt;" in page and "B &amp; Co" in page and 'href="https://x/2"' in page
    assert "prefers-color-scheme:dark" in page and "共 3 条,其中新出现 2 条" in page
    raw = open(csv_path, "rb").read()
    assert raw.startswith(b"\xef\xbb\xbf")  # BOM so Excel reads Chinese
    rows = list(csv.reader(open(csv_path, encoding="utf-8-sig")))
    assert rows[0][1] == "岗位" and rows[1][0] == "✓"


def test_main_latest_log_and_no_logs(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(rp, "LOG_DIR", str(tmp_path))
    assert rp.main(["--no-open"]) == 1
    assert "还没有扫描记录" in capsys.readouterr().err
    (tmp_path / "discovery-scan-2026-01-01-000000.json").write_text(json.dumps({"jobs": []}), encoding="utf-8")
    (tmp_path / "discovery-scan-2026-01-02-000000.json").write_text(json.dumps(LOG), encoding="utf-8")
    opened = []
    monkeypatch.setattr(rp, "open_file", opened.append)
    assert rp.main(["--lang", "en"]) == 0
    out = capsys.readouterr().out
    assert "Saved 3 jobs" in out and opened and opened[0].endswith("2026-01-02-000000.html")
    assert rp.main(["--all", "--no-open"]) == 0


def test_open_file_uses_browser(monkeypatch):
    seen = []
    monkeypatch.setattr(rp.webbrowser, "open", seen.append)
    rp.open_file("C:\\a\\b.html")
    assert seen[0].startswith("file://") and "\\" not in seen[0]
