import json
import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CLITests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, '-X', 'utf8', '-m', 'hallucination_guard', *map(str, args)],
                              cwd=ROOT, text=True, encoding='utf-8', capture_output=True)

    def test_full_offline_workflow_and_separate_evaluation(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            result = self.run_cli('run', '--output-dir', out)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Recall', result.stdout)
            predictions = json.loads((out / 'predictions.json').read_text(encoding='utf-8'))
            metrics = json.loads((out / 'metrics.json').read_text(encoding='utf-8'))
            self.assertEqual(len(predictions), 20)
            self.assertEqual(metrics['total'], 20)
            self.assertEqual(sum(metrics[key] for key in ['tp', 'fp', 'tn', 'fn']), 20)
            self.assertTrue((out / 'report.html').is_file())
            self.assertTrue((out / 'results.csv').is_file())
            self.assertIn('input_sha256', json.loads((out / 'run_metadata.json').read_text(encoding='utf-8')))
            separate = self.run_cli('evaluate', '--predictions', out / 'predictions.json', '--output', out / 'separate.json')
            self.assertEqual(separate.returncode, 0, separate.stderr)
            self.assertEqual(metrics, json.loads((out / 'separate.json').read_text(encoding='utf-8')))

    def test_detect_does_not_need_truth(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            source = out / 'new.json'
            source.write_text(json.dumps([{'id': 'unseen', 'user_question': '支持货到付款吗？',
                                         'system_reply': '不支持货到付款。', 'knowledge_base': '不支持货到付款。'}], ensure_ascii=False), encoding='utf-8')
            result = self.run_cli('detect', '--input', source, '--output', out / 'prediction.json')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads((out / 'prediction.json').read_text(encoding='utf-8'))[0]['id'], 'unseen')

    def test_invalid_input_exits_cleanly(self):
        result = self.run_cli('detect', '--input', 'missing-file.json')
        self.assertEqual(result.returncode, 2)
        self.assertIn('错误', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_output_cannot_overwrite_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'source.json'
            original = '[{"id":"x","user_question":"q","system_reply":"a","knowledge_base":"k"}]'
            source.write_text(original, encoding='utf-8')
            result = self.run_cli('detect', '--input', source, '--output', source)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(source.read_text(encoding='utf-8'), original)

    def test_main_commands_and_errors_in_process(self):
        from hallucination_guard.__main__ import main
        with tempfile.TemporaryDirectory() as temporary, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            out = Path(temporary)
            self.assertEqual(main(['run', '--output-dir', str(out)]), 0)
            self.assertEqual(main(['detect', '--output', str(out / 'only.json')]), 0)
            self.assertEqual(main(['evaluate', '--predictions', str(out / 'only.json'), '--output', str(out / 'eval.json')]), 0)
            self.assertEqual(main(['detect', '--input', str(out / 'missing.json')]), 2)
            self.assertEqual(main(['detect', '--input', str(out / 'only.json'), '--output', str(out / 'only.json')]), 2)


if __name__ == '__main__':
    unittest.main()
