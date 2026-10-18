import copy
import io
import json
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "parser"))
sys.path.insert(0, str(ROOT / "tools"))
import review_logic as review
import stats_v2 as stats
import struct_extract
import parse_gdoc
import tagedit
import selfcheck


def field(value, source="manual", confirmed=True):
    return {"value": value, "source": source, "confirmed": confirmed}


def trade(tid="t1", result="win", r=1):
    return {"id": tid, "symbolLabel": "TEST", "direction": "long", "resultStatus": result,
            "entry": 100, "stopLoss": 95, "exit": 105, "actualR": r, "rIncluded": True,
            "fields": {k: field(v) for k, v in {
                "reviewModel": "HTF POI", "confirmationMode": "POI Touch",
                "requiredConfirmations": ["None"], "planTiming": "Before Entry",
                "plannedEntry": 100, "plannedSL": 95, "plannedRR": 2, "minRRThreshold": 1,
                "htfBias": "Bullish", "htfPOIType": ["OB"], "htfPOITF": ["4H"],
                "invalidationLogic": ["Protected Low"], "executionAdherence": "Followed Plan",
            }.items()}}


def assessed(t):
    t["complianceV2"] = review.derive_checklist(t)
    t["quality"] = review.derive_quality(t)
    return t


class RuleTests(unittest.TestCase):
    def test_htf_missing_or_unconfirmed_requirements_are_unknown(self):
        for value in (None, field(["None"], "doc:keyword", False)):
            with self.subTest(value=value):
                t = trade()
                t["fields"]["requiredConfirmations"] = value
                c = review.derive_checklist(t)
                self.assertIsNone(c["compliance"])
                self.assertEqual(c["notApplicable"], 0)
                self.assertGreater(c["unknown"], 0)

    def test_deviation_grade_uses_specific_evidence(self):
        t = trade()
        t["fields"]["executionAdherence"] = field("Deviation")
        self.assertIsNone(review.derive_checklist(t)["compliance"])
        t["fields"].update(requiredConfirmations=field(["Sweep"]), liquiditySweep=field("No"))
        self.assertEqual(review.derive_checklist(t)["compliance"], "Minor Violation")
        t["fields"]["plannedRR"] = field(.5)
        self.assertEqual(review.derive_checklist(t)["compliance"], "Major Violation")
        t["fields"]["executionAdherence"] = field("Followed Plan")
        self.assertEqual(review.derive_checklist(t)["compliance"], "Major Violation")

    def test_htf_does_not_require_ltf_sweep(self):
        t = trade()
        t["fields"]["liquiditySweep"] = field("No")
        c = review.derive_checklist(t)
        self.assertEqual(c["compliance"], "Fully Compliant")
        self.assertEqual(c["notApplicable"], 4)
        t["complianceV2"] = c
        self.assertNotIn("No Sweep", [x["tag"] for x in stats.suggest_mistakes(t)["suggestions"]])

    def test_ltf_checks_only_planned_confirmations(self):
        t = trade()
        t["fields"].update({k: field(v) for k, v in {
            "reviewModel": "LTF Confirmation", "confirmationMode": "LTF Confirmation",
            "requiredConfirmations": ["Displacement", "Key Structure", "Entry Trigger"],
            "displacement": "Yes", "brokenStructure": ["Key LH"], "entryTriggerType": ["BOS"],
            "orderType": "Limit", "liquiditySweep": "No",
        }.items()})
        c = review.derive_checklist(t)
        self.assertEqual(c["compliance"], "Fully Compliant")
        self.assertEqual(c["notApplicable"], 1)
        self.assertEqual(t["fields"]["orderType"]["value"], "Limit")

    def test_required_sweep_missing_is_unknown_not_violation(self):
        t = trade()
        t["fields"]["requiredConfirmations"] = field(["Sweep"])
        c = review.derive_checklist(t)
        self.assertIsNone(c["compliance"])
        self.assertEqual(c["no"], 0)
        self.assertLess(c["coverage"], 1)

    def test_required_sweep_explicit_no_is_violation(self):
        t = trade()
        t["fields"].update(requiredConfirmations=field(["Sweep"]), liquiditySweep=field("No"))
        self.assertEqual(review.derive_checklist(t)["compliance"], "Minor Violation")

    def test_unknown_model_does_not_apply_confirmation_rules(self):
        t = trade()
        del t["fields"]["reviewModel"]
        t["fields"]["liquiditySweep"] = field("No")
        c = review.derive_checklist(t)
        self.assertIsNone(c["compliance"])
        self.assertEqual(c["no"], 0)

    def test_ltf_without_defined_requirements_is_unknown(self):
        t = trade()
        t["fields"].update(reviewModel=field("LTF Confirmation"), confirmationMode=field("LTF Confirmation"))
        del t["fields"]["requiredConfirmations"]
        self.assertIsNone(review.derive_checklist(t)["compliance"])

    def test_unconfirmed_keyword_cannot_pass_a_rule(self):
        t = trade()
        t["fields"]["htfBias"] = field("Bullish", "doc:keyword", False)
        self.assertIsNone(review.derive_checklist(t)["compliance"])

    def test_rr_threshold_is_not_invented(self):
        t = trade()
        del t["fields"]["minRRThreshold"]
        self.assertIsNone(review.derive_checklist(t)["compliance"])

    def test_countertrend_is_not_automatically_a_violation(self):
        t = trade()
        t["fields"]["htfBias"] = field("Bearish")
        self.assertEqual(review.derive_checklist(t)["no"], 0)

    def test_unknown_status_cannot_be_fully_compliant(self):
        groups = {"Must Have": [{"text": "RR", "status": "—"}], "Confirmation": [], "Avoid": []}
        self.assertIsNone(review.derive_compliance(groups)["value"])

    def test_retrospective_plan_cannot_prove_full_compliance(self):
        t = trade()
        t["entryTime"] = "2026-09-13T10:00:00+08:00"
        t["planRecordedAt"] = "2026-09-30T10:00:00+08:00"
        self.assertIsNone(review.derive_checklist(t)["compliance"])
        self.assertEqual(review.derive_planned_actual(t)["timing"], "Retrospective")

    def test_date_only_entry_rejects_later_plan(self):
        t = trade()
        t.update(entryDate="2026-09-13", entryTime=None,
                 planRecordedAt="2026-09-30T23:00:00+08:00")
        self.assertEqual(review.plan_timing(t), "Retrospective")
        self.assertIsNone(review.derive_checklist(t)["compliance"])

    def test_date_only_entry_same_day_is_unknown(self):
        t = trade()
        t.update(entryDate="2026-09-13", planRecordedAt="2026-09-13T01:00:00+08:00")
        self.assertIsNone(review.plan_timing(t))
        self.assertIsNone(review.derive_checklist(t)["compliance"])

    def test_date_only_entry_accepts_earlier_plan(self):
        t = trade()
        t.update(entryDate="2026-09-13", planRecordedAt="2026-09-12T23:59:00+08:00")
        self.assertEqual(review.plan_timing(t), "Before Entry")
        self.assertEqual(review.derive_checklist(t)["compliance"], "Fully Compliant")

    def test_date_only_entry_compares_beijing_calendar_date(self):
        t = trade()
        t.update(entryDate="2026-09-13", planRecordedAt="2026-09-12T18:00:00+00:00")
        self.assertIsNone(review.plan_timing(t))

    def test_undated_closed_trade_cannot_prove_before_entry(self):
        t = trade()
        t.update(exitDate="2026-09-13", planRecordedAt="2026-09-12T23:00:00+08:00")
        self.assertIsNone(review.plan_timing(t))
        t["planRecordedAt"] = "2026-09-30T23:00:00+08:00"
        self.assertEqual(review.plan_timing(t), "Retrospective")

    def test_uncomparable_or_invalid_times_are_unknown(self):
        t = trade()
        t.update(entryTime="2026-09-13T10:00:00", planRecordedAt="2026-09-12T10:00:00+08:00")
        self.assertIsNone(review.plan_timing(t))
        t.update(entryTime=None, entryDate="invalid")
        self.assertIsNone(review.plan_timing(t))

    def test_checklist_counts_partition_items(self):
        c = review.derive_checklist(trade())
        self.assertEqual(c["yes"] + c["no"] + c["unknown"] + c["notApplicable"], c["total"])


