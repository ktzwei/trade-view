"""复盘判定：模型约定、证据完整度、执行质量各自保留，不从结果猜原因。"""
import math
from datetime import date, datetime, timedelta, timezone

from schema import RULE_BUCKETS

QUALITY_VALUES = {"Good Win", "Good Loss", "Bad Win", "Bad Loss"}
MODELS = {"HTF POI", "LTF Confirmation"}
CONFIRMATIONS = {"sweep": "Sweep", "displacement": "Displacement",
                 "structure": "Key Structure", "retrace": "Entry Trigger"}


def number(v):
    try:
        n = float(v)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def field(t, key):
    return (t.get("fields") or {}).get(key) or {}


def confirmed_value(t, key):
    f = field(t, key)
    if f.get("source") not in ("manual", "doc:label") or not f.get("confirmed"):
        return None
    return f.get("value")


def values(v):
    return v if isinstance(v, list) else ([] if v is None else [v])


def quality_value(t):
    v = (t.get("quality") or {}).get("value")
    result = t.get("resultStatus")
    return v if result in ("win", "loss") and v in QUALITY_VALUES and v.endswith("Win" if result == "win" else "Loss") else None


def plan_timing(t):
    timing = confirmed_value(t, "planTiming")
    if timing != "Before Entry" or not t.get("planRecordedAt"):
        return timing
    try:
        recorded = datetime.fromisoformat(t["planRecordedAt"])
        if t.get("entryTime"):
            entry = datetime.fromisoformat(t["entryTime"])
            return "Before Entry" if recorded < entry else "Retrospective"
        recorded_day = (recorded.astimezone(timezone(timedelta(hours=8))).date()
                        if recorded.tzinfo else recorded.date())
        if t.get("entryDate"):
            entry_day = date.fromisoformat(t["entryDate"])
            if recorded_day == entry_day:
                return None
            return "Before Entry" if recorded_day < entry_day else "Retrospective"
        if t.get("exitTime") and recorded >= datetime.fromisoformat(t["exitTime"]):
            return "Retrospective"
        if t.get("exitDate") and recorded_day > date.fromisoformat(t["exitDate"]):
            return "Retrospective"
        if t.get("resultStatus") in ("win", "loss", "be", "open"):
            return None
    except (ValueError, TypeError):
        return None
    return timing


def derive_quality(t):
    result = t.get("resultStatus")
    if result not in ("win", "loss"):
        return {"value": None, "source": "derived", "basis": "未结束或保本，不套用胜负四象限"}
    explicit = confirmed_value(t, "tradeQuality")
    if explicit in QUALITY_VALUES and explicit.endswith("Win" if result == "win" else "Loss"):
        return {"value": explicit, "source": field(t, "tradeQuality")["source"],
                "basis": "已确认的质量判定"}
    compliance = confirmed_value(t, "ruleCompliance")
    if compliance not in ("Fully Compliant", "Minor Violation", "Major Violation"):
        compliance = ((t.get("complianceV2") or {}).get("derivedCompliance") or {}).get("value")
    if compliance in ("Fully Compliant", "Minor Violation", "Major Violation"):
        good = compliance == "Fully Compliant"
        return {"value": ("Good " if good else "Bad ") + ("Win" if result == "win" else "Loss"),
                "source": "derived", "basis": "执行合规度 × 已结束结果"}
    classification = ((t.get("analysis") or {}).get("classification") or {}).get("value")
    if classification in QUALITY_VALUES and classification.endswith("Win" if result == "win" else "Loss"):
        return {"value": classification, "source": "ai-review", "basis": "带原文证据的分析层判定"}
    return {"value": None, "source": "derived", "basis": "证据不足，保留未判定"}


