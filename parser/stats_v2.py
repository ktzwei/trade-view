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
from review_logic import (QUALITY_VALUES, confirmed_value, derive_checklist, derive_compliance,
                          derive_planned_actual, derive_quality, quality_value)

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
    t["planRecordedAt"] = (manual_entry or {}).get("planRecordedAt")
    t["planHistory"] = (manual_entry or {}).get("planHistory") or []
    t["manualClearedFields"] = [k for k, v in ((manual_entry or {}).get("fields") or {}).items()
                               if v in (None, "", [])]
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
    ("reviewModel", "复盘模型", "single"),
    ("confirmationMode", "计划确认方式", "single"),
    ("orderType", "实际下单方式", "single"),
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
    rs = [t["actualR"] for t in ts if is_closed(t) and r_included(t)]
    pos = [r for r in rs if r > 0]
    neg = [r for r in rs if r < 0]
    closed = [t for t in ts if is_closed(t)]
    wins = [t for t in ts if t.get("resultStatus") == "win"]
    judged = [t for t in closed if quality_value(t)]
    good = [t for t in judged if quality_value(t) in ("Good Win", "Good Loss")]
    comp = [t for t in closed if t.get("complianceV2", {}).get("compliance") is not None]
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
        "goodTradeRate": rate(len(good), len(judged)),
        "qualityJudged": len(judged), "qualityUnknown": len(closed) - len(judged),
        "qualityCoverage": rate(len(judged), len(closed)),
        "complianceRate": rate(sum(t["complianceV2"]["compliance"] == "Fully Compliant" for t in comp), len(comp)),
        "complianceJudged": len(comp), "complianceCoverage": rate(len(comp), len(closed)),
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
        tags = confirmed_value(t, "mistakes") or []
        tags = tags if isinstance(tags, list) else [tags]
        primary = confirmed_value(t, "primaryMistake")
        if primary:
            tags = tags + [primary]
        for tag in dict.fromkeys(tags):
            by.setdefault(tag, []).append(t)
    rows = []
    from schema import MISTAKE_CATEGORY
    for tag, ts in by.items():
        rs = [t["actualR"] for t in ts if is_closed(t) and r_included(t)]
        neg = sum(r for r in rs if r < 0)
        conf = ts
        rows.append({"tag": tag, "category": MISTAKE_CATEGORY.get(tag, "其他"),
                     "count": len(ts), "confirmedCount": len(conf),
                     "unconfirmed": not conf,
                     "trades": [t["id"] for t in ts],
                     "netR": r2(sum(rs)) if rs else None,
                     "lostR": r2(neg) if rs else None,
                     "rCounted": len(rs)})
    rows.sort(key=lambda x: (-(x["count"]), (x["lostR"] or 0)))
    tagged_losses = {t["id"]: t for ts in by.values() for t in ts
                     if is_closed(t) and r_included(t) and t["actualR"] < 0}
    return {"rows": rows,
            "mostCommon": rows[0]["tag"] if rows else None,
            "costliest": (min(rows, key=lambda x: (x["lostR"] or 0)) if rows else None),
            "totalLostR": r2(sum(t["actualR"] for t in tagged_losses.values())),
            "lossTradeCount": len(tagged_losses),
            "note": "各标签显示相关交易亏损，同笔交易可出现在多行；合计按交易去重，不代表因果归因。"}


IMAGE_KINDS = ["HTF Context", "LTF Entry", "After Trade", "Review Screen"]


def load_image_meta():
    """data/manual/_images.json：{tradeId: {sha256: {type, timeframe, caption}}}（需求 §24）。"""
    p = MANUAL_DIR / "_images.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def apply_image_meta(trades, meta):
    """把手填的截图分类合并到交易图上（原图与原始数据不动，§37）。

    未分类的图保持 type=None，前端显示「未分类」，不猜它是 HTF 还是 LTF。
    """
    n = 0
    for t in trades:
        cur = (meta or {}).get(t["id"]) or {}
        for im in t.get("images") or []:
            key = str(im.get("sha256") or im.get("order"))
            m = cur.get(key)
            if not m:
                im.setdefault("type", None)
                im.setdefault("kindSource", None)
                continue
            if m.get("type"):
                im["type"] = m["type"]
            if m.get("timeframe"):
                im["timeframe"] = m["timeframe"]
            if m.get("caption"):
                im["caption"] = m["caption"]
            im["kindSource"] = "manual"
            n += 1
    return n


