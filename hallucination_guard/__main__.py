"""CLI boundaries separate prediction from ground-truth evaluation."""

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

from .detector import detect_replies
from .evaluation import evaluate
from .io import load_records, write_json
from .reporting import percent, render_report, write_csv


def ensure_separate(inputs: list[Path], outputs: list[Path]) -> None:
    protected = {path.resolve() for path in inputs}
    if any(path.resolve() in protected for path in outputs):
        raise ValueError('输出路径不能覆盖输入或人工标注文件')


def print_metrics(metrics: dict) -> None:
    print(f"Samples={metrics['total']}  TP={metrics['tp']}  FP={metrics['fp']}  TN={metrics['tn']}  FN={metrics['fn']}")
    print('  '.join(f'{label}={percent(metrics[key])}' for label, key in [
        ('Precision', 'precision'), ('Recall', 'recall'), ('F1', 'f1'), ('Accuracy', 'accuracy')]))
    print(f"漏检 FN: {', '.join(metrics['false_negative_ids']) or '无'}")
    print(f"误报 FP: {', '.join(metrics['false_positive_ids']) or '无'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='客服回复幻觉检测：离线规则、证据解释、独立评估')
    commands = parser.add_subparsers(dest='command', required=True)
    detect = commands.add_parser('detect', help='只检测，不读取人工标注')
    detect.add_argument('--input', type=Path, default=Path('data/replies.json'))
    detect.add_argument('--output', type=Path, default=Path('output/predictions.json'))
    evaluate_parser = commands.add_parser('evaluate', help='按 id 对齐预测和人工标注')
    evaluate_parser.add_argument('--predictions', type=Path, default=Path('output/predictions.json'))
    evaluate_parser.add_argument('--truth', type=Path, default=Path('data/ground_truth.json'))
    evaluate_parser.add_argument('--output', type=Path, default=Path('output/metrics.json'))
    run = commands.add_parser('run', help='先检测，再评估，生成 JSON、CSV 和 HTML 报告')
    run.add_argument('--input', type=Path, default=Path('data/replies.json'))
    run.add_argument('--truth', type=Path, default=Path('data/ground_truth.json'))
    run.add_argument('--output-dir', type=Path, default=Path('output'))
    args = parser.parse_args(argv)
    try:
        if args.command == 'detect':
            ensure_separate([args.input], [args.output])
            predictions = detect_replies(load_records(args.input, 'replies'))
            write_json(args.output, predictions)
            print(f'已检测 {len(predictions)} 条，结果：{args.output}')
        elif args.command == 'evaluate':
            ensure_separate([args.predictions, args.truth], [args.output])
            metrics = evaluate(load_records(args.predictions, 'predictions'), load_records(args.truth, 'truth'))
            write_json(args.output, metrics)
            print_metrics(metrics)
        else:
            directory = args.output_dir
            destinations = [directory / name for name in ['predictions.json', 'metrics.json', 'report.html', 'results.csv', 'run_metadata.json']]
            ensure_separate([args.input, args.truth], destinations)
            records = load_records(args.input, 'replies')
            predictions = detect_replies(records)
            # Prediction is complete before labels are even read.
            metrics = evaluate(predictions, load_records(args.truth, 'truth'))
            metadata = {
                'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                'detector_version': 'rules-v1', 'mode': 'offline-rules',
                'input_sha256': hashlib.sha256(args.input.read_bytes()).hexdigest(),
                'truth_sha256': hashlib.sha256(args.truth.read_bytes()).hexdigest(),
                'evaluation_note': '已查看样本上的规则基线；非盲测、非线上泛化指标',
            }
            directory.mkdir(parents=True, exist_ok=True)
            write_json(directory / 'predictions.json', predictions)
            write_json(directory / 'metrics.json', metrics)
            write_json(directory / 'run_metadata.json', metadata)
            write_csv(directory / 'results.csv', predictions, metrics)
            (directory / 'report.html').write_text(render_report(records, predictions, metrics, metadata), encoding='utf-8')
            print('ID   检测     风险  类型')
            for row in predictions:
                print(f"{row['id']:4} {'有幻觉' if row['is_hallucination'] else '未检出'}  {row['severity']:2}    {'、'.join(row['types']) or '-'}")
            print_metrics(metrics)
            print(f'报告：{directory / "report.html"}')
        return 0
    except (ValueError, OSError) as error:
        print(f'错误：{error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
