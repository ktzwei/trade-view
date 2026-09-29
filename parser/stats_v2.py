#!/usr/bin/env python3
"""统计层 v2 —— 落实需求 §7–§35 / §42（P0–P2）。

设计原则（需求 §37 / §4.1）：
  * 只统计「文档里真实写了的」，没写的显示「未记录」，绝不用 0 或猜测补；
  * 每个字段都带来源（doc:label / doc:keyword=自动识别 / manual=手填 / derived=派生），
    自动识别值一律标记 confirmed=false，前端必须显示成「自动识别·待确认」；
  * 所有比率类指标同时给出样本数，样本不足 5 笔时标 lowSample，避免误读。

输出结构见 build_result() 的 keys；由 build.py 调用并写进 data/trades.json 的 "v2"。
"""
import json
import re
from pathlib import Path

MANUAL_DIR = Path(__file__).resolve().parent.parent / "data" / "manual"

# ---------------------------------------------------------------- 小工具
def fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 2) if xs else None


def rate(a, b):
    return round(a / b, 3) if b else None


def r2(v, n=2):
    return None if v is None else round(v, n)


def is_closed(t):
    return t.get("resultStatus") in ("win", "loss", "be")


def r_included(t):
    return bool(t.get("rIncluded")) and t.get("actualR") is not None


def sample_flag(r_counted, min_n=5):
    return "样本不足" if (r_counted or 0) < min_n else None


# ---------------------------------------------------------------- 手填层
def load_manual():
    """data/manual/*.json：{ "<tradeId>": {"fields": {...}, "notes": "...", "mistakes": [...]}, "_meta": {...} }"""
    manual = {}
    if not MANUAL_DIR.exists():
        return manual
    for p in sorted(MANUAL_DIR.glob("*.json")):
        try:
            manual[p.stem] = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:  # 手填文件写坏了不能拖垮整条管线
            print(f"[WARN] 手填层读取失败 {p.name}: {e}")
    return manual


def merge_fields(t, manual_entry):
    """文档标签层 + 自动识别层 + 手填层 → 最终字段表（手填优先级最高）。"""
    st = dict(t.get("structured") or {})
    fields = {k: dict(v) for k, v in (st.get("fields") or {}).items()}
    for k, v in ((manual_entry or {}).get("fields") or {}).items():
        if v in (None, "", []):
            fields.pop(k, None)          # 手填空值 = 显式清掉自动识别结果
            continue
        prev = fields.get(k) or {}
        fields[k] = {"value": v, "source": "manual", "confirmed": True,
                     "evidence": (manual_entry or {}).get("notes") or "手填结构化字段",
                     "previousAuto": prev.get("value") if prev.get("source") == "doc:keyword" else None}
    t["fields"] = fields
    t["fieldStats"] = {
        "confirmed": len([f for f in fields.values() if f.get("confirmed")]),
        "auto": len([f for f in fields.values() if not f.get("confirmed")]),
        "total": len(fields),
    }
    return fields


def fval(t, key, default=None):
    f = (t.get("fields") or {}).get(key) or {}
    v = f.get("value")
    return default if v in (None, "", []) else v


def flist(t, key):
    v = fval(t, key)
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


# 周期类字段（xxxTF）→ 实际取值来源：先看该字段自身，再看「值里带周期的兄弟字段」的 tf 元数据
TF_SOURCE = {
    "htfPOITF": ("htfPOIType",), "ltfPOITF": ("ltfPOIType",),
    "entryTriggerTF": ("entryTriggerType", "entryTrigger"),
    "displacementTF": ("displacementQuality", "displacement"),
    "structureShiftTF": ("structureShiftType",),
    "biasSourceTF": ("htfBias",), "htfStructureTF": ("htfStructureKind", "htfStructure"),
    "sweepTF": ("liquiditySweep",), "invalidationTF": ("invalidationLogic",),
    "protectedTF": ("protectedStructure",), "reactionTF": ("reaction", "reactionType"),
}


def field_values(t, field):
    """取字段值；对「周期类」字段（xxxTF）回退到实际识别出的周期，保证 §2 的周期口径统一。

    需求 §2：HTF（1D/4H/1H）与 LTF（15min/5min）职责不同，所以周期单独存、单独统计。
    """
    vals = flist(t, field)
    if vals:
        return vals
    if field.endswith("TF"):
        from schema import ALL_TF
        for src in TF_SOURCE.get(field, ()):
            f = (t.get("fields") or {}).get(src) or {}
            if f.get("tf"):
                return list(f["tf"])
            v = f.get("value")
            hit = [x for x in (v if isinstance(v, list) else [v])
                   if isinstance(x, str) and x in ALL_TF]
            if hit:
                return hit
    return []


# ---------------------------------------------------------------- 单笔派生
COMPLIANCE_ORDER = ["Fully Compliant", "Minor Violation", "Major Violation"]
QUALITY_MAP = {("win", "Fully Compliant"): "Good Win", ("win", "Minor Violation"): "Bad Win",
               ("win", "Major Violation"): "Bad Win", ("loss", "Fully Compliant"): "Good Loss",
               ("loss", "Minor Violation"): "Bad Loss", ("loss", "Major Violation"): "Bad Loss",
               ("be", "Fully Compliant"): "Good Loss", ("be", "Minor Violation"): "Bad Loss",
               ("be", "Major Violation"): "Bad Loss"}