def image_summary(trades):
    """截图分类统计（需求 §24）：每类几张、还差几张没标。"""
    rows, total, labeled = {}, 0, 0
    for t in trades:
        for im in t.get("images") or []:
            total += 1
            k = im.get("type")
            if k:
                labeled += 1
                r = rows.setdefault(k, {"kind": k, "count": 0, "trades": [], "tf": {}})
                r["count"] += 1
                if t["id"] not in r["trades"]:
                    r["trades"].append(t["id"])
                if im.get("timeframe"):
                    r["tf"][im["timeframe"]] = r["tf"].get(im["timeframe"], 0) + 1
    order = [k for k in IMAGE_KINDS if k in rows] + [k for k in rows if k not in IMAGE_KINDS]
    return {"total": total, "labeled": labeled, "unlabeled": total - labeled,
            "rows": [rows[k] for k in order]}


def numeric_summary(trades):
    """数值字段汇总（需求 §13 Protected Price、§19 MAE/MFE）。

    没有数字就记 0 笔，不填 0、不算均值——§37「只统计文档里真实写了的」。
    """
    from schema import FIELDS
    out = []
    for spec in FIELDS:
        if spec.get("kind") != "number":
            continue
        k = spec["key"]
        rows = []
        for t in trades:
            f = (t.get("fields") or {}).get(k) or {}
            v = fnum(f.get("value"))
            if v is None:
                continue
            rows.append({"tradeId": t["id"],
                         "label": t.get("symbolLabel") or t["id"],
                         "value": v, "unit": f.get("unit") or spec.get("unit"),
                         "source": f.get("source"), "confirmed": bool(f.get("confirmed")),
                         "evidence": (f.get("evidence") or "")[:200]})
        vals = [r["value"] for r in rows]
        out.append({"key": k, "label": spec["label"], "unit": spec.get("unit"),
                    "group": spec.get("group"), "note": spec.get("note"),
                    "recorded": len(rows), "total": len(trades),
                    "avg": mean(vals), "min": round(min(vals), 4) if vals else None,
                    "max": round(max(vals), 4) if vals else None, "rows": rows})
    return out


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
    """按已判执行质量观察亏损分布，保留未定级，不作因果归因。"""
    closed = [t for t in trades if is_closed(t)]
    good_loss = [t for t in closed if t.get("quality", {}).get("value") == "Good Loss"]
    bad_loss = [t for t in closed if t.get("quality", {}).get("value") == "Bad Loss"]
    unknown = [t for t in closed if t.get("resultStatus") == "loss" and not quality_value(t)]
    s = lambda ts: r2(sum(t["actualR"] for t in ts if r_included(t)))
    return {
        "goodLoss": {"count": len(good_loss), "r": s(good_loss), "trades": [t["id"] for t in good_loss]},
        "badLoss": {"count": len(bad_loss), "r": s(bad_loss), "trades": [t["id"] for t in bad_loss]},
        "unknownQuality": {"count": len(unknown), "trades": [t["id"] for t in unknown]},
        "note": "按执行质量分组观察亏损；标签与亏损同时出现，不证明违规造成了全部损失，也不能用单笔亏损判定策略无效。",
    }


