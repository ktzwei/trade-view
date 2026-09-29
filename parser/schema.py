#!/usr/bin/env python3
"""统一字段字典 —— 整个系统的 single source of truth。

时间周期定义（需求 §2）：
    HTF = 1D / 4H / 1H   → Context / Bias / Liquidity / POI / Major Structure / Target
    LTF = 15min / 5min   → Reaction / Sweep / Displacement / Structure Shift / Entry

字段分层（需求 §4.1 / §35）：
    tier = "core"      单笔默认显示的字段
    tier = "advanced"  折叠进「更多细节」的字段

三条铁律（需求 §37）：
    1. 选项只有这里定义的枚举值，其它一律非法（validate_override 会报错）。
    2. 文档没写的字段 = null，前端显示「未记录」，不做默认值填充。
    3. 凡是从原文字面自动识别出来的值，必须带 evidence（原文句子），
       来源标 doc:keyword；用户手动选的标 manual；文档直接写标签的标 doc:label。
"""

SCHEMA_VERSION = "2.0"

HTF_TF = ["1D", "4H", "1H"]
LTF_TF = ["15m", "5m"]
ALL_TF = HTF_TF + LTF_TF


def F(key, label, options, group, multi=False, tier="core", note=None):
    return {"key": key, "label": label, "options": list(options), "group": group,
            "multi": multi, "tier": tier, "note": note}


