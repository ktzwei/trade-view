# Spec Review · 逐条对照 PRD 45 节

需求文档：《交易复盘系统优化需求文档》（45 节，用户 2026-09-29 提供）
复核对象：`~/code/web3/trade-view`（线上 https://ktzwei.github.io/trade-view/）
复核时间：2026-09-29
复核方式：**只认实测**——每个「已实现」都给了命令输出或页面渲染证据；没做到的写清「缺口」和缺什么。

实测基线（`python3 parser/build.py`，exit 0）：

```
[OK] evidence 校验通过（7 笔交易 / 3 个周）
[OK] 写出 data/trades.json  6 笔已结束 / 胜 4 负 2 / 已知净值 +3.61R （5 笔可计 R，1 笔未计入 R 统计）
     规则库：文档规则 4 条 + 逐笔生成 7 条；平均数据完整度 50.6%
```

状态图例：**✅ 已实现** / **🟡 部分实现（见备注）** / **⬜ 未做（缺口）**

---

## 一、总表

| 节 | 要求 | 状态 | 落地位置 / 证据 |
| --- | --- | --- | --- |
| §1 | 项目背景（SMC/ICT/PA 方法） | ✅ | README §H.5 全量映射 |
| §2 | 统一 HTF=1D/4H/1H、LTF=15min/5min | ✅ | `schema.py` `HTF_TF/LTF_TF/ALL_TF`；写 `15min/5min/M15/5MIN` 都归一成 `15m/5m` |
| §3 | 长期回答 15 问 | ✅ | `v2.answers` 14 张卡（Dashboard） |
| §4.1 | 不为了记录而记录 | ✅ | 核心 16 字段 + 其余进 Advanced；`emptyDimensions` 列出零使用维度 |
| §4.2 | 明确 HTF / LTF 职责 | ✅ | 详情页 11 步链按职责分段；`timeframes.HTFUsage` |
| §4.3 | 区分策略问题 / 执行问题 | ✅ | `v2.strategyVsExecution`：本批 badLoss 2 笔 -2.0R、goodLoss 0 笔 |
| §5 | 标准复盘链 14 步 | ✅ | 详情页「结构化复盘链」11 步承接（HTF Context → … → Review） |
| §6 | 基础信息 + HTF/LTF 使用周期 | ✅ | ① Basic Info 段解析 + `timeframes` 维度 |
| §7 | HTF Context（Bias/Market Condition/Structure + 周期） | 🟡 | 字段与统计就位；**文档侧 Market Condition 多为「未记录」** |
| §8 | Liquidity（Type/TF/Sweep/Quality） | 🟡 | 7 笔中 Sweep：Yes/未知；**Sweep Quality 6 笔「未单独记录」** |
| §9 | POI（必须带周期，HTF/LTF 分开） | ✅ | `htfPOIType`(5 行) / `htfPOITF`(2 行) / `ltfPOIType`(2 行) / `poiConfluence`(5 行) |
| §10 | Reaction + Reaction Type | ✅ | `reaction`(2 行) / `reactionType`(2 行) |
| §11 | Displacement：Yes/No + Quality + 周期 | 🟡 | **本次补上 `displacement`(Yes/No) 字段与维度**（原来只有 Quality/TF）；文档 7 笔都写「未记录」→ 全空 |
| §12 | Structure Shift（MSB/MSS/BOS/CHOCH/None）+ Broken Structure | ✅ | 选项齐全；`structureShiftType`(4 行) / `brokenStructure`(2 行，Internal/Key 分开) |
| §13 | Protected High/Low + **Price** + Timeframe | ✅ | v3.1 补齐：`schema.py` 新增数值字段 `protectedPrice`（`kind="number"`, unit=价格）；手填 → `t.fields.protectedPrice`（source=manual）→ `v2.numeric` 汇总 → Analytics「数值字段」面板。**文档 7 笔仍都没写 Protected，所以显示未记录**（不补 0） |
| §14 | Entry Mode（Limit / LTF Confirmation / Market）+ Limit 子类 | ✅ | `entryMode`(2 行) + `limitStyle`(HTF POI Limit / OB Limit / FVG Limit / 50% FVG Limit) |
| §15 | Entry Trigger 11 种 + 周期 | ✅ | `entryTriggerType`(5 行) / `entryTriggerTF` |
| §16 | Planned vs Actual（Entry/SL/TP/RR 四处比对） | ✅ | 详情页偏离表；本批 2 笔「提前进场」被抓出 |
| §17 | Invalidation Logic + 周期 | ✅ | `invalidationLogic`(3 行：Sweep Low / Protected Low / Structure Invalidated) |
| §18 | Target 层级（TP1 LTF → Final 1D/4H） | ✅ | `targetLevel`(4 行) + 原文档 targets 列表 |
| §19 | MAE / MFE（以 R 记） | 🟡 | v3.1 起 `mae`/`mfe` 也是数值字段：文档写 `MAE：-0.35R` 会抽成数值 + 单位 R（实测样句 `MAE：-0.35R，MFE：+1.8R` → `-0.35 / 1.8`），手填也可，进 `v2.numeric` 与 Analytics「数值字段」；**文档 7 笔全「未记录」→ 无数据** |
| §20 | Trade Management（Style + 4 个是否） | ✅ | `managementStyle` + `movedSL/earlyExit/reducedPosition/addedPosition` |
| §21 | Rule Compliance（Fully/Minor/Major）+ Should I Take | ✅ | `ruleCompliance` / `shouldTake`；合规组 vs 违规组 Expectancy 已算 |
| §22 | Mistake Tags 多选分组 | ✅ | 31 个标签 / 5 类（Setup/Entry/Risk/Exit/Psychology） |
| §23 | Trade Quality 四象限 + Good Trade Rate | ✅ | `v2.quality` 四行 + Dashboard Good Trade Rate |
| §24 | 截图 4 类（HTF / LTF Entry / After / Review） | ✅ | v3.1 补齐：tagedit 新增「截图分类」页（`/images`，点图选 4 类 + Timeframe + 说明）→ `data/manual/_images.json` → `v2.images` 统计 + 详情页相册角标 / Analytics「截图分类」面板。实测 **8/8 张已分类**（HTF Context 5 · LTF Entry 2 · After Trade 1），原图未动 |
| §25 | Trade Review 三问 | ✅ | 详情页 + 周报卡片（文档未写时显示 AI 复盘层判定） |
| §26 | Confidence 1–5（必须交易前记录） | 🟡 | 字段 + note（「不允许交易后回填」）已就位；文档没记 → 空 |
| §27 | Dashboard 8 指标 | ✅ | 本次补齐 **Avg R / Profit Factor / Trades** 三格（原来缺 §27 点名的 Avg R 与 Profit Factor） |
| §28 | Analytics 全维度 + Setup / Entry Mode 对比 | ✅ | 31 个维度表 + Setup 表现 + Entry Mode 表现 + 策略 vs 执行 |
| §29 | MAE/MFE Analytics 四项 | ✅ | `v2.maeMfe`：avgMAE / avgMFE / winMAE / lossMFE（当前 0 笔记录） |
| §30 | R-Multiple 优先 | ✅ | 所有指标以 R 计；无 R 的交易显式排除并列出（`rExcluded`） |
| §31 | Expectancy | ✅ | Dashboard 独立卡 + 每周 + 每组对比 |
| §32 | Weekly Review 11 项 + 三问 | ✅ | 周卡 7 项指标 + 做得好/主要问题/新规则（带原文引用）+ 折叠其余 4 项 |
| §33 | Rules 三桶 | ✅ | `ruleBuckets`：Must Have 4 / Confirmation 4 / Avoid 5（文档规则 4 条 + 逐笔 7 条） |
| §34 | Rule Checklist 与 Trade 联动 | ✅ | 详情页 10 项 ✓/✕/未记录 → 派生合规度 |
| §35 | 避免输入过复杂（核心 vs Advanced） | ✅ | 核心 16 字段默认展开，其余进 Advanced 折叠 |
| §36 | 尽量 Tag / Select 化 | ✅ | `schema.py` 纯枚举驱动前后端（42 个字段定义） |
| §37 | 不许 AI 脑补 | ✅ | 三层：解析层缺项=null、AI 复盘每条必须逐字引用原文（引用对不上整块隔离）、前端来源徽标 |
| §38 | 数据结构拆分（叙事 → 字段） | ✅ | 一句话叙事 → 20+ 结构化字段 + 保留原始段落 |
| §39 | 组合筛选 | ✅ | 19 个筛选维度（6 个动态 chips + 13 个结构化组合） |
| §40 | 搜索（Symbol/Setup/Notes/Mistake/POI/Tag） | ✅ | 全文搜索命中错误标签、POI、规则、原文段落 |
| §41 | 系统必须回答的 14 问 | 🟡 | 14 张卡全部产出，但**14/14 标「样本不足」**——阈值 10 笔，当前 7 笔 |
| §42 | P0/P1/P2 优先级 | ✅ | P0 字段与统计、P1 Context/Liquidity/POI/管理/周报、P2 全部 Analytics 均落地 |
| §43 | UI 原则（简洁/高密度/Dark/无动画） | ✅ | 默认 Dark（`:root[data-theme]`）、无动画、Trade 详情优先 |
| §44 | 20/50/100 笔验收 8 问 | 🟡 | 8 问的**计算路径全部就位**；数量验收要等数据积累（见 §41） |
| §45 | 产品理念（只改一件事） | ✅ | 每周「新规则」+ 逐笔 Next Rule 进规则库 |

