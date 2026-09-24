#!/usr/bin/env python3
"""Google Docs《交易复盘》 → 结构化交易数据 (sourceData)。

设计原则（对应需求 §2 数据真实性）：
  1. 文档里没写的字段一律 None / null，绝不推测、绝不补全。
  2. 本脚本只做「机械提取」：拆分标题层级、解析【】字段、抓取图片、抽取数字。
  3. 语义判断（Error Type / 规则违反 / 好坏交易归类）不在这里做，
     放在 analysis/analysis.json，由 build.py 合并，并且必须带原文证据。

用法：
  python3 parser/parse_gdoc.py            # 抓取并生成 data/source.json
  python3 parser/parse_gdoc.py --offline  # 用缓存好的 docx（cache/ 下）
"""
import argparse
import hashlib
import json
import os
import re
import struct
import sys
import unicodedata
import urllib.request
import zipfile
from datetime import datetime, timedelta

DOC_ID = "16gYSHlO1vvtG8lGN8UGj2v-8K3cLcXS3uli6nIHy-dU"
DOC_URL = f"https://docs.google.com/document/d/{DOC_ID}/edit"
DOCX_URL = f"https://docs.google.com/document/d/{DOC_ID}/export?format=docx"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "cache")
IMAGES = os.path.join(ROOT, "images")
DATA = os.path.join(ROOT, "data")
TZ = "+08:00"  # 北京时间

# 文档中可识别的字段标签 → 内部 key
SECTION_KEYS = {
    "市场背景": "context",
    "setup": "setup",
    "入场原因": "entryReason",
    "入场模型": "entryModel",
    "交易时间": "time",
    "执行": "execution",
    "invalidation": "invalidation",
    "target logic": "targetLogic",
    "结果": "result",
    "risk check": "riskCheck",
    "结构理解": "structureNote",
    "做得好的": "worked",
    "需要改进": "improve",
    "主要问题": "mainProblem",
    "下次规则": "nextRule",
}

MISSING = "Not Recorded"  # 前端展示缺失值时使用，实际数据里是 null


# ---------------------------------------------------------------- 抓取
def fetch_docx() -> bytes:
    os.makedirs(CACHE, exist_ok=True)
    cache_file = os.path.join(CACHE, "doc.docx")
    req = urllib.request.Request(DOCX_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
    with open(cache_file, "wb") as f:
        f.write(raw)
    return raw


def load_docx(offline: bool) -> bytes:
    if offline:
        with open(os.path.join(CACHE, "doc.docx"), "rb") as f:
            return f.read()
    return fetch_docx()


# ---------------------------------------------------------------- docx 解析
def docx_blocks(raw: bytes):
    """把 document.xml 拆成有序 block 列表：title / h1 / h2 / para / image。"""
    zf = zipfile.ZipFile(__import__("io").BytesIO(raw))
    xml = zf.read("word/document.xml").decode("utf-8")
    rels_xml = zf.read("word/_rels/document.xml.rels").decode("utf-8")
    rels = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="([^"]+)"', rels_xml))

    blocks = []
    for m in re.finditer(r"<w:p[ >].*?</w:p>", xml, re.S):
        p = m.group(0)
        style = re.findall(r'<w:pStyle w:val="([^"]+)"', p)
        style = style[0] if style else ""
        text = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S))
        text = unescape(text).strip()
        rid = re.findall(r'r:embed="(rId\d+)"', p)
        if text:
            kind = {"Title": "title", "Heading1": "h1", "Heading2": "h2"}.get(style, "para")
            blocks.append({"kind": kind, "text": text})
        for r in rid:
            target = rels.get(r, "")
            name = os.path.basename(target)
            if name:
                blocks.append({"kind": "image", "media": name})
    return blocks, zf


def unescape(s: str) -> str:
    return (s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
             .replace("&quot;", '"').replace("&apos;", "'"))


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(33)
    if head[12:16] == b"IHDR":
        w, h = struct.unpack(">II", head[16:24])
        return w, h
    return None, None


