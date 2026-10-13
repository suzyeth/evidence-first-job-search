# Take-home 测试打法

> 公司发来 take-home 任务时(通常在初筛之后)先冷静读这份。
> Take-home 是杠杆最高的阶段:其他环节你都在和一大批候选人比,这里是你能单独拉开差距的窗口。它也是风险最高的阶段,很多人在这里翻车。

---

## 0. 心态

| ❌ 常见误区 | ✅ 正确做法 |
|-----------|------------|
| "越长越精致越好" | **超时是减分**,说明你估时能力弱 |
| "把会的技术全展示一遍" | **回答他们问的问题**,不炫无关的东西 |
| "做不完先交半成品" | **把范围砍到能做完**:完成的小东西 > 半残的大东西 |
| "要原创、要独特视角" | **70% 展示熟练度 + 30% 独特视角**,不是反过来 |
| "等对方回复澄清问题再开工" | **48 小时没回就自己做合理假设,并写进文档**,招聘方经常忘了回 |

---

## 1. 收到任务后的第一个小时

### Step 1 — 读题 3 遍(15 分钟)
1. 第一遍:整体读,不动笔
2. 第二遍:列出**明确要交付的东西**
3. 第三遍:列出**隐性期待**(约束、质量标准、没写出来的要求)

### Step 2 — 估时(15 分钟)
- 题目写了 "spend 3–4 hours" → 你的实际预算 = 标称 × 1.0–1.5(不是 × 2)
- 写了 "as long as you need" → 自己定 6 小时上限
- 没写时间 → 发邮件问:"What's the expected time investment for this task?"

### Step 3 — 定范围(20 分钟)
写下来:
- **Must have**:题目明确要求的,100% 完成
- **Should have**:题目暗示的,争取 90%
- **Nice to have**:你自己想加的,**只在前两类做完后**才碰

### Step 4 — 发邮件澄清(10 分钟)

题目有任何模糊或矛盾的地方,马上问:

```
Hi [Name],

Thanks for the task. Two quick clarifications before I start:

1. [SPECIFIC QUESTION 1]
2. [SPECIFIC QUESTION 2]

Happy to make my own assumptions if these are intentionally
open-ended; just wanted to flag in case they're important.

Aiming to submit by [DATE].

Best,
[Your Name]
```

→ 先问(显示协作),同时表明你能自己拿主意(显示独立)。没人回就按自己的假设做,在提交里写明。

---

## 2. 常见题型

### A 类:设计题(写设计文档)
> "Design a new feature for [product]. Submit a 1–2 page doc."

**目标**:展示设计思考,不是文笔。

**结构**:
1. **TL;DR**(1 句):"I propose X for these N reasons"
2. **Problem**(1 段):解决什么用户 / 业务问题
3. **Solution**(2–3 段 + 1 张图或流程):核心机制和交互循环
4. **Why this works**(1 段):从系统 / 经济 / 情绪 / 留存角度论证
5. **Risks + mitigations**(2–3 条):**必须有**,说明你想过坏的一面
6. **Scope / cost**(1 段):粗估工程和内容工作量
7. (可选)**数据表**:如果数值平衡是核心

**避坑**:
- 不要写 9 页:他们只会细读第 1 页
- 不要解释对方早就懂的概念
- 不要"创新"到对方根本做不出来的程度
- 立足于用户行为、数据和现实约束

### B 类:数据题(给数据做分析)
> "Here's a dataset of user retention. What insights do you draw?"

**目标**:展示数据素养 + 业务叙事。

**结构**:
1. **TL;DR**(3–5 句):最重要的 1–2 个发现
2. **Methodology**(1 段):用了什么指标 / 分群 / 假设
3. **Findings**:每条 1 段 + 1 张图,按重要性排序
4. **Recommendations**:2–3 条可执行建议
5. **With more time**:说明你知道分析的局限

**工具**:表格软件够应付大多数情况;题目鼓励且你简历写了 Python,可以用 notebook(给链接,不要整段粘贴)。避免用对方可能打不开的 BI 工具。

**避坑**:不要把数据全倒出来(他们要看的是你挑出了什么);2–3 张有洞见的图胜过 50 张;每个发现都要跟一句"所以呢":X 发生了,因此该做 Y。

### C 类:平衡题(给一个现有系统,找问题提修改)
> "Here's an existing economy. Identify problems and propose fixes."

**目标**:展示系统思维 + 数值直觉。

**结构**:
1. **TL;DR**:发现了 N 个问题,主要修改是 X
2. **Issues**:每个 1 段 + 1 个数值例子,按对用户的影响排序
3. **Fixes**:每个修改对应一个问题,附**改前 / 改后对照表**
4. **Side effects**:**必须有**,每个修改可能破坏什么
5. **Validation**:怎么验证修改有效(A/B 测试 / 模拟 / playtest)

**避坑**:不要"全都修",挑影响最大的 2–3 个;题目常故意留明显问题当陷阱,看你能不能找到更深的那个;改前改后的数字要自洽,加减乘除验算一遍。

### D 类:评审题(评价一个现有设计)
> "Critique this feature. What works, what doesn't?"

**目标**:展示品味 + 沟通能力,语气最重要。

