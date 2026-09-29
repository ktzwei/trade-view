# 交易复盘系统 · Trading Review System

> SMC Trading Review System —— 不是「把 Google Docs 转成网页」，而是以《交易复盘》为 Source of Truth 的
> **Personal Trading Operating System**：`Context → Liquidity → Structure → POI → Entry Reason → Entry Trigger → Invalidation → Target → Risk → Execution → Result → Review → Rule`

线上地址：**https://ktzwei.github.io/trade-view/**
数据源：Google Docs《交易复盘》（doc id `16gYSHlO1vvtG8lGN8UGj2v-8K3cLcXS3uli6nIHy-dU`）

---

## A. 对当前 Google Docs 的理解

### A.1 文档结构（三层，已保留）
```
Title   交易复盘
H1      第1周｜2026年9月13日–9月19日            ← Week
H2      1｜ETH/USDT Long｜+2.30R               ← Trade
正文    【市场背景 Context】【Setup】【入场原因】【入场模型】【交易时间】
        【执行】【Invalidation】【Target Logic】【结果】【Risk Check】
        【做得好的】【需要改进】【主要问题】【下次规则】【结构理解】
        + 内嵌图片（每笔 1 张，共 4 张）
H1      第2周｜2026年9月20日–9月26日
H1      SMC 执行规则（规则一～规则五 + 固定复盘模板 10 项）
```
Week 层级在页面里明显大于 Trade（H1 23px / Trade 16px + 独立卡片刻意区分）。

### A.2 现有交易字段（Parser 实际提取到的）
| 字段 | 来源 | 4 笔中有几笔记录 |
|---|---|---|
| Entry / SL / Exit / Target | 【执行】 | Entry 4/4、SL 3/4、Exit 2/4、Target 2/4 |
| 计划 R / 实际 R | 【结果】【Risk Check】 | 计划 2/4、实际 3/4 |
| 入场模型 | 【入场模型】 | 2/4（XAU 未写，QQQ 写了计划 vs 实际） |
| Setup 流程 | 【Setup】 | 4/4 |
| 入场原因 / 触发 | 【入场原因】【入场模型】 | 4/4 |
| Invalidation（逻辑） | 【Invalidation】 | 2/4 |
| Target Logic | 【Target Logic】 | 3/4 |
| 时间（进出场） | 【交易时间】 | 4/4 |
| 复盘（好/问题/下次规则） | 【做得好的】【需要改进】【主要问题】【下次规则】 | 4/4 |
| MAE / MFE / Fees / PnL | — | 0/4 |
| POI / Displacement 独立字段 | — | 2/4（其余写在叙述里） |

### A.3 现有 SMC 逻辑（文档已写的五条规则，网页原样收录）
1. **先看流动性**：标出高周期 SSL / BSL；Sweep 只启动观察，不能单独触发入场。
2. **再看位移和结构**：Sweep 后需有明确 displacement 与 MSS/BOS；弱 MSB 等后续 BOS 或低周期确认；internal MSB 只说明内部结构转强。
3. **只在计划 POI 执行**：discount/premium 中找 OB、BB、IMB 重叠区；HTF 限价单放在 POI 内，价格未到不抢入。
4. **止损与目标成对**：SL 放在能否定逻辑的结构点并记录准确价格；TP 对应对侧流动性或 IMB；下单前算计划盈亏比，未达最低要求则跳过。
5. **复盘执行偏差**：分别记录 HTF 限价与 HTF+低周期确认；逐笔填计划/实际 Entry、SL、TP、R 与提前出场原因；缺少 SL 的交易不统计 R。