# ---------------------------------------------------------------- 枚举字段
FIELDS = [
    # --- HTF Context (§7)
    F("htfBias", "HTF Bias（大方向）", ["Bullish", "Bearish", "Neutral"], "HTF Context"),
    F("biasSourceTF", "Bias 来源周期", HTF_TF, "HTF Context", multi=True),
    F("marketCondition", "市场环境（Market Condition）",
      ["Trending", "Range", "Expansion", "Compression", "Reversal", "Unclear"], "HTF Context"),
    F("htfStructureTF", "HTF 结构对应周期", HTF_TF, "HTF Context", multi=True),
    F("htfStructureKind", "HTF 结构类型",
      ["Bullish Structure", "Bearish Structure", "Range", "Transition"], "HTF Context", multi=True),

    # --- Liquidity (§8)
    F("liquidityType", "流动性类型",
      ["BSL", "SSL", "Internal Liquidity", "External Liquidity", "Equal High", "Equal Low",
       "Previous High", "Previous Low", "Swing High", "Swing Low"], "Liquidity", multi=True),
    F("liquidityTF", "流动性周期", ALL_TF, "Liquidity", multi=True),
    F("liquiditySweep", "是否被扫（Sweep）", ["Yes", "No", "Partial"], "Liquidity"),
    F("sweepQuality", "Sweep 质量", ["Strong", "Normal", "Weak"], "Liquidity"),
    F("sweepTF", "Sweep 观察周期", LTF_TF, "Liquidity", multi=True),

    # --- POI (§9)
    F("htfPOIType", "HTF POI 类型",
      ["OB", "FVG", "IMB", "Breaker", "Mitigation Block", "Support", "Resistance",
       "Previous High", "Previous Low", "Premium", "Discount", "OTE", "Supply", "Demand"],
      "POI", multi=True),
    F("htfPOITF", "HTF POI 周期", HTF_TF, "POI", multi=True),
    F("ltfPOIType", "LTF Entry POI 类型",
      ["OB", "FVG", "IMB", "Breaker", "Mitigation Block", "Support", "Resistance",
       "Previous High", "Previous Low", "Premium", "Discount", "OTE", "Supply", "Demand"],
      "POI", multi=True),
    F("ltfPOITF", "LTF Entry POI 周期", LTF_TF, "POI", multi=True),
    F("poiConfluence", "POI Confluence（多因素共振）",
      ["OB", "FVG", "IMB", "Breaker", "Mitigation Block", "Premium", "Discount", "OTE",
       "BSL", "SSL", "HTF Structure", "HTF Bias 一致"], "POI", multi=True),

    # --- Reaction (§10)
    F("reaction", "Reaction（到达 POI 后的反应）", ["Strong", "Weak", "No Reaction"], "LTF Entry"),
    F("reactionTF", "Reaction 周期", LTF_TF, "LTF Entry", multi=True),
    F("reactionType", "Reaction 类型",
      ["Rejection", "Sweep", "Momentum Shift", "Candle Reversal", "Consolidation",
       "Immediate Displacement"], "LTF Entry", multi=True),

    # --- Displacement (§11)
    F("displacementTF", "Displacement 所在周期", LTF_TF, "LTF Entry", multi=True),
    F("displacementQuality", "Displacement 质量", ["Strong", "Medium", "Weak"], "LTF Entry"),

    # --- Structure (§12)
    F("structureShiftType", "结构变化类型",
      ["MSB", "MSS", "BOS", "CHOCH", "None"], "Structure", multi=True),
    F("structureShiftTF", "结构变化周期", LTF_TF, "Structure", multi=True),
    F("brokenStructure", "被破坏的结构（Broken Structure）",
      ["Internal Structure", "Internal LH", "Internal HL", "Key Structure", "Key LH", "Key HL",
       "Protected High", "Protected Low", "External Structure"], "Structure", multi=True),

    # --- Protected Structure (§13)
    F("protectedStructure", "Protected Structure", ["Protected High", "Protected Low", "None"],
      "Structure"),
    F("protectedTF", "Protected Structure 周期", ALL_TF, "Structure", multi=True),

    # --- Entry (§14 / §15)
    F("entryMode", "Entry Mode（入场方式）", ["Limit", "LTF Confirmation", "Market"], "Entry"),
    F("limitStyle", "Limit 挂单方式",
      ["HTF POI Limit", "OB Limit", "FVG Limit", "50% FVG Limit"], "Entry"),
    F("entryTriggerType", "Entry Trigger",
      ["POI Touch", "Sweep", "MSB", "MSS", "BOS", "Displacement", "FVG Retest", "OB Retest",
       "Breaker Retest", "Rejection", "First Retracement"], "Entry", multi=True),
    F("entryTriggerTF", "Entry Trigger 周期", LTF_TF, "Entry", multi=True),

    # --- Invalidation (§17)
    F("invalidationLogic", "Invalidation 依据",
      ["Sweep Low", "Sweep High", "Protected Low", "Protected High", "OB Invalidated",
       "Structure Invalidated", "HTF Bias Invalidated"], "Invalidation", multi=True),
    F("invalidationTF", "Invalidation 周期", ALL_TF, "Invalidation", multi=True),

    # --- Target (§18)
    F("targetLevel", "Target 结构层级",
      ["LTF Internal Liquidity", "HTF Liquidity", "HTF Swing High/Low", "External Liquidity"],
      "Target", multi=True),

    # --- Management (§20)
    F("managementStyle", "Trade Management 方式",
      ["Set and Forget", "Manual", "Partial TP", "Move SL to BE", "Trailing Stop"],
      "Management", multi=True),
    F("movedSL", "移动过 SL", ["Yes", "No"], "Management", tier="advanced"),
    F("earlyExit", "提前止盈", ["Yes", "No"], "Management", tier="advanced"),
    F("reducedPosition", "减仓", ["Yes", "No"], "Management", tier="advanced"),
    F("addedPosition", "加仓", ["Yes", "No"], "Management", tier="advanced"),

    # --- Compliance (§21) / Quality (§23) / Confidence (§26)
    F("ruleCompliance", "Rule Compliance（规则符合度）",
      ["Fully Compliant", "Minor Violation", "Major Violation"], "Review"),
    F("shouldTake", "Should I Take This Trade?", ["Yes", "No", "Borderline"], "Review"),
    F("tradeQuality", "Trade Quality", ["Good Win", "Good Loss", "Bad Win", "Bad Loss"], "Review"),
    F("confidence", "Confidence Before Trade（交易前信心 1–5）", ["1", "2", "3", "4", "5"],
      "Review", tier="advanced",
      note="必须交易前记录，不允许交易结束后回填。"),
]

FIELD_BY_KEY = {f["key"]: f for f in FIELDS}


