/* Trading Review — 前端（零依赖，静态 JSON 驱动）
   设计原则：一屏只回答三个问题 —— 这笔为什么做 / 结果怎样 / 下次怎么改。
   其余原始字段一律折叠进「原始记录」，不抢戏，但一个都不丢。 */
(() => {
  const state = { data: null, range: 'all', q: '', filters: {} };
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
    [...$('#nav').children].forEach((a) => a.classList.toggle('on', a.dataset.nav === (parts[0] || 'dashboard')));
    const view = $('#view');
    window.scrollTo(0, 0);
    if (parts.length === 0) return dashboard(view);
    switch (parts[0]) {
      case 'weeks': return parts[1] ? weekDetail(view, decodeURIComponent(parts[1])) : weeksView(view);
      case 'trades': return tradesView(view);
      case 'trade': return tradeDetail(view, decodeURIComponent(parts[1] || ''));
      case 'analytics': return analyticsView(view);
      case 'rules': return rulesView(view);
      default: return dashboard(view);
    }
  }

  /* ------------------------------------------------------------ 过滤 */
  function inRange(t) {
    const d = (t.entryTime || '').slice(0, 10);
    if (!d || state.range === 'all') return true;
    const now = new Date();
    if (state.range === 'month') return d >= `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`;
    const day = now.getDay() || 7;
    const mon = new Date(now.getTime() - (day - 1) * 864e5);
    return d >= mon.toISOString().slice(0, 10);
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
  function dashboard(view) {
    const ts = filtered();
    const weeks = state.data.weeks.filter((w) => w.tradeIds.some((id) => ts.some((t) => t.id === id)));
    const top = state.data.analytics.mistakeFrequency.filter((m) => m.count > 1).slice(0, 1)[0];
    const recentRules = state.data.rules.generated.slice(-2).reverse();
    view.innerHTML = `
      ${keyStats(ts)}
      ${ACTIVE() || state.q ? `<div class="sec"><div class="callout">当前筛选：${[
        state.q ? `搜索「${esc(state.q)}」` : '',
        ...Object.entries(state.filters).filter(([, v]) => v).map(([k, v]) => `${esc(k)}=${esc(v)}`),
      ].filter(Boolean).join(' · ')} —— 命中 ${ts.length} 笔。</div></div>` : ''}
      ${answersPanel()}
      ${top || recentRules.length ? `<div class="sec"><div class="analytics-grid">
        ${top ? `<div class="panel"><h3>最该盯的重复错误</h3>
          <div class="callout warn"><b>${esc(top.key)}</b> · 已出现 ${top.count} 次
          <div class="small" style="margin-top:4px">${top.trades.map((id) => `<a href="#/trade/${encodeURIComponent(id)}" style="text-decoration:underline">${esc(shortId(id))}</a>`).join(' · ')}</div></div></div>` : ''}
        ${recentRules.length ? `<div class="panel"><h3>最近长出来的规则</h3>
          ${recentRules.map((r) => `<div class="callout">${esc(short(r.text, 120))}
            <div class="small muted" style="margin-top:4px">来自 <a href="#/trade/${encodeURIComponent(r.createdFrom)}" style="text-decoration:underline">${esc(r.createdFromLabel)}</a></div></div>`).join('')}</div>` : ''}
      </div></div>` : ''}
      <div class="sec">
        <h2>Weeks <span class="hint">点一行进单笔复盘</span></h2>
        ${weeks.length ? weeks.map((w) => weekBlock(w, ts)).join('') : '<div class="empty">该筛选条件下没有交易。</div>'}
      </div>`;
  }

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

  /* 一笔交易 = 一行 */
  function tradeRow(t) {
    const r = t.review || {};
    const m0 = (((t.analysis || {}).mistakes) || [])[0];
    const note = short(r.mainProblem || (r.improve || [])[0] || (r.worked || [])[0]
      || (t.entryReasonItems || [])[0] || (m0 ? m0.tag + '（文档未写复盘要点）' : '文档未写复盘要点'), 78);
    const viol = ((t.analysis || {}).ruleViolations || []).length;
    const bad = t.resultStatus === 'loss' || viol;
    return `<a class="trow" href="#/trade/${encodeURIComponent(t.id)}">
      <span class="td d">${esc(dateOf(t))}</span>
      <span class="td sym">${esc(t.symbolLabel)} <span class="muted">${dirWord(t.direction)}</span></span>
      <span class="td r">${t.actualR !== null ? rTxt(t.actualR) : `<span class="small muted">${['win','loss','be'].includes(t.resultStatus) ? 'R 未计入' : '未结束'}</span>`}</span>
      <span class="td res">${resChip(t)}${viol ? `<span class="chip warn">⚠ ${viol}</span>` : ''}</span>
      <span class="td note ${bad ? 'bad' : ''}">${esc(note)}</span>
      <span class="td go">›</span>
    </a>`;
  }

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
    v.innerHTML = `<div class="sec"><h2>Weeks</h2>
      ${weeks.map((w) => weekBlock(w, ts)).join('')}</div>
      ${allTradesFold(ts)}`;
  }
  function weekDetail(v, label) {
    const w = state.data.weeks.find((x) => x.label === label);
    if (!w) { v.innerHTML = '<div class="empty">找不到这个周。</div>'; return; }
    const ts = state.data.trades.filter((t) => w.tradeIds.includes(t.id));
    v.innerHTML = `<a class="small muted" href="#/weeks">← 全部周</a>${keyStats(ts)}${weekBlock(w, ts)}`;
  }
  function tradesView(v) {
    const ts = filtered();
    const uniq = (k) => [...new Set(state.data.trades.map(k).filter(Boolean))];
    const chips = (key, opts, fmt = (x) => x) => `<div class="filt">${opts.map((o) =>
      `<a class="chip tag ${state.filters[key] === o ? 'on' : ''}" href="#/trades${qs({ ...state.filters, [key]: state.filters[key] === o ? null : o })}">${esc(fmt(o))}</a>`).join('')}</div>`;
    v.innerHTML = `
      <div class="sec"><h2>Trades <span class="hint">${ts.length} / ${state.data.trades.length} 笔</span></h2>
        ${chips('result', ['win', 'loss', 'be'], (x) => ({ win: 'Win', loss: 'Loss', be: 'BE' }[x]))}
        ${chips('symbol', uniq((t) => t.symbolLabel))}
        ${chips('setup', [...new Set(state.data.trades.flatMap(setupTags))])}
        ${chips('mistake', [...new Set(state.data.analytics.mistakeFrequency.map((m) => m.key))])}
        ${chips('violation', [...new Set(state.data.analytics.violationFrequency.map((m) => m.key))])}
        <details class="fold" open><summary>结构化筛选（§39 组合筛选）</summary>
          <div style="margin-top:8px">
            ${[['entryMode', '入场方式'], ['htfPOITF', 'HTF POI 周期'], ['ltfPOITF', 'LTF Entry POI 周期'],
               ['marketCondition', '市场环境'], ['liquiditySweep', 'Sweep'], ['displacementQuality', 'Displacement'],
               ['structureShiftType', '结构变化'], ['brokenStructure', '被破坏的结构'], ['protectedStructure', 'Protected 结构'],
               ['targetLevel', 'Target 层级'], ['ruleCompliance', 'Rule Compliance'], ['shouldTake', '该不该做'], ['tradeQuality', 'Trade Quality']]
              .map(([key, lab]) => { const vals = uniqF(key); return vals.length ? `<div class="frowline"><span class="fl">${esc(lab)}</span>${chips(key, vals)}</div>` : ''; }).join('')}
            <div class="frowline"><span class="fl">错误标签（字段）</span>${chips('mistakes', uniqF('mistakes'))}</div>
          </div>
        </details>
        <div style="margin-top:12px">${keyStats(ts)}</div>
      </div>
      <div class="sec trows">${ts.length ? ts.map(tradeRow).join('') : '<div class="empty">没有符合条件的交易。</div>'}</div>`;
  }
  const qs = (o) => {
    const s = new URLSearchParams(Object.entries(o).filter(([, v]) => v !== null && v !== undefined && v !== ''));
    const str = s.toString();
    return str ? '?' + str : '';
  };
  function allTradesFold(ts) {
    return `<div class="sec"><h2>所有交易</h2><div class="trows">${ts.map(tradeRow).join('')}</div></div>`;
  }

  /* ------------------------------------------------------------ 单笔复盘（核心页） */
  function tradeDetail(v, id) {
    const t = state.data.trades.find((x) => x.id === id);
    if (!t) { v.innerHTML = '<div class="empty">找不到这笔交易。</div>'; return; }
    const a = t.analysis || {}, imgs = t.images || [], r = t.review || {};
    const lens = (t.context && t.context.timeframes) || [];
    const viol = a.ruleViolations || [];
    const fails = (a.riskCheck || []).filter((i) => i.status === 'fail');
    const improve = [...(r.improve || [])];
    v.innerHTML = `
      <a class="small muted" href="#/week/${encodeURIComponent(t.week.label)}">← ${esc(t.week.label)}</a>

      <div class="td-head">
        <div class="td-title">
          <h1>${esc(t.symbolLabel)} <span class="d-${esc(t.direction)}">${dirWord(t.direction).toUpperCase()}</span></h1>
          <div class="sub">${esc(t.entryTimeLabel || '')}${t.exitTimeLabel ? ' → ' + esc(t.exitTimeLabel) : ''}
            ${t.holdingLabel ? ` · 持仓 ${esc(t.holdingLabel)}` : ''}</div>
        </div>
        <div class="td-r">${t.actualR !== null ? rTxt(t.actualR) : NR}${resChip(t)}</div>
      </div>

      <div class="pricebar">
        <span><i>Entry</i><b>${num(t.entry)}</b></span>
        <span><i>SL</i><b>${num(t.stopLoss)}</b></span>
        <span><i>TP / Exit</i><b>${t.exit !== null ? num(t.exit) : (t.stopLoss !== null && t.resultStatus === 'loss' ? '止损出场' : NR)}</b></span>
        ${(t.targets || []).length ? `<span><i>计划 TP</i><b>${esc((t.targets || []).map((x) => x.priceText).filter(Boolean).join(' / '))}</b></span>` : ''}
        <span><i>Planned RR</i><b>${t.plannedRRText ? esc(t.plannedRRText.replace(/^计划\s*RR\s*/, '')) : (t.plannedRR !== null ? esc(t.plannedRR) + 'R' : NR)}</b></span>
        <span><i>Entry Model</i><b>${esc((t.entryModel || {}).label || '未记录')}</b></span>
      </div>

      ${(t.mae || t.mfe || t.fees !== null) ? `<div class="pricebar" style="margin-top:8px">
        ${t.mae ? `<span><i>MAE 最大浮亏</i><b>${esc(t.mae.raw)}</b></span>` : ''}
        ${t.mfe ? `<span><i>MFE 最大浮盈</i><b>${esc(t.mfe.raw)}</b></span>` : ''}
        ${t.pnl !== null ? `<span><i>PnL</i><b>${esc(t.pnl)}</b></span>` : ''}
        ${t.fees !== null ? `<span><i>Fees</i><b>${esc(t.fees)}</b></span>` : ''}
      </div>` : ''}
      ${imgs.length ? `<div class="card chart-wrap" style="margin-top:14px">
        <img class="chart-main" id="main-chart" src="${esc(imgs[0].path)}" alt="${esc(t.symbolLabel)} 图表">
        <div class="chart-bar"><span>${esc(imgs[0].caption || '文档内嵌交易图')}（点击放大）</span>
          <span>${imgs[0].type ? `分类：${esc(imgs[0].type)}${imgs[0].timeframe ? ' · ' + esc(imgs[0].timeframe) : ''}` : '分类：未标注（§24 四类之一）'}${imgs[0].kindSource === 'manual' ? ' · 手填' : ''}</span>
          <span>${lens.length ? '参考周期 ' + esc(lens.join('/').toUpperCase()) : ''}</span></div>
        ${imgs.length > 1 ? `<div class="gallery">${imgs.map((i, n) => `<figure class="gal-item"><img src="${esc(i.path)}" data-lb="${n}" alt="图 ${n + 1}"><figcaption>${esc(imgKind(i))}</figcaption></figure>`).join('')}</div>` : ''}
        <div class="imgstrip small">${imgStrip(imgs, t)}</div>
      </div>` : '<div class="empty">这笔交易还没有绑定图表。</div>'}

      ${chainBlock(t)}
      ${checklistBlock(t)}
      ${plannedActualBlock(t)}
      ${maeMfeBlock(t)}

      <div class="logic-line">
        ${(t.setup.flow || []).length ? `<div class="flow">${t.setup.flow.map((x, i) => `${i ? '<span class="arw">→</span>' : ''}<span class="step">${esc(x)}</span>`).join('')}</div>` : ''}
        <div class="badges-row">${poiChips(t.poi)}${(a.mistakes || []).map((m) => `<span class="chip warn">${esc(m.tag)}</span>`).join('')}${viol.map((x) => `<span class="chip warn">⚠ ${esc(x.tag)}</span>`).join('')}</div>
      </div>

      <div class="three">
        <div class="panel good"><h3>① 做对了什么</h3>
          ${(r.worked || []).length ? `<ul class="reasons">${r.worked.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>`
            : `<div class="muted small">未记录。${t.resultStatus === 'loss' ? '亏损交易也一定有做对的地方。' : ''}</div>`}</div>

        <div class="panel bad"><h3>② 问题在哪</h3>
          ${improve.length ? `<ul class="reasons">${improve.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}
          ${r.mainProblem ? `<div class="callout warn"><b>主要问题：</b>${esc(r.mainProblem)}</div>` : ''}
          ${!improve.length && !r.mainProblem ? '<div class="muted small">未记录。</div>' : ''}
          ${fails.length ? `<div class="small" style="margin-top:8px">规则卡点未过：${fails.map((f) => `<span class="chip warn">${esc(f.label)}</span>`).join(' ')}</div>` : ''}
          ${(a.mistakes || []).length ? `<div class="small muted" style="margin-top:8px">AI 归类：${a.mistakes.map((m) => `“${esc(m.evidence)}”`).join(' / ')}</div>` : ''}
          ${a.classification ? `<div class="small muted" style="margin-top:6px">结果分类：<b>${esc(a.classification.value)}</b> —— ${esc(a.classification.reason)}</div>` : ''}</div>

        <div class="panel rule"><h3>③ 下次怎么做</h3>
          ${(r.nextRules || []).length ? `<ul class="reasons">${r.nextRules.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>`
            : '<div class="muted small">未记录。这一格空着，下次大概率还会犯同一个错。</div>'}</div>
      </div>

      <details class="fold">
        <summary>原始记录（为什么不这样写 / 当时看到什么 / 所有已记字段）</summary>
        <div class="rawgrid">
          ${(t.sectionsLabeled || []).length ? `<div class="panel span2"><h3>文档逐字段原文</h3>
            ${t.sectionsLabeled.map((x) => `<div class="kvraw"><b>${esc(x.label)}</b>${esc(x.text || '')}</div>`).join('')}</div>` : ''}
          ${(t.liquidity || t.displacement || (t.poi || []).length) ? `<div class="panel"><h3>Liquidity / Displacement / POI</h3>
            <div class="badges-row">
              ${t.liquidity ? `<span class="chip ${t.liquidity.sslSwept ? 'win' : 'ghost'}">SSL ${t.liquidity.sslSwept ? '已扫' : '未记录'}</span>` : ''}
              ${t.liquidity && t.liquidity.bslTarget ? `<span class="chip">BSL ${esc(t.liquidity.bslTarget)}</span>` : ''}
              ${t.displacement ? `<span class="chip ${t.displacement.strength === 'strong' ? 'win' : 'warn'}">${esc(t.displacement.type || 'Displacement')} · ${t.displacement.strength === 'strong' ? 'Strong' : t.displacement.strength === 'weak' ? 'Weak' : '未记录'}</span>` : ''}
              ${poiChips(t.poi)}
            </div></div>` : ''}
          ${(t.entryReason || []).length ? `<div class="panel"><h3>Entry Reasons</h3><ul class="reasons">${t.entryReason.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></div>` : ''}
          ${t.entryTrigger && (t.entryTrigger.text || t.entryTrigger.raw) ? `<div class="panel"><h3>Entry Trigger</h3><div class="raw">${esc(t.entryTrigger.text || t.entryTrigger.raw)}</div></div>` : ''}
          ${(t.targets || []).length ? `<div class="panel"><h3>Targets</h3><table class="plain"><thead><tr><th>Level</th><th>Price</th><th>Type</th></tr></thead><tbody>
            ${t.targets.map((x) => `<tr><td>${esc(x.label)}</td><td>${esc(x.priceText || (x.priceLow != null ? x.priceLow : '')) || NR}</td><td>${(x.types || []).map((y) => `<span class="chip">${esc(y)}</span>`).join(' ') || NR}</td></tr>`).join('')}</tbody></table></div>` : ''}
          ${(a.riskCheck || []).length ? `<div class="panel"><h3>下单前风控自查</h3><div class="check">
            ${(a.riskCheck || []).map((i) => `<div class="row ${i.status}"><span class="ic">${({ pass: '✔', fail: '✘', partial: '~', unknown: '?' })[i.status]}</span>
              <div class="lab"><b>${esc(i.label)}</b> <span class="small muted">${({ pass: '通过', fail: '违反', partial: '部分', unknown: '未知' })[i.status]}</span>
              ${i.evidence ? `<div class="ev">“${esc(i.evidence)}”</div>` : ''}${i.note ? `<div class="ev">${esc(i.note)}</div>` : ''}</div></div>`).join('')}</div></div>` : ''}
          ${t.mae !== null || t.mfe !== null || t.fees !== null || t.pnl !== null ? `<div class="panel"><h3>结果明细</h3><div class="kv">
            <div><div class="k">MAE</div><div class="v">${nr(t.mae)}</div></div>
            <div><div class="k">MFE</div><div class="v">${nr(t.mfe)}</div></div>
            <div><div class="k">PnL</div><div class="v">${nr(t.pnl)}</div></div>
            <div><div class="k">Fees</div><div class="v">${nr(t.fees)}</div></div></div></div>` : ''}
          ${Object.keys(t.rawSections || {}).length ? `<div class="panel"><h3>Google Docs 原文</h3>
            ${Object.entries(t.rawSections).map(([k, vv]) => `<div class="kvraw"><b>${esc(k)}</b>${esc(Array.isArray(vv) ? vv.join(' / ') : vv)}</div>`).join('')}</div>` : ''}
        </div>
        <div class="small muted" style="margin-top:8px">数据完整度 ${t.dataCompleteness ? t.dataCompleteness.percent : '—'}%${t.dataCompleteness && t.dataCompleteness.missing.length ? ` · 缺：${esc(t.dataCompleteness.missing.join('、'))}` : ''}
          ${!t.rIncluded ? ` · <b>本笔不计入 R 统计</b>：${esc(t.rExcludeReason || '缺少可计算的 SL / 实际 R')}` : ''}
          · 版本 <span class="mono">${esc(t.id)}</span></div>
      </details>`;

    if (imgs.length) {
      $('#main-chart').addEventListener('click', () => openLightbox(t, 0));
      v.querySelectorAll('[data-lb]').forEach((el) => el.addEventListener('click', () => openLightbox(t, +el.dataset.lb)));
    }
  }


  /* ---- Analytics v2：全维度表（§28 P2） ---- */
  const cellR = (v) => (v === null || v === undefined ? '—' : (v > 0 ? '+' : '') + Number(v).toFixed(2) + 'R');
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
  function analyticsV2() {
    const D = V2(), dims = D.dimensions || {}, order = D.dimensionOrder || [];
    const M = D.mistakes || {}, S = D.strategyVsExecution || {}, MM = D.maeMfe || {}, tf = D.timeframes || {};
    const NUM = D.numeric || [], IMGS = D.images || {};
    const FOCUS = ['structureShiftType', 'entryMode', 'htfPOITF', 'ltfPOITF', 'marketCondition', 'liquiditySweep',
      'liquiditySweep', 'sweepQuality', 'displacementQuality', 'brokenStructure', 'protectedStructure', 'ruleCompliance', 'tradeQuality', 'shouldTake'];
    const focus = [...new Set(FOCUS)].filter((k) => dims[k]);
    const rest = order.filter((k) => !focus.includes(k));
    const group = (k) => (FBYK()[k] || {}).group || '其他';
    const groups = {};
    rest.forEach((k) => { (groups[group(k)] = groups[group(k)] || []).push(k); });
    const mk = (r) => `<tr><td>${esc(r.tag)}<span class="srcb">${esc(r.category || '其他')}</span>${r.unconfirmed ? '<span class="srcb auto">建议·待确认</span>' : ''}<div class="small muted">${(r.trades || []).map((id) => `<a href="#/trade/${encodeURIComponent(id)}" style="text-decoration:underline">${esc(shortId(id))}</a>`).join(' · ')}</div></td>
      <td class="num">${r.count}</td><td class="num">${r.confirmedCount || 0}</td><td class="num">${r.rCounted}</td><td class="num">${cellR(r.lostR)}</td></tr>`;
    return `
    <div class="sec"><h2>结构化 Analytics <span class="hint">§28 全维度 · 缺记录的行一律单列，不参与平均</span></h2>
      <div class="analytics-grid">
        <div class="panel span2"><h3>策略问题 vs 执行问题 <span class="hint small">§4.3</span></h3>
          <div class="badges-row">
            <span class="chip loss">违规亏损 ${S.badLoss ? S.badLoss.count : 0} 笔 · ${S.badLoss ? S.badLoss.r.toFixed(2) : '0'}R</span>
            <span class="chip">规则内亏损 ${S.goodLoss ? S.goodLoss.count : 0} 笔 · ${S.goodLoss ? S.goodLoss.r.toFixed(2) : '0'}R</span>
            <span class="chip ghost">无判定 ${S.unknownQuality ? S.unknownQuality.count : 0} 笔</span></div>
          <div class="small muted" style="margin-top:8px">${esc(S.note || '')}<br>违规造成的亏损才是系统要重点发现的问题，规则内的亏损是策略成本。</div></div>
        <div class="panel"><h3>Expectancy / 结论口径</h3>
          <div class="kv"><div><div class="k">Expectancy</div><div class="v">${cellR((D.dashboard || {}).expectancy)}</div></div>
            <div><div class="k">Good Trade Rate</div><div class="v">${pct((D.dashboard || {}).goodTradeRate)}</div></div>
            <div><div class="k">Rule Compliance</div><div class="v">${pct((D.dashboard || {}).ruleComplianceRate)}</div></div>
            <div><div class="k">Profit Factor</div><div class="v">${(D.dashboard || {}).profitFactor === null || (D.dashboard || {}).profitFactor === undefined ? NR : Number(D.dashboard.profitFactor).toFixed(2)}</div></div></div></div>
        <div class="panel"><h3>MAE / MFE 分析 <span class="hint small">§29</span></h3>
          <div class="kv"><div><div class="k">平均 MAE</div><div class="v">${cellR(MM.avgMAE)}</div></div>
            <div><div class="k">平均 MFE</div><div class="v">${cellR(MM.avgMFE)}</div></div>
            <div><div class="k">盈利单 MAE</div><div class="v">${cellR(MM.winMAE)}</div></div>
            <div><div class="k">亏损单 MFE</div><div class="v">${cellR(MM.lossMFE)}</div></div></div>
          <div class="small muted" style="margin-top:8px">${esc(MM.note || '')}</div></div>
        <div class="panel"><h3>数值字段 <span class="hint small">§13 Protected Price / §19 MAE·MFE</span></h3>
          ${NUM.length ? `<table class="plain"><thead><tr><th>字段</th><th class="num">已记录</th><th class="num">平均</th><th class="num">范围</th></tr></thead><tbody>
            ${NUM.map((n) => `<tr><td>${esc(n.label)}<span class="srcb">${esc(n.group || '其他')}</span></td>
              <td class="num">${n.recorded}/${n.total}</td>
              <td class="num">${n.avg === null ? NR : (n.avg > 0 ? '+' : '') + n.avg + (n.unit ? ' ' + esc(n.unit) : '')}</td>
              <td class="num">${n.min === null ? NR : n.min + ' ~ ' + n.max}</td></tr>`).join('')}
            </tbody></table><div class="small muted" style="margin-top:6px">没记录的行不计入平均，也不补 0（§4.1）。</div>`
            : '<div class="muted small">没有数值字段定义。</div>'}</div>
        <div class="panel"><h3>截图分类 <span class="hint small">§24</span></h3>
          ${(IMGS.rows || []).length ? `<div class="kv">${IMGS.rows.map((r) => `<div><div class="k">${esc(IMG_KIND_WORD[r.kind] || r.kind)}</div>
              <div class="v">${r.count} 张<span class="srcb">${esc(Object.keys(r.tf || {}).join('/') || '周期未标')}</span></div></div>`).join('')}</div>`
            : '<div class="muted small">还没有分类记录。</div>'}
          <div class="small muted" style="margin-top:8px">共 ${IMGS.total || 0} 张 · 已分类 ${IMGS.labeled || 0} · 未分类 ${IMGS.unlabeled || 0}。分类在本地编辑器「截图分类」页勾选。</div></div>
        <div class="panel"><h3>错误标签统计 <span class="hint small">§22 / §28</span></h3>
          ${(M.rows || []).length ? `<table class="plain"><thead><tr><th>错误</th><th class="num">出现</th><th class="num">已确认</th><th class="num">可计 R</th><th class="num">Lost R</th></tr></thead><tbody>${M.rows.map(mk).join('')}</tbody></table>
            <div class="small muted" style="margin-top:6px">最常出现：<b>${esc(M.mostCommon || '未记录')}</b>${M.costliest ? ` · 损失最大：<b>${esc(M.costliest.tag)}</b>（${M.costliest.lostR === null ? 'R 未计' : M.costliest.lostR.toFixed(2) + 'R'}）` : ''}</div>`
            : '<div class="muted small">文档里没有错误标签记录。</div>'}</div>
        <div class="panel span2"><h3>周期使用 <span class="hint small">§2 HTF 固定 1D/4H/1H · LTF 固定 15min/5min</span></h3>
          <div class="three"><div><div class="small muted">HTF 使用分布</div>${freqBars(tf.HTFUsage, (D.dashboard || {}).trades)}</div>
          <div><div class="small muted">LTF 使用分布</div>${freqBars(tf.LTFUsage, (D.dashboard || {}).trades)}</div>
          <div><div class="small muted">Entry 周期（§28 15min vs 5min）</div>${freqBars(dims.entryTriggerTF ? dims.entryTriggerTF.rows : (dims.ltfPOITF ? dims.ltfPOITF.rows : []), (D.dashboard || {}).trades)}</div></div></div>
      </div>
      <div class="analytics-grid" style="margin-top:12px">${focus.map(dimTable).join('')}</div>
      <details class="fold"><summary>其余维度表（${rest.length} 个：HTF/LTF 逐项对比）</summary>
        <div style="margin-top:10px">${Object.keys(groups).map((g) => `<h3 class="dimgroup">${esc(g)}</h3><div class="analytics-grid">${groups[g].map(dimTable).join('')}</div>`).join('')}
        ${(D.emptyDimensions || []).length ? `<div class="callout small">以下 ${D.emptyDimensions.length} 个维度当前完全没记录，因此没有任何统计：${D.emptyDimensions.map((k) => esc((FBYK()[k] || {}).label || k)).join('、')}</div>` : ''}</div>
      </details>
    </div>`;
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
  function analyticsView(v) {
    const A = state.data.analytics, S = state.data.stats;
    const freq = (rows, key) => rows.length ? `<div class="freq">${rows.map((m) => `<div class="frow">
      <div><a class="chip tag" href="#/trades?${key}=${encodeURIComponent(m.key)}">${esc(m.key)}</a>
      <span class="small muted">${m.count} 笔</span></div>
      <div class="fbar"><i style="width:${Math.min(100, m.count * 25)}%"></i></div></div>`).join('')}</div>` : '<div class="muted small">暂无</div>';
    v.innerHTML = `
      ${keyStats(state.data.trades)}
      <div class="sec"><h2>Analytics <span class="hint">样本小的时候，比率只能当趋势看</span></h2>
        <div class="analytics-grid">
          <div class="panel span2"><h3>累计 R</h3>${sparkline(A.cumulativeR)}
            <div class="small muted">${A.cumulativeR.map((c) => `${esc(c.date.slice(5))} ${c.cum > 0 ? '+' : ''}${c.cum}R`).join(' · ') || '—'}</div></div>
          <div class="panel"><h3>最常犯的错</h3>${freq(A.mistakeFrequency, 'mistake')}</div>
          <div class="panel"><h3>规则违反</h3>${freq(A.violationFrequency, 'violation')}</div>
          <div class="panel span2"><h3>Setup 表现</h3>${perfTable(A.setupTagPerformance, 'Setup 标签')}</div>
          <div class="panel"><h3>Entry Model</h3>${perfTable(A.entryModelPerformance, 'Entry Model')}
            <div class="small muted" style="margin-top:6px">HTF Limit ${S.htfLimitTrades} 笔 · LTF Confirmation ${S.ltfConfirmationTrades} 笔 · Market Entry ${S.marketEntryTrades} 笔</div></div>
          <div class="panel"><h3>复盘最容易漏记的字段</h3>
            ${state.data.unknownFields.map((u) => `<div class="frow"><div>${esc(u.field)} <span class="small muted">${u.count} 笔</span></div>
              <div class="fbar"><i style="width:${Math.min(100, u.count * 25)}%"></i></div></div>`).join('')}
            <div class="small muted" style="margin-top:6px">平均完整度 ${A.dataCompletenessAvg}%。越靠上越常忘。</div></div>
        </div>
        <details class="fold"><summary>旧版补充统计（持仓时间 / MAE·MFE 记录率 / Good-Bad 分类）</summary>
          <div class="analytics-grid" style="margin-top:10px">
            <div class="panel"><h3>Holding Time</h3>
              <table class="plain"><thead><tr><th>交易</th><th class="num">持仓</th><th>结果</th></tr></thead><tbody>
                ${A.holding.perTrade.map((h) => `<tr><td>${esc(h.symbolLabel)} <span class="small muted">${esc(h.id.slice(0, 10))}</span></td>
                  <td class="num">${h.hours} h</td><td>${esc(h.status || '—')}</td></tr>`).join('')}</tbody></table>
              <div class="small muted" style="margin-top:6px">平均：盈利 ${A.holding.avgWinnerHours === null ? '—' : A.holding.avgWinnerHours + ' h'} / 亏损 ${A.holding.avgLoserHours === null ? '—' : A.holding.avgLoserHours + ' h'}。${esc(A.holding.note)}</div></div>
            <div class="panel"><h3>MAE / MFE</h3><div class="muted small">已记录 ${A.maeMfe.recorded} / ${A.maeMfe.total} 笔。${esc(A.maeMfe.note)}</div></div>
            <div class="panel"><h3>Good / Bad 分类</h3>
              <div class="badges-row"><span class="chip win">Good Win ${S.goodWins}</span><span class="chip warn">Bad Win ${S.badWins}</span>
                <span class="chip">Good Loss ${S.goodLosses}</span><span class="chip loss">Bad Loss ${S.badLosses}</span></div>
              <div class="small muted" style="margin-top:8px">看的是「有没有守自己的规则」，不是赚没赚钱。Bad Win 最危险。</div></div>
          </div>
        </details>
      </div>
      ${analyticsV2()}`;
  }

  /* ------------------------------------------------------------ Rules */
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