### A.4 数据完整度（机器算出来的，不是感觉）
- 6 笔已结束、4 胜 2 负、**Known Net R +3.61R**（5 笔可计 R，1 笔因缺 SL 排除）
- 平均数据完整度：**61%**（逐笔 73% / 73% / 60% / 67% / 40% / 53%）
- 最常缺：`mae`、`mfe`、`fees`（6 笔 0 记录）、`plannedRR` 4 笔、`stopLoss` 2 笔、`poi` 3 笔、`displacement` 3 笔
- 新增两笔（2026-09-28 解析时的文档状态）：`XAU/USDT Short`（开仓时间未记录、只有风险金额 0.4 = 1R → 文档写明 +2.05R）、`HYPE/USDT Long`（无【交易时间】行，开仓日取自标题 → -1R）
- **QQQ 缺 SL → 按规则不计 R**（页面显示「R 未计入」，而不是硬算一个假数）
- **未成交的挂单不算交易**：文档里写了 `【状态】Pending / 未成交` 的 BTC 挂单不进胜负与 R 统计，只在周列表里显示「未成交 / 未结束」。
- 千分位价格必须按原值解析（`82,953.7` 曾被正则读成 `82.0` —— 已修，价格一律去掉逗号再转数字；这是数据真实性硬要求）
- XAU 那笔：Entry / SL / Target / 计划 RR 齐全（0.74–0.78），却违反规则四 → 说明问题不在「没记」，在「记了也照做」

---

## B. Data Schema

### B.1 三层数据，物理隔离
```
data/source.json     ← sourceData：Parser 从 Google Docs 机械提取，一字不改
analysis/analysis.json ← analysis：AI 复盘归类（Error Type / Rule Violation / Risk Check 判定），每条结论必须带原文引用
data/trades.json     ← 合并结果（网页唯一数据源），每笔交易里 source 与 analysis 两个块分开存放
```

### B.2 缺失值规则（硬约束）
- 文档没写 → `null`，前端渲染 `— 未记录`，**绝不填 0、绝不从图片猜 SL、绝不硬算 R**。
- Parser 里所有「计算值」（如风险点数 = |Entry − SL|）只有两个输入都存在时才算，并标 `derived: true`。
- QQQ 的 `actualR` 就是 `null` + `rIncluded:false` + `rExcludeReason`，这是页面里最诚实的一行。

### B.3 证据校验（防 AI 编造）
`analysis/analysis.json` 里每个 `pass / fail / partial` 判定都必须提供 `evidence`：
```
"rrMeetsRequirement": { "status": "fail", "evidence": "计划 RR 约 0.74–0.78，不符合高质量交易的收益风险结构" }
```
`parser/build.py` 会校验这段引用**逐字存在于该笔交易原文**，对不上直接构建失败并打印违规条目。
`status: "unknown"` 表示文档没写，不允许为了把表格填满而编造。

