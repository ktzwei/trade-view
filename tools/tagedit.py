#!/usr/bin/env python3
"""手填结构化层编辑器（需求 §35 / §37 / §5 的落地工具）。

为什么需要它：自动识别只能给「建议」（§37），原始交易数据不能改；
真正的结构化值需要人来确认或填写。本工具把确认结果写进 data/manual/，
build 时手填层优先级最高，且永远标记来源 = manual（可追溯）。

用法：
    python3 tools/tagedit.py                # 启动本地编辑界面 http://127.0.0.1:8787
    python3 tools/tagedit.py --port 9000
    python3 tools/tagedit.py set 2026-09-13-ethusdt-long-01 ruleCompliance="Fully Compliant"
    python3 tools/tagedit.py build           # 只重建站点数据

写出的文件：
    data/manual/<tradeId>.json   {"fields": {"htfBias": "Bullish", ...}, "notes": "..."}
    data/manual/_weeks.json      {"第1周": {"didWell": "...", "mainProblem": "...", "nextFocus": "..."}}
"""
from __future__ import annotations

import argparse
import html
import json
import subprocess
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "parser"))
from schema import ALL_TF, FIELDS, MISTAKE_GROUPS, SCHEMA_VERSION  # noqa: E402

MANUAL = ROOT / "data" / "manual"
TRADES = ROOT / "data" / "trades.json"
WEEK_KEYS = [("didWell", "This Week I Did Well（哪里做得对）"),
             ("mainProblem", "Main Problem（本周主要问题）"),
             ("nextFocus", "Next Week Focus（下周重点改进）")]
# 数值字段（需求 §13 Protected Price、§19 MAE/MFE）+ 旧的手填数值项；从 schema 派生，避免两处维护
NUMERIC = {f["key"] for f in FIELDS if f.get("kind") == "number"} | {
    "plannedRR", "confidence", "plannedEntry", "plannedSL"}
# 需求 §24：截图四类分类（写进 data/manual/_images.json，原图不动）
IMG_KINDS = ["HTF Context", "LTF Entry", "After Trade", "Review Screen"]
IMAGES = MANUAL / "_images.json"
CHECKLIST = {
    "Must Have": ["htfBias", "htfPOIType", "invalidationLogic", "plannedRR"],
    "Confirmation": ["liquiditySweep", "displacementQuality", "brokenStructure", "entryTriggerType"],
    "Avoid": ["mistakes"],
}


