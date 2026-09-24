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

### A.4 数据完整?（机器算出来的，不是感觉）
- 4 笔已结束、3 胜 1 负、**Known Net R +2.56R**（3 笔可计 R）
- 平均数据完整度：**68%**（逐笔 73% / 73% / 60% / 67%）
- 最常缺：`mae` 4 笔、`mfe` 4 笔、`fees` 4 笔、`plannedRR` 3 笔、`stopLoss` 1 笔、`actualR` 1 笔、`poi` 1 笔、`displacement` 1 笔
- **QQQ 缺 SL → 按规则不计 R**（页面显示「R 未计入」，而不是硬算一个假数）
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

```
Dashboard  #/            → 顶部统计条 + Recent Mistakes + Recent Rules + 按周的交易卡片
Weeks      #/weeks       → 全部周列表（周标题明显大于交易）
Week       #/week/第1周   → 该周统计 + Weekly Review + 本周交易卡片
Trades     #/trades      → 全部交易 + 多维筛选（结果/方向/标的/入场模型/错误/违规/Setup）
Trade      #/trade/<id>  → 单笔完整复盘（图表在第一屏，详见 D）
Analytics  #/analytics   → 累计 R、Setup 表现、Entry Model 对比、错误频次、持仓时间、完整度
Rules      #/rules       → 文档内规则 + 由交易生成的 Next Rules（每条显示 Created From）
```
切换维度：`This Week / This Month / All`（全局，作用于首页统计与列表）+ 全文搜索 + 可分享的筛选 URL（如 `#/trades?violation=Low%20RR`）。

---

## D. UI Wireframe

**Dashboard**
```
┌ Trading Review ─────── Dashboard Weeks Trades Analytics Rules ─ [This Week|Month|All] [搜索] ┐
│ 数据源：交易复盘(Google Docs) · 解析时间 · 版本哈希 · 可计 R 3 笔 / 1 笔因缺 SL 不计入            │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│ [Closed 4] [Win/Loss/BE 3/1/0] [WinRate 75%] [Net R +2.56R] [AvgR +0.85R] [HTF 1][LTF 0]  │
│ [Rule Violations 3] [Missing Data 4]                                                      │
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
5. **MAE / MFE 全缺**：无法回答「SL 是否过紧、TP 是否过早」，这是下一个最该补的记录项。
6. **Trade Management 全缺**：是否移动过止损、是否分批、是否提前出场都没有记录，所以「提前出场」这类错误只能从文字里读出来。
7. **无网页编辑**：Manual Override（§93）机制未实现，避免和 Google Docs 同步打架。
8. **Parser 是规则式的**：字段标签变化（比如把【执行】改成【进场】）会掉字段；当前靠 `_notes` 保留原文兜底，不会静默丢数据。