### B.4 完整 Trade Schema（实际字段）
```jsonc
{
  "id": "2026-09-21-xauusdt-long-01",       // 稳定 ID：日期-标的-方向-序号（不用标题当主键）
  "weekLabel": "第2周", "week": {"year","isoWeek","start","end"},
  "symbolLabel": "XAU/USDT", "direction": "long",
  "entryTime": "...+08:00", "exitTime": "...+08:00", "holdingMinutes": 1167,

  // ---- sourceData（原文提取，null = 未记录）----
  "entry": 4352.77, "stopLoss": 4305.20, "exit": null,
  "targets": [{"label":"Target","price":"4388–4390","type":["BSL","External Liquidity"],"sizePercent":null}],
  "plannedRR": 0.76, "plannedRRLow": 0.74, "plannedRRHigh": 0.78,   // 区间取中值仅用于统计，页面同时显示区间
  "actualR": -1, "rIncluded": true, "resultStatus": "loss",
  "context": {"timeframe":"15m","trend":null}, "liquidity": {...}, "structure": {...},
  "displacement": {"type":null,"strength":null}, "poi": [],
  "setup": {"flow": ["SSL Sweep","Internal Bullish MSB","Liquidity-to-Liquidity"]},
  "entryReason": {"raw": "...", "items": ["SSL 被扫","出现 bullish reaction", ...]},
  "entryModel": {"planned":null,"actual":null,"category":"UNKNOWN","label":"未记录"},
  "entryTrigger": {"text": "...", "modelLabel": "未记录"},
  "invalidation": {"logic":"较大的结构失效位","price":4305.20},
  "targetLogic": {...}, "tradeManagement": {...},
  "review": {"worked":[], "improve":null, "mainProblem":[], "nextRules":["..."]},
  "images": [{"path":"images/2026-09-21-xauusdt-long-01-1.png","type":"analysis","timeframe":null}],
  "mae": null, "mfe": null, "pnl": null, "fees": null,
  "rawSections": {"context":"原文…","execution":"原文…"},   // 逐字原文，页面可展开对照

  // ---- analysis（AI 层，逐条带 evidence 引用）----
  "analysis": {
    "riskCheck": [{"key":"rrMeetsRequirement","label":"RR Meets Requirement","status":"fail","evidence":"…"}],
    "compliance": {"pass":6,"fail":2,"partial":0,"unknown":2,"rate":0.75},
    "errorType": {"primary":"Risk Management Error","secondary":["Execution Error"],"evidence":"…"},
    "classification": {"value":"Bad Loss","reason":"…","evidence":"…"},
    "ruleViolations": [{"tag":"Low RR","evidence":"RR 在下单前已经不合格"}],
    "mistakes": [{"tag":"Entry / SL 结构级别不匹配","evidence":"…"}]
  }
}
```
`stats` / `weeks` / `rules` / `analytics` 结构见 `data/trades.json` 文件头。

---

## C. Information Architecture

**v2 简化原则（用户反馈「内容繁琐，弄简单些，目的是好复盘、能进步」）**：一屏只回答三个问题 —— 这笔为什么做 / 结果怎样 / 下次怎么改。原始字段一个不丢，但全部折叠进「原始记录」，默认不出现。

```
Dashboard  #/            → 4 个关键数字 + 最该盯的重复错误 + 最近长出来的规则 + 按周：周复盘三行 + 一笔一行
Weeks      #/weeks       → 同上（周维度）
Week       #/week/第1周  → 该周三行复盘 + 一笔一行 + 折叠的周复盘其他条目
Trades     #/trades      → 一笔一行 + 筛选
Trade      #/trade/<id>  → ① 头部三价格 + 大图 ② 复盘三问（做对了/问题/下次）③ 原始记录（折叠）
Analytics  #/analytics   → 累计 R、Setup 表现、最常犯错、缺记录热点（统计用，可不下钻）
Rules      #/rules       → 文档规则 + 从交易里长出来的规则（按类别分组，每条挂来源）
```

单笔页三层（复盘优先，避免信息平铺）：
1. **这是什么交易**：品种 / 方向 / 开平时间（缺就写「未记录」）/ Entry · SL · Exit · 计划 TP · Planned RR · Actual R + 大图（图表仍是第一优先级）。
2. **复盘三问**：① 做对了什么 ② 问题在哪（含 AI 归类错因 + 规则卡点）③ 下次怎么做（文档里写了的就照抄，没写就明说这格空着）。
3. **原始记录（折叠）**：文档逐字段原文 + Liquidity/Displacement/POI + 下单前风控自查 + Google Docs 原文对照。

切换维度：`This Week / This Month / All`（全局，作用于首页统计与列表）+ 全文搜索 + 可分享的筛选 URL（如 `#/trades?violation=Low%20RR`）。

---

## D. UI Wireframe