def derive_planned_actual(t):
    """需求 §16 Planned vs Actual：计划值来自文档计划字段，实际值来自成交字段，只做对比不做推测。"""
    p_sl, a_exit = fnum(t.get("stopLoss")), fnum(t.get("exit"))
    p_entry = fnum(t.get("entry"))
    planned = {
        "entry": p_entry, "sl": p_sl,
        "tp": fval(t, "targetLevel") or (t.get("targets") or [{}])[0].get("note"),
        "rr": t.get("plannedRR"),
    }
    actual = {
        "entry": p_entry, "exit": a_exit, "r": t.get("actualR"),
        "exitReason": fval(t, "managementStyle"),
    }
    dev = []
    if t.get("entryModel", {}).get("planned") and t.get("entryModel", {}).get("actual") \
            and t["entryModel"]["planned"] != t["entryModel"]["actual"]:
        dev.append({"field": "entryMode", "planned": t["entryModel"]["planned"],
                    "actual": t["entryModel"]["actual"], "note": "计划与实际入场方式不一致"})
    if p_sl is None:
        dev.append({"field": "sl", "note": "未记录准确 SL，无法比较计划与实际风险"})
    return {"planned": planned, "actual": actual, "deviations": dev,
            "recorded": {"plannedEntry": p_entry is not None, "plannedSL": p_sl is not None,
                         "plannedRR": t.get("plannedRR") is not None,
                         "actualR": t.get("actualR") is not None}}


def derive_quality(t):
    """需求 §23 Trade Quality：结果 × 合规度，两边都必须有记录才给结论。"""
    manual = fval(t, "tradeQuality")
    if manual:
        return {"value": manual, "source": "manual",
                "basis": "手填"}
    comp = fval(t, "ruleCompliance")
    src = "标注" if comp in COMPLIANCE_ORDER else None
    if src is None:      # 文档没写合规度 → 用清单派生值（仍标记为派生，不冒充文档记录）
        dc = (t.get("complianceV2") or {}).get("derivedCompliance") or {}
        if dc.get("value"):
            comp, src = dc["value"], "派生"
    st = t.get("resultStatus")
    if comp in COMPLIANCE_ORDER and st in ("win", "loss", "be"):
        return {"value": QUALITY_MAP.get((st, comp)), "source": "derived",
                "basis": f"结果={st} × 合规度={comp}（{src}）"}
    cls = ((t.get("analysis") or {}).get("classification") or {}).get("value")
    if cls:
        return {"value": cls, "source": "ai-review", "basis": "分析层分类（旧字段）"}
    miss = []
    if comp not in COMPLIANCE_ORDER:
        miss.append("规则合规度")
    if st not in ("win", "loss", "be"):
        miss.append("已结束的结果")
    return {"value": None, "source": "derived", "basis": "缺：" + "、".join(miss) + "——不猜"}


def derive_checklist(t):
    """需求 §33 / §34：Must Have / Confirmation / Avoid 三组清单逐项判定（✓ / ✕ / 未记录）。"""
    from schema import RULE_BUCKETS
    out = {"Must Have": [], "Confirmation": [], "Avoid": []}
    for bucket, items in RULE_BUCKETS.items():
        for it in items:
            mode, field = it["mode"], it["field"]
            val = flist(t, field) if mode.startswith(("in:", "not_in:")) else fval(t, field)
            status, shown = "未记录", val
            if mode == "set":
                status = "✓" if val else "未记录"
            elif mode.startswith("in:"):
                want = mode[3:].split(",")
                status = ("✓" if any(v in want for v in (val or [])) else "✕") if val else "未记录"
            elif mode.startswith("not_in:"):
                bad = mode[7:].split(",")
                status = ("✕" if any(v in bad for v in (val or [])) else "✓") if val else "未记录"
            elif mode == "rr_gate":
                thr = t.get("minRRThreshold")
                rr = t.get("plannedRR")
                if rr is None:
                    status = "未记录"
                elif thr is None:
                    status = "—"          # 需求 §5：没定义最低 RR 标准就不下结论
                else:
                    status = "✓" if rr >= thr else "✕"
            out[bucket].append({"id": it["id"], "text": it["text"], "field": field,
                                "status": status, "value": shown,
                                "source": ((t.get("fields") or {}).get(field) or {}).get("source")})
    allit = out["Must Have"] + out["Confirmation"] + out["Avoid"]
    yes = [i for i in allit if i["status"] == "✓"]
    no = [i for i in allit if i["status"] == "✕"]
    known = len(yes) + len(no)
    mh_missing = [i["text"] for i in out["Must Have"] if i["status"] == "未记录"]
    cf_missing = [i["text"] for i in out["Confirmation"] if i["status"] == "未记录"]
    return {"groups": out, "yes": len(yes), "no": len(no), "unknown": len(allit) - known,
            "known": known, "total": len(allit),
            "passRate": rate(len(yes), known),
            "mustHaveMissing": mh_missing, "confirmationMissing": cf_missing,
            "derivedCompliance": derive_compliance(out)}


def derive_compliance(out):
    """需求 §21 / §34：按清单派生合规度（文档没写时才用，且标记成「派生」）。

    Must Have 违反 / Avoid 命中 → Major（FOMO、追价、低 RR、弱 MSB 都算严重违规）；
    Confirmation 缺失 → Minor；Must Have 本身没记录 → 不下结论（不猜，需求 §37）。
    """
    mh_no = [i["text"] for i in out["Must Have"] if i["status"] == "✕"]
    av_no = [i["text"] for i in out["Avoid"] if i["status"] == "✕"]
    cf_no = [i["text"] for i in out["Confirmation"] if i["status"] == "✕"]
    mh_missing = [i["text"] for i in out["Must Have"] if i["status"] == "未记录"]
    if mh_no or av_no:
        return {"value": "Major Violation", "basis": "派生（清单）= " + "；".join(mh_no + av_no),
                "caveat": None}
    if mh_missing:
        return {"value": None, "basis": "派生（清单）：核心项未记录（" + "、".join(mh_missing) + "），不下结论",
                "caveat": None}
    if cf_no:
        return {"value": "Minor Violation", "basis": "派生（清单）= 确认项未通过：" + "；".join(cf_no),
                "caveat": None}
    cf_missing = [i["text"] for i in out["Confirmation"] if i["status"] == "未记录"]
    return {"value": "Fully Compliant", "basis": "派生（清单）：核心项全部通过",
            "caveat": ("确认项未记录 " + str(len(cf_missing)) + " 项，合规判定偏乐观") if cf_missing else None}