def derive_compliance(groups):
    failures = [i for i in groups["Must Have"] + groups["Avoid"] if i["status"] == "✕"]
    confirmation_failures = [i for i in groups["Confirmation"] if i["status"] == "✕"]
    unknown = [i for items in groups.values() for i in items if i["status"] in ("未记录", "—")]
    if failures:
        return {"value": "Major Violation", "basis": "已确认违反：" + "；".join(i["text"] for i in failures),
                "caveat": "另有条件尚未判定" if unknown else None}
    if confirmation_failures:
        return {"value": "Minor Violation", "basis": "计划要求的确认项未通过：" +
                "；".join(i["text"] for i in confirmation_failures),
                "caveat": "另有条件尚未判定" if unknown else None}
    if unknown:
        return {"value": None, "basis": "尚未判定：" + "；".join(i["text"] for i in unknown), "caveat": None}
    return {"value": "Fully Compliant", "basis": "所有适用条件均已确认通过", "caveat": None}


def derive_checklist(t):
    model = confirmed_value(t, "reviewModel")
    timing = plan_timing(t)
    required = values(confirmed_value(t, "requiredConfirmations"))
    confirmation_mode = confirmed_value(t, "confirmationMode")
    valid_required = bool(required) and not ("None" in required and len(required) > 1)
    if model == "LTF Confirmation" and "None" in required:
        valid_required = False
    groups = {bucket: [] for bucket in RULE_BUCKETS}
    for bucket, items in RULE_BUCKETS.items():
        for spec in items:
            key, mode = spec["field"], spec["mode"]
            val = confirmed_value(t, key)
            status, note = "未记录", "缺少已确认记录"
            if bucket == "Confirmation":
                if model not in MODELS or timing != "Before Entry":
                    note = "未确认交易前模型，不能判定该条件是否适用"
                elif required and not valid_required:
                    note = "确认要求存在冲突，需修正计划"
                elif not required and model == "LTF Confirmation":
                    note = "未记录本模型的必需确认条件"
                elif CONFIRMATIONS[spec["id"]] not in required:
                    status, note = "不适用", "该模型的交易前计划未要求此项"
                elif val is not None:
                    wanted = mode[3:].split(",") if mode.startswith("in:") else []
                    if mode.startswith("in:"):
                        status = "✓" if any(v in wanted for v in values(val)) else "✕"
                    elif mode.startswith("not_in:"):
                        key_structures = {"Key Structure", "Key LH", "Key HL", "Protected High",
                                          "Protected Low", "External Structure"}
                        status = "✓" if any(v in key_structures for v in values(val)) else "✕"
                    else:
                        status = "✓" if val else "未记录"
                    note = "按交易前确认要求检查"
            elif mode == "model":
                status = "✓" if model in MODELS else "未记录"
            elif mode == "plan_timing":
                status = "✓" if timing == "Before Entry" else "未记录"
                note = "事后补录不能证明交易前计划" if timing == "Retrospective" else note
            elif mode == "confirmation_plan":
                expected_mode = "POI Touch" if model == "HTF POI" else "LTF Confirmation"
                if model in MODELS and confirmation_mode is not None:
                    if confirmation_mode != expected_mode or (required and not valid_required):
                        status, note = "✕", "模型与确认方式 / 必需条件冲突"
                    elif model == "HTF POI" or valid_required:
                        status, note = "✓", "按记录的模型与条件检查"
            elif mode == "bias":
                if val in ("Bullish", "Bearish", "Neutral") and t.get("direction") in ("long", "short"):
                    status = "✓"
                    note = "已明确背景与交易方向；是否允许逆势由交易前模型约定，不自动判错"
            elif mode == "poi":
                if val and confirmed_value(t, "htfPOITF"):
                    status = "✓"
            elif mode == "invalidation":
                sl = number(confirmed_value(t, "plannedSL"))
                entry = number(confirmed_value(t, "plannedEntry"))
                if val and sl is not None and entry is not None:
                    correct_side = sl < entry if t.get("direction") == "long" else sl > entry
                    status = "✓" if correct_side and sl > 0 and entry > 0 and t.get("direction") in ("long", "short") else "✕"
                    note = "已记录失效依据，并检查计划 SL 的方向；不推断结构价格"
            elif mode == "rr_gate":
                rr = number(val)
                threshold = number(confirmed_value(t, "minRRThreshold"))
                if rr is not None and threshold is not None and threshold > 0:
                    status, note = ("✓" if rr >= threshold else "✕"), "按交易前记录的最低 RR 检查"
                else:
                    note = "计划 RR 或交易前阈值未记录，不预设标准"
            elif mode == "adherence":
                if val in ("Followed Plan", "Deviation"):
                    status = "✓" if val == "Followed Plan" else "✕"
            elif mode.startswith("not_in:"):
                if val is not None:
                    bad = mode[7:].split(",")
                    status = "✕" if any(v in bad for v in values(val)) else "✓"
                elif confirmed_value(t, "executionAdherence") == "Followed Plan":
                    status, note = "✓", "人工确认按计划执行，未记录该违规"
            groups[bucket].append({**spec, "status": status, "value": val,
                                   "source": field(t, key).get("source"), "note": note})
    all_items = [i for items in groups.values() for i in items]
    yes = sum(i["status"] == "✓" for i in all_items)
    no = sum(i["status"] == "✕" for i in all_items)
    unknown = sum(i["status"] == "未记录" for i in all_items)
    na = sum(i["status"] == "不适用" for i in all_items)
    derived = derive_compliance(groups)
    applicable = len(all_items) - na
    return {"groups": groups, "model": model, "yes": yes, "no": no, "unknown": unknown,
            "notApplicable": na, "known": yes + no, "total": len(all_items),
            "passRate": round(yes / (yes + no), 3) if yes + no else None,
            "coverage": round((yes + no) / applicable, 3) if applicable else None,
            "mustHaveMissing": [i["text"] for i in groups["Must Have"] if i["status"] == "未记录"],
            "confirmationMissing": [i["text"] for i in groups["Confirmation"] if i["status"] == "未记录"],
            "derivedCompliance": derived, "compliance": derived["value"]}