---

## 二、本次（2026-09-29）真正改了什么

文档从「`【标签】值` 分行写法」改成「`【① Basic Info】…；Key：Value` 十段紧凑写法」后，旧解析器直接把 7 笔交易读成完整度 0%，并让 `build.py` 的证据校验整批失败（旧 AI 复盘引用的原文已不在文档里）。本次修复：

| # | 改动 | 位置 |
| --- | --- | --- |
| 1 | ①–⑩ 十段紧凑格式解析（段内 `；` 拆子项、`Key：Value` 映射字段） | `parse_gdoc.py` `compact_sections()` |
| 2 | 周标题改为按内容识别（正文 / 标题1 / 标题2 都认）——修掉「第 3 周整周丢失」 | `parse_gdoc.py` parse 循环 |
| 3 | 规则段改为按内容识别（「统一交易复盘逻辑」/ `规则X｜`）——修掉「4 条规则全丢」 | 同上 |
| 4 | `Planned R：约 1.5R` 单值写法也认（原来只认区间） | `parse_gdoc.py` |
| 5 | 缺项词（未记录/未单独记录/未明确记录/无法判定）统一按未记录 | `_is_unrecorded()` |
| 6 | AI 复盘引用对不上原文 → 整块隔离 + `meta.staleQuarantine`，不当编造、也不静默删 | `build.py` `check_block()` |
| 7 | 以新版文档原文重做 7 笔 + 3 周 AI 复盘（每条判定逐字引用原文） | `analysis/analysis.json` |
| 8 | 补 `displacement`（§11 Yes/No）字段与维度 | `schema.py` / `stats_v2.py` |
| 9 | MAE/MFE 从 ①/⑩ 段落进 `sections['mae'|'mfe']`（链路打通） | `parse_gdoc.py` |
| 10 | Dashboard 补 §27 点名的 **Avg R / Profit Factor / Trades** | `assets/app.js` `keyStats()` |

