#!/usr/bin/env python3
"""结构化字段抽取引擎（需求 §7–§26 / §37 / §38）。

分工：
    schema.py  → 枚举字典（唯一真源）
    rules.py   → 逐句识别规则（带区块范围 + 否定处理）
    本文件      → 引擎：文档标签解析 + 逐句识别 + 证据留痕
    手填层      → data/manual/trades.json（用户确认/覆盖，build.py 合并）

输出：
    structured = {
      "fields": {字段: {"value","source","evidence","confirmed","tf"?,"price"?,"perTF"?}},
      "unparsed": [...],          # 没认出来的原文，不静默丢弃
      "sources": {...},           # 各类来源计数
      "stats": {"confirmed": n, "suggested": n}
    }
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from schema import FIELD_BY_KEY, MISTAKE_TAGS  # noqa: E402
from rules import (RULES, META_SECTIONS, NEG_TOKENS, NO_RECORD_TOKENS, PLACEHOLDER_MARKERS,  # noqa: E402
                   ENTRY_MODE_RULES, PLAN_MARKERS, ACTUAL_MARKERS, FUTURE_MARKERS)

TF_ALIASES = {"1d": "1D", "d1": "1D", "日线": "1D", "4h": "4H", "h4": "4H", "4小时": "4H",
              "1h": "1H", "h1": "1H", "1小时": "1H", "15m": "15m", "15min": "15m",
              "15分钟": "15m", "m15": "15m", "5m": "5m", "5min": "5m", "5分钟": "5m", "m5": "5m"}
POI_MAP = {"bb": "OB", "mitigation block": "Mitigation Block", "mitigationblock": "Mitigation Block"}


def num(s):
    try:
        return float(str(s).replace(",", ""))
    except Exception:
        return None


def norm_head(text):
    return re.sub(r"\s+", "", (text or "").lower())


def parse_tf_tokens(text):
    """从文本里抓周期。大小写不敏感：4H / 4h / h4 / H4 / M15 / m15 / 15min / 15分钟 都认。"""
    out = []
    pat = r"([MmHhDd]\s*\d+|\d+\s*(?:min|m|h|小时|分钟)|\d+[Dd]\b|日线)"
    for tok in re.findall(pat, text or "", re.I):
        key = re.sub(r"\s+", "", tok).lower()
        tf = TF_ALIASES.get(key)
        if tf and tf not in out:
            out.append(tf)
    return out


def match_options(field, text):
    """在文本里找出该字段的合法取值（大小写不敏感），返回 (命中列表, 剩余文本)。"""
    spec = FIELD_BY_KEY.get(field)
    opts = spec["options"] if spec else (MISTAKE_TAGS if field == "mistakes" else [])
    found, rest = [], text or ""
    for opt in sorted(opts, key=len, reverse=True):
        pat = re.escape(opt)
        if re.search(pat, rest, re.I):
            if opt not in found:
                found.append(opt)
            rest = re.sub(pat, " ", rest, flags=re.I)
    leftover = re.sub(r"[\s/、,，+｜|和与·]+", "", rest)
    return found, leftover


def parse_struct_value(field, body):
    """解析【字段】行正文 → (values, leftover, extra)。extra 带周期 / 价格 / 每周期结构。"""
    body = body or ""
    extra = {}
    if field.endswith("TF"):
        vals = parse_tf_tokens(body)
        return vals, ("" if vals else body), extra
    if field in ("htfPOI", "ltfPOI"):
        base = "htfPOIType" if field == "htfPOI" else "ltfPOIType"
        vals, leftover = match_options(base, body)
        extra["tf"] = parse_tf_tokens(body)
        return vals, leftover, extra
    if field == "htfStructure":
        pairs = re.findall(r"(1D|4H|1H|日线)[：:]\s*([^/、，\n]+)", body)
        kinds, tfs, per = [], [], []
        for tf, kind in pairs:
            t = TF_ALIASES.get(tf.lower().replace(" ", ""), tf)
            if t not in tfs:
                tfs.append(t)
            k, _ = match_options("htfStructureKind", kind)
            for x in k:
                if x not in kinds:
                    kinds.append(x)
            per.append({"tf": t, "kind": (k[0] if k else None), "raw": kind.strip()})
        if pairs:
            return kinds, ("" if kinds else body), {"tf": tfs, "perTF": per}
        vals, leftover = match_options("htfStructureKind", body)
        extra["tf"] = parse_tf_tokens(body)
        return vals, leftover, extra
    if field == "displacement":
        per = re.findall(r"(\d+\s*(?:min|m)|15m|5m|15分钟|5分钟)[：:]\s*([^/、，\n]+)", body)
        tfs, quality = [], None
        for tf, kind in per:
            t = TF_ALIASES.get(tf.replace(" ", "").lower())
            if t and t not in tfs:
                tfs.append(t)
            got = False
            for q in ("Strong", "Medium", "Weak"):
                if re.search(q, kind, re.I):
                    quality = quality or q
                    got = True
            if re.search(r"\bno\b|没有|无", kind, re.I) and not got:
                quality = quality or "None"
        extra["tf"] = tfs
        return ([quality] if quality else []), "", extra
    if field == "protectedStructure":
        m = re.search(r"(?:约|@|at)?\s*([\d,]+(?:\.\d+)?)", body)
        extra["price"] = num(m.group(1)) if m else None
        extra["tf"] = parse_tf_tokens(body)
        vals, leftover = match_options("protectedStructure", body)
        return vals, leftover, extra
    if field == "liquiditySweep":
        vals, leftover = match_options("liquiditySweep", body)
        q, _ = match_options("sweepQuality", body)
        if q:
            extra["quality"] = q[0]
        extra["tf"] = parse_tf_tokens(body)
        return vals, leftover, extra
    if field == "confidence":
        m = re.search(r"[1-5]", body)
        return ([m.group(0)] if m else []), ("" if m else body), extra
    if field == "structureShiftType":
        vals, leftover = match_options("structureShiftType", body)
        extra["tf"] = parse_tf_tokens(body)
        return vals, leftover, extra
    if field in FIELD_BY_KEY or field == "mistakes":
        vals, leftover = match_options(field, body)
        extra["tf"] = parse_tf_tokens(body)
        return vals, leftover, extra
    return [], body, extra


def key_sentences(t):
    """把一笔交易的全部原文拆成 (区块, 句子)。结构化字段行也进来源池。"""
    out = []
    for k, v in (t.get("rawSections") or {}).items():
        chunks = v if isinstance(v, list) else [v]
        for c in chunks:
            for s in re.split(r"(?<=[。！？；])\s*|\n", c or ""):
                s = s.strip()
                if len(s) >= 4:
                    out.append((k, s))
    return out


SEPS = "，,；;。！？!?"


def clause_of(sent, start, end):
    """取命中处所在的短句（按标点切），避免长句里别处的「未记录」误伤。"""
    i = start - 1
    while i >= 0 and sent[i] not in SEPS:
        i -= 1
    j = end
    while j < len(sent) and sent[j] not in SEPS:
        j += 1
    return sent[i + 1:j]


def is_negated(sent, start, end):
    """命中处所在的短句里出现否定词 → 视为否定语境（需求 §37：不脑补）。"""
    cl = clause_of(sent, start, end).lower()
    if any(tok in cl for tok in NEG_TOKENS):
        return True
    if any(tok in sent for tok in NO_RECORD_TOKENS) and any(
            tok in clause_of(sent, start, end) for tok in NO_RECORD_TOKENS):
        return True
    # 命中处紧邻的 6 字窗口再兜一层
    win = sent[max(0, start - 6):min(len(sent), end + 2)].lower()
    return any(tok in win for tok in NEG_TOKENS)


def _entry_mode(text_sections):
    """Entry Mode 单独解析：计划 / 实际分开记录（§14 / §16）。"""
    planned, actual, evidence = None, None, []
    for section, sent in text_sections:
        if section not in ("setup", "entryModel", "entryReason", "execution", "_extra"):
            continue
        if any(mark in sent for mark in PLACEHOLDER_MARKERS):
            continue
        for pat, val in ENTRY_MODE_RULES:
            for m in re.finditer(pat, sent, re.I):
                if is_negated(sent, m.start(), m.end()):
                    continue
                is_plan = any(p in sent for p in PLAN_MARKERS)
                is_actual = any(a in sent for a in ACTUAL_MARKERS)
                if is_plan and not is_actual:
                    planned = planned or val
                elif is_actual:
                    actual = actual or val
                else:
                    actual = actual or val
                evidence.append((section, sent))
                break
    return planned, actual, evidence


def extract_structured(t):
    struct = {"fields": {}, "unparsed": [], "sources": {},
              "stats": {"confirmed": 0, "suggested": 0}}
    struct_raw = t.get("structRaw") or {}
    sents = key_sentences(t)

    def put(field, values, source, evidence, extra=None, confirmed=False, keep_all=True):
        if not values:
            return
        spec = FIELD_BY_KEY.get(field)
        multi = bool(spec["multi"]) if spec else field in (
            "biasSourceTF", "liquidityType", "liquidityTF", "poiConfluence", "reactionType",
            "reactionTF", "displacementTF", "structureShiftType", "structureShiftTF",
            "brokenStructure", "protectedTF", "entryTriggerType", "entryTriggerTF",
            "invalidationLogic", "invalidationTF", "targetLevel", "managementStyle",
            "mistakes", "sweepTF", "htfPOIType", "htfPOITF", "ltfPOIType", "ltfPOITF")
        vals = list(values)
        cur = struct["fields"].get(field)
        if cur:
            merged = cur["value"] if isinstance(cur["value"], list) else [cur["value"]]
            for v in vals:
                if v not in merged:
                    merged.append(v)
            cur["value"] = merged if multi else merged[0]
            if confirmed:
                cur["confirmed"] = True
                if source == "doc:label":
                    cur["source"] = "doc:label"
            if evidence and evidence not in (cur.get("evidence") or ""):
                cur["evidence"] = (cur.get("evidence", "") + " ⏐ " + evidence).strip(" ⏐")
            if extra:
                for k2, v2 in extra.items():
                    if v2:
                        cur[k2] = v2
            return
        struct["fields"][field] = {"value": (vals if multi else vals[0]), "source": source,
                                   "evidence": evidence, "confirmed": confirmed,
                                   "multi": multi}
        if extra:
            for k2, v2 in extra.items():
                if v2:
                    struct["fields"][field][k2] = v2
        struct["sources"][source] = struct["sources"].get(source, 0) + 1

    # ---------- 1) 文档里直接写的结构化字段行（最强证据，视为已确认）
    for field, bodies in struct_raw.items():
        for body in bodies:
            vals, leftover, extra = parse_struct_value(field, body)
            put(field, vals, "doc:label", body, extra=extra, confirmed=True)
            if field == "htfPOI" and extra.get("tf"):
                put("htfPOITF", extra["tf"], "doc:label", body, confirmed=True)
            if field == "ltfPOI" and extra.get("tf"):
                put("ltfPOITF", extra["tf"], "doc:label", body, confirmed=True)
            if field == "htfStructure":
                if extra.get("tf"):
                    put("htfStructureTF", extra["tf"], "doc:label", body, confirmed=True)
                if extra.get("perTF"):
                    struct["fields"]["htfStructurePerTF"] = {
                        "value": extra["perTF"], "source": "doc:label", "confirmed": True,
                        "evidence": body, "multi": True}
            if field == "displacement" and extra.get("tf"):
                put("displacementTF", extra["tf"], "doc:label", body, confirmed=True)
            if field == "protectedStructure":
                if extra.get("tf"):
                    put("protectedTF", extra["tf"], "doc:label", body, confirmed=True)
                if extra.get("price") is not None:
                    struct["fields"]["protectedPrice"] = {
                        "value": extra["price"], "source": "doc:label", "confirmed": True,
                        "evidence": body, "multi": False}
            if field == "liquiditySweep":
                if extra.get("quality"):
                    put("sweepQuality", [extra["quality"]], "doc:label", body, confirmed=True)
                if extra.get("tf"):
                    put("sweepTF", extra["tf"], "doc:label", body, confirmed=True)
            if field == "structureShiftType" and extra.get("tf"):
                put("structureShiftTF", extra["tf"], "doc:label", body, confirmed=True)
            if leftover:
                struct["unparsed"].append({"field": field, "raw": body, "leftover": leftover})

    # ---------- 2) 逐句识别（建议值；否定句不算；感想类区块默认跳过）
    for section, sent in sents:
        if section in META_SECTIONS:
            continue
        if any(mark in sent for mark in PLACEHOLDER_MARKERS):
            continue  # 占位句（还没成交/待补）不是事实
        if any(mark in sent for mark in FUTURE_MARKERS):
            continue  # 「以后应该…」写的是以后要做什么，不是当时做了什么
        for field, rules in RULES.items():
            for rule in rules:
                if section not in rule["sections"]:
                    continue
                if rule.get("ctx") and not any(c.lower() in sent.lower() for c in rule["ctx"]):
                    continue
                hits = list(re.finditer(rule["re"], sent, re.I))
                if not hits:
                    continue
                if rule.get("all"):
                    # 一句里可能同时出现多个（例如「1H IMB、BB、OB 重叠」）
                    got = False
                    for m2 in hits:
                        if is_negated(sent, m2.start(), m2.end()) and not rule.get("neg_v"):
                            continue
                        v2 = (m2.group(rule["g"]) or "").strip() if rule.get("g") else rule["v"]
                        v2 = POI_MAP.get(v2.lower(), v2)
                        spec2 = FIELD_BY_KEY.get(field)
                        if spec2 and v2 not in spec2["options"]:
                            v2 = rule.get("v")
                        ex2 = {}
                        if rule.get("g") == 2:
                            tf2 = parse_tf_tokens(m2.group(1) or "")
                            if tf2:
                                ex2["tf"] = tf2
                        put(field, [v2], "doc:keyword", f"[{section}] {sent}", extra=ex2)
                        got = True
                    if got:
                        break
                    continue
                m = hits[0]
                if is_negated(sent, m.start(), m.end()):
                    if not rule.get("neg_v"):
                        break
                    value = rule["neg_v"]
                else:
                    value = (m.group(rule["g"]) or "").strip() if rule.get("g") else rule["v"]
                    value = POI_MAP.get(str(value).lower(), value)
                    mapped = FIELD_BY_KEY.get(field)
                    if mapped and value not in mapped["options"] and field != "mistakes":
                        value = POI_MAP.get(str(value).lower(), rule.get("v"))
                extra = {}
                if rule.get("g") == 2:
                    tf = parse_tf_tokens(m.group(1) or "")
                    if tf:
                        extra["tf"] = tf
                put(field, [value], "doc:keyword", f"[{section}] {sent}", extra=extra)
                break

    # ---------- 3) Entry Mode（计划 / 实际分开）
    pl, ac, ev = _entry_mode(sents)
    for val, src_field in ((pl, "entryModePlanned"), (ac, "entryMode")):
        if val:
            struct["fields"][src_field] = {"value": val, "source": "doc:keyword",
                                           "evidence": " ⏐ ".join(f"[{s}] {x}" for s, x in ev[:3]),
                                           "confirmed": False, "multi": False}

    # ---------- 4) 统计
    struct["stats"]["confirmed"] = sum(1 for f in struct["fields"].values() if f.get("confirmed"))
    struct["stats"]["suggested"] = sum(1 for f in struct["fields"].values() if not f.get("confirmed"))
    return struct
