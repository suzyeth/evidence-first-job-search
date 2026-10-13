---
name: job-search
description: 求职作战系统——岗位发现(LinkedIn/Indeed 增量扫描 + 雇主 ATS 板直查)、已跟踪岗位存活检查、JD 驱动的简历/求职信定制、投前简历五维评审、PDF 渲染与投递追踪状态机。当用户说"跑一下求职""扫新岗""查队列死活""按这个 JD 改简历""评一下这份简历""渲简历 PDF""记一笔投递"、或任何涉及找工作/投递/简历定制/岗位筛选的任务时调用。
---

# Job Search 作战系统

> 本文件写给 AI 助手读(Claude Code、Codex、Cursor、Gemini CLI,或贴进任何聊天 AI 都可以)。顶部的 frontmatter 供支持 skill 的工具自动识别,其他工具可以忽略。

一套"发现 → 筛选 → 定制 → 评审 → 投递 → 追踪"的闭环。核心信条:

1. **聚合站只负责召回,雇主 ATS 才是真相。** LinkedIn/Indeed 上活着 ≠ 岗位活着;镜像死了也 ≠ 岗位死了。
2. **事实只有一个源头。** 所有简历都从 `master-cv-data.md` 往下派生,下游永远不能出现源头没有的声明。
3. **没读 JD 不动简历。** 每条定制都必须能链回 JD 原文的一行。
4. **岗位半衰期以天计。** 要么每周扫,要么关掉这条线;"建档但不扫"是最坏状态。

---

## 0. 首次使用:搭工作区

在用户选定的私有目录(**不要**放进任何公开 git 仓库)里按 `templates/` 建骨架:

```
<workspace>/
├── master-cv-data.md          ← templates/master-cv-data.md(事实库,唯一权威)
├── applications.md            ← templates/applications.md(投递 SSOT + 状态机)
├── SUBMIT-QUEUE.md            ← templates/SUBMIT-QUEUE.md(待投执行队列)
├── FOCUS.md                   ← templates/FOCUS.md(本周焦点 + 日志)
├── <track>/resume.md          ← 每条求职赛道一份主简历(从 master-cv 派生)
├── applications/<slug>/       ← 每个岗位一个包:JD.md + resume_<co>.md + cover-letter.md
├── pdf-template/              ← templates/resume.css, cover-letter.css
├── confidential-terms.txt     ← templates/confidential-terms.txt(保密词清单)
└── tools/                     ← scripts/ 下的全部脚本及配置
```

然后让用户填 `master-cv-data.md` 和 `tools/sweep_config.json`(赛道、关键词、地点、跟踪岗位)。**在这两份填好之前不要跑任何定制或扫描**——没有事实库就没有真实性校验。

`prompts/cv-reviewer.md` 是独立评审用的 prompt,文件开头写了在不同 AI 工具里怎么用。

---

## 1. 例行 sweep("跑一下求职")

详细规程见 [references/sweep-runbook.md](references/sweep-runbook.md)。流程:

1. `date` 校准日期;读 `FOCUS.md` / `applications.md` 修改时间,判断上轮之后有没有新投递回填。
2. **存活检查**:`python tools/sweep.py live --log` —— 逐个查 `sweep_config.json` 里 `tracked` 的岗位。
   - `DEAD` → 同步划掉 SUBMIT-QUEUE + applications.md,**并当场从 tracked 摘掉**(不摘下轮会重报)。
   - `DEAD?` → 只中一个死信标记,人工复核。
   - `ERR` → 网络错 ≠ 死,换渠道人工核。
3. **净新增**:`python tools/sweep.py new <距上轮天数>`(LinkedIn + Indeed),或 `linkedin 1` 做 24h 热扫。覆盖率 < 95% 时不得说"全量跑完",用 `--resume` 补。每个命中岗位会自动标担保状态:`担保✅(法人名 · 城市)` 先核对法人是不是同一家;`担保❓` 名字太常见,必须先查法人名;`担保❌` 名册查无;`担保?(中介…)` 中介岗不查。标注只是初筛,入队前仍按第 ③ 道 Gate 用 `sponsor_check.py --jd` 复核。
4. **雇主板补扫**:`python tools/boardsweep.py [--since YYYY-MM-DD]`,直打 Ashby / Greenhouse 公开 API,同样标担保状态(Greenhouse 用 JD 里的真实公司名,Ashby 用板 slug;slug 和公司名差太多时用 `sponsor_check.py --add-alias` 加对照)。它还会读每个命中岗位的 JD 全文自动体检:`JD❌不担保` / `JD⚠️要安全审查(SC/DV)` / `正文Senior` / `要N年+`(超过配置里的 `max_years`)/ `£Xk<门槛`。这几项分别对应 5 道 Gate 的 ③②②③,标出来的岗位直接降级,不用再点开 JD。
5. 新岗逐个过 **5 道 Gate**(见下),过了才入 SUBMIT-QUEUE,**入队即加进 tracked**:`python tools/sweep.py add <雇主 ATS 链接>`(自动识别渠道、确认在架、生成标签;Ashby 自动改成按标题跟踪)。优先用雇主 ATS 链接,LinkedIn 链接只在找不到雇主页时用。
6. 回写 `applications.md`(新增"第 N 轮"段)+ `FOCUS.md` 日志;清临时文件。