**结构**:
1. **What works**(1 段,真诚地找优点)
2. **What doesn't**(2–3 个具体问题,按重要性排)
3. **Alternative**(1 段):你会怎么重做
4. **Open questions**(1 段):你缺数据判断不了的部分

**避坑**:不要全盘否定(看题的人可能就是原设计者的同事);不用绝对化措辞,把 "This is wrong" 换成 "I'd consider whether X might be better";每条批评都配一个替代方案。

### E 类:编程题
> "Implement [feature] in [language]. Submit code + README."

**目标**:展示代码质量 + 自我管理 + 沟通。

- README 包含:运行步骤、**设计决策**、取舍、"what I'd do with more time"
- 代码模块化,至少有一个测试文件(说明你懂测试文化)
- 注释少而准

**避坑**:不要过度工程化;不要零测试;README 要让评审 5 分钟内跑起来。

---

## 3. 时间管理

### 时间分配(以 6 小时为例)
```
第 0–1 小时:读题 + 定范围 + 发澄清邮件 + 列计划
第 1–4 小时:主体工作(60–70%)
第 4–5 小时:打磨图表、写完文档 / README
第 5–6 小时:自查 + 减重(删掉弱内容 > 加新内容)
```

### 到点了怎么办

| 用掉的时间 vs 完成度 | 动作 |
|------|--------|
| 时间到,完成 80% | 继续打磨到 100%,**不扩范围** |
| 时间到,完成 60% | **停止加东西**,把已有的打磨完整再交,注明 "scoped to focus on X" |
| 时间到,完成 30% | 发邮件申请延期 1–2 天(说明具体原因),**或者**直接砍掉一半范围 |

### 红线:永远不超过标称时间的 2 倍
对方会问 "how long did this take?",照实回答远超标称会减分。

---

## 4. 提交前 30 分钟检查

- [ ] 顶部有 **TL;DR / Summary**,对方只读这一段就决定要不要细看
- [ ] 拼写语法检查过一遍
- [ ] 数字自洽(改前改后验算过)
- [ ] **假设写清楚**:"I assumed X because Y — let me know if this is wrong"
- [ ] 有 **What I'd do with more time** 一节
- [ ] 文件名带姓名 + 公司 + 岗位:`First_Last_Company_Role_TakeHome.pdf`
- [ ] 编程题的 README 5 分钟能跑通
- [ ] 文档交 PDF,不交 .docx(防格式错乱)

---

## 5. 提交邮件

```
Subject: Take-home submission — [Role] — [Your Name]

Hi [Name],

Attached / linked is my submission for the [Role] take-home.

A few notes:
- Time invested: ~[N] hours
- One assumption I made: [SPECIFIC ASSUMPTION]
- One thing I'd extend with more time: [SPECIFIC EXTENSION]

Happy to walk through any design decisions or trade-offs in a follow-up call.

Best,
[Your Name]
```

→ 报时间(估时准、守范围),报假设(有自知),报"还能怎么扩展"(知道边界)。

---

## 6. 提交后的等待

- **7 天内不跟进**,对方在内部评审
- 7 天没回 → [follow-up-emails.md](follow-up-emails.md) 模板 1
- 14 天没回 → 模板 2
- 被拒 → 模板 5,并礼貌请求反馈。拿到的可能是具体反馈,也可能是套话,都有用

---

## 7. 针对具体公司做准备

每家公司的题型和看重点不同。拿到题后,在 `interview-prep/companies/<company>.md` 记下:
- **预期题型**(参照上面 A–E):从 JD、Glassdoor 面经、对方工程 / 设计博客推断
- **对方最看重什么**:比如这个产品的社区对改动的接受度、商业模式、技术栈
- **你的可迁移优势**:你过去哪段经历最能对上
- **诚实声明**:如果你对对方的产品不熟,**直接说明**,比如 "relatively new to [product]; this design is based on [N] hours of play plus general system principles"。假装是老玩家,面试一追问就会穿帮;诚实反而加分

---

## 8. 永远不做的 5 件事

1. **抄网上的设计或代码**:一搜就能搜到,直接拒,还伤名声
2. **找人代做**:面试一问细节就答不上来
3. **超时 2 倍以上**
4. **没有 README / TL;DR 就交**:对方 30 秒决定要不要细看
5. **刚交完就问 "when will you decide"**:显得焦虑

---

## 9. 为什么值得投入

| 阶段 | 你能在多大程度上影响结果 |
|------|------|
| 简历初筛 | 小(ATS + 几十秒扫读) |
| 电话初筛 | 中(招聘官主导) |
| **Take-home** | **大**(几天的独立工作,全由你展示) |
| 终面 | 中(多人面 + 行为面,主观) |

→ 准备好一次 take-home,往往比多改几版简历更有用。

没收到 take-home 也正常,有些公司直接进入用人经理面试,那就把精力放在面试准备上。

---

## TL;DR(收到题后先读这里)

1. 读题 3 遍,分清 must / should / nice
2. 发邮件澄清 + 自己做合理假设
3. 时间预算 = 标称 × 1.0–1.5,绝不超过 2 倍
4. 顶部必须有 TL;DR
5. 交之前删弱内容,不加新内容
6. 提交邮件报时间 / 假设 / 可扩展点
7. 不抄、不找人代做、不超时、不交 docx、不焦虑追问
