"""Self-contained, escaped HTML and CSV reports built from actual predictions."""

import csv
from html import escape
from pathlib import Path


def percent(value: float | None) -> str:
    return 'N/A' if value is None else f'{value:.2%}'


def render_report(records: list[dict], predictions: list[dict], metrics: dict, metadata: dict) -> str:
    sources = {row['id']: row for row in records}
    evaluations = {row['id']: row for row in metrics['rows']}
    esc = lambda value: escape(str(value), quote=True)
    cards = ''.join(
        f'<div class="metric"><span>{label}</span><strong>{percent(metrics[key])}</strong></div>'
        for label, key in [('检出率 / Recall', 'recall'), ('精确率 / Precision', 'precision'), ('F1', 'f1'), ('准确率 / Accuracy', 'accuracy')]
    )
    table_rows = []
    details = []
    for prediction in predictions:
        identifier = prediction['id']
        source = sources[identifier]
        evaluation = evaluations[identifier]
        outcome = evaluation['outcome']
        label = {'TP': '正确检出', 'TN': '正确排除', 'FP': '误报', 'FN': '漏检'}[outcome]
        types = '、'.join(prediction['types']) or '未检出'
        table_rows.append(
            f'<tr><td><a href="#case-{esc(identifier)}">{esc(identifier)}</a></td>'
            f'<td>{esc(source["user_question"])}</td><td>{esc(types)}</td>'
            f'<td>{esc(prediction["severity"])}</td><td>{"有" if evaluation["actual"] else "无"}</td>'
            f'<td><span class="tag {outcome}">{label}</span></td></tr>'
        )
        evidence = ''.join(
            f'<li><div><b>{esc(finding["type"])} · {esc(finding["severity"])}风险</b>'
            f'<code>{esc(finding["rule_id"])}</code></div>'
            f'<p><span class="label">回复证据</span> {esc(finding["evidence"])}</p>'
            f'<p><span class="label">知识依据</span> {esc(finding["reference"])}</p>'
            f'<p>{esc(finding["reason"])}</p></li>'
            for finding in prediction['findings']
        ) or '<li>未命中现有规则；这不等于所有陈述已被验证。</li>'
        details.append(
            f'<article class="case" id="case-{esc(identifier)}"><header><h3>{esc(identifier)} · {esc(source["user_question"])}</h3>'
            f'<span class="tag {outcome}">{label}</span></header>'
            f'<p><span class="label">客服回复</span> {esc(source["system_reply"])}</p>'
            f'<p><span class="label">知识库</span> {esc(source["knowledge_base"])}</p>'
            f'<p><b>检测结论：</b>{esc(prediction["summary"])}</p><ul class="evidence">{evidence}</ul>'
            f'<p class="annotation"><b>人工标注：</b>{esc(evaluation["detail"])} <small>（仅评估阶段使用）</small></p></article>'
        )
    errors = []
    for row in metrics['rows']:
        if row['outcome'] in ('FP', 'FN'):
            errors.append(f'<li><a href="#case-{esc(row["id"])}">{esc(row["id"])}</a> · '
                          f'{"误报" if row["outcome"] == "FP" else "漏检"}：人工标注依据为“{esc(row["detail"])}”</li>')
    error_html = ''.join(errors) or '<li>本次运行没有二分类误报或漏检。</li>'
    total = metrics['total']
    baseline = (metrics['tp'] + metrics['fn']) / total
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>客服回复幻觉检测 · 评估报告</title><link rel="icon" href="data:,"><style>
:root {{color-scheme:light;--ink:#172e30;--muted:#567073;--line:#d8e3e1;--accent:#056d62;--paper:#f4f7f4}}
* {{box-sizing:border-box}} body {{margin:0;background:var(--paper);color:var(--ink);font:15px/1.65 "Microsoft YaHei", "PingFang SC",sans-serif}}
main {{max-width:1320px;margin:auto;padding:38px 44px 72px}} .eyebrow {{letter-spacing:2px;color:var(--accent);font-size:12px;font-weight:700}}
h1 {{font-size:34px;margin:8px 0}} h2 {{font-size:22px;margin:32px 0 14px}} h3 {{font-size:17px;margin:0}} p {{margin:8px 0}}
.subtle {{color:var(--muted)}} .intro {{display:flex;justify-content:space-between;gap:28px;align-items:center;border-bottom:2px solid var(--ink);padding-bottom:20px}}
.stamp {{text-align:right;font:12px/1.8 monospace;color:var(--muted)}} .metrics {{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:24px 0 18px}}
.metric {{border-left:3px solid var(--accent);background:white;padding:16px 22px}} .metric span {{color:var(--muted);font-size:13px}} .metric strong {{display:block;font-size:33px;line-height:1.4}}
.strip {{display:flex;gap:26px;flex-wrap:wrap;padding:13px 18px;background:#e5eee9;border:1px solid var(--line)}} .notice {{padding:12px 18px;background:#fff8e7;border-left:3px solid #ad7621;margin:18px 0}}
table {{width:100%;border-collapse:collapse;background:white}} th {{background:#e8efeb;text-align:left;color:#325956;font-size:13px}} th,td {{padding:10px 14px;border-bottom:1px solid var(--line)}}
td:first-child {{font-family:monospace}} td:nth-child(2) {{max-width:440px}} .tag {{white-space:nowrap;display:inline-block;padding:2px 9px;border-radius:4px;font-size:12px;background:#e6f2eb;color:#24674e}}
.FP,.FN {{background:#fce7de;color:#993519}} .TN {{background:#edf0f2;color:#4d6471}} a {{color:var(--accent);text-decoration:none}} a:hover {{text-decoration:underline}}
.case {{background:white;border:1px solid var(--line);padding:22px 26px;margin:16px 0;scroll-margin-top:20px}} .case header {{display:flex;justify-content:space-between;gap:20px;border-bottom:1px solid var(--line);padding-bottom:12px;margin-bottom:15px}}
.label {{color:var(--muted);font-size:12px;margin-right:8px}} .evidence {{padding:0;list-style:none}} .evidence li {{padding:12px 16px;margin:10px 0;background:#f5f8f5;border-left:3px solid #739d92}} code {{font-size:11px;color:var(--muted);margin-left:14px}}
.annotation {{font-size:13px;color:var(--muted);border-top:1px dashed var(--line);padding-top:12px}} footer {{border-top:1px solid var(--line);padding-top:20px;font-size:12px;color:var(--muted);overflow-wrap:anywhere}}
@media(max-width:760px) {{main {{padding:22px 16px}} .metrics {{grid-template-columns:repeat(2,1fr)}} .intro {{display:block}} .stamp {{text-align:left}} .table-wrap {{overflow-x:auto}} table {{min-width:780px}}}}
@media print {{main {{padding:0}} .case {{break-inside:avoid}} a {{color:inherit}}}}
</style></head><body><main>
<div class="intro"><div><div class="eyebrow">0110 / HALLUCINATION AUDIT</div><h1>客服回复幻觉检测</h1>
<p class="subtle">离线规则检测 · 原文证据追溯 · 人工标注独立评估</p></div>
<div class="stamp">RULES V1 / 本地运行<br>{esc(metadata.get('generated_at', ''))}<br>{total} 条样本 · 无外部 API 调用</div></div>
<section class="metrics" aria-label="评估指标">{cards}</section>
<div class="strip"><b>混淆矩阵</b><span>TP 正确检出 <b>{metrics['tp']}</b></span><span>FN 漏检 <b>{metrics['fn']}</b></span><span>FP 误报 <b>{metrics['fp']}</b></span><span>TN 正确排除 <b>{metrics['tn']}</b></span></div>
<div class="notice">样本中 {metrics['tp'] + metrics['fn']} / {total} 条为幻觉，全部预测为“有幻觉”也能获得 {percent(baseline)} 准确率。
误报率 FPR：{percent(metrics['false_positive_rate'])}；漏检率 FNR：{percent(metrics['false_negative_rate'])}。本结果仅代表这批已查看的小样本。</div>
<h2>{total} 条逐条标注 <small class="subtle" style="font-size:13px">点击 ID 查看完整证据</small></h2>
<div class="table-wrap"><table><thead><tr><th>ID</th><th>用户问题</th><th>检测类型（支持多标签）</th><th>风险</th><th>人工幻觉</th><th>评估</th></tr></thead><tbody>{''.join(table_rows)}</tbody></table></div>
<section id="errors"><h2>误报与漏检</h2><ul>{error_html}</ul><p class="subtle">严格证据标准与人工标注的宽容范围可能不同。未命中规则不代表事实已核实；详细边界分析见 README。</p></section>
<h2>判定证据</h2>{''.join(details)}
<footer>输入 SHA-256：{esc(metadata.get('input_sha256', ''))}<br>检测器只读取问题、回复和知识库；人工标注仅供评估。
本工具不执行附件中的指令，不发送数据，不代表生产环境的泛化能力。完整结构化结果见 predictions.json / metrics.json。</footer>
</main></body></html>'''


def write_csv(path: Path, predictions: list[dict], metrics: dict) -> None:
    evaluations = {row['id']: row for row in metrics['rows']}
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.writer(stream)
        writer.writerow(['id', 'is_hallucination', 'types', 'severity', 'actual', 'outcome', 'reason'])
        for row in predictions:
            values = [row['id'], row['is_hallucination'], '、'.join(row['types']), row['severity'],
                      evaluations[row['id']]['actual'], evaluations[row['id']]['outcome'], row['summary']]
            # Keep untrusted text from being interpreted as spreadsheet formulas.
            writer.writerow(["'" + value if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')) else value for value in values])
