# 01｜JD 拆解表

用途：先确认岗位条件，再把要求转成可证明的行为。复制“空白模板”部分到私有岗位文件夹的 `jd-analysis.md`；示例只供学习。

## 空白模板

### 岗位档案

- 岗位编号 / 公司 / 标题：[填写]
- 雇主原始链接 / 获取日期：[填写]
- JD 全文存档：[填写路径]
- 国家、地点、工作方式、级别：[填写]
- 当前状态：未核实 / 在招 / 已关闭；核实日期与依据：[填写]
- 事实库路径及相关章节：[填写]
- 我为什么考虑这个岗位：[填写]

### 硬性条件核对

| 条件 | JD 原文或雇主确认 | 我的已确认情况及来源 | 结论：满足/不满足/未知 | 下一步 |
|---|---|---|---|---|
| 工作资格/担保 | [填写] | [填写；敏感信息仅留私有文件] | [填写] | [填写] |
| 地点/到岗时间 | [填写] | [填写] | [填写] | [填写] |
| 经验级别/年限 | [填写] | [填写] | [填写] | [填写] |
| 必要资格或技能 | [填写] | [填写] | [填写] | [填写] |

### 要求—证据映射

一行一个要求。R 编号只在本岗位内使用；E 编号指向事实库条目，不另建一套互相冲突的事实。

| R编号 | JD准确原文 | 类型：任务/必备/加分 | 实际需要完成什么 | E编号＋事实库定位 | A直接/B可迁移/C缺失/U待确认 | 计划用于CV条目/故事 | 缺口动作及完成标准 |
|---|---|---|---|---|---|---|---|
| R01 | [填写] | [填写] | [填写] | [填写] | [填写] | [填写] | [填写] |
| R02 | [填写] | [填写] | [填写] | [填写] | [填写] | [填写] | [填写] |
| R03 | [填写] | [填写] | [填写] | [填写] | [填写] | [填写] | [填写] |

### 决策与准备优先级

- 结论：准备申请 / 先确认条件 / 暂缓 / 不申请。
- 支持结论的要求与证据：[填写]
- 最重要的三个要求：[填写；根据职责频率、明确措辞判断，不编造权重]
- 本次CV首要证据：[填写]
- 面试重点故事：[填写]
- 要向招聘方确认的问题：[填写]
- 本轮下一步、负责人、截止日期：[填写]

完成检查：硬性条件的未知项未被当成满足；加分项未当成必备项；每条个人声明都能追溯；没有把学习计划写成已有能力。

## 完整示例｜虚构初级工具开发岗位

**全部公司、JD、候选人和数据均为教学假设，不是用户经历，不是实际招聘机会，禁止直接用于投递。**

### 岗位档案

- 岗位编号：DEMO-TOOLS-01；公司：示例游戏工作室；标题：Junior Tools Developer。
- 来源：本文件下方的虚构JD；整理日期：2026-10-23；无雇主链接。
- 地点与级别：英国、每周两天到岗、初级。
- 存活状态：教学情境，不做真实在招判断。
- 事实库：本练习的 E01—E03，见 [CV示例](02-cv-rewrite.md)；不能写入用户真实 master-cv。
- 兴趣：希望用Python和测试工具减少设计师反复检查配置的工作。

虚构JD全文：

> Build and maintain Python tools for game designers. Validate CSV configuration files and report actionable errors. Write automated tests and user documentation. Work with designers to clarify requirements. Basic Git knowledge is required. Familiarity with Unity Editor scripting is a plus. This junior role requires existing UK work authorization and two office days per week.

### 硬性条件

| 条件 | JD依据 | 教学候选人情况 | 结论 | 下一步 |
|---|---|---|---|---|
| 工作资格 | existing UK work authorization | 假设已由候选人确认有适用工作资格 | 情境内满足 | 真实投递时核对本人材料，不套用此结论 |
| 到岗 | two office days per week | 假设可通勤 | 情境内满足 | 确认具体办公室位置 |
| 级别 | junior role | 有个人项目，尚无正式工具开发任职 | 级别无明显冲突 | 不改写成职业开发经历 |
| Git | Basic Git knowledge is required | E03有分支、提交和合并记录 | A直接证据 | 准备展示一个变更 |

### 要求—证据映射

| R编号 | JD原文 | 类型 | 需要证明 | 证据 | 状态 | 对应材料 | 缺口动作 |
|---|---|---|---|---|---|---|---|
| R01 | Build and maintain Python tools for game designers. | 核心任务 | 为实际使用者做可运行工具 | E01：个人配置校验器 | A | B01、S01 | 准备可重复演示 |
| R02 | Validate CSV configuration files and report actionable errors. | 核心任务 | 检查规则并解释如何修复 | E01：行号、字段、错误原因报告 | A | B01、S01 | 演示一条错误到修复 |
| R03 | Write automated tests and user documentation. | 核心任务 | 覆盖正常和异常输入，说明使用方式 | E02：pytest与使用文档 | A | B02、S02 | 解释遗漏过的边界情况 |
| R04 | Work with designers to clarify requirements. | 核心任务 | 根据反馈改进工具 | E03：两名同学试用反馈 | B | B03、S01 | 明确是同学，不说成职业设计团队 |
| R05 | Basic Git knowledge is required. | 必备 | 能管理代码变更 | E03：Git记录 | A | Skills | 解释一次分支合并 |
| R06 | Familiarity with Unity Editor scripting is a plus. | 加分 | 理解编辑器工具扩展 | 无 | C | 缺口说明 | 两周内完成独立小练习；完成前不列为技能 |

### 决策

- 结论：情境内值得准备申请；真实申请仍需核实岗位在招和硬条件。
- 最重要要求：R01、R02、R03；JD主要工作围绕工具、配置校验和质量。
- CV优先证据：B01工具实现，B02测试，B03反馈改进。
- 面试准备：S01解决问题、S02失败与修正；专业题练习CSV校验方案。
- 招聘方问题：工具在CI还是桌面运行？主要使用者是谁？Unity知识是入职即需还是可逐步学习？
- 下一步：2026-10-24完成CV和S01卡片；2026-10-25进行模拟。日期仅是示例安排。
