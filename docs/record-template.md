# 交易记录模板 · 可直接复制到 Google Docs

这份模板就是解析器（`parser/parse_gdoc.py`）能完整读懂的写法。
**照抄下面的骨架，把值填进去就行；格式错了不会报错，只会变成「未记录」——不会猜、不会补。**

三条硬规则（需求 §4.1 / §37）：

1. **标签必须写成 `【标签】值`**（全角方括号 + 同一行写值）。标签名可以是中文或英文，只要包含下面表里的关键词就认得（大小写、空格都无所谓）。
2. **没记录就留空或整行不写**。页面显示「未记录」；系统绝不会因为「上下文看起来像」就替你判 Yes。
3. **R 值以文档写的为准**。系统只做加总与期望值，不自己推算你的盈亏。

---

## 0. 文档骨架（复制这段开始写）

```
第 3 周｜9月28日 – 10月4日

周总结：本周 X 笔，X 胜 X 负，净值 +X.XXR

1｜HYPE/USDT Long｜2026年9月28日–9月29日｜+2.05R

【交易时间】2026-09-28 09:10 → 2026-09-29 02:35
【市场背景 Context】4H 处于上升结构，1H 回踩至 4H OB，日线下方有 SSL 未取。
【计划入场方式】HTF Limit
【入场模型】原计划 HTF Limit；实际执行市价
【执行】计划 POI 约 42.15；实际 Entry 42.38；初始 SL 41.10；Exit 45.60；Target 45.8；总止损风险 128 = 1R
【Setup】HTF POI 到达 → 15m SSL Sweep → 5m Bullish Displacement → 结构变化 → First Retracement
【入场原因】价格进入 4H OB 并扫掉下方 SSL，5m 出现强势 bullish displacement 并突破内部 LH。
【结构理解】5m 突破的是 Internal LH，不代表主趋势反转。
【Invalidation】止损放在被扫的 SSL 低点下方，若跌破该低点则结构失效。
【Target logic】TP1 内部流动性；TP2 上方 BSL；Final 4H swing high。
【Risk check】风险 1.28 点；目标空间约 3.6–4.2 点；计划 RR 约 2.8–3.3
【结果】原计划约 1.5R，实际约 +2.05R
【MAE】-0.35R
【MFE】+3.8R
【手续费】0.86
【保护低点】41.10
【交易管理】分批止盈 50%，SL 上移至 BE
【做得好的】等到了 POI 和 Sweep 才动手，没有提前进。
【需要改进】分批止盈太早，剩下半仓被 BE 扫掉。
【主要问题】提前止盈。
【下次规则】首目标只出 1/3，剩余仓位跟到 HTF 流动性。

【HTF Bias】Bullish
【Bias 来源周期】4H
【Market Condition】Trending
【HTF Structure｜周期】Bullish Structure｜4H
【流动性类型】SSL
【流动性周期】1H
【流动性被扫】Yes
【Sweep 质量】Strong
【Sweep 周期】15min
【HTF POI｜周期】OB｜4H
【LTF Entry POI｜周期】FVG｜5min
【POI Confluence】4H OB + 1H FVG + Discount
【Reaction】Strong
【Reaction 类型】Sweep
【Reaction 周期】15min
【Displacement】Yes
【Displacement 质量】Strong
【Displacement 周期】5min
【结构变化】MSS
【结构变化周期】5min
【被破坏的结构】Key LH
【Protected 结构】Protected Low
【Protected 结构周期】1H
【Entry Mode】LTF Confirmation
【Limit 方式】50% FVG Limit
【Entry Trigger｜周期】Sweep + Displacement｜15min；MSB｜5min
【Invalidation 依据】Sweep Low
【Invalidation 周期】5min
【Target 层级】TP1 LTF Internal Liquidity；TP2 1H Liquidity；Final 4H Swing High
【Management Style】Partial TP
【Trade Quality】Good Win
【Rule Compliance】Fully Compliant
【Should I Take This Trade】Yes
【Trade Management】移动过 SL；提前止盈
【Confidence】4
【Mistake Tags】Move SL to BE Too Early
```

> 图片直接插在这笔交易下面即可（顺序就是文档里的顺序，会自动绑到这笔交易）。
> 交易标题必须用 `序号｜SYMBOL/方向｜日期区间｜结果R`，用全角竖线 `｜` 分隔。

---

## 1. 周级（每周写一次）

| 写法 | 作用 |
| --- | --- |
| `第 3 周｜9月28日 – 10月4日` | 周标题（一级标题）。**必须**以「第 N 周」开头，解析器靠它分周 |
| 紧跟的正文第一段 | 周总结原文（页面上显示为「周总结」） |
| `This Week I Did Well` / `Main Problem` / `Next Week Focus` | 三问。写进文档里即可，或在本机用 `python3 tools/tagedit.py` 的周复盘表单填（写到 `data/manual/_weeks.json`） |

---

## 2. 交易级基础字段（§6）