def suggest_mistakes(t):
    """需求 §22 / §37：从清单结果「建议」错误标签 —— 只建议，不改原始数据，等人工确认。"""
    from schema import MISTAKE_TAGS
    cv = t.get("complianceV2") or {}
    items = {i["id"]: i for g in (cv.get("groups") or {}).values() for i in g}
    out, seen = [], set()

    def add(tag, why):
        if tag and tag not in seen:
            seen.add(tag)
            out.append({"tag": tag, "source": "derived:checklist", "evidence": why})

    sw, dp, st = items.get("sweep"), items.get("displacement"), items.get("structure")
    rr = items.get("rr")
    if sw and sw["status"] == "✕":
        add("No Sweep", "清单：Liquidity Sweep = " + str(sw["value"]))
    if dp and dp["status"] == "✕":
        v = str(dp["value"])
        add("No Displacement" if v in ("None", "No") else "Weak Displacement", "清单：Displacement = " + v)
    if st and st["status"] == "✕":
        add("Internal MSB Only", "清单：结构破坏只到 " + str(st["value"]))
    if rr and rr["status"] == "✕":
        add("Poor RR", "清单：RR = " + str(rr["value"]))
    if (t.get("entryModel") or {}).get("deviation"):
        add("Chase Price", "入场与计划不一致：" + str((t.get("entryModel") or {}).get("deviation"))[:60])
    unmapped = []
    for m in ((t.get("analysis") or {}).get("mistakes") or []):
        tag = m.get("tag")
        if tag in set(MISTAKE_TAGS):
            add(tag, "分析层：" + str(m.get("evidence"))[:80])
        else:
            unmapped.append(tag)          # 不在 §22 词表里的旧标签，如实登记、不硬塞
    return {"suggestions": out, "unmapped": unmapped}



# ---------------------------------------------------------------- 聚合
DIMENSIONS = [
    ("htfBias", "HTF Bias", "single"),
    ("biasSourceTF", "Bias 来源周期", "multi"),
    ("marketCondition", "市场环境", "single"),
    ("htfStructureKind", "HTF Structure", "multi"),
    ("liquidityType", "Liquidity 类型", "multi"),
    ("liquiditySweep", "Liquidity Sweep", "single"),
    ("sweepQuality", "Sweep 质量", "single"),
    ("htfPOIType", "HTF POI 类型", "multi"),
    ("htfPOITF", "HTF POI 周期", "multi"),
    ("ltfPOIType", "LTF POI 类型", "multi"),
    ("poiConfluence", "POI Confluence", "multi"),
    ("reaction", "POI 到达后反应", "single"),
    ("reactionType", "Reaction 类型", "multi"),
    ("displacement", "Displacement 是否出现（§11）", "single"),
    ("displacementQuality", "Displacement 质量", "single"),
    ("displacementTF", "Displacement 周期", "multi"),
    ("structureShiftType", "结构变化类型", "multi"),
    ("brokenStructure", "被破坏的结构", "multi"),
    ("protectedStructure", "Protected Structure", "single"),
    ("entryMode", "入场方式", "single"),
    ("limitStyle", "Limit 挂单方式", "single"),
    ("entryTriggerType", "Entry Trigger", "multi"),
    ("entryTriggerTF", "触发周期", "multi"),
    ("invalidationLogic", "Invalidation 依据", "multi"),
    ("targetLevel", "目标层级", "multi"),
    ("managementStyle", "管理方式", "multi"),
    ("ruleCompliance", "规则合规度", "single"),
    ("shouldTake", "这笔该不该做", "single"),
    ("confidence", "交易前信心", "single"),
]

DIM_LABEL = {k: lab for k, lab, _ in DIMENSIONS}


def bucket_stats(ts, key, label):
    rs = [t["actualR"] for t in ts if r_included(t)]
    pos = [r for r in rs if r > 0]
    neg = [r for r in rs if r < 0]
    closed = [t for t in ts if is_closed(t)]
    wins = [t for t in ts if t.get("resultStatus") == "win"]
    good = [t for t in ts if t.get("quality", {}).get("value") in ("Good Win", "Good Loss")]
    comp = [t for t in ts if t.get("complianceV2", {}).get("passRate") is not None]
    return {
        "key": key, "label": label, "count": len(ts), "trades": [t["id"] for t in ts],
        "closed": len(closed), "wins": len(wins),
        "winRate": rate(len(wins), len(closed)),
        "rCounted": len(rs),
        "netR": r2(sum(rs)) if rs else None,
        "avgR": r2(sum(rs) / len(rs)) if rs else None,
        "expectancy": r2(sum(rs) / len(rs)) if rs else None,
        "totalR": r2(sum(rs)) if rs else None,
        "profitFactor": r2(sum(pos) / abs(sum(neg))) if neg else (None if not pos else "∞"),
        "goodTradeRate": rate(len(good), len(closed)),
        "complianceRate": mean([t["complianceV2"]["passRate"] for t in comp]),
        "sampleNote": sample_flag(len(rs)),
    }


