# 复盘判定与每周改进行为

保留 PLAN → EXECUTION → REVIEW。交易事实、记录完整度、执行判定分别展示；自动识别只提供建议。
主要录入流程为：交易截图 → ChatGPT 识别缺项并提问 → 回答或明确跳过 → Google 文档 → 夜一解析与生成页面。
给 ChatGPT 的完整约定见 [chatgpt-recording.md](chatgpt-recording.md)，代码块内包含复盘规则、提问与写入流程，可整段复制到网页版。

## 交易前计划

选择 `Review Model`：`HTF POI` 或 `LTF Confirmation`，另记 `Confirmation Mode` 与实际 `Order Type`。
确认方式与下单方式是两个维度，允许 `LTF Confirmation + Limit`。历史 `Entry Mode` 原样保留，不自动拆分。

`Required Confirmations` 只选择该笔交易前约定的条件：Sweep、Displacement、Key Structure、Entry Trigger。
`None` 表示无需这些 LTF 条件，不能与其他选项并选。HTF POI 不默认强制 Sweep；LTF 模型未记录确认要求时，判定保持未知。
这些字段描述你的交易计划，不证明模型有效，也不替你设定最低 RR。

计划 Entry、SL、TP、RR 与实际成交记录分开。没有计划价格就显示未记录，不能用实际价格填充。
`Plan Timing` 区分 `Before Entry` 与 `Retrospective`。旧交易补录请选择后者。
编辑器会保留计划修改历史与北京时间；保存时点晚于已记录入场时点的手填计划，按事后补录展示。
只有入场日期时，保存日期晚于入场日按事后补录展示；同一天因先后不明保留未知。已成交交易缺少入场日期和时间时，也不能仅凭手填声明证明交易前计划。
文档里的计划时点属于文档声明；未记录时点时不推定为交易前计划。

## 清单与质量

清单有四种状态：符合、违反、未记录、不适用。只用文档显式字段及已确认手填值判定。
最低 RR、适用条件、交易前计划不明确时保留未知。不适用排除清单判定分母，并另列数量。
核心规则明确违反才派生 Major Violation；计划要求的确认明确未通过才派生 Minor Violation。
全部适用项均通过才能派生 Fully Compliant。已确认质量标注仍保留其来源。

Good Trade Rate = 好交易数 / 已判定质量的交易数。
同时展示已判数、未判数和判定覆盖率。未结束、保本和证据不足不套用胜负四象限。
规则合规率 = 完全合规的已结束交易数 / 已完成清单判定的已结束交易数；未知单列。

## 问题与亏损

在人工确认的错误标签中选择一个 `Primary Mistake`，`Cause Chain` 记录事情经过。
例：未到计划 POI → 提前入场 → Entry / SL 结构层级不匹配。
自动建议和分析层观察保留供回看，未经确认不进入错误统计。
每个标签行显示相关交易的亏损，同一笔可以出现在多行；合计按交易 ID 去重。
相关亏损不能解释为该错误造成的全部损失。
MAE / MFE 只描述波动；需结合交易前止损与退出规则回看，不用固定阈值直接评价执行好坏。
样本不足时不选“最佳 Setup”；达到展示阈值也只是样本内观察。

## 每周只验证一个行为

让 ChatGPT 在 Google 文档中写入专用 `【周复盘】` 段：

- 下周触发条件，例如“要求 LTF 确认的 Setup”。
- 下周动作，例如“入场前保存确认截图”。
- 检查方式，例如“有截图的次数 / 适用机会数”。

下一周先检查上周约定，填写适用机会数、完成次数和执行记录。完成次数不能超过适用次数。
零适用机会保留为零，完成率显示未记录，不当作 0% 或 100%。原来的周复盘三问仍可使用。
行为计数由人记录，不根据盈亏或错误标签反推。
标签格式见 [记录模板](record-template.md)。文档值直接进入页面，本地周表单用于可选订正并保留来源。

## 本地操作与验证

```bash
python3 tools/tagedit.py --port 8787
python3 tools/tagedit.py build
python3 tools/tagedit.py build --refresh-source
python3 -m unittest discover -s tests -p 'test_*.py'
node tests/frontend-review.test.cjs
python3 parser/build.py
python3 parser/selfcheck.py
```

保存与默认重建使用本地源数据；“同步源文档”才拉取 Google Docs。
重建成功后刷新编辑器状态，失败返回错误状态并保留已保存的手填文件。发布仍由原发布流程完成。
