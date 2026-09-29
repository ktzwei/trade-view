#!/usr/bin/env python3
"""自动识别规则表（需求 §37：只做建议，不改原始数据）。

每条规则：
    re        正则
    v         命中后取的枚举值（必须在 schema.py 里有定义）
    sections  只在这些文档区块里找（防止把「目标里的 IMB」当成「入场 POI」）
    ctx       该句还必须出现这些关键词之一（可省）
    neg_v     句子被否定时改取的值；不写 = 否定即忽略

铁律：
- 否定句（没有 / 未 / 无 / 不应该 / 待补 …）不算命中，避免「未等待 LTF confirmation」
  被读成「用了 LTF Confirmation」这种反向错误。
- 复盘感想类区块（nextRule / improve / reviewConclusion …）默认不参与识别：
  那里写的是「以后应该怎样」，不是「当时怎么做的」。
- 认出来的值一律标 source=doc:keyword、confirmed=false，前端显示「自动识别 · 待确认」，
  并且带原文证据；用户在手填层确认或推翻。
"""

META_SECTIONS = {"nextRule", "nextRules", "improve", "reviewConclusion", "reviewAnalysis",
                 "worked", "riskCheck", "_notes", "notes", "structureNote"}

NEG_TOKENS = ["没有", "没了", "未", "无", "不", "没", "别", "非", "仅", "只", "暂", "待补",
              "尚未", "忘记", "漏", "忽略", "不应该", "not ", "n't", "without", "lack", "fail"]

# 整句级别的「无数据」标记：命中即视为该短句不是在陈述事实
NO_RECORD_TOKENS = ["未记录", "没有记录", "无记录", "不做推断", "不计入", "无法确认", "不确定",
                    "不做脑补", "未填写", "暂缺"]

# 纯占位句（还没成交/待补数据），整句跳过，避免把「是否出现 LTF confirmation」读成结论
PLACEHOLDER_MARKERS = ["待成交后补充", "待补充", "待填写", "待填：", "待补：", "待成交后再补"]

# 未来 / 建议语气：「以后应同时记录 Protected Low」这类句子不是当时的事实
FUTURE_MARKERS = ["以后应", "以后要", "以后需", "下次应", "下次要", "下回应", "今后", "将来", "待复盘中",
                  "建议以后", "记录时应注意"]