# ---------------------------------------------------------------- 工具
def slug(sym: str) -> str:
    return re.sub(r"[^a-z0-9]", "", sym.lower())


def to_iso(date_str: str, time_str: str) -> str:
    return f"{date_str}T{time_str}:00{TZ}"


def num(s):
    if s is None:
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def sentences(text: str):
    if not text:
        return []
    parts = re.split(r"(?<=[。！？])", text)
    return [p.strip() for p in parts if p.strip()]


def split_range(text):
    """'4388–4390' → (4388.0, 4390.0)"""
    if not text:
        return None, None
    m = re.search(r"([\d.]+)\s*[–\-—~]\s*([\d.]+)", text)
    if m:
        return num(m.group(1)), num(m.group(2))
    return num(text), num(text)


def label_key(text: str):
    """【市场背景 Context】 → ('context', '1H 下方 SSL 被扫…')"""
    m = re.match(r"^【([^】]+)】\s*(.*)$", text, re.S)
    if not m:
        return None, text
    head = m.group(1).strip()
    body = m.group(2).strip()
    norm = head.lower().replace(" ", "")
    for name, key in SECTION_KEYS.items():
        if name.lower().replace(" ", "") in norm:
            return key, body
    return "other:" + head, body


def heading_trade(text: str):
    """'1｜ETH/USDT Long｜2026年9月13日–9月15日｜+2.30R' → dict"""
    parts = [p.strip() for p in text.split("｜")]
    if len(parts) < 2:
        return None
    no = parts[0]
    sym_dir = parts[1]
    m = re.match(r"([A-Za-z/]+)\s+(Long|Short)", sym_dir, re.I)
    if not m:
        return None
    symbol = m.group(1).upper().replace("/", "")
    direction = m.group(2).lower()
    return {
        "num": no.zfill(2) if no.isdigit() else no,
        "symbol": symbol,
        "symbolLabel": m.group(1).upper(),
        "direction": direction,
        "dateText": parts[2] if len(parts) > 2 else None,
        "resultText": parts[3] if len(parts) > 3 else None,
        "raw": text,
    }


def parse_cn_date(s: str):
    """2026年9月13日 → 2026-09-13"""
    if not s:
        return None
    m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return None


def iso_week(d: str):
    dt = datetime.strptime(d, "%Y-%m-%d").date()
    y, w, _ = dt.isocalendar()
    monday = dt - timedelta(days=dt.weekday())
    sunday = monday + timedelta(days=6)
    return y, w, monday.isoformat(), sunday.isoformat()


