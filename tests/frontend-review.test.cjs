const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'assets/app.js'), 'utf8');
const context = { fetch: () => new Promise(() => {}), URLSearchParams, Date };
vm.createContext(context);
vm.runInContext(source.replace(/\}\)\(\);\s*$/, `globalThis.reviewTest = {
  state, metrics, srcBadge, entryModeCol, planSection, execSection, reviewSection,
  behaviorBlock, overviewView, analyticsView, rulesBuckets, weekV2, maeMfeBlock, chainBlock, filtered
};})();`), context);
const api = context.reviewTest;
api.state.data = JSON.parse(fs.readFileSync(path.join(root, 'data/trades.json'), 'utf8'));
const f = (value) => ({ value, source: 'manual', confirmed: true });
const good = { id: 'good', direction: 'long', resultStatus: 'win', actualR: 1, rIncluded: true,
  quality: { value: 'Good Win' }, complianceV2: { compliance: 'Fully Compliant' } };
const bad = { ...good, id: 'bad', resultStatus: 'loss', actualR: -1,
  quality: { value: 'Bad Loss' }, complianceV2: { compliance: 'Major Violation' } };
const unknown = { ...good, id: 'unknown', quality: { value: null }, complianceV2: {} };
const metrics = api.metrics([good, bad, unknown]);
assert.equal(metrics.goodRate, .5);
assert.equal(metrics.qualityJudged, 2);
assert.equal(metrics.qualityUnknown, 1);
assert.equal(metrics.qualityCoverage, 2 / 3);
assert.equal(metrics.compRate, .5);
const conflict = { ...bad, id: 'conflict', fields: { tradeQuality: f('Good Loss') },
  quality: { value: null, source: 'conflict', reportedQuality: 'Good Loss',
    checklistCompliance: 'Major Violation', basis: '判定冲突：Good Loss 与 Major Violation 不一致' } };
assert.equal(api.metrics([conflict]).qualityJudged, 0);
assert.match(api.reviewSection(conflict), /判定冲突：Good Loss 与 Major Violation/);
assert.doesNotMatch(api.reviewSection(conflict), /class="on">Good Loss/);
const originalData = api.state.data;
api.state.data = { ...originalData, trades: [conflict] };
api.state.range = 'all';
api.state.filters = { tradeQuality: 'Good Loss' };
assert.equal(api.filtered().length, 0);
api.state.filters = { ruleCompliance: 'Major Violation' };
assert.equal(api.filtered().length, 1);
api.state.data = originalData;
api.state.filters = {};
assert.match(api.srcBadge({ source: 'doc:keyword', confirmed: false }), /自动识别·待确认/);

const t = { ...good, fields: { confirmationMode: f('LTF Confirmation'), orderType: f('Limit'),
  reviewModel: f('LTF Confirmation') }, review: {}, analysis: {},
  plannedVsActual: { planned: { entry: 100, sl: 95, tp: 110, rr: 2 },
    actual: { entry: 103, exit: 110, r: 1 }, timingNote: '交易前记录',
    deviations: [{ field: 'entry', difference: 3, note: '成交价与计划价格不同' }] } };
assert.equal(api.entryModeCol(t), 'LTF Confirmation · Limit');
assert.match(api.planSection(t), /100\.00/);
assert.match(api.execSection(t), /103\.00/);
assert.match(api.execSection(t), /实际下单方式/);
const excursionHtml = api.maeMfeBlock({ ...t, maeMfe: { mae: -.9, mfe: 2 } });
assert.doesNotMatch(excursionHtml, /SL 可能偏紧|SL 相对宽松|止盈偏早|出场时机基本合理|NaN/);
assert.match(excursionHtml, /交易前退出规则/);
assert.doesNotMatch(api.chainBlock(t), /三选一/);
assert.match(api.behaviorBlock({}), /Google 文档的【周复盘】/);
const weeklyHtml = api.behaviorBlock({ behaviorReview: {
  goal: { week: '第1周', action: '入场前保存截图', trigger: '确认型 Setup', metric: '截图数/适用次数' },
  eligible: 3, completed: 2, completionRate: 2 / 3, reflection: '漏了一次'
} });
assert.match(weeklyHtml, /检查 第1周 的约定：入场前保存截图/);
assert.match(weeklyHtml, /完成 2 \/ 3 次 · 完成率 67%/);
for (const html of [api.planSection(t), api.execSection(t), api.reviewSection(t),
  api.behaviorBlock({ behaviorGoal: { action: '<script>', trigger: 'setup', metric: 'count' } })]) {
  assert.doesNotMatch(html, /\[object Object\]|NaN|<script>/);
}
api.state.range = 'all';
for (const tab of ['setup', 'entry', 'poi', 'structure', 'mistakes', 'risk']) {
  const view = { innerHTML: '' };
  api.analyticsView(view, tab);
  assert.match(view.innerHTML, /以下分析基于全部/);
  assert.doesNotMatch(view.innerHTML, /\[object Object\]|NaN/);
}
const view = { innerHTML: '' };
api.overviewView(view);
assert.match(view.innerHTML, /已判/);
assert.match(view.innerHTML, /每周只验证一个行为/);
assert.doesNotMatch(view.innerHTML, /\[object Object\]|NaN/);
console.log('Frontend review regression checks passed.');
