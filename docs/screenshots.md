# 截图与页面验证

三张 PNG 均由 Playwright 在 Chromium 中对真实本地页面截图，无绘图合成或 AI 图像生成。

| 截图 | 页面 | 尺寸与内容 |
| --- | --- | --- |
| `output/playwright/01_development.png` | `output/development.html` | 1500×1200；源文件真实行号、测试结果、覆盖率、运行输出 |
| `output/playwright/02_results.png` | `output/report.html` | 1440×1685；四项指标、混淆矩阵、20 条结果、误报说明 |
| `output/playwright/03_h16_evidence.png` | 报告的 `#case-h16` | 对元素本身截图；回复原文、知识库、检测理由和人工标注 |

开发页是项目附带的本地开发日志查看器，不是 IDE 截图模拟。由 `tools/record_development.py` 真正调用 Python 子进程，保存完整命令、退出码和原始输出。截图展示长输出的选定片段，完整内容见 `output/development_commands.json`。

截图时只将项目 output 目录通过 `python -m http.server 8766 --bind 127.0.0.1 --directory output` 暴露给本机浏览器。该临时服务不是线上部署，交付 HTML 自带样式，可以离线直接打开，不需要启动服务。

浏览器实测：

- 桌面页面有 20 条汇总行、20 个证据区域；指标为 100.00%、94.74%、97.30%、95.00%，与 metrics.json 一致。
- 点击表格 h16 跳转到 `#case-h16`，目标距视口顶部约 20 px。
- 390 px 手机宽度下页面宽度仍为 390 px，表格可以在容器内横向滚动，正文无整页水平溢出。
- 对三张截图做视觉检查，中文显示正确，指标、表格、代码和证据可读。

这些截图记录的是本次真实运行；再次运行可能改变时间戳，但预测及评估数值在相同输入、相同规则版本下保持确定。