# ---------------------------------------------------------------- Mistake Tags (§22)
MISTAKE_GROUPS = {
    "Setup": ["Wrong HTF Bias", "Wrong POI", "Weak POI", "No Sweep", "Bad Liquidity Read",
              "No Displacement", "Weak Displacement", "Weak MSB", "Internal MSB Only",
              "Against Structure", "Poor RR"],
    "Entry": ["Front Run", "Early Entry", "Late Entry", "FOMO", "Chase Price",
              "Missed Confirmation"],
    "Risk": ["SL Too Tight", "SL Too Wide", "Oversized Position", "Poor Risk Management"],
    "Exit": ["Early Exit", "Late Exit", "Move SL Too Early", "Move SL to BE Too Early",
             "Hold Too Long"],
    "Psychology": ["Revenge Trade", "FOMO", "Overconfidence", "Fear", "Impatience", "Hesitation"],
}
MISTAKE_TAGS = [t for tags in MISTAKE_GROUPS.values() for t in tags]
# 去重（需求 §22 里 FOMO 在 Entry 与 Psychology 各列一次），并保留「标签 → 分类」反查表
MISTAKE_TAGS = list(dict.fromkeys(MISTAKE_TAGS))
MISTAKE_CATEGORY = {tag: cat for cat, tags in MISTAKE_GROUPS.items() for tag in tags}

# 交易错误标签（多选，需求 §22）。放进统一字段字典，解析 / 统计 / 前端共用一套值。
FIELDS.append({"key": "mistakes", "label": "错误标签（Mistake Tags）", "group": "Review",
               "multi": True, "tier": "core", "options": MISTAKE_TAGS,
               "note": "可多选（需求 §22）；用于统计「最常出现的错误」「损失最大的错误」。"})
FIELD_BY_KEY = {f["key"]: f for f in FIELDS}


# ---------------------------------------------------------------- 中文标签（前端显示）
ZH = {
    "Bullish": "看涨", "Bearish": "看跌", "Neutral": "中性",
    "Trending": "趋势", "Range": "震荡", "Expansion": "扩张", "Compression": "收缩",
    "Reversal": "反转", "Unclear": "不清晰",
    "Bullish Structure": "多头结构", "Bearish Structure": "空头结构", "Transition": "过渡期",
    "BSL": "买方流动性", "SSL": "卖方流动性", "Internal Liquidity": "内部流动性",
    "External Liquidity": "外部流动性", "Equal High": "等高", "Equal Low": "等低",
    "Previous High": "前高", "Previous Low": "前低", "Swing High": "摆动高点",
    "Swing Low": "摆动低点",
    "Yes": "是", "No": "否", "Partial": "部分",
    "Strong": "强", "Normal": "正常", "Weak": "弱", "Medium": "中等",
    "Rejection": "拒绝", "Sweep": "扫单", "Momentum Shift": "动能转换",
    "Candle Reversal": "K线反转", "Consolidation": "盘整", "Immediate Displacement": "立刻位移",
    "OB": "订单块", "FVG": "公平价值缺口", "IMB": "失衡", "Breaker": "破坏块",
    "Mitigation Block": "缓解块", "Support": "支撑", "Resistance": "阻力",
    "Premium": "溢价区", "Discount": "折价区", "OTE": "最优交易区",
    "Supply": "供给", "Demand": "需求",
    "No Reaction": "无反应",
    "MSB": "市场结构突破", "MSS": "市场结构转换", "BOS": "结构突破",
    "CHOCH": "性质转变", "None": "无",
    "Internal LH": "内部低高点", "Internal HL": "内部高低点", "Key LH": "关键低高点",
    "Key HL": "关键高低点", "Protected High": "受保护高点", "Protected Low": "受保护低点",
    "External Structure": "外部结构",
    "Limit": "提前挂单", "LTF Confirmation": "低周期确认", "Market": "市价",
    "HTF POI Limit": "HTF POI 挂单", "OB Limit": "OB 挂单", "FVG Limit": "FVG 挂单",
    "50% FVG Limit": "FVG 50% 挂单",
    "POI Touch": "触碰 POI", "FVG Retest": "FVG 回测", "OB Retest": "OB 回测",
    "Breaker Retest": "Breaker 回测", "First Retracement": "首次回撤",
    "Sweep Low": "扫低点", "Sweep High": "扫高点", "OB Invalidated": "OB 失效",
    "Structure Invalidated": "结构失效", "HTF Bias Invalidated": "HTF Bias 失效",
    "LTF Internal Liquidity": "LTF 内部流动性", "HTF Liquidity": "HTF 流动性",
    "HTF Swing High/Low": "HTF 摆动高低点",
    "Set and Forget": "挂上不管", "Manual": "手工管理", "Partial TP": "分批止盈",
    "Move SL to BE": "SL 移保本", "Trailing Stop": "移动止损",
    "Fully Compliant": "完全符合规则", "Minor Violation": "轻微违规",
    "Major Violation": "严重违规",
    "Should I Take This Trade?": "该不该做这笔",
    "Good Win": "好盈利", "Good Loss": "好亏损", "Bad Win": "坏盈利", "Bad Loss": "坏亏损",
    "Borderline": "边缘可做",
}