class QualityTests(unittest.TestCase):
    def samples(self):
        good = assessed(trade("good"))
        bad = trade("bad", "loss", -1)
        bad["fields"]["executionAdherence"] = field("Deviation")
        bad["fields"]["plannedRR"] = field(.5)
        bad = assessed(bad)
        unknown = trade("unknown")
        unknown["fields"] = {}
        unknown["analysis"] = {"classification": {"value": "未定级"}}
        return [good, bad, assessed(unknown)]

    def test_rates_share_judged_denominator(self):
        ts = self.samples()
        for result in [stats.dashboard(ts), stats.bucket_stats(ts, "all", "all"), stats.quality_summary(ts)]:
            self.assertEqual(result["goodTradeRate"], .5)
        self.assertEqual(stats.dashboard(ts)["qualityJudged"], 2)
        self.assertEqual(stats.dashboard(ts)["qualityUnknown"], 1)
        self.assertEqual(stats.quality_summary(ts)["coverage"], .667)

    def test_document_quality_preserves_its_source(self):
        t = trade()
        t["fields"] = {"tradeQuality": field("Good Win", "doc:label")}
        self.assertEqual(review.derive_quality(t)["source"], "doc:label")

    def test_conflicting_quality_preserves_evidence_and_leaves_statistics(self):
        t = trade(result="loss", r=-1)
        t["fields"].update(plannedRR=field(.5), tradeQuality=field("Good Loss", "doc:label"))
        t["analysis"] = {"classification": {"value": "Good Loss"}}
        assessed(t)
        self.assertIsNone(t["quality"]["value"])
        self.assertEqual(t["quality"]["reportedQuality"], "Good Loss")
        self.assertEqual(t["quality"]["checklistCompliance"], "Major Violation")
        self.assertIn("判定冲突", t["quality"]["basis"])
        self.assertEqual(t["fields"]["tradeQuality"]["value"], "Good Loss")
        for result in (stats.dashboard([t]), stats.bucket_stats([t], "all", "all"), stats.quality_summary([t])):
            self.assertIsNone(result["goodTradeRate"])
        self.assertEqual(stats.dashboard([t])["qualityJudged"], 0)
        dims = stats.dimension_tables([t])
        self.assertEqual(dims["tradeQuality"]["rows"][0]["key"], "(未记录)")
        self.assertEqual(dims["ruleCompliance"]["rows"][0]["key"], "Major Violation")
        sve = stats.strategy_vs_execution([t])
        self.assertEqual(sve["goodLoss"]["count"], 0)
        self.assertEqual(sve["badLoss"]["count"], 0)
        src = {"weeks": [{"label": "周", "start": "2026-09-13", "end": "2026-09-19", "tradeIds": [t["id"]]}]}
        self.assertIsNone(stats.weekly_v2(src, [t], {})[0]["goodTradeRate"])

    def test_compliance_annotation_conflict_does_not_fall_back_to_analysis(self):
        t = trade()
        t["fields"]["ruleCompliance"] = field("Major Violation", "doc:label")
        t["analysis"] = {"classification": {"value": "Good Win"}}
        assessed(t)
        self.assertIsNone(t["quality"]["value"])
        self.assertEqual(t["quality"]["source"], "conflict")

    def test_quality_annotation_must_match_actual_result(self):
        t = trade(result="loss", r=-1)
        t["fields"] = {"tradeQuality": field("Good Win", "doc:label")}
        assessed(t)
        self.assertIsNone(t["quality"]["value"])
        self.assertEqual(t["quality"]["reportedQuality"], "Good Win")

    def test_be_is_not_a_bad_loss(self):
        t = assessed(trade(result="be", r=0))
        self.assertIsNone(t["quality"]["value"])
        self.assertIsNone(stats.quality_summary([t])["goodTradeRate"])

    def test_empty_quality_sample_is_null(self):
        t = trade()
        t["fields"] = {}
        self.assertIsNone(stats.dashboard([assessed(t)])["goodTradeRate"])