**Dashboard**
```
┌ Trading Review ─────── Dashboard Weeks Trades Analytics Rules ─ [This Week|Month|All] [搜索] ┐
│ 数据源：交易复盘(Google Docs) · 解析时间 · 版本哈希 · 可计 R 3 笔 / 1 笔因缺 SL 不计入            │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│ [Known Net R +3.61R · 5 笔可计 R] [Win/Loss 4/2 · 67%] [规则违反 7] [待补记录 6]              │
├─ Recent Mistakes ──────────────────┬─ Recent Rules ──────────────────────────────────────┤
│ 条形：Missing Protected Low 2 笔    │ 规则文本 + 来源：QQQ/USDT 2026-09-15                 │
├─ Weeks ───────────────────────────┴────────────────────────────────────────────────────────┤
│ 第1周  2026-09-13 – 09-19 · ISO Week 37      Trades 3 Wins 3 Loss 0 Known Net R +3.56R      │
│ ┌ 周总结原文 ─────────────────────────────────────────────────────────────────────────────┐ │
│ │ Main Strength / Main Problem / Repeated Mistake / Main Lesson / New Rule / Best-Worst │ │
│ └────────────────────────────────────────────────────────────────────────────────────────┘ │
│ ┌ Trade 卡片 ────────────────────────────────┬ 图缩略 ────────────────────────────────┐  │
│ │ ETH/USDT LONG ●Win ●Good Win  09-13→09-15  │ [chart thumb]                          │  │
│ │ Entry 2483.71 | SL 2434.00 | Exit 2598.26  │ 数据完整度 73% ▓▓▓▓▓▓▓░░░              │  │
│ │ Planned RR — | Actual +2.30R | HTF Limit   │ 缺：plannedRR、mae、mfe、fees          │  │
│ │ SSL Sweep → Bullish Displacement → …       │                                        │  │
│ │ 入场原因一句话 + 标签                        │                                        │  │
│ └────────────────────────────────────────────┴────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

**Trade Detail（图表第一优先级，桌面 60/40 双栏）**
```
← 全部周
┌ ETH/USDT LONG ●Win ●Good Win  2026-09-13 17:24 → 2026-09-15 04:22        +2.30R ┐
│ Entry 2483.71 · SL 2434.00 · Exit 2598.26 · Planned RR 未记录 · HTF Limit        │
└──────────────────────────────────────────────────────────────────────────────────┘
┌ 左：图表(60%) ─────────────────────┬ 右：信息(40%) ────────────────────────────────┐
│  [Main Chart 大图，点击 Lightbox]   │ Market Context / Liquidity / Structure /      │
│  Lightbox：全屏 · 缩放 · ←→ · 触屏  │ Displacement / POI / Entry Reason /           │
│  Gallery 缩略图切换                 │ Entry Trigger / Invalidation /                │
│                                    │ Pre-Trade Risk Check（✅❌ 未知 + 原文引用）    │
└────────────────────────────────────┴───────────────────────────────────────────────┘
Setup Flow（竖向流程图）· Target Logic 表 · Trade Management · Result · What Worked /
What Went Wrong / Next Rule · AI 复盘分析（Error Type / 分类 / Rule Violations，全带引用）
· Tags · ▸ 查看 Google Docs 原文（sourceData 逐字段对照）
```

**Mobile**：全部单列，主图在最上，缩略图横滑，图片点开即全屏并可双指缩放。

---

## E. MVP Plan

**已实现（PRD §87 的 22 项，逐条对应）**：Docs 结构化 ✅ / Week 页 ✅ / Trade Card ✅ / 图片 Gallery+Lightbox ✅ /
Context ✅ / Liquidity ✅ / Structure ✅ / POI ✅ / Setup Flow ✅ / Entry Reason ✅ / Entry Trigger ✅ /
Invalidation ✅ / Target Logic ✅ / Risk Check ✅ / Result ✅ / What Worked ✅ / What Went Wrong ✅ /
Next Rule ✅ / Tags ✅ / Filter ✅ / Responsive ✅ / JSON 数据层 ✅
外加：全文搜索、Analytics 初版、Rules 页（含 Created From 溯源）、数据完整度、Good/Bad 分类、原文对照。

**暂不实现（按 §88 与「不过早做重后端」）**：登录 / 多用户 / 实时行情 / 下单 / 交易所 API / 权限 / 社交 /
AI 聊天窗口；也暂不做自动同步与网页编辑（§93 Edit Trade 需等 Manual Override 机制设计完再上）。

---

## F. Implementation Plan

**Tech Stack**：`HTML + CSS + 原生 JS（零依赖、零构建）` + `Python 3（Parser）` + `静态 JSON`，部署 GitHub Pages。
> PRD §72 建议 Next.js / Vite；这个项目选零构建静态站的理由：① §76 明确「MVP 先 Static Data / JSON / GitHub 即可」；
> ② §77 要求「可以部署为 GitHub Pages」，静态站直接满足，不需要 CI、不做构建即可维护；
> ③ 数据量小、纯展示+筛选，没有 SSR/路由需求。**将来若要上 Analytics 高级图或 Edit Trade，可以平滑迁到 Vite/React**——数据层已经是纯 JSON，前端可替换。

**目录结构**
```
trade-view/
├── index.html                  # SPA 外壳（顶部导航 / 搜索 / 期间切换）
├── assets/app.css app.js       # Notion/Linear 风格样式 + 全部视图逻辑（hash 路由）
├── data/source.json            # Parser 输出（sourceData）
├── data/trades.json            # 合并后的唯一前端数据源
├── analysis/analysis.json      # AI 分析层（每条判定带原文引用）
├── parser/parse_gdoc.py        # Google Docs → structured trades（含图片绑定）
├── parser/build.py             # 证据校验 + 统计口径 + 合并输出
├── cache/doc.docx              # 文档快照（不进 git；文档改没改看 meta.sourceVersion 内容哈希）
├── images/<tradeId>-N.png      # 图片按交易一一绑定命名
└── publish.sh                  # 一键发布到 ktzwei.github.io/trade-view/
```

**Data Flow**
```
Google Docs ──(export?format=docx)──► cache/doc.docx ──► parse_gdoc.py
   ├─ 按 document.xml 顺序切块：H1=Week、H2=Trade、【=字段、drawing=图片
   ├─ 图片按「文档顺序」绑定到当前 Trade（注意：不能用 media 文件名，Google 每次导出会重命名！）
   └─► data/source.json（纯事实，缺失一律 null）