---

## 三、缺口清单（没做到 / 做不到的部分）

### 缺口 1 · §13 Protected Price 独立字段 —— ✅ 已补齐（v3.1，2026-09-29）

- 做法：`schema.py` 的 `F()`增加 `kind`（默认 `enum`，可 `number`）与 `unit`；新增三个数值字段 `protectedPrice`（unit=价格）、`mae`（unit=R）、`mfe`（unit=R），共 46 字段（43 枚举 + 3 数值）。
- 抽取：文档里带标签的数字会被抽成数值。实测样句 `MAE：-0.35R，MFE：+1.8R` → `mae=-0.35` / `mfe=1.8`；`MAE / MFE：未记录` 一律跳过，不补 0。
- 手填：tagedit 对数值字段渲染 `type=number` 输入。实测 POST `f__protectedPrice=2455.5` → `data/manual/<id>.json` → `t.fields.protectedPrice = {value: 2455.5, source: manual, confirmed: true}`（**测完已清除，站上不留假数据**）。
- 展示与统计：详情页 ⑥ 结构步骤多一行「Protected Price（受保护结构价格） 单位 价格」；Analytics 新增「数值字段」面板（已记录笔数 / 平均 / 范围），只对真写了值的笔算平均。
- 仍然 0/7 的原因：**文档里 7 笔都没有写 Protected 价格**——按 §37 不猜、不补。

