#!/usr/bin/env python3
"""合并 sourceData + AI analysis，计算统计口径，输出前端数据 data/trades.json。

本脚本做三件事：
  1. 证据校验：analysis 里每条 pass/fail/partial 的 evidence 必须是原文的逐字子串，
     对不上就直接报错退出（防止 AI 把推测写进复盘）。
  2. 统计口径统一：缺 SL 的交易不计 R（§5 / 规则五），未定义最低 RR 标准时不下「不合格」结论。
  3. 生成周复盘、Setup / Entry Model / Mistake 统计、规则库（含规则来源交易）。
"""
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "source.json"
ANA = ROOT / "analysis" / "analysis.json"
OUT = ROOT / "data" / "trades.json"

CHECK_STATUS = {"pass", "fail", "partial", "unknown"}


# ------------------------------------------------------------------ 工具
def trade_haystack(t):
    parts = [t.get("heading") or "", t.get("executionRaw") or ""]
    for v in (t.get("rawSections") or {}).values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            parts.extend([x for x in v if isinstance(x, str)])
    return "\n".join(parts)


def find_evidences(obj, path=""):
    """递归找出所有名为 evidence 的字符串字段。"""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "evidence" and isinstance(v, str) and v.strip():
                out.append((path, v))
            else:
                out.extend(find_evidences(v, f"{path}.{k}" if path else k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.extend(find_evidences(v, f"{path}[{i}]"))
    return out


def sentences(text):
    if isinstance(text, (list, tuple)):
        text = "；".join([x for x in text if isinstance(x, str)])
    if not text or not isinstance(text, str):
        return []
    parts = re.split(r"[。；;]\s*", text)
    return [p.strip() for p in parts if p.strip()]


def hours(mins):
    if mins is None:
        return None
    return round(mins / 60.0, 1)


def fmt_r(v, unit=2):
    if v is None:
        return None
    return f"{v:+.{unit}f}R"


# ------------------------------------------------------------------ 载入 + 校验
def load():
    src = json.loads(SRC.read_text(encoding="utf-8"))
    ana = json.loads(ANA.read_text(encoding="utf-8"))
    errors = []
    stale = []   # 引用原文已不存在（文档被重写过）→ 整块隔离，不当编造处理，也不静默删除

    haystacks = {t["id"]: trade_haystack(t) for t in src["trades"]}
    week_haystack = {}
    for w in src["weeks"]:
        parts = [w.get("summaryRaw") or ""]
        for tid in w["tradeIds"]:
            parts.append(haystacks.get(tid, ""))
        week_haystack[w["label"]] = "\n".join(parts)

    # 1. analysis 里引用的交易必须真实存在（不存在 = 文档已重写/删笔 → 隔离该块）
    for tid in list(ana["trades"]):
        if tid not in haystacks:
            stale.append(f"{tid}（当前文档里没有这笔交易）")
            ana["trades"].pop(tid, None)

    # 2. 每条 evidence / note 里的关键引用必须能在原文里逐字找到
    #    对不上 = 这份复盘是照旧版文档写的（文档后来被重写过，措辞已变）→ 整块隔离：
    #      · 不进站点、不计入统计（否则就是把旧文档的结论当现在的原文用）
    #      · 全部对不上的条目逐条打印 + 写进 meta，绝不静默删除
    #    (analysis.json 没有绑定文档版本，所以只说「对不上」，不说「谁对谁错」。)
    def check_block(owner, blk, hay):
        evs = find_evidences(blk, owner)
        bad = [(p_, ev) for p_, ev in evs if ev not in hay]
        if bad:
            stale.append((owner, len(evs), bad))
            return False
        return True

    for tid in list(ana["trades"]):
        if tid not in haystacks:
            continue
        if not check_block(tid, ana["trades"][tid], haystacks[tid]):
            ana["trades"].pop(tid, None)
    for wid in list(ana.get("weeks", {})):
        blk = ana["weeks"][wid]
        if wid not in week_haystack:
            stale.append((wid, 0, [("(周)", "当前文档里找不到这一周")]))
            ana["weeks"].pop(wid, None)
            continue
        if not check_block(wid, blk, week_haystack[wid]):
            ana["weeks"].pop(wid, None)

    # 3. status 取值合法
    for tid, blk in ana["trades"].items():
        for item in blk.get("riskCheck", []):
            if item["status"] not in CHECK_STATUS:
                errors.append(f"[riskCheck] {tid} {item['key']} status 非法：{item['status']}")
            if item["status"] != "unknown" and not item.get("evidence"):
                errors.append(f"[riskCheck] {tid} {item['key']} 非 unknown 却没有 evidence")

    if stale:
        print(f"[WARN] 分析层有 {len(stale)} 块复盘引用的原文已不在当前文档 —— 已隔离（不上线、不计入统计），需重做 AI 复盘：")
        items = []
        for owner, total, bad in stale:
            items.append({"block": owner, "evidenceTotal": total,
                          "mismatch": [{"path": p_, "quote": ev} for p_, ev in bad[:12]],
                          "mismatchCount": len(bad)})
            print(f"   - {owner}：{len(bad)}/{total} 条引用对不上，例：{bad[0][1]!r}")
        ana.setdefault("meta", {})["staleQuarantine"] = {
            "count": len(stale),
            "reason": "文档已重写（措辞/分节都变了），这些复盘的逐字引用在当前原文里找不到。按「不猜、不编造」，旧结论一律不上线，重做后再显示。",
            "items": items,
        }
    if errors:
        print("[FAIL] 数据校验未通过：")
        for e in errors:
            print("   -", e)
        raise SystemExit(1)
    print(f"[OK] evidence 校验通过（{len(ana['trades'])} 笔交易 / {len(ana.get('weeks', {}))} 个周）")
    return src, ana


# ------------------------------------------------------------------ 合并
def build_trades(src, ana):
    checklist = ana["meta"]["checklist"]
    labels = {c["key"]: c["label"] for c in checklist}
    out = []
    for t in src["trades"]:
        a = ana["trades"].get(t["id"], {})
        provided = {i["key"]: i for i in a.get("riskCheck", [])}
        rc = []
        for c in checklist:
            item = provided.get(c["key"], {"status": "unknown",
                                           "note": "文档未记录，AI 不做推测。"})
            item = dict(item)
            item["label"] = labels[c["key"]]
            rc.append(item)

        counts = {s: 0 for s in CHECK_STATUS}
        for i in rc:
            counts[i["status"]] += 1
        known = counts["pass"] + counts["fail"] + counts["partial"]
        compliance = {
            "pass": counts["pass"], "fail": counts["fail"], "partial": counts["partial"],
            "unknown": counts["unknown"], "known": known, "total": len(rc),
            "rate": round(counts["pass"] / known, 3) if known else None,
        }

        t2 = dict(t)
        t2["analysis"] = {
            "source": "ai-review",
            "errorType": a.get("errorType"),
            "classification": a.get("classification"),
            "ruleViolations": a.get("ruleViolations", []),
            "mistakes": a.get("mistakes", []),
            "riskCheck": rc,
            "compliance": compliance,
            "notes": a.get("notes"),
        }
        out.append(t2)
    return out


# ------------------------------------------------------------------ 统计
def global_stats(trades):
    closed = [t for t in trades if t.get("resultStatus") in ("win", "loss", "be")]
    wins = [t for t in closed if t["resultStatus"] == "win"]
    losses = [t for t in closed if t["resultStatus"] == "loss"]
    be = [t for t in closed if t["resultStatus"] == "be"]
    r_known = [t for t in trades if t.get("rIncluded") and t.get("actualR") is not None]
    r_unknown = [t for t in trades if not (t.get("rIncluded") and t.get("actualR") is not None)]
    net = sum(t["actualR"] for t in r_known)
    winners_r = [t["actualR"] for t in r_known if t["actualR"] > 0]
    losers_r = [t["actualR"] for t in r_known if t["actualR"] < 0]

    def em(cat):
        return [t for t in trades if (t.get("entryModel") or {}).get("category") == cat]

    violations = sum(len((t.get("analysis") or {}).get("ruleViolations", [])) for t in trades)
    missing = [t for t in trades if (t.get("dataCompleteness") or {}).get("percent", 100) < 100]
    return {
        "closed": len(closed),
        "open": len(trades) - len(closed),
        "wins": len(wins), "losses": len(losses), "be": len(be),
        "winRate": round(len(wins) / len(closed), 3) if closed else None,
        "netR": round(net, 2), "netRKnownCount": len(r_known),
        "avgR": round(net / len(r_known), 2) if r_known else None,
        "avgWinnerR": round(sum(winners_r) / len(winners_r), 2) if winners_r else None,
        "avgLoserR": round(sum(losers_r) / len(losers_r), 2) if losers_r else None,
        "htfLimitTrades": len(em("HTF_LIMIT")),
        "ltfConfirmationTrades": len(em("HTF_LTF_CONFIRMATION")),
        "marketEntryTrades": len(em("MARKET_ENTRY")),
        "otherEntryModelTrades": len(em("OTHER")) + len(em("UNKNOWN")),
        "ruleViolations": violations,
        "missingDataTrades": len(missing),
        "rExcluded": [{"id": t["id"], "symbolLabel": t["symbolLabel"],
                       "reason": t.get("rExcludeReason")
                                 or ("未记录准确 SL" if not t.get("stopLoss") else "未记录实际 R")}
                      for t in r_unknown if t.get("resultStatus") in ("win", "loss", "be")],
        "openTrades": [{"id": t["id"], "symbolLabel": t["symbolLabel"],
                        "reason": "未结束（挂单 / 持仓中），不计入胜负与 R 统计"}
                       for t in trades if t.get("resultStatus") not in ("win", "loss", "be")],
        "goodWins": len([t for t in trades if ((t.get("analysis") or {}).get("classification") or {}).get("value") == "Good Win"]),
        "badWins": len([t for t in trades if ((t.get("analysis") or {}).get("classification") or {}).get("value") == "Bad Win"]),
        "goodLosses": len([t for t in trades if ((t.get("analysis") or {}).get("classification") or {}).get("value") == "Good Loss"]),
        "badLosses": len([t for t in trades if ((t.get("analysis") or {}).get("classification") or {}).get("value") == "Bad Loss"]),
    }


def unknown_fields(trades):
    freq = {}
    for t in trades:
        for f in (t.get("dataCompleteness") or {}).get("missing", []):
            freq.setdefault(f, []).append(t["id"])
    return sorted([{"field": k, "count": len(v), "trades": v} for k, v in freq.items()],
                  key=lambda x: -x["count"])


SETUP_TAG_RULES = [
    (r"sweep", "Liquidity Sweep"),
    (r"displacement", "Displacement"),
    (r"msb|mss", "MSB / MSS"),
    (r"bos", "BOS"),
    (r"poi|ob\b|imb|bb\b|discount|premium|fvg", "POI"),
    (r"liquidity-to-liquidity", "Liquidity-to-Liquidity"),
    (r"reversal", "Reversal"),
    (r"pullback", "Pullback"),
]


def setup_tags(t):
    tags = []
    for step in ((t.get("setup") or {}).get("flow") or []):
        for pat, name in SETUP_TAG_RULES:
            if re.search(pat, step, re.I) and name not in tags:
                tags.append(name)
    return tags


def analytics(trades, weeks):
    # 累计 R 曲线（只含可计 R 的交易，按入场时间排序）
    r_trades = sorted([t for t in trades if t.get("rIncluded") and t.get("actualR") is not None],
                      key=lambda t: (t.get("entryTime") or t.get("entryDate")
                                     or t.get("exitTime") or t.get("exitDate") or ""))
    cum, curve = 0.0, []
    for t in r_trades:
        cum += t["actualR"]
        curve.append({"id": t["id"], "symbolLabel": t["symbolLabel"],
                      "date": (t.get("entryTime") or t.get("entryDate")
                               or t.get("exitTime") or t.get("exitDate") or "")[:10],
                      "r": t["actualR"],
                      "cum": round(cum, 2)})

    def group(keyfn, items):
        buckets = {}
        for t in items:
            for k in keyfn(t) or []:
                buckets.setdefault(k, []).append(t)
        out = []
        for k, ts in buckets.items():
            rs = [x["actualR"] for x in ts if x.get("rIncluded") and x["actualR"] is not None]
            wins = [x for x in ts if x.get("resultStatus") == "win"]
            closed = [x for x in ts if x.get("resultStatus") in ("win", "loss", "be")]
            out.append({
                "key": k, "trades": [x["id"] for x in ts], "count": len(ts),
                "wins": len(wins), "closed": len(closed),
                "winRate": round(len(wins) / len(closed), 3) if closed else None,
                "netR": round(sum(rs), 2) if rs else None,
                "avgR": round(sum(rs) / len(rs), 2) if rs else None,
                "rCounted": len(rs),
            })
        return sorted(out, key=lambda x: (-x["count"], -(x["netR"] or -99)))

    setup_sig = group(lambda t: [" → ".join((t.get("setup") or {}).get("flow") or []) or "(未记录)"], trades)
    setup_tag = group(lambda t: setup_tags(t) or ["(未分类)"], trades)
    entry_model = group(lambda t: [(t.get("entryModel") or {}).get("category") or "UNKNOWN"], trades)
    mistakes = group(lambda t: [m["tag"] for m in ((t.get("analysis") or {}).get("mistakes") or [])], trades)
    violations = group(lambda t: [v["tag"] for v in ((t.get("analysis") or {}).get("ruleViolations") or [])], trades)

    holding = [{"id": t["id"], "symbolLabel": t["symbolLabel"], "hours": hours(t.get("holdingMinutes")),
                "status": t.get("resultStatus")} for t in trades if t.get("holdingMinutes")]
    hw = [h["hours"] for h in holding if h["status"] == "win"]
    hl = [h["hours"] for h in holding if h["status"] == "loss"]

    cov = [t["dataCompleteness"]["percent"] for t in trades if t.get("dataCompleteness")]
    return {
        "cumulativeR": curve,
        "setupPerformance": setup_sig,
        "setupTagPerformance": setup_tag,
        "entryModelPerformance": entry_model,
        "mistakeFrequency": mistakes,
        "violationFrequency": violations,
        "holding": {
            "perTrade": holding,
            "avgWinnerHours": round(sum(hw) / len(hw), 1) if hw else None,
            "avgLoserHours": round(sum(hl) / len(hl), 1) if hl else None,
            "note": "样本数量少时均值仅供参考。",
        },
        "maeMfe": {"recorded": len([t for t in trades if t.get("mae") is not None or t.get("mfe") is not None]),
                   "total": len(trades),
                   "note": "MAE / MFE 目前全部未记录，因此无法分析「SL 是否过紧」「TP 是否过早」。"},
        "weeklyR": [{"label": w["label"], "netR": (w.get("stats") or {}).get("knownNetR"),
                     "rCounted": (w.get("stats") or {}).get("rCounted")} for w in weeks],
        "dataCompletenessAvg": round(sum(cov) / len(cov), 1) if cov else None,
    }


def build_weeks(src, ana, trades):
    by_id = {t["id"]: t for t in trades}
    out = []
    for w in src["weeks"]:
        wt = [by_id[i] for i in w["tradeIds"] if i in by_id]
        rk = [t for t in wt if t.get("rIncluded") and t.get("actualR") is not None]
        best = max(rk, key=lambda t: t["actualR"]) if rk else None
        worst = min(rk, key=lambda t: t["actualR"]) if rk else None
        wk = {k: v for k, v in w.items() if k != "tradeIds"}
        wk["tradeIds"] = w["tradeIds"]
        wk["stats"] = dict(w["stats"])
        wk["stats"]["rCountedIds"] = [t["id"] for t in rk]
        wk["stats"]["rExcluded"] = [{"id": t["id"], "symbolLabel": t["symbolLabel"],
                                     "reason": "未记录准确 SL，不计 R"} for t in wt if t not in rk]
        wk["stats"]["winRate"] = (round(wk["stats"]["wins"] / wk["stats"]["closed"], 3)
                                  if wk["stats"]["closed"] else None)
        wk["bestTrade"] = {"id": best["id"], "symbolLabel": best["symbolLabel"],
                           "actualR": best["actualR"]} if best else None
        wk["worstTrade"] = {"id": worst["id"], "symbolLabel": worst["symbolLabel"],
                            "actualR": worst["actualR"]} if worst else None
        misses = {}
        for t in wt:
            for f in (t.get("dataCompleteness") or {}).get("missing", []):
                misses.setdefault(f, 0)
                misses[f] += 1
        wk["missingData"] = [{"field": k, "count": v} for k, v in
                             sorted(misses.items(), key=lambda x: -x[1])]
        wk["avgCompleteness"] = (round(sum(t["dataCompleteness"]["percent"] for t in wt if t.get("dataCompleteness")) / len(wt), 1)
                                 if wt else None)
        wk["review"] = dict(ana.get("weeks", {}).get(w["label"]) or {})
        # best execution：本周 checklist 通过率最高、且无 fail 的交易
        def score(t):
            c = (t.get("analysis") or {}).get("compliance") or {}
            return (c.get("rate") or 0) - 0.5 * c.get("fail", 0)
        cand = [t for t in wt if (t.get("analysis") or {}).get("compliance")]
        if cand:
            be = max(cand, key=score)
            be_c = be["analysis"]["compliance"]
            wk["review"]["bestExecution"] = {
                "id": be["id"], "symbolLabel": be["symbolLabel"],
                "text": f"{be['symbolLabel']} {be['id'][:10]}：风控清单 {be_c['pass']} 项通过 / "
                        f"{be_c['fail']} 项未过" + (f" / {be_c['partial']} 项部分通过" if be_c["partial"] else "")
                        + ("（其余未记录）" if be_c["unknown"] else ""),
                "compliance": be_c,
            }
        wk["review"].setdefault("mainLesson", None)
        out.append(wk)
    return out


RULE_CATEGORY = [
    (r"POI|抢跑|front[- ]?run|限价|提前单", "Entry Rules"),
    (r"SL|止损|RR|盈亏比|风险", "Risk Rules"),
    (r"流动性|Sweep|BSL|SSL", "Liquidity Rules"),
    (r"MSB|MSS|BOS|结构|保护", "Structure Rules"),
    (r"目标|TP|Magnet|减仓|移动", "Management Rules"),
]


MODEL_LABELS = {
    "HTF_LIMIT": "HTF Limit",
    "HTF_LTF_CONFIRMATION": "HTF + LTF Confirmation",
    "MARKET_ENTRY": "Market Entry",
    "OTHER": "Other（非标准分类）",
    "UNKNOWN": "未记录",
}

SECTION_LABELS = [
    ("context", "市场背景 Context"),
    ("setup", "Setup"),
    ("entryReason", "入场原因"),
    ("entryModel", "入场模型"),
    ("time", "交易时间"),
    ("execution", "执行"),
    ("invalidation", "Invalidation"),
    ("targetLogic", "Target Logic"),
    ("result", "结果"),
    ("riskCheck", "Risk Check"),
    ("worked", "做得好的"),
    ("improve", "需要改进"),
    ("mainProblem", "主要问题"),
    ("nextRule", "下次规则"),
    ("structureNote", "结构理解"),
]


def human_duration(minutes):
    if not minutes:
        return None
    h = minutes / 60.0
    if h < 1:
        return f"{int(minutes)} 分钟"
    if h < 24:
        return f"{h:.1f} 小时"
    d = int(h // 24)
    rest = h - d * 24
    return f"{d} 天 {rest:.0f} 小时"


def enrich(t, weeks_by_id):
    """给前端补齐展示字段：标签、周引用、原文对照等。只做格式化，不产生新事实。"""
    em = t.get("entryModel") or {}
    em["label"] = MODEL_LABELS.get(em.get("category") or "UNKNOWN", "未记录")
    if em.get("planned") and em.get("actual") and em["planned"] != em["actual"]:
        em["plannedDiffersFromActual"] = True
    t["entryModel"] = em

    t["entryTrigger"] = {
        "text": t["rawSections"].get("entryModel") or t["rawSections"].get("entryTrigger"),
        "modelLabel": em["label"],
    }
    t["entryReasonItems"] = (t.get("entryReason") or {}).get("items") or []

    ed, xd = t.get("entryDate"), t.get("exitDate")
    et, xt = t.get("entryTime"), t.get("exitTime")
    t["entryTimeLabel"] = ((et or "").replace("T", " ")[:16]
                           or (f"{ed}（时间未记录）" if ed else "开仓时间未记录"))
    t["exitTimeLabel"] = ((xt or "").replace("T", " ")[:16]
                          or (f"{xd}（时间未记录）" if xd else None))
    t["entryDateLabel"] = ed
    t["exitDateLabel"] = xd
    t["partialCloseLabels"] = [p.replace("T", " ")[:16] for p in (t.get("partialCloses") or [])]
    t["holdingLabel"] = human_duration(t.get("holdingMinutes"))
    t["riskPoints"] = (t.get("derived") or {}).get("riskPoints")

    if t.get("rIncluded") is not True:
        if not t.get("stopLoss") and t.get("riskAmount"):
            t["rExcludeReason"] = "文档只记录了风险金额、没有止损价格，也没有写出 Actual R —— 按要求不强行换算"
        elif not t.get("stopLoss"):
            t["rExcludeReason"] = "未记录准确 SL，无法判断计划 RR 与实际 R —— 按规则不纳入 R 统计"
        else:
            t["rExcludeReason"] = "文档没有写出 Actual R，不代算"

    w = weeks_by_id.get(t.get("weekLabel"))
    t["week"] = {"label": w["label"], "start": w["start"], "end": w["end"],
                 "isoWeek": w.get("isoWeek")} if w else None

    for i, img in enumerate(t.get("images") or [], 1):
        img["path"] = img.get("url") or img.get("file")
        img["order"] = i
    t["sectionsLabeled"] = [{"label": lab, "text": t["rawSections"][k], "key": k}
                            for k, lab in SECTION_LABELS if t["rawSections"].get(k)]
    t["sections"] = {k: v for k, v in (t.get("sections") or {}).items() if isinstance(v, str)}
    return t


RULE_INSTRUCTION = re.compile(
    r"必须|不能|不要|不准|禁止|避免|宁可|只[能要]|应当|应该|需要|需|强制|确保|允许|等待|等更好|先|优先|记录")


def build_rules(src, trades):
    doc = [dict(r, createdFrom=None, source="doc:rules") for r in src["rules"]["items"]]
    generated, skipped = [], []
    for t in trades:
        for s in sentences(t.get("sections", {}).get("nextRule") or t.get("rawSections", {}).get("nextRule") or ""):
            # 只把「可执行的指令句」收进规则库；纯事实/价格描述（如“4388–4390 是本笔多单目标”）
            # 仍留在该笔的原文里，但不冒充规则。
            if not RULE_INSTRUCTION.search(s):
                skipped.append(s)
                continue
            cat = "General Rules"
            for pat, name in RULE_CATEGORY:
                if re.search(pat, s):
                    cat = name
                    break
            generated.append({"text": s, "category": cat,
                              "createdFrom": t["id"], "createdFromLabel":
                              f"{t['symbolLabel']} {(t.get('entryTime') or '')[:10]}",
                              "evidence": t["rawSections"].get("nextRule"),
                              "source": "trade.nextRule"})
    return {"doc": doc, "template": src["rules"]["template"], "generated": generated,
            "skippedNonRule": skipped,
            "categories": ["Liquidity Rules", "Structure Rules", "Entry Rules", "Risk Rules",
                           "Management Rules", "General Rules"]}


def main():
    src, ana = load()
    weeks_by_id = {w["label"]: w for w in src["weeks"]}
    tid2week = {i: w["label"] for w in src["weeks"] for i in w["tradeIds"]}
    for t in src["trades"]:
        t["weekLabel"] = tid2week.get(t["id"])
    trades = build_trades(src, ana)
    trades = [enrich(t, weeks_by_id) for t in trades]
    for t in trades:
        # 周链接（enrich 后统一用 id 关联，方便前端跳转）
        t["week"] = dict(t.get("week") or {}, id=t.get("weekLabel"))
    weeks = build_weeks(src, ana, trades)
    # v2 统计层（需求 §7–§35）：字段合并 → 单笔派生（合规度 / Trade Quality / Planned vs Actual /
    # MAE·MFE）→ 全维度聚合（含 Expectancy、Entry Mode、15m vs 5m、错误分析、策略 vs 执行）
    import stats_v2
    v2 = stats_v2.build_result(trades, src)
    from schema import RULE_BUCKETS, SCHEMA_VERSION, FIELDS, MISTAKE_GROUPS, ALL_TF, HTF_TF, LTF_TF
    data = {
        "meta": dict(src["meta"], analysisGeneratedAt=ana["meta"]["generatedAt"],
                     analysisRole="ai-review",
                     schemaVersion=SCHEMA_VERSION,
                     principle="交易事实来自 Google Docs；带「AI」标记的字段是分析层，且必须附原文引用。"
                               "缺失数据一律显示「未记录」，不用 0 或猜测填充。自动识别字段标记为「待确认」。"),
        "stats": global_stats(trades),
        "weeks": weeks,
        "v2": v2,
        "ruleBuckets": RULE_BUCKETS,
        # 前端用的字段元数据（标签 / 选项 / 分组 / 是否多选 / 必填层级）——唯一真源是 parser/schema.py
        "schema": {"version": SCHEMA_VERSION, "allTF": ALL_TF, "htfTF": HTF_TF, "ltfTF": LTF_TF,
                   "fields": FIELDS, "mistakeGroups": MISTAKE_GROUPS},
        "trades": trades,
        "rules": build_rules(src, trades),
        "analytics": analytics(trades, weeks),
        "unknownFields": unknown_fields(trades),
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    s = data["stats"]
    print(f"[OK] 写出 {OUT.relative_to(ROOT)}  "
          f"{s['closed']} 笔已结束 / 胜 {s['wins']} 负 {s['losses']} / 已知净值 {s['netR']:+}R "
          f"（{s['netRKnownCount']} 笔可计 R，{len(s['rExcluded'])} 笔未计入 R 统计）")
    print(f"     规则库：文档规则 {len(data['rules']['doc'])} 条 + 逐笔生成 {len(data['rules']['generated'])} 条；"
          f"平均数据完整度 {data['analytics']['dataCompletenessAvg']}%")


if __name__ == "__main__":
    main()