def derive_planned_actual(t):
    planned = {k: number(field(t, f).get("value")) for k, f in
               (("entry", "plannedEntry"), ("sl", "plannedSL"), ("tp", "plannedTP"), ("rr", "plannedRR"))}
    # Planned RR 本身是原文计划字段，可回退；Entry / SL 不与成交价混用。
    if "plannedRR" not in (t.get("fields") or {}) and "plannedRR" not in t.get("manualClearedFields", []):
        planned["rr"] = number(t.get("plannedRR"))
    closed_or_open = t.get("resultStatus") in ("win", "loss", "be", "open")
    actual_entry = number(t.get("entry")) if closed_or_open else None
    actual = {"entry": actual_entry, "exit": number(t.get("exit")), "r": number(t.get("actualR")),
              "exitReason": field(t, "managementStyle").get("value")}
    deviations = []
    if planned["entry"] is not None and actual_entry is not None and planned["entry"] != actual_entry:
        deviations.append({"field": "entry", "planned": planned["entry"], "actual": actual_entry,
                           "difference": round(actual_entry - planned["entry"], 8), "note": "成交价与计划价格不同"})
    em = t.get("entryModel") or {}
    if em.get("planned") and em.get("actual") and em["planned"] != em["actual"]:
        deviations.append({"field": "entryMode", "planned": em["planned"], "actual": em["actual"],
                           "note": "计划与实际入场方式不同"})
    timing = plan_timing(t)
    return {"planned": planned, "actual": actual, "deviations": deviations, "timing": timing,
            "timingNote": "交易前记录" if timing == "Before Entry" else
                          "事后补录，只供回看" if timing == "Retrospective" else "计划记录时点未知",
            "recorded": {"plannedEntry": planned["entry"] is not None,
                         "plannedSL": planned["sl"] is not None, "plannedRR": planned["rr"] is not None,
                         "actualEntry": actual_entry is not None, "actualR": actual["r"] is not None}}