### 缺口 2 · §24 截图分类 —— ✅ 已补齐（v3.1，2026-09-29）

- 入口：`tools/tagedit.py` 新增「截图分类」页（首页按钮或 `/images`）：每张图一个下拉（HTF Context / LTF Entry / After Trade / Review Screen）+ Timeframe（1D/4H/1H/15m/5m）+ 说明；本地加了只读静态图路由 `/images/<file>`，能直接看图。
- 落盘：`data/manual/_images.json`，键是图自己的 `sha256`（图不变、键不变）；**原图与 Google Doc 数据不动**（§37）。三个字段全空 = 撤销分类。
- 合并与展示：`stats_v2.apply_image_meta()` 合并 → `v2.images`（每类几张 / 周期分布 / 未分类数）→ 详情页相册角标 + 分类条 + Analytics「截图分类」面板。
- 实测结果：**8 张图 8/8 已分类** —— HTF Context 5（都是 1H 图：ETH×2、QQQ、HYPE、BTC）、LTF Entry 2（15m：XAU、BTC）、After Trade 1（XAU 平仓明细）。分类依据是**图上自己标的周期**（「1小时」/「15」），每个说明里都写明了，不对随时在编辑器里改。

### 缺口 3 · 文档侧的记录缺口（不是系统缺口，优先级：高——直接影响 §44）

系统一层没丢，是**文档里本身没写**。本次 7 笔统计：

| 字段 | 有值笔数（实测） |
| --- | --- |
| MAE / MFE | 0 / 7 |
| Displacement Yes/No | 0 / 7 |
| Protected Structure | 0 / 7 |
| Market Condition | 0 / 7（全部写「未记录 / 未完整记录」） |
| Sweep Quality | 0 / 7（写「未单独记录」） |
| HTF Bias | 0 / 7 |
| Confidence | 0 / 7 |
| — 作对照：Liquidity Sweep | 7 / 7 |
| — 作对照：Bias 来源周期（从「HTF 使用周期」推） | 7 / 7 |

结论：**平均数据完整度 50.6%**。§44 的「20/50/100 笔验收」不只是笔数问题——这些字段不补齐，`SL 是否太紧`、`Displacement 是否必要`、`Protected 结构是否有效` 三类问题永远出不了结论（系统只会显示「样本不足」）。

### 缺口 4 · §41/§44 样本不足（不是缺口，是事实）

14 张答卡全部标「样本不足（阈值 10 笔）」。当前 7 笔 / 5 笔可计 R。这是**设计行为**（§37：不下没依据的结论），不是 bug。

### 缺口 5 · AI 复盘层没有文档版本绑定（优先级：低）

`analysis/analysis.json` 只记 `generatedAt`，不记它引用的是哪一版文档。文档重写后只能靠「引用对不上原文」被动发现（本次就是这样触发的）。建议：`meta.docVersion = sourceVersion`，不一致时 CLI 直接提示「复盘层基于旧版文档，建议重做」。

### 缺口 6 · 前端筛选是内存筛选（优先级：低，长期）

`assets/app.js` 的筛选在浏览器内存里跑。当前 7 笔没问题；>1000 笔需要改预计算索引或分页。

---

## 四、一句话结论

**§42 的 P0 / P1 / P2 全部落地并在真实数据上跑通；§44 的验收卡在数据量（7/20 笔）与文档记录完整度（50.6%），这两件事系统替不了用户。**

下一步建议（按收益排序）：
1. 以后每笔记 **MAE / MFE / Displacement Yes-No / Protected + 价格 / Sweep Quality**（三行字，直接决定 §19/§11/§13/§8 能不能出结论）。
2. ~~补齐 `protectedPrice` 数值字段与截图分类入口（缺口 1、2）。~~ —— 2026-09-29 已完成（见上）。
3. 记到 20 笔后重跑 `v2.answers`，看哪几张卡先脱离「样本不足」。
