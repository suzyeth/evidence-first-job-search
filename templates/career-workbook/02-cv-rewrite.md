# 02｜CV 改写表

复制空白部分到私有岗位文件夹的 `cv-rewrite.md`。真实事实仍以现有 `master-cv-data.md` 为准；改写表只是映射，不替代事实库。

## 空白模板

- 公司/岗位/版本/日期：[填写]
- JD及拆解表：[填写]
- 输入CV / 目标CV：[填写]
- 事实库路径：[填写；已有 shared/master-cv-data.md 时直接引用]

### 证据盘点

| E编号 | 事实库章节/条目 | 真实角色和时间 | 我做的具体动作 | 工具与方法 | 结果/证据文件 | 允许公开的范围 | 确认状态 |
|---|---|---|---|---|---|---|---|
| E01 | [填写] | [填写] | [填写] | [填写] | [填写] | [填写] | 已确认/待确认 |

### 逐条改写

结构：动作＋对象或问题＋方法＋结果或用途。没有业绩数字时，可以写清交付物、覆盖范围和使用场景。

| B编号 | 原文 | 对应R编号 | 依据E编号 | 改写中文 | 改写英文（需要时） | 修改理由 | 可能追问 |
|---|---|---|---|---|---|---|---|
| B01 | [填写] | [填写] | [填写] | [填写] | [填写] | [填写] | [填写] |

### 数字与归属核对

| 声明 | 基线/分母/时间段 | 测量方式及记录 | 个人与团队贡献边界 | 可以声称什么 | 不能声称什么 |
|---|---|---|---|---|---|
| [填写；没有数字也检查归属] | [填写] | [填写] | [填写] | [填写] | [填写] |

### 最终排版内容

- Summary：[填写；目标方向不能冒充当前职位]
- Skills：[填写；只列有证据的技能，学习中单独标注]
- Experience/Projects标题与日期：[填写；个人项目不要混成任职]
- Bullet顺序及最终文本：[填写]
- 删去或降级的内容及原因：[填写]
- 尚待确认的事实：[填写；不得进入可投递版本]

### 出口检查

- [ ] 每条B均能回溯R和E；E在真实事实库中已确认。
- [ ] 任职标题、日期、工具熟练程度、数字和责任范围未升级。
- [ ] 协助未改为主导；试用未改为上线；个人项目未改为商业项目。
- [ ] 英文与中文保持同一责任范围；没有保密数据。
- [ ] 对每条CV能解释“为什么、怎么做、哪里出错、结果如何核实”。
- [ ] 定稿通过既有fact_check与五维评审；模板和虚构示例不作为真实简历送检。

## 完整示例｜同一工具开发案例

**教学虚构，所有事实和文件名只在示例中成立。不是用户CV，也未通过用户事实库校验。**

- 目标：DEMO-TOOLS-01 Junior Tools Developer。
- 输入：一段过于笼统的个人项目描述；输出：英文Projects段。
- 教学事实记录（不能导入真实master-cv）：

| E编号 | 示例事实定位 | 角色/时间 | 具体动作 | 结果与佐证 | 公开边界 |
|---|---|---|---|---|---|
| E01 | 本节/E01 | 个人项目开发者；2026-08至2026-09 | 用Python检查CSV必填字段、重复ID、跨表引用；输出行号/字段/原因 | 示例项目有24份合成配置表；demo-report.html为演示产物 | 可展示合成数据；不声称生产部署 |
| E02 | 本节/E02 | 同一项目 | 编写18个pytest用例及快速开始文档；后补空表测试 | tests目录、README及本地运行记录；18包含修复后用例 | 不声称覆盖率百分比或零缺陷 |
| E03 | 本节/E03 | 同一项目 | 请两名同学试用；根据反馈给错误报告添加定位信息；用Git管理变更 | feedback.md与提交记录 | 不说成带领设计师团队或正式客户 |

### 改写前后

| B编号 | 原文 | JD关联/证据 | 改写中文 | 改写英文 | 理由与追问 |
|---|---|---|---|---|---|
| B01 | 做过Python游戏工具，提高工作效率 | R01/R02；E01 | 开发Python配置校验器，检查24份合成CSV表的必填字段、重复ID和跨表引用，并生成包含行号与错误原因的报告 | Built a Python validator for 24 synthetic CSV configuration files, checking required fields, duplicate IDs and cross-table references and reporting row-level errors. | 用可演示交付替代无证据效率承诺；追问跨表引用怎么查 |
| B02 | 负责测试保证质量 | R03；E02 | 编写18个pytest用例覆盖正常输入及异常配置，并整理安装、运行和故障排查说明 | Wrote 18 pytest tests for valid and invalid configurations and documented setup, usage and troubleshooting. | 不用“保证”暗示无缺陷；追问遗漏过哪种情况 |
| B03 | 与团队协作优化体验 | R04；E03 | 邀请两名同学试用，根据反馈为报告补充字段定位和修复提示 | Gathered feedback from two peer testers and added field locations and remediation hints to error reports. | 明确同学试用，未夸大为职业协作；追问反馈如何取舍 |

### 数字与归属

| 声明 | 基线/口径 | 证据 | 贡献边界 | 可声称 | 不可声称 |
|---|---|---|---|---|---|
| 24份表 | 示例数据目录内24份合成CSV；无生产规模含义 | 文件清单 | 本人实现校验器 | 测试对象规模 | 公司全量数据 |
| 18个测试 | 修复空表问题后的测试用例数量 | 本地测试输出 | 本人编写 | 已有测试数量 | 100%覆盖、绝不出错 |
| 两名试用者 | 两名同学的一次反馈轮次 | 反馈笔记 | 反馈来自同学、修改由本人做 | 基于试用改进 | 商业采用、节省多少人力 |

### 最终英文项目段

**Summary**：Early-career developer with Python project experience in configuration validation, automated testing and user documentation, seeking a junior tools development role.

**Skills**：Python, CSV validation, pytest, Git. Unity Editor scripting is not listed because it is not yet evidenced.

**CSV Configuration Validator — Personal Project | Aug–Sep 2026**

- Built a Python validator for 24 synthetic CSV configuration files, checking required fields, duplicate IDs and cross-table references and reporting row-level errors.
- Wrote 18 pytest tests for valid and invalid configurations and documented setup, usage and troubleshooting.
- Gathered feedback from two peer testers and added field locations and remediation hints to error reports.

删除：无依据的效率百分比、团队领导、生产部署描述。待确认项：本教学情境无；真实使用必须全部换成用户已确认事实。状态：教学完成，禁止作为真实申请文件。
