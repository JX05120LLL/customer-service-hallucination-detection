# 验证与交付记录

需求来源：题目 0110 与用户提供的两份 JSON，无外部规划文件。

| 用户目标 | 验证方式 | 结果与证据 |
| --- | --- | --- |
| 对知识库自动检测并提供证据 | 独立规则测试，包含改数字、新 ID、支持性改写和否定 | 34 项检测器测试通过，详见 detector_tdd.md |
| 按人工标注计算漏检/误报 | 虚构 TP/TN/FP/FN、重排 ID、零分母及非法输入测试 | 23 项评估测试通过，详见 evaluation_tdd.md |
| 文件可以读取，报告不执行数据里的标签 | BOM、重复 ID、错误 JSON、报告转义测试 | 8 项 IO/报告测试通过 |
| 用户一条命令完成任务，检测可以脱离标签运行 | CLI 子进程集成测试、单独 detect/evaluate、输入覆盖保护 | 5 项 CLI 测试通过 |

## RED / GREEN

- IO/报告：先执行 `python -m unittest tests.test_io_reporting -v`，因目标模块尚未实现而 RED，保存于 `io_report_red.txt`；实现后同一目标 8 项通过，见 `io_report_green.txt`。
- CLI：先执行 `python -m unittest tests.test_cli -v`，因模块入口尚未实现而 4 项失败，见 `cli_red.txt`；完成后增加同进程覆盖采集验证，当前 5 项通过。
- 检测器：除首次 RED 外，审查发现的履约分类、前置条件、接口业务域、否定作用域均先加复现测试，确认失败后修复。具体记录见 `detector_tdd.md`。
- 评估器：使用独立虚构数据验证，没有根据提供的人工标签调整指标公式。

## 最终验证

`python tools/record_development.py` 实际按顺序执行：

1. `python -m unittest discover -s tests -v`：70 tests，OK。
2. `python -m coverage run -m unittest discover -s tests`：70 tests，OK。
3. `python -m coverage report -m`：331 条语句，134 个分支，合计覆盖率 98%。检测器与评估器均为 100%。
4. `python -m hallucination_guard run`：TP=18、FP=1、TN=1、FN=0；仅 h16 误报。

完整命令、退出码、原始输出保存在 `output/development_commands.json`。`python -m compileall -q hallucination_guard tests tools` 通过。

说明：检测器阶段文档中的标准库 trace 覆盖率，把跟踪开始前执行的定义行也计入未覆盖；最终统一使用 Coverage.py 口径，以 `output/coverage.txt` 为准。未被覆盖的少量路径包括文件超限、未知输入类型，以及由子进程执行的模块启动出口。浏览器截图脚本属于开发辅助，不纳入核心包覆盖率。

## 复审与可复现性

- 独立审查确认：检测不读 ground truth；评估按 ID 严格对齐；零分母不伪装为 0；无硬编码样本 ID 的决策分支。
- 复核正常支付子集、带医生前提的改写、保留偏码限制的改写、物流功能不可用但查询产品参数等构造样例。
- HTML 由结构化输出生成，浏览器检查指标、20 行表格、20 个证据区域及 h16 锚点；截图来自实际渲染。
- 源数据复制后保留原始字节，运行 metadata 记录 SHA-256。
- 初次本地交付时未初始化 Git 或提交；后续按用户要求发布到 GitHub 公开仓库。公开文件不包含浏览器安装、缓存、本机浏览器配置或环境凭证，未部署在线检测服务。

本批样本在开发阶段已查看，不能视为独立盲测。70 个测试验证实现行为，不等于 70 条独立业务评测数据。
