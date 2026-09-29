# 交易记录模板 · 可直接复制到 Google Docs

这份模板就是解析器（`parser/parse_gdoc.py`）能完整读懂的写法。
**照抄下面的骨架，把值填进去就行；格式错了不会报错，只会变成「未记录」——不会猜、不会补。**

三条硬规则（需求 §4.1 / §37）：

1. **标签必须写成 `【标签】值`**（全角方括号 + 同一行写值）。标签名可以是中文或英文，只要包含下面表里的关键词就认得（大小写、空格都无所谓）。
2. **没记录就留空或整行不写**。页面显示「未记录」；系统绝不会因为「上下文看起来像」就替你判 Yes。
3. **R 值以文档写的为准**。系统只做加总与期望值，不自己推算你的盈亏。

---

## 0. 文档骨架（复制这段开始写 · 现行 ①–⑩ 格式）

> 这是文档现在的写法，解析器会把它拆成 30 个统计维度。**每行一个 `【①…】` 段，段内用「；」分隔子项，子项写成「Key：Value」。**

```
第 3 周｜2026年9月27日–10月3日

周总结：1 笔已结束交易，0 胜 1 负，合计 -1R；另有 1 笔挂单未成交，不计入结果统计。

1｜HYPE/USDT Long｜2026年9月28日–9月29日｜-1.00R
【① Basic Info】2026-09-28 09:10 → 2026-09-29 02:35（北京时间）；HYPE/USDT；Long；Exchange：OKX；Entry Mode：HTF Limit；HTF 使用周期：1H；LTF 使用周期：15min；Entry 88.30；SL 88.32；Exit 86.90；Actual R：-1.00R。
【② HTF Context】1D Bias：Bullish；4H Bias：Bullish；1H：价格回撤至 1H IMB；Market Condition：Trending；Major Structure：Bullish Structure。
【③ HTF Liquidity & POI】Liquidity：1H SSL；Timeframe：1H；Sweep：Yes；Sweep Quality：Normal；HTF POI：1H IMB + OB；POI Confluence：IMB + OB + Discount。
【④ LTF Reaction】15min Reaction：Weak；Reaction Type：Rejection。
【⑤ LTF Confirmation】Sweep：Yes；Displacement：Yes / Strong / 15min；Structure Shift：Bullish MSB → BOS；Broken Structure：Internal LH。
【⑥ Entry】Setup Flow：HTF POI → 15min Sweep → Displacement → MSB → 回踩；Entry Reason：流动性事件 + 1H POI；Entry Trigger：回踩 OB/IMB。
【⑦ Invalidation & SL】什么发生就证明我错了：跌破 Protected Low；SL 88.32。
【⑧ Target & Risk Check】Target：上方 BSL；TP1 92.10；Planned RR：约 2.5R；Actual R：-1.00R；Risk Check：Entry 偏离计划 POI（No）；追价（No）。
【⑨ Trade Management】分批止盈 50%；SL 上移至 87.9；原因为结构推动。
【⑩ Result & Review】Loss，Actual R -1.00R；做得好的：等到了 Sweep；Trade Quality：Good Loss。
【Rule Violation / 改进】Rule Violation：无（符合全部规则）；改进：SL 空间可再收窄一档。
【Next Rule】首目标只出 1/3，剩余仓位跟到 HTF Target。

2｜BTC/USDT Long（挂单）｜未成交
【① Basic Info】2026-09-28 08:00 计划；BTC/USDT；Long；Exchange：OKX；Entry Mode：HTF Limit；HTF 使用周期：4H；LTF 使用周期：15min；Planned Entry 约 82,953.7；SL 约 82,348.7；Planned RR 约 3.26R；Result：Pending。
【② HTF Context】1D / 4H：未记录；1H：价格位于 Dealing Range Discount 区，存在 1H IMB，当前大周期倾向做多。
【③ HTF Liquidity & POI】下方 Liquidity 已被 Sweep；HTF POI：1H IMB + Discount；HTF Target 类型：未明确标注。
...
（③ 之后同上面那一笔的 ④–⑩ 结构，缺什么就写「未记录」）

统一交易复盘逻辑｜后续所有交易沿用

规则一｜先做 HTF Context：固定按 1D → 4H → 1H 分析 Bias、Market Condition、Major Structure、Liquidity、POI、Premium/Discount 与 HTF Target。
规则二｜再做 LTF Confirmation：固定按 15min → 5min 观察 Reaction、Sweep、Displacement、MSB/MSS/BOS、Broken Structure 与 Entry。
规则三｜POI 必须分层记录：HTF POI 与 LTF Entry POI 分开，POI 必须带 Timeframe。
规则四｜Entry、Invalidation、Target 必须成对：下单前记录 Planned Entry、SL、TP 与 Planned RR，RR 不符合标准就跳过。
规则五｜复盘必须区分「策略问题」和「执行问题」：盈利也可能是 Bad Win，亏损也可能是 Good Loss。缺少可靠数据时标记未记录，不反推、不补写。
```

### 0.1 解析器认得哪些写法

| 位置 | 写法 | 说明 |
| --- | --- | --- |
| 周标题 | `第 3 周｜2026年9月27日–10月3日` 单独一行 | 正文 / 标题1 / 标题2 都认，不靠样式 |
| 周总结 | 以 `周总结：` 开头 | 数字会被总账核对 |
| 交易标题 | `<序号>｜<SYMBOL> <Long/Short>｜<日期区间>｜<±R>` | 名称以 `-挂单` 结尾视为未成交 |
| 交易字段 | `【① Basic Info】…；Key：Value；…` | ①–⑩ 十段全覆盖（旧写法 `【标签】值` 也仍然认） |
| 规则段 | 标题含「统一交易复盘逻辑」或 `规则X｜…` | 逐条进 Rules 页三桶 |
| 缺失 | 写 `未记录` / `未单独记录` / 无法判定 | 一律当未记录，不猜、不补 |

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