analysis/analysis.json ──(evidence 逐条校验)──► build.py ──► data/trades.json ──► 前端
```

**Google Docs Parser**
- 标题映射：H1=Week（`第N周｜起始–结束`）、H2=Trade（`序号｜标的 方向｜结果`），正文 `【字段】` 归位；H1「SMC 执行规则」→ rules。
- 图片绑定：按 XML 顺序，Trade 标题之后的图片归该笔；归属无法判定 → 标 `unresolved`，不猜（§53）。
- 不确定即空：不认识的字段进 `_notes` 原文保留，不硬塞进 schema。
- 同步（§54）：当前手动跑 `./publish.sh`（解析 → 校验 → 自检 → push）；`meta.sourceVersion` 是**正文内容哈希**（段落文本 + 每张图 sha256）—— Google 每次导出的 docx 字节都不同（9c46… 和 5f19… 是同一份文档），所以不能用字节哈希判断「文档改没改」。

**Deployment**：`./publish.sh` → 推送到 `ktzwei/trade-view` 仓库（GitHub Pages 已开启，main 分支根目录），线上 `https://ktzwei.github.io/trade-view/`；`ktzwei.github.io` 首页的「项目导航」已加入口卡片。
（PRD §77 写的仓库是 `zzjanuary/trade-view`：现有凭据对它是只读，推不上去；代码与仓库名无关，随时可整目录搬过去。）

---

## G. 已知限制 / 差距清单（诚实版）