def dimension_tables(trades):
    tables = {}
    for field, label, kind in DIMENSIONS:
        buckets = {}
        for t in trades:
            keys = field_values(t, field)
            if not keys:
                keys = ["(未记录)"]
            for k in keys:
                buckets.setdefault(str(k), []).append(t)
        rows = [bucket_stats(ts, k, k) for k, ts in buckets.items()]
        rows.sort(key=lambda x: (-(x["rCounted"] or 0), -(x["netR"] or -99)))
        tables[field] = {"label": label, "kind": kind, "rows": rows}
    # Entry Mode：Limit / LTF Confirmation / Market（需求 §14 / §28 核心比较）
    em = {}
    for t in trades:
        cat = (t.get("entryModel") or {}).get("category") or "UNKNOWN"
        v = fval(t, "entryMode")
        if cat == "HTF_LIMIT":
            v = v or "Limit"
        elif cat == "HTF_LTF_CONFIRMATION":
            v = v or "LTF Confirmation"
        elif cat == "MARKET_ENTRY":
            v = v or "Market"
        em.setdefault(v or "(未记录)", []).append(t)
    tables["entryModeCore"] = {"label": "入场方式（Limit / LTF Confirmation / Market）", "kind": "single",
                               "rows": sorted([bucket_stats(ts, k, k) for k, ts in em.items()],
                                              key=lambda x: -(x["netR"] or -99))}
    # LTF Entry 周期比较（15m vs 5m）
    ltf = {}
    for t in trades:
        for k in (field_values(t, "entryTriggerTF") or field_values(t, "ltfPOITF")):
            ltf.setdefault(k, []).append(t)
    tables["ltfEntryTF"] = {"label": "LTF Entry 周期（15min vs 5min）", "kind": "multi",
                            "rows": sorted([bucket_stats(ts, k, k) for k, ts in ltf.items()],
                                           key=lambda x: -(x["netR"] or -99))}
    return tables


def mistake_analysis(trades):
    by = {}
    for t in trades:
        tags = flist(t, "mistakes")
        for tag in tags:
            by.setdefault(tag, []).append(t)
    rows = []
    from schema import MISTAKE_CATEGORY
    for tag, ts in by.items():
        rs = [t["actualR"] for t in ts if r_included(t)]
        neg = sum(r for r in rs if r < 0)
        conf = [t for t in ts if str(((t.get("fields") or {}).get("mistakes") or {}).get("source", ""))
                .startswith(("manual", "doc"))]
        rows.append({"tag": tag, "category": MISTAKE_CATEGORY.get(tag, "其他"),
                     "count": len(ts), "confirmedCount": len(conf),
                     "unconfirmed": not conf,
                     "trades": [t["id"] for t in ts],
                     "netR": r2(sum(rs)) if rs else None,
                     "lostR": r2(neg) if rs else None,
                     "rCounted": len(rs)})
    rows.sort(key=lambda x: (-(x["count"]), (x["lostR"] or 0)))
    return {"rows": rows,
            "mostCommon": rows[0]["tag"] if rows else None,
            "costliest": (min(rows, key=lambda x: (x["lostR"] or 0)) if rows else None),
            "totalLostR": r2(sum(x["lostR"] or 0 for x in rows))}


def mae_mfe_analysis(trades):
    rec = [t for t in trades if t.get("mae") is not None or t.get("mfe") is not None]
    def pick(ts, f):
        return [fnum(t.get(f)) for t in ts if fnum(t.get(f)) is not None]
    wins = [t for t in trades if t.get("resultStatus") == "win"]
    losses = [t for t in trades if t.get("resultStatus") == "loss"]
    mae_all, mfe_all = pick(rec, "mae"), pick(rec, "mfe")
    win_mae = pick(wins, "mae")
    loss_mae = pick(losses, "mae")
    loss_mfe = pick(losses, "mfe")
    win_mfe = pick(wins, "mfe")
    return {
        "recorded": len(rec), "total": len(trades),
        "avgMAE": mean(mae_all), "avgMFE": mean(mfe_all),
        "winMAE": mean(win_mae), "lossMAE": mean(loss_mae),
        "lossMFE": mean(loss_mfe), "winMFE": mean(win_mfe),
        "maxMAE": min(mae_all) if mae_all else None, "maxMFE": max(mfe_all) if mfe_all else None,
        "note": ("MAE / MFE 全部未记录，无法判断「SL 是否过紧 / TP 是否过早」。"
                 if not rec else "MAE / MFE 为文档记录值，单位 R；样本不足 5 笔时只作参考。"),
        "sampleNote": sample_flag(len(rec)),
    }


def strategy_vs_execution(trades):
    """需求 §4.3 / §41：亏损里有多少来自违规（执行问题）而不是策略本身。"""
    closed = [t for t in trades if is_closed(t)]
    good_loss = [t for t in closed if t.get("quality", {}).get("value") == "Good Loss"]
    bad_loss = [t for t in closed if t.get("quality", {}).get("value") == "Bad Loss"]
    unknown = [t for t in closed if t.get("quality", {}).get("value") is None]
    s = lambda ts: r2(sum(t["actualR"] for t in ts if r_included(t)))
    return {
        "goodLoss": {"count": len(good_loss), "r": s(good_loss), "trades": [t["id"] for t in good_loss]},
        "badLoss": {"count": len(bad_loss), "r": s(bad_loss), "trades": [t["id"] for t in bad_loss]},
        "unknownQuality": {"count": len(unknown), "trades": [t["id"] for t in unknown]},
        "note": "Good Loss = 按规则做但仍然止损（策略成本）；Bad Loss = 违规造成的亏损（执行问题，才是要改的）。",
    }


