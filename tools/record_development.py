"""Record real commands and source files in an inspectable development log page.

This is a log viewer, not a simulated IDE. It never invents terminal output.
Run from the project directory: python tools/record_development.py
"""

import html
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'output'
OUTPUT.mkdir(exist_ok=True)
environment = dict(os.environ, PYTHONUTF8='1')
commands = [
    [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
    [sys.executable, '-m', 'coverage', 'run', '-m', 'unittest', 'discover', '-s', 'tests'],
    [sys.executable, '-m', 'coverage', 'report', '-m'],
    [sys.executable, '-m', 'hallucination_guard', 'run'],
]
records = []
for command in commands:
    process = subprocess.run(command, cwd=ROOT, env=environment, text=True, encoding='utf-8',
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    record = {'command': 'python ' + ' '.join(command[1:]), 'exit_code': process.returncode, 'output': process.stdout}
    records.append(record)
    print(record['command'])
    print(process.stdout, end='')
    if process.returncode:
        raise SystemExit(process.returncode)
(OUTPUT / 'development_commands.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
(OUTPUT / 'test_results.txt').write_text(records[0]['output'], encoding='utf-8')
(OUTPUT / 'coverage.txt').write_text(records[2]['output'], encoding='utf-8')
(OUTPUT / 'run.txt').write_text(records[3]['output'], encoding='utf-8')
source = (ROOT / 'hallucination_guard' / '__main__.py').read_text(encoding='utf-8').splitlines()
start = next(index for index, line in enumerate(source) if "records = load_records(args.input" in line)
excerpt = '\n'.join(f'{index + 1:>3}  {line}' for index, line in enumerate(source[start:start + 24], start))
terminals = []
for index in (0, 2, 3):
    record = records[index]
    lines = record['output'].splitlines()
    if index == 0:
        visible = '\n'.join(lines[:3] + ['… 完整输出见 test_results.txt …'] + lines[-5:])
    elif index == 3:
        visible = '\n'.join(lines[-5:])
    else:
        visible = record['output']
    terminals.append(f'<section><div class="command">$ {html.escape(record["command"])}<span>exit {record["exit_code"]}</span></div><pre>{html.escape(visible)}</pre></section>')
page = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>开发验证控制台 · 客服回复幻觉检测</title><link rel="icon" href="data:,"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>*{{box-sizing:border-box}} body{{margin:0;background:#11191d;color:#dce6e6;font:14px/1.7 "Microsoft YaHei",sans-serif}} main{{max-width:1500px;margin:auto;padding:28px 36px}} h1{{font-size:26px;margin:4px 0}} .muted{{color:#8da6ac}} .head{{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #35454b;padding-bottom:18px}} .grid{{display:grid;grid-template-columns:0.95fr 1.2fr;gap:22px;margin-top:24px}} .panel{{background:#172328;border:1px solid #35454b;padding:20px;min-width:0}} h2{{font-size:15px;margin:0 0 18px;color:#8dd5be}} pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.8 Consolas,"Microsoft YaHei",monospace;margin:12px 0;color:#c2d5d7}} section{{border-bottom:1px solid #35454b;padding-bottom:12px;margin-bottom:14px}} .command{{color:#8dd5be;font:12px/1.7 Consolas,monospace}} .command span{{float:right;color:#9fb1b6}} .files{{font-family:Consolas;line-height:2;color:#9eb8c0}} footer{{margin-top:18px;color:#8da6ac;font-size:12px}} .pill{{background:#1e453b;color:#97e7c7;padding:5px 13px}}</style></head><body><main>
<div class="head"><div><div class="muted">LOCAL DEVELOPMENT / 0110</div><h1>开发验证控制台</h1><div class="muted">实际源码 + 真实命令输出 · 由 record_development.py 现场执行并记录</div></div><span class="pill">所有命令 exit 0</span></div>
<div class="grid"><div class="panel"><h2>源码检查 · 检测与评估分离</h2><div class="files">hallucination_guard/<br>├─ detector.py &nbsp; 领域规则与证据<br>├─ evaluation.py &nbsp; 独立指标计算<br>├─ io.py &nbsp; 输入校验<br>├─ reporting.py &nbsp; 报告生成<br>└─ __main__.py &nbsp; 命令行编排</div><p class="muted">__main__.py · 原文件行号</p><pre>{html.escape(excerpt)}</pre></div><div class="panel"><h2>终端执行记录 · Python {sys.version.split()[0]}</h2>{''.join(terminals)}</div></div>
<footer>记录时间：{datetime.now(timezone.utc).isoformat(timespec='seconds')}　|　这是本地开发日志查看器，非 IDE 模拟图。完整原始输出见 development_commands.json。</footer>
</main></body></html>'''
(OUTPUT / 'development.html').write_text(page, encoding='utf-8')
