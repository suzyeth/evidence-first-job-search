# JD 驱动的简历 / 求职信定制

**核心原则:没读 JD 之前不动任何候选人面向的文档。**

凭"听起来对"的印象写出来的段落,30 分钟面试就会崩。招聘官会问"具体哪条 JD 让你这么写?"——答不出就是减分。

---

## Step 1 — 抓 JD 全文,存档

```
applications/<company-slug>/
├── JD.md              ← JD 原文 + 抓取日期 + source URL
├── resume_<co>.md     ← 本岗定制版简历
├── CV-TWEAKS.md       ← (可选)改了什么、为什么
├── form-answer.md     ← (可选)投递表单的短答题
└── cover-letter.md
```

抓取优先级:
1. 雇主官方 careers 页 / ATS(Greenhouse / Ashby / Lever / Workable)
2. JS 渲染抓不到 → 试 LinkedIn / 行业招聘站镜像
3. 搜索引擎 site 限定查询抓 snippet
4. 最后:请用户打开页面复制全文

JD.md 必须包含:source URL + 日期、职责原文(引用,不意译)、Required qualifications、核心 signal 总结。

## Step 2 — 抽 5 类 signal

| Signal | 怎么提取 | 例子 |
|--------|---------|------|
| Title 关键词 | 岗位名 + 团队 | Technical Designer / Live team |
| 职责动词 | Responsibilities 每条的开头动词 | script / implement / design / collaborate |
| 必备技能 | Required / Must have 段 | scripting + direct implementation |
| 领域 | 品类 / 业务 / 产品阶段 | MMO / live environment / B2B SaaS |
| 价值观信号 | 藏在职责描述里的差异化短语 | "from concept through to release" = 端到端负责 |

## Step 3 — 跟 master-cv 交叉对照

逐条标注:
- ✅ master-cv 里**有真实证据** → 可以强调 / 提前 / 加关键词
- ⚠️ master-cv 没记**但确实做过** → **先回去补 master-cv**,再用到派生简历
- ❌ master-cv 没有**且没做过** → **不能加**(无论 JD 多想要)

## Step 4 — 简历局部调整(只改这三处)

改:
- **Summary 首句**:JD 最关心的 1–2 个关键词出现在前 10 个词
- **Skills 关键词**:加 JD 特有的词(必须有 master-cv 证据)
- **Bullet 顺序**:JD 关心的 bullet 提到每段前面

不改:工作经历事实、教育、项目事实(可以调强调,不能改事实)。

## Step 5 — 求职信

- **Para 1**:你是谁 + 投什么 + 一句最强钩子
- **Para 2**:为什么是这个岗 / 这家公司 —— 从 JD 提炼这家公司和别家的差异点,每个 claim 能追溯到 JD 原文
- **Para 3**:证据映射 —— 挑 2–3 个对 JD signal 最强的项目,不堆全部,每条明确链回一条 JD 要求

## Step 6 — 投前 verify

- [ ] Para 2 每个 claim 在 JD.md 有对应引文
- [ ] Para 3 的证据与 master-cv 一致
- [ ] Skills 新增关键词都有 master-cv 支撑
- [ ] 没有编造经验或夸大归属(solo 就是 solo,团队就标团队)
- [ ] 跑过 cv-review-rubric 五维评审
- [ ] 文件名合规

任何一项不过 → 回 Step 3。

---

## 常见坑

1. **凭印象写"我懂你们的文化"** → 要么有 JD 实证 + 真实体验,要么用通用框架不押公司文化。
2. **JD 不要的关键词仍放在显眼位置** → 让位给 JD 要的词。
3. **派生简历出现 master-cv 没有的声明** → 每句候选人面向的话都必须能在 master-cv 找到证据。
4. **把英文求职信直接翻译成中文投国内** → 必须用中文语气重写,不是翻译。
5. **JD 不存档** → 几个月后岗位下线,再也想不起当时为什么这么写。

## 投出后

立刻在 `applications.md` 加一行,状态 📝 → ✉️;同步 `SUBMIT-QUEUE.md` 打勾和 `FOCUS.md`。
