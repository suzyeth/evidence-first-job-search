# Evidence-First Job Search

[![CI](https://github.com/suzyeth/evidence-first-job-search/actions/workflows/ci.yml/badge.svg)](https://github.com/suzyeth/evidence-first-job-search/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/suzyeth/evidence-first-job-search)](https://github.com/suzyeth/evidence-first-job-search/releases/latest)

[中文说明](README.zh.md)

A job-search workflow for AI assistants, built around one rule: **every claim needs evidence.** Every line on your CV must trace back to your own fact base, and every job must be confirmed live on the employer's own careers page.

It is **built for the UK**, with checks against the gov.uk register of visa sponsors, and works with Claude Code, Codex, Cursor, Gemini CLI or any chat assistant.

## Just want to check visa sponsorship? 3 steps

![sponsor_check.py demo: Bumble resolves to Badoo Limited, Spotlight Sports to Spotlightsportsgroup, the common word "Linear" is flagged as ambiguous, and a JD is flagged as not sponsoring](docs/demo-sponsor-check.png)

You need [Python 3.10+](https://www.python.org/downloads/) and nothing else (on Windows, tick "Add python.exe to PATH" when installing).

1. Click the green **Code** button → **Download ZIP**, and unzip it.
2. Open a terminal in the `scripts` folder (Windows: open the folder, type `cmd` in the address bar, press Enter).
3. Run:

   ```bash
   python sponsor_check.py "Bumble" "Monzo" "Wise" --lang en
   ```

   Use `py` on Windows or `python3` on macOS if `python` isn't found. The first run downloads today's register (about 10 MB, ~10 s) and caches it for a day. Add `--jd JD.txt` to also scan a saved job description for sponsorship wording.

**A ❌ means this *name* isn't on the register, not that the employer can't sponsor.** The register lists legal entities. Bumble, for example, is listed as *Badoo Limited*, and "Amazon Web Services" doesn't appear under that name. The output links to Companies House so you can find the legal name. If you find one the tool missed, [report it](https://github.com/suzyeth/evidence-first-job-search/issues/new?template=sponsor-alias.yml) and it will be added to the alias table.

## Why the UK needs its own tool

- **Sponsorship lives in a register keyed by legal names.** Trading names, names written without spaces, `t/a` names and common words such as "Linear" all break a simple search.
- **LinkedIn shows closed jobs as if they were open.** The only reliable check is the employer's own applicant tracking system (Greenhouse, Ashby, Lever…).
- **Indeed UK lists roles that never reach LinkedIn,** so discovery searches both.
- **A licence isn't a yes.** A sponsor can still decline for a particular role, or the salary may sit below the Skilled Worker threshold.

## The workflow

### 1. Find jobs

```bash
python sweep.py new 7          # LinkedIn + Indeed, last 7 days
python boardsweep.py           # employers' own boards: Greenhouse, Ashby, Lever, Workable, Teamtailor
```

Results are de-duplicated across sites, senior roles are filtered out, and agencies are flagged. **Every job is tagged with its sponsor status**, e.g. `sponsor✅(Anysphere UK Ltd · Cheltenham)`, so you can see who can sponsor before opening the JD. If LinkedIn rate-limits you (429), use `--sites indeed` for now and rerun with `--resume` later.

### 2. Track the ones you want

```bash
python sweep.py add https://jobs.ashbyhq.com/<company>/<job-id>
python sweep.py live --prune   # check every tracked job; drop the ones confirmed closed
```

`add` takes a Greenhouse, Ashby, Lever, Workable, Teamtailor, BambooHR or LinkedIn link, confirms the job is live, and labels it for you.

### 3. Check sponsorship

```bash
python sponsor_check.py "Bumble" --jd JD.txt
python sponsor_check.py --watch "Bumble" "Monzo"          # report later register changes
python sponsor_check.py --add-alias "Bumble" "Badoo Limited"
```

`--watch` records a baseline and then reports employers that leave the register, change rating or lose their Skilled Worker route.

### 4. Check the JD

`boardsweep.py` reads every job's full description. You can also run `python jd_check.py JD.txt` on a saved one. It flags:

- "no sponsorship" wording, and SC/DV security clearance
- seniority hidden in the body ("We're looking for a Senior…")
- required experience above your limit
- salary below the Skilled Worker thresholds: £41,700 standard and £33,400 reduced floor, checked against gov.uk on 2026-10-13. Going rates for some occupation codes are higher.

### 5. Tailor your CV and fact-check it

Start from your **fact base** (`templates/master-cv-data.md`). Tailor each CV to the JD by changing only the summary, the skills line and the bullet order, never the facts. Then:

```bash
python fact_check.py ../applications/acme/resume_acme.md   # finds master-cv-data.md in a parent folder
```

The check fails if a number, skill, metric, employment date or job title isn't in your fact base. It also fails on a confidential term or a leftover `[FILL]`. An inflated "Senior…" title fails unless the fact base records it as a title. Exit code 1 means don't render the PDF. A 5-dimension review rubric and a standalone reviewer prompt cover what a script can't check.

### 6. After applying

Follow-up email templates, a take-home playbook and a salary negotiation handbook are in `references/`.

## Setup

**With an AI assistant**

- **Claude Code:** copy the folder to `~/.claude/skills/job-search/` and ask it to set up your job-search workspace.
- **Codex / Cursor / Gemini CLI:** put the folder in your workspace. The agent reads `AGENTS.md`, then `SKILL.md`.
- **Chat assistants:** paste `SKILL.md`, then the files the task needs.

**Scripts** (Python 3.10+, run from `scripts/`)

```bash
cp sweep_config.example.json sweep_config.json            # your searches and tracked jobs
cp boardsweep_config.example.json boardsweep_config.json  # employer board slugs
python -m pip install --target vendor python-jobspy       # only needed for sweep.py new / linkedin
```

`sponsor_check.py`, `jd_check.py` and `fact_check.py` use only the standard library. Your configs, logs and fact base are git-ignored.

**Language:** output is Chinese by default. Add `--lang en` to any script, or set `JOBSEARCH_LANG=en`. Reference docs are mostly in Chinese.

## Other countries

| Works anywhere | UK only |
|---|---|
| Finding jobs (`sweep.py`: about 60 countries on Indeed via JobSpy; `boardsweep.py`), tracking (`add` / `live`), `fact_check.py`, and the sponsorship-wording, hidden-seniority and years checks in `jd_check.py` | `sponsor_check.py` (gov.uk register), the salary thresholds and SC/DV flag in `jd_check.py`, and the right-to-work and salary reference docs |

For example, to search Germany:

- In `sweep_config.json`, put the location in each query, e.g. `["DA", "data analyst", "Berlin, Germany"]`. The example config already maps Germany, the Netherlands, Ireland, France, Spain, Canada, Australia, Singapore, the US and China to Indeed.
- In `boardsweep_config.json`, set `location_regex` to e.g. `"berlin|munich|germany|remote.*(europe|emea)"`. Country codes such as `DE` are expanded to names first.
- Pass `--no-sponsor` to skip UK register tags.

## Development

```bash
python -m pip install pytest pytest-cov
python -m pytest tests --cov=scripts
```

Tests run offline; CI runs them on Ubuntu and Windows with Python 3.10 and 3.12 and requires 80% coverage.

## Acknowledgements

The drafter–reviewer pattern and the idea of running a job search as an agent workflow were influenced by [MadsLorentzen/ai-job-search](https://github.com/MadsLorentzen/ai-job-search). Job discovery uses [JobSpy](https://github.com/speedyapply/JobSpy).

## Disclaimer

For personal, educational use. The scripts access public pages and APIs of LinkedIn, Indeed and applicant tracking systems; you are responsible for following each site's terms of service and keeping request rates reasonable. Salary and immigration information is indicative only; check current official guidance.

MIT License