# ---------------------------------------------------------------- 读写
def load_json(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def save_manual(tid, fields, notes=""):
    MANUAL.mkdir(parents=True, exist_ok=True)
    path = MANUAL / f"{tid}.json"
    cur = load_json(path, {})
    cur["tradeId"] = tid
    cur["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    cur["fields"] = fields
    if notes:
        cur["notes"] = notes
    path.write_text(json.dumps(cur, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def effective(t, key):
    f = (t.get("fields") or {}).get(key) or {}
    return f.get("value"), f.get("source"), f.get("confirmed")


def source_badge(src, confirmed):
    if src == "manual" or confirmed:
        return "手填/已确认"
    if src == "doc:label":
        return "文档记录"
    if src == "doc:keyword":
        return "自动识别·待确认"
    if src == "derived:checklist":
        return "清单派生·待确认"
    return src or "文档没写"


def rebuild():
    out = []
    for script in ("parser/parse_gdoc.py", "parser/build.py"):
        r = subprocess.run([sys.executable, script], cwd=str(ROOT), capture_output=True, text=True)
        out.append(f"$ python3 {script}\n{r.stdout.strip()}\n{r.stderr.strip()}")
        if r.returncode != 0:
            out.append(f"[失败] {script} 退出码 {r.returncode}")
            break
    return "\n".join(out)


# ---------------------------------------------------------------- HTML
CSS = """
:root{--bg:#0e1116;--panel:#161b22;--line:#252c36;--fg:#d7dee8;--dim:#8b98a8;
--ok:#3fb950;--bad:#f85149;--warn:#d29922;--auto:#58a6ff;--manual:#a371f7}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:14px/1.55 -apple-system,BlinkMacSystemFont,"Helvetica Neue",sans-serif}
a{color:var(--auto);text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:1080px;margin:0 auto;padding:20px 16px 80px}
h1{font-size:19px;margin:0 0 4px}h2{font-size:15px;margin:22px 0 8px;color:#e6edf3}
.sub{color:var(--dim);font-size:12px;margin-bottom:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin-bottom:12px}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{color:var(--dim);font-weight:600;font-size:12px}
.badge{display:inline-block;padding:1px 7px;border-radius:10px;font-size:11px;border:1px solid var(--line);color:var(--dim)}
.b-manual{color:var(--manual);border-color:#4c3a7a}.b-auto{color:var(--auto);border-color:#1f4a7a}
.b-doc{color:var(--ok);border-color:#1d4d2b}
.fld{border-bottom:1px solid var(--line);padding:9px 0;display:grid;grid-template-columns:250px 1fr;gap:10px}
.fld:last-child{border-bottom:0}
.lbl{font-size:12.5px}.lbl b{font-weight:600}
.ev{color:var(--dim);font-size:11.5px;margin-top:3px}
input[type=text],input[type=number],select,textarea{background:#0b0e13;color:var(--fg);
border:1px solid var(--line);border-radius:6px;padding:5px 8px;font:13px/1.4 inherit;width:100%}
select[multiple]{height:auto;min-height:74px}
.chk{display:inline-block;margin:0 10px 4px 0;font-size:12.5px;color:var(--fg)}
.chk input{margin-right:4px}
button{background:#21262d;color:var(--fg);border:1px solid var(--line);border-radius:6px;
padding:7px 14px;font:13px inherit;cursor:pointer}
button.p{background:#1f6feb;border-color:#1f6feb;color:#fff}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
pre{background:#0b0e13;border:1px solid var(--line);border-radius:6px;padding:10px;overflow:auto;font-size:12px}
details{margin:6px 0}summary{cursor:pointer;color:var(--dim);font-size:13px}
.nav{color:var(--dim);font-size:12px;margin-bottom:10px}
"""


def page(title, body):
    return (f"<!doctype html><html lang=zh><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body>"
            f"<div class=wrap>{body}</div></body></html>")


def badge_for(src, confirmed):
    txt = source_badge(src, confirmed)
    cls = "b-manual" if "手填" in txt else ("b-doc" if txt.startswith("文档") else "b-auto")
    return f"<span class='badge {cls}'>{html.escape(txt)}</span>"


def control(t, f):
    key, opts, multi = f["key"], f.get("options") or [], bool(f.get("multi"))
    val, src, conf = effective(t, key)
    vals = val if isinstance(val, list) else ([] if val is None else [val])
    name = f"f__{key}"
    if multi and opts:
        chks = "".join(
            f"<label class=chk><input type=checkbox name='{name}' value='{html.escape(o)}'"
            f"{' checked' if o in vals else ''}>{html.escape(o)}</label>" for o in opts)
        ctl = chks
    elif opts and not multi:
        sel = "".join(f"<option value='{html.escape(o)}'{' selected' if o in vals else ''}>{html.escape(o)}</option>"
                      for o in [""] + opts)
        ctl = f"<select name='{name}'>{sel}</select>"
    else:
        typ = "number" if key in NUMERIC else "text"
        step = " step='0.01'" if typ == "number" else ""
        ctl = f"<input type={typ}{step} name='{name}' value='{html.escape('' if val is None else str(val))}'>"
    return (f"<div class=fld><div class=lbl><b>{html.escape(str(f['label']))}</b><br>"
            f"{badge_for(src, conf)}<div class=ev>{html.escape(str(f.get('note') or ''))}</div></div>"
            f"<div>{ctl}<div class=ev>当前值：{html.escape(json.dumps(val, ensure_ascii=False))}"
            f"{(' ｜ 原标题：' + html.escape(str((t.get('fields', {}).get(key) or {}).get('evidence'))[:160])) if (t.get('fields', {}).get(key) or {}).get('evidence') else ''}"
            f"</div><label class=chk style='margin-top:5px'><input type=checkbox name='c__{key}' value=1>"
            f"确认这个值</label></div></div>")


def index_page(trades):
    rows = []
    for t in trades:
        st = t.get("fieldStats") or {}
        q = (t.get("quality") or {})
        rows.append(
            "<tr>"
            f"<td><a href='/t/{urllib.parse.quote(t['id'])}'>{html.escape(t['id'])}</a><br>"
            f"<span class=badge>{html.escape(str(t.get('symbolLabel') or ''))}</span></td>"
            f"<td>{html.escape(str(t.get('date') or ''))}</td>"
            f"<td>{html.escape(str(t.get('direction') or ''))}</td>"
            f"<td>{html.escape(str(t.get('actualR') if t.get('actualR') is not None else '未记录'))}</td>"
            f"<td>{html.escape(str(q.get('value') or '未判定'))}"
            f"<div class=ev>{html.escape(str(q.get('basis') or ''))}</div></td>"
            f"<td>{st.get('confirmed', 0)} 已确认 / {st.get('auto', 0)} 待确认</td>"
            "</tr>")
    body = ("<h1>交易复盘 · 手填结构化层</h1>"
            f"<div class=sub>schema v{SCHEMA_VERSION} ｜ 自动识别只是建议（需求 §37），确认后写入 "
            f"<code>data/manual/</code>，手填层优先级最高。</div>"
            "<div class=card><div class=row>"
            "<a class=p href='/images' style='text-decoration:none'>截图分类（§24）</a> "
            "<a class=p href='/weeks' style='text-decoration:none'>周复盘（§32）</a> "
            "<form method=post action='/build' style='margin:0'>"
            "<button class=p>保存后重建站点数据</button></form>"
            f"<span class=sub style='margin:0'>手动确认 {sum(1 for t in trades if (t.get('fieldStats') or {}).get('confirmed'))}"
            f" / {len(trades)} 笔</span></div></div>"
            "<table><tr><th>交易</th><th>日期</th><th>方向</th><th>实际 R</th><th>Trade Quality</th>"
            "<th>字段</th></tr>" + "".join(rows) + "</table>"
            "<h2>周复盘手填（需求 §32）</h2><div class=card>"
            "<a href='/weeks'>→ 打开周复盘填写页</a></div>")
    return page("交易复盘 · 手填", body)


def trade_page(t):
    groups = {}
    for f in FIELDS:
        groups.setdefault(f["group"], []).append(f)
    parts = [f"<div class=nav><a href='/'>← 全部交易</a></div>",
             f"<h1>{html.escape(t['id'])}</h1>",
             f"<div class=sub>{html.escape(str(t.get('symbolLabel') or ''))} · "
             f"{html.escape(str(t.get('date') or ''))} · {html.escape(str(t.get('direction') or ''))} · "
             f"结果 {html.escape(str(t.get('resultStatus') or '未结束'))} · "
             f"实际 R {html.escape(str(t.get('actualR') if t.get('actualR') is not None else '未记录'))}</div>"]
    cv = t.get("complianceV2") or {}
    if cv.get("derivedCompliance"):
        dc = cv["derivedCompliance"]
        parts.append(f"<div class=card>派生合规度：<b>{html.escape(str(dc.get('value') or '不下结论'))}</b>"
                     f"<div class=ev>{html.escape(str(dc.get('basis') or ''))}</div></div>")
    parts.append("<form method=post>")
    for g, fs in groups.items():
        core = [f for f in fs if f.get("tier") != "advanced"]
        adv = [f for f in fs if f.get("tier") == "advanced"]
        parts.append(f"<h2>{html.escape(g)}</h2><div class=card>")
        parts += [control(t, f) for f in core]
        if adv:
            parts.append("<details><summary>Advanced / More Details（"
                         + str(len(adv)) + " 项，需求 §35）</summary>"
                         + "".join(control(t, f) for f in adv) + "</details>")
        parts.append("</div>")
    parts.append("<div class=card><div class=lbl><b>备注（Notes）</b></div>"
                 "<textarea name='notes' rows=3></textarea></div>")
    parts.append("<div class=card><button class=p type=submit>保存这一笔</button> "
                 "<span class=sub style='margin:0'>保存只写 data/manual/，不回写 Google Docs</span></div></form>")
    return page(t["id"], "".join(parts))


def weeks_page(weeks, manual_weeks):
    parts = ["<div class=nav><a href='/'>← 全部交易</a></div><h1>周复盘手填（需求 §32）</h1>",
             "<form method=post action='/weeks'>"]
    for w in weeks:
        m = manual_weeks.get(w["label"]) or {}
        parts.append(f"<h2>{html.escape(w['label'])} <span class=sub>"
                     f"{html.escape(str(w.get('start') or ''))} ~ {html.escape(str(w.get('end') or ''))} ｜ "
                     f"{w.get('trades')} 笔 ｜ 净 R {html.escape(str(w.get('netR')))} ｜ "
                     f"Expectancy {html.escape(str(w.get('expectancy')))}</span></h2><div class=card>")
        for k, label in WEEK_KEYS:
            parts.append(f"<div class=fld><div class=lbl><b>{html.escape(label)}</b></div>"
                         f"<div><textarea name='w__{html.escape(w['label'])}__{k}' rows=2>"
                         f"{html.escape(str(m.get(k) or ''))}</textarea></div></div>")
        parts.append("</div>")
    parts.append("<div class=card><button class=p type=submit>保存周复盘</button></div></form>")
    return page("周复盘", "".join(parts))


# ---------------------------------------------------------------- handlers
def images_page(trades):
    """需求 §24：截图分类（HTF Context / LTF Entry / After Trade / Review Screen + Timeframe）。

    分类只写 data/manual/_images.json，原图与原始数据不动（§37）。
    """
    data = load_json(IMAGES, {})
    total = sum(len(t.get("images") or []) for t in trades)
    done = sum(len(v or {}) for v in data.values())
    parts = [f"<div class=nav><a href='/'>← 全部交易</a></div>",
             "<h1>截图分类 · 手填层</h1>",
             "<div class=sub>需求 §24：每张图分四类，并标周期。分类写进 <code>data/manual/_images.json</code>，"
             "原图与 Google Docs 数据都不动。</div>",
             f"<div class=card>共 {total} 张图 ｜ 已分类 {done} 张 ｜ 未分类 {max(0, total - done)} 张</div>"]
    for t in trades:
        imgs = t.get("images") or []
        if not imgs:
            continue
        cur = data.get(t["id"]) or {}
        parts.append(f"<form method=post action='/images'><h2>{html.escape(t['id'])} "
                     f"<span class=badge>{html.escape(str(t.get('symbolLabel') or ''))}</span></h2><div class=card>")
        for im in imgs:
            key = str(im.get("sha256") or im.get("order"))
            m = cur.get(key) or {}
            opts = "".join(f"<option value='{html.escape(o)}'"
                           f"{' selected' if m.get('type') == o else ''}>{html.escape(o)}</option>"
                           for o in [""] + IMG_KINDS)
            tfs = "".join(f"<option value='{html.escape(v)}'"
                          f"{' selected' if m.get('timeframe') == v else ''}>{html.escape(v)}</option>"
                          for v in [""] + list(ALL_TF))
            path = urllib.parse.quote(str(im.get("file") or im.get("path") or ""))
            parts.append(
                f"<div class=fld><div class=lbl><b>图 {im.get('order')}</b> "
                f"<span class=badge>{html.escape(str(im.get('width')))}×{html.escape(str(im.get('height')))}</span>"
                f"<div class=ev>sha {html.escape(key)} ｜ {html.escape(str(im.get('file') or ''))}</div>"
                f"<a href='/{path}' target=_blank><img src='/{path}' "
                f"style='max-width:280px;margin-top:6px;border:1px solid #30363d;border-radius:6px'></a></div>"
                f"<div><input type=hidden name='t__{html.escape(key)}' value='{html.escape(t['id'])}'>"
                f"<select name='k__{html.escape(key)}'>{opts}</select> "
                f"<select name='tf__{html.escape(key)}'>{tfs}</select>"
                f"<input type=text name='cap__{html.escape(key)}' placeholder='说明（可留空）' "
                f"value='{html.escape(str(m.get('caption') or ''))}' style='width:300px;margin-top:6px'>"
                f"<div class=ev>当前：{html.escape(json.dumps(m, ensure_ascii=False))}</div></div></div>")
        parts.append("<div class=row><button class=p type=submit>保存本笔图片分类</button>"
                     "<span class=sub style='margin:0'>保存后自动重建站点数据</span></div></div></form>")
    return page("截图分类", "".join(parts))


class H(BaseHTTPRequestHandler):
    trades = []
    weeks = []

    def log_message(self, *a):        # 本地工具，别刷屏
        pass

    def send_html(self, s, code=200):
        b = s.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def send_bytes(self, data, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path.startswith("/images/"):
            # 只读放行仓库里的 images/（本地标注看图用，越界一律 404）
            rel = urllib.parse.unquote(u.path.lstrip("/"))
            fp = (ROOT / rel).resolve()
            if str(fp).startswith(str((ROOT / "images").resolve())) and fp.is_file():
                ct = "image/png" if fp.suffix.lower() == ".png" else (
                    "image/jpeg" if fp.suffix.lower() in (".jpg", ".jpeg") else "application/octet-stream")
                return self.send_bytes(fp.read_bytes(), ct)
            return self.send_html(page("404", "<h1>404</h1>"), 404)
        if u.path == "/images":
            return self.send_html(images_page(self.trades))
        if u.path == "/":
            return self.send_html(index_page(self.trades))
        if u.path == "/weeks":
            return self.send_html(weeks_page(self.weeks, load_json(MANUAL / "_weeks.json", {})))
        if u.path.startswith("/t/"):
            tid = urllib.parse.unquote(u.path[3:])
            t = next((x for x in self.trades if x["id"] == tid), None)
            if not t:
                return self.send_html(page("404", "<h1>没有这笔交易</h1>"), 404)
            return self.send_html(trade_page(t))
        return self.send_html(page("404", "<h1>404</h1>"), 404)

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        qs = urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8"), keep_blank_values=True)
        if u.path == "/build":
            out = rebuild()
            self.send_html(page("重建", f"<div class=nav><a href='/'>← 返回</a></div><h1>重建结果</h1>"
                                      f"<pre>{html.escape(out)}</pre>"))
            return
        if u.path == "/images":
            data = load_json(IMAGES, {})
            for k, v in qs.items():
                if not k.startswith("k__"):
                    continue
                key = k[3:]
                tid = (qs.get(f"t__{key}") or [""])[0].strip()
                if not tid:
                    continue
                kind = (v[0] or "").strip()
                tf = (qs.get(f"tf__{key}") or [""])[0].strip()
                cap = (qs.get(f"cap__{key}") or [""])[0].strip()
                if not (kind or tf or cap):
                    data.get(tid, {}).pop(key, None)   # 三项全空 = 撤销这张图的分类
                    continue
                data.setdefault(tid, {})[key] = {"type": kind or None,
                                                 "timeframe": tf or None,
                                                 "caption": cap or None}
            MANUAL.mkdir(parents=True, exist_ok=True)
            IMAGES.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            out = rebuild()
            return self.send_html(page("图片分类已保存",
                                      f"<div class=nav><a href='/images'>← 返回截图分类</a></div>"
                                      f"<h1>已保存</h1><pre>{html.escape(out)}</pre>"))
        if u.path == "/weeks":
            data = load_json(MANUAL / "_weeks.json", {})
            for k, v in qs.items():
                if not k.startswith("w__"):
                    continue
                _, label, field = k.split("__", 2)
                data.setdefault(label, {})[field] = (v[0] or "").strip() or None
            MANUAL.mkdir(parents=True, exist_ok=True)
            (MANUAL / "_weeks.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                                               encoding="utf-8")
            out = rebuild()
            return self.send_html(page("周复盘已保存", f"<div class=nav><a href='/'>← 返回</a></div>"
                                                       f"<h1>已保存并重建</h1><pre>{html.escape(out)}</pre>"))
        if u.path.startswith("/t/"):
            tid = urllib.parse.unquote(u.path[3:])
            t = next((x for x in self.trades if x["id"] == tid), None)
            if not t:
                return self.send_html(page("404", "<h1>没有这笔交易</h1>"), 404)
            fields = dict((load_json(MANUAL / f"{tid}.json", {}) or {}).get("fields") or {})
            bad = []
            for f in FIELDS:
                key, opts = f["key"], f.get("options") or []
                multi, conf = bool(f.get("multi")), bool(qs.get(f"c__{key}"))
                cur, src, _ = effective(t, key)
                if multi:
                    vals = qs.get(f"f__{key}", [])
                    newval = [v for v in vals if v]
                else:
                    raw = (qs.get(f"f__{key}") or [""])[0].strip()
                    if not raw:
                        newval = None
                    elif key in NUMERIC:
                        try:
                            newval = float(raw)
                        except ValueError:
                            bad.append(f"{key}='{raw}' 不是数字，已忽略")
                            continue
                    else:
                        newval = raw
                        if opts and raw not in opts:
                            bad.append(f"{key}='{raw}' 不在词表里，已忽略（词表见 schema.py）")
                            continue
                changed = newval != (cur if isinstance(cur, list) or newval is not None or cur is not None else None)
                if newval in (None, [], ""):
                    if key in fields:
                        fields[key] = None            # 显式清空 → 手填空值 = 删掉自动识别结果
                    continue
                if changed or conf:
                    fields[key] = newval
            fields = {k: v for k, v in fields.items() if v is not None or k in fields}
            save_manual(tid, fields, (qs.get("notes") or [""])[0].strip())
            out = rebuild()
            msg = ("<div class=card style='border-color:#d29922'>以下输入被忽略：" +
                   html.escape("；".join(bad)) + "</div>") if bad else ""
            return self.send_html(page("已保存", f"<div class=nav><a href='/'>← 返回</a></div>"
                                                 f"<h1>已保存 {html.escape(tid)}</h1>{msg}"
                                                 f"<pre>{html.escape(out)}</pre>"))
        return self.send_html(page("404", "<h1>404</h1>"), 404)


def load_state():
    data = load_json(TRADES, {"trades": [], "weeks": []})
    H.trades = data.get("trades", [])
    H.weeks = (data.get("v2") or {}).get("weekly") or data.get("weeks", [])
    if not H.weeks:            # v2 还没有时退回原始周数据
        H.weeks = [dict(w, trades=len(w.get("tradeIds", [])), netR=None, expectancy=None)
                   for w in data.get("weeks", [])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="serve", choices=["serve", "build", "set"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--port", type=int, default=8787)
    a = ap.parse_args()
    if a.cmd == "build":
        print(rebuild())
        return
    if a.cmd == "set":
        if len(a.args) < 2:
            sys.exit("用法: tagedit.py set <tradeId> key=value [key=value ...]")
        tid, fields = a.args[0], dict((load_json(MANUAL / f"{a.args[0]}.json", {}) or {}).get("fields") or {})
        for kv in a.args[1:]:
            k, _, v = kv.partition("=")
            fields[k] = None if v.strip() == "" else v.strip()
        fields = {k: v for k, v in fields.items() if v is not None}
        print("写入", save_manual(tid, fields))
        print(rebuild())
        return
    load_state()
    print(f"[tag] 手填层编辑器 → http://127.0.0.1:{a.port}  （{len(H.trades)} 笔交易）")
    HTTPServer(("127.0.0.1", a.port), H).serve_forever()


if __name__ == "__main__":
    main()