def dashboard(trades):
    closed = [t for t in trades if is_closed(t)]
    rk = [t for t in trades if r_included(t)]
    rs = [t["actualR"] for t in rk]
    pos = [r for r in rs if r > 0]
    neg = [r for r in rs if r < 0]
    good = [t for t in closed if t.get("quality", {}).get("value") in ("Good Win", "Good Loss")]
    comp = [t for t in trades if t.get("complianceV2", {}).get("passRate") is not None]
    wins = [t for t in closed if t.get("resultStatus") == "win"]
    mae = mae_mfe_analysis(trades)
    return {
        "trades": len(trades), "closed": len(closed),
        "open": len([t for t in trades if not is_closed(t)]),
        "winRate": rate(len(wins), len(closed)),
        "netR": r2(sum(rs)) if rs else None, "rCounted": len(rs),
        "avgR": mean(rs), "expectancy": mean(rs),
        "profitFactor": r2(sum(pos) / abs(sum(neg))) if neg else (None if not pos else "∞"),
        "ruleComplianceRate": mean([t["complianceV2"]["passRate"] for t in comp]),
        "goodTradeRate": rate(len(good), len(closed)),
        "goodTradeRateSample": len(closed),
        "qrCounted": len([t for t in closed if t.get("quality", {}).get("value")]),
        "avgMAE": mae["avgMAE"], "avgMFE": mae["avgMFE"],
        "rExcluded": [{"id": t["id"], "symbolLabel": t["symbolLabel"],
                       "reason": t.get("rExcludeReason")} for t in trades if not r_included(t)],
        "sampleNote": sample_flag(len(rs)),
    }



def week_notes(manual):
    return (manual or {}).get("_weeks", {})


def weekly_v2(src, trades, manual):
    by_id = {t["id"]: t for t in trades}
    notes = week_notes(manual)
    out = []
    for w in src["weeks"]:
        wt = [by_id[i] for i in w["tradeIds"] if i in by_id]
        rk = [t for t in wt if r_included(t)]
        closed = [t for t in wt if is_closed(t)]
        wins = [t for t in closed if t.get("resultStatus") == "win"]
        rs = [t["actualR"] for t in rk]
        # 本周最佳 Setup / 最大错误：都要求至少 2 笔，避免单笔巧合被当成结论
        setups = {}
        for t in rk:
            sig = " → ".join((t.get("setup") or {}).get("flow") or []) or "(未记录)"
            setups.setdefault(sig, []).append(t)
        cand = {k: v for k, v in setups.items() if len(v) >= 2} or setups
        best = max(cand.items(), key=lambda kv: sum(x["actualR"] for x in kv[1])) if cand else (None, None)
        mrows = mistake_analysis(rk)["rows"]
        big = mrows[0] if mrows else None
        costliest = min(mrows, key=lambda x: (x["lostR"] or 0)) if mrows else None
        good = [t for t in closed if t.get("quality", {}).get("value") in ("Good Win", "Good Loss")]
        comp = mean([t["complianceV2"]["passRate"] for t in wt
                     if t.get("complianceV2", {}).get("passRate") is not None])
        mae = mae_mfe_analysis(wt)
        n = notes.get(w["label"]) or {}
        out.append({
            "label": w["label"], "start": w["start"], "end": w["end"], "isoWeek": w.get("isoWeek"),
            "trades": len(wt), "closed": len(closed), "wins": len(wins), "losses": len(wt) - len(wins),
            "winRate": rate(len(wins), len(closed)),
            "netR": r2(sum(rs)) if rs else None, "rCounted": len(rk),
            "avgR": mean(rs), "expectancy": mean(rs),
            "goodTradeRate": rate(len(good), len(closed)),
            "ruleComplianceRate": comp,
            "bestSetup": ({"setup": best[0], "netR": r2(sum(x["actualR"] for x in best[1])),
                           "count": len(best[1])} if best[0] else None),
            "biggestMistake": big, "costliestMistake": costliest,
            "mistakeLostR": r2(sum(x["lostR"] or 0 for x in mrows)) if mrows else None,
            "avgMAE": mae["avgMAE"], "avgMFE": mae["avgMFE"],
            "didWell": n.get("didWell"), "mainProblem": n.get("mainProblem"),
            "nextFocus": n.get("nextFocus"),
            "notesSource": "manual/_weeks.json" if n else None,
            "summaryRaw": w.get("summaryRaw"),
            "tradeIds": w["tradeIds"],
            "sampleNote": sample_flag(len(rk)),
        })
    return out


def timeframe_usage(trades):
    """需求 §2 / P0-1：HTF / LTF 使用情况统一口径。"""
    from schema import HTF_TF, LTF_TF
    htf_use, ltf_use = {}, {}
    for t in trades:
        for f in ("biasSourceTF", "htfStructureTF", "liquidityTF", "htfPOITF", "invalidationTF",
                  "protectedTF", "sweepTF", "displacementTF", "structureShiftTF"):
            for tf in field_values(t, f):
                if tf in HTF_TF:
                    htf_use.setdefault(tf, []).append(t)
        for f in ("ltfPOITF", "entryTriggerTF", "reactionTF"):
            for tf in field_values(t, f):
                if tf in LTF_TF:
                    ltf_use.setdefault(tf, []).append(t)
    rows = lambda d: sorted([bucket_stats(ts, k, k) for k, ts in d.items()],
                            key=lambda x: -(x["rCounted"] or 0))
    return {"HTF": HTF_TF, "LTF": LTF_TF,
            "HTFUsage": rows(htf_use), "LTFUsage": rows(ltf_use),
            "note": "HTF = 1D / 4H / 1H（Context / Bias / Liquidity / POI / 主要结构 / 目标）；"
                    "LTF = 15min / 5min（Reaction / Sweep / Displacement / 结构变化 / Entry）。"}