| 标签 | 说明 |
| --- | --- |
| `【交易时间】` | `2026-09-28 09:10 → 2026-09-29 02:35`。只记到平仓时间也可以（写「开仓时间未记录」时不会拿平仓时间冒充开仓） |
| `【市场背景 Context】` | HTF 语境原文 |
| `【Setup】` | 用 `→` 串起流程，前端会拆成步骤标签做统计 |
| `【入场原因】` | 原文照抄 |
| `【入场模型】` | 例：`原计划 HTF Limit；实际执行市价`（解析器能拆出 planned/actual） |
| `【执行】` | 价格都在这里：`实际 Entry` / `初始 SL` / `Exit` / `Target` / `TP1（50%）` / `总止损风险 128 = 1R` |
| `【结构理解】` | 结构说明原文 |
| `【Invalidation】` | 失效条件原文 |
| `【Target logic】` | 目标逻辑原文（含 `IMB` `BSL` `内部流动性` 等词会被识别成目标类型） |
| `【Risk check】` | `风险 1.28 点` / `目标空间约 3.6–4.2 点` / `计划 RR 约 2.8–3.3` |
| `【结果】` | `实际约 +2.05R`；`原计划约 1.5R，实际约 +1.26R` 会取「实际」 |
| `【MAE】` / `【MFE】` / `【最大浮亏】` / `【最大浮盈】` | 支持 `-0.35R`（推荐）或价格 |
| `【手续费】` / `【Fees】` | 数字 |
| `【风险金额】` | `128` |
| `【计划 RR】` | 文字形式也行 |
| `【保护低点】` / `【保护高点】` | 价格或结构描述 |
| `【交易管理】` / `【Trade Management】` | `移动过 SL` / `提前止盈` / `减仓` / `加仓` 会被识别成开关 |
| `【做得好的】` / `【需要改进】` / `【主要问题】` / `【下次规则】` | 复盘四问；`【下次规则】` 会自动进「规则库」，页面显示它来自哪一笔 |

---

## 3. 结构化字段（§7–§26，决定 Analytics 能不能算）

这些是**标签行**，写多少算多少。写了的进统计，没写的显示「未记录」，不进统计。

### HTF Context（§7）
`【HTF Bias】Bullish | Bearish | Neutral` · `【Bias 来源周期】1D | 4H | 1H` ·
`【Market Condition】Trending | Range | Expansion | Compression | Reversal | Unclear` ·
`【HTF Structure】Bullish Structure | Bearish Structure | Range | Transition` + `【HTF Structure 周期】1D | 4H | 1H`

### Liquidity（§8）
`【流动性类型】BSL | SSL | Internal Liquidity | External Liquidity | Equal High | Equal Low | Previous High | Previous Low | Swing High | Swing Low` ·
`【流动性周期】1D | 4H | 1H | 15min | 5min` ·
`【流动性被扫】Yes | No | Partial` · `【Sweep 质量】Strong | Normal | Weak` · `【Sweep 周期】…`

### POI（§9）
`【HTF POI】OB | FVG | IMB | Breaker | Mitigation Block | Premium | Discount | OTE | Supply | Demand | …` + `【HTF POI 周期】1D | 4H | 1H` ·
`【LTF Entry POI】…` + `【LTF Entry POI 周期】15min | 5min` ·
`【POI Confluence】4H OB + 1H FVG + Discount`（多个用 `+` 连接）
> HTF POI 和 LTF Entry POI 是两个字段，分开写。

### LTF 反应（§10 / §11）
`【Reaction】Strong | Weak | No Reaction` · `【Reaction 类型】Rejection | Sweep | Momentum Shift | Candle Reversal | Consolidation | Immediate Displacement` · `【Reaction 周期】15min | 5min` ·
`【Displacement】Yes | No` · `【Displacement 质量】Strong | Medium | Weak` · `【Displacement 周期】15min | 5min`

### 结构（§12 / §13）
`【结构变化】MSB | MSS | BOS | CHOCH | None` · `【结构变化周期】15min | 5min | 1H | 4H | 1D` ·
`【被破坏的结构】Internal LH | Internal HL | Key LH | Key HL | Protected High | Protected Low | External Structure` ·
`【Protected 结构】Protected High | Protected Low | None` · `【Protected 结构周期】1D | 4H | 1H | 15min | 5min`

### Entry（§14 / §15）
`【Entry Mode】Limit | LTF Confirmation | Market` · `【计划入场方式】…` ·
`【Limit 方式】HTF POI Limit | OB Limit | FVG Limit | 50% FVG Limit` ·
`【Entry Trigger】POI Touch | Sweep | MSB | MSS | BOS | Displacement | FVG Retest | OB Retest | Breaker Retest | Rejection | First Retracement` + `【Entry Trigger 周期】15min | 5min`

