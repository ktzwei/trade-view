#!/usr/bin/env python3
"""发布前自检：证据、图片、统计及复盘判定一致性。"""
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def validate(d):
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
        if t.get("stopLoss") is None and t.get("rIncluded") and t.get("rBasis") != "doc:risk_amount":
            errs.append(f"{t['id']}: 缺 SL 却把 R 计入了统计")
        if (t.get("stopLoss") is None and t.get("actualR") is not None
                and t.get("rBasis") != "doc:risk_amount"):
            errs.append(f"{t['id']}: 缺 SL 却写出 actualR（禁止硬算 R）")
        if t.get("rBasis") == "doc:risk_amount" and not t.get("riskAmount"):
            errs.append(f"{t['id']}: 标记为按风险金额计 R，但没有 riskAmount")
        if t.get("rIncluded") and t.get("actualR") is None:
            errs.append(f"{t['id']}: 计入 R 统计却没有 actualR")
        if t.get("rIncluded") is not True and not t.get("rExcludeReason"):
            errs.append(f"{t['id']}: R 未计入统计但没有说明原因")
        if t.get("entryDate") is None and t.get("entryTime") is None and "undated" not in t["id"]:
            errs.append(f"{t['id']}: 开仓日期未知，id 必须带 undated 前缀")
        if t.get("dataCompleteness", {}).get("percent", 100) < 70:
            warns.append(f"{t['id']}: 数据完整度 {t['dataCompleteness']['percent']}%，建议补记录")

    s = d["stats"]
    if s["closed"] != s["wins"] + s["losses"] + s["be"]:
        errs.append("胜负平数量对不上")
    if s["rExcluded"] and s["netRKnownCount"] + len(s["rExcluded"]) != s["closed"]:
        errs.append("可计 R 笔数 + 未计入笔数 ≠ 全部交易笔数，请检查 SL 记录")

    ids = [t["id"] for t in d["trades"]]
    if len(ids) != len(set(ids)):
        errs.append("交易 ID 重复")
    closed = [t for t in d["trades"] if t.get("resultStatus") in ("win", "loss", "be")]
    r_trades = [t for t in closed if t.get("rIncluded") and t.get("actualR") is not None]
    net = round(sum(t["actualR"] for t in r_trades), 2)
    if s["closed"] != len(closed) or s["netRKnownCount"] != len(r_trades) or s["netR"] != net:
        errs.append("汇总统计与逐笔记录不一致")
    week_ids = [i for w in d["weeks"] for i in w["tradeIds"]]
    if sorted(week_ids) != sorted(ids):
        errs.append("周分组与交易关联不一致")
    from build import trade_haystack, find_evidences
    from review_logic import quality_value
    for t in d["trades"]:
        original = trade_haystack(t)
        for path, evidence in find_evidences(t.get("analysis") or {}):
            if evidence and evidence not in original:
                errs.append(f"{t['id']}: 引用不在原文中 {path}")
        cv = t.get("complianceV2") or {}
        if cv:
            if cv.get("yes", 0) + cv.get("no", 0) + cv.get("unknown", 0) + cv.get("notApplicable", 0) != cv.get("total"):
                errs.append(f"{t['id']}: 清单状态数量不一致")
            if cv.get("compliance") == "Fully Compliant" and (cv.get("unknown") or cv.get("no")):
                errs.append(f"{t['id']}: 存在未知或违反条件却判为完全合规")
        if t.get("rIncluded") and t not in closed:
            errs.append(f"{t['id']}: 未结束交易被计入 R")
    q = (d.get("v2") or {}).get("dashboard") or {}
    if q:
        judged = [t for t in closed if quality_value(t)]
        good = sum(quality_value(t) in ("Good Win", "Good Loss") for t in judged)
        expected = round(good / len(judged), 3) if judged else None
        if q.get("qualityJudged") != len(judged) or q.get("qualityUnknown") != len(closed) - len(judged) or q.get("goodTradeRate") != expected:
            errs.append("质量率或判定覆盖数量与逐笔记录不一致")
    def finite(obj):
        if isinstance(obj, dict):
            return all(finite(v) for v in obj.values())
        if isinstance(obj, list):
            return all(finite(v) for v in obj)
        return not isinstance(obj, float) or math.isfinite(obj)
    if not finite(d):
        errs.append("数据含有 NaN 或无穷数值")
    return errs, warns


def main():
    with open(os.path.join(ROOT, "data/trades.json"), encoding="utf-8") as source:
        d = json.load(source)
    errs, warns = validate(d)
    for warning in warns:
        print(f"[warn] {warning}")
    for error in errs:
        print(f"[FAIL] {error}")
    print(f"[selfcheck] {len(d['trades'])} 笔交易 / {len(d['weeks'])} 周 / {len(d['rules']['generated'])} 条生成规则；"
          f"Known Net R {d['stats']['netR']:+.2f}R；错误 {len(errs)}，警告 {len(warns)}")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