def dashboard(trades):
    closed = [t for t in trades if is_closed(t)]
    rk = [t for t in trades if is_closed(t) and r_included(t)]
    rs = [t["actualR"] for t in rk]
    pos = [r for r in rs if r > 0]
    neg = [r for r in rs if r < 0]
    judged = [t for t in closed if quality_value(t)]
    good = [t for t in judged if quality_value(t) in ("Good Win", "Good Loss")]
    comp = [t for t in closed if t.get("complianceV2", {}).get("compliance") is not None]
    wins = [t for t in closed if t.get("resultStatus") == "win"]
    mae = mae_mfe_analysis(trades)
    return {
        "trades": len(trades), "closed": len(closed),
        "open": len([t for t in trades if not is_closed(t)]),
        "winRate": rate(len(wins), len(closed)),
        "netR": r2(sum(rs)) if rs else None, "rCounted": len(rs),
        "avgR": mean(rs), "expectancy": mean(rs),
        "profitFactor": r2(sum(pos) / abs(sum(neg))) if neg else (None if not pos else "∞"),
        "ruleComplianceRate": rate(sum(t["complianceV2"]["compliance"] == "Fully Compliant" for t in comp), len(comp)),
        "ruleComplianceDecided": len(comp), "ruleComplianceUnknown": len(closed) - len(comp),
        "ruleComplianceCoverage": rate(len(comp), len(closed)), "goodWins": len(good),
        "goodTradeRate": rate(len(good), len(judged)),
        "qualityJudged": len(judged), "qualityUnknown": len(closed) - len(judged),
        "qualityCoverage": rate(len(judged), len(closed)),
        "goodTradeRateSample": len(judged),
        "qrCounted": len(judged),
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
    previous_goal = None
    for w in sorted(src["weeks"], key=lambda x: x.get("start") or ""):
        wt = [by_id[i] for i in w["tradeIds"] if i in by_id]
        rk = [t for t in wt if is_closed(t) and r_included(t)]
        closed = [t for t in wt if is_closed(t)]
        wins = [t for t in closed if t.get("resultStatus") == "win"]
        rs = [t["actualR"] for t in rk]
        # Setup 只有达到展示样本阈值才排名；错误标签只描述已确认的观察。
        setups = {}
        for t in rk:
            sig = " → ".join((t.get("setup") or {}).get("flow") or []) or "(未记录)"
            setups.setdefault(sig, []).append(t)
        cand = {k: v for k, v in setups.items() if len(v) >= MIN_Q_SAMPLE and k != "(未记录)"}
        best = max(cand.items(), key=lambda kv: mean([x["actualR"] for x in kv[1]])) if cand else (None, None)
        mrows = mistake_analysis(rk)["rows"]
        big = mrows[0] if mrows else None
        costliest = min(mrows, key=lambda x: (x["lostR"] or 0)) if mrows else None
        judged = [t for t in closed if quality_value(t)]
        good = [t for t in judged if quality_value(t) in ("Good Win", "Good Loss")]
        comp_trades = [t for t in closed if t.get("complianceV2", {}).get("compliance") is not None]
        comp = rate(sum(t["complianceV2"]["compliance"] == "Fully Compliant" for t in comp_trades), len(comp_trades))
        mae = mae_mfe_analysis(wt)
        n = dict(w.get("weekReview") or {})
        note_sources = {k: "doc:label" for k in n}
        manual_notes = notes.get(w["label"]) or {}
        n.update(manual_notes)
        note_sources.update({k: "manual/_weeks.json" for k in manual_notes})
        goal = {k: n.get("focus" + k.title()) for k in ("trigger", "action", "metric")}
        goal = dict(goal, week=w["label"]) if any(goal.values()) else None
        eligible, completed = fnum(n.get("focusEligible")), fnum(n.get("focusCompleted"))
        valid_counts = (eligible is not None and completed is not None and
                        eligible.is_integer() and completed.is_integer() and 0 <= completed <= eligible)
        behavior = {"goal": previous_goal,
                    "eligible": int(eligible) if valid_counts else None,
                    "completed": int(completed) if valid_counts else None,
                    "completionRate": rate(completed, eligible) if valid_counts and previous_goal else None,
                    "reflection": n.get("focusResult"),
                    "status": "已记录" if valid_counts and previous_goal else "待检查" if previous_goal else "没有上周改进行为"}
        out.append({
            "label": w["label"], "start": w["start"], "end": w["end"], "isoWeek": w.get("isoWeek"),
            "trades": len(wt), "closed": len(closed), "wins": len(wins),
            "losses": sum(t.get("resultStatus") == "loss" for t in closed),
            "be": sum(t.get("resultStatus") == "be" for t in closed),
            "winRate": rate(len(wins), len(closed)),
            "netR": r2(sum(rs)) if rs else None, "rCounted": len(rk),
            "avgR": mean(rs), "expectancy": mean(rs),
            "goodTradeRate": rate(len(good), len(judged)),
            "qualityJudged": len(judged), "qualityUnknown": len(closed) - len(judged),
            "qualityCoverage": rate(len(judged), len(closed)),
            "ruleComplianceRate": comp,
            "ruleComplianceDecided": len(comp_trades), "ruleComplianceUnknown": len(closed) - len(comp_trades),
            "bestSetup": ({"setup": best[0], "netR": r2(sum(x["actualR"] for x in best[1])),
                           "count": len(best[1])} if best[0] else None),
            "biggestMistake": big, "costliestMistake": costliest,
            "mistakeLostR": mistake_analysis(rk)["totalLostR"] if mrows else None,
            "avgMAE": mae["avgMAE"], "avgMFE": mae["avgMFE"],
            "didWell": n.get("didWell"), "mainProblem": n.get("mainProblem"),
            "nextFocus": n.get("nextFocus"),
            "behaviorGoal": goal, "behaviorReview": behavior,
            "reviewNotes": n, "noteSources": note_sources,
            "notesSource": " + ".join(sorted(set(note_sources.values()))) or None,
            "summaryRaw": w.get("summaryRaw"),
            "tradeIds": w["tradeIds"],
            "sampleNote": sample_flag(len(rk)),
        })
        previous_goal = goal
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
    known = [t for t in closed if quality_value(t)]
    buckets = {}
    for t in closed:
        buckets.setdefault(quality_value(t) or "(无法判定)", []).append(t)
    rows = []
    for q in ("Good Win", "Good Loss", "Bad Win", "Bad Loss", "(无法判定)"):
        ts = buckets.get(q, [])
        rs = [x["actualR"] for x in ts if r_included(x)]
        rows.append({"value": q, "count": len(ts), "netR": r2(sum(rs)) if rs else None,
                     "rCounted": len(rs), "trades": [x["id"] for x in ts]})
    return {"rows": rows, "closed": len(closed), "judged": len(known),
            "unknown": len(closed) - len(known), "coverage": rate(len(known), len(closed)),
            "goodTradeRate": rate(sum(quality_value(t) in ("Good Win", "Good Loss") for t in known), len(known)),
            "note": "质量率只使用已判定交易；未判定单列，并显示覆盖率。保本保留为未定级，不归为亏损。"}


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
MIN_Q_SAMPLE = 10       # 展示样本内比较的最小组样本，不代表策略有效性已得到证明
TIE_EPS = 0.05


def _rr(v):
    return "—" if v is None else (("+" if v > 0 else "") + str(r2(v)) + "R")


def _cmp(r_a, r_b, name_a, name_b):
    """两组期望值对比；样本不足或差异过小都明确不下结论。"""
    if not r_a or not r_b or r_a.get("expectancy") is None or r_b.get("expectancy") is None:
        return None, "两组里至少一组没有可计 R 的交易"
    na, nb = r_a["rCounted"], r_b["rCounted"]
    if min(na, nb) < MIN_Q_SAMPLE:
        return None, "一方样本只有 " + str(min(na, nb)) + " 笔，样本不足"
    a, b = r_a["expectancy"], r_b["expectancy"]
    if abs(a - b) < TIE_EPS:
        return None, "两者差值 < " + str(TIE_EPS) + "R，看不出区别"
    w, l = (name_a, a, na), (name_b, b, nb)
    if b > a:
        w, l = (name_b, b, nb), (name_a, a, na)
    return (w[0] + " 样本内平均 R 较高：" + _rr(w[1]) + "（" + str(w[2]) + " 笔） vs " +
            l[0] + " " + _rr(l[1]) + "（" + str(l[2]) + " 笔）"), None


def _row(rows, key):
    for r in rows or []:
        if r["key"] == key:
            return r
    return None


def _best(rows):
    cand = [r for r in (rows or []) if r["key"] != "(未记录)" and r["expectancy"] is not None and r["rCounted"] >= MIN_Q_SAMPLE]
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
         + "；最常出现：" + (mis.get("mostCommon") or "无") ) if b else "有效样本不足，暂不选择最佳结构形态；保留记录继续检查执行",
        "按 Structure Shift Type 分组，指标 = Expectancy（平均每笔 R）")

    # 确认逻辑与下单方式分别统计；旧 Entry Mode 不能当作两者的替代。
    rows = dims["confirmationMode"]["rows"]
    txt, why = _cmp(_row(rows, "LTF Confirmation"), _row(rows, "POI Touch"), "LTF Confirmation", "POI Touch")
    add("按确认方式分组，执行与结果有什么区别？", txt or "暂不比较（" + (why or "缺少已确认记录") + "）",
        "按计划确认方式分组；实际 Limit / Market / Stop 单独记录")

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
            + ("；样本内均值较高 " + best["key"] if best["rCounted"] >= MIN_Q_SAMPLE else "；样本不足，暂不排名"),
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

    # MAE / MFE 只描述已记录波动，不用固定阈值判定止损或退出好坏。
    add("止损设置有什么需要检查？",
        "亏损单平均 MAE " + _rr(mae.get("lossMAE")) + "；需结合计划 SL、实际止损与调整记录检查" if mae.get("lossMAE") is not None
        else "MAE 未记录，暂时无法比较",
        "单靠 MAE 不能判定止损过紧或过宽")
    paired = [t for t in trades if t.get("resultStatus") == "win" and r_included(t) and fnum(t.get("mfe")) is not None]
    gap = mean([fnum(t["mfe"]) - t["actualR"] for t in paired])
    add("退出执行有什么需要检查？",
        "同组盈利交易的 MFE 与实际 R 平均相差 " + _rr(gap) + "；回看是否执行了交易前退出规则" if paired
        else "缺少同时记录 MFE 与实际 R 的盈利交易",
        "只比较同一批交易；存在差距不等于应该拿到全部 MFE，样本 " + str(len(paired)),
        len(paired) < MIN_Q_SAMPLE)

    # 11 Execution vs Strategy
    bl = sve.get("badLoss") or {}
    gl = sve.get("goodLoss") or {}
    tot_loss_r = (bl.get("r") or 0) + (gl.get("r") or 0)
    if bl.get("count") or gl.get("count"):
        share = rate(abs(bl.get("r") or 0), abs(tot_loss_r)) if tot_loss_r else 0
        add("亏损交易的执行质量分别怎样？",
            "违规亏损（Bad Loss）" + str(bl.get("count", 0)) + " 笔 / " + _rr(bl.get("r")) +
            "，合规亏损（Good Loss）" + str(gl.get("count", 0)) + " 笔 / " + _rr(gl.get("r")) +
            "；已分类亏损中 " + pct_str(share) + " 出现在有违规的交易里",
            "这里只描述执行质量与亏损的分布，不能证明因果；未定级亏损单独列出")
    else:
        add("亏损交易的执行质量分别怎样？", "还没有可分类的亏损交易（需要先记 Rule Compliance）",
            "依赖 Rule Compliance 字段")

    # 12 Mistake
    c = mis.get("costliest")
    add("哪些已确认问题的相关交易亏损较多？",
        ("相关亏损较多的标签：" + c["tag"] + "（" + c["category"] + "）· " + str(c["count"]) + " 笔 / " + _rr(c["lostR"])) if c
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
    apply_image_meta(trades, load_image_meta())
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
        # 数值字段（§13 Protected Price、§19 MAE/MFE）：文档/手填层取到的数值同步成交易级属性，
        # 供 MAE·MFE 统计与详情页使用；取不到就保持未记录（不填 0）。
        for nk in ("mae", "mfe", "protectedPrice"):
            nf = (t.get("fields") or {}).get(nk) or {}
            nv = fnum(nf.get("value"))
            if nv is not None:
                t[nk] = nv
                t[nk + "Source"] = nf.get("source")
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
        "numeric": numeric_summary(trades),
        "images": image_summary(trades),
        "quality": quality_summary(trades),
        "strategyVsExecution": strategy_vs_execution(trades),
        "confidence": confidence_vs_result(trades),
        "weekly": weekly_v2(src, trades, manual),
        "manualTrades": sorted(k for k in manual if not k.startswith("_")),
        "emptyDimensions": [k for k, v in dims.items() if all(x["key"] == "(未记录)" for x in v["rows"])],
        "answers": answers(trades, dims, mistake_analysis(trades), mae_mfe_analysis(trades),
                           strategy_vs_execution(trades), dashboard(trades)),
        "dataQuality": {
            "fieldsConfirmed": sum(t["fieldStats"]["confirmed"] for t in trades),
            "fieldsAuto": sum(t["fieldStats"]["auto"] for t in trades),
            "note": "自动识别值只是建议（需求 §37），在网站里以「自动识别·待确认」标记；确认/修改后写进 data/manual/。",
        },
    }