def quality_summary(trades):
    closed = [t for t in trades if is_closed(t)]
    known = [t for t in closed if t.get("quality", {}).get("value")]
    buckets = {}
    for t in closed:
        buckets.setdefault(t.get("quality", {}).get("value") or "(无法判定)", []).append(t)
    rows = []
    for q in ("Good Win", "Good Loss", "Bad Win", "Bad Loss", "(无法判定)"):
        ts = buckets.get(q, [])
        rs = [x["actualR"] for x in ts if r_included(x)]
        rows.append({"value": q, "count": len(ts), "netR": r2(sum(rs)) if rs else None,
                     "rCounted": len(rs), "trades": [x["id"] for x in ts]})
    return {"rows": rows, "closed": len(closed), "judged": len(known),
            "goodTradeRate": rate(len([t for t in closed if (t.get("quality") or {}).get("value")
                                       in ("Good Win", "Good Loss")]), len(closed)),
            "note": "Good = 符合规则（哪怕亏钱）；Bad = 违规（哪怕赚钱）。目标是提高 Good Trade Rate，而不是只看胜率。"}


def confidence_vs_result(trades):
    rows = {}
    for t in trades:
        c = fval(t, "confidence")
        if c is None:
            continue
        rows.setdefault(str(c), []).append(t)
    return sorted([bucket_stats(ts, k, f"信心 {k}") for k, ts in rows.items()],
                  key=lambda x: x["key"])



# ---------------------------------------------------------------- §41 系统必须回答的问题
MIN_Q_SAMPLE = 10       # 需求 §44：20 笔起才谈结论，这里更保守
TIE_EPS = 0.05


def _rr(v):
    return "—" if v is None else (("+" if v > 0 else "") + str(r2(v)) + "R")


def _cmp(r_a, r_b, name_a, name_b):
    """两组期望值对比；样本不足或差异过小都明确不下结论。"""
    if not r_a or not r_b or r_a.get("expectancy") is None or r_b.get("expectancy") is None:
        return None, "两组里至少一组没有可计 R 的交易"
    na, nb = r_a["rCounted"], r_b["rCounted"]
    if min(na, nb) < 2:
        return None, "一方样本只有 " + str(min(na, nb)) + " 笔，样本不足"
    a, b = r_a["expectancy"], r_b["expectancy"]
    if abs(a - b) < TIE_EPS:
        return None, "两者差值 < " + str(TIE_EPS) + "R，看不出区别"
    w, l = (name_a, a, na), (name_b, b, nb)
    if b > a:
        w, l = (name_b, b, nb), (name_a, a, na)
    return (w[0] + " 更好：Expectancy " + _rr(w[1]) + "（" + str(w[2]) + " 笔） vs " +
            l[0] + " " + _rr(l[1]) + "（" + str(l[2]) + " 笔）"), None


def _row(rows, key):
    for r in rows or []:
        if r["key"] == key:
            return r
    return None


def _best(rows):
    cand = [r for r in (rows or []) if r["key"] != "(未记录)" and r["expectancy"] is not None and r["rCounted"] >= 2]
    if not cand:
        return None
    return max(cand, key=lambda r: r["expectancy"])