# ---------------------------------------------------------------- 自动识别规则（只认字面）
# 每条 (正则, 取值, 必须出现的上下文关键词列表)。命中即取值，evidence 取该句原文。
EXTRACT = {
    "htfBias": [
        (r"(?:HTF|1D|4H|1H)?\s*(?:Bias|方向|偏)\s*[:：]?\s*(Bullish|bearish|看涨|偏多|多头)",
         "Bullish", ["Bias", "偏", "方向", "结构"]),
        (r"(?:HTF|1D|4H|1H)?\s*(?:Bias|方向|偏)\s*[:：]?\s*(Bearish|看跌|偏空|空头)",
         "Bearish", ["Bias", "偏", "方向", "结构"]),
        (r"(?:HTF|1D|4H|1H)?\s*(?:Bias|方向)\s*[:：]?\s*(Neutral|中性)", "Neutral",
         ["Bias", "方向"]),
        (r"主要下跌结构|下跌结构|转弱|bearish\s*structure", "Bearish", ["结构", "背景", "Context"]),
        (r"上涨结构|多头结构|bullish\s*structure", "Bullish", ["结构", "背景", "Context"]),
    ],
    "marketCondition": [
        (r"震荡(?:区间|行情|市)|区间震荡|\bRange\b", "Range", ["背景", "Context", "环境", "结构"]),
        (r"趋势(?:行情|市)|单边行情|\bTrend(?:ing)?\b", "Trending", ["背景", "Context", "环境"]),
        (r"扩张|Expansion", "Expansion", ["背景", "Context", "环境"]),
        (r"收缩|Compression|横盘收窄", "Compression", ["背景", "Context", "环境"]),
        (r"反转(?:行情|市)?|Reversal", "Reversal", ["背景", "Context", "环境"]),
    ],
    "liquidityType": [
        (r"\bSSL\b|下方流动性|卖方流动性|sell[- ]?side", "SSL", []),
        (r"\bBSL\b|上方流动性|买方流动性|buy[- ]?side", "BSL", []),
        (r"内部流动性|Internal Liquidity", "Internal Liquidity", []),
        (r"外部流动性|External Liquidity", "External Liquidity", []),
        (r"等高|Equal High|\bEQH\b", "Equal High", []),
        (r"等低|Equal Low|\bEQL\b", "Equal Low", []),
        (r"前高|Previous High|\bPDH\b|昨日高", "Previous High", []),
        (r"前低|Previous Low|\bPDL\b|昨日低", "Previous Low", []),
        (r"Swing High", "Swing High", []),
        (r"Swing Low", "Swing Low", []),
    ],
    "liquiditySweep": [
        (r"SSL\s*被\s*Sweep|SSL\s*被扫|流动性被扫|\bSweep(?:ed)?\b|扫了[^。；]{0,6}流动性|"
         r"扫单|假突破后收回|liquidity\s*hunt", "Yes", ["流动性", "Liquidity", "Sweep", "扫"]),
        (r"部分扫|Partial(?:ly)?\s*Sweep", "Partial", ["Sweep", "扫"]),
        (r"没有\s*Sweep|未出现\s*Sweep|无\s*Sweep|没有扫|未扫", "No", ["Sweep", "扫"]),
    ],
    "sweepQuality": [
        (r"(?:Sweep|扫)[^。；]{0,8}(?:很强|强势|干净|彻底|爽快)|\bStrong\s*Sweep\b", "Strong",
         ["Sweep", "扫"]),
        (r"(?:Sweep|扫)[^。；]{0,8}(?:偏弱|很弱|弱|\bWeak\b)", "Weak", ["Sweep", "扫"]),
        (r"(?:Sweep|扫)[^。；]{0,8}正常|Normal\s*Sweep", "Normal", ["Sweep", "扫"]),
    ],
    "htfPOIType": [
        (r"(?:\b(?:1D|4H|1H)\b|HTF)[^。；\n]{0,12}\bOB\b|OB[^。；\n]{0,8}\b(?:1D|4H|1H)\b",
         "OB", []),
        (r"(?:\b(?:1D|4H|1H)\b|HTF)[^。；\n]{0,12}\bIMB\b", "IMB", []),
        (r"(?:\b(?:1D|4H|1H)\b|HTF)[^。；\n]{0,12}\bFVG\b", "FVG", []),
        (r"(?:\b(?:1D|4H|1H)\b|HTF)[^。；\n]{0,12}\bBreaker\b", "Breaker", []),
        (r"(?:\b(?:1D|4H|1H)\b|HTF)[^。；\n]{0,12}\bBB\b", "OB", []),
        (r"折价|\bDiscount\b", "Discount", []),
        (r"溢价|\bPremium\b", "Premium", []),
        (r"\bOTE\b", "OTE", []),
    ],
    "ltfPOIType": [
        (r"\b(?:15m|5m|15 ?min|5 ?min|15分钟|5分钟)\b[^。；\n]{0,12}\bOB\b", "OB", []),
        (r"\b(?:15m|5m|15 ?min|5 ?min|15分钟|5分钟)\b[^。；\n]{0,12}\bFVG\b", "FVG", []),
        (r"\b(?:15m|5m|15 ?min|5 ?min|15分钟|5分钟)\b[^。；\n]{0,12}\bIMB\b", "IMB", []),
        (r"\b(?:15m|5m|15 ?min|5 ?min|15分钟|5分钟)\b[^。；\n]{0,12}\bBreaker\b", "Breaker", []),
    ],
    "reaction": [
        (r"反应(?:很|相当)?(?:强|好|明显)|Strong\s*Reaction|强烈拒绝", "Strong", ["反应", "Reaction"]),
        (r"反应(?:偏)?(?:弱|一般|不强)|Weak\s*Reaction|无明显反应|没有反应|毫无反应", "Weak",
         ["反应", "Reaction"]),
        (r"No\s*Reaction", "No Reaction", ["反应", "Reaction"]),
    ],
    "reactionType": [
        (r"\bRejection\b|拒绝|插针回落|长上影|长下影", "Rejection", ["反应", "Reaction"]),
        (r"动能转换|Momentum Shift|动能(?:明显)?转变", "Momentum Shift", ["反应", "Reaction"]),
        (r"K线反转|Candle Reversal|吞没", "Candle Reversal", ["反应", "Reaction"]),
        (r"立刻位移|Immediate Displacement", "Immediate Displacement", ["反应", "Reaction"]),
        (r"盘整|Consolidation|横盘", "Consolidation", ["反应", "Reaction"]),
    ],
    "displacementQuality": [
        (r"强势\s*(?:bullish|bearish)?\s*[Dd]isplacement|Strong\s*[Dd]isplacement|超级强位移",
         "Strong", ["位移", "Displacement"]),
        (r"位移(?:偏弱|较弱|弱)|\bWeak\s*[Dd]isplacement|displacement\s*偏弱", "Weak",
         ["位移", "Displacement"]),
        (r"Medium\s*[Dd]isplacement|位移中等|一般位移", "Medium", ["位移", "Displacement"]),
    ],
    "structureShiftType": [
        (r"\bMSS\b|市场结构转换|Structure Shift", "MSS", ["结构", "Structure"]),
        (r"\bMSB\b|市场结构突破", "MSB", ["结构", "Structure"]),
        (r"\bBOS\b|结构突破|Break of Structure", "BOS", ["结构", "Structure"]),
        (r"\bCHOCH\b|性质转变", "CHOCH", ["结构", "Structure"]),
    ],
    "brokenStructure": [
        (r"[Ii]nternal\s*(?:LH|HL)|内部\s*(?:LH|HL)|内部结构(?:高点|低点)?(?:被)?(?:突破|破坏)",
         "Internal LH", ["结构", "Structure"]),
        (r"[Kk]ey\s*(?:LH|HL)|关键结构(?:被)?(?:突破|破坏)|突破关键结构|关键\s*(?:LH|HL)",
         "Key LH", ["结构", "Structure"]),
        (r"Protected\s*High|保护高点", "Protected High", ["保护"]),
        (r"Protected\s*Low|保护低点", "Protected Low", ["保护"]),
        (r"外部结构|External Structure", "External Structure", ["结构"]),
    ],
    "protectedStructure": [
        (r"Protected\s*Low|保护低点", "Protected Low", ["保护"]),
        (r"Protected\s*High|保护高点", "Protected High", ["保护"]),
        (r"没有\s*Protected\s*(?:High|Low)|Protected\s*Structure\s*[:：]\s*None", "None", ["保护"]),
    ],
    "entryMode": [
        (r"LTF\s*[Cc]onfirmation|低周期确认|等待\s*(?:15m|5m)[^。；]{0,10}确认", "LTF Confirmation", []),
        (r"HTF\s*Limit|提前挂单|\bLimit\b|限价单", "Limit", []),
        (r"市价(?:进入|进场|入场)|Market\s*Entry|直接市价", "Market", []),
    ],
    "limitStyle": [
        (r"50%\s*FVG|FVG\s*50%", "50% FVG Limit", ["挂单", "Limit"]),
        (r"FVG\s*Limit|挂[^。；]{0,6}FVG", "FVG Limit", ["挂单", "Limit"]),
        (r"OB\s*Limit|挂[^。；]{0,6}OB", "OB Limit", ["挂单", "Limit"]),
        (r"HTF\s*POI\s*Limit|HTF\s*Limit", "HTF POI Limit", ["挂单", "Limit"]),
    ],
    "entryTriggerType": [
        (r"POI\s*Touch|触碰\s*POI|到达\s*POI", "POI Touch", []),
        (r"Sweep", "Sweep", ["Sweep", "扫"]),
        (r"\bMSS\b", "MSS", ["结构"]),
        (r"\bMSB\b", "MSB", ["结构"]),
        (r"\bBOS\b", "BOS", ["结构"]),
        (r"Displacement|位移", "Displacement", ["位移"]),
        (r"FVG\s*(?:回测|Retest)", "FVG Retest", []),
        (r"OB\s*(?:回测|Retest)", "OB Retest", []),
        (r"Breaker\s*(?:回测|Retest)", "Breaker Retest", []),
        (r"首次回撤|First\s*Retracement|第一次回撤", "First Retracement", []),
        (r"Rejection|拒绝", "Rejection", ["反应"]),
    ],
    "invalidationLogic": [
        (r"保护低点|Protected\s*Low", "Protected Low", ["Invalidation", "止损", "失效"]),
        (r"保护高点|Protected\s*High", "Protected High", ["Invalidation", "止损", "失效"]),
        (r"OB\s*失效|OB\s*Invalidated", "OB Invalidated", ["失效"]),
        (r"结构失效|Structure\s*Invalidated|结构被破坏", "Structure Invalidated", ["失效"]),
        (r"Bias\s*失效|HTF\s*Bias\s*Invalidated|方向失效", "HTF Bias Invalidated", ["失效"]),
        (r"扫低点|Sweep\s*Low", "Sweep Low", ["失效"]),
        (r"扫高点|Sweep\s*High", "Sweep High", ["失效"]),
    ],
    "managementStyle": [
        (r"分批止盈|部分止盈|Partial\s*TP|TP1[^。；]{0,10}TP2", "Partial TP", ["管理", "Management"]),
        (r"移动\s*SL\s*(?:到|至)\s*(?:保本|BE)|SL\s*(?:移|挪)[^。；]{0,4}保本|Move\s*SL\s*to\s*BE",
         "Move SL to BE", ["管理", "Management"]),
        (r"移动止损|Trailing\s*Stop", "Trailing Stop", ["管理", "Management"]),
        (r"挂上不管|Set\s*and\s*Forget|不干预", "Set and Forget", ["管理", "Management"]),
        (r"手工管理|Manual", "Manual", ["管理", "Management"]),
    ],
    "targetLevel": [
        (r"内部流动性|Internal Liquidity|LTF\s*流动性", "LTF Internal Liquidity", ["目标", "Target"]),
        (r"外部流动性|External Liquidity", "External Liquidity", ["目标", "Target"]),
        (r"4H\s*Swing|1D\s*Swing|HTF\s*Swing", "HTF Swing High/Low", ["目标", "Target"]),
        (r"1H\s*流动性|HTF\s*流动性|上方流动性", "HTF Liquidity", ["目标", "Target"]),
    ],
    "ruleCompliance": [
        (r"完全符合规则|Fully\s*Compliant|完全按规则", "Fully Compliant", []),
        (r"轻微违规|Minor\s*Violation", "Minor Violation", []),
        (r"严重违规|Major\s*Violation", "Major Violation", []),
    ],
    "shouldTake": [
        (r"Should\s*I\s*Take[^。；]*[:：]\s*(?:Yes|是|该做)", "Yes", []),
        (r"Should\s*I\s*Take[^。；]*[:：]\s*(?:No|不该做|否)", "No", []),
        (r"Borderline|边缘可做|可做可不做", "Borderline", []),
    ],
    "tradeQuality": [
        (r"Good\s*Win|好盈利", "Good Win", []),
        (r"Good\s*Loss|好亏损", "Good Loss", []),
        (r"Bad\s*Win|坏盈利", "Bad Win", []),
        (r"Bad\s*Loss|坏亏损", "Bad Loss", []),
    ],
}