class PlanTests(unittest.TestCase):
    def test_actual_price_does_not_fill_plan(self):
        t = trade()
        t["fields"] = {}
        p = review.derive_planned_actual(t)
        self.assertIsNone(p["planned"]["entry"])
        self.assertIsNone(p["planned"]["sl"])
        self.assertEqual(p["actual"]["entry"], 100)

    def test_plan_and_actual_difference(self):
        t = trade()
        t["entry"] = 103
        self.assertEqual(review.derive_planned_actual(t)["deviations"][0]["difference"], 3)

    def test_pending_has_no_actual_entry(self):
        self.assertIsNone(review.derive_planned_actual(trade(result=None))["actual"]["entry"])

    def test_manual_clear_rr_does_not_restore_source_value(self):
        t = trade()
        t["plannedRR"] = 2
        stats.merge_fields(t, {"fields": {"plannedRR": None}})
        self.assertIsNone(review.derive_planned_actual(t)["planned"]["rr"])

    def test_explicit_plan_labels_are_extracted(self):
        compact = parse_gdoc.compact_sections("【① Basic Info】Review Model：LTF Confirmation；Required Confirmations：Displacement + Key Structure；Order Type：Limit；Planned Entry：82,953.7；Plan Timing：Before Entry")
        extracted = struct_extract.extract_structured({"structRaw": compact["struct"]})
        self.assertEqual(extracted["fields"]["plannedEntry"]["value"], 82953.7)
        self.assertEqual(extracted["fields"]["orderType"]["value"], "Limit")
        self.assertTrue(extracted["fields"]["reviewModel"]["confirmed"])

    def test_template_choices_are_not_a_confirmed_model(self):
        values, _, _ = struct_extract.parse_struct_value("reviewModel", "HTF POI 或 LTF Confirmation")
        self.assertEqual(values, [])
        self.assertEqual(struct_extract.parse_struct_value("causeChain", "未记录")[0], [])