def answers(trades, dims, mis, mae, sve, dash):
    out = []
    total_r = dash["rCounted"]
    base = str(total_r) + " 笔可计 R / " + str(dash["closed"]) + " 笔已结束 / 共 " + str(dash["trades"]) + " 笔"

    def add(q, a, basis, flag=None):
        out.append({"q": q, "a": a, "basis": basis,
                    "insufficient": bool(flag) or total_r < MIN_Q_SAMPLE,
                    "sample": base})

    # 1 Setup
    b = _best(dims["structureShiftType"]["rows"])
    add("我什么 Setup / 结构形态最赚钱？",
        ("表现最好：" + b["key"] + " · Expectancy " + _rr(b["expectancy"]) + "（" + str(b["rCounted"]) + " 笔）"
         + "；最常出现：" + (mis.get("mostCommon") or "无") ) if b else "结构形态基本都没记录，先补 Broken Structure / Structure Shift",
        "按 Structure Shift Type 分组，指标 = Expectancy（平均每笔 R）")

    # 2 Entry Mode
    rows = dims["entryMode"]["rows"]
    txt, why = _cmp(_row(rows, "LTF Confirmation"), _row(rows, "Limit"), "LTF Confirmation", "Limit")
    if not txt:
        mrow = _row(rows, "Market")
        hint = []
        if _row(rows, "Limit"):
            hint.append("Limit " + str(_row(rows, "Limit")["count"]) + " 笔")
        if _row(rows, "LTF Confirmation"):
            hint.append("LTF Confirmation " + str(_row(rows, "LTF Confirmation")["count"]) + " 笔")
        txt = "暂不下结论（" + (why or "缺数据") + "）" + ("；已有 " + "、".join(hint) if hint else "")
    add("Limit 与 LTF Confirmation 哪个更适合我？", txt, "按 Entry Mode 分组比较 Expectancy / Win Rate")

    # 3 Timeframe 15m vs 5m
    rows = dims["ltfEntryTF"]["rows"]
    txt, why = _cmp(_row(rows, "15m"), _row(rows, "5m"), "15min Entry", "5min Entry")
    add("15min 与 5min Entry 哪个表现更好？",
        txt or ("暂不下结论（" + (why or "LTF Entry 周期大多未记录") + "）"),
        "按 LTF Entry 周期分组（Entry Trigger / 入场确认所用周期）")

    # 4 HTF POI
    rows = [r for r in dims["htfPOITF"]["rows"] if r["key"] != "(未记录)"]
    if rows:
        best = max(rows, key=lambda r: (r["rCounted"] > 0, r["expectancy"] or -9))
        add("1D / 4H / 1H 哪种 HTF POI 对我最有效？",
            "记录到的 HTF POI 周期： " + "，".join(r["key"] + "（" + str(r["count"]) + " 笔，Expectancy " + _rr(r["expectancy"]) + "）" for r in rows)
            + ("；样本内最好 " + best["key"] if best["rCounted"] else ""),
            "按 HTF POI 周期分组；注意 1D POI 目前可能完全没有出现")
    else:
        add("1D / 4H / 1H 哪种 HTF POI 对我最有效？", "HTF POI 周期没记录", "按 HTF POI 周期分组")

    # 5 Market Condition
    rows = [r for r in dims["marketCondition"]["rows"] if r["key"] != "(未记录)"]
    b = _best(rows)
    add("我在哪种市场环境下表现最好？",
        ("最好：" + b["key"] + " · Expectancy " + _rr(b["expectancy"]) + "（" + str(b["rCounted"]) + " 笔）") if b
        else "Market Condition 全部未记录，先补「Trending / Range / Expansion / Compression / Reversal」",
        "按 Market Condition 分组")

    # 6 Sweep
    rows = dims["liquiditySweep"]["rows"]
    txt, why = _cmp(_row(rows, "Yes"), _row(rows, "No"), "有 Sweep", "无 Sweep")
    add("Sweep 是否真的提高交易结果？",
        txt or ("暂不下结论（" + (why or "「无 Sweep」组的交易太少") + "）"),
        "Sweep = Yes / Partial 与 No 两组比较；需求 §8 不强制每笔都有 Sweep")

    # 7 Displacement
    rows = dims["displacementQuality"]["rows"]
    strong, weak = _row(rows, "Strong"), _row(rows, "Weak")
    mid = _row(rows, "Medium")
    txt, why = _cmp(strong, weak or mid, "Strong Displacement", "Weak / Medium")
    add("Displacement 是否是必要条件？",
        txt or ("暂不下结论（" + (why or "Displacement 质量分组未记录") + "）"),
        "按 Displacement 质量分组")

    # 8 Structure: Internal vs Key
    rows = dims["brokenStructure"]["rows"]
    internal = [r for r in rows if "Internal" in r["key"]]
    key = [r for r in rows if "Key" in r["key"] or "Protected" in r["key"] or "External" in r["key"]]
    txt, why = _cmp(key[0] if key else None, internal[0] if internal else None, "Key / Protected 结构破坏", "仅 Internal 结构破坏")
    add("Internal MSB 和 Key Structure Break 有什么区别？",
        txt or ("暂不下结论（" + (why or "被破坏结构（Internal vs Key / Protected）记录不足") + "）"),
        "按 Broken Structure 分组：Internal LH/HL vs Key LH/HL / Protected / External")

    # 9 Risk: SL 太紧 or 太宽
    if mae.get("lossMAE") is not None and mae.get("recorded"):
        v = mae["lossMAE"]
        verdict = "偏紧（止损常在浮亏很小甚至没到 -0.8R 前就被打掉）" if v > -0.8 else (
            "偏宽（亏损交易打到的浮亏明显超过 1R 才止损）" if v < -1.15 else "大致合理（亏损交易的 MAE 集中在 -0.8R ~ -1.15R）")
        add("我的止损通常放得太紧还是太宽？", "亏损交易平均 MAE " + _rr(v) + " → " + verdict,
            "MAE（最大不利波动）按 R 记录；只有 " + str(mae["recorded"]) + " / " + str(mae["total"]) + " 笔有记录")
    else:
        add("我的止损通常放得太紧还是太宽？", "MAE 没记录，暂时算不出来（需求 §19 要求按 R 记 MAE）",
            "MAE = Maximum Adverse Excursion，最大不利波动")

    # 10 Exit: 提前止盈
    if mae.get("winMFE") is not None and mae.get("winMFE") is not None and _win_r(trades) is not None:
        wmfe, wr = mae["winMFE"], _win_r(trades)
        gap = wmfe - wr
        verdict = ("偏早（盈利单平均还能多走 " + _rr(gap) + " 才回头）" if gap > 0.5 else
                   ("偏晚/正好（盈利单基本吃到了大部分有利波动）" if gap > -0.05 else "有过头回吐（盈利单回吐了部分利润）"))
        add("我的止盈通常太早还是太晚？", "盈利单平均 MFE " + _rr(wmfe) + " vs 实际拿到 " + _rr(wr) + " → " + verdict,
            "MFE（最大有利波动）对比实际 R")
    else:
        add("我的止盈通常太早还是太晚？", "MFE 没记录，暂时算不出来", "MFE = Maximum Favorable Excursion")

    # 11 Execution vs Strategy
    bl = sve.get("badLoss") or {}
    gl = sve.get("goodLoss") or {}
    tot_loss_r = (bl.get("r") or 0) + (gl.get("r") or 0)
    if bl.get("count") or gl.get("count"):
        share = rate(abs(bl.get("r") or 0), abs(tot_loss_r)) if tot_loss_r else 0
        add("我的亏损主要来自策略本身还是执行错误？",
            "违规亏损（Bad Loss）" + str(bl.get("count", 0)) + " 笔 / " + _rr(bl.get("r")) +
            "，合规亏损（Good Loss）" + str(gl.get("count", 0)) + " 笔 / " + _rr(gl.get("r")) +
            " → 目前亏损里 " + pct_str(share) + " 来自违规执行",
            "Bad Loss = 违规+亏损（执行问题）；Good Loss = 按规则做但止损（策略成本）")
    else:
        add("我的亏损主要来自策略本身还是执行错误？", "还没有可分类的亏损交易（需要先记 Rule Compliance）",
            "依赖 Rule Compliance 字段")

    # 12 Mistake
    c = mis.get("costliest")
    add("什么错误让我损失最多？",
        ("最贵错误：" + c["tag"] + "（" + c["category"] + "）· " + str(c["count"]) + " 笔 / " + _rr(c["lostR"])) if c
        else "还没有带 R 的错误标签记录",
        "Mistake Tags 统计（含「自动建议·待确认」标记）")

    # 13 Discipline
    rows = dims["ruleCompliance"]["rows"]
    full = _row(rows, "Fully Compliant")
    viol = _row(rows, "Minor Violation") or _row(rows, "Major Violation")
    txt, why = _cmp(full, viol, "完全合规", "有违规")
    add("严格遵守规则时，策略 Expectancy 是多少？",
        (txt or "") + ("" if txt else "暂不下结论（" + (why or "Rule Compliance 基本未记录，先在网站确认每笔的合规度") + "）"),
        "按 Rule Compliance 分组 : Fully Compliant vs Minor / Major Violation")

    # 14 Next focus
    focus = []
    if c:
        focus.append("最贵的错误是「" + c["tag"] + "」，先盯它")
    if b is None:
        focus.append("Market Condition / Broken Structure 补记录，否则无法比较行情与结构")
    if total_r < MIN_Q_SAMPLE:
        focus.insert(0, "样本只有 " + str(total_r) + " 笔可计 R（需求 §44 要求 20/50/100 笔），先稳定记录再下结论")
    add("下一阶段应该重点改进哪 1–2 个问题？", "；".join(focus[:2]) or "继续积累样本",
        "综合上面各项的样本量与最贵错误")

    return out


