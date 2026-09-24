#!/usr/bin/env python3
"""发布前自检：JSON 可读、证据链完整、图片文件都存在。任何一项失败都不许发布。"""
import json, os, sys, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(ROOT, "data/trades.json"), encoding="utf-8"))
errs, warns = [], []

if not d.get("trades"):
    errs.append("trades 为空")

for t in d["trades"]:
    if not t.get("rawSections"):
        errs.append(f"{t['id']}: 缺少 rawSections（sourceData 原文）")
    for im in t.get("images", []):
        p = os.path.join(ROOT, im["path"])
        if not os.path.exists(p):
            errs.append(f"{t['id']}: 图片不存在 {im['path']}")
    a = t.get("analysis") or {}
    for item in a.get("riskCheck", []):
        if item["status"] in ("pass", "fail", "partial") and not item.get("evidence"):
            errs.append(f"{t['id']}: riskCheck「{item['label']}」状态为 {item['status']} 但没有原文引用")
    if t.get("stopLoss") is None and t.get("rIncluded"):
        errs.append(f"{t['id']}: 缺 SL 却把 R 计入了统计")
    if t.get("stopLoss") is None and t.get("actualR") is not None:
        errs.append(f"{t['id']}: 缺 SL 却写出 actualR（禁止硬算 R）")
    if t.get("dataCompleteness", {}).get("percent", 100) < 70:
        warns.append(f"{t['id']}: 数据完整度 {t['dataCompleteness']['percent']}%，建议补记录")

s = d["stats"]
assert s["closed"] == s["wins"] + s["losses"] + s["be"], "胜负平数量对不上"
if s["rExcluded"] and s["netRKnownCount"] + len(s["rExcluded"]) != s["closed"]:
    warns.append("可计 R 笔数 + 未计入笔数 ≠ 已结束笔数，请检查 SL 记录")

for w in warns:
    print(f"[warn] {w}")
for e in errs:
    print(f"[FAIL] {e}")
print(f"[selfcheck] {len(d['trades'])} 笔交易 / {len(d['weeks'])} 周 / {len(d['rules']['generated'])} 条生成规则；"
      f"Known Net R {s['netR']:+.2f}R；错误 {len(errs)}，警告 {len(warns)}")
sys.exit(1 if errs else 0)