class WeeklyAndMistakeTests(unittest.TestCase):
    def test_weekly_follows_previous_goal_and_counts_only_losses(self):
        ts = [assessed(trade("first")), assessed(trade("second", "loss", -1)),
              assessed(trade("pending", None)), assessed(trade("be", "be", 0))]
        src = {"weeks": [{"label": "第一周", "start": "2026-09-13", "end": "2026-09-19", "tradeIds": ["first"]},
                         {"label": "第二周", "start": "2026-09-20", "end": "2026-09-26", "tradeIds": ["second", "pending", "be"]}]}
        manual = {"_weeks": {"第一周": {"focusTrigger": "确认型 Setup", "focusAction": "入场前保存确认截图", "focusMetric": "截图完成数/适用次数"},
                             "第二周": {"focusEligible": 3, "focusCompleted": 2, "focusResult": "漏了一次"}}}
        weeks = stats.weekly_v2(src, ts, manual)
        self.assertEqual(weeks[1]["losses"], 1)
        self.assertEqual(weeks[1]["be"], 1)
        self.assertEqual(weeks[1]["behaviorReview"]["goal"]["action"], "入场前保存确认截图")
        self.assertEqual(weeks[1]["behaviorReview"]["completionRate"], .667)
        self.assertIsNone(weeks[0]["bestSetup"])

    def test_weekly_quality_denominator(self):
        ts = QualityTests().samples()
        src = {"weeks": [{"label": "周", "start": "2026-09-13", "end": "2026-09-19", "tradeIds": [t["id"] for t in ts]}]}
        self.assertEqual(stats.weekly_v2(src, ts, {})[0]["goodTradeRate"], .5)

    def test_multi_tag_loss_is_deduplicated(self):
        t = trade(result="loss", r=-1)
        t["fields"]["mistakes"] = field(["Early Entry", "FOMO", "FOMO"])
        m = stats.mistake_analysis([t])
        self.assertEqual(len(m["rows"]), 2)
        self.assertEqual(m["totalLostR"], -1)
        self.assertTrue(all(r["count"] == 1 and r["lostR"] == -1 for r in m["rows"]))

    def test_suggestions_do_not_enter_mistake_stats(self):
        t = trade(result="loss", r=-1)
        t["fields"]["mistakes"] = field(["No Sweep"], "derived:checklist", False)
        self.assertEqual(stats.mistake_analysis([t])["rows"], [])


class StatsAnswerTests(unittest.TestCase):
    def poi_trades(self, tf, count, r, result="win"):
        ts = [assessed(trade(f"{tf}-{i}", result, r)) for i in range(count)]
        for t in ts:
            t["fields"]["htfPOITF"] = field([tf])
        return ts

    def poi_answer(self, ts):
        answers = stats.answers(ts, stats.dimension_tables(ts), {}, {}, {}, stats.dashboard(ts))
        return next(a for a in answers if a["q"] == "1D / 4H / 1H 哪种 HTF POI 对我最有效？")

    def test_poi_comparison_requires_two_qualified_groups(self):
        for small_r in (.5, 5):
            with self.subTest(small_r=small_r):
                a = self.poi_answer(self.poi_trades("1D", 10, 1) + self.poi_trades("4H", 1, small_r))
                self.assertIn("暂不比较", a["a"])
                self.assertNotIn("均值较高", a["a"])
                self.assertTrue(a["insufficient"])

    def test_poi_comparison_excludes_small_group_with_higher_mean(self):
        a = self.poi_answer(self.poi_trades("1D", 10, 1) + self.poi_trades("4H", 10, .5)
                            + self.poi_trades("1H", 1, 5))
        self.assertIn("1D 样本内平均 R 较高", a["a"])
        comparison = a["a"].split("；仅比较样本达标的周期：")[1]
        self.assertIn("vs 4H", comparison)
        self.assertNotIn("1H", comparison)
        self.assertFalse(a["insufficient"])

    def test_poi_comparison_counts_only_closed_trades_with_r(self):
        for r, result in ((None, "win"), (1, "open"), (1, None)):
            with self.subTest(r=r, result=result):
                ts = self.poi_trades("1D", 10, 1) + self.poi_trades("4H", 9, .5)
                ts += self.poi_trades("4H", 1, r, result)
                a = self.poi_answer(ts)
                self.assertIn("暂不比较", a["a"])
                self.assertTrue(a["insufficient"])

    def test_poi_comparison_treats_zero_mean_as_recorded(self):
        a = self.poi_answer(self.poi_trades("1D", 10, 0, "be") + self.poi_trades("4H", 10, -1, "loss"))
        self.assertIn("1D 样本内平均 R 较高", a["a"])
        self.assertFalse(a["insufficient"])