# ---------------------------------------------------------------- 一致性校验
def validate_override(obj, path=""):
    """校验手动结构化层。任何越界值都是错误 —— 这是「AI 不脑补」的硬闸门。"""
    errs = []
    if not isinstance(obj, dict):
        return [f"{path or 'root'}: 必须是对象"]

    if "errors" in obj and obj["errors"]:
        errs.append(f"{path}: errors 必须是空列表")
    if "aiNotes" in obj and obj["aiNotes"]:
        errs.append(f"{path}: aiNotes 必须为空（AI 不得写入原始交易数据，需求 §37）")

    for key, raw in obj.items():
        if key in ("errors", "aiNotes", "note", "updatedAt"):
            continue
        spec = FIELD_BY_KEY.get(key)
        if spec is None and key not in ("imageTags", "mistakes", "protectedPrice", "sweepLevel",
                                        "htfStructure", "displacementTF", "confidence"):
            errs.append(f"{path}: 未知字段 {key}")
            continue
        values = raw.get("value") if isinstance(raw, dict) else raw
        if values is None:
            continue
        values = values if isinstance(values, list) else [values]
        allowed = None
        if spec:
            allowed = spec["options"]
        elif key == "mistakes":
            allowed = MISTAKE_TAGS
        for v in values:
            if allowed and str(v) not in allowed:
                errs.append(f"{path}.{key}: 非法取值 {v!r}，允许：{allowed}")
        if spec and not spec["multi"] and len(values) > 1:
            errs.append(f"{path}.{key}: 该字段只能有一个取值，收到 {len(values)} 个")
    return errs