# ---------------------------------------------------------------- 主解析
def parse(blocks, zf):
    weeks, trades, images_index = [], [], {}
    rules_section = None
    cur_week = cur_trade = None
    unresolved_images = []

    for bi, b in enumerate(blocks):
        if b["kind"] == "h1":
            t = b["text"]
            if "规则" in t:
                rules_section = {"title": t, "lines": [], "index": bi}
                cur_week = cur_trade = None
                continue
            if "周" in t:
                m = re.match(r"第\s*(\d+)\s*周", t)
                idx = int(m.group(1)) if m else None
                dates = re.findall(r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日", t)
                start = end = None
                year = None
                for y, mo, dd in dates:
                    if y:
                        year = int(y)
                if dates:
                    y0, m0, d0 = dates[0]
                    yy = int(y0) if y0 else (year or 2000)
                    start = f"{yy:04d}-{int(m0):02d}-{int(d0):02d}"
                if len(dates) > 1:
                    y1, m1, d1 = dates[1]
                    yy = int(y1) if y1 else (year or 2000)
                    end = f"{yy:04d}-{int(m1):02d}-{int(d1):02d}"
                iy, iw, monday, sunday = iso_week(start) if start else (None, None, None, None)
                cur_week = {
                    "label": f"第{idx}周" if idx else t,
                    "index": idx,
                    "rawHeading": t,
                    "start": start or monday,
                    "end": end or sunday,
                    "year": iy,
                    "isoWeek": iw,
                    "summaryRaw": None,
                    "trades": [],
                }
                weeks.append(cur_week)
                cur_trade = None
            continue

        if b["kind"] == "h2":
            h = heading_trade(b["text"])
            if h and cur_week is not None:
                cur_trade = {
                    "num": h["num"],
                    "symbol": h["symbol"],
                    "symbolLabel": h["symbolLabel"],
                    "direction": h["direction"],
                    "headingResult": h["resultText"],
                    "rawHeading": h["raw"],
                    "sections": {},
                    "rawSections": {},
                    "images": [],
                    "sourceBlockIndex": bi,
                }
                cur_week["trades"].append(cur_trade)
                trades.append(cur_trade)
            continue

        if b["kind"] == "image":
            if cur_trade is not None:
                cur_trade["images"].append({"media": b["media"], "blockIndex": bi})
            else:
                unresolved_images.append({"media": b["media"], "blockIndex": bi})
            continue

        # 普通段落
        if rules_section is not None:
            rules_section["lines"].append({"text": b["text"], "index": bi})
            continue

        if cur_trade is not None:
            key, body = label_key(b["text"])
            if key and key.startswith("other:"):
                cur_trade["sections"].setdefault("_extra", []).append(b["text"])
                cur_trade["rawSections"].setdefault("_extra", []).append(b["text"])
            elif key:
                cur_trade["sections"][key] = body
                cur_trade["rawSections"][key] = body
            else:
                cur_trade["sections"].setdefault("_notes", []).append(b["text"])
        elif cur_week is not None and cur_week["summaryRaw"] is None:
            cur_week["summaryRaw"] = b["text"]

    # ---------------- 组装 trade 对象
    out_trades = []
    for t in trades:
        s = t["sections"]
        d = {}
        d["id"] = build_id(t)
        d["num"] = t["num"]
        d["symbol"] = t["symbol"]
        d["symbolLabel"] = t["symbolLabel"]
        d["direction"] = t["direction"]
        d["headingResult"] = t["headingResult"]
        d["heading"] = t["rawHeading"]
        d["sourceBlockIndex"] = t["sourceBlockIndex"]

        # 交易时间
        et = xt = None
        hold = None
        stext = s.get("time", "")
        m = re.search(
            r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s*→\s*(?:(\d{4}-\d{2}-\d{2})\s+)?(\d{2}:\d{2})",
            stext,
        )
        if m:
            d1, t1, d2, t2 = m.group(1), m.group(2), m.group(3) or m.group(1), m.group(4)
            et, xt = to_iso(d1, t1), to_iso(d2, t2)
            hold = int(
                (datetime.fromisoformat(xt) - datetime.fromisoformat(et)).total_seconds() // 60
            )
        d["entryTime"] = et
        d["exitTime"] = xt
        d["holdingMinutes"] = hold
        d["timeText"] = stext or None

        # 执行价格
        ex = s.get("execution", "")
        d["entry"] = num(re.search(r"(?:实际\s*)?Entry\s*([\d.]+)", ex).group(1)) if re.search(r"(?:实际\s*)?Entry\s*([\d.]+)", ex) else None
        d["stopLoss"] = num(re.search(r"SL\s*([\d.]+)", ex).group(1)) if re.search(r"SL\s*([\d.]+)", ex) else None
        d["exit"] = num(re.search(r"Exit\s*([\d.]+)", ex).group(1)) if re.search(r"Exit\s*([\d.]+)", ex) else None
        plan_poi = re.search(r"计划\s*POI\s*约?\s*([\d.]+)", ex)
        d["plannedPOI"] = num(plan_poi.group(1)) if plan_poi else None

        targets = []
        tgt = re.search(r"Target\s*([\d.]+\s*[–\-—]\s*[\d.]+)", ex)
        if tgt:
            lo, hi = split_range(tgt.group(1))
            targets.append({"label": "Target", "priceLow": lo, "priceHigh": hi,
                            "priceText": tgt.group(1).replace(" ", ""), "sizePercent": None,
                            "types": extract_target_types(s.get("targetLogic", "")),
                            "source": "execution"})
        for m2 in re.finditer(r"TP(\d)\s*([\d.]+)\s*（(\d+)%）", ex):
            targets.append({"label": f"TP{m2.group(1)}", "priceLow": num(m2.group(2)),
                            "priceHigh": num(m2.group(2)), "priceText": m2.group(2),
                            "sizePercent": num(m2.group(3)),
                            "types": extract_target_types(s.get("targetLogic", "")),
                            "source": "execution"})
        if not targets and s.get("targetLogic"):
            # 只有文字描述、没有价格的计划目标（保持 price 为 null，不猜价格）
            targets.append({"label": "Planned Target", "priceLow": None, "priceHigh": None,
                            "priceText": None, "sizePercent": None,
                            "types": extract_target_types(s.get("targetLogic", "")),
                            "note": s.get("targetLogic"),
                            "source": "targetLogic"})
        d["targets"] = targets
        d["executionRaw"] = ex or None

        # 结果 / R
        res = s.get("result", "")
        combo = " ".join([res or "", t["headingResult"] or ""])
        status, actualR, plannedR, rIncluded = None, None, None, None
        if re.search(r"止损|亏损", combo):
            status = "loss"
        elif re.search(r"盈利|获利|已结束", combo):
            status = "win"
        elif re.search(r"持平|\bBE\b", combo):
            status = "be"
        mr = re.findall(r"([+-]?\d+(?:\.\d+)?)\s*R", res)
        mplan = re.search(r"原计划约\s*([\d.]+)\s*R", res)
        if mplan:
            plannedR = num(mplan.group(1))
        if mr:
            vals = [num(x) for x in mr]
            # 「原计划约 1.5R，实际约 +1.26R」→ 取最后一个（实际）
            actualR = vals[-1]
            rIncluded = True
        if status is None and actualR is not None:
            status = "win" if actualR > 0 else ("loss" if actualR < 0 else "be")
        if status == "win" and actualR is None:
            rIncluded = False  # 缺 SL 无法计算 → 不计入 R 统计
        d["resultStatus"] = status
        d["actualR"] = actualR
        d["plannedR"] = plannedR
        d["rIncluded"] = rIncluded
        d["resultRaw"] = res or None
        d["pnl"] = None          # 文档未记录金额盈亏
        d["fees"] = None         # 文档未记录手续费

        # Risk Check
        rc = s.get("riskCheck", "")
        rr = re.search(r"风险\s*([\d.]+)\s*点", rc)
        rew = re.search(r"目标空间约\s*([\d.]+)\s*[–\-—]\s*([\d.]+)\s*点", rc)
        prr = re.search(r"计划\s*RR\s*约\s*([\d.]+)\s*[–\-—]\s*([\d.]+)", rc)
        d["plannedRiskPoints"] = num(rr.group(1)) if rr else None
        d["plannedRewardLow"] = num(rew.group(1)) if rew else None
        d["plannedRewardHigh"] = num(rew.group(2)) if rew else None
        d["plannedRRLow"] = num(prr.group(1)) if prr else None
        d["plannedRRHigh"] = num(prr.group(2)) if prr else None
        if d["plannedRRLow"] is not None and d["plannedRRHigh"] is not None:
            # 区间取中值用于统计；区间本身也保留，前端两个都显示
            d["plannedRR"] = round((d["plannedRRLow"] + d["plannedRRHigh"]) / 2, 3)
            d["plannedRRMidpointUsed"] = d["plannedRRLow"] != d["plannedRRHigh"]
        else:
            d["plannedRR"] = None
            d["plannedRRMidpointUsed"] = None
        d["plannedRRText"] = prr.group(0) if prr else None
        d["riskCheckRaw"] = rc or None
        d["minRRThreshold"] = None   # 用户自己的最低 RR 标准尚未在文档中定义

        # 派生数字（只在输入齐全时计算，且标记 derived）
        derived = {}
        if d["entry"] is not None and d["stopLoss"] is not None:
            derived["riskPoints"] = round(abs(d["entry"] - d["stopLoss"]), 4)
            if d["exit"] is not None:
                sign = 1 if d["direction"] == "long" else -1
                derived["rewardPoints"] = round(sign * (d["exit"] - d["entry"]), 4)
                derived["rComputed"] = round(derived["rewardPoints"] / derived["riskPoints"], 3)
        d["derived"] = derived or None

        # 语义字段（只从原文识别，不做推断）
        ctx = s.get("context", "")
        tf = re.findall(r"\b(\d+m|\d+H|\d+h)\b", ctx)
        d["context"] = {
            "raw": ctx or None,
            "timeframes": sorted({x.lower() for x in tf}) or None,
            "trend": ("bearish" if re.search(r"下跌结构|主要下跌|转弱", ctx) else
                      ("bullish" if re.search(r"上涨结构|多头结构", ctx) else None)),
        }
        setup_text = s.get("setup", "")
        flow = [x.strip().rstrip("。；;，,") for x in re.split(r"→|->", setup_text) if x.strip()]
        d["setup"] = {"raw": setup_text or None, "flow": flow or None}
        d["entryReason"] = {"raw": s.get("entryReason") or None,
                            "items": sentences(s.get("entryReason", "")) or None}
        d["entryModel"] = classify_entry_model(s.get("entryModel", ""))
        d["entryModelRaw"] = s.get("entryModel") or None

        d["liquidity"] = {
            "raw": " ".join(filter(None, [ctx, s.get("entryReason", ""), s.get("targetLogic", "")])),
            "sslSwept": True if re.search(r"SSL\s*被\s*Sweep|SSL\s*被扫|流动性被扫|liq hunt", " ".join([ctx, s.get("entryReason", "")])) else None,
            "bslTarget": extract_price_range(s.get("targetLogic", "")),
            "targetLiquidity": "Buy-side Liquidity" if re.search(r"Buy-side|BSL", s.get("targetLogic", "") + s.get("entryReason", "")) else None,
            "internalLiquidity": "Internal Liquidity" if re.search(r"内部流动性", " ".join([s.get("targetLogic", ""), ctx])) else None,
            "htfMagnet": "HTF Magnet" if re.search(r"HTF Magnet", _join_sections(s)) else None,
        }

        struct_txt = " ".join(filter(None, [ctx, s.get("structureNote", ""), s.get("entryReason", "")]))
        d["structure"] = {
            "raw": struct_txt or None,
            "internalMSB": ("bullish" if re.search(r"[Ii]nternal\s*bullish\s*MSB|Internal MSB", struct_txt) else None),
            "msbNote": s.get("structureNote") or None,
            "majorTrendReversal": False if re.search(r"不代表[^。]*主趋势[^。]*反转|完成反转", struct_txt) else None,
            "protectedHigh": None,
            "protectedLow": None,
        }

        dis = " ".join(filter(None, [ctx, s.get("entryReason", "")]))
        mweak = re.search(r"(bullish|bearish)\s+MSB\s*的位移(?:偏弱|较弱|弱)", dis, re.I)
        if re.search(r"bullish displacement|Bullish Displacement|强势\s*bullish", dis, re.I):
            strength = "weak" if re.search(r"位移偏弱|较弱|weak", dis) else ("strong" if re.search(r"强势|Strong|超级强", dis) else None)
            d["displacement"] = {"type": "bullish", "strength": strength, "raw": ctx or None}
        elif mweak:
            d["displacement"] = {"type": mweak.group(1).lower(), "strength": "weak", "raw": ctx or None}
        else:
            d["displacement"] = None

        d["poi"] = extract_poi(d)

        il = s.get("invalidation", "")
        logic = None
        mlog = re.search(r"(?:止损|SL)\s*(?:逻辑)?\s*(?:放在|位于|在)([^，。；]+?)(?:下方|之上|下|上)", il)
        if mlog:
            logic = mlog.group(0)
        d["invalidation"] = {
            "raw": il or None,
            "logic": logic,
            "price": d["stopLoss"],
            "priceRecorded": d["stopLoss"] is not None,
        }

        tgt_text = s.get("targetLogic", "")
        d["targetLogic"] = {
            "raw": tgt_text or None,
            "targetType": extract_target_types(tgt_text),
            "reason": tgt_text or None,
        }

        d["tradeManagement"] = {
            "movedSL": True if re.search(r"移动 ?SL", " ".join(filter(None, list(s.values())[:0]))) else None,
            "partialTP": True if len(targets) > 1 else None,
            "breakEven": None,
            "earlyExit": None,
            "addedPosition": None,
            "reducedPosition": None,
            "weekendExit": True if re.search(r"周末", " ".join([tgt_text, res])) else None,
            "notes": None,
        }

        d["review"] = {
            "worked": sentences(s.get("worked", "")) or None,
            "improve": sentences(s.get("improve", "")) or None,
            "mainProblem": s.get("mainProblem") or None,
            "nextRules": sentences(s.get("nextRule", "")) or None,
        }

        d["mae"] = None
        d["mfe"] = None

        # 图片绑定（保持原文顺序）
        imgs = []
        for k, im in enumerate(t["images"], 1):
            imgs.append({"media": im["media"], "order": k,
                         "file": f"images/{d['id']}-{k}.png",
                         "type": None, "timeframe": None,
                         "sourceBlockIndex": im["blockIndex"]})
        d["images"] = imgs

        d["tags"] = build_tags(d)
        d["rawSections"] = t["rawSections"]        # 原始文档原文，前端「查看原文」用
        d["dataCompleteness"] = completeness(d)
        d["analysis"] = None            # 由 build.py 合并 analysis/analysis.json
        out_trades.append(d)

    # 周统计：把 trade 对象按 sourceBlockIndex 归回它所属的周
    by_block = {x["sourceBlockIndex"]: x for x in out_trades}
    for w in weeks:
        wt = [by_block[t["sourceBlockIndex"]] for t in w["trades"] if t["sourceBlockIndex"] in by_block]
        known = [x["actualR"] for x in wt if x["rIncluded"] and x["actualR"] is not None]
        w["tradeIds"] = [x["id"] for x in wt]
        w["stats"] = {
            "closed": len(wt),
            "wins": sum(1 for x in wt if x["resultStatus"] == "win"),
            "losses": sum(1 for x in wt if x["resultStatus"] == "loss"),
            "be": sum(1 for x in wt if x["resultStatus"] == "be"),
            "knownNetR": round(sum(known), 3) if known else None,
            "rCounted": len(known),
        }
        w["summaryRaw"] = w["summaryRaw"]
        del w["trades"]


    # 规则章节
    rules = {"source": rules_section["title"] if rules_section else None, "items": [], "template": []}
    if rules_section:
        for ln in rules_section["lines"]:
            txt = ln["text"]
            m = re.match(r"^(规则[一二三四五六七八九十]+)｜([^：]+)：?(.*)$", txt)
            if m:
                rules["items"].append({"id": m.group(1), "title": m.group(2).strip(),
                                       "body": m.group(3).strip(), "sourceBlockIndex": ln["index"]})
            elif re.match(r"^[①②③④⑤⑥⑦⑧⑨⑩]", txt):
                rules["template"].append({"text": txt, "sourceBlockIndex": ln["index"]})
            else:
                rules.setdefault("notes", []).append(txt)

    # nextRules 汇总（规则来源可追溯，§62）
    rule_book = []
    for t in out_trades:
        for r in (t["review"]["nextRules"] or []):
            rule_book.append({"rule": r, "createdFrom": t["id"], "symbol": t["symbol"],
                              "date": (t["entryTime"] or "")[:10]})
    for r in rules["items"]:
        rule_book.append({"rule": f"{r['id']}｜{r['title']}：{r['body']}",
                          "createdFrom": "doc:rules", "symbol": None, "date": None})

    return {
        "meta": {
            "sourceTitle": "交易复盘",
            "sourceDocId": DOC_ID,
            "sourceUrl": DOC_URL,
            "parsedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
            "schemaVersion": "1.0",
        },
        "weeks": weeks,
        "trades": out_trades,
        "rules": rules,
        "ruleBook": rule_book,
        "unresolvedImages": unresolved_images,
    }


def _join_sections(s):
    """把 sections 里的字符串值拼成一个文本块（跳过列表型 _extra/_notes）。"""
    parts = []
    for k, v in s.items():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            parts.extend([x for x in v if isinstance(x, str)])
    return " ".join(parts)


def build_id(t):
    d = t["sections"].get("time", "")
    m = re.search(r"(\d{4}-\d{2}-\d{2})", d)
    date = m.group(1) if m else "0000-00-00"
    return f"{date}-{slug(t['symbol'])}-{t['direction']}-{t['num']}"


def classify_entry_model(text: str):
    if not text:
        return {"planned": None, "actual": None, "category": None, "note": None}
    planned = None
    actual = None
    if re.search(r"原计划[^；。]*HTF Limit", text):
        planned = "HTF_LIMIT"
    if re.search(r"实际执行[^；。]*(?:市价|Market)", text):
        actual = "MARKET_ENTRY"
    if planned is None and re.search(r"HTF Limit", text):
        planned = "HTF_LIMIT"
    if actual is None and re.search(r"市价|Market Entry", text) and "实际" in text:
        actual = "MARKET_ENTRY"
    cat = actual or planned
    if cat is None:
        if re.search(r"HTF", text) and not re.search(r"更低周期确认|LTF confirmation", text.replace("未使用", "未使用")):
            cat = "OTHER"
        else:
            cat = "OTHER"
    return {"planned": planned, "actual": actual, "category": cat, "note": text}


def extract_price_range(text):
    m = re.search(r"(\d{3,5}\s*[–\-—]\s*\d{3,5})", text or "")
    return m.group(1).replace(" ", "") if m else None


def extract_target_types(text):
    if not text:
        return None
    out = []
    for pat, name in [(r"IMB", "IMB"), (r"BSL|Buy-side", "BSL"), (r"内部流动性", "Internal Liquidity"),
                      (r"external\s*(?:liquidity)?|External Liquidity", "External Liquidity"),
                      (r"上方流动性", "Liquidity"),
                      (r"Dealing Range|EQ", "EQ"), (r"HTF Magnet", "HTF Magnet")]:
        if re.search(pat, text):
            out.append(name)
    return out or None


def extract_poi(d):
    frames = []
    txt = " ".join(filter(None, [d["context"]["raw"], d["entryReason"]["raw"],
                                 d.get("entryModelRaw"), d["setup"]["raw"]]))
    for tf in re.findall(r"(\d+)\s*([HhmM])\b", txt):
        t = f"{tf[0]}{tf[1].lower()}"
        if t not in frames:
            frames.append(t)
    out = []
    for pat, name in [(r"\bIMB\b", "IMB"), (r"\bBB\b", "BB"), (r"\bOB\b", "OB"),
                      (r"FVG", "FVG"), (r"discount|折价", "Discount"), (r"premium", "Premium")]:
        if re.search(pat, txt):
            out.append({"type": name, "timeframes": frames or None, "source": "context/entryReason"})
    return out or None


def build_tags(d):
    tags = [{"group": "Direction", "value": d["direction"].capitalize()}]
    for step in (d["setup"]["flow"] or []):
        tags.append({"group": "Setup Step", "value": step})
    if d["entryModel"]["category"]:
        tags.append({"group": "Entry Model", "value": d["entryModel"]["category"]})
    for p in (d["poi"] or []):
        tags.append({"group": "POI", "value": p["type"]})
    if d["resultStatus"]:
        tags.append({"group": "Result", "value": d["resultStatus"].capitalize()})
    if d["plannedRRLow"] is not None and d["plannedRRHigh"] is not None:
        if d["plannedRRHigh"] < 1:
            tags.append({"group": "Risk", "value": "Low RR"})
    return tags


EXPECTED = ["entry", "stopLoss", "targets", "plannedRR", "actualR", "entryTime", "exitTime",
            "context", "liquidity", "structure", "poi", "displacement", "mae", "mfe", "fees"]


def completeness(d):
    filled, missing = 0, []
    for f in EXPECTED:
        v = d.get(f)
        if isinstance(v, dict):
            v = v.get("raw") or v.get("price")
        if v not in (None, [], {}, "", 0):
            filled += 1
        else:
            missing.append(f)
    return {"percent": round(filled / len(EXPECTED) * 100), "missing": missing,
            "total": len(EXPECTED), "filled": filled}


# ---------------------------------------------------------------- 图片导出
def export_images(zf, trades, unresolved):
    os.makedirs(IMAGES, exist_ok=True)
    written = []
    for t in trades:
        for im in t["images"]:
            src = f"word/media/{im['media']}"
            dst = os.path.join(ROOT, im["file"])
            with open(dst, "wb") as f:
                f.write(zf.read(src))
            w, h = png_size(dst)
            im["width"], im["height"] = w, h
            im["sha256"] = hashlib.sha256(open(dst, "rb").read()).hexdigest()[:16]
            im["url"] = im["file"]
            im["caption"] = "文档内嵌交易图（原图，未标注 Timeframe）"
            written.append(im["file"])
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="用 cache/doc.docx，不联网")
    args = ap.parse_args()

    raw = load_docx(args.offline)
    digest = hashlib.sha256(raw).hexdigest()
    blocks, zf = docx_blocks(raw)
    doc = parse(blocks, zf)
    exported = export_images(zf, doc["trades"], doc["unresolvedImages"])
    doc["meta"]["sourceVersion"] = digest[:16]
    doc["meta"]["sourceBytes"] = len(raw)
    doc["meta"]["blocks"] = len(blocks)
    doc["meta"]["unresolvedImageCount"] = len(doc["unresolvedImages"])
    doc["meta"]["exportedImages"] = exported

    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "source.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    print(f"[OK] 解析完成：{len(doc['weeks'])} 周 / {len(doc['trades'])} 笔交易 / "
          f"{len(exported)} 张图 / 未绑定图 {len(doc['unresolvedImages'])}")
    for w in doc["weeks"]:
        st = w["stats"]
        print(f"  {w['label']} {w['start']}~{w['end']} "
              f"trades={st['closed']} W/L={st['wins']}/{st['losses']} "
              f"knownNetR={st['knownNetR']}")
    for t in doc["trades"]:
        print(f"  {t['id']:38s} {str(t['resultStatus']):5s} R={t['actualR']} "
              f"RR={t['plannedRR']} imgs={len(t['images'])} "
              f"completeness={t['dataCompleteness']['percent']}%")
    print(f"[OK] 写出 data/source.json（sourceVersion={digest[:16]}）")
    return doc


if __name__ == "__main__":
    main()
