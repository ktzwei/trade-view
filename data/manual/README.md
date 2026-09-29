# data/manual —— 手填结构化层

需求 §37：自动识别（`doc:keyword`）只出「建议」，永远不改原始文档数据。
凡是「确认过的结构化值」都写在这里，优先级最高，来源永远标记 `manual`，可追溯。

## 文件格式

`data/manual/<tradeId>.json`

```json
{
  "tradeId": "2026-09-13-ethusdt-long-01",
  "updatedAt": "2026-09-29T17:04:03+0800",
  "fields": {
    "htfBias": "Bullish",
    "brokenStructure": ["Key LH"],
    "ruleCompliance": "Fully Compliant"
  },
  "notes": "4H→1H POI 明确，5min 破坏 Key LH 后入场。"
}
```

* 单值字段写字符串，多选字段（`multi: true`）写数组，数字字段写数字。
* 值必须来自 `parser/schema.py` 的词表，否则 build 会把它当成写作错误。
* `fields` 里把某个键设成 `null` = 显式清掉这条自动识别结果（留痕在 Git 历史里）。

## 三种方式写它

1. **本地编辑界面（推荐）**
   ```bash
   cd ~/code/web3/trade-view && python3 tools/tagedit.py
   # → http://127.0.0.1:8787  保存后自动重建站点数据
   ```
2. **命令行**
   ```bash
   python3 tools/tagedit.py set 2026-09-13-ethusdt-long-01 ruleCompliance="Fully Compliant" htfBias=Bullish
   ```
3. **直接写 JSON**（例如批量补历史交易）。

## 字段来源标记一览

| source | 含义 | 可信度 |
|---|---|---|
| `manual` | 手填 / 已确认（本目录） | 高，统计以此为准 |
| `doc:label` | 文档里的 `【字段】值` 标签行 | 高（作者自己写的） |
| `doc:keyword` | 从正文逐句自动识别 | **建议**，需确认 |
| `derived:checklist` | 从规则清单结果派生 | **建议**，需确认 |

前端界面一律显示来源；`未记录` 表示文档里真的没写，不会用 0 或猜测补（需求 §37）。