### Invalidation / Target / 管理（§17–§20）
`【Invalidation 依据】Sweep Low | Protected Low | Protected High | OB Invalidated | Structure Invalidated | HTF Bias Invalidated` + `【Invalidation 周期】…` ·
`【Target 层级】TP1 内部流动性；TP2 1H 流动性；Final 4H Swing High` ·
`【Management Style】Set and Forget | Manual | Partial TP | Move SL to BE | Trailing Stop` ·
`【Trade Management】移动过 SL / 提前止盈 / 减仓 / 加仓`

### 复盘判定（§21–§26）
`【Rule Compliance】Fully Compliant | Minor Violation | Major Violation` ·
`【Should I Take This Trade】Yes | No | Borderline` ·
`【Trade Quality】Good Win | Good Loss | Bad Win | Bad Loss` ·
`【Mistake Tags】Front Run, Early Entry, Weak MSB, Internal MSB Only, SL Too Tight, Early Exit, FOMO`（多个用 `,` 或 `、` 分隔）·
`【Confidence】1–5`（**必须交易前记，事后不许回填**）

---

## 4. 规则段（§33）

一级标题写 `SMC 执行规则`（或 `交易规则` / `规则库`），然后：

```
规则一｜Risk 优先：单笔风险不超过 1R
规则二｜HTF 优先：没有明确 HTF POI 不进场
① 交易前：明确 HTF Bias / POI / Invalidation / RR
② 触发：Sweep → Displacement → 结构变化 → First Retracement
③ 避免：FOMO、Mid Range Entry、Weak MSB、Poor RR
```

- `规则N｜标题：正文` 会进规则库，页面上标注来源 `doc:rules`。
- `①②③` 开头的行进入「固定复盘模板」。

---

## 5. 常见写法对照

| 会掉字段的写法 | 正确写法 |
| --- | --- |
| `HTF Bias：Bullish`（没有方括号） | `【HTF Bias】Bullish` |
| `【HTF Bias】看多`（不在枚举里） | `【HTF Bias】Bullish`（不在枚举的值会被保留在原文里，但不会进统计） |
| `【Sweep】有` | `【流动性被扫】Yes` |
| `1. HYPE/USDT Long`（用 `.` 和半角） | `1｜HYPE/USDT Long｜2026年9月28日–9月29日｜+2.05R` |
| 把 MFE 写进备注里 | 单独一行 `【MFE】+3.8R` |

---

## 6. 改完文档之后

```bash
cd ~/code/web3/trade-view
python3 parser/parse_gdoc.py     # 拉取并解析 Google Docs
python3 parser/build.py          # 重算统计并写出 data/trades.json
./publish.sh                     # 发布到 GitHub Pages
```

手填/订正（不改原始文档，写在本机 `data/manual/`）：

```bash
python3 tools/tagedit.py --port 8791    # 浏览器打开 http://127.0.0.1:8791
```

- 手填值优先级最高、来源标记恒为 `manual`，页面上和「文档记录 / 自动识别·待确认 / 派生」区分显示。
- 手填的三个问题（备选答案之后）：每条字段旁有「确认这个值」，等于把自动识别的建议**人工确认**成正式值。---

## 7. 为什么这几行不能省（少一行就少一种统计）

| 行 | 为什么必须记 | 少了会怎样 |
| --- | --- | --- |
| 交易时间 | 算持仓时长、对齐时区、判断是否在允许窗口内 | 页面只能显示「开仓未记录」，时段分析全废 |
| 执行 Entry/SL/Exit | 算 R、算实际盈亏、算 MAE/MFE 基准 | 缺 SL → **本笔不进 R 统计** |
| 计划 RR | 判断是否满足「未达最低 RR 就跳过」 | 无法证明规则四有没有守 |
| 风险金额（=1R） | 只有金额没 SL 时，唯一能把结果换算成 R 的依据 | 只能记「+2.05R」这种文字 |
| MAE | 止损是不是放太紧？有没有被噪音打掉？ | 无法回答「止损位置」这类问题 |
| MFE | 有没有过早出场、利润回吐多少 | 无法回答「出场时机」 |
| 手续费 | 高频小 R 交易的真实净值 | 净 R 虚高 |
| 保护低/高点 | 移动止损是否有结构依据（对应规则） | 「SL 只按结构条件移动」这条规则无法核验 |

一句话：**只有 SL 和风险金额齐全，这笔才进 R 统计**；MAE / MFE 只记实际观测值，不推算、不估算。

## 8. 回溯已有交易（建议顺序）

1. `2026-09-15-qqqusdt-long-03`（QQQ）：只缺 SL → 补上就多一笔可计 R。
2. `undated-xauusdt-short-02`（XAU Short）：只有风险金额 0.4 → 补 SL 价格或补【MAE】。
3. `2026-09-28-hypeusdt-long-01`（HYPE）：补【MAE】就能判断「上移 SL 是否太早」。
4. 其余 3 笔（ETH ×2、XAU Long）：补【MAE】【MFE】即可把完整度推到 80%+。
