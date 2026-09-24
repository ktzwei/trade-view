/* Trading Review — 前端（零依赖，静态 JSON 驱动） */
(() => {
  const state = { data: null, range: 'all', q: '', filters: {} };
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (s) => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
  const NR = '<span class="nr">未记录</span>';
  const nr = (v, fmt) => (v === null || v === undefined || v === '' ? NR : (fmt ? fmt(v) : esc(v)));
  const num = (v, d = 2) => (v === null || v === undefined ? NR : Number(v).toFixed(d));
  const rTxt = (v) => (v === null || v === undefined ? NR
    : `<span class="${v > 0 ? 'rpos' : v < 0 ? 'rneg' : 'rzero'}">${v > 0 ? '+' : ''}${Number(v).toFixed(2)}R</span>`);
  const pct = (v) => (v === null || v === undefined ? NR : Math.round(v * 100) + '%');
  const dirChip = (d) => d === 'long' ? '<span class="chip long">LONG</span>'
    : d === 'short' ? '<span class="chip short">SHORT</span>' : `<span class="chip">${esc(d || '方向未知')}</span>`;
  const resChip = (t) => {
    const s = t.resultStatus;
    const map = { win: 'win', loss: 'loss', be: 'be' };
    const label = { win: 'Win', loss: 'Loss', be: 'BE' }[s] || '未记录';
    return `<span class="chip ${map[s] || ''}">${label}</span>`;
  };
  const img = (p) => p;

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
      route();
    })
    .catch((e) => { $('#view').innerHTML = `<div class="empty">数据加载失败：${esc(e.message)}<br>请确认 data/trades.json 存在（先跑 python3 parser/build.py）。</div>`; });

  function renderMeta() {
    const m = state.data.meta, s = state.data.stats;
    $('#brand-sub').textContent = m.sourceTitle || 'SMC Trading Review System';
    $('#meta-bar').innerHTML = [
      `<span>数据源：<b>${esc(m.sourceTitle || '交易复盘')}</b>（Google Docs）</span>`,
      `<span>解析时间：<b>${esc((m.parsedAt || '').slice(0, 16).replace('T', ' '))}</b></span>`,
      `<span>源文档版本：<b class="mono">${esc((m.sourceVersion || '').slice(0, 12))}</b></span>`,
      `<span>交易数：<b>${s.closed + s.open}</b>（已结束 ${s.closed}）</span>`,
      `<span>可计 R：<b>${s.netRKnownCount}</b> 笔，另有 <b>${s.rExcluded.length}</b> 笔因缺 SL 不计入</span>`,
    ].join('');
    $('#foot-src').innerHTML = `数据管线：Google Docs → parser/parse_gdoc.py（sourceData）→ analysis/analysis.json（AI 分析层，逐条带原文引用并做子串校验）→ parser/build.py → data/trades.json`;
  }

  /* ------------------------------------------------------------ 路由 */
  function route() {
    const h = location.hash.replace(/^#\/?/, '');
    const [path, qs] = h.split('?');
    state.filters = Object.fromEntries(new URLSearchParams(qs || ''));
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
  function todayStr() { const d = new Date(); return d.toISOString().slice(0, 10); }
  function inRange(t) {
    const d = (t.entryTime || '').slice(0, 10);
    if (!d) return true;
    if (state.range === 'all') return true;
    const now = new Date();
    if (state.range === 'month') {
      return d >= `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`;
    }
    const day = now.getDay() || 7;                       // 周一为一周起点
    const mon = new Date(now.getTime() - (day - 1) * 864e5);
    return d >= mon.toISOString().slice(0, 10);
  }
  function blob(t) {
    return [t.symbolLabel, t.direction, t.heading,
      ...Object.values(t.rawSections || {}),
      JSON.stringify(t.setup || {}), JSON.stringify(t.tags || {}),
      JSON.stringify(t.analysis || {})].join(' ').toLowerCase();
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
    return ts;
  }
  const ACTIVE = () => Object.keys(state.filters).filter((k) => state.filters[k]).length;

  function statStrip(trades) {
    const rk = trades.filter((t) => t.rIncluded && t.actualR !== null);
    const wins = trades.filter((t) => t.resultStatus === 'win');
    const closed = trades.filter((t) => ['win', 'loss', 'be'].includes(t.resultStatus));
    const losses = trades.filter((t) => t.resultStatus === 'loss');
    const net = rk.reduce((a, t) => a + t.actualR, 0);
    const winsR = rk.filter((t) => t.actualR > 0).map((t) => t.actualR);
    const lossR = rk.filter((t) => t.actualR < 0).map((t) => t.actualR);
    const viol = trades.reduce((a, t) => a + ((t.analysis || {}).ruleViolations || []).length, 0);
    const miss = trades.filter((t) => (t.dataCompleteness || {}).percent < 100).length;
    const avg = (a) => a.length ? (a.reduce((x, y) => x + y, 0) / a.length).toFixed(2) : null;
    const cell = (k, v, s) => `<div class="stat"><div class="k">${k}</div><div class="v">${v}</div>${s ? `<div class="s">${s}</div>` : ''}</div>`;
    return `<div class="stats">
      ${cell('Closed Trades', closed.length, `未结束 ${trades.length - closed.length}`)}
      ${cell('Win / Loss / BE', `${wins.length} / ${losses.length} / ${closed.length - wins.length - losses.length}`)}
      ${cell('Win Rate', pct(closed.length ? wins.length / closed.length : null))}
      ${cell('Known Net R', rTxt(rk.length ? net : null), `${rk.length} 笔可计 R`)}
      ${cell('Avg R', rTxt(avg(rk.map((t) => t.actualR))), '仅计 R 的交易')}
      ${cell('Avg Winner R', rTxt(avg(winsR)), '')}
      ${cell('Avg Loser R', rTxt(avg(lossR)), '')}
      ${cell('HTF Limit', trades.filter((t) => (t.entryModel || {}).category === 'HTF_LIMIT').length, '笔')}
      ${cell('LTF Confirmation', trades.filter((t) => (t.entryModel || {}).category === 'HTF_LTF_CONFIRMATION').length, '笔')}
      ${cell('Rule Violations', viol, '按笔累加')}
      ${cell('Missing Data', miss, '完整度 < 100%')}
    </div>`;
  }

  /* ------------------------------------------------------------ Dashboard */
  function dashboard(view) {
    const ts = filtered();
    const weeks = state.data.weeks.filter((w) => w.tradeIds.some((id) => ts.some((t) => t.id === id)));
    const recentRules = state.data.rules.generated.slice(-4).reverse();
    const mistakes = state.data.analytics.mistakeFrequency.slice(0, 4);
    view.innerHTML = `
      ${statStrip(ts)}
      ${ACTIVE() || state.q ? `<div class="sec"><div class="callout">当前正在筛选：${[
        state.q ? `搜索「${esc(state.q)}」` : '',
        ...Object.entries(state.filters).filter(([, v]) => v).map(([k, v]) => `${esc(k)}=${esc(v)}`),
      ].filter(Boolean).join(' · ')} —— 命中 ${ts.length} 笔。<a href="#/trades" style="text-decoration:underline">在 Trades 页调整</a></div></div>` : ''}
      <div class="sec">
        <h2>Recent Mistakes <span class="hint">重复出现的问题优先看</span></h2>
        <div class="analytics-grid">
          <div class="panel">
            <h3>Mistake Frequency</h3>
            <div class="freq">${mistakes.length ? mistakes.map((m) => `
              <div class="frow"><div><a class="chip tag" href="#/trades?mistake=${encodeURIComponent(m.key)}">${esc(m.key)}</a>
              <span class="small muted">${m.trades.length} 笔</span></div>
              <div class="fbar"><i style="width:${Math.min(100, m.count * 25)}%"></i></div></div>`).join('')
              : '<div class="muted small">暂无</div>'}</div>
          </div>
          <div class="panel">
            <h3>Recent Rules <span class="ai-mark">来自交易复盘</span></h3>
            ${recentRules.map((r) => `<div class="callout" style="margin-bottom:8px">
              ${esc(r.text)}<div class="small muted" style="margin-top:4px">来源：<a href="#/trade/${encodeURIComponent(r.createdFrom)}" style="text-decoration:underline">${esc(r.createdFromLabel)}</a></div>
            </div>`).join('')}
          </div>
        </div>
      </div>
      <div class="sec">
        <h2>Weeks</h2>
        ${weeks.length ? weeks.map((w) => weekBlock(w, ts)).join('') : '<div class="empty">该筛选条件下没有交易。</div>'}
      </div>`;
    bindCards(view);
  }

  const setupTags = (t) => {
    const rules = [[/sweep/i, 'Liquidity Sweep'], [/displacement/i, 'Displacement'], [/msb|mss/i, 'MSB / MSS'],
      [/bos/i, 'BOS'], [/poi|imb|bb|discount|premium|fvg|\bob\b/i, 'POI'],
      [/liquidity-to-liquidity/i, 'Liquidity-to-Liquidity'], [/pullback/i, 'Pullback']];
    const out = [];
    ((t.setup || {}).flow || []).forEach((s) => rules.forEach(([re, n]) => { if (re.test(s) && !out.includes(n)) out.push(n); }));
    return out;
  };

  function weekBlock(w, ts) {
    const wt = ts.filter((t) => w.tradeIds.includes(t.id));
    const st = w.stats;
    const rk = wt.filter((t) => t.rIncluded && t.actualR !== null);
    const net = rk.reduce((a, t) => a + t.actualR, 0);
    const rev = w.review || {};
    return `<div class="week" id="week-${esc(w.label)}">
      <div class="week-head">
        <div class="week-title">
          <h2>${esc(w.label)}</h2>
          <span class="dates">${esc(w.start)} – ${esc(w.end)}${w.isoWeek ? ` · ISO Week ${w.isoWeek}` : ''}</span>
        </div>
        <div class="week-nums">
          <span>Trades <b>${wt.length}</b></span>
          <span>Wins <b>${wt.filter((t) => t.resultStatus === 'win').length}</b></span>
          <span>Loss <b>${wt.filter((t) => t.resultStatus === 'loss').length}</b></span>
          <span>Known Net R <b>${rTxt(rk.length ? net : null)}</b></span>
        </div>
      </div>
      ${w.summaryRaw ? `<div class="week-summary">${esc(w.summaryRaw)}</div>` : ''}
      ${rev ? `<div class="week-review">
        ${rev.mainStrength ? `<div class="wr"><div class="k">Main Strength</div><div class="v">${esc(rev.mainStrength.text)}<div class="small muted">“${esc(rev.mainStrength.evidence)}”</div></div></div>` : ''}
        ${rev.mainProblem ? `<div class="wr"><div class="k">Main Problem</div><div class="v">${esc(rev.mainProblem.text)}<div class="small muted">“${esc(rev.mainProblem.evidence)}”</div></div></div>` : ''}
        ${rev.repeatedMistake ? `<div class="wr"><div class="k">Repeated Mistake</div><div class="v">${esc(rev.repeatedMistake.text)}<div class="small muted">“${esc(rev.repeatedMistake.evidence)}”</div></div></div>` : ''}
        ${rev.mainLesson ? `<div class="wr"><div class="k">Main Lesson</div><div class="v">${esc(rev.mainLesson.text)}<div class="small muted">“${esc(rev.mainLesson.evidence)}”</div></div></div>` : ''}
        ${rev.newRule ? `<div class="wr"><div class="k">New Rule</div><div class="v">${esc(rev.newRule.text)}<div class="small muted">“${esc(rev.newRule.evidence)}”</div></div></div>` : ''}
        <div class="wr"><div class="k">Best / Worst</div><div class="v">
          ${w.bestTrade ? `Best：<a href="#/trade/${encodeURIComponent(w.bestTrade.id)}" style="text-decoration:underline">${esc(w.bestTrade.symbolLabel)}</a> ${rTxt(w.bestTrade.actualR)}<br>` : ''}
          ${w.worstTrade ? `Worst：<a href="#/trade/${encodeURIComponent(w.worstTrade.id)}" style="text-decoration:underline">${esc(w.worstTrade.symbolLabel)}</a> ${rTxt(w.worstTrade.actualR)}` : ''}
        </div></div>
        <div class="wr"><div class="k">Missing Data</div><div class="v">${w.missingData && w.missingData.length
          ? w.missingData.map((m) => `<span class="chip warn">${esc(m.field)} · ${m.count} 笔</span>`).join(' ')
          : '<span class="muted small">无</span>'}
          <div class="small muted" style="margin-top:4px">平均完整度 ${w.avgCompleteness}%</div></div></div>
        ${w.stats.rExcluded && w.stats.rExcluded.length ? `<div class="wr"><div class="k">R 未计入</div><div class="v">${w.stats.rExcluded
          .map((x) => `${esc(x.symbolLabel)} <span class="small muted">（${esc(x.reason)}）</span>`).join('<br>')}</div></div>` : ''}
      </div>` : ''}
      <div class="trades-list">${wt.map(tradeCard).join('')}</div>
    </div>`;
  }

  function tradeCard(t) {
    const imgs = t.images || [];
    const meta = t.analysis || {};
    const cls = (meta.classification || {}).value;
    const viol = (meta.ruleViolations || []);
    const tp = (t.targets || []).map((x) => x.label + (x.price ? ` ${x.price}` : '')).join(' / ');
    return `<article class="tcard" data-id="${esc(t.id)}">
      <div class="tcard-main">
        <div class="tcard-top">
          <span class="sym">${esc(t.symbolLabel)}</span>${dirChip(t.direction)}${resChip(t)}
          <span class="when">${esc(t.entryTimeLabel || '')}${t.exitTimeLabel ? ' → ' + esc(t.exitTimeLabel) : ''}</span>
          ${cls ? `<span class="chip ${cls.includes('Win') ? 'win' : 'loss'}">${esc(cls)}</span>` : ''}
          ${viol.map((v) => `<span class="chip warn">⚠ ${esc(v.tag)}</span>`).join('')}
        </div>
        <div class="tcard-metrics">
          <div class="m"><div class="k">Entry</div><div class="v">${num(t.entry)}</div></div>
          <div class="m"><div class="k">SL</div><div class="v">${num(t.stopLoss)}</div></div>
          <div class="m"><div class="k">TP / Exit</div><div class="v">${t.exit !== null ? num(t.exit) : (tp || NR)}</div></div>
          <div class="m"><div class="k">Planned RR</div><div class="v">${t.plannedRR !== null ? num(t.plannedRR) + 'R' : NR}</div></div>
          <div class="m"><div class="k">Actual R</div><div class="v">${t.actualR !== null ? rTxt(t.actualR) : NR}</div></div>
          <div class="m"><div class="k">Entry Model</div><div class="v small">${esc((t.entryModel || {}).label || '未记录')}</div></div>
        </div>
        ${(t.setup || {}).flow && t.setup.flow.length ? `<div class="flow">${t.setup.flow.map((s, i) =>
          `${i ? '<span class="arw">→</span>' : ''}<span class="step">${esc(s)}</span>`).join('')}</div>` : ''}
        <div class="tcard-thesis">${esc((t.sections || {}).entryReason || '')}</div>
        <div class="tcard-tags">
          ${setupTags(t).map((s) => `<a class="chip tag" href="#/trades?setup=${encodeURIComponent(s)}">${esc(s)}</a>`).join('')}
          ${(t.poi || []).map((p) => `<span class="chip">${esc(p.label)}</span>`).join('')}
          <span class="chip ghost">${esc(t.week.label)}</span>
        </div>
      </div>
      <div class="tcard-side">
        ${imgs.length ? `<img class="thumb" src="${esc(img(imgs[0].path))}" alt="${esc(t.symbolLabel)} 图表" loading="lazy">` : '<div class="thumb"></div>'}
        ${imgs.length > 1 ? `<div class="thumbs">${imgs.slice(1, 3).map((i) => `<img src="${esc(img(i.path))}" alt="" loading="lazy">`).join('')}</div>` : ''}
        <div class="badges">${t.entryModel && t.entryModel.plannedDiffersFromActual ? '<span class="chip warn">计划与实际入场模型不同</span>' : ''}
          ${t.rIncluded ? '' : '<span class="chip warn">R 未计入</span>'}</div>
        <div class="completeness">数据完整度 ${t.dataCompleteness ? t.dataCompleteness.percent : '—'}%
          <div class="bar" style="margin-top:4px"><i style="width:${t.dataCompleteness ? t.dataCompleteness.percent : 0}%"></i></div>
          ${t.dataCompleteness && t.dataCompleteness.missing.length ? `<div style="margin-top:5px" class="small muted">缺：${esc(t.dataCompleteness.missing.join('、'))}</div>` : ''}
        </div>
      </div>
    </article>`;
  }

  function bindCards(root) {
    root.querySelectorAll('.tcard').forEach((c) => c.addEventListener('click', (e) => {
      if (e.target.closest('a')) return;
      location.hash = `#/trade/${encodeURIComponent(c.dataset.id)}`;
    }));
  }

  /* ------------------------------------------------------------ Weeks / Trades 列表 */
  function weeksView(v) {
    v.innerHTML = `<div class="sec"><h2>Weeks</h2></div>` +
      state.data.weeks.map((w) => `<div class="week"><div class="week-head">
        <div class="week-title"><h2><a href="#/week/${encodeURIComponent(w.label)}">${esc(w.label)}</a></h2>
        <span class="dates">${esc(w.start)} – ${esc(w.end)}${w.isoWeek ? ' · ISO Week ' + w.isoWeek : ''}</span></div>
        <div class="week-nums"><span>Trades <b>${w.stats.trades}</b></span>
        <span>Wins <b>${w.stats.wins}</b></span><span>Loss <b>${w.stats.losses}</b></span>
        <span>Known Net R <b>${rTxt(w.stats.knownNetR)}</b></span></div></div>
        ${w.summaryRaw ? `<div class="week-summary">${esc(w.summaryRaw)}</div>` : ''}</div>`).join('');
  }

  function weekDetail(v, label) {
    const w = state.data.weeks.find((x) => x.label === label);
    if (!w) { v.innerHTML = '<div class="empty">找不到这个周。</div>'; return; }
    const ts = state.data.trades.filter((t) => w.tradeIds.includes(t.id));
    v.innerHTML = `<a class="small muted" href="#/weeks">← 全部周</a>${weekBlock(w, ts)}`;
    bindCards(v);
  }

  function tradesView(v) {
    const ts = filtered();
    const uniq = (k) => [...new Set(state.data.trades.map(k).filter(Boolean))];
    const chips = (key, opts, fmt = (x) => x) => `<div class="filt">${opts.map((o) =>
      `<a class="chip tag ${state.filters[key] === o ? 'on' : ''}" href="#/trades${qs({ ...state.filters, [key]: state.filters[key] === o ? null : o })}">${esc(fmt(o))}</a>`).join('')}</div>`;
    v.innerHTML = `
      <div class="sec"><h2>Trades <span class="hint">${ts.length} / ${state.data.trades.length} 笔</span></h2>
        ${chips('result', ['win', 'loss', 'be'], (x) => ({ win: 'Win', loss: 'Loss', be: 'BE' }[x]))}
        ${chips('direction', ['long', 'short'], (x) => x.toUpperCase())}
        ${chips('symbol', uniq((t) => t.symbolLabel))}
        ${chips('model', uniq((t) => (t.entryModel || {}).category), (x) => ((state.data.trades.find((t) => (t.entryModel || {}).category === x).entryModel || {}).label || x))}
        ${chips('mistake', [...new Set(state.data.analytics.mistakeFrequency.map((m) => m.key))])}
        ${chips('violation', [...new Set(state.data.analytics.violationFrequency.map((m) => m.key))])}
        ${chips('setup', [...new Set(state.data.trades.flatMap(setupTags))])}
        <div style="margin-top:10px">${statStrip(ts)}</div>
      </div>
      <div class="trades-list sec">${ts.length ? ts.map(tradeCard).join('') : '<div class="empty">没有符合条件的交易。</div>'}</div>`;
    bindCards(v);
  }
  const qs = (o) => {
    const s = new URLSearchParams(Object.entries(o).filter(([, v]) => v !== null && v !== undefined && v !== ''));
    const str = s.toString();
    return str ? '?' + str : '';
  };

  /* ------------------------------------------------------------ 交易详情 */
  function tradeDetail(v, id) {
    const t = state.data.trades.find((x) => x.id === id);
    if (!t) { v.innerHTML = '<div class="empty">找不到这笔交易。</div>'; return; }
    const a = t.analysis || {}, s = t.sections || {}, imgs = t.images || [];
    const rc = a.riskCheck || [];
    const ic = { pass: '✔', fail: '✘', partial: '~', unknown: '?' };
    const lab = { pass: '通过', fail: '违反', partial: '部分', unknown: '未知' };
    const plan = t.plannedRR !== null && t.plannedRRLow !== null && t.plannedRRLow !== t.plannedRRHigh;
    v.innerHTML = `
      <a class="small muted" href="#/week/${encodeURIComponent(t.week.label)}">← ${esc(t.week.label)}</a>
      <div class="trade-header" style="margin-top:8px">
        <div>
          <h1>${esc(t.symbolLabel)} ${t.direction === 'long' ? 'LONG' : t.direction === 'short' ? 'SHORT' : ''}</h1>
          <div class="sub">${esc(t.entryTimeLabel || '')}${t.exitTimeLabel ? ' → ' + esc(t.exitTimeLabel) : ''}
            · 持仓 ${t.holdingLabel ? esc(t.holdingLabel) : NR} · ${esc(t.week.label)}（${esc(t.week.start)} – ${esc(t.week.end)}）</div>
          <div class="badges-row" style="margin-top:10px">
            ${dirChip(t.direction)}${resChip(t)}
            <span class="chip">${esc((t.entryModel || {}).label || 'Entry Model 未记录')}</span>
            ${a.classification ? `<span class="chip ai">${esc(a.classification.value)} · AI</span>` : ''}
            ${a.errorType ? `<span class="chip ai">${esc(a.errorType.primary)} · AI</span>` : ''}
            ${(a.ruleViolations || []).map((x) => `<span class="chip warn">⚠ ${esc(x.tag)}</span>`).join('')}
            <span class="chip ghost">${esc(t.id)}</span>
          </div>
        </div>
        <div class="rr"><div class="k small muted">Actual R</div><div class="big">${t.actualR !== null ? rTxt(t.actualR) : NR}</div>
          <div class="small muted">Planned RR ${t.plannedRR !== null ? esc(t.plannedRR) + 'R' : '未记录'}</div></div>
      </div>

      <div class="panel" style="margin-top:14px">
        <div class="kv">
          <div><div class="k">Entry</div><div class="v">${num(t.entry)}</div></div>
          <div><div class="k">Stop Loss</div><div class="v">${num(t.stopLoss)}${t.riskPoints !== null ? `<span class="nr">风险 ${esc(t.riskPoints)} 点</span>` : ''}</div></div>
          <div><div class="k">TP / Exit</div><div class="v">${t.exit !== null ? num(t.exit) : NR}</div></div>
          <div><div class="k">Targets</div><div class="v small">${(t.targets || []).length ? t.targets.map((x) => `${esc(x.label)}${x.price ? ' ' + esc(x.price) : ''}${x.sizePercent ? `（${x.sizePercent}%）` : ''}`).join('<br>') : NR}</div></div>
          <div><div class="k">Planned RR</div><div class="v">${t.plannedRR !== null ? num(t.plannedRR) + 'R' : NR}${plan ? `<span class="nr">区间 ${esc(t.plannedRRLow)}–${esc(t.plannedRRHigh)}（中值）</span>` : ''}</div></div>
          <div><div class="k">MAE / MFE</div><div class="v small">${nr(t.mae)} / ${nr(t.mfe)}</div></div>
          <div><div class="k">PnL / Fees</div><div class="v small">${nr(t.pnl)} / ${nr(t.fees)}</div></div>
          <div><div class="k">数据完整度</div><div class="v">${t.dataCompleteness ? t.dataCompleteness.percent + '%' : '—'}</div></div>
        </div>
      </div>

      <div class="detail">
        <div class="stack">
          <div class="card chart-wrap">
            ${imgs.length ? `<img class="chart-main" id="main-chart" src="${esc(imgs[0].path)}" alt="${esc(t.symbolLabel)} 图表">`
              : '<div class="empty">这笔交易还没有绑定图表。</div>'}
            <div class="chart-bar"><span>${imgs.length ? esc(imgs.length === 1 ? '文档内嵌分析图（原图）' : imgs[0].typeLabel || '分析图') : ''}</span>
              <span>${esc(t.context && t.context.timeframe ? '参考周期 ' + t.context.timeframe : '')} · 点击放大</span></div>
            ${imgs.length > 1 ? `<div class="gallery">${imgs.map((i, n) => `<img src="${esc(i.path)}" data-lb="${n}" alt="图 ${n + 1}">`).join('')}</div>` : ''}
          </div>

          ${s.context ? `<div class="panel"><h3>Market Context</h3><div class="raw">${esc(s.context)}</div></div>` : ''}

          <div class="panel"><h3>Liquidity</h3>
            <div class="badges-row">
              ${t.liquidity.sslSwept ? '<span class="chip win">SSL Swept</span>' : '<span class="chip ghost">SSL Swept 未记录</span>'}
              ${t.liquidity.bslTarget ? `<span class="chip">BSL ${esc(t.liquidity.bslTarget)}</span>` : '<span class="chip ghost">BSL 未记录</span>'}
              ${t.liquidity.internalLiquidity ? '<span class="chip">Internal Liquidity</span>' : ''}
              ${t.liquidity.externalLiquidity ? '<span class="chip">External Liquidity</span>' : ''}
              ${t.liquidity.htfMagnet ? '<span class="chip">HTF Magnet</span>' : ''}
              ${(t.targets || []).some((x) => x.type && /BSL|Liquidity/.test(x.type)) ? '<span class="chip warn">Target = Buy-side Liquidity</span>' : ''}
            </div>
            ${s.targetLogic ? `<div class="raw small" style="margin-top:8px">${esc(s.targetLogic)}</div>` : ''}</div>

          <div class="panel"><h3>Structure</h3>
            <div class="badges-row">
              ${t.structure.internalMSB ? `<span class="chip">Internal MSB ${esc(t.structure.internalMSB)}</span>` : '<span class="chip ghost">Internal MSB 未记录</span>'}
              ${t.structure.majorTrendReversal === true ? '<span class="chip warn">主趋势反转</span>' : ''}
              ${t.structure.majorTrendReversal === false ? '<span class="chip ghost">未构成主趋势反转</span>' : ''}
              ${(t.structure.notes || []).map((n) => `<span class="chip">${esc(n)}</span>`).join('')}
            </div>
            ${s.structure ? `<div class="raw small" style="margin-top:8px">${esc(s.structure)}</div>` : ''}</div>

          <div class="panel"><h3>Displacement</h3>
            ${t.displacement ? `<div class="badges-row"><span class="chip ${t.displacement.strength === 'strong' ? 'win' : 'warn'}">${esc(t.displacement.type)} · ${t.displacement.strength === 'strong' ? 'Strong' : t.displacement.strength === 'weak' ? 'Weak' : t.displacement.strength}</span></div>`
              : `<div class="muted small">未记录。位移（价格运动本身）与 MSB/MSS（结构变化）是两个字段，本笔只记录了结构相关的部分。</div>`}
            ${s.displacement ? `<div class="raw small" style="margin-top:8px">${esc(s.displacement)}</div>` : ''}</div>

          <div class="panel"><h3>POI</h3>
            ${(t.poi || []).length ? `<div class="badges-row">${t.poi.map((p) => `<span class="chip">${esc(p.label)}</span>`).join('')}</div>
              <div class="small muted" style="margin-top:6px">POI Confluence：${esc((t.poi || []).map((p) => p.label).join(' + '))}</div>`
              : '<div class="muted small">未记录。文档里没有把这笔的 POI（OB / BB / IMB / FVG）单独写出来，因此这里保持空白 —— 不推测。</div>'}</div>

          <div class="panel"><h3>Setup Flow</h3>
            ${(t.setup.flow || []).length ? `<div class="flow-v">${t.setup.flow.map((x, i) => `
              <div class="node"><span class="dot"></span><div class="item">${esc(x)}</div></div>
              ${i < t.setup.flow.length - 1 ? '<div class="line" style="margin-left:4px"></div>' : ''}`).join('')}</div>`
              : '<div class="muted small">未记录</div>'}</div>

          <div class="panel"><h3>Entry Reasons <span class="hint small">为什么值得观察</span></h3>
            ${(t.entryReason || []).length ? `<ul class="reasons">${t.entryReason.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>` : '<div class="muted small">未记录</div>'}</div>

          <div class="panel"><h3>Entry Trigger <span class="hint small">什么条件真的触发了进场</span></h3>
            ${t.entryTrigger && t.entryTrigger.text ? `<div class="raw">${esc(t.entryTrigger.text)}</div>
              <div class="small muted" style="margin-top:6px">Entry Model：${esc(t.entryTrigger.modelLabel || '未记录')}</div>`
              : '<div class="muted small">未记录</div>'}</div>

          <div class="panel"><h3>Invalidation <span class="hint small">逻辑失效 vs 止损价</span></h3>
            <div class="kv" style="margin-top:0">
              <div><div class="k">Logical Invalidation</div><div class="v small">${t.invalidation.logic ? esc(t.invalidation.logic) : NR}</div></div>
              <div><div class="k">Stop Loss Price</div><div class="v">${num(t.stopLoss)}</div></div>
            </div>
            ${s.invalidation ? `<div class="raw small" style="margin-top:8px">${esc(s.invalidation)}</div>` : ''}</div>

          <div class="panel"><h3>Target Logic</h3>
            <table class="plain"><thead><tr><th>Level</th><th>Price</th><th>Type</th><th class="num">Size %</th></tr></thead><tbody>
              ${(t.targets || []).length ? t.targets.map((x) => `<tr><td>${esc(x.label)}</td><td>${x.price ? esc(x.price) : NR}</td>
                <td>${(x.type || []).map((y) => `<span class="chip">${esc(y)}</span>`).join(' ') || NR}</td>
                <td class="num">${x.sizePercent !== null && x.sizePercent !== undefined ? x.sizePercent + '%' : '—'}</td></tr>`).join('')
              : '<tr><td colspan="4" class="muted">未记录</td></tr>'}
            </tbody></table>
            ${s.targetLogic ? `<div class="raw small" style="margin-top:8px">${esc(s.targetLogic)}</div>` : ''}</div>

          <div class="panel"><h3>Trade Management</h3>
            <div class="badges-row">${Object.entries(t.tradeManagement || {}).map(([k, vv]) => `<span class="chip ${vv === true ? 'warn' : 'ghost'}">${esc(k)}: ${vv === null ? '未记录' : vv ? '是' : '否'}</span>`).join('')}</div></div>
        </div>

        <div class="stack">
          <div class="panel"><h3>Pre-Trade Risk Check <span class="hint small">${a.compliance ? `${a.compliance.pass} 通过 / ${a.compliance.fail} 违反 / ${a.compliance.partial} 部分 / ${a.compliance.unknown} 未知` : ''}</span></h3>
            <div class="check">${rc.map((i) => `<div class="row ${i.status}">
              <span class="ic">${ic[i.status]}</span>
              <div class="lab"><b>${esc(i.label)}</b><span class="small muted"> · ${lab[i.status]}</span>
                ${i.note ? `<div class="small muted">${esc(i.note)}</div>` : ''}
                ${i.evidence ? `<div class="ev">“${esc(i.evidence)}”</div>` : ''}</div></div>`).join('')}</div>
            ${a.compliance && a.compliance.rate !== null ? `<div class="small muted" style="margin-top:8px">Rule Compliance（仅计已判定项）：${pct(a.compliance.rate)}</div>` : ''}
          </div>

          <div class="panel"><h3>Result</h3>
            <div class="kv" style="margin-top:0">
              <div><div class="k">Result</div><div class="v">${resChip(t)}</div></div>
              <div><div class="k">Actual R</div><div class="v">${t.actualR !== null ? rTxt(t.actualR) : NR}</div></div>
              <div><div class="k">Holding Time</div><div class="v">${t.holdingLabel ? esc(t.holdingLabel) : NR}</div></div>
              <div><div class="k">PnL</div><div class="v">${nr(t.pnl)}</div></div>
              <div><div class="k">Fees</div><div class="v">${nr(t.fees)}</div></div>
            </div>
            ${!t.rIncluded ? `<div class="callout warn" style="margin-top:10px">本笔不计入 R 统计：${esc(t.rExcludeReason || '缺少可计算的 SL / 实际 R')}</div>` : ''}
            ${s.result ? `<div class="raw small" style="margin-top:8px">${esc(s.result)}</div>` : ''}</div>

          <div class="panel"><h3>What Worked</h3>${(t.review.worked || []).length
            ? `<ul class="reasons">${t.review.worked.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>`
            : '<div class="muted small">未记录 —— 一笔亏损交易也应该有做得对的地方，缺这一块就只剩情绪结论。</div>'}</div>

          <div class="panel"><h3>What Went Wrong</h3>${(t.review.mistakes || []).length
            ? `<ul class="reasons">${t.review.mistakes.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>`
            : '<div class="muted small">未记录</div>'}
            ${(a.mistakes || []).length ? `<div style="margin-top:8px">${a.mistakes.map((m) => `<span class="chip warn">${esc(m.tag)}</span>`).join(' ')}<div class="small muted" style="margin-top:4px">AI 标签（依据原文）：${a.mistakes.map((m) => '“' + esc(m.evidence) + '”').join(' / ')}</div></div>` : ''}</div>

          <div class="panel"><h3>Next Rule</h3>${(t.review.nextRules || []).length
            ? `<ul class="reasons">${t.review.nextRules.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>`
            : '<div class="muted small">未记录</div>'}</div>

          ${a.classification || a.errorType ? `<div class="panel"><h3>AI 复盘分析 <span class="ai-mark">分析层</span></h3>
            ${a.classification ? `<div class="callout ${a.classification.value.includes('Win') ? 'good' : 'bad'}"><b>${esc(a.classification.value)}</b>：${esc(a.classification.reason)}<div class="small" style="margin-top:4px">依据：“${esc(a.classification.evidence)}”</div></div>` : ''}
            ${a.errorType ? `<div class="callout" style="margin-top:8px">Error Type：<b>${esc(a.errorType.primary)}</b>${(a.errorType.secondary || []).length ? `（次要：${esc(a.errorType.secondary.join('、'))}）` : ''}
              <div class="small" style="margin-top:4px">依据：“${esc(a.errorType.evidence)}”</div></div>` : ''}
            ${(a.ruleViolations || []).length ? `<div style="margin-top:8px">Rule Violations：${a.ruleViolations.map((x) => `<span class="chip warn">${esc(x.tag)}</span>`).join(' ')}
              <div class="small muted" style="margin-top:4px">${a.ruleViolations.map((x) => '“' + esc(x.evidence) + '”').join(' / ')}</div></div>` : '<div class="small muted" style="margin-top:6px">未发现规则违反。</div>'}
            <div class="small muted" style="margin-top:8px">AI 只做结构与归类，不修改任何原始交易事实；每条结论都能在上面找到对应原文引用。</div>
          </div>` : ''}

          <div class="panel"><h3>Tags</h3><div class="badges-row">
            ${dirChip(t.direction)}
            ${setupTags(t).map((x) => `<a class="chip tag" href="#/trades?setup=${encodeURIComponent(x)}">${esc(x)}</a>`).join('')}
            ${(t.poi || []).map((p) => `<span class="chip">${esc(p.label)}</span>`).join('')}
            ${resChip(t)}
            ${(a.mistakes || []).map((m) => `<a class="chip tag warn" href="#/trades?mistake=${encodeURIComponent(m.tag)}">${esc(m.tag)}</a>`).join('')}
            <span class="chip ghost">${esc((t.entryModel || {}).label || '')}</span>
            <span class="chip ghost">${esc(t.week.label)}</span>
          </div></div>

          <details class="raw-src panel"><summary>查看 Google Docs 原文（sourceData）</summary>
            ${Object.entries(t.rawSections || {}).map(([k, vv]) => `<div class="kvraw"><b>${esc(k)}</b>${esc(Array.isArray(vv) ? vv.join(' / ') : vv)}</div>`).join('')}
            <div class="kvraw"><b>heading</b>${esc(t.heading || '')}</div>
          </details>
        </div>
      </div>`;
    if (imgs.length) {
      $('#main-chart').addEventListener('click', () => openLightbox(t, 0));
      v.querySelectorAll('[data-lb]').forEach((el) => el.addEventListener('click', () => openLightbox(t, +el.dataset.lb)));
    }
  }

  /* ------------------------------------------------------------ Analytics */
  function sparkline(curve) {
    if (!curve.length) return '<div class="muted small">暂无可计 R 的交易。</div>';
    const w = 560, h = 150, pad = 26;
    const xs = curve.map((_, i) => pad + i * ((w - pad * 2) / Math.max(1, curve.length - 1)));
    const vals = [0, ...curve.map((c) => c.cum)];
    const min = Math.min(...vals), max = Math.max(...vals);
    const y = (v) => h - pad - ((v - min) / (max - min || 1)) * (h - pad * 2);
    const pts = [[xs[0], y(0)], ...curve.map((c, i) => [xs[i], y(c.cum)])];
    const path = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' ');
    const zero = `<line x1="${pad}" x2="${w - pad}" y1="${y(0)}" y2="${y(0)}" stroke="#dcdbd7" stroke-dasharray="3 3"/>`;
    return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
      ${zero}<path d="${path}" fill="none" stroke="#345d8f" stroke-width="2"/>
      ${curve.map((c, i) => `<circle cx="${xs[i]}" cy="${y(c.cum)}" r="3.5" fill="#345d8f"><title>${esc(c.symbolLabel)} ${esc(c.date)} ${c.r > 0 ? '+' : ''}${c.r}R → 累计 ${c.cum}R</title></circle>`).join('')}
      <text x="${pad}" y="12" font-size="10" fill="#8b8a85">累计 R（仅计可计 R 的交易）</text>
    </svg>`;
  }

  function perfTable(rows, firstCol) {
    if (!rows.length) return '<div class="muted small">暂无数据</div>';
    return `<table class="plain"><thead><tr><th>${esc(firstCol)}</th><th class="num">Trades</th><th class="num">Win Rate</th><th class="num">Avg R</th><th class="num">Net R</th></tr></thead>
      <tbody>${rows.map((r) => `<tr><td>${esc(r.key)}<div class="small muted">${r.trades.map((id) => `<a href="#/trade/${encodeURIComponent(id)}" style="text-decoration:underline">${esc(id.replace(/^20/, '').slice(0, 12))}</a>`).join(' · ')}</div></td>
        <td class="num">${r.count}</td><td class="num">${r.winRate === null ? '—' : pct(r.winRate)}</td>
        <td class="num">${r.avgR === null ? '—' : (r.avgR > 0 ? '+' : '') + r.avgR + 'R'}</td>
        <td class="num">${r.netR === null ? '—' : (r.netR > 0 ? '+' : '') + r.netR + 'R'}</td></tr>`).join('')}</tbody></table>`;
  }

  function analyticsView(v) {
    const A = state.data.analytics, S = state.data.stats;
    const freq = (rows) => rows.length ? `<div class="freq">${rows.map((m) => `<div class="frow">
      <div><a class="chip tag" href="#/trades?${rows === A.mistakeFrequency ? 'mistake' : 'violation'}=${encodeURIComponent(m.key)}">${esc(m.key)}</a>
      <span class="small muted">${m.count} 笔</span></div>
      <div class="fbar"><i style="width:${Math.min(100, m.count * 25)}%"></i></div></div>`).join('')}</div>` : '<div class="muted small">暂无</div>';
    v.innerHTML = `
      ${statStrip(state.data.trades)}
      <div class="sec"><h2>Analytics <span class="hint">数据量小的时候，比率类指标只能当趋势看</span></h2>
        <div class="analytics-grid">
          <div class="panel"><h3>Cumulative R</h3>${sparkline(A.cumulativeR)}
            <div class="small muted">逐笔累计：${A.cumulativeR.map((c) => `${esc(c.date.slice(5))} ${c.cum > 0 ? '+' : ''}${c.cum}R`).join(' · ') || '—'}</div></div>
          <div class="panel"><h3>Setup Performance</h3>${perfTable(A.setupTagPerformance, 'Setup 标签')}</div>
          <div class="panel"><h3>Entry Model Comparison <span class="hint small">HTF Limit vs LTF Confirmation</span></h3>
            ${perfTable(A.entryModelPerformance, 'Entry Model')}
            <div class="small muted" style="margin-top:6px">目前样本：HTF Limit ${S.htfLimitTrades} 笔 · LTF Confirmation ${S.ltfConfirmationTrades} 笔 · Market Entry ${S.marketEntryTrades} 笔 —— 还不足以判断你更适合哪种。</div></div>
          <div class="panel"><h3>Mistake Analytics</h3>${freq(A.mistakeFrequency)}</div>
          <div class="panel"><h3>Rule Violations</h3>${freq(A.violationFrequency)}</div>
          <div class="panel"><h3>Holding Time</h3>
            <table class="plain"><thead><tr><th>交易</th><th class="num">持仓</th><th>结果</th></tr></thead><tbody>
              ${A.holding.perTrade.map((h) => `<tr><td><a href="#/trade/${encodeURIComponent(h.id)}" style="text-decoration:underline">${esc(h.symbolLabel)}</a>
                <span class="small muted">${esc(h.id.slice(0, 10))}</span></td><td class="num">${h.hours} h</td><td>${esc(h.status || '—')}</td></tr>`).join('')}
            </tbody></table>
            <div class="small muted" style="margin-top:6px">平均：盈利 ${A.holding.avgWinnerHours === null ? '—' : A.holding.avgWinnerHours + ' h'} / 亏损 ${A.holding.avgLoserHours === null ? '—' : A.holding.avgLoserHours + ' h'}。${esc(A.holding.note)}</div></div>
          <div class="panel"><h3>MAE / MFE</h3><div class="muted small">已记录 ${A.maeMfe.recorded} / ${A.maeMfe.total} 笔。${esc(A.maeMfe.note)}</div></div>
          <div class="panel"><h3>Data Completeness</h3>
            <div class="small">平均完整度 <b>${A.dataCompletenessAvg}%</b></div>
            <div class="freq" style="margin-top:8px">${state.data.unknownFields.map((u) => `<div class="frow">
              <div>${esc(u.field)} <span class="small muted">${u.count} 笔</span></div>
              <div class="fbar"><i style="width:${Math.min(100, u.count * 25)}%"></i></div></div>`).join('')}</div>
            <div class="small muted" style="margin-top:6px">越靠上代表你复盘时越常忘记记录。</div></div>
          <div class="panel"><h3>Good / Bad 分类 <span class="hint small">§83</span></h3>
            <div class="badges-row"><span class="chip win">Good Win ${S.goodWins}</span><span class="chip warn">Bad Win ${S.badWins}</span>
              <span class="chip">Good Loss ${S.goodLosses}</span><span class="chip loss">Bad Loss ${S.badLosses}</span></div>
            <div class="small muted" style="margin-top:8px">分类依据是「是否遵守自己的规则」，不是赚没赚钱。Bad Win 最危险：它奖励了错误行为。</div></div>
        </div>
      </div>`;
  }

  /* ------------------------------------------------------------ Rules */
  function rulesView(v) {
    const R = state.data.rules;
    const cats = R.categories.filter((c) => R.generated.some((g) => g.category === c));
    v.innerHTML = `
      <div class="sec"><h2>Trading Rules <span class="hint">每条规则都能追溯到它从哪笔交易长出来</span></h2>
        <div class="analytics-grid">
          <div class="panel"><h3>文档内已有规则 <span class="hint small">sourceData</span></h3>
            ${R.doc.map((r) => `<div class="callout" style="margin-bottom:8px"><b>${esc(r.title)}</b><div class="small" style="margin-top:4px">${esc(r.body)}</div></div>`).join('') || '<div class="muted small">未记录</div>'}
          </div>
          <div class="panel"><h3>固定复盘模板</h3><ol class="reasons">${R.template.map((x) => `<li>${esc(typeof x === 'string' ? x : (x.text || x.label || ''))}</li>`).join('')}</ol></div>
        </div>
      </div>
      <div class="sec"><h2>由交易生成的 Next Rules <span class="hint">${R.generated.length} 条</span></h2>
        ${cats.map((c) => `<div class="panel" style="margin-bottom:12px"><h3>${esc(c)}</h3>
          ${R.generated.filter((g) => g.category === c).map((g) => `<div class="callout" style="margin-bottom:8px">
            ${esc(g.text)}
            <div class="small muted" style="margin-top:4px">Created From：<a href="#/trade/${encodeURIComponent(g.createdFrom)}" style="text-decoration:underline">${esc(g.createdFromLabel)}</a></div>
          </div>`).join('')}</div>`).join('') || '<div class="muted small">暂无</div>'}
      </div>`;
  }

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