1. **只有 4 笔样本**：Analytics 的 Win Rate / Avg R 目前只是趋势，不构成结论；HTF Limit vs LTF Confirmation 的对比现在无意义（各 1 / 0 笔）。
2. **URL 用 hash 路由**（`#/trade/2026-09-21-xauusdt-long-01`）：可分享、可收藏，但不是 §69 想要的 `/trades/...` 干净路径。纯静态站点要干净路径需要 Vite/Next 或 404 重写。
3. **图片分辨率**：保存原图（2048px 宽），未压缩，4 张共 844KB（单张 187–228KB）—— 换来放大看细节不糊。
4. **XAU 缺【入场模型】【POI】【Displacement】** → 该笔无法参与入场模型对比统计，页面显示「未记录」。
5. **MAE / MFE 全缺（解析器已支持，等文档补值）**：文档 ⑩ 已要求记录 MAE/MFE，解析器现在认 `【MAE】`/`【MFE】`/`【最大浮亏】`/`【最大浮盈】`（支持 `-0.35R` 或价格两种写法），并新增 `【手续费】`、`【风险金额】`、`【保护低点】`/`【保护高点】`、`【计划 RR】`。补值模板见 `docs/record-template.md`。**未补之前页面显示「未记录」，不代算。**
6. **Trade Management 部分缺**：止损移动 / 分批 / 提前出场目前只能从文字里读；HYPE 那笔的「上移 SL」已能被识别。
7. **无网页编辑**：Manual Override（§93）机制未实现，避免和 Google Docs 同步打架。
8. **Parser 是规则式的**：字段标签变化会掉字段；已做三层兜底：`_extra` 保留未识别原文、`rawSections` 全量留档、规则段按内容识别（"SMC 执行规则" 是正文段落也能抓到）。
9. **Google 偶尔连不上**：`publish.sh` 拉取失败时自动回落到 `cache/doc.docx` 离线解析（数据为上次成功拉取的版本），不再整个发布会卡死。

---

## H. v3 · 结构化复盘层（2026-09-29 新增）

需求文档《交易复盘系统优化需求文档》(45 节) 的落地版本。核心一句话：**字段带来源标记、缺项显示「未记录」、系统不猜。**

### H.1 四层数据，来源可追溯

| 层 | 存在哪 | 来源标记 | 是否会覆盖原始文档 |
| --- | --- | --- | --- |
| 文档原文段落 | `data/source.json` → `rawSections` | — | — |
| 文档里的 `【标签】` 字段行 | `trades[].fields` | `doc:label` | 原文照抄 |
| 逐句自动识别（§37 的「建议」） | `trades[].fields` | `doc:keyword` | **不改原文，只加建议** |
| 手填确认 | `data/manual/<tradeId>.json` | `manual` | 优先级最高 |
| 机器派生（合规度 / Planned vs Actual 偏离 / Quality） | `trades[]` | `derived` | 派生值单独放，不动原值 |

页面上每种来源都有徽标：**文档记录** / **自动识别·待确认** / **手填·已确认** / **派生**。
`tools/tagedit.py` 里每个自动识别值旁边有「确认这个值」——人工确认后来源变成 `manual`，可追溯。

### H.2 新增文件

| 文件 | 作用 |
| --- | --- |
| `parser/schema.py` | 枚举唯一真源：5 个周期、12 组字段、错误标签分组、规则三桶 |
| `parser/rules.py` | 逐句识别规则（含否定处理、区块范围限定，避免「没等 Sweep」被读成 Sweep=Yes） |
| `parser/struct_extract.py` | 抽取引擎：字段行 + 逐句识别 + 证据留痕 |
| `parser/stats_v2.py` | 统计层：来源合并 → 单笔派生 → 28 个维度聚合 → 周报 → §41 十二问自动作答 |
| `tools/tagedit.py` | 本地手填编辑器（默认 8791），写 `data/manual/`，含周复盘三问表单 |
| `docs/record-template.md` | 可复制到 Google Docs 的记录模板（含「少一行少哪种统计」对照表） |

