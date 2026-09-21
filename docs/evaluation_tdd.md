# 独立评估模块的 TDD 记录

本模块的验收行为来自本次任务中的评估需求，没有外部计划文件。测试使用虚构 ID 和独立构造样本；编写、验证本模块时未读取 20 条回复或人工答案。`evaluate` 只消费调用方传入的预测和人工标注，不调用检测器、不写回规则、不读写文件。

## 用户路径与保证

作为评审者，我需要将预测按 ID 与人工标注严格对齐，看到可信的混淆矩阵、检出率以及每个误报/漏检样本；无效数据不得被静默丢弃。

| 保证 | 测试入口 | 类型 | 结果 |
| --- | --- | --- | --- |
| TP/TN/FP/FN、精确率、召回率、F1、准确率、误报率、漏检率计算正确 | `test_confusion_matrix_and_ids`、`test_metrics_do_not_assume_balanced_classes` | 单元 | PASS |
| 样本可重排，按 ID 匹配，返回可追溯逐行证据 | `test_reordered_predictions_match_by_id`、`test_rows_include_traceable_evidence` | 单元 | PASS |
| 分母为零时返回 `None`，不把未定义指标伪装成 0 | 三个零分母测试 | 单元 | PASS |
| 所有指定标签映射正确，类型指标仅表示人工主类型覆盖 | `test_every_truth_type_is_mapped`、`test_type_match_measures_primary_label_coverage` | 单元 | PASS |
| 重复/缺失/多余 ID、非布尔值、未知标签、无效类型和空输入明确报错 | 输入校验相关测试 | 单元 | PASS |
| 评估不会修改输入预测或人工标注 | `test_input_is_not_mutated` | 单元 | PASS |

## 实际 RED / GREEN

先添加 `tests/test_evaluation.py`，随后执行：

```powershell
python -m unittest discover -s tests -p test_evaluation.py -v
```

RED 输出为 `ModuleNotFoundError: No module named 'hallucination_guard.evaluation'`，`FAILED (errors=1)`，退出码 1。此时预期实现模块尚未创建，失败指向待实现接口。

随后添加 `hallucination_guard/evaluation.py` 并再次执行完全相同命令，输出：

```text
Ran 23 tests in 0.002s
OK
```

GREEN 退出码 0。没有为了通过测试而修改检测器、人工标签或数据。按用户全局规则，没有执行 Git 提交。

## 覆盖率

使用环境已经安装的 `coverage`；运行应用与单元测试仅需 Python 标准库。以下命令在内存中采集，不写覆盖率缓存：

```powershell
python -c "import coverage, unittest; cov = coverage.Coverage(config_file=False, data_file=None, include=['*/hallucination_guard/evaluation.py'], branch=True); cov.start(); suite = unittest.defaultTestLoader.discover('tests', pattern='test_evaluation.py'); result = unittest.TextTestRunner(verbosity=1).run(suite); cov.stop(); cov.report(show_missing=True); raise SystemExit(not result.wasSuccessful())"
```

实际结果：23 个测试通过；`evaluation.py` 60 条语句、30 个分支，未覆盖语句 0、部分覆盖分支 0，总覆盖率 **100%**。

## 指标边界

- `false_positive_rate = FP / (FP + TN)`，`false_negative_rate = FN / (FN + TP)`。
- `f1 = 2TP / (2TP + FP + FN)`。没有任何预测阳性、人工阳性时 F1 未定义，返回 `None`；存在 FP/FN 且 TP 为零时 F1 为 0。
- `type_match_rate` 的分母是全部人工阳性样本，包括漏检；分子是检测阳性且预测类型集合包含映射后人工主类型的样本数。
- 人工标注是单标签而检测结果支持多标签。因此该类型指标只衡量人工主类型覆盖，不惩罚额外类型，**不能当作多标签准确率**。
- 本记录证明评估逻辑及其边界正确，不证明检测器具备相同的检出率或泛化能力。完整批处理与报告生成由集成测试另行验证。
