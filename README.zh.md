# Evidence-First Job Search · 证据优先的 AI 求职工作流

[![CI](https://github.com/suzyeth/evidence-first-job-search/actions/workflows/ci.yml/badge.svg)](https://github.com/suzyeth/evidence-first-job-search/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/suzyeth/evidence-first-job-search)](https://github.com/suzyeth/evidence-first-job-search/releases/latest)

[English](README.md)

一套交给 AI 助手执行的求职工作流，只有一条原则：**每一句都要有证据**。简历上的每条经历都要能在你自己的事实库里找到出处，每个岗位都要在雇主自己的招聘页上确认还在招。

**专门针对英国市场**，能直接对照 gov.uk 的签证担保名册；Claude Code、Codex、Cursor、Gemini CLI 或任何聊天 AI 都能用。

## 只想查签证担保？3 步上手

![sponsor_check.py 演示：Bumble 查到法人 Badoo Limited，Spotlight Sports 查到连写的 Spotlightsportsgroup，常见词 "Linear" 被标为无法判断，JD 被识别为不担保](docs/demo-sponsor-check.png)

只需要装好 [Python 3.10 以上版本](https://www.python.org/downloads/)，别的都不用装（Windows 安装时记得勾选 "Add python.exe to PATH"）。

1. 在本页点绿色的 **Code** 按钮 → **Download ZIP**，下载后解压。
2. 在解压出来的 `scripts` 文件夹里打开命令行（Windows：打开这个文件夹，在地址栏输入 `cmd` 回车）。
3. 运行：

   ```bash
   python sponsor_check.py "Bumble" "Monzo" "Wise"
   ```

   找不到 `python` 的话，Windows 上换成 `py`，Mac 上换成 `python3`。第一次运行会自动下载当天的名册（约 10 MB，十秒左右），之后一天内直接用缓存。把 JD 存成文本文件、加上 `--jd JD.txt`，还能顺便看 JD 里写的是愿意担保还是不担保。

**❌ 的意思是"这个名字"不在名册上，不等于这家公司不能担保。** 名册登记的是法人名：比如 Bumble 登记的是 *Badoo Limited*，"Amazon Web Services" 这个名字在名册里就找不到。结果里会给出 Companies House 的链接，方便你反查法人名；如果发现工具漏掉的对应关系，欢迎[在这里提交](https://github.com/suzyeth/evidence-first-job-search/issues/new?template=sponsor-alias.yml)，核实后加进对照表。

## 为什么英国需要单独的工具

- **担保名册按法人名登记。** 商号、连写无空格的名字、带 `t/a` 的名字、"Linear" 这种常见词，直接搜都会出错。
- **LinkedIn 上已经关闭的岗位，看起来和在招的一模一样。** 唯一可靠的办法是去雇主自己的招聘系统（Greenhouse、Ashby、Lever…）核实。
- **有些岗位只发在 Indeed UK，LinkedIn 上根本没有**，所以两边一起扫。
- **有牌照不等于这个岗位能办。** 雇主可能明确说这个岗位不担保，或者薪资低于 Skilled Worker 门槛。

## 工作流程

### 1. 找岗位

```bash
python sweep.py new 7          # LinkedIn + Indeed,近 7 天
python boardsweep.py           # 直接扫雇主招聘板:Greenhouse、Ashby、Lever、Workable、Teamtailor
```

结果会跨站去重、过滤掉 Senior 岗、标出中介。**每个岗位都自动标上担保状态**，比如 `担保✅(Anysphere UK Ltd · Cheltenham)`，打开 JD 之前就知道这家能不能办签证。LinkedIn 报 429（被限流）时，先用 `--sites indeed` 顶上，过一阵再用 `--resume` 补跑。

### 2. 跟踪想投的岗位

```bash
python sweep.py add https://jobs.ashbyhq.com/<公司>/<岗位ID>
python sweep.py live --prune   # 检查所有在跟的岗位;确认下架的自动摘掉
```

`add` 支持 Greenhouse、Ashby、Lever、Workable、Teamtailor、BambooHR 和 LinkedIn 的链接：会先确认岗位还在招，再自动生成标签加进列表。

### 3. 查签证担保

```bash
python sponsor_check.py "Bumble" --jd JD.txt
python sponsor_check.py --watch "Bumble" "Monzo"          # 之后报告名册变动
python sponsor_check.py --add-alias "Bumble" "Badoo Limited"
```

`--watch` 第一次先记基线，之后会报告掉出名册、评级变化、失去 Skilled Worker 路线的雇主。

### 4. JD 体检

`boardsweep.py` 会自动读每个岗位的 JD 全文；单独一份存好的 JD 也可以用 `python jd_check.py JD.txt` 检查。会标出：

- 写明不担保、要求 SC/DV 安全审查
- 标题没写、正文里藏着的 Senior（"We're looking for a Senior…"）
- 年限要求超过你设的上限
- 薪资低于 Skilled Worker 门槛：标准 £41,700，降低标准下限 £33,400（2026-10-13 核对 gov.uk）。部分职业代码的 going rate 更高。

### 5. 定制简历，再做事实核对

从你的**事实库**（`templates/master-cv-data.md`）出发。按 JD 定制简历时，只改开头一句、技能行和要点顺序，事实一律不动。改完运行：

```bash
python fact_check.py ../applications/acme/resume_acme.md   # 会自动向上找 master-cv-data.md
```

数字、技能、指标、任职时间、职位在事实库里找不到，或者混进了保密词、残留 `[FILL]`，都会判不通过。写成 "Senior…" 的职位，必须是事实库里有记录的职位。退出码为 1 就别渲 PDF。脚本查不了的部分，交给五维评审规则和一个独立评审 prompt。

### 6. 投递之后

跟进邮件模板、take-home 打法、谈薪手册都在 `references/` 里。

## 安装和配置

**配合 AI 助手使用**

- **Claude Code**：把整个文件夹放到 `~/.claude/skills/job-search/`，然后说"帮我搭求职工作区"。
- **Codex / Cursor / Gemini CLI**：把文件夹放进你的工作区，AI 会先读 `AGENTS.md`，再按 `SKILL.md` 干活。
- **聊天 AI**：先贴 `SKILL.md`，再按任务贴对应的文件。

**脚本**（Python 3.10+，在 `scripts/` 目录下运行）

```bash
cp sweep_config.example.json sweep_config.json            # 你的搜索词和在跟的岗位
cp boardsweep_config.example.json boardsweep_config.json  # 目标公司的招聘板 slug
python -m pip install --target vendor python-jobspy       # 只有 sweep.py new / linkedin 需要
```

`sponsor_check.py`、`jd_check.py`、`fact_check.py` 只用标准库，不用装任何东西。你的配置、日志、事实库都在 `.gitignore` 里，不会被提交。

**语言**：输出默认中文；任何脚本加 `--lang en`（或设置环境变量 `JOBSEARCH_LANG=en`）就是英文。参考文档主要是中文。

## 换成别的国家

| 哪国都能用 | 只支持英国 |
|---|---|
| 找岗位（`sweep.py`:JobSpy 支持约 60 个国家的 Indeed;`boardsweep.py`）、跟踪岗位（`add` / `live`）、`fact_check.py`,以及 `jd_check.py` 里的担保措辞、隐藏 Senior、年限检查 | `sponsor_check.py`(gov.uk 担保名册）、`jd_check.py` 的薪资门槛和 SC/DV 标记，以及工作许可、薪资相关的参考文档 |

以德国为例：

- `sweep_config.json` 里每条搜索写上地点，比如 `["DA", "data analyst", "Berlin, Germany"]`。示例配置已经把德国、荷兰、爱尔兰、法国、西班牙、加拿大、澳大利亚、新加坡、美国和中国对应到了 Indeed。
- `boardsweep_config.json` 里把 `location_regex` 改成比如 `"berlin|munich|germany|remote.*(europe|emea)"`。`DE` 这样的国家代码会先转成国名。
- 加 `--no-sponsor` 跳过英国担保名册标注。

## 开发

```bash
python -m pip install pytest pytest-cov
python -m pytest tests --cov=scripts
```

测试全程不联网；CI 在 Ubuntu 和 Windows、Python 3.10 和 3.12 上运行，覆盖率低于 80% 判失败。

## 致谢

起草 + 评审分离的做法，以及把求职当成 agent 工作流来跑的思路，参考了 [MadsLorentzen/ai-job-search](https://github.com/MadsLorentzen/ai-job-search)。岗位发现基于 [JobSpy](https://github.com/speedyapply/JobSpy)。

## 免责声明

本项目仅供个人学习和求职使用。脚本会访问 LinkedIn、Indeed 和各招聘系统的公开页面或接口，请自行遵守这些网站的服务条款，并控制访问频率。薪资和签证信息仅供参考，以官方最新政策为准。

MIT License
