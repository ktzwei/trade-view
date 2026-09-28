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
  const nr = (v, fmt) => (v === null || v === undefined || v === '' ? NR : (fmt ? fmt(v) : esc(v)));
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
    </div>`;
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
      ${(rev.mainStrength || rev.mainProblem || rev.newRule) ? `<div class="week-core">
        ${rev.mainStrength ? `<div class="wr good"><div class="k">做得好</div><div class="v">${esc(rev.mainStrength.text)}</div></div>` : ''}
        ${rev.mainProblem ? `<div class="wr bad"><div class="k">主要问题</div><div class="v">${esc(rev.mainProblem.text)}</div></div>` : ''}
        ${rev.newRule ? `<div class="wr rule"><div class="k">新规则</div><div class="v">${esc(rev.newRule.text)}</div></div>` : ''}
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

      ${imgs.length ? `<div class="card chart-wrap" style="margin-top:14px">
        <img class="chart-main" id="main-chart" src="${esc(imgs[0].path)}" alt="${esc(t.symbolLabel)} 图表">
        <div class="chart-bar"><span>${esc(imgs[0].caption || '文档内嵌交易图')}（点击放大）</span>
          <span>${lens.length ? '参考周期 ' + esc(lens.join('/').toUpperCase()) : ''}</span></div>
        ${imgs.length > 1 ? `<div class="gallery">${imgs.map((i, n) => `<img src="${esc(i.path)}" data-lb="${n}" alt="图 ${n + 1}">`).join('')}</div>` : ''}
      </div>` : '<div class="empty">这笔交易还没有绑定图表。</div>'}

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
        <details class="fold"><summary>更多统计（持仓时间 / MAE·MFE / Good-Bad 分类）</summary>
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
      </div>`;
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
      <details class="fold"><summary>文档里原有的规则与固定复盘模板</summary>
        <div class="analytics-grid" style="margin-top:10px">
          <div class="panel"><h3>SMC 执行规则（原文）</h3>
            ${R.doc.map((r) => `<div class="callout" style="margin-bottom:8px"><b>${esc(r.title)}</b><div class="small" style="margin-top:4px">${esc(r.body)}</div></div>`).join('') || '<div class="muted small">未记录</div>'}</div>
          <div class="panel"><h3>固定复盘模板</h3><ol class="reasons">${R.template.map((x) => `<li>${esc(typeof x === 'string' ? x : (x.text || x.label || ''))}</li>`).join('')}</ol></div>
        </div>
      </details>`;
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