# 语义明确的「否定即取值」场景（Sweep 类）
RULES = {
    # ---------------- HTF Context (§7)
    "htfBias": [
        {"re": r"主要下跌结构|下跌结构|空头结构|bearish\s*structure|偏空|看跌",
         "v": "Bearish", "sections": ["context", "entryReason", "_extra"]},
        {"re": r"主要上涨结构|上涨结构|多头结构|bullish\s*structure|偏多|看涨",
         "v": "Bullish", "sections": ["context", "entryReason", "_extra"]},
        {"re": r"HTF\s*Bias\s*[:：]?\s*Neutral|方向\s*[:：]?\s*中性", "v": "Neutral",
         "sections": ["context", "_extra"]},
    ],
    "marketCondition": [
        {"re": r"震荡(?:行情|区间|市)|区间震荡|(?<!dealing )(?<!Dealing )\brange\b", "v": "Range",
         "sections": ["context", "_extra", "_notes"]},
        {"re": r"单边(?:行情|上涨|下跌)|趋势(?:行情|市)|\btrending\b", "v": "Trending",
         "sections": ["context", "_extra", "_notes"]},
        {"re": r"扩张(?:行情)?|\bexpansion\b", "v": "Expansion",
         "sections": ["context", "_extra", "_notes"]},
        {"re": r"收缩|窄幅|\bcompression\b", "v": "Compression",
         "sections": ["context", "_extra", "_notes"]},
        {"re": r"反转(?:行情|市)|\breversal\b", "v": "Reversal",
         "sections": ["context", "_extra", "_notes"]},
    ],
    # ---------------- Liquidity (§8)
    "liquidityType": [
        {"re": r"\bssl\b|下方流动性|卖方流动性|sell[- ]?side", "v": "SSL",
         "sections": ["context", "setup", "entryReason", "execution", "invalidation", "_extra"]},
        {"re": r"\bbsl\b|上方流动性|买方流动性|buy[- ]?side", "v": "BSL",
         "sections": ["context", "setup", "entryReason", "execution", "_extra"]},
        {"re": r"内部流动性|internal\s*liquidity", "v": "Internal Liquidity",
         "sections": ["context", "setup", "entryReason", "_extra"]},
        {"re": r"外部流动性|external\s*liquidity", "v": "External Liquidity",
         "sections": ["context", "setup", "entryReason", "_extra"]},
        {"re": r"\beql\b|等低(?:点)?|equal\s*low", "v": "Equal Low",
         "sections": ["context", "setup", "entryReason", "_extra"]},
        {"re": r"\beqh\b|等(?:高|高点)|equal\s*high", "v": "Equal High",
         "sections": ["context", "setup", "entryReason", "_extra"]},
        {"re": r"前高|previous\s*high|\bpdh\b|昨日高", "v": "Previous High",
         "sections": ["context", "setup", "targetLogic", "_extra"]},
        {"re": r"前低|previous\s*low|\bpdl\b|昨日低", "v": "Previous Low",
         "sections": ["context", "setup", "targetLogic", "_extra"]},
    ],
    "liquiditySweep": [
        {"re": r"[Ss]weep|被扫|扫了|扫单|流动性被吃|假突破后收回|liquidity\s*hunt|测试.{0,4}流动性",
         "v": "Yes", "neg_v": "No",
         "sections": ["context", "setup", "entryReason", "execution", "_extra"]},
        {"re": r"部分扫|partial(?:ly)?\s*sweep", "v": "Partial",
         "sections": ["context", "setup", "execution", "_extra"]},
    ],
    "sweepQuality": [
        {"re": r"(?:[Ss]weep|扫)(?!\s*→)\s*[^。；\n]{0,4}(?:很强|强势|干净|彻底|爽快)",
         "v": "Strong", "sections": ["context", "setup", "execution", "_extra"]},
        {"re": r"(?:[Ss]weep|扫)(?!\s*→)\s*[^。；\n]{0,4}(?:偏弱|很弱|弱|\bweak\b)",
         "v": "Weak", "sections": ["context", "setup", "execution", "_extra"]},
    ],
    # ---------------- POI (§9)
    "htfPOIType": [
        {"re": r"\b(1D|4H|1H)\b[^。；\n]{0,12}?\b(BB|OB|IMB|FVG|Breaker|Mitigation\s*Block)\b",
         "g": 2, "all": True, "v": "OB",
         "sections": ["context", "setup", "entryReason", "execution", "_extra"]},
    ],
    "ltfPOIType": [
        {"re": r"\b(15m|5m|15\s?min|5\s?min|15分钟|5分钟)\b[^。；\n]{0,12}?\b(BB|OB|IMB|FVG|Breaker)\b",
         "g": 2, "all": True, "v": "OB",
         "sections": ["context", "setup", "entryReason", "execution", "_extra"]},
    ],
    "poiConfluence": [
        {"re": r"折价|discount", "v": "Discount", "sections": ["context", "setup", "entryReason", "_extra"]},
        {"re": r"溢价|premium", "v": "Premium", "sections": ["context", "setup", "entryReason", "_extra"]},
        {"re": r"\bote\b|最优交易区", "v": "OTE", "sections": ["context", "setup", "_extra"]},
    ],
    # ---------------- Reaction (§10)
    "reaction": [
        {"re": r"反应(?:很|相当|明显)?强|强烈拒绝|strong\s*reaction", "v": "Strong",
         "sections": ["context", "execution", "_extra"]},
        {"re": r"反应(?:偏|较)?弱|无明显反应|没有反应|毫无反应|weak\s*reaction", "v": "Weak",
         "sections": ["context", "execution", "_extra"]},
    ],
    "reactionType": [
        {"re": r"\brejection\b|插针回落|长上影|长下影|拒绝", "v": "Rejection",
         "sections": ["context", "execution", "_extra"]},
        {"re": r"动能转换|momentum\s*shift|动能(?:明显)?转变", "v": "Momentum Shift",
         "sections": ["context", "execution", "_extra"]},
        {"re": r"k线反转|candle\s*reversal|吞没", "v": "Candle Reversal",
         "sections": ["context", "execution", "_extra"]},
        {"re": r"盘整|consolidation|横盘", "v": "Consolidation",
         "sections": ["context", "execution", "_extra"]},
    ],
    # ---------------- Displacement (§11)
    "displacementQuality": [
        {"re": r"强势\s*(?:bullish|bearish)?\s*[Dd]isplacement|强(?:烈)?位移|strong\s*[Dd]isplacement",
         "v": "Strong", "sections": ["context", "setup", "execution", "_extra"]},
        {"re": r"位移偏弱|[Dd]isplacement\s*偏弱|位移(?:明显)?(?:很|较|偏)?弱|weak\s*[Dd]isplacement",
         "v": "Weak", "sections": ["context", "setup", "execution", "_extra"]},
        {"re": r"medium\s*[Dd]isplacement|位移中等", "v": "Medium",
         "sections": ["context", "setup", "execution", "_extra"]},
    ],
    # ---------------- Structure (§12)
    "structureShiftType": [
        {"re": r"\bmss\b|市场结构转换", "v": "MSS",
         "sections": ["context", "setup", "entryReason", "execution", "_extra"]},
        {"re": r"\bmsb\b|市场结构突破", "v": "MSB",
         "sections": ["context", "setup", "entryReason", "execution", "_extra"]},
        {"re": r"\bbos\b|结构突破|break\s*of\s*structure", "v": "BOS",
         "sections": ["context", "setup", "entryReason", "execution", "_extra"]},
        {"re": r"\bchoch\b|性质转变", "v": "CHOCH",
         "sections": ["context", "setup", "entryReason", "execution", "_extra"]},
    ],
    "brokenStructure": [
        {"re": r"[Ii]nternal\s*LH|内部\s*LH|内部(?:高点|低点)(?:被)?(?:突破|破坏)",
         "v": "Internal LH", "sections": ["context", "setup", "entryReason", "execution", "_extra"]},
        {"re": r"[Kk]ey\s*LH|关键\s*LH|关键(?:高点|低点)(?:被)?(?:突破|破坏)",
         "v": "Key LH", "sections": ["context", "setup", "entryReason", "execution", "_extra"]},
        {"re": r"protected\s*high|保护高点", "v": "Protected High",
         "sections": ["context", "setup", "invalidation", "_extra"]},
        {"re": r"protected\s*low|保护低点", "v": "Protected Low",
         "sections": ["context", "setup", "invalidation", "_extra"]},
        {"re": r"外部结构|external\s*structure", "v": "External Structure",
         "sections": ["context", "setup", "targetLogic", "_extra"]},
        {"re": r"内部(?:小)?结构(?:被)?(?:突破|破坏)|突破内部(?:小)?结构", "v": "Internal Structure",
         "sections": ["context", "setup", "entryReason", "execution", "_extra"]},
        {"re": r"关键结构(?:被)?(?:突破|破坏)|突破关键结构|结构(?:被)?(?:明显)?突破",
         "v": "Key Structure", "sections": ["context", "setup", "entryReason", "execution", "_extra"]},
    ],
    # ---------------- Protected Structure (§13)
    "protectedStructure": [
        {"re": r"protected\s*low|保护低点", "v": "Protected Low",
         "sections": ["context", "setup", "invalidation", "entryModel", "_extra", "_notes"]},
        {"re": r"protected\s*high|保护高点", "v": "Protected High",
         "sections": ["context", "setup", "invalidation", "entryModel", "_extra", "_notes"]},
    ],
    # ---------------- Entry Trigger (§15)
    "entryTriggerType": [
        {"re": r"[Ss]weep|被扫", "v": "Sweep",
         "sections": ["setup", "entryReason", "execution", "_extra"]},
        {"re": r"首次回撤|first\s*retracement|第一次回撤", "v": "First Retracement",
         "sections": ["setup", "entryReason", "execution", "_extra"]},
        {"re": r"fvg\s*(?:回测|retest)", "v": "FVG Retest",
         "sections": ["setup", "entryReason", "execution", "_extra"]},
        {"re": r"ob\s*(?:回测|retest)", "v": "OB Retest",
         "sections": ["setup", "entryReason", "execution", "_extra"]},
        {"re": r"\bmss\b", "v": "MSS", "sections": ["setup", "entryReason", "execution", "_extra"]},
        {"re": r"\bmsb\b", "v": "MSB", "sections": ["setup", "entryReason", "execution", "_extra"]},
        {"re": r"\bbos\b", "v": "BOS", "sections": ["setup", "entryReason", "execution", "_extra"]},
        {"re": r"[Dd]isplacement|位移", "v": "Displacement",
         "sections": ["setup", "entryReason", "execution", "_extra"]},
        {"re": r"触碰\s*POI|到达\s*POI|poi\s*touch", "v": "POI Touch",
         "sections": ["setup", "entryReason", "execution", "_extra"]},
    ],
    # ---------------- Invalidation (§17)
    "invalidationLogic": [
        {"re": r"protected\s*low|保护低点", "v": "Protected Low",
         "sections": ["invalidation", "execution", "entryModel", "_extra"]},
        {"re": r"protected\s*high|保护高点", "v": "Protected High",
         "sections": ["invalidation", "execution", "entryModel", "_extra"]},
        {"re": r"ob\s*失效|ob\s*invalidated", "v": "OB Invalidated",
         "sections": ["invalidation", "execution", "_extra"]},
        {"re": r"结构失效|structure\s*invalidated|结构被破坏|结构低点|结构高点",
         "v": "Structure Invalidated", "sections": ["invalidation", "execution", "_extra"]},
        {"re": r"bias\s*失效|方向失效|htf\s*bias\s*invalidated", "v": "HTF Bias Invalidated",
         "sections": ["invalidation", "execution", "_extra"]},
        {"re": r"扫低点|sweep\s*low", "v": "Sweep Low", "sections": ["invalidation", "_extra"]},
        {"re": r"扫高点|sweep\s*high", "v": "Sweep High", "sections": ["invalidation", "_extra"]},
    ],
    # ---------------- Target 层级 (§18)
    "targetLevel": [
        {"re": r"(?:1D|4H|1H)[^，,；。]{0,12}(?:内部流动性|流动性)|(?:内部流动性|流动性)[^，,；。]{0,12}(?:1D|4H|1H)",
         "v": "HTF Liquidity", "sections": ["targetLogic", "setup", "_extra", "_notes"]},
        {"re": r"内部流动性|internal\s*liquidity", "v": "LTF Internal Liquidity",
         "sections": ["targetLogic", "setup", "_extra", "_notes"]},
        {"re": r"外部流动性|external\s*liquidity", "v": "External Liquidity",
         "sections": ["targetLogic", "setup", "_extra", "_notes"]},
        {"re": r"(?:4H|1D)\s*swing|htf\s*swing", "v": "HTF Swing High/Low",
         "sections": ["targetLogic", "setup", "_extra", "_notes"]},
        {"re": r"1H\s*流动性|htf\s*流动性|上方流动性|买方流动性|\bbsl\b", "v": "HTF Liquidity",
         "sections": ["targetLogic", "setup", "_extra", "_notes"]},
    ],
    # ---------------- Management (§20)
    "managementStyle": [
        {"re": r"分批止盈|部分止盈|partial\s*tp", "v": "Partial TP",
         "sections": ["execution", "entryModel", "worked", "_extra"]},
        {"re": r"移动\s*SL\s*(?:到|至)\s*(?:保本|BE)|sl\s*(?:移|挪)[^。；]{0,4}保本|move\s*sl\s*to\s*be",
         "v": "Move SL to BE", "sections": ["execution", "entryModel", "_extra"]},
        {"re": r"移动止损|trailing\s*stop", "v": "Trailing Stop",
         "sections": ["execution", "entryModel", "_extra"]},
        {"re": r"挂上不管|set\s*and\s*forget|不干预", "v": "Set and Forget",
         "sections": ["execution", "entryModel", "_extra"]},
    ],
}

# Entry Mode 单独处理（要区分「计划」和「实际」，需求 §14 / §16）
ENTRY_MODE_RULES = [
    (r"\bltf\s*confirmation|低周期确认|等待\s*(?:15m|5m)[^。；]{0,8}确认|15m\s*确认|5m\s*确认",
     "LTF Confirmation"),
    (r"\blimit\b|限价单|挂单|预设(?:的)?\s*(?:[Ll]imit|挂单)", "Limit"),
    (r"市价|market\s*entry|直接进", "Market"),
]
PLAN_MARKERS = ["原计划", "计划", "预案", "预设", "本来打算", "planned"]
ACTUAL_MARKERS = ["实际执行", "实际", "最终", "最后", "真实执行", "执行了", "结果执行"]
