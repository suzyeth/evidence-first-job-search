# Evidence-First Job Search

[![CI](https://github.com/suzyeth/evidence-first-job-search/actions/workflows/ci.yml/badge.svg)](https://github.com/suzyeth/evidence-first-job-search/actions/workflows/ci.yml)

[中文说明](README.zh.md)

An AI-assisted job-search workflow where **every claim needs evidence**: every CV line traces back to your own fact base, and every posting has to be confirmed live on the employer's own ATS. **Built for the UK market**, with gov.uk visa-sponsor checks. It covers the whole pipeline: finding roles, checking whether a posting is really live, verifying visa sponsorship, JD-driven CV tailoring, pre-submission review, follow-ups, and salary negotiation.

It works with any assistant. Claude Code, Codex, Cursor and Gemini CLI can read the files directly; with a chat assistant (ChatGPT, Claude, Gemini…) you paste in the relevant files.

## Just want to check visa sponsorship? 3 steps

![sponsor_check.py demo: Bumble resolves to Badoo Limited, Spotlight Sports to Spotlightsportsgroup, the common word "Linear" is flagged as ambiguous, and a JD is flagged as not sponsoring](docs/demo-sponsor-check.png)

No git, no AI tool, no packages. You only need [Python 3.10+](https://www.python.org/downloads/) (on Windows, tick "Add python.exe to PATH" during install).

1. On this page click the green **Code** button → **Download ZIP**, then unzip it.
2. Open a terminal in the unzipped folder's `scripts` directory (Windows: open the folder, type `cmd` in the address bar, press Enter).
3. Run it with the companies you want to check:

   ```bash
   python sponsor_check.py "Bumble" "Monzo" "Wise"
   ```

   On Windows, use `py` if `python` isn't found; on macOS, use `python3`. The first run downloads today's register (about 10 MB, ~10 s); after that it's cached for a day. Add `--jd JD.txt` to also scan a saved job description for sponsorship wording.

Can't find a company? It may be registered under a different legal name. The output links to Companies House so you can look it up, and you can [report it here](https://github.com/suzyeth/evidence-first-job-search/issues/new?template=sponsor-alias.yml) so it gets added to the alias table.

## Why

Most AI job-search tools assume the US market. This one handles the UK-specific parts:

- **Visa sponsorship checks.** The JD alone isn't enough; the employer has to appear on the gov.uk Register of Licensed Sponsors. The register uses *legal entity* names, so a trading name returning zero hits doesn't mean no licence. `scripts/sponsor_check.py` downloads the day's register, handles the lookup traps (names written without spaces, `t/a` trading names, quoted names with commas, common-word company names), maps trading names to legal entities, points you to Companies House when nothing matches, and scans the JD for sponsorship wording, all in one command.
- **Is the LinkedIn posting actually live?** LinkedIn serves normal-looking pages for closed jobs. The runbook gives a reliable dead-job check plus the public APIs of the ATSs UK employers use (Greenhouse, Ashby, Lever, Workable, Teamtailor…), so you can verify at the source.
- **Indeed UK blind spot.** Some roles never reach LinkedIn, so discovery scans both.
- **UK salary bands**, the negotiation process, and less obvious leverage such as sponsorship term length.

## What's inside

| Stage | Contents |
|-------|----------|
| Discover | `scripts/sweep.py`: incremental LinkedIn + Indeed scan (resumable, cross-site dedup, filters senior roles, tags agencies). `scripts/boardsweep.py`: scans target employers' own job boards. **Every hit is tagged with its sponsor-register status**, e.g. `担保✅(Anysphere UK Ltd · Cheltenham)` / `担保❓` / `担保❌`, so you see who can sponsor before you open the JD (`--no-sponsor` to turn off) |
| Track | `sweep.py live`: checks every tracked posting across 9 channels (Greenhouse, Ashby, Lever, Workable, LinkedIn…) |
| Screen | 5 gates: live / level fit / right to work / evidenced hard skills / direct vs agency |
| Sponsorship | `scripts/sponsor_check.py`: gov.uk sponsor register lookup with trading-name aliases + JD sponsorship-wording scan. `--add-alias "Brand" "Legal Name Ltd"` adds a mapping after checking the legal name is really on the register |
| JD check | `scripts/jd_check.py`, also run automatically by `boardsweep.py` on every hit's full JD: flags "no sponsorship" wording, SC/DV security clearance, seniority hidden in the body ("We're looking for a Senior…"), years of experience above your limit, and salary below the Skilled Worker thresholds (£41,700 standard / £33,400 reduced floor, checked against gov.uk on 2026-10-13; occupation going rates can be higher) |
| Tailor | Extract 5 signal types from the JD and map them to your own fact base. **Only true claims ship** |
| Fact check | `scripts/fact_check.py`: fails the CV if a number, skill or metric isn't in your fact base, or if a confidential term or `[FILL]` slipped in. Exit code 1 = don't render the PDF |
| Review | 5-dimension rubric plus a standalone reviewer prompt (truthfulness is a hard veto) |
| After applying | Follow-up email templates, take-home playbook, salary negotiation handbook |
| Templates | Fact base, application tracker, submit queue, JD archive, cover-letter skeleton, CV PDF stylesheets |

Reference docs and script output are mostly in Chinese; code, configs and email templates are in English.

## Usage

- **Claude Code:** copy the folder to `~/.claude/skills/job-search/` and ask it to set up your job-search workspace.
- **Codex / Cursor / Gemini CLI:** put the folder in your workspace. The agent reads `AGENTS.md`, then works from `SKILL.md`.
- **Chat assistants:** paste `SKILL.md` first, then the files the task needs (e.g. `references/jd-driven-resume-workflow.md` + your fact base + the JD).

Whichever you use, start by filling in your **fact base** from `templates/master-cv-data.md`. Every CV is derived from it, and that is what stops the AI from inventing experience.

## Scripts (Python 3.10+)

```bash
cd scripts
cp sweep_config.example.json sweep_config.json
cp boardsweep_config.example.json boardsweep_config.json
python -m pip install --target vendor python-jobspy   # discovery only

python sweep.py new 3 --plan     # show the query matrix, no network
python sweep.py live --log       # liveness check for tracked jobs
python sweep.py new 7            # new postings from the last 7 days, each tagged with sponsor status
python boardsweep.py --since 2026-01-01   # + sponsor tag and JD check on every hit
python sponsor_check.py "Bumble" "Monzo" --jd JD.md   # stdlib only, no install
python fact_check.py ../applications/acme/resume_acme.md --master ../master-cv-data.md
python jd_check.py JD.txt --max-years 3                 # check one saved JD
python sponsor_check.py --add-alias "Bumble" "Badoo Limited"
```

Your configs, logs and fact base are listed in `.gitignore`. Tests run offline: `python -m pip install pytest pytest-cov && python -m pytest tests --cov=scripts` (coverage gate: 80%).

## Other countries

Change the locations and `indeed_country_*` in `sweep_config.json`, then replace the right-to-work section of `references/sweep-runbook.md` and the salary bands in `references/salary-negotiation.md` with local equivalents.

## Acknowledgements

The drafter-reviewer pattern and the idea of running a job search as an agent workflow were influenced by [MadsLorentzen/ai-job-search](https://github.com/MadsLorentzen/ai-job-search). Job discovery uses [JobSpy](https://github.com/speedyapply/JobSpy).

## Disclaimer

For personal, educational use. The scripts access public pages and APIs of LinkedIn, Indeed and various ATSs. You are responsible for complying with each site's terms of service and keeping request rates reasonable. Salary and immigration information is indicative only; check current official guidance.

MIT License
