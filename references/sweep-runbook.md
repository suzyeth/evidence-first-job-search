# Sweep 执行规程

> "跑一下求职" = 存活实核 + 净新增发现。本文件是每轮的操作手册和踩坑记录。

## 流程

1. `date` 校准日期;看 `applications.md` / `FOCUS.md` 修改时间,报告上轮之后有没有新投递。
2. `sweep.py live --log` 跑全队列存活。先看 `tools/logs/live-log.md`,如果定时任务今天已经跑过可省一次。
3. `sweep.py new <天数>`(窗口 = 距上轮天数)跑 LinkedIn + Indeed 净新增。
4. `boardsweep.py` 补扫雇主板(聚合站漏掉的岗主要靠这一步)。
5. 新岗逐 JD 过 5 道 Gate(见 SKILL.md),**年限数字和硬门槛优先看**。
6. 回写 `applications.md`"第 N 轮"段 + `FOCUS.md`;DEAD 的当场从 `sweep_config.json` 的 `tracked` 摘掉。
7. 清临时文件。

## 权威端点(以雇主 ATS 为准,聚合站不可信)

| ATS | 公开端点 | 注意 |
|-----|---------|------|
| Greenhouse | `boards-api.greenhouse.io/v1/boards/<board>/jobs` | 部分板只在 EU 节点:`boards-api.eu.greenhouse.io`,两个都试。board slug ≠ 品牌名很常见(如 `addepar1`) |
| Ashby | `api.ashbyhq.com/posting-api/job-board/<co>` | slug 可能带点(`mistral.ai`、`monday.com`);看 `isListed` |
| Lever | `api.lever.co/v0/postings/<co>?mode=json` | 以列表存在性为准,不信详情页 |
| Workable | `apply.workable.com/api/v1/widget/accounts/<co>?details=true` | widget 可能返回空数组,此时找 `jobs.workable.com/jobs/<uuid>` 或雇主自建站 |
| Teamtailor | `<co>.teamtailor.com/jobs/<slug>` | 在架 200,下架 410 Gone,可直接作判据 |
| Pinpoint | `<co>.pinpointhq.com/postings.json` | 内部 id ≠ 公开页 URL id |
| BambooHR | `<co>.bamboohr.com/careers/list` | |
| Workday | `POST /wday/cxs/<tenant>/<site>/jobs` | 用 req ID 搜;total=0 不一定是死,先用已知存活 ID 做对照 |
| amazon.jobs | `/en/search.json?base_query=&loc_query=&result_limit=50` | 直返资格原文 |
| Google careers | 列表/详情服务端渲染,可直接 grep | |
| 需要浏览器的 | Radware / AWS WAF 保护的站、纯客户端渲染站 | 在浏览器页面上下文里 `fetch` 同一 API 往往能通(curl 被拒时) |

抓页用 UA 伪装;JS 渲染的列表页抓不到时,换 LinkedIn 双渠道印证再判死。

## LinkedIn 的两种假阳性(机制不同,都要防)

1. **已下架的岗照样返回 200。** `jobs-guest/jobs/api/jobPosting/<id>` 对死岗也返回 HTTP 200 —— **不能只看状态码**。判死只能用 `jobs/view/<id>` 页面,grep 正文 `No longer accepting applications` + `closed-job` 组件,两个都中才坐实(`sweep.py live` 就是这么做的)。
2. **LinkedIn 独有的岗**(雇主板查无)可能 200 且连死标都没有 → 只能反查雇主 ATS;雇主板没有就不能进"可投"格。

反方向同样成立:**LinkedIn 镜像死了,雇主板上可能还活着**。镜像状态在两个方向上都不可信。

LinkedIn 换 ID 重挂很常见:旧 ID 判死后,先按标题+公司再搜一次。

## 渠道维护纪律

- **能用 `ashby_title` 就不用 `ashby_id`。** id 渠道只核存在性,抓不到"同一个 req 改题升格"(Senior → Lead 后连续多轮显示 OK 实为超线)。title 渠道精确匹配标题 + `isListed`,升格/下架都会立刻判死。
- 跟踪了 LinkedIn 镜像的岗,尽快反查真 ATS 把渠道升级掉。
- 批量往 `tracked` 加条目前先 grep 一遍,避免重复登记出现"幽灵条目"。
- **入队即入 tracked。** 漏登记的岗从来不会出现在 liveness 报告里,"队列全绿"就是假的。用 `sweep.py add <链接>` 一步完成,它会先确认岗位在架、拒绝重复登记。

## 工作许可核查(以英国为例,其他国家换成对应名册)

**在建包之前做,不是投之前做。**

**首选脚本**:`python scripts/sponsor_check.py "<公司>" [--jd JD.md]`。它自动下载当日名册,处理下面第 2 条的四种写法(连写、t/a、引号、常见词告警),查无时给出 Companies House 链接,并扫描 JD 的担保措辞。查到新的「商号 → 法人名」映射就加进 `scripts/sponsor_aliases.json`。以下是脚本背后的手工方法,脚本报 ❓ / ⚠️ 时按它人工复核。

1. 从 gov.uk "Register of licensed sponsors: workers" 页面 grep 当日 CSV 链接,下载后 grep 雇主名,看 Skilled Worker 路线。
2. **按法人名查,不是商号**:商号查不到 ≠ 不能担保。四种写法都查过才能下"零命中"结论:
   - 连写无空格(`Spotlightsportsgroup`)
   - 带 `t/a`(`XXX LIMITED t/a Brand`)
   - 名字含逗号被双引号包住 → 用全名中段片段做 contains,不要用缩写或首词
   - 商号是常见英文词(Nothing / Linear / Notion…)→ 子串 grep 被噪音淹没,必须先拿法人名
3. 仍查不到 → Companies House 公开搜索 `find-and-update.company-information.service.gov.uk/search/companies?q=` 拿英国法人名再回查;撞名多的看 officers 确认是同一家。
4. Companies House 直接 No results = 英国无实体,可判死。实体成立 < 1 年多半还没取牌,但不绝对 —— 值得首轮问一句。
5. **名册命中 ≠ 这个岗会担保。** 还要全文扫 JD 的 sponsor / right to work / authorisation。两道都过才算数。

## 节奏

- 存活检查:每周至少一次(可设定时任务;无人值守任务的命令必须与权限 allow 规则精确匹配,否则会卡在权限弹窗)。
- 净新增:LinkedIn 24h 每日,7d 每周,全来源每 3–7 天。
- 短窗口机会(hackathon / sprint / camp)每月扫一次:提前期只有 3–6 周,这条线的损失永远是错过窗口,不是被拒。
- 岗位半衰期 < 30 天,常见 4–5 天就关。干净岗发现后当周建包。

## 判定纪律

- 超线(Lead/Senior/年限数字超出)不入池,不"试试看"。
- 中介单先问后投,不裸交 CV。
- 顶级旗舰公司无内推时性价比极低,优先找内推路径。
- 执行清单 SSOT = `SUBMIT-QUEUE.md`;投递 SSOT = `applications.md`。
- 词表扩充纪律:**只加已经真实产出过岗位的词**,每条注明来源;产出为 0 的词注释保留,防止下次有人提议加回来。噪音来自 Indeed 时在展示层过滤,不删词。