class DocsIntegrationTests(unittest.TestCase):
    def test_latest_doc_results_do_not_read_plans_or_review_words_as_returns(self):
        cases = [
            ("Win；Actual R +3.00R。结构低点止损。", "win", 3.0),
            ("Loss，Actual R ≈ -1.01R。因逆势缩小 1R。", "loss", -1.01),
            ("Result：Loss。Actual R≈-1.15R。原计划目标2R。", "loss", -1.15),
            ("Win，缺少事前模型与 1R，也不计算 Actual R。", "win", None),
            ("Pending / 未成交，没有 Actual R。", None, None),
            ("Win；Actual R = 0.821 ÷ 0.4 ≈ +2.05R。", "win", 2.05),
        ]
        for result, status, actual_r in cases:
            with self.subTest(result=result):
                blocks = [
                    {"kind": "h1", "text": "第1周｜2026年10月4日–10月10日"},
                    {"kind": "h2", "text": "1｜JP225/USDT Long｜2026年10月9日｜已结束"},
                    {"kind": "para", "text": "【① Basic Info】Entry=68,442.25；初始 SL = 67,388；Exit：67,833；1R=0.42 U。"},
                    {"kind": "para", "text": "【⑩ Result & Review】" + result},
                ]
                t = parse_gdoc.parse(blocks, None)["trades"][0]
                self.assertEqual(t["symbol"], "JP225USDT")
                self.assertEqual(t["resultStatus"], status)
                self.assertEqual(t["actualR"], actual_r)
                self.assertEqual(t["entry"], 68442.25)
                self.assertEqual(t["stopLoss"], 67388)
                self.assertEqual(t["exit"], 67833)
                self.assertEqual(t["riskAmount"], .42)

    def test_target_r_and_partial_close_labels_are_not_target_prices(self):
        for target in ("原计划目标为2R。", "分批退出TP1 89.475，TP2 92.56。"):
            blocks = [
                {"kind": "h1", "text": "第1周｜2026年10月4日–10月10日"},
                {"kind": "h2", "text": "1｜HYPE/USDT Long｜2026年10月9日｜Win"},
                {"kind": "para", "text": "【⑧ Target & Risk Check】" + target},
            ]
            t = parse_gdoc.parse(blocks, None)["trades"][0]
            self.assertIsNone(t["targets"][0]["priceLow"])

    def test_candidate_and_retracted_quality_are_not_confirmed(self):
        for body in ("Trade Quality目前仍为待判定、Good Loss候选，而非已确认Fully Compliant。",
                     "撤销此前Bad Loss的结论。", "暂不对 Good Win / Bad Win 做最终定级。"):
            with self.subTest(body=body):
                extracted = struct_extract.extract_structured({"structRaw": {"tradeQuality": [body]}})
                self.assertNotIn("tradeQuality", extracted["fields"])
                self.assertEqual(extracted["unparsed"][0]["raw"], body)

    def test_rule_lines_preserve_all_rules_regardless_of_heading_style(self):
        for kind in ("para", "h1", "h2"):
            with self.subTest(kind=kind):
                blocks = self.doc_trade() + [{"kind": "h1", "text": "统一交易复盘逻辑｜后续所有交易沿用"}]
                blocks += [{"kind": "para", "text": f"规则{x}｜规则标题：规则内容"} for x in "一二三四"]
                blocks += [{"kind": kind, "text": "规则五｜执行质量：按交易前适用条件判定"}]
                parsed = parse_gdoc.parse(blocks, None)
                self.assertEqual(len(parsed["rules"]["items"]), 5)
                self.assertEqual(parsed["rules"]["items"][-1]["body"], "按交易前适用条件判定")
                self.assertEqual(len(parsed["trades"]), 1)

    def test_cause_chain_keeps_narrative_about_missing_records(self):
        narrative = "没有记录初始止损，价格跌破 POI 后仍继续持仓"
        blocks = self.doc_trade() + [{"kind": "para", "text": "【Cause Chain】" + narrative}]
        src = parse_gdoc.parse(blocks, None)
        with patch.object(stats, "load_manual", return_value={}):
            stats.build_result(src["trades"], src)
        self.assertEqual(src["trades"][0]["fields"]["causeChain"]["value"], narrative)
        for placeholder in ("未记录", "没有记录。", " 未记录 "):
            self.assertEqual(struct_extract.parse_struct_value("causeChain", placeholder)[0], [])

    def test_prompt_examples_do_not_become_trades_or_week_notes(self):
        prompt = (ROOT / "docs/chatgpt-recording.md").read_text().split("```text\n", 1)[1].split("```", 1)[0]
        examples = [{"kind": "para", "text": line} for line in prompt.splitlines()]
        examples += [{"kind": "h1", "text": "第99周｜2026年9月13日–9月19日"},
                     {"kind": "h2", "text": "99｜TEST/USDT Long｜2026年9月13日｜+99R"},
                     {"kind": "image", "rid": "example-only"},
                     {"kind": "para", "text": "【周复盘】下周动作：示例，不应计入"}]
        for insert_at in (0, 4, len(self.doc_trade())):
            with self.subTest(insert_at=insert_at):
                blocks = self.doc_trade()
                blocks[insert_at:insert_at] = ([{"kind": "h1", "text": parse_gdoc.ASSISTANT_PROMPT_START}]
                    + examples + [{"kind": "para", "text": parse_gdoc.ASSISTANT_PROMPT_END}])
                src = parse_gdoc.parse(blocks, None)
                self.assertEqual(len(src["trades"]), 1)
                self.assertEqual(len(src["weeks"]), 1)
                self.assertFalse(src["weeks"][0].get("weekReview"))
                self.assertEqual(src["trades"][0]["actualR"], 1)
                self.assertNotIn("示例，不应计入", str(src["trades"][0]))

    def test_unbalanced_prompt_markers_fail_explicitly(self):
        start, end = parse_gdoc.ASSISTANT_PROMPT_START, parse_gdoc.ASSISTANT_PROMPT_END
        for markers in ([start], [end], [end, start], [start, start, end]):
            with self.subTest(markers=markers), self.assertRaisesRegex(ValueError, "ChatGPT 约定"):
                parse_gdoc.parse([{"kind": "para", "text": m} for m in markers] + self.doc_trade(), None)

    def doc_trade(self, displacement="Yes / Strong / 15min"):
        blocks = [
            {"kind": "h1", "text": "第1周｜2026年9月13日–9月19日"},
            {"kind": "para", "text": "周总结：1 笔已结束交易"},
            {"kind": "h2", "text": "1｜ETH/USDT Long｜2026年9月13日｜+1.00R"},
            {"kind": "para", "text": "【交易时间】2026-09-13 10:00 → 2026-09-13 11:00"},
            {"kind": "para", "text": "【执行】实际 Entry 100；初始 SL 95；Exit 105"},
            {"kind": "para", "text": "【结果】实际 +1.00R"},
        ]
        labels = {
            "Review Model": "LTF Confirmation", "Confirmation Mode": "LTF Confirmation",
            "Required Confirmations": "Displacement", "Plan Timing": "Before Entry",
            "Planned Entry": "99", "Planned SL": "94", "Planned TP": "109",
            "Planned RR": "2", "Min RR": "1", "Order Type": "Limit",
            "Execution Adherence": "Followed Plan", "HTF Bias": "Bullish",
            "HTF POI": "OB", "HTF POI 周期": "4H", "Invalidation 依据": "Protected Low",
            "Displacement": displacement,
        }
        blocks.extend({"kind": "para", "text": f"【{key}】{value}"} for key, value in labels.items())
        return blocks

    def test_doc_plan_and_actual_reach_build_without_manual(self):
        src = parse_gdoc.parse(self.doc_trade(), None)
        with patch.object(stats, "load_manual", return_value={}):
            stats.build_result(src["trades"], src)
        t = src["trades"][0]
        self.assertEqual(t["plannedVsActual"]["planned"]["entry"], 99)
        self.assertEqual(t["plannedVsActual"]["actual"]["entry"], 100)
        self.assertEqual(t["plannedVsActual"]["deviations"][0]["difference"], 1)
        self.assertEqual(t["fields"]["orderType"]["source"], "doc:label")
        self.assertEqual(t["complianceV2"]["compliance"], "Fully Compliant")

    def test_doc_displacement_presence_quality_and_tf_are_separate(self):
        for text, expected in [("Yes", "Fully Compliant"), ("No", "Minor Violation"),
                               ("Yes / Strong / 15min", "Fully Compliant"),
                               ("15min: Strong", None), ("Yes / No", None),
                               ("未记录", None)]:
            with self.subTest(text=text):
                src = parse_gdoc.parse(self.doc_trade(text), None)
                with patch.object(stats, "load_manual", return_value={}):
                    stats.build_result(src["trades"], src)
                t = src["trades"][0]
                self.assertEqual(t["complianceV2"]["compliance"], expected)
                if text == "Yes / Strong / 15min":
                    self.assertEqual(t["fields"]["displacement"]["value"], "Yes")
                    self.assertEqual(t["fields"]["displacementQuality"]["value"], "Strong")
                    self.assertEqual(t["fields"]["displacementTF"]["value"], ["15m"])

    def test_doc_poi_labels_use_canonical_keys_and_keep_tf(self):
        extracted = struct_extract.extract_structured({"structRaw": {
            "htfPOI": ["4H OB + FVG"], "ltfPOI": ["15min FVG"],
        }})["fields"]
        self.assertCountEqual(extracted["htfPOIType"]["value"], ["OB", "FVG"])
        self.assertEqual(extracted["htfPOITF"]["value"], ["4H"])
        self.assertEqual(extracted["ltfPOIType"]["value"], ["FVG"])
        self.assertEqual(extracted["ltfPOITF"]["value"], ["15m"])
        self.assertNotIn("htfPOI", extracted)

    def doc_weeks(self, counts="3", completed="2"):
        blocks = self.doc_trade()
        blocks.append({"kind": "para", "text": "【周复盘】本周主要问题：确认记录不足；下周触发条件：确认型 Setup；下周动作：入场前保存截图；下周检查方式：截图数/适用次数"})
        blocks += [
            {"kind": "h1", "text": "第2周｜2026年9月20日–9月26日"},
            {"kind": "para", "text": "周总结：本周检查行为"},
            {"kind": "h2", "text": f"【Weekly Review】Focus Eligible：{counts}；Focus Completed：{completed}；Focus Result：执行了约定。仍需保持。"},
        ]
        return parse_gdoc.parse(blocks, None)

    def test_doc_week_goal_and_next_week_check_reach_build(self):
        src = self.doc_weeks()
        with patch.object(stats, "load_manual", return_value={}):
            v2 = stats.build_result(src["trades"], src)
        first, second = v2["weekly"]
        self.assertEqual(first["behaviorGoal"]["action"], "入场前保存截图")
        self.assertEqual(first["mainProblem"], "确认记录不足")
        self.assertEqual(first["notesSource"], "doc:label")
        self.assertEqual(second["behaviorReview"]["goal"], first["behaviorGoal"])
        self.assertEqual(second["behaviorReview"]["completionRate"], .667)
        self.assertEqual(second["behaviorReview"]["reflection"], "执行了约定。仍需保持。")
        self.assertNotIn("下周动作", str(src["trades"][0]["rawSections"]))

    def test_doc_week_zero_unknown_and_invalid_counts_are_distinct(self):
        for eligible, completed, expected in [("0", "0", 0), ("未记录", "未记录", None),
                                              ("1.5", "1", None), ("-1", "0", None),
                                              ("2", "3", None)]:
            with self.subTest(eligible=eligible, completed=completed):
                src = self.doc_weeks(eligible, completed)
                weeks = stats.weekly_v2(src, src["trades"], {})
                review = weeks[1]["behaviorReview"]
                self.assertEqual(review["eligible"], expected)
                self.assertIsNone(review["completionRate"])

    def test_manual_week_correction_overrides_only_given_keys(self):
        src = self.doc_weeks()
        manual = {"_weeks": {"第1周": {"focusAction": "更新后的动作", "mainProblem": None}}}
        weeks = stats.weekly_v2(src, src["trades"], manual)
        self.assertEqual(weeks[0]["behaviorGoal"]["trigger"], "确认型 Setup")
        self.assertEqual(weeks[0]["behaviorGoal"]["action"], "更新后的动作")
        self.assertIsNone(weeks[0]["mainProblem"])
        self.assertEqual(weeks[0]["noteSources"]["focusTrigger"], "doc:label")
        self.assertEqual(weeks[0]["noteSources"]["focusAction"], "manual/_weeks.json")
        self.assertEqual(weeks[1]["behaviorReview"]["goal"]["action"], "更新后的动作")

    def test_week_reflection_preserves_sentences_about_missing_records(self):
        fields = parse_gdoc.weekly_review_fields("【周复盘】本周主要问题：有一次截图未记录。需要补齐缺失证据。；下周动作：补齐缺失证据；上周行为适用次数：0。")
        self.assertEqual(fields["mainProblem"], "有一次截图未记录。需要补齐缺失证据。")
        self.assertEqual(fields["focusAction"], "补齐缺失证据")
        self.assertEqual(fields["focusEligible"], 0)