### H.3 前端新增（`assets/app.js` / `app.css` / `index.html`）

- **单笔详情**：11 步结构化复盘链（每个字段带来源徽标 + 原文证据）、Rule Checklist（✓/✕/未记录）、Planned vs Actual 偏离表、MAE / MFE 判读卡、Advanced 折叠（核心字段之外的其余字段）。
- **Dashboard**：Expectancy / Good Trade Rate / Rule Compliance / Avg MAE·MFE 第二排指标；**「系统要回答的问题」14 张问答卡**（样本不足时明确写「暂不下结论」并给依据）。
- **Analytics**：结构形态 / 入场方式 / LTF 周期 / HTF POI 周期 / 市场环境 / Sweep / Displacement / 被破坏结构 / 合规度 / Trade Quality / 错误标签（按类聚合 + 损失 R）/ 策略问题 vs 执行问题 / 周期使用 / 其余全部维度表 / **未记录维度清单**。
- **Rules**：Must Have / Confirmation / Avoid 三桶，每桶列出每笔的 ✓ / ✕ / 未记录计数。
- **Weeks**：Expectancy / Good Trade Rate / 合规率 / Avg MAE·MFE / 最佳 Setup / 最大错误 / 错误损失 R + 三问（做得好 / 主要问题 / 下周重点）。
- **Trades**：13 组结构化组合筛选（入场方式、HTF/LTF POI 周期、市场环境、Sweep、Displacement、结构变化、被破坏结构、Protected、Target 层级、合规度、该不该做、Trade Quality、错误标签）。
- **默认 Dark Mode**（§43）：`:root[data-theme]` 变量 + 顶栏切换按钮，选择记在 localStorage。

### H.4 新增命令

```bash
python3 parser/parse_gdoc.py      # 拉文档 → data/source.json
python3 parser/build.py           # 统计 + v2 层 → data/trades.json（含 v2.*）
python3 parser/selfcheck.py       # 证据校验
python3 tools/tagedit.py --port 8791   # 本机手填/确认（浏览器打开 127.0.0.1:8791）
./publish.sh                      # 上面的流程 + push 到 GitHub Pages
```

### H.5 需求映射（45 节 → 实现位置）

