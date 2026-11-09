# Getting started (no coding needed)

[中文版](使用说明.md)

This guide is for people who have never written code. You install Python once; after that you double-click one file and use a numbered menu.

---

## What the tool does

| Menu | What it does | You need |
|---|---|---|
| 1 | **Check visa sponsorship**: is the company on the UK sponsor register | Company names |
| 2 | **Suggest job titles**: wider titles you could search, based on your background, each with the evidence behind it | Your fact base (step 4) |
| 3 | **Scan for new jobs** on LinkedIn and Indeed; results saved as a web page and a spreadsheet | Setup (step 5) |
| 4 | **Track jobs**: add a job link; check tracked jobs are still open | Job links |
| 5 | **Check a job description**: "no sponsorship" wording, security clearance, hidden seniority, years required, pay vs the visa threshold | JD text or file |
| 6 | **Fact-check a CV**: every number, skill and job title must be traceable to your fact base | CV file + fact base |
| 7 | **Setup / change settings** | A few answers |
| 8 | Open this guide | |

**Everything stays on your computer.** The tool only reads public pages: the gov.uk sponsor register, LinkedIn, Indeed and company career pages.

---

## Step 1: Install Python (once)

**Windows**

1. Go to <https://www.python.org/downloads/> and click **Download Python 3.x**.
2. Run the installer. **First tick "Add python.exe to PATH" at the bottom**, then click **Install Now**.

**Mac**

1. Go to <https://www.python.org/downloads/> and download the macOS installer.
2. Run it and click Continue through the steps.

> Not sure which version you have? Skip the check: when you double-click the start file in step 3, it tells you if Python is missing or too old.

---

## Step 2: Download the tool

1. On the project's GitHub page, click the green **Code** button → **Download ZIP**.
2. **Unzip it first**:
   - Windows: right-click → Extract All.
   - Mac: double-click the ZIP.
3. Move the folder somewhere easy to find, such as Documents/job-search-tool.

> ⚠️ Don't double-click files while they are still inside the ZIP.

---

## Step 3: Open the menu

- **Windows**: double-click **`开始使用-Start.bat`**.
  - If a blue "Windows protected your PC" box appears, click **More info** → **Run anyway**. Windows shows this for every file downloaded from the internet.
- **Mac**: **right-click** **`开始使用-Start.command`** → **Open** → **Open**.
  - You only need to right-click the first time; after that you can double-click.
  - If it says you don't have permission: open Terminal, type `bash ` (with a space), drag the file into the window and press Enter.

Type a number and press Enter. After each task, press Enter to return to the menu. Type `L` to switch between Chinese and English.

**Most useful tip**: when you're asked for a file, **drag it from its folder into the window**; the path is filled in for you.

---

## Step 4: Prepare your fact base (needed for suggestions and CV checks)

The fact base is a text file called `master-cv-data.md` listing what you have **actually done**: jobs, projects, skills and numbers. Every suggestion and every CV check is measured against it.

1. Copy `templates/master-cv-data.md` to the top level of the tool folder (next to the Start files).
2. Open it in Notepad (Windows) or TextEdit (Mac) and fill it in:
   - For each job, write the company, title and dates, then what you did, which tools you used and any numbers.
   - Write numbers exactly; your CV must use the same figures.
   - Start a line with `❌` for things you have **not** done (for example `❌ never used Tableau`). Those lines never count as evidence.
3. Save it.

> 💡 An AI can turn your existing CV into this format, but **check every line yourself** and delete anything you didn't do. The tool trusts this file completely.

---

## Step 5: Setup (menu 7)

The wizard asks a few questions and writes the search settings for you. You never edit a config file by hand. Press Enter to accept the default in brackets.

You'll be asked:
- where you're looking (default London, UK);
- how many years of experience is too many;
- whether to filter out Senior / Lead roles;
- which **directions** to search.

**Directions come from your fact base:**
- **Core**: you have evidence for most of what these roles need.
- **Adjacent**: about half is covered; worth searching too.
- **Stretch**: thin evidence; read each JD carefully.
- **Missing** lists what such roles usually want that your fact base doesn't show yet. If you have done it, add it to the fact base and run setup again.

No fact base yet? Just type the job titles you want, separated by commas, for example `data analyst, ux researcher`.

Run setup again whenever you want to change your searches. Your tracked jobs are kept, and the old settings are saved as a `.bak` file.

---

## Step 6: Everyday use

**1 · Sponsorship**
- ✅ means the company is on the register with the Skilled Worker route.
- ❌ only means **this name** isn't on the register. The register uses legal names, which often differ from brand names (Bumble is registered as Badoo Limited). Use the Companies House link in the result to find the legal name.
- ❓ means the name is too common to tell (for example "Linear").

**2 · Job-title suggestions**
- Three tiers. Each direction shows the evidence you have, what's missing, and quotes from your fact base.
- After a few scans, each title also shows how often it appeared in your past scans. A title that never appears is unlikely to return anything.
- Type `core` or numbers like `1,3,5-8` to add titles to your searches.

**3 · Scan**
- The first time, you're asked to install the free scanning add-on (about a minute, installed inside the tool folder).
- The results open in your browser as a sortable, searchable table: new jobs are marked ✓, and a `.csv` copy opens in Excel. Both are saved in `scripts/logs`.
- LinkedIn and Indeed are for discovery only: **always confirm a job on the employer's own site before applying.**

**4 · Track**
- Paste a job link (Greenhouse, Ashby, Lever, Workable, Teamtailor, BambooHR or LinkedIn). The tool checks the job is open, then adds it.
- Or press Enter to check all your tracked jobs.

**5 · JD check**
- Drag in a `.txt` file, or press Enter and paste the text. Press Enter twice to finish.

**6 · CV check**
- Drag in your CV (`.md` or `.txt`).
- ❌ means fix the CV, or (if it's true) add it to the fact base first.
- ⚠️ means the wording differs from the fact base; check the meaning is the same.

---

## Three ways to use it

1. **Menu only** (this guide). No AI tool needed.
2. **With an AI coding assistant** (Claude Code, Codex, Cursor…): give it the folder and say "set up my job-search workspace" or "tailor my CV to this JD". It follows `SKILL.md`. Run every CV it writes through menu 6.
3. **With a chat AI**: paste `SKILL.md` first, then the files for the task. Run its CVs through menu 6 too.

---

## FAQ

- **The window flashes and closes, or says Python wasn't found.**
  Python is missing or wasn't added to PATH. Re-run the Python installer, choose **Modify**, and tick **Add Python to environment variables**.
- **429 errors or many failed tasks while scanning.**
  LinkedIn is rate-limiting you. Wait an hour or two, or scan fewer days.
- **"The config file has a formatting error".**
  The message says which line and what's wrong. If you can't fix it, delete `scripts/sweep_config.json` and run setup (menu 7) again.
- **The suggestions don't fit.**
  They come only from your fact base: add what you've really done. You can also type titles at the end of setup. The title list is `scripts/role_taxonomy.json` and can be edited in Notepad.
- **Is my data safe?**
  Your fact base, settings and scan results stay on your computer. Don't put them in a public folder or GitHub repository.

---

Salary and visa thresholds are indicative and change over time; check current gov.uk guidance. The tool reads public pages of LinkedIn, Indeed and applicant tracking systems; keep request rates reasonable and follow each site's terms.
