"""Evaluation tests use fabricated samples, never the interview answer key."""

import copy
import unittest

from hallucination_guard.evaluation import evaluate


def prediction(sample_id, value, types=None):
    return {"id": sample_id, "is_hallucination": value, "types": types or []}


def truth(sample_id, value, kind=None):
    return {
        "id": sample_id,
        "is_hallucination": value,
        "hallucination_type": kind,
        "detail": "独立测试样例",
    }


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.predictions = [
            prediction("a", True, ["政策与优惠"]),
            prediction("b", False),
            prediction("c", True, ["事实信息"]),
            prediction("d", False),
        ]
        self.truths = [
            truth("a", True, "优惠编造"),
            truth("b", False),
            truth("c", False),
            truth("d", True, "参数编造"),
        ]

    def test_confusion_matrix_and_ids(self):
        result = evaluate(self.predictions, self.truths)
        self.assertEqual(
            {key: result[key] for key in ("total", "tp", "tn", "fp", "fn")},
            {"total": 4, "tp": 1, "tn": 1, "fp": 1, "fn": 1},
        )
        self.assertEqual(result["false_positive_ids"], ["c"])
        self.assertEqual(result["false_negative_ids"], ["d"])
        for metric in ("precision", "recall", "f1", "accuracy",
                       "false_positive_rate", "false_negative_rate"):
            self.assertEqual(result[metric], 0.5)

    def test_rows_include_traceable_evidence(self):
        rows = evaluate(self.predictions, self.truths)["rows"]
        self.assertEqual([row["outcome"] for row in rows], ["TP", "TN", "FP", "FN"])
        self.assertEqual(rows[0], {
            "id": "a", "predicted": True, "actual": True, "outcome": "TP",
            "predicted_types": ["政策与优惠"], "expected_type": "政策与优惠",
            "type_match": True, "detail": "独立测试样例",
        })
        self.assertIsNone(rows[1]["type_match"])
        self.assertFalse(rows[3]["type_match"])

    def test_reordered_predictions_match_by_id(self):
        expected = evaluate(self.predictions, self.truths)
        actual = evaluate(list(reversed(self.predictions)), self.truths)
        self.assertEqual(actual, expected)

    def test_metrics_do_not_assume_balanced_classes(self):
        predictions = [prediction("a", True), prediction("b", True),
                       prediction("c", False), prediction("d", True),
                       prediction("e", False)]
        truths = [truth("a", True, "政策编造"), truth("b", True, "政策偏差"),
                  truth("c", True, "参数编造"), truth("d", False), truth("e", False)]
        result = evaluate(predictions, truths)
        self.assertAlmostEqual(result["precision"], 2 / 3)
        self.assertAlmostEqual(result["recall"], 2 / 3)
        self.assertAlmostEqual(result["f1"], 2 / 3)
        self.assertEqual(result["accuracy"], 3 / 5)
        self.assertEqual(result["false_positive_rate"], 1 / 2)
        self.assertEqual(result["false_negative_rate"], 1 / 3)

    def test_no_positive_predictions_precision_is_undefined(self):
        result = evaluate([prediction("a", False)], [truth("a", True, "参数编造")])
        self.assertIsNone(result["precision"])
        self.assertEqual(result["recall"], 0)
        self.assertEqual(result["f1"], 0)
        self.assertIsNone(result["false_positive_rate"])

    def test_all_negative_truth_recall_is_undefined(self):
        result = evaluate([prediction("a", False)], [truth("a", False)])
        for key in ("precision", "recall", "f1", "false_negative_rate", "type_match_rate"):
            self.assertIsNone(result[key])
        self.assertEqual(result["accuracy"], 1)
        self.assertEqual(result["false_positive_rate"], 0)

    def test_false_positive_only_f1_is_zero(self):
        result = evaluate([prediction("a", True)], [truth("a", False)])
        self.assertEqual(result["f1"], 0)
        self.assertIsNone(result["recall"])

    def test_every_truth_type_is_mapped(self):
        mapping = {
            "政策编造": "政策与优惠", "政策偏差": "政策与优惠", "优惠编造": "政策与优惠",
            "参数编造": "产品参数", "信息编造": "事实信息", "能力越界": "能力越界",
            "安全误导": "安全误导", "信息遗漏": "误导性遗漏",
        }
        for source, target in mapping.items():
            with self.subTest(source=source):
                result = evaluate([prediction("a", True, [target])], [truth("a", True, source)])
                self.assertEqual(result["rows"][0]["expected_type"], target)
                self.assertTrue(result["rows"][0]["type_match"])

    def test_type_match_measures_primary_label_coverage(self):
        predictions = [prediction("a", True, ["事实信息", "政策与优惠"]),
                       prediction("b", True, ["事实信息"]), prediction("c", False)]
        truths = [truth("a", True, "政策编造"), truth("b", True, "参数编造"),
                  truth("c", True, "安全误导")]
        result = evaluate(predictions, truths)
        self.assertEqual(result["type_match_rate"], 1 / 3)
        self.assertEqual([row["type_match"] for row in result["rows"]], [True, False, False])

    def test_input_is_not_mutated(self):
        before = copy.deepcopy((self.predictions, self.truths))
        evaluate(self.predictions, self.truths)
        self.assertEqual((self.predictions, self.truths), before)

    def test_empty_input_rejected(self):
        for predictions, truths in (([], []), ([], self.truths), (self.predictions, [])):
            with self.subTest(predictions=bool(predictions), truths=bool(truths)):
                with self.assertRaisesRegex(ValueError, "非空"):
                    evaluate(predictions, truths)

    def test_non_list_input_rejected(self):
        for predictions, truths in (({}, self.truths), (self.predictions, None)):
            with self.assertRaisesRegex(ValueError, "列表"):
                evaluate(predictions, truths)

    def test_duplicate_id_rejected_on_either_side(self):
        with self.assertRaisesRegex(ValueError, "重复.*a"):
            evaluate(self.predictions + [self.predictions[0]], self.truths)
        with self.assertRaisesRegex(ValueError, "重复.*a"):
            evaluate(self.predictions, self.truths + [self.truths[0]])

    def test_missing_and_extra_prediction_ids_rejected(self):
        with self.assertRaisesRegex(ValueError, "缺少.*d"):
            evaluate(self.predictions[:-1], self.truths)
        with self.assertRaisesRegex(ValueError, "多余.*extra"):
            evaluate(self.predictions + [prediction("extra", False)], self.truths)

    def test_missing_or_invalid_id_rejected(self):
        for bad_id in (None, "", " ", 123, []):
            with self.subTest(bad_id=bad_id):
                with self.assertRaisesRegex(ValueError, "id"):
                    evaluate([prediction(bad_id, False)], [truth("a", False)])
        with self.assertRaisesRegex(ValueError, "id"):
            evaluate([{"is_hallucination": False, "types": []}], [truth("a", False)])

    def test_non_object_records_rejected(self):
        with self.assertRaisesRegex(ValueError, "对象"):
            evaluate(["sample"], [truth("a", False)])

    def test_booleans_must_be_actual_bool_on_either_side(self):
        for value in (0, 1, "true", None):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "bool"):
                    evaluate([prediction("a", value)], [truth("a", False)])
                with self.assertRaisesRegex(ValueError, "bool"):
                    evaluate([prediction("a", False)], [truth("a", value)])

    def test_missing_boolean_rejected(self):
        with self.assertRaisesRegex(ValueError, "bool"):
            evaluate([{"id": "a", "types": []}], [truth("a", False)])

    def test_unknown_truth_type_rejected(self):
        for label in ("臆想类型", None, [], ""):
            with self.subTest(label=label):
                with self.assertRaisesRegex(ValueError, "未知.*类型"):
                    evaluate([prediction("a", True)], [truth("a", True, label)])

    def test_negative_truth_does_not_accept_positive_label(self):
        with self.assertRaisesRegex(ValueError, "正常.*类型"):
            evaluate([prediction("a", False)], [truth("a", False, "参数编造")])

    def test_negative_truth_accepts_empty_label_conventions(self):
        for label in (None, "", "无"):
            with self.subTest(label=label):
                result = evaluate([prediction("a", False)], [truth("a", False, label)])
                self.assertIsNone(result["rows"][0]["expected_type"])

    def test_prediction_types_must_be_a_string_list(self):
        for types in (None, "政策与优惠", [123], [""], [" "]):
            with self.subTest(types=types):
                sample = {"id": "a", "is_hallucination": True, "types": types}
                with self.assertRaisesRegex(ValueError, "types"):
                    evaluate([sample], [truth("a", True, "政策编造")])

    def test_detail_must_be_string(self):
        sample = truth("a", False)
        sample["detail"] = 123
        with self.assertRaisesRegex(ValueError, "detail"):
            evaluate([prediction("a", False)], [sample])


if __name__ == "__main__":
    unittest.main()