### 5 道 Gate(入队前全过)

| Gate | 判据 | 一票否决的典型信号 |
|------|------|------|
| ① 存活 | 雇主自己的 ATS / careers 页在架 | 只在 LinkedIn 镜像存在、雇主板查无 |
| ② 级别 | **读正文首段**,不只看标题(`jd_check.py` 会自动标「正文Senior」和超线年限) | Senior/Lead/Principal;"X+ years" 超出用户年限 —— 标题不带 Senior 但正文第一句是 Senior 的情况很常见 |
| ③ 工作权 | 用户所在国家的工作许可/担保条件 | JD 明写不担保;雇主不在官方担保名册 —— 英国用 `python tools/sponsor_check.py "<公司>" --jd <JD.md>` 一步查名册 + 扫 JD |
| ④ 硬技能 | Required 段逐条对 master-cv | 有 master-cv 里完全没有证据的硬性要求 |
| ⑤ 渠道 | 直投 vs 中介 | 中介岗:先问清雇主再给 CV,不裸交 |

---

## 2. JD 驱动的简历 / 求职信定制

完整步骤见 [references/jd-driven-resume-workflow.md](references/jd-driven-resume-workflow.md)。要点:

1. 抓 JD 原文存 `applications/<slug>/JD.md`(带 source URL + 日期)——岗位下线后这是唯一记录。
2. 抽 **5 类 signal**:title 关键词 / 职责动词 / 必备技能 / 领域 / 价值观信号。
3. 每条 signal 对照 `master-cv-data.md`:✅ 有证据 → 可强调;⚠️ 做过但没记 → **先补 master-cv** 再用;❌ 没做过 → 不加,无论 JD 多想要。
4. 简历只改三处:**Summary 首句、Skills 关键词、bullet 顺序**。经历事实不改。
5. 求职信 Para 2 = 这家公司的差异点(每句链回 JD 原文);Para 3 = 2–3 个最对位的证据项目。
6. 写作风格按 [references/tone.md](references/tone.md):具体胜抽象、动词胜形容词、数字胜声明。

---

## 3. 投前评审(渲 PDF 之前必跑)

按 [references/cv-review-rubric.md](references/cv-review-rubric.md) 五维评估:A JD 对齐 / **B 真实性(一票否决)** / C 6 秒扫描 / D ATS 文字层 / E 差异化。可以在当前对话里直接跑,但更推荐用 [prompts/cv-reviewer.md](prompts/cv-reviewer.md) 在**新对话 / 独立代理**里跑:写简历的和评简历的分开,更不容易自我放水。

**先跑机器核对**:`python tools/fact_check.py applications/<slug>/resume_<co>.md`。数字 / 技能 / 指标在事实库找不到、命中 `confidential-terms.txt` 保密词、残留 `[FILL]` 都会判 ❌(退出码 1)。处理方式只有两种:改简历,或者(确实做过的)先把对外写法补进 master-cv 的「对外关键词」节。机器核对过了再做五维人工评审。

保密词放在工作区根目录的 `confidential-terms.txt`(模板见 `templates/`),一行一个。

---

## 4. 渲染 PDF

见 [references/pdf-rendering.md](references/pdf-rendering.md)。Pandoc + wkhtmltopdf(含中文改用 weasyprint)。文件名 `<First>_<Last>_Resume_<Track>[_<Company>].pdf`,下划线无空格,< 1 MB,简历 ≤ 2 页,求职信 1 页。

---

## 5. 追踪状态机(`applications.md`)

📝 Drafting → ✉️ Applied → 👀 Screening → 📞 Phone Screen → 🎯 Interview → 💼 Offer → 🤝 Accepted;终态 ❌ Rejected / 🚪 Withdrew / 💤 Ghosted。

- 终态行移到"归档"表,**不删**。
- `applications.md` 和 `FOCUS.md` 必须同步更新——只改一个是最常见的漂移来源。
- 反思阈值:3 次拒 → 复查简历/求职信;5 次 → 复查赛道选择;10 次 → 复查整体定位。

---

## 6. 投递之后

| 场景 | 读哪份 |
|------|--------|
| 投出 2 周没回音、面试后感谢信、被拒后回复 | [references/follow-up-emails.md](references/follow-up-emails.md) |
| 收到 take-home / 设计题 / 编程题 | [references/take-home-playbook.md](references/take-home-playbook.md) |
| 收到 offer、谈薪、接受、辞职 | [references/salary-negotiation.md](references/salary-negotiation.md) |

起草这几类邮件时:经历要点只能取自 `master-cv-data.md`,遵守保密项;占位符全部替换后再给用户发送。邮件由用户自己发,不要代发。

---

## 隐私纪律(对任何使用者都适用)

- 工作区放本地私有目录;**不要** `git init` 后推公开仓库,不要把简历/投递表贴进在线 PDF 转换器或 pastebin。
- 投递表、薪资谈判记录、签证/身份信息属于敏感信息,不汇总进任何可分享文档,也不写进求职信。
- 前雇主保密数据(营收、内部代号、未公开指标)只存在 master-cv 的"内部备注"区,永不进候选人面向的文档。