| 需求 | 落地位置 |
| --- | --- |
| §2 HTF 1D/4H/1H、LTF 15m/5m 统一 | `schema.py`（`HTF_TF`/`LTF_TF`/`ALL_TF`）→ 前后端全部按此校验与展示 |
| §5 标准复盘链 | 详情页 11 步链，顺序按文档 |
| §6 基础信息 + HTF/LTF 周期 | 详情页头部 + `timeframes` 统计 |
| §7 HTF Context | 链①步 + `marketCondition` 维度 |
| §8 Liquidity | 链②步 + Sweep Yes/No/Partial 对比 |
| §9 POI（HTF POI 与 LTF Entry POI 分开） | 链③步 + `htfPOITF` / `ltfPOITF` 两个维度 |
| §10–11 Reaction / Displacement | 链④⑤步 + 质量维度 |
| §12 Structure（Internal vs Key） | 链⑥步 + `brokenStructure` 维度（Internal LH/HL vs Key LH/HL 分开统计） |
| §13 Protected High/Low | `protectedStructure` / `protectedTF` 字段 + 维度 |
| §14 Entry Mode（Limit / LTF Confirmation / Market） | 链⑦步 + Entry Mode 对比（Trades / Win Rate / Avg R / Expectancy） |
| §15 Entry Trigger | `entryTriggerType` + `entryTriggerTF` |
| §16 Planned vs Actual | 详情页偏离表（价格、时间、RR、R 四处比对） |
| §17 Invalidation | 链⑥步 + `invalidationLogic` / TF |
| §18 Target 层级 | `targetLevel` + 原文档 targets 列表 |
| §19–20 MAE / MFE + 管理 | 判读卡（SL 太紧 / 提前止盈）+ `managementStyle` |
| §21 Rule Compliance | 每笔派生值 + 全局合规率 + 合规组 vs 违规组 Expectancy |
| §22 Mistake Tags | 31 个标签分 5 类（Setup / Entry / Risk / Exit / Psychology）+ 自动建议（标记「未确认」） |
| §23 Trade Quality | Good Win / Good Loss / Bad Win / Bad Loss 四象限 + Good Trade Rate |
| §24 截图 | 每笔 1–4 张原图（HTF/LTF/After/Review 归属待手工标注） |
| §25 Trade Review 三问 | 详情页 + 周报三问 |
| §26 Confidence | 字段（提示必须交易前记） |
| §27 Dashboard 指标 | 首页 8 项：Trades / Win Rate / Net R / Avg R / Expectancy / Profit Factor / Rule Compliance Rate / Good Trade Rate |
| §28 Analytics 全维度 | 28 个维度表 + 错误分析 + 策略 vs 执行 |
| §29 MAE/MFE Analytics | Avg MAE / Avg MFE / 盈利单 MAE / 亏损单 MFE |
| §30–31 R 优先 + Expectancy | 所有指标以 R 计；Expectancy 独立成卡 |
| §32 Weekly Review | 周卡新增 7 项指标 + 三问 |
| §33–34 Rules 三桶 + Checklist 联动 | Rules 页三桶 + 每笔 Checklist 派生合规度 |
| §35 避免字段过多 | 默认 16 个核心字段 + 其余进 Advanced 折叠 |
| §36 Tag/Select 化 | 全部枚举字段结构化（`schema.py` 是唯一真源） |
| §37 不许 AI 脑补 | 双保险：解析层证据校验 + 前端「未记录 / 自动识别·待确认」徽标；建议永不覆盖原值 |
| §38 数据结构拆分 | 一句话叙事 → 拆成 20+ 结构化字段 + 保留原始 Notes |
| §39–40 Filter / 搜索 | 13 组组合筛选 + 全文搜索（含错误标签、POI、Tag） |
| §41 系统必须回答的 12 问 | Dashboard「系统要回答的问题」卡 + `v2.answers` |
| §42 开发优先级 | P0/P1/P2 全部完成（见 §H.3 / §H.5） |
| §43 UI 原则 | 暗色默认、高密度、无动画、Trade 详情优先 |
| §44 验收标准 | 每张答卡带样本量与「样本不足」提示（当前 7 笔，阈值 10 笔） |
| §45 产品理念 | 每笔 -> 复盘 -> 统计 -> 找问题 -> 只改一件事 |

### H.6 已知限制（诚实版）

1. **样本极小**（7 笔，其中可计 R 的 5 笔）：所有对比维度都标了「样本不足」，系统**不给结论**。§44 的 20/50/100 笔验收要等数据。
2. **`tradeQuality` 全部显示「派生」**：文档里没写这个字段——目前由合规度 + 结果推导，页面标了来源，等你手填覆盖。
3. **`mistakes` 字段几乎空**，错误分析主要来自 `analysis/analysis.json` 的 AI 复盘（页面标「自动识别·待确认」）。
4. **Market Condition / Bias 来源周期 / Protected 结构 / MAE / MFE 目前全空**：字段和统计都已就位，等文档补值或手填。
5. **"Setup" 仍是自由文本**：`setup.flow` 拆步骤做了标签，但没有独立的 Setup 枚举字段——跨交易的 Setup 对比目前用「结构形态 × 入场方式」组合代替。
6. **周复盘三问**写在 `data/manual/_weeks.json`（手填）或文档正文里；文档正文里的写法还没做解析。
7. Markdown 里 `app.js` 的筛选是前端内存筛选，数据量大（>1000 笔）时需要改预计算索引。
