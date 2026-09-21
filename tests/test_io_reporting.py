import json
import tempfile
import unittest
from pathlib import Path

from hallucination_guard.io import load_records, write_json
from hallucination_guard.reporting import render_report


class InputTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'input.json'

    def save(self, value):
        self.path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8-sig')

    def test_accepts_bom_and_unicode(self):
        data = [{'id': 'new', 'user_question': '问题', 'system_reply': '回复', 'knowledge_base': '依据'}]
        self.save(data)
        self.assertEqual(load_records(self.path, 'replies'), data)

    def test_rejects_invalid_structures(self):
        for value in ({}, [], [None], [{'id': 'x'}], [{'id': ' ', 'user_question': 'q', 'system_reply': 'a', 'knowledge_base': 'k'}]):
            with self.subTest(value=value):
                self.save(value)
                with self.assertRaises(ValueError):
                    load_records(self.path, 'replies')

    def test_rejects_duplicate_id(self):
        row = {'id': 'x', 'user_question': 'q', 'system_reply': 'a', 'knowledge_base': 'k'}
        self.save([row, row])
        with self.assertRaisesRegex(ValueError, '重复'):
            load_records(self.path, 'replies')

    def test_rejects_invalid_json_and_missing_file(self):
        self.path.write_text('{', encoding='utf-8')
        with self.assertRaises(ValueError):
            load_records(self.path, 'replies')
        with self.assertRaises(ValueError):
            load_records(self.path.with_name('absent'), 'replies')

    def test_prediction_boolean_must_be_boolean(self):
        self.save([{'id': 'a', 'is_hallucination': 'false', 'types': []}])
        with self.assertRaises(ValueError):
            load_records(self.path, 'predictions')

    def test_truth_and_predictions_can_be_loaded(self):
        data = [{'id': 'a', 'is_hallucination': False, 'hallucination_type': None, 'detail': '正常'}]
        self.save(data)
        self.assertEqual(load_records(self.path, 'truth'), data)
        data = [{'id': 'a', 'is_hallucination': False, 'types': []}]
        self.save(data)
        self.assertEqual(load_records(self.path, 'predictions'), data)

    def test_write_json_creates_parent_and_preserves_chinese(self):
        path = self.path.parent / 'nested' / 'result.json'
        write_json(path, {'note': '结果'})
        self.assertIn('结果', path.read_text(encoding='utf-8'))


class ReportTests(unittest.TestCase):
    def test_report_escapes_data_and_shows_actual_metrics(self):
        source = [{'id': 'x', 'user_question': '<script>alert(1)</script>', 'system_reply': '回复', 'knowledge_base': '依据'}]
        predictions = [{'id': 'x', 'is_hallucination': True, 'types': ['事实信息'], 'severity': '低', 'summary': '缺少依据', 'review_required': True,
                        'findings': [{'type': '事实信息', 'severity': '低', 'evidence': '<img src=x onerror=alert(1)>', 'reference': '依据', 'reason': '缺少依据', 'rule_id': 'test'}]}]
        metrics = {'total': 1, 'tp': 0, 'fp': 1, 'tn': 0, 'fn': 0, 'precision': 0.0, 'recall': None, 'f1': 0.0, 'accuracy': 0.0,
                   'false_positive_rate': 1.0, 'false_negative_rate': None, 'false_positive_ids': ['x'], 'false_negative_ids': [],
                   'rows': [{'id': 'x', 'outcome': 'FP', 'actual': False, 'predicted': True, 'expected_type': None, 'predicted_types': ['事实信息'], 'type_match': None, 'detail': '正常'}]}
        html = render_report(source, predictions, metrics, {'generated_at': '2026-09-20', 'input_sha256': 'abc'})
        self.assertNotIn('<script>alert', html)
        self.assertNotIn('<img src=x', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('误报', html)
        self.assertIn('N/A', html)
        self.assertIn('100.00%', html)
        self.assertIn('id="case-x"', html)


if __name__ == '__main__':
    unittest.main()