def _win_r(trades):
    ws = [t["actualR"] for t in trades if is_closed(t) and r_included(t) and t.get("resultStatus") == "win"]
    return mean(ws)


def pct_str(v):
    return "—" if v is None else str(r2(v * 100, 0)) + "%"


def build_result(trades, src):
    """主入口：合并手填层 → 单笔派生 → 全维度聚合。返回写进 trades.json 的 "v2" 对象。"""
    manual = load_manual()
    for t in trades:
        merge_fields(t, manual.get(t["id"]))
        t["complianceV2"] = derive_checklist(t)
        t["quality"] = derive_quality(t)
        t["plannedVsActual"] = derive_planned_actual(t)
        t["timeframes"] = {
            "HTF": sorted({tf for f in ("biasSourceTF", "htfStructureTF", "liquidityTF", "htfPOITF",
                                        "invalidationTF", "protectedTF")
                           for tf in field_values(t, f)}),
            "LTF": sorted({tf for f in ("ltfPOITF", "entryTriggerTF", "reactionTF", "sweepTF",
                                        "displacementTF", "structureShiftTF")
                           for tf in field_values(t, f)}),
        }
        sug = suggest_mistakes(t)
        t["mistakeSuggestions"] = sug
        t["mistakeTags"] = flist(t, "mistakes")
        if not t["mistakeTags"] and sug["suggestions"]:
            f = (t.setdefault("fields", {})).setdefault("mistakes", {})
            f["value"] = [x["tag"] for x in sug["suggestions"]]
            f["source"], f["confirmed"] = "derived:checklist", False
            f["evidence"] = "；".join(x["evidence"] for x in sug["suggestions"])[:300]
            t["mistakeTags"] = list(f["value"])
        t["maeMfe"] = {"mae": fnum(t.get("mae")), "mfe": fnum(t.get("mfe"))}

    tables = dimension_tables(trades)
    dims = {k: v for k, v in tables.items()}
    skipped = [v for v in dims.values() if all(x["key"] == "(未记录)" for x in v["rows"])]
    return {
        "dashboard": dashboard(trades),
        "timeframes": timeframe_usage(trades),
        "dimensions": dims,
        "dimensionOrder": [k for k, _, _ in DIMENSIONS],
        "entryModePerformance": dims["entryModeCore"],
        "ltfTimeframePerformance": dims["ltfEntryTF"],
        "marketConditionPerformance": dims["marketCondition"],
        "setupPerformance": dims["structureShiftType"],
        "mistakes": mistake_analysis(trades),
        "maeMfe": mae_mfe_analysis(trades),
        "quality": quality_summary(trades),
        "strategyVsExecution": strategy_vs_execution(trades),
        "confidence": confidence_vs_result(trades),
        "weekly": weekly_v2(src, trades, manual),
        "manualTrades": sorted(manual.keys()),
        "emptyDimensions": [k for k, v in dims.items() if all(x["key"] == "(未记录)" for x in v["rows"])],
        "answers": answers(trades, dims, mistake_analysis(trades), mae_mfe_analysis(trades),
                           strategy_vs_execution(trades), dashboard(trades)),
        "dataQuality": {
            "fieldsConfirmed": sum(t["fieldStats"]["confirmed"] for t in trades),
            "fieldsAuto": sum(t["fieldStats"]["auto"] for t in trades),
            "note": "自动识别值只是建议（需求 §37），在网站里以「自动识别·待确认」标记；确认/修改后写进 data/manual/。",
        },
    }
