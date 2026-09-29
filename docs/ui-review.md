# UI 整改落地对照（《交易复盘系统 UI 整改意见》§一–§二十）

原则（§一）：**本次不新增功能**，只做信息架构、页面减负、卡片合并、导航精简、标签中性化、高级字段折叠。
数据层 / 解析层 / 统计层未改；改动全部在展示层（`index.html` + `assets/app.js` + `assets/app.css`）。

| 节 | 要求 | 落地 | 状态 |
|---|---|---|---|
| §二 | 一级导航精简为 Overview / Trades / Analytics / Rules，Weeks 下线 | 导航改为 4 项；`#/weeks` 仍可访问，改为 Overview 内折叠入口「周复盘明细」 | ✅ |
| §二 | Overview 支持本周 / 上周 / 本月切换 | 顶栏时间范围：本周（默认）/ 上周 / 本月 / 全部；按交易日期判断，**没写日期的不隐藏**（不猜） | ✅ |
| §三 | 首页 6 个核心指标 | Net R · Trades · Win Rate · Expectancy · Good Trade Rate · Rule Compliance（口径与 stats 层一致，按当前范围实时算） | ✅ |
| §三 | 首页顺序：R Curve → Recent Trades → This Week Focus | 三段依次；This Week Focus 取周复盘三问：本周主要问题 / 下周重点 / 做得好的 | ✅ |
| §三 | 首页不继续堆模块 | 原 §41 答卡（14 张）移到 Analytics 底部折叠；周复盘明细折叠在 Overview，默认收起 | ✅ |
| §四 | 交易详情统一三段式 PLAN → EXECUTION → REVIEW | 详情页默认只有：截图 Tab、PLAN、EXECUTION、REVIEW、Advanced（折叠） | ✅ |
| §五 | PLAN：HTF Context / POI / Liquidity / Trade Plan | 「HTF — Why」链：HTF Context → Liquidity → POI；Trade Plan 显示 Direction / Plan Entry / Plan SL / Plan TP（文档写的是文字就标「Plan Target」并附原文）/ Planned RR | ✅ |
| §六 | EXECUTION：LTF Confirmation / Entry Mode / Actual | 「LTF — When」链：Sweep → Displacement → MSS·MSB → Entry Trigger；Entry Mode 三段条（Limit Entry / LTF Confirmation / Market Entry）高亮当前；Actual Entry / Exit / R | ✅ |
| §七 | REVIEW：Result / Trade Quality / Mistake / Lesson | Result 大字 R；Quality 四档条（Good Win / Good Loss / Bad Win / Bad Loss）；Mistake 标签；Lesson（问题 + 下次怎么改 + 做对了），不写作文 | ✅ |
| §八 | 高级字段不默认展开，核心 10~12 个 | 默认只留三段式核心字段；Protected Price / MAE / MFE / Confidence / 结构化复盘链 / 规则清单 / Planned vs Actual / 原始记录全部收进「更多细节 / Advanced」 | ✅ |
| §九 | HTF / LTF 视觉分组 | 「HTF — Why」（Bias → Liquidity → POI）与「LTF — When」（Sweep → Displacement → MSS/MSB → Entry），带周期徽标（1D/4H/1H、15m/5m） | ✅ |
| §十 | 截图用 Tab / Gallery，不纵向堆叠 | 截图区按 **HTF / 15min / 5min / Result / 其他** 分 Tab，默认一张大图，缩略图切换，点大图放大（灯箱） | ✅ |
| §十一 | 颜色系统统一，SMC 概念不彩色化 | POI / 周期 / 方向 / 来源标签全部改中性灰；颜色只保留：盈利绿、亏损红、违规、Good Trade、当前改进重点 | ✅ |
| §十二 | Analytics 问题驱动，不做图表博物馆 | 顶部 6 个问题入口：Setup / Entry / POI / Structure / Mistakes / Risk；默认只渲染当前这一个面板 | ✅ |
| §十三 | Entry：Limit vs LTF Confirmation vs Market | 三种入场方式 × Trades / Win Rate / Avg R / Expectancy / Profit Factor 对照表（另附入场周期、限价方式分布） | ✅ |
| §十四 | Structure：Internal MSB / Key Structure Break / Protected | 结构类型、结构周期、Broken Structure、Protected Structure、位移质量维度表；并提示「Internal / Key / Protected 要分清」 | ✅ |
| §十五 | Mistakes：次数 + 损失 R，直接给「最该先改」 | 错误清单（次数 / 损失 R / 相关笔数 / 出现哪些交易）+ 顶部结论「最该先改：X —— 出现 N 次，损失 X R」 | ✅ |
| §十六 | Trades 列表只保留 7 列 | Date · Symbol · Direction · Setup · Entry Mode · Result · Quality；点开进三段式详情；筛选收进折叠 | ✅ |
| §十七 | 一个决策阶段 = 一个区域，不再一概念一卡片 | 详见 §五–§七；概念卡片（Bias/Liquidity/POI/Sweep/Reaction…）合并进 PLAN / EXECUTION 的链式区域 | ✅ |
| §十八 | 最终四模块结构 | Overview（6 指标 + R Curve + Recent Trades + 本周重点）/ Trades（列表 + 三段式详情）/ Analytics（6 个问题）/ Rules（Must Have / Confirmation / Avoid） | ✅ |
| §十九 | 不新增 Dashboard / 图表 / 页面 / 卡片 / 动画 | 未新增页面与动画；Analytics 面板数减少（原来一次铺开全部图表） | ✅ |
| §二十 | 3 秒看本周、30 秒看一笔 | 首页默认「本周」+ 6 指标；详情页三段式 + 截图 Tab，高级字段默认收起 | ✅ |

## 保留未动（有意为之）
- 数据口径与「未记录」原则：缺项一律显示「未记录」，不当 0 算（需求 §4.1 / §37）。
- 每条 AI 判定仍带原文引用，「自动识别」在网站里标记为「建议·待确认」。
- MAE / MFE / Protected Price 等字段仍在（只搬进 Advanced），统计口径未变。

## 复核命令
```bash
cd ~/code/web3/trade-view
python3 parser/parse_gdoc.py && python3 parser/build.py && python3 parser/selfcheck.py
node /tmp/tv_smoke4.mjs        # 22 项视图渲染断言
bash /tmp/tv_domcheck.sh       # 真实 Chrome 渲染各页 DOM 到 /tmp/dom_*.html
./publish.sh
```
