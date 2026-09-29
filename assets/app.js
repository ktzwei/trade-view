/* Trading Review — 前端（零依赖，静态 JSON 驱动）
   设计原则：一屏只回答三个问题 —— 这笔为什么做 / 结果怎样 / 下次怎么改。
   其余原始字段一律折叠进「原始记录」，不抢戏，但一个都不丢。 */
(() => {
  const state = { range: 'week', q: '', filters: {}, data: null };
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (s) => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
  const NR = '<span class="nr">未记录</span>';
  const nr = (v, fmt) => {
    if (v === null || v === undefined || v === '') return NR;
    if (typeof v === 'object') return esc(v.raw || '');   // MAE/MFE 这类 {raw, r, price}
    return fmt ? fmt(v) : esc(v);
  };
  const num = (v, d = 2) => (v === null || v === undefined ? NR : Number(v).toFixed(d));
  const rTxt = (v) => (v === null || v === undefined ? NR
    : `<span class="${v > 0 ? 'rpos' : v < 0 ? 'rneg' : 'rzero'}">${v > 0 ? '+' : ''}${Number(v).toFixed(2)}R</span>`);
  const pct = (v) => (v === null || v === undefined ? NR : Math.round(v * 100) + '%');
  const short = (s, n = 100) => {
    const x = String(s || '').replace(/\s+/g, ' ').trim();
    return x.length > n ? x.slice(0, n) + '…' : x;
  };
  const dirChip = (d) => d === 'long' ? '<span class="chip long">LONG</span>'
    : d === 'short' ? '<span class="chip short">SHORT</span>' : `<span class="chip">${esc(d || '方向未知')}</span>`;
  const dirWord = (d) => d === 'long' ? '多' : d === 'short' ? '空' : '方向未知';
  const resChip = (t) => {
    const s = t.resultStatus;
    // 未结束的（挂单 / 持仓中）用文档标题里的结果词，例如「未成交」
    const label = { win: 'Win', loss: 'Loss', be: 'BE' }[s]
      || (t.headingResult ? short(t.headingResult, 8) : '未记录');
    return `<span class="chip ${s === 'win' ? 'win' : s === 'loss' ? 'loss' : s === 'be' ? 'be' : 'ghost'}">${esc(label)}</span>`;
  };
  const dateOf = (t) => String(t.entryTime || t.entryDate || '').slice(5, 10)
    || (t.exitDate ? String(t.exitDate).slice(5, 10) + ' 平' : '开仓未记录');
  const img = (p) => p;

  /* ================= v3 · 结构化复盘层（需求 §2 / §5 / §7–§35 / §41） ================= */
  const arr = (x) => (Array.isArray(x) ? x : (x === null || x === undefined ? [] : [x]));
  const V2 = () => state.data.v2 || {};
  const V2W = (label) => (V2().weekly || []).find((w) => w.label === label) || null;
  const FBYK = () => { const m = {}; ((state.data.schema || {}).fields || []).forEach((f) => { m[f.key] = f; }); return m; };
  const LBL = (k) => (FBYK()[k] || {}).label || k;
  const fv = (t, k) => (t.fields || {})[k] || null;
  const valTxt = (f) => {
    if (!f) return null;
    const v = f.value;
    if (v === null || v === undefined || v === '') return null;
    if (Array.isArray(v)) return v.filter((x) => x !== null && x !== '').join(' / ') || null;
    return String(v);
  };
  const srcBadge = (f) => {
    const src = (f || {}).source || '';
    if (!src) return '';
    if (src === 'manual') return '<span class="srcb manual">手填·已确认</span>';
    if (src.indexOf('doc') === 0) return '<span class="srcb doc">文档记录</span>';
    if (src === 'derived') return '<span class="srcb">派生</span>';
    return '<span class="srcb auto">自动识别·待确认</span>';
  };
  const cfield = (t, k) => {
    const f = fv(t, k);
    if (!FBYK()[k]) return '';
    const v = valTxt(f);
    const tf = f && f.tf && f.tf.length ? `<span class="srcb">${esc(f.tf.join('/'))}</span>` : '';
    const spec = FBYK()[k] || {};
    const unit = spec.kind === 'number' && spec.unit ? `<span class="srcb">单位 ${esc(spec.unit)}</span>` : '';
    return `<div class="cfield"><div class="k">${esc(LBL(k))}${tf}</div>
      <div class="v">${v ? esc(v) : NR}${unit}${srcBadge(f)}</div>
      ${f && f.evidence ? `<div class="ev">“${esc(short(f.evidence, 92))}”</div>` : ''}</div>`;
  };
  const CHAIN = [
    ['① HTF Context 市场环境', ['htfBias', 'biasSourceTF', 'marketCondition', 'htfStructureKind', 'htfStructureTF'], '先回答：市场在哪里、大方向是什么。'],
    ['② HTF Liquidity 流动性', ['liquidityType', 'liquidityTF', 'liquiditySweep', 'sweepQuality', 'sweepTF'], '流动性在哪里被扫 —— 不要求每笔都有 Sweep。'],
    ['③ HTF POI 兴趣点', ['htfPOIType', 'htfPOITF', 'poiConfluence', 'ltfPOIType', 'ltfPOITF'], 'HTF POI 与 LTF Entry POI 是两个不同概念。'],
    ['④ LTF Reaction 反应', ['reaction', 'reactionType', 'reactionTF'], '到达 POI 后市场有没有反应。'],
    ['⑤ Displacement 位移', ['displacementQuality', 'displacementTF'], '有没有位移、强不强、在哪一级周期。'],
    ['⑥ Structure Shift 结构改变', ['structureShiftType', 'structureShiftTF', 'brokenStructure', 'protectedStructure', 'protectedTF', 'protectedPrice', 'invalidationLogic', 'invalidationTF'], '要能区分 Internal Structure 与 Key / Protected Structure。'],
    ['⑦ Entry 入场', ['entryMode', 'limitStyle', 'entryTriggerType', 'entryTriggerTF'], 'Limit 挂单 / LTF Confirmation / Market 三选一，统计口径靠它。'],
    ['⑧ Target 目标', ['targetLevel'], '目标按结构层级记录。'],
    ['⑨ Trade Management 持仓管理', ['managementStyle', 'movedSL', 'earlyExit', 'reducedPosition', 'addedPosition']],
    ['⑩ Result 结果', ['mae', 'mfe', 'confidence'], 'MAE / MFE 一律记成 R。'],
    ['⑪ Review 复盘', ['ruleCompliance', 'shouldTake', 'tradeQuality', 'mistakes']],
  ];
  const IMG_KIND_WORD = { 'HTF Context': 'HTF 环境', 'LTF Entry': 'LTF 入场', 'After Trade': '事后全图', 'Review Screen': '复盘屏' };
  const imgKind = (i) => (i.type ? `${i.type}${i.timeframe ? ' · ' + i.timeframe : ''}` : '未分类');
  function imgStrip(imgs, t) {
    const counts = {};
    imgs.forEach((i) => { const k = i.type || '未分类'; counts[k] = (counts[k] || 0) + 1; });
    const parts = Object.keys(counts).map((k) => `<span class="chip">${esc(IMG_KIND_WORD[k] || k)} × ${counts[k]}</span>`);
    const un = imgs.filter((i) => !i.type).length;
    return `${parts.join(' ')} <span class="muted">需求 §24 四类（HTF Context / LTF Entry / After Trade / Review Screen）在本地编辑器 <b>截图分类</b> 页勾选，原图不改。</span>`
      + (un ? ` <span class="muted">还有 ${un} 张没标。</span>` : '');
  }
  function chainBlock(t) {
    const used = CHAIN.flatMap((c) => c[1]);
    const steps = CHAIN.map(([title, keys, note]) => {
      const body = keys.map((k) => cfield(t, k)).join('');
      const filled = keys.some((k) => valTxt(fv(t, k)));
      return `<div class="chainstep${filled ? '' : ' bare'}"><h4>${esc(title)}${filled ? '' : ' <span class="muted">未记录</span>'}</h4>
        ${note ? `<div class="small muted">${esc(note)}</div>` : ''}<div class="cfields">${body}</div></div>`;
    }).join('');
    const adv = Object.keys(t.fields || {}).filter((k) => !used.includes(k) && valTxt(fv(t, k)));
    const advHtml = adv.length ? `<details class="fold"><summary>Advanced / 其他字段（${adv.length}）</summary>
      <div class="cfields" style="margin-top:8px">${adv.map((k) => cfield(t, k)).join('')}</div></details>` : '';
    const fs = t.fieldStats || { confirmed: 0, auto: 0, total: 0 };
    return `<div class="sec"><h2>结构化复盘链 <span class="hint">§5 标准链 · ${fs.confirmed} 项已确认 / ${fs.auto} 项自动识别 / 共 ${fs.total} 项</span></h2>
      <div class="callout small">自动识别只出「建议」，不改原始数据；显示「自动识别·待确认」的项需要在本地编辑器里点确认才算数。缺的字段一律显示未记录，不猜。</div>
      <div class="chain">${steps}</div>${advHtml}</div>`;
  }
  function checklistBlock(t) {
    const c = t.complianceV2 || {};
    const g = c.groups || {};
    const ic = { '✓': 'pass', '✕': 'fail', '未记录': 'unknown' };
    const panel = (name, items, note) => `<div class="panel"><h3>${esc(name)} <span class="hint small">${items.filter((i) => i.status === '✓').length}/${items.length}</span></h3>
      ${note ? `<div class="small muted" style="margin-bottom:6px">${esc(note)}</div>` : ''}
      <div class="check">${items.map((i) => `<div class="row ${ic[i.status] || 'unknown'}"><span class="ic">${i.status === '✓' ? '✔' : i.status === '✕' ? '✘' : '?'}</span>
        <div class="lab"><b>${esc(i.text)}</b> <span class="small muted">${esc(i.status === '✓' ? '已记录' : i.status === '✕' ? '违反' : '未记录')}</span>
        <div class="ev">${i.value ? esc(Array.isArray(i.value) ? i.value.join(' / ') : i.value) : '文档里没有这条记录'}${i.source ? ` · ${esc(i.source)}` : ''}</div></div></div>`).join('')}</div></div>`;
    const dev = c.compliance || null;
    const decided = dev && dev !== '未记录';
    const sug = t.mistakeSuggestions || { suggestions: [], unmapped: [] };
    return `<div class="sec"><h2>Rule Checklist <span class="hint">§21 / §34 规则联动</span></h2>
      <div class="callout ${dev === 'Major Violation' ? 'warn' : ''}">Rule Compliance：<b>${esc(dev || '未记录')}</b>
        ${decided ? `<span class="small muted">（由下方 Must Have 未过的项派生，不是 AI 猜的）</span>`
          : '<span class="small muted">（三桶清单里有「未记录」项，因此不下结论 —— 要么补记录，要么在编辑器里直接标 Rule Compliance）</span>'}</div>
      <div class="three">
        ${panel('Must Have 必须有', g['Must Have'] || [], '缺一项就不该进场。')}
        ${panel('Confirmation 确认条件', g['Confirmation'] || [], '不是每笔都要全有，但要有记录才能统计。')}
        ${panel('Avoid 避免', g['Avoid'] || [], '命中即执行问题。')}
      </div>
      ${(sug.suggestions || []).length || (sug.unmapped || []).length ? `<div class="callout small">错误标签<b>建议</b>（未确认，不会写进统计）：${(sug.suggestions || []).map((x) => `<span class="chip warn">${esc(x.tag || x)}</span>`).join(' ')}${(sug.unmapped || []).map((x) => `<span class="chip ghost">${esc(x)}</span>`).join(' ')}
        <div class="muted" style="margin-top:4px">在本地编辑器确认后才计入 Mistake 统计（§37：AI 不改原始数据）。</div></div>` : ''}</div>`;
  }
  function plannedActualBlock(t) {
    const pa = t.plannedVsActual;
    if (!pa) return '';
    const rec = pa.recorded || {};
    const cell = (k, ok, v, cls) => `<div><div class="k">${k}${ok ? '' : ' <span class="srcb">未记录</span>'}</div><div class="v ${cls || ''}">${v}</div></div>`;
    const planTp = arr(pa.planned.tp).join(' / ') || null;
    const dev = arr(pa.deviations);
    return `<div class="sec"><h2>Planned vs Actual <span class="hint">§16 策略问题 vs 执行问题</span></h2>
      <div class="panel"><div class="kv kv2">
        ${cell('计划 Entry', rec.plannedEntry, pa.planned.entry === null ? NR : num(pa.planned.entry))}
        ${cell('计划 SL', rec.plannedSL, pa.planned.sl === null ? NR : num(pa.planned.sl))}
        ${cell('计划 TP', !!planTp, planTp ? esc(planTp) : NR)}
        ${cell('计划 RR', rec.plannedRR, pa.planned.rr === null ? NR : esc(pa.planned.rr) + 'R')}
        ${cell('实际 Entry', rec.actualEntry !== false, pa.actual.entry === null ? NR : num(pa.actual.entry))}
        ${cell('实际 Exit', pa.actual.exit === null, pa.actual.exit === null ? NR : num(pa.actual.exit))}
        ${cell('实际 R', rec.actualR, rTxt(pa.actual.r))}
      </div>
      <div class="small muted" style="margin-top:8px">${dev.length ? `偏离：${dev.map((d) => `<span class="chip warn">${esc(d)}</span>`).join(' ')}` : '未检测到计划与实际的偏离（或计划值未记录）。'}</div></div></div>`;
  }
  function maeMfeBlock(t) {
    const m = t.maeMfe || {};
    const MM2 = V2().maeMfe || {};
    const row = (k, v, note) => `<div><div class="k">${k}</div><div class="v">${v === null || v === undefined ? NR : (v > 0 ? '+' : '') + Number(v).toFixed(2) + 'R'}</div><div class="small muted">${note}</div></div>`;
    const r = t.actualR;
    const read = (() => {
      if (m.mae === null || m.mae === undefined) return '未记录 MAE，无法判断 SL 是否过紧。';
      if (m.mae <= -0.8) return 'MAE 接近 −1R：SL 可能偏紧，容易被插针洗掉。';
      if (m.mae >= -0.45) return 'MAE 离 SL 还有距离：SL 相对宽松。';
      return 'MAE 在中间区间。';
    })();
    const read2 = (() => {
      if (m.mfe === null || m.mfe === undefined) return '未记录 MFE，无法判断是否提前止盈。';
      if (r !== null && m.mfe - r >= 0.8) return `MFE ${Number(m.mfe).toFixed(2)}R 明显高于实际 ${Number(r).toFixed(2)}R：止盈偏早。`;
      if (r !== null && r > 0) return '实际 R 与 MFE 差距不大：出场时机基本合理。';
      return '结果非盈利，MFE 只用于看是否浮盈回吐。';
    })();
    return `<div class="sec"><h2>MAE / MFE <span class="hint">§19 / §29 研究 SL 与止盈</span></h2>
      <div class="analytics-grid"><div class="panel"><div class="kv">
        ${row('MAE 最大浮亏', m.mae, 'Maximum Adverse Excursion —— 止损前最深浮亏')}
        ${row('MFE 最大浮盈', m.mfe, 'Maximum Favorable Excursion —— 最大浮盈')}
        </div>
        <div class="callout small" style="margin-top:10px">${esc(read)}<br>${esc(read2)}</div></div>
      <div class="panel"><h3>同维度整体</h3>
        <table class="plain"><thead><tr><th>口径</th><th class="num">笔数</th><th class="num">平均 R</th></tr></thead><tbody>
        ${[['全部 MAE', 'avgMAE', 'total'], ['全部 MFE', 'avgMFE', 'total'],
           ['盈利单 MAE', 'winMAE', 'winN'], ['亏损单 MFE', 'lossMFE', 'lossN']]
          .map(([k, kk, ck]) => `<tr><td>${esc(k)}</td><td class="num">${MM2[ck] === undefined ? (MM2.recorded || 0) : MM2[ck]}</td><td class="num">${MM2[kk] === null || MM2[kk] === undefined ? '—' : (MM2[kk] > 0 ? '+' : '') + Number(MM2[kk]).toFixed(2) + 'R'}</td></tr>`).join('')}
        </tbody></table>
        <div class="small muted" style="margin-top:6px">已记录 ${MM2.recorded || 0} / ${MM2.total || 0} 笔。${esc(MM2.note || '')}</div></div></div></div>`;
  }
  function answersPanel() {
    const ans = V2().answers || [];
    if (!ans.length) return '';
    return `<div class="sec"><h2>系统要回答的问题 <span class="hint">§41 · 基于全部交易，不受筛选影响</span></h2>
      <div class="qa">${ans.map((a) => `<div class="qacard${a.insufficient ? ' thin' : ''}">
        <div class="q">${esc(a.q)}${a.insufficient ? ' <span class="srcb auto">样本不足</span>' : ''}</div>
        <div class="a">${esc(a.a)}</div>
        <div class="b">依据：${esc(a.basis)}</div></div>`).join('')}</div></div>`;
  }

  /* ------------------------------------------------------------ 载入 */
  fetch('data/trades.json?ts=' + Date.now())
    .then((r) => r.json())
    .then((d) => {
      state.data = d;
      renderMeta();
      /* 测试缝：便于无头冒烟测试切换时间范围 */
      window.__tr = { state, route, setRange: (r) => { state.range = r; route(); } };
      window.addEventListener('hashchange', route);
      $('#range').addEventListener('click', (e) => {
        const b = e.target.closest('button'); if (!b) return;
        state.range = b.dataset.range;
        [...$('#range').children].forEach((x) => x.classList.toggle('active', x === b));
        route();
      });
      let t; $('#search').addEventListener('input', (e) => {
        clearTimeout(t); t = setTimeout(() => { state.q = e.target.value.trim(); route(); }, 160);
      });
      initLightbox();
      initTheme();
      [...$('#range').children].forEach((x) => x.classList.toggle('active', x.dataset.range === state.range));
      route();
    })
    .catch((e) => { $('#view').innerHTML = `<div class="empty">数据加载失败：${esc(e.message)}<br>请确认 data/trades.json 存在（先跑 python3 parser/build.py）。</div>`; });

  /* 需求 §43 要求 Dark Mode：默认暗色，可切亮色 */
  function initTheme() {
    const btn = $('#theme-toggle');
    if (!btn) return;
    const cur = document.documentElement.getAttribute('data-theme') || 'dark';
    btn.textContent = cur === 'dark' ? '☾ Dark' : '☀ Light';
    btn.addEventListener('click', () => {
      const next = (document.documentElement.getAttribute('data-theme') || 'dark') === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      try { localStorage.setItem('tr-theme', next); } catch (e) {}
      btn.textContent = next === 'dark' ? '☾ Dark' : '☀ Light';
    });
  }
  function renderMeta() {
    const m = state.data.meta;
    $('#brand-sub').textContent = m.sourceTitle || 'SMC Trading Review System';
    $('#meta-bar').innerHTML = [
      `<span>来源：<b>${esc(m.sourceTitle || '交易复盘')}</b>（Google Docs）</span>`,
      `<span>更新：<b>${esc((m.parsedAt || '').slice(0, 16).replace('T', ' '))}</b></span>`,
      `<span class="mono">版本 ${esc((m.sourceVersion || '').slice(0, 8))}</span>`,
    ].join('');
    $('#foot-src').innerHTML = `数据管线：Google Docs → parse_gdoc.py（sourceData，缺就 null）→ analysis.json（每条判定带原文引用）→ build.py（引用子串校验）→ data/trades.json。页面不猜、不补、不硬算 R。`;
  }

  /* ------------------------------------------------------------ 路由 */
  function route() {
    const h = location.hash.replace(/^#\/?/, '');
    const [path, qsStr] = h.split('?');
    state.filters = Object.fromEntries(new URLSearchParams(qsStr || ''));
    const parts = path.split('/').filter(Boolean);
    [...$('#nav').children].forEach((a) => a.classList.toggle('on', a.dataset.nav === (parts[0] || 'overview')));
    const view = $('#view');
    window.scrollTo(0, 0);
    if (parts.length === 0) return overviewView(view);
    switch (parts[0]) {
      case 'weeks': return parts[1] ? weekDetail(view, decodeURIComponent(parts[1])) : weeksView(view);
      case 'trades': return tradesView(view);
      case 'trade': return tradeDetail(view, decodeURIComponent(parts[1] || ''));
      case 'analytics': return analyticsView(view, parts[1]);
      case 'rules': return rulesView(view);
      default: return overviewView(view);
    }
  }

  /* ------------------------------------------------------------ 过滤 */
  /* ================= v4 · UI 整改（信息架构 + 视觉减负） ================= */
  /* ---- 旧版保留的 helper：设置标签 / POI 标签 / 短 ID / 查询串 / R 文本 ---- */
  const setupTags = (t) => {
    const rules = [[/sweep/i, 'Liquidity Sweep'], [/displacement/i, 'Displacement'], [/msb|mss/i, 'MSB / MSS'],
      [/bos/i, 'BOS'], [/poi|imb|bb|discount|premium|fvg|\bob\b/i, 'POI'],
      [/liquidity-to-liquidity/i, 'Liquidity-to-Liquidity'], [/pullback/i, 'Pullback']];
    const out = [];
    ((t.setup || {}).flow || []).forEach((s) => rules.forEach(([re, n]) => { if (re.test(s) && !out.includes(n)) out.push(n); }));
    return out;
  };
  const poiLabel = (p) => {
    const t = p.label || p.type;
    if (!t) return '';
    const tf = (p.timeframes || []).join('/').toUpperCase();
    return tf ? `${t} ${tf}` : t;
  };
  const poiChips = (list) => (list || []).map((p) => {
    const s = poiLabel(p);
    return s ? `<span class="chip poi">${esc(s)}</span>` : '';
  }).join('');
  const shortId = (id) => {
    const p = String(id).split('-');
    const d = p.length > 2 ? p.slice(1, 3).join('-') : id;
    const sym = (p[3] || '').replace('usdt', '').toUpperCase();
    return `${d} ${sym}`.trim();
  };
  const qs = (o) => {
    const s = new URLSearchParams(Object.entries(o).filter(([, v]) => v !== null && v !== undefined && v !== ''));
    const str = s.toString();
    return str ? '?' + str : '';
  };
  const cellR = (v) => (v === null || v === undefined ? '—' : (v > 0 ? '+' : '') + Number(v).toFixed(2) + 'R');
  /* ============================================================
     v4 · UI 整改（信息架构 + 视觉减负）
     依据《交易复盘系统 UI 整改意见》§一–§二十
     原则：不新增功能，只做 信息分组 / 页面减负 / 卡片合并 /
          导航精简 / 图表精简 / 标签中性化 / 高级字段折叠
     ============================================================ */

  /* ---------------- 时间范围（本周 / 上周 / 本月 / 全部） ---------------- */
  const DATE_RE = /\d{4}-\d{2}-\d{2}/;
  const tradeDate = (t) => {
    const m = `${t.entryTime || ''} ${t.entryDate || ''} ${t.exitTime || ''}`.match(DATE_RE);
    return m ? m[0] : null;
  };
  const isoDay = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 10);
  const weekStartOf = (base) => { const day = base.getDay() || 7; return new Date(base.getTime() - (day - 1) * 864e5); };
  const RANGE_WORD = { week: '本周', last: '上周', month: '本月', all: '全部' };
  const byTimeDesc = (a, b) => String(b.entryTime || b.entryDate || '').localeCompare(String(a.entryTime || a.entryDate || ''));
  const byTimeAsc = (a, b) => String(a.entryTime || a.entryDate || '').localeCompare(String(b.entryTime || b.entryDate || ''));

  function inRange(t) {
    if (state.range === 'all') return true;
    const d = tradeDate(t);
    if (!d) return true; /* 缺日期就不隐藏 —— 不猜、不乱归周 */
    const now = new Date();
    if (state.range === 'month') return d >= `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`;
    const mon = weekStartOf(now);
    if (state.range === 'week') return d >= isoDay(mon);
    if (state.range === 'last') { const prev = new Date(mon.getTime() - 7 * 864e5); return d >= isoDay(prev) && d < isoDay(mon); }
    return true;
  }

  /* ---------------- 指标（按当前时间范围现算；口径同 parser/stats_v2.py） ---------------- */
  function metrics(ts) {
    const closed = ts.filter((t) => ['win', 'loss', 'be'].includes(t.resultStatus));
    const rk = ts.filter((t) => t.rIncluded && t.actualR !== null);
    const wins = closed.filter((t) => t.resultStatus === 'win').length;
    const losses = closed.filter((t) => t.resultStatus === 'loss').length;
    const net = rk.reduce((a, t) => a + t.actualR, 0);
    const pos = rk.filter((t) => t.actualR > 0).reduce((a, t) => a + t.actualR, 0);
    const neg = rk.filter((t) => t.actualR < 0).reduce((a, t) => a + t.actualR, 0);
    const good = closed.filter((t) => ['Good Win', 'Good Loss'].includes(qualityCol(t))).length;
    const comp = ts.map((t) => (t.complianceV2 || {}).passRate).filter((v) => v !== null && v !== undefined);
    const r2 = (v) => Math.round(v * 100) / 100;
    return {
      n: ts.length, closed: closed.length, wins, losses, rCounted: rk.length,
      netR: rk.length ? r2(net) : null,
      avgR: rk.length ? r2(net / rk.length) : null,
      winRate: closed.length ? wins / closed.length : null,
      goodWins: good, goodRate: closed.length ? good / closed.length : null,
      compDecided: comp.length, compRate: comp.length ? comp.reduce((a, b) => a + b, 0) / comp.length : null,
      pf: neg ? r2(pos / Math.abs(neg)) : (pos ? '∞' : null),
    };
  }
  const pfTxt = (v) => (v === null || v === undefined ? NR : v === '∞' ? '∞' : Number(v).toFixed(2));

  function curveOf(ts) {
    let cum = 0;
    return ts.filter((t) => t.rIncluded && t.actualR !== null).slice().sort(byTimeAsc)
      .map((t) => { cum += t.actualR; return { cum: Math.round(cum * 100) / 100, r: t.actualR, date: dateOf(t), symbolLabel: t.symbolLabel }; });
  }

  /* ---------------- 列表列（§16 只保留 7 列） ---------------- */
  const UNRATED = ['未定级', '未记录', '未分类', ''];
  const setupCol = (t) => {
    const poi = [valTxt(fv(t, 'htfPOIType')), valTxt(fv(t, 'htfPOITF'))].filter(Boolean).join(' ');
    return poi || setupTags(t)[0] || null;
  };
  const entryModeCol = (t) => valTxt(fv(t, 'entryMode')) || (t.entryModel || {}).category || null;
  const qualityCol = (t) => { const v = String((t.quality || {}).value || ''); return UNRATED.includes(v) ? null : v; };
  const qualityChip = (t) => {
    const q = qualityCol(t);
    if (!q) return NR;
    return `<span class="chip ${/Good/.test(q) ? 'goodq' : 'badq'}">${esc(q)}</span>`;
  };
  const ENTRY_MODES = ['Limit Entry', 'LTF Confirmation', 'Market Entry'];
  const QUALITIES = ['Good Win', 'Good Loss', 'Bad Win', 'Bad Loss'];
  const THEAD7 = '<div class="thead7"><span>Date</span><span>Symbol</span><span>Direction</span><span>Setup</span><span>Entry Mode</span><span>Result</span><span>Quality</span></div>';

  function tradeRow(t) {
    const r = t.review || {}, a = t.analysis || {};
    const note = short(r.mainProblem || (r.improve || [])[0] || a.notes || '', 90);
    const sc = setupCol(t), ec = entryModeCol(t);
    return `<a class="trow cols7" href="#/trade/${encodeURIComponent(t.id)}" title="${esc(note || t.heading || '')}">
      <span class="td d">${esc(dateOf(t))}</span>
      <span class="td sym">${esc(t.symbolLabel || '')}</span>
      <span class="td dir">${esc(dirWord(t.direction))}</span>
      <span class="td setup">${sc ? esc(sc) : NR}</span>
      <span class="td mode">${ec ? esc(ec) : NR}</span>
      <span class="td r">${rTxt(t.rIncluded ? t.actualR : null)}</span>
      <span class="td q">${qualityChip(t)}</span>
    </a>`;
  }

  /* ---------------- 决策阶段组件（§17 一个决策阶段 = 一个区域） ---------------- */
  function phase(no, title, hint, body) {
    return `<section class="phase"><div class="phase-head"><span class="phase-no">${esc(no)}</span>
      <h2>${esc(title)}</h2><span class="hint">${esc(hint)}</span></div>${body}</section>`;
  }
  function wval(t, k) {
    const f = fv(t, k), v = valTxt(f);
    if (!v) return '';
    return `<span class="chip ghost">${esc(v)}</span>`;
  }
  function wcell(title, keys, t, opts) {
    const o = opts || {};
    const chips = keys.map((k) => wval(t, k)).filter(Boolean).join(' ');
    const tf = keys.map((k) => fv(t, k)).filter(Boolean)
      .reduce((acc, f) => acc.concat(f.tf || []), []).filter((v, i, arr) => arr.indexOf(v) === i);
    return `<div class="wcell${chips ? '' : ' bare'}"><div class="wcell-t">${esc(title)}${tf.length ? ` <span class="srcb">${esc(tf.join('/'))}</span>` : ''}</div>
      <div class="wcell-v">${chips || '<span class="muted">未记录</span>'}</div></div>`;
  }
  function wchain(cells) {
    const parts = cells.filter(Boolean);
    return `<div class="wchain">${parts.map((c, i) => `${i ? '<span class="warw">→</span>' : ''}${c}`).join('')}</div>`;
  }
  const isGood = (v) => /Good/.test(String(v || ''));

  /* ---------------- 截图：Tab / Gallery（§10，默认只显示一张大图） ---------------- */
  function imgGroupOf(im) {
    const ty = im.type || '';
    const tf = String(im.timeframe || '').toLowerCase();
    if (ty === 'LTF Entry') return /5\s*m|5分钟/.test(tf) ? '5min' : '15min';
    if (ty === 'HTF Context') return 'HTF';
    if (ty === 'After Trade' || ty === 'Review Screen') return 'Result';
    if (/1h|4h|1d|1小时|4小时|日线/.test(tf)) return 'HTF';
    if (/5\s*m|5分钟/.test(tf)) return '5min';
    if (/15|分钟|\bm\b/.test(tf)) return '15min';
    return '其他';
  }
  const IMG_TABS = [['HTF', 'HTF 1D/4H/1H'], ['15min', '15min'], ['5min', '5min'], ['Result', 'Result / 事后'], ['其他', '其他']];

  function imgTabsBlock(t) {
    const imgs = t.images || [];
    if (!imgs.length) return '';
    const groups = {};
    imgs.forEach((im, i) => { const g = imgGroupOf(im); (groups[g] = groups[g] || []).push({ im, i }); });
    const tabs = IMG_TABS.filter(([k]) => (groups[k] || []).length);
    const active = tabs[0][0];
    const tabBtns = tabs.map(([k, lab]) => `<button class="itab${k === active ? ' on' : ''}" data-g="${esc(k)}">${esc(lab)} <span class="muted">${groups[k].length}</span></button>`).join('');
    const panes = tabs.map(([k]) => `<div class="ipane${k === active ? ' on' : ''}" data-g="${esc(k)}">
        <figure class="istage"><img src="${esc(groups[k][0].im.path)}" alt="" data-g="${esc(k)}" data-i="${groups[k][0].i}">
          <figcaption>${esc(groups[k][0].im.caption || imgKind(groups[k][0].im))}</figcaption></figure>
        <div class="ithumbs">${groups[k].map(({ im, i }) => `<button class="ithumb${i === groups[k][0].i ? ' on' : ''}" data-g="${esc(k)}" data-i="${i}" title="${esc(im.caption || imgKind(im))}">
          <img src="${esc(im.path)}" alt="" loading="lazy"></button>`).join('')}</div>
      </div>`).join('');
    return `<div class="sec"><h2>图表 / 截图 <span class="hint">§10 按周期分 Tab，默认一张大图；点图放大</span></h2>
      <div class="imtabs" data-imgtabs><div class="itab-btns">${tabBtns}</div>${panes}
        <div class="small muted" style="margin-top:8px">${imgStrip(imgs, t)}</div></div></div>`;
  }
  function initImgTabs(root, t) {
    const box = root.querySelector('[data-imgtabs]'); if (!box) return;
    const show = (g, i) => {
      box.querySelectorAll('.itab').forEach((b) => b.classList.toggle('on', b.dataset.g === g));
      box.querySelectorAll('.ipane').forEach((p) => p.classList.toggle('on', p.dataset.g === g));
      const pane = box.querySelector(`.ipane[data-g="${g}"]`); if (!pane) return;
      const im = (t.images || [])[i];
      if (im) { pane.querySelector('.istage img').src = im.path; pane.querySelector('.istage figcaption').textContent = im.caption || imgKind(im); pane.querySelector('.istage img').dataset.i = i; }
      pane.querySelectorAll('.ithumb').forEach((b) => b.classList.toggle('on', Number(b.dataset.i) === i));
    };
    box.addEventListener('click', (e) => {
      const tb = e.target.closest('.itab');
      if (tb) { const first = box.querySelector(`.ipane[data-g="${tb.dataset.g}"] .ithumb`); return show(tb.dataset.g, first ? Number(first.dataset.i) : 0); }
      const th = e.target.closest('.ithumb');
      if (th) return show(th.dataset.g, Number(th.dataset.i));
      const st = e.target.closest('.istage img');
      if (st) return openLightbox(t, Number(st.dataset.i) || 0);
    });
  }

  /* ---------------- 三段式：PLAN / EXECUTION / REVIEW（§4–§7） ---------------- */
  function planSection(t) {
    const p = ((t.plannedVsActual || {}).planned) || {};
    const tpItems = arr(p.tp).filter(Boolean);
    const tpIsPrice = tpItems.length && tpItems.every((x) => /^[\d.,\s\/+-]+$/.test(String(x)));
    const tpTxt = tpItems.join('；');
    const cell = (k, v) => `<span><i>${esc(k)}</i><b>${v === null || v === undefined || v === '' ? NR : esc(v)}</b></span>`;
    const planBar = `<div class="pricebar">
      ${cell('Direction', dirWord(t.direction))}
      ${cell('Plan Entry', p.entry === null || p.entry === undefined ? null : num(p.entry))}
      ${cell('Plan SL', p.sl === null || p.sl === undefined ? null : num(p.sl))}
      ${cell(tpIsPrice ? 'Plan TP' : 'Plan Target', tpItems.length ? (tpIsPrice ? tpItems.join(' / ') : (tpTxt.length > 40 ? tpTxt.slice(0, 40) + '…' : tpTxt)) : null)}
      ${cell('Planned RR', p.rr === null || p.rr === undefined ? null : `${p.rr}R`)}
    </div>${tpItems.length && !tpIsPrice ? `<div class="small muted" style="margin-top:6px">目标原文：${esc(tpTxt)}</div>` : ''}`;
    const body = `<div class="tf-strip">HTF — Why <span class="srcb">1D / 4H / 1H</span></div>
      ${wchain([
        wcell('HTF Context', ['htfBias', 'biasSourceTF', 'marketCondition', 'htfStructureKind', 'htfStructureTF'], t),
        wcell('Liquidity', ['liquidityType', 'liquidityTF'], t),
        wcell('POI', ['htfPOIType', 'htfPOITF', 'poiConfluence', 'ltfPOIType', 'ltfPOITF'], t),
      ])}
      <div class="small muted" style="margin:10px 0 0">回答「为什么关注这个方向和这个位置」。</div>
      <h3 class="phase-sub">Trade Plan</h3>${planBar}`;
    return phase('PLAN', '为什么准备做这笔交易', 'HTF Context · 交易前逻辑', body);
  }

  function execSection(t) {
    const a = ((t.plannedVsActual || {}).actual) || {};
    const pa = t.plannedVsActual || {};
    const dev = arr(pa.deviations);
    const mode = valTxt(fv(t, 'entryMode')) || ((t.entryModel || {}).category) || null;
    const modeWord = { HTF_LIMIT: 'Limit Entry', LTF_CONFIRMATION: 'LTF Confirmation', MARKET_ENTRY: 'Market Entry' }[mode] || mode;
    const seg = `<div class="seg">${ENTRY_MODES.map((m) => `<span class="${m === modeWord ? 'on' : ''}">${esc(m)}</span>`).join('')}</div>
      <div class="small muted" style="margin-top:6px">Entry Mode 是统计口径：Limit Entry = 提前挂单；LTF Confirmation = 等低周期确认；Market Entry = 直接市价。文档没写就是未记录。</div>`;
    const actCells = [
      a.entry === null || a.entry === undefined ? null : ['Actual Entry', num(a.entry)],
      a.exit === null || a.exit === undefined ? null : ['Actual Exit', num(a.exit)],
      a.r === null || a.r === undefined ? null : ['Actual R', rTxt(a.r)],
    ].filter(Boolean);
    const body = `<div class="tf-strip">LTF — When <span class="srcb">15min / 5min</span></div>
      ${wchain([
        wcell('Sweep / Reaction', ['liquiditySweep', 'sweepQuality', 'sweepTF', 'reaction', 'reactionType', 'reactionTF'], t),
        wcell('Displacement', ['displacementQuality', 'displacementTF'], t),
        wcell('MSS / MSB', ['structureShiftType', 'structureShiftTF', 'brokenStructure'], t),
        wcell('Entry Trigger', ['entryTriggerType', 'entryTriggerTF', 'limitStyle'], t),
      ])}
      <div class="small muted" style="margin:10px 0 0">回答「什么时候真正进入」。Internal / Key / Protected 要能分清，不知道为什么突破就不算确认。</div>
      <h3 class="phase-sub">Entry Mode</h3>${seg}
      ${actCells.length ? `<h3 class="phase-sub">Actual</h3><div class="pricebar">${actCells.map(([k, v]) => `<span><i>${esc(k)}</i><b>${v}</b></span>`).join('')}</div>` : ''}
      ${dev.length ? `<div class="callout warn" style="margin-top:10px">计划与实际的偏离（执行问题）：${dev.map((d) => `<span class="chip warn">${esc(d)}</span>`).join(' ')}</div>` : ''}`;
    return phase('EXECUTION', '实际市场发生了什么 / 最终怎么入场', 'LTF Confirmation · 实际执行', body);
  }

  function reviewSection(t) {
    const a = t.analysis || {}, r = t.review || {};
    const q = qualityCol(t);
    const mis = (a.mistakes || []).map((m) => `<span class="chip warn">${esc(m.tag || m)}</span>`).join(' ');
    const vio = (a.ruleViolations || []).map((m) => `<span class="chip warn">${esc(m.tag || m)}</span>`).join(' ');
    const next = (r.improve || [])[0] || r.nextRules || null;
    const body = `<div class="review-grid">
        <div class="rbox"><div class="k">Result</div><div class="rv">${rTxt(t.rIncluded ? t.actualR : null)} ${resChip(t)}</div></div>
        <div class="rbox"><div class="k">Trade Quality</div>
          <div class="seg">${QUALITIES.map((x) => `<span class="${x === q ? 'on' : ''}">${esc(x)}</span>`).join('')}</div>
          <div class="small muted" style="margin-top:6px">Good = 按规则做的（赢或亏都算好交易）；Bad = 违规或乱做的。</div></div>
      </div>
      <div class="review-grid" style="margin-top:12px">
        <div class="rbox"><div class="k">Mistake</div><div class="rv">${mis || vio || NR}</div></div>
        <div class="rbox"><div class="k">Lesson · 下次怎么改</div><div class="rv">${r.mainProblem ? esc(short(r.mainProblem, 180)) : next ? esc(short(next, 180)) : NR}</div>
          ${next && r.mainProblem ? `<div class="small muted">改进动作：${esc(short(next, 140))}</div>` : ''}
          ${(r.worked || []).length ? `<div class="small muted">做对了：${esc(short(r.worked[0], 120))}</div>` : ''}</div>
      </div>
      <div class="small muted" style="margin-top:10px">Review 不用写成长篇作文：结果 → 质量 → 错误 → 一句教训，够了。</div>`;
    return phase('REVIEW', '这笔交易质量怎么样 / 哪里要改进', '结果 · 质量 · 错误 · 教训', body);
  }

  /* ---------------- 交易详情（PLAN → EXECUTION → REVIEW + 高级折叠） ---------------- */
  function tradeDetail(view, id) {
    const t = state.data.trades.find((x) => x.id === id);
    if (!t) { view.innerHTML = `<div class="empty">找不到交易 ${esc(id)}。<a href="#/trades">返回列表</a></div>`; return; }
    const adv = `<details class="fold"><summary>更多细节 / Advanced（§8：默认收起，不让复盘变成填表）</summary>
      <div style="padding:6px 14px 14px">
        ${numericBlock(t)}
        ${chainBlock(t)}
        ${checklistBlock(t)}
        ${plannedActualBlock(t)}
        ${maeMfeBlock(t)}
        <details class="fold"><summary>原始记录（文档原文）</summary>
          <div class="rawgrid">${Object.entries(t.rawSections || {}).map(([k, v]) => `<div class="panel"><h3>${esc(k)}</h3><div class="kvraw-lite"><div>${esc(short(v, 1800))}</div></div></div>`).join('')}</div>
        </details>
      </div></details>`;
    view.innerHTML = `
      <div class="td-head">
        <div>
          <h1>${esc(t.symbolLabel || '')} <span class="d-${esc(t.direction || 'x')}">${esc(dirWord(t.direction))}</span></h1>
          <div class="sub">${esc(t.id)} · ${esc(t.weekLabel || '')} · ${esc(t.entryTime || t.entryDate || '')} · <a href="#/trades">← 返回列表</a></div>
        </div>
        <div class="rr"><div class="small muted">Actual R</div><div class="big">${rTxt(t.rIncluded ? t.actualR : null)}</div><div>${resChip(t)}</div></div>
      </div>
      ${imgTabsBlock(t)}
      ${planSection(t)}
      ${execSection(t)}
      ${reviewSection(t)}
      ${adv}`;
    initImgTabs(view, t);
  }

  function numericBlock(t) {
    const keys = ['protectedPrice', 'mae', 'mfe', 'confidence'];
    const has = keys.filter((k) => FBYK()[k]);
    if (!has.length) return '';
    return `<div class="sec"><h2>关键数值 <span class="hint">§13 / §19 / §29（高级字段）</span></h2>
      <div class="panel"><div class="cfields">${has.map((k) => cfield(t, k)).join('')}</div></div></div>`;
  }

  /* ---------------- Overview（§3：只回答三个问题） ---------------- */
  function overviewView(view) {
    const ts = filtered();
    const m = metrics(ts);
    const weeks = state.data.weeks.filter((w) => w.tradeIds.some((id) => ts.some((t) => t.id === id)));
    const w0 = weeks.slice().sort((a, b) => String(a.start).localeCompare(String(b.start))).pop() || null;
    const W = w0 ? V2W(w0.label) : null;
    const recent = ts.slice().sort(byTimeDesc).slice(0, 6);
    const cell = (k, v, s) => `<div class="stat"><div class="k">${k}</div><div class="v">${v}</div>${s ? `<div class="s">${s}</div>` : ''}</div>`;
    const focus = W ? `
        ${W.mainProblem ? `<div class="focusline bad"><b>本周主要问题</b><span>${esc(W.mainProblem)}</span></div>` : ''}
        ${W.nextFocus ? `<div class="focusline rule"><b>下周重点</b><span>${esc(W.nextFocus)}</span></div>` : ''}
        ${W.didWell ? `<div class="focusline good"><b>做得好的</b><span>${esc(W.didWell)}</span></div>` : ''}`
      : '<div class="small muted">这个范围里没有周复盘记录。</div>';
    view.innerHTML = `
      <div class="sec"><h2>${esc(RANGE_WORD[state.range] || '')}表现 <span class="hint">§3 首页只回答：最近怎么样 / 最大问题是什么 / 最近做了哪些交易</span></h2>
        <div class="stats stats-6">
          ${cell('Net R', rTxt(m.netR), `${m.rCounted} 笔可计 R`)}
          ${cell('Trades', `${m.closed} / ${m.n}`, '已结束 / 全部')}
          ${cell('Win Rate', pct(m.winRate), `${m.wins} 胜 / ${m.losses} 负`)}
          ${cell('Expectancy', rTxt(m.avgR), '平均每笔期望值（§31）')}
          ${cell('Good Trade Rate', pct(m.goodRate), `${m.goodWins} 好 / ${m.closed} 笔（§23）`)}
          ${cell('Rule Compliance', pct(m.compRate), m.compDecided ? `${m.compDecided} 笔有结论` : '还没有一笔有结论')}
        </div>
        <div class="small muted" style="margin-top:8px">口径：只统计文档里真实写了的数据；缺项显示「未记录」，不当 0 算。Profit Factor ${pfTxt(m.pf)}（总盈利 R ÷ 总亏损 R，§27）。</div>
      </div>
      <div class="sec"><h2>R Curve <span class="hint">${esc(RANGE_WORD[state.range] || '')}逐笔累计 R</span></h2>
        <div class="panel">${sparkline(curveOf(ts))}</div></div>
      <div class="sec"><h2>Recent Trades <span class="hint">最近 ${recent.length} 笔 · <a href="#/trades">全部交易 →</a></span></h2>
        <div class="trows">${recent.length ? THEAD7 + recent.map(tradeRow).join('') : '<div class="empty">这个范围里没有交易，切到「全部」看总账。</div>'}</div></div>
      <div class="sec"><h2>This Week Focus <span class="hint">${w0 ? esc(w0.label) : ''}</span></h2>
        <div class="focusbox">${focus}</div></div>
      ${weeks.length ? `<details class="fold"><summary>周复盘（${weeks.length} 周：Expectancy / MAE·MFE / 最佳 Setup / 最大错误）· <a href="#/weeks">全部周 →</a></summary>
        <div style="padding:4px 14px 14px">${weeks.map((w) => weekBlock(w, ts)).join('')}</div></details>` : ''}`;
  }

  /* ---------------- Trades（§16：列表只留 7 列） ---------------- */
  function tradesView(view) {
    const ts = filtered();
    const uniq = (k) => [...new Set(state.data.trades.map(k).filter(Boolean))];
    const qsx = (o) => {
      const s = new URLSearchParams(Object.entries(o).filter(([, v]) => v !== null && v !== undefined && v !== ''));
      const str = s.toString(); return str ? `?${str}` : '';
    };
    const chips = (key, opts, fmt = (x) => x) => `<div class="filt">${opts.map((o) => {
      const on = state.filters[key] === o ? ' on' : '';
      return `<a class="chip tag${on}" href="#/trades${qsx({ ...state.filters, [key]: state.filters[key] === o ? null : o })}">${esc(fmt(o))}</a>`;
    }).join('')}</div>`;
    const R = state.data.trades;
    const setupVals = [...new Set(R.flatMap((t) => setupTags(t)).filter(Boolean))];
    const modeVals = [...new Set(R.map((t) => valTxt(fv(t, 'entryMode'))).filter(Boolean))];
    const qualVals = [...new Set(R.map((t) => ((t.quality || {}).value || '')).filter(Boolean))];
    const filt = `<details class="fold"${ACTIVE() ? ' open' : ''}><summary>筛选 / 搜索（当前 ${ts.length} 笔）</summary>
      <div style="padding:6px 14px 14px">
        <div class="frowline"><span class="fl">结果</span>${chips('result', ['win', 'loss', 'be'], (x) => ({ win: 'Win', loss: 'Loss', be: 'BE' }[x]))}</div>
        <div class="frowline"><span class="fl">方向</span>${chips('direction', ['long', 'short'], dirWord)}</div>
        ${uniq((t) => t.symbolLabel).length ? `<div class="frowline"><span class="fl">标的</span>${chips('symbol', uniq((t) => t.symbolLabel))}</div>` : ''}
        ${setupVals.length ? `<div class="frowline"><span class="fl">Setup</span>${chips('setup', setupVals)}</div>` : ''}
        ${modeVals.length ? `<div class="frowline"><span class="fl">Entry Mode</span>${chips('entryMode', modeVals)}</div>` : ''}
        ${qualVals.length ? `<div class="frowline"><span class="fl">交易质量</span>${chips('qv', qualVals)}</div>` : ''}
        <div class="frowline"><span class="fl">时间范围</span><span class="small muted">用右上角 本周 / 上周 / 本月 / 全部 切</span></div>
        ${ACTIVE() ? `<div style="margin-top:8px"><a class="chip tag on" href="#/trades">清空筛选</a></div>` : ''}
      </div></details>`;
    view.innerHTML = `<div class="sec"><h2>交易列表 <span class="hint">§16 只保留 7 列，点开看 PLAN → EXECUTION → REVIEW</span></h2>
      ${filt}
      <div class="trows" style="margin-top:12px">${ts.length ? THEAD7 + ts.slice().sort(byTimeDesc).map(tradeRow).join('') : '<div class="empty">没有符合条件的交易。</div>'}</div></div>`;
  }

  /* ---------------- Analytics（§12–§15：问题驱动，不再铺十几个图） ---------------- */
  const ATABS = [['setup', 'Setup'], ['entry', 'Entry'], ['poi', 'POI'], ['structure', 'Structure'], ['mistakes', 'Mistakes'], ['risk', 'Risk']];

  function entryTable() {
    const src = V2().entryModePerformance || {};
    const rows = (src.rows || []).slice().sort((a, b) => (b.count || 0) - (a.count || 0));
    if (!rows.length) return '<div class="muted small">还没有数据。</div>';
    return `<table class="plain"><thead><tr><th>入场方式（Entry Mode）</th><th class="num">Trades</th><th class="num">Win Rate</th><th class="num">Avg R</th><th class="num">Expectancy</th><th class="num">Profit Factor</th></tr></thead>
      <tbody>${rows.map((r) => `<tr><td>${esc(r.key)}<div class="small muted">${(r.trades || []).map((id) => `<a href="#/trade/${encodeURIComponent(id)}" style="text-decoration:underline">${esc(shortId(id))}</a>`).join(' · ')}</div></td>
        <td class="num">${r.closed || 0} / ${r.count || 0}</td><td class="num">${r.winRate === null || r.winRate === undefined ? '—' : pct(r.winRate)}</td>
        <td class="num">${cellR(r.avgR)}</td><td class="num">${cellR(r.expectancy)}</td>
        <td class="num">${r.profitFactor === null || r.profitFactor === undefined ? '—' : Number(r.profitFactor).toFixed(2)}</td></tr>`).join('')}</tbody></table>
      <div class="small muted" style="margin-top:6px">${esc(src.label || '入场方式')} · 口径：只统计文档里真实写了 Entry Mode 的交易，未写 = 「(未记录)」（§37 不猜）。</div>`;
  }

  function mistakesTab() {
    const M = V2().mistakes || {};
    const rows = (M.rows || []).slice().sort((a, b) => (b.count || 0) - (a.count || 0));
    const byLoss = (M.rows || []).slice().sort((a, b) => (a.lostR || 0) - (b.lostR || 0));
    const top = byLoss[0];
    const viol = (state.data.analytics || {}).violationFrequency || [];
    return `<div class="sec"><h2>Mistakes <span class="hint">§15 最值得优先改的错误</span></h2>
      ${top ? `<div class="callout warn">最该先改：<b>${esc(top.tag)}</b> —— 出现 ${top.count} 次，损失 ${cellR(top.lostR)}。<br>
        <span class="small muted">口径：只统计文档里真实写了 / 已确认的错误标签；自动识别的只是建议（§37）。</span></div>` : ''}
      <div class="panel" style="margin-top:12px"><h3>错误清单</h3>
        <table class="plain"><thead><tr><th>Mistake</th><th>类别</th><th class="num">次数</th><th class="num">损失 R</th><th class="num">相关笔数</th><th>出现交易</th></tr></thead>
        <tbody>${rows.length ? rows.map((r) => `<tr><td>${esc(r.tag)}${r.unconfirmed ? '<span class="srcb auto">建议·待确认</span>' : ''}</td>
          <td>${esc(r.category || '其他')}</td><td class="num">${r.count}</td><td class="num">${cellR(r.lostR)}</td><td class="num">${r.rCounted || 0}</td>
          <td>${(r.trades || []).map((id) => `<a href="#/trade/${encodeURIComponent(id)}" style="text-decoration:underline">${esc(shortId(id))}</a>`).join(' · ')}</td></tr>`).join('')
          : '<tr><td colspan="6" class="muted">还没有记录任何错误标签。</td></tr>'}</tbody></table></div>
      <div class="analytics-grid" style="margin-top:12px">
        <div class="panel"><h3>规则违反频率</h3>${freqBars(viol.map((r) => ({ label: r.key, count: r.count, rCounted: r.rCounted, expectancy: r.avgR })), Math.max(1, ...viol.map((r) => r.count)))}</div>
        <div class="panel"><h3>错误分布</h3>${freqBars(rows.map((r) => ({ label: r.tag, count: r.count, rCounted: r.rCounted, expectancy: r.rCounted ? r.lostR / r.rCounted : null })))}</div>
      </div></div>`;
  }

  function riskTab() {
    const SVE = V2().strategyVsExecution || {}, MM = V2().maeMfe || {}, NUM = V2().numeric || [];
    const TF = V2().timeframes || {}, DQ = V2().dataQuality || {}, H = (state.data.analytics || {}).holding || {};
    const S = state.data.stats || {};
    const IM = V2().images || {};
    const line = (k, v, s) => `<div class="frowline2"><span class="fl">${esc(k)}</span><span>${v}</span>${s ? `<span class="small muted">${esc(s)}</span>` : ''}</div>`;
    return `<div class="sec"><h2>Risk <span class="hint">§12 亏损来自策略还是执行 / 风险与数据质量</span></h2>
      <div class="analytics-grid">
        <div class="panel"><h3>策略问题 vs 执行问题</h3>
          ${line('Good Loss（按规则仍止损）', `${(SVE.goodLoss || {}).count || 0} 笔`, cellR((SVE.goodLoss || {}).r))}
          ${line('Bad Loss（违规亏损）', `${(SVE.badLoss || {}).count || 0} 笔`, cellR((SVE.badLoss || {}).r))}
          ${line('未定级亏损', `${(SVE.unknownQuality || {}).count || 0} 笔`)}
          <div class="small muted" style="margin-top:6px">${esc(SVE.note || '')}</div></div>
        <div class="panel"><h3>MAE / MFE（§19 / §29）</h3>
          ${line('平均 MAE', MM.avgMAE === null || MM.avgMAE === undefined ? NR : `${Number(MM.avgMAE).toFixed(2)}R`, `已记录 ${MM.recorded || 0} / ${MM.total || 0} 笔`)}
          ${line('平均 MFE', MM.avgMFE === null || MM.avgMFE === undefined ? NR : `+${Number(MM.avgMFE).toFixed(2)}R`)}
          ${line('盈利单 MAE / 亏损单 MFE', `${MM.winMAE === null || MM.winMAE === undefined ? '—' : Number(MM.winMAE).toFixed(2)} / ${MM.lossMFE === null || MM.lossMFE === undefined ? '—' : Number(MM.lossMFE).toFixed(2)}`)}
          <div class="small muted" style="margin-top:6px">${esc(MM.note || '')}</div></div>
        <div class="panel"><h3>数值字段记录情况（§13）</h3>
          <table class="plain"><thead><tr><th>字段</th><th class="num">已记录</th><th class="num">平均</th></tr></thead>
          <tbody>${NUM.map((n) => `<tr><td>${esc(n.label || n.key)}<div class="small muted">单位 ${esc(n.unit || '—')}</div></td>
            <td class="num">${n.recorded} / ${n.total}</td><td class="num">${n.avg === null || n.avg === undefined ? '—' : Number(n.avg).toFixed(2)}</td></tr>`).join('')}</tbody></table></div>
        <div class="panel"><h3>截图分类（§24）</h3>
          ${(IM.rows || []).map((r) => line(esc(r.kind), `${r.count} 张`, Object.keys(r.tf || {}).join('/') || '周期未标')).join('')}
          ${line('合计', `${IM.total || 0} 张`, `已分类 ${IM.labeled || 0} / 未分类 ${IM.unlabeled || 0}`)}
          <div class="small muted" style="margin-top:6px">分类在本地编辑器「截图分类」页勾选，原图不改动。</div></div>
        <div class="panel"><h3>持仓时间 / 盈亏比</h3>
          ${line('平均盈利持仓', H.avgWinnerHours === null || H.avgWinnerHours === undefined ? NR : `${Number(H.avgWinnerHours).toFixed(1)} 小时`)}
          ${line('平均亏损持仓', H.avgLoserHours === null || H.avgLoserHours === undefined ? NR : `${Number(H.avgLoserHours).toFixed(1)} 小时`)}
          ${line('平均盈利单 R', S.avgWinnerR === null || S.avgWinnerR === undefined ? NR : `+${Number(S.avgWinnerR).toFixed(2)}R`)}
          ${line('平均亏损单 R', S.avgLoserR === null || S.avgLoserR === undefined ? NR : `${Number(S.avgLoserR).toFixed(2)}R`)}
          <div class="small muted" style="margin-top:6px">${esc(H.note || '')}</div></div>
        <div class="panel"><h3>时间周期使用（HTF / LTF）</h3>
          ${line('HTF 固定', (TF.HTF || []).join(' / '))}
          ${line('LTF 固定', (TF.LTF || []).join(' / '))}
          ${(TF.HTFUsage || []).map((u) => line(`HTF ${u.label}`, `${u.count} 次`)).join('')}
          ${(TF.LTFUsage || []).map((u) => line(`LTF ${u.label || u.key}`, `${u.count} 次`)).join('')}</div>
        <div class="panel"><h3>数据质量（§4.1 不必填，缺就不算）</h3>
          ${line('已确认字段 / 自动识别', `${DQ.fieldsConfirmed || 0} / ${DQ.fieldsAuto || 0}`)}
          ${line('平均完整度', (state.data.analytics || {}).dataCompletenessAvg === null || (state.data.analytics || {}).dataCompletenessAvg === undefined ? NR : `${Number((state.data.analytics || {}).dataCompletenessAvg).toFixed(1)}%`)}
          ${line('未记录维度数', String((V2().emptyDimensions || []).length))}
          <div class="small muted" style="margin-top:6px">${esc(DQ.note || '')}</div></div>
      </div>
      <details class="fold"><summary>全部维度明细（点开看每个维度逐项统计）</summary>
        <div style="padding:8px 14px 14px" class="analytics-grid">${(V2().dimensionOrder || []).map((k) => dimTable(k)).join('')}</div></details>
      <details class="fold"><summary>系统要回答的问题（§41 · 基于全部交易，不受时间范围影响）</summary>
        <div style="padding:4px 14px 14px">${answersPanel()}</div></details></div>`;
  }

  function analyticsView(view, tab) {
    const T = ATABS.some(([k]) => k === tab) ? tab : 'setup';
    const ts = filtered();
    const A = state.data.analytics || {};
    const V = V2();
    const panels = {
      setup: () => `<div class="sec"><h2>Setup 表现 <span class="hint">§12 哪个 Setup 真的赚钱</span></h2>
          <div class="analytics-grid">
            <div class="panel"><h3>按 Setup 标签</h3>${perfTable(A.setupTagPerformance || [], 'Setup 标签')}</div>
            <div class="panel"><h3>按 Setup 名称</h3>${perfTable(A.setupPerformance || [], 'Setup')}</div>
            ${dimTable('tradeQuality')}${dimTable('shouldTake')}
          </div></div>`,
      entry: () => `<div class="sec"><h2>Entry <span class="hint">§13 Limit Entry vs LTF Confirmation vs Market Entry</span></h2>
          <div class="panel">${entryTable()}</div>
          <div class="analytics-grid" style="margin-top:12px">${dimTable('entryTriggerType')}${dimTable('limitStyle')}${dimTable('entryTriggerTF')}</div></div>`,
      poi: () => `<div class="sec"><h2>POI <span class="hint">§12 哪个 HTF POI 最有效</span></h2>
          <div class="analytics-grid">${dimTable('htfPOIType')}${dimTable('htfPOITF')}${dimTable('poiConfluence')}${dimTable('ltfPOIType')}${dimTable('ltfPOITF')}</div></div>`,
      structure: () => `<div class="sec"><h2>Structure <span class="hint">§14 Internal / Key / Protected 到底哪种有价值</span></h2>
          <div class="callout small">只记「MSB = Yes」看不出价值 —— 要分清突破的是 Internal Structure（小级别）还是 Key / Protected Structure（大级别）。</div>
          <div class="analytics-grid">${dimTable('structureShiftType')}${dimTable('structureShiftTF')}${dimTable('brokenStructure')}${dimTable('protectedStructure')}${dimTable('displacementQuality')}</div></div>`,
      mistakes: mistakesTab,
      risk: riskTab,
    };
    view.innerHTML = `
      <div class="sec"><h2>你想分析什么？ <span class="hint">§12 问题驱动 —— 点一个问题，只看相关分析</span></h2>
        <div class="atabs">${ATABS.map(([k, lab]) => `<a class="atab${k === T ? ' on' : ''}" href="#/analytics/${k}">${esc(lab)}</a>`).join('')}</div>
        <div class="small muted" style="margin-top:8px">当前时间范围：${esc(RANGE_WORD[state.range] || '')} · ${ts.length} 笔（右上角可切）。</div>
      </div>
      ${panels[T]()}`;
  }

  function blob(t) {
    return [t.symbolLabel, t.direction, t.heading,
      ...Object.values(t.rawSections || {}),
      JSON.stringify(t.setup || {}), JSON.stringify(t.analysis || {})].join(' ').toLowerCase();
  }
  function filtered() {
    let ts = state.data.trades.filter(inRange);
    if (state.q) { const q = state.q.toLowerCase(); ts = ts.filter((t) => blob(t).includes(q)); }
    const f = state.filters;
    if (f.symbol) ts = ts.filter((t) => t.symbolLabel === f.symbol);
    if (f.direction) ts = ts.filter((t) => t.direction === f.direction);
    if (f.result) ts = ts.filter((t) => t.resultStatus === f.result);
    if (f.model) ts = ts.filter((t) => (t.entryModel || {}).category === f.model);
    if (f.mistake) ts = ts.filter((t) => ((t.analysis || {}).mistakes || []).some((m) => m.tag === f.mistake));
    if (f.violation) ts = ts.filter((t) => ((t.analysis || {}).ruleViolations || []).some((m) => m.tag === f.violation));
    if (f.setup) ts = ts.filter((t) => setupTags(t).includes(f.setup));
    /* v3：§39 结构化维度组合筛选（值来自 fields，缺记录 = 不匹配，不补默认值） */
    const eqv = (t, key, want) => valTxt(fv(t, key)) === want;
    const hasv = (t, key, want) => {
      const f = fv(t, key); if (!f) return false;
      const vals = Array.isArray(f.value) ? f.value : [f.value];
      return vals.map(String).some((x) => x.split(' + ').map((y) => y.trim()).includes(want) || x === want);
    };
    const VF = [['entryMode', eqv], ['htfPOITF', hasv], ['ltfPOITF', hasv], ['marketCondition', eqv],
      ['liquiditySweep', eqv], ['displacementQuality', eqv], ['structureShiftType', hasv],
      ['brokenStructure', hasv], ['protectedStructure', eqv], ['targetLevel', hasv], ['managementStyle', hasv],
      ['ruleCompliance', eqv], ['shouldTake', eqv], ['tradeQuality', eqv], ['mistakes', hasv], ['reaction', eqv]];
    VF.forEach(([key, fn]) => { if (f[key]) ts = ts.filter((t) => fn(t, key, f[key])); });
    if (f.qv) ts = ts.filter((t) => (t.quality || {}).value === f.qv);
    return ts;
  }
  const ACTIVE = () => Object.keys(state.filters).filter((k) => state.filters[k]).length;

  /* ------------------------------------------------------------ 统计小条 */
  function keyStats(ts) {
    const closed = ts.filter((t) => ['win', 'loss', 'be'].includes(t.resultStatus));
    const rk = ts.filter((t) => t.rIncluded && t.actualR !== null);
    const wins = ts.filter((t) => t.resultStatus === 'win').length;
    const losses = ts.filter((t) => t.resultStatus === 'loss').length;
    const net = rk.reduce((a, t) => a + t.actualR, 0);
    const viol = ts.reduce((a, t) => a + ((t.analysis || {}).ruleViolations || []).length, 0);
    const miss = ts.filter((t) => (t.dataCompleteness || {}).percent < 100).length;
    const cell = (k, v, s) => `<div class="stat"><div class="k">${k}</div><div class="v">${v}</div>${s ? `<div class="s">${s}</div>` : ''}</div>`;
    return `<div class="stats stats-4">
      ${cell('Known Net R', rTxt(rk.length ? net : null), `${rk.length} 笔可计 R`)}
      ${cell('Win / Loss', `${wins} / ${losses}`, closed.length
        ? `Win Rate ${pct(wins / closed.length)}${ts.length > closed.length ? ` · ${ts.length - closed.length} 笔未结束` : ''}`
        : '无已结束交易')}
      ${cell('规则违反', viol ? `<span class="warnv">${viol}</span>` : '0', viol ? '点开交易看依据' : '全部通过')}
      ${cell('待补记录', miss, '完整度 < 100%')}
    </div>
    ${(() => { const D = V2().dashboard; if (!D) return '';
      const M = V2().maeMfe || {};
      return `<div class="stats stats-4">
        ${cell('Expectancy', D.expectancy === null || D.expectancy === undefined ? NR : rTxt(D.expectancy), '平均每笔期望值（§31）')}
        ${cell('Good Trade Rate', pct(D.goodTradeRate), `${D.goodWins || 0} 好 / ${D.trades || 0} 笔（§23）`)}
        ${cell('Rule Compliance', pct(D.ruleComplianceRate), D.ruleComplianceDecided ? `${D.ruleComplianceDecided} 笔有结论` : '还没有一笔有结论')}
        ${cell('Avg R', D.avgR === null || D.avgR === undefined ? NR : rTxt(D.avgR), `${D.rCounted || 0} 笔可计 R`)}
        ${cell('Profit Factor', D.profitFactor === null || D.profitFactor === undefined ? NR : Number(D.profitFactor).toFixed(2), '总盈利 R ÷ 总亏损 R（§27）')}
        ${cell('Trades', `${D.closed || 0} / ${D.trades || 0}`, '已结束 / 全部（§27）')}
        ${cell('Avg MAE / MFE', `${M.mae && M.mae.avg != null ? M.mae.avg.toFixed(2) : '—'} / ${M.mfe && M.mfe.avg != null ? '+' + M.mfe.avg.toFixed(2) : '—'}`, `已记录 ${M.recorded || 0} 笔`)}
      </div>`; })()}`;
  }

  /* ------------------------------------------------------------ Dashboard */
  function weekBlock(w, ts) {
    const wt = ts.filter((t) => w.tradeIds.includes(t.id));
    const rk = wt.filter((t) => t.rIncluded && t.actualR !== null);
    const net = rk.reduce((a, t) => a + t.actualR, 0);
    const rev = w.review || {};
    const more = [
      rev.repeatedMistake ? ['重复错误', rev.repeatedMistake.text] : null,
      rev.mainLesson ? ['本周教训', rev.mainLesson.text] : null,
      rev.missingDataNote ? ['缺记录', rev.missingDataNote] : null,
      w.bestTrade ? ['最好', `${w.bestTrade.symbolLabel} ${w.bestTrade.actualR !== null ? (w.bestTrade.actualR > 0 ? '+' : '') + w.bestTrade.actualR + 'R' : ''}`] : null,
      w.worstTrade ? ['最差', `${w.worstTrade.symbolLabel} ${w.worstTrade.actualR !== null ? (w.worstTrade.actualR > 0 ? '+' : '') + w.worstTrade.actualR + 'R' : ''}`] : null,
      w.missingData && w.missingData.length ? ['缺记录', w.missingData.map((m) => `${m.field}×${m.count}`).join('、')] : null,
      w.stats.rExcluded && w.stats.rExcluded.length ? ['R 未计入', w.stats.rExcluded.map((x) => x.symbolLabel).join('、')] : null,
    ].filter(Boolean);
    return `<div class="week" id="week-${esc(w.label)}">
      <div class="week-head">
        <div class="week-title">
          <h2><a href="#/week/${encodeURIComponent(w.label)}">${esc(w.label)}</a></h2>
          <span class="dates">${esc(w.start)} – ${esc(w.end)}</span>
        </div>
        <div class="week-nums">
          <span>${wt.length} 笔</span>
          <span>${wt.filter((t) => t.resultStatus === 'win').length} 胜 / ${wt.filter((t) => t.resultStatus === 'loss').length} 负</span>
          <span class="wk-r">${rTxt(rk.length ? net : null)}</span>
        </div>
      </div>
      ${weekV2(w)}
      ${(rev.mainStrength || rev.mainProblem || rev.newRule) ? `<div class="week-core">
        ${rev.mainStrength ? `<div class="wr good"><div class="k">做得好</div><div class="v">${esc(rev.mainStrength.text)}</div>${rev.mainStrength.evidence ? `<div class="ev">原文：${esc(rev.mainStrength.evidence)}</div>` : ''}</div>` : ''}
        ${rev.mainProblem ? `<div class="wr bad"><div class="k">主要问题</div><div class="v">${esc(rev.mainProblem.text)}</div>${rev.mainProblem.evidence ? `<div class="ev">原文：${esc(rev.mainProblem.evidence)}</div>` : ''}</div>` : ''}
        ${rev.newRule ? `<div class="wr rule"><div class="k">新规则</div><div class="v">${esc(rev.newRule.text)}</div>${rev.newRule.evidence ? `<div class="ev">原文：${esc(rev.newRule.evidence)}</div>` : ''}</div>` : ''}
      </div>` : ''}
      <div class="trows">${wt.map(tradeRow).join('')}</div>
      ${more.length ? `<details class="fold"><summary>周复盘其他条目</summary>
        <div class="kvraw-lite">${more.map(([k, v]) => `<div><b>${esc(k)}</b>${esc(v)}</div>`).join('')}</div></details>` : ''}
    </div>`;
  }

  /* ------------------------------------------------------------ 周 / 交易列表 */
  function weeksView(v) {
    const ts = filtered();
    const weeks = state.data.weeks.filter((w) => w.tradeIds.some((id) => ts.some((t) => t.id === id)));
    v.innerHTML = `<div class="sec"><h2>周复盘 <span class="hint">§二 已并入 Overview；这里保留完整周明细</span></h2>
      <div class="small muted" style="margin-bottom:8px"><a href="#/">← 回到 Overview</a></div>
      ${weeks.map((w) => weekBlock(w, ts)).join('')}</div>`;
  }
  function weekDetail(v, label) {
    const w = state.data.weeks.find((x) => x.label === label);
    if (!w) { v.innerHTML = '<div class="empty">找不到这个周。</div>'; return; }
    const ts = state.data.trades.filter((t) => w.tradeIds.includes(t.id));
    v.innerHTML = `<a class="small muted" href="#/weeks">← 全部周</a>${keyStats(ts)}${weekBlock(w, ts)}`;
  }
  function dimTable(key) {
    const D = (V2().dimensions || {})[key];
    if (!D || !(D.rows || []).length) return '';
    const rows = D.rows;
    const allUnrec = rows.every((r) => r.key === '(未记录)');
    return `<div class="panel"><h3>${esc(D.label || key)} <span class="hint small">${D.kind === 'multi' ? '多选 · 一笔可命中多项' : '单选'}</span></h3>
      <table class="plain"><thead><tr><th>值</th><th class="num">笔数</th><th class="num">可计 R</th><th class="num">胜率</th><th class="num">Avg R</th><th class="num">Net R</th><th class="num">Expectancy</th><th class="num">合规率</th></tr></thead><tbody>
      ${rows.map((r) => `<tr class="${r.key === '(未记录)' ? 'unrec' : ''}"><td>${esc(r.label || r.key)}<div class="small muted">${(r.trades || []).map((id) => `<a href="#/trade/${encodeURIComponent(id)}" style="text-decoration:underline">${esc(shortId(id))}</a>`).join(' · ')}</div>${r.sampleNote ? `<span class="srcb auto">${esc(r.sampleNote)}</span>` : ''}</td>
        <td class="num">${r.count}</td><td class="num">${r.rCounted}</td><td class="num">${r.winRate === null ? '—' : pct(r.winRate)}</td>
        <td class="num">${cellR(r.avgR)}</td><td class="num">${cellR(r.netR)}</td><td class="num">${cellR(r.expectancy)}</td>
        <td class="num">${r.complianceRate === null || r.complianceRate === undefined ? '—' : pct(r.complianceRate)}</td></tr>`).join('')}
      </tbody></table>
      ${allUnrec ? '<div class="small muted">这个维度目前一笔都没记录 —— 没有记录就没有统计。</div>' : ''}</div>`;
  }
  function freqBars(rows, total) {
    if (!rows || !rows.length) return '<div class="muted small">暂无</div>';
    const t = total || Math.max(...rows.map((r) => r.count));
    return `<div class="freq">${rows.map((r) => `<div class="frow"><div>${esc(r.label || r.key)} <span class="small muted">${r.count} 笔 · ${r.rCounted} 可计 R · ${cellR(r.expectancy)}</span></div>
      <div class="fbar"><i style="width:${Math.min(100, Math.round((r.count / Math.max(1, t)) * 100))}%"></i></div></div>`).join('')}</div>`;
  }

  /* ------------------------------------------------------------ Analytics（精简版） */
  function sparkline(curve) {
    if (!curve.length) return '<div class="muted small">暂无可计 R 的交易。</div>';
    const w = 560, h = 150, pad = 26;
    const xs = curve.map((_, i) => pad + i * ((w - pad * 2) / Math.max(1, curve.length - 1)));
    const vals = [0, ...curve.map((c) => c.cum)];
    const min = Math.min(...vals), max = Math.max(...vals);
    const y = (v) => h - pad - ((v - min) / (max - min || 1)) * (h - pad * 2);
    const pts = [[xs[0], y(0)], ...curve.map((c, i) => [xs[i], y(c.cum)])];
    const path = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' ');
    return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
      <line x1="${pad}" x2="${w - pad}" y1="${y(0)}" y2="${y(0)}" stroke="#dcdbd7" stroke-dasharray="3 3"/>
      <path d="${path}" fill="none" stroke="#345d8f" stroke-width="2"/>
      ${curve.map((c, i) => `<circle cx="${xs[i]}" cy="${y(c.cum)}" r="3.5" fill="#345d8f"><title>${esc(c.symbolLabel)} ${esc(c.date)} ${c.r > 0 ? '+' : ''}${c.r}R → 累计 ${c.cum}R</title></circle>`).join('')}</svg>`;
  }
  function perfTable(rows, firstCol) {
    if (!rows.length) return '<div class="muted small">暂无数据</div>';
    return `<table class="plain"><thead><tr><th>${esc(firstCol)}</th><th class="num">笔数</th><th class="num">胜率</th><th class="num">Avg R</th><th class="num">Net R</th></tr></thead>
      <tbody>${rows.map((r) => `<tr><td>${esc(r.key)}<div class="small muted">${r.trades.map((id) => `<a href="#/trade/${encodeURIComponent(id)}" style="text-decoration:underline">${esc(shortId(id))}</a>`).join(' · ')}</div></td>
        <td class="num">${r.count}</td><td class="num">${r.winRate === null ? '—' : pct(r.winRate)}</td>
        <td class="num">${r.avgR === null ? '—' : (r.avgR > 0 ? '+' : '') + r.avgR + 'R'}</td>
        <td class="num">${r.netR === null ? '—' : (r.netR > 0 ? '+' : '') + r.netR + 'R'}</td></tr>`).join('')}</tbody></table>`;
  }
  function rulesView(v) {
    const R = state.data.rules;
    const cats = R.categories.filter((c) => R.generated.some((g) => g.category === c));
    v.innerHTML = `
      <div class="sec"><h2>我的规则 <span class="hint">${R.generated.length} 条从交易里长出来的</span></h2>
        ${cats.map((c) => { const gs = R.generated.filter((g) => g.category === c); return `<div class="panel" style="margin-bottom:12px"><h3>${esc(c)} <span class="hint small">${gs.length} 条</span></h3>
          ${gs.map((g) => `<div class="callout rule-item">${esc(g.text)}
            <div class="small muted" style="margin-top:4px">来自 <a href="#/trade/${encodeURIComponent(g.createdFrom)}" style="text-decoration:underline">${esc(g.createdFromLabel)}</a></div>
          </div>`).join('')}</div>`; }).join('') || '<div class="muted small">暂无</div>'}
      </div>
      ${rulesBuckets()}
      <details class="fold"><summary>文档里原有的规则与固定复盘模板</summary>
        <div class="analytics-grid" style="margin-top:10px">
          <div class="panel"><h3>SMC 执行规则（原文）</h3>
            ${R.doc.map((r) => `<div class="callout" style="margin-bottom:8px"><b>${esc(r.title)}</b><div class="small" style="margin-top:4px">${esc(r.body)}</div></div>`).join('') || '<div class="muted small">未记录</div>'}</div>
          <div class="panel"><h3>固定复盘模板</h3><ol class="reasons">${R.template.map((x) => `<li>${esc(typeof x === 'string' ? x : (x.text || x.label || ''))}</li>`).join('')}</ol></div>
        </div>
      </details>`;
  }


  /* ---- Rules 三桶 + 每笔联动统计（§33 / §34） ---- */
  function rulesBuckets() {
    const B = state.data.ruleBuckets || {};
    const groups = state.data.trades.map((t) => (t.complianceV2 || {}).groups).filter(Boolean);
    const stat = (bucket, id) => {
      const s = { pass: 0, fail: 0, unknown: 0 };
      groups.forEach((g) => (g[bucket] || []).forEach((i) => {
        if (i.id !== id) return;
        if (i.status === '✓') s.pass++; else if (i.status === '✕') s.fail++; else s.unknown++;
      }));
      return s;
    };
    const panel = (name, items, note) => `<div class="panel"><h3>${esc(name)} <span class="hint small">${items.length} 条</span></h3>
      <div class="small muted" style="margin-bottom:8px">${esc(note)}</div>
      ${items.map((it) => { const s = stat(name, it.id); return `<div class="rline"><div class="txt">${esc(it.text)}<div class="small muted">判定字段：${esc((FBYK()[it.field] || {}).label || it.field)}</div></div>
        <div class="cnt">${s.pass ? `<span class="chip win">✓ ${s.pass}</span>` : ''}${s.fail ? `<span class="chip loss">✕ ${s.fail}</span>` : ''}<span class="chip ghost">未记录 ${s.unknown}</span></div></div>`; }).join('')}</div>`;
    return `<div class="sec"><h2>规则清单 <span class="hint">§33 / §34 · 每笔交易按这三桶自动打勾</span></h2>
      <div class="callout small">这三桶就是 Rule Checklist 的判定来源：命中 Avoid 或缺少 Must Have 里的记录，合规度会相应降级；三桶里有「未记录」项时系统不下结论。</div>
      <div class="three">
        ${panel('Must Have', B['Must Have'] || [], '缺一项就不该进场。')}
        ${panel('Confirmation', B['Confirmation'] || [], '不是每笔都要全有，但要有记录才能统计它是否有效。')}
        ${panel('Avoid', B['Avoid'] || [], '命中即执行问题。')}
      </div></div>`;
  }
  /* ---- 周报 v2（§32） ---- */
  function weekV2(w) {
    const W = V2W(w.label);
    if (!W) return '';
    const num2 = (v, unit) => (v === null || v === undefined ? '<span class="muted">未记录</span>' : Number(v).toFixed(2) + (unit || ''));
    const cell = (k, v) => `<div class="wkv"><div class="k">${esc(k)}</div><div class="v">${v}</div></div>`;
    return `<div class="week-v2">
      ${cell('Expectancy', cellR(W.expectancy))}
      ${cell('Good Trade Rate', pct(W.goodTradeRate))}
      ${cell('Rule Compliance', pct(W.ruleComplianceRate))}
      ${cell('Avg MAE / MFE', `${num2(W.avgMAE)} / ${num2(W.avgMFE)}`)}
      ${cell('最佳 Setup', W.bestSetup ? `${esc(short(W.bestSetup.setup, 42))}（${cellR(W.bestSetup.netR)}）` : '<span class="muted">未记录</span>')}
      ${cell('最大错误', W.biggestMistake ? esc(W.biggestMistake.tag || W.biggestMistake) : '<span class="muted">未记录</span>')}
      ${cell('错误损失 R', W.mistakeLostR === null || W.mistakeLostR === undefined ? '<span class="muted">未记录</span>' : cellR(W.mistakeLostR))}
      </div>
      ${(W.didWell || W.mainProblem || W.nextFocus) ? `<div class="week-core">
        ${W.didWell ? `<div class="wr good"><div class="k">This Week I Did Well</div><div class="v">${esc(W.didWell)}</div></div>` : ''}
        ${W.mainProblem ? `<div class="wr bad"><div class="k">Main Problem</div><div class="v">${esc(W.mainProblem)}</div></div>` : ''}
        ${W.nextFocus ? `<div class="wr rule"><div class="k">Next Week Focus</div><div class="v">${esc(W.nextFocus)}</div></div>` : ''}
      </div>` : `<div class="small muted" style="margin:6px 0 0">本周的「做得好 / 主要问题 / 下周重点」还没记录 —— 在本地编辑器（tag）里补，或按 docs/record-template.md 写进下周文档。</div>`}
      ${W.sampleNote ? `<div class="small muted" style="margin-top:4px">${esc(W.sampleNote)}</div>` : ''}`;
  }
  const uniqF = (key) => {
    const out = [];
    state.data.trades.forEach((t) => {
      const f = fv(t, key); if (!f) return;
      (Array.isArray(f.value) ? f.value : [f.value]).forEach((v) => String(v).split(' + ').map((x) => x.trim()).forEach((x) => { if (x && !out.includes(x)) out.push(x); }));
    });
    return out;
  };

  /* ------------------------------------------------------------ Lightbox */
  let LB = { imgs: [], i: 0, id: null };
  function initLightbox() {
    $('#lb-close').addEventListener('click', closeLightbox);
    $('#lb-prev').addEventListener('click', (e) => { e.stopPropagation(); stepLightbox(-1); });
    $('#lb-next').addEventListener('click', (e) => { e.stopPropagation(); stepLightbox(1); });
    $('#lb-stage').addEventListener('click', () => $('#lb-stage').classList.toggle('zoom'));
    $('#lightbox').addEventListener('click', (e) => { if (e.target.id === 'lightbox') closeLightbox(); });
    document.addEventListener('keydown', (e) => {
      if ($('#lightbox').hidden) return;
      if (e.key === 'Escape') closeLightbox();
      if (e.key === 'ArrowLeft') stepLightbox(-1);
      if (e.key === 'ArrowRight') stepLightbox(1);
    });
  }
  function openLightbox(t, i) { LB = { imgs: t.images || [], i, id: t.id }; drawLightbox(); $('#lightbox').hidden = false; }
  function stepLightbox(d) { if (!LB.imgs.length) return; LB.i = (LB.i + d + LB.imgs.length) % LB.imgs.length; drawLightbox(); }
  function drawLightbox() {
    const cur = LB.imgs[LB.i]; if (!cur) return;
    $('#lb-img').src = cur.path;
    $('#lb-cap').textContent = `${LB.imgs.length > 1 ? `(${LB.i + 1}/${LB.imgs.length}) ` : ''}${cur.caption || ''}`;
    $('#lb-stage').classList.remove('zoom');
    const multi = LB.imgs.length > 1;
    $('#lb-prev').style.display = multi ? '' : 'none';
    $('#lb-next').style.display = multi ? '' : 'none';
  }
  function closeLightbox() { $('#lightbox').hidden = true; $('#lb-img').src = ''; }
})();