def vocab(buckets):
    """给前端用的字段字典（含 manual/自动识别来源统计）。"""
    return {
        "version": SCHEMA_VERSION,
        "htf": HTF_TF, "ltf": LTF_TF, "allTF": ALL_TF,
        "fields": FIELDS,
        "zh": ZH,
        "mistakeGroups": MISTAKE_GROUPS,
        "buckets": buckets,
    }


# ---------------------------------------------------------------- 规则清单 (§33 / §34)
# Must Have / Confirmation / Avoid —— 每一项都绑定一个「可判定的字段」，避免主观打分。
RULE_BUCKETS = {
    "Must Have": [
        {"id": "htfBias", "text": "明确 HTF Bias（方向判断）", "field": "htfBias", "mode": "set"},
        {"id": "htfPOI", "text": "明确 HTF POI 与周期", "field": "htfPOIType", "mode": "set"},
        {"id": "invalidation", "text": "明确 Invalidation（失效依据）", "field": "invalidationLogic",
         "mode": "set"},
        {"id": "rr", "text": "RR 符合要求", "field": "plannedRR", "mode": "rr_gate"},
    ],
    "Confirmation": [
        {"id": "sweep", "text": "Liquidity Sweep", "field": "liquiditySweep",
         "mode": "in:Yes,Partial"},
        {"id": "displacement", "text": "Displacement", "field": "displacementQuality", "mode": "set"},
        {"id": "structure", "text": "Key Structure Shift", "field": "brokenStructure",
         "mode": "not_in:Internal LH,Internal HL"},
        {"id": "retrace", "text": "First Retracement / Entry Trigger",
         "field": "entryTriggerType", "mode": "set"},
    ],
    "Avoid": [
        {"id": "fomo", "text": "FOMO", "field": "mistakes", "mode": "not_in:FOMO"},
        {"id": "midrange", "text": "Mid Range Entry", "field": "midRange", "mode": "none"},
        {"id": "weakmsb", "text": "Weak MSB", "field": "mistakes", "mode": "not_in:Weak MSB,Internal MSB Only"},
        {"id": "poorrr", "text": "Poor RR", "field": "mistakes", "mode": "not_in:Poor RR"},
        {"id": "chase", "text": "Chase Price", "field": "mistakes", "mode": "not_in:Chase Price,Late Entry"},
    ],
}