class EditorTests(unittest.TestCase):
    def test_note_only_post_preserves_document_plan_despite_selection_order(self):
        t = trade()
        t["fields"] = {k: field(v["value"], "doc:label") for k, v in t["fields"].items()}
        t["fields"]["requiredConfirmations"] = field(["Entry Trigger", "Sweep"], "doc:label")
        t["entryDate"] = "2026-09-13"
        handler = object.__new__(tagedit.H)
        handler.path, handler.trades = "/t/t1", [t]
        body = urllib.parse.urlencode({"f__requiredConfirmations": ["", "Sweep", "Entry Trigger"],
                                      "notes": "只补备注"}, doseq=True).encode()
        handler.headers, handler.rfile = {"Content-Length": str(len(body))}, io.BytesIO(body)
        handler.rebuild_response = lambda *a, **kw: None
        with tempfile.TemporaryDirectory() as directory, patch.object(tagedit, "MANUAL", Path(directory)):
            handler.do_POST()
            saved = json.loads((Path(directory) / "t1.json").read_text())
        self.assertEqual(saved["fields"], {})
        self.assertNotIn("planRecordedAt", saved)
        t["structured"] = {"fields": copy.deepcopy(t["fields"])}
        stats.merge_fields(t, saved)
        self.assertEqual(review.plan_timing(t), "Before Entry")

    def test_plan_selection_reorder_preserves_timestamp_but_changes_keep_history(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(tagedit, "MANUAL", Path(directory)):
            first = {"requiredConfirmations": ["Entry Trigger", "Sweep"]}
            tagedit.save_manual("t", first)
            path = Path(directory) / "t.json"
            before = json.loads(path.read_text())
            tagedit.save_manual("t", {"requiredConfirmations": ["Sweep", "Entry Trigger"]}, "备注")
            reordered = json.loads(path.read_text())
            self.assertEqual(reordered["planRecordedAt"], before["planRecordedAt"])
            self.assertFalse(reordered.get("planHistory"))
            tagedit.save_manual("t", {"requiredConfirmations": ["Sweep"]})
            self.assertEqual(len(json.loads(path.read_text())["planHistory"]), 1)
            tagedit.save_manual("t", {"requiredConfirmations": None})
            self.assertEqual(len(json.loads(path.read_text())["planHistory"]), 2)

    def doc_weeks(self):
        src = DocsIntegrationTests().doc_weeks()
        return src, stats.weekly_v2(src, src["trades"], {})

    def test_week_form_saves_only_changed_field_and_follows_doc_updates(self):
        src, weeks = self.doc_weeks()
        submitted = {f"w__{w['label']}__{key}": [str(w["reviewNotes"].get(key) or "")]
                     for w in weeks for key, _ in tagedit.WEEK_KEYS}
        submitted["w__第1周__focusAction"] = ["订正动作"]
        saved = tagedit.week_corrections(weeks, {}, submitted)
        self.assertEqual(saved, {"第1周": {"focusAction": "订正动作"}})
        src["weeks"][0]["weekReview"]["focusTrigger"] = "文档更新后的触发条件"
        updated = stats.weekly_v2(src, src["trades"], {"_weeks": saved})
        self.assertEqual(updated[0]["behaviorGoal"]["trigger"], "文档更新后的触发条件")
        self.assertEqual(updated[0]["behaviorGoal"]["action"], "订正动作")

    def test_week_explicit_clear_does_not_pin_other_doc_fields(self):
        _, weeks = self.doc_weeks()
        saved = tagedit.week_corrections(weeks, {}, {"w__第1周__focusAction": [""]})
        self.assertEqual(saved, {"第1周": {"focusAction": None}})

    def test_week_count_correction_checks_against_document_count(self):
        _, weeks = self.doc_weeks()
        for value in ("4", "-1", "NaN"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                tagedit.week_corrections(weeks, {}, {"w__第2周__focusCompleted": [value]})
        html = tagedit.weeks_page(weeks, {})
        self.assertIn("入场前保存截图", html)
        self.assertIn("value='3'", html)

    def test_rebuild_is_offline_and_refreshes_state(self):
        success = type("Completed", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()
        with patch.object(tagedit.subprocess, "run", return_value=success) as run, patch.object(tagedit, "load_state") as load:
            self.assertTrue(tagedit.rebuild()["ok"])
        self.assertEqual([c.args[0][1] for c in run.call_args_list], ["parser/build.py", "parser/selfcheck.py"])
        load.assert_called_once()

    def test_rebuild_failure_stops_and_reports_failure(self):
        failure = type("Completed", (), {"returncode": 1, "stdout": "", "stderr": "error"})()
        with patch.object(tagedit.subprocess, "run", return_value=failure) as run, patch.object(tagedit, "load_state") as load:
            self.assertFalse(tagedit.rebuild()["ok"])
        run.assert_called_once()
        load.assert_not_called()

    def test_plan_edits_preserve_history(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(tagedit, "MANUAL", Path(directory)):
            tagedit.save_manual("t", {"plannedEntry": 100}, "note")
            tagedit.save_manual("t", {"plannedEntry": 103}, "")
            saved = json.loads((Path(directory) / "t.json").read_text())
        self.assertEqual(saved["planHistory"][0]["fields"]["plannedEntry"], 100)
        self.assertEqual(saved["fields"]["plannedEntry"], 103)
        self.assertEqual(saved["notes"], "")

    def test_nonfinite_plan_is_rejected(self):
        with self.assertRaises(ValueError):
            tagedit.save_manual("t", {"plannedEntry": float("nan")})

    def test_explicit_clear_removes_unconfirmed_source_field(self):
        handler = object.__new__(tagedit.H)
        handler.path = "/t/t1"
        t = trade()
        t["fields"]["htfBias"] = field("Bullish", "doc:keyword", False)
        handler.trades = [t]
        body = urllib.parse.urlencode({"f__htfBias": ""}).encode()
        handler.headers = {"Content-Length": str(len(body))}
        handler.rfile = io.BytesIO(body)
        handler.rebuild_response = lambda *a, **kw: None
        with tempfile.TemporaryDirectory() as directory, patch.object(tagedit, "MANUAL", Path(directory)):
            handler.do_POST()
            saved = json.loads((Path(directory) / "t1.json").read_text())
        self.assertIsNone(saved["fields"]["htfBias"])


class SelfcheckTests(unittest.TestCase):
    def snapshot(self):
        return json.loads((ROOT / "data/trades.json").read_text())

    def test_changed_net_r_is_rejected(self):
        data = self.snapshot()
        data["stats"]["netR"] = 999
        self.assertIn("汇总统计与逐笔记录不一致", selfcheck.validate(data)[0])

    def test_duplicate_id_is_rejected(self):
        data = self.snapshot()
        data["trades"].append(copy.deepcopy(data["trades"][0]))
        self.assertIn("交易 ID 重复", selfcheck.validate(data)[0])

    def test_fake_nonempty_evidence_is_rejected(self):
        data = self.snapshot()
        data["trades"][0]["analysis"]["riskCheck"][0]["evidence"] = "THIS SENTENCE IS NOT IN THE SOURCE"
        self.assertTrue(any("引用不在原文中" in e for e in selfcheck.validate(data)[0]))


if __name__ == "__main__":
    unittest.main()
