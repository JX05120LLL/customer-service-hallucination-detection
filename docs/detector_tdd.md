# 检测器开发与验证证据

本模块的用户旅程：审核人员输入客服回复与知识库，获得可定位的风险片段和判断依据；正确拒绝、保留不确定性、正确参数和合法信息子集不应仅因关键词被标记。测试样本在开发中独立编写，包含新 ID 和不同数值，不读取人工评估标签。

## RED → GREEN

1. 先创建 `tests/test_detector.py`，再执行：

   ```powershell
   python -m unittest discover -s tests -p test_detector.py -v
   ```

   真实 RED 输出摘录：

   ```text
   ModuleNotFoundError: No module named 'hallucination_guard.detector'
   Ran 1 test in 0.000s
   FAILED (errors=1)
   ```

   这是新增检测器尚未实现造成的导入失败；当时测试模块未能加载，不能称为 29 个业务测试已逐个执行失败。

2. 实现 `detect_reply`、`detect_replies` 后运行同一命令：

   ```text
   Ran 29 tests in 0.010s
   OK
   ```

3. 使用 Python 标准库 `trace` 执行同一批测试并统计检测器可执行源码行：

   ```powershell
   python -c "import trace, unittest; from hallucination_guard import detector; suite=unittest.defaultTestLoader.discover('tests',pattern='test_detector.py'); tracer=trace.Trace(count=True,trace=False); result=tracer.runfunc(unittest.TextTestRunner().run,suite); path=detector.__file__; executable=set(trace._find_executable_linenos(path)); covered={line for (filename,line),count in tracer.results().counts.items() if filename==path and count}; print('detector.py line coverage: %d/%d = %.2f%%' % (len(executable & covered),len(executable),100*len(executable & covered)/len(executable))); raise SystemExit(not result.wasSuccessful())"
   ```

   首次输出：`Ran 29 tests in 0.125s`、`OK`、`detector.py line coverage: 137/149 = 91.95%`。

   审查修复后以同一命令复测：`Ran 34 tests in 0.175s`、`OK`、`detector.py line coverage: 157/169 = 92.90%`。这是**行覆盖率**，不是分支覆盖率，也不是泛化准确率。模块在追踪前已导入，因此定义行未计入已执行，结果偏保守。该统计命令使用 `trace` 内部辅助函数，只是开发验证方式，不是项目运行依赖。

   曾尝试的 `python -m trace --count --summary --missing -C output/coverage_detector -m unittest ...` 命令失败，原因是 `trace -m` 表示显示未覆盖行，并不用于执行模块；失败未作为覆盖证据，改用上述实际通过的命令。

本检测模块的开发阶段未创建 Git 提交；随后由主流程按用户要求将完整交付发布到 GitHub 公开仓库。上文 RED/GREEN 证据记录保留开发时实际执行结果。

## 审查反馈的两轮真实回归

仍使用上面的 `unittest discover` 命令，先补充测试、运行出实际失败，再修正业务逻辑。

| 轮次 | RED 实际输出 | 修复内容 | GREEN 实际输出 |
| --- | --- | --- | --- |
| 第一轮 | `Ran 31 tests in 0.015s`；`FAILED (failures=3)` | 发货/到货/快递统一为履约政策；“经医生确认后”及“在医生指导下”保留前提时不再误报；完整说明偏码反馈的尺码建议不再被判为遗漏 | `Ran 31 tests in 0.010s`；`OK` |
| 第二轮 | `Ran 34 tests in 0.015s`；`FAILED (failures=3)` | 缺少物流接口不等于不能查产品参数；“蓝牙5.4可能更稳定”中“可能”只限定稳定性；“不是人造革而是头层牛皮”按转折后的肯定声明判断 | `Ran 34 tests in 0.013s`；`OK` |

这些测试还验证反例：“不需要咨询医生”不能解除风险；“没有用户反馈偏大”不能视为保留偏码反馈；“蓝牙5.4尚未确认”保留不确定性；“不是真皮而是PU”不应触发真皮错误。

## 测试保障范围

| 行为 | 测试 | 结果 |
| --- | --- | --- |
| 无理由退货数字不与质量问题期限混用 | return period tests | PASS |
| 运费、发票、优惠组合与知识库一致性 | freight / invoice / coupon tests | PASS |
| 蓝牙、延迟、材质、保修期限和接口主体核验 | spec / warranty / connector tests | PASS |
| 缺少接口时不接受已查询、已修改、已升级声明 | missing interfaces test | PASS |
| 缺少接口必须与已执行动作的业务域一致 | unavailable interface domain test | PASS |
| 拒绝服务、尚未查询、合理不确定回复不触发肯定声明规则 | refusal and uncertainty tests | PASS |
| 参数之后对优点的推测不掩盖已断言参数，转折后的声明独立核验 | uncertainty scope / contrast tests | PASS |
| 不把知识库未标注当成肯定支持 | unknown feature / affiliation tests | PASS |
| 关键人群限制和偏码反馈不得被无条件保证抹除 | health / sizing tests | PASS |
| 正确保留医生前提或偏码反馈的回复不因前句保证而误报 | preserved condition / qualification tests | PASS |
| 正确支付方式子集和有知识库支持的实拍声明通过 | payment / supported photo tests | PASS |
| 每个证据与引用都可在对应输入原文中定位 | assert_detected helper | PASS |
| 改 ID 不改结论、输入不被修改、空批次与非法输入 | batch / invalid input / ID tests | PASS |

## 可解释性与已知局限

- 决策代码只处理传入字典，不读文件、不调用网络、不访问人工标签，不根据 ID 分支；`id` 仅用于输出与重复记录校验。
- 规则先按中文标点和“而是 / 但是 / 不过”切分声明，再核对参数、限定条件和明确能力限制；同一回复可触发多个风险。缺少接口的结论须绑定对应业务域，只有省略宾语的已执行声明才借用问题上下文补全。
- 对未支持断言采取较严格口径。例如“所有图片实物拍摄”即使与色差提示兼容，也需要独立证据；该类风险设 `review_required=true`，不宣称断言已被证明为假。
- 对未命中规则的回复也设 `review_required=true`，并显示“未检出不等于验证真实”。检测器覆盖的是已实现的领域模式，不能认证任意句子的真实性。
- 否定与不确定性通过命中前缀和命中内容识别，并识别“尚未确认”等后置限制；复杂转折、引用、双重否定、跨句指代、未支持的同义改写仍可能漏报或误报。不会因为某一规则命中就证明其余声明正确。
- 保修期限支持阿拉伯数字与常见单字中文数字；复杂中文数词、隐含单位、区间同义表达尚未完整覆盖。
- 支付子集可以通过，但目前没有全面实现所有支付方式和所有产品属性的抽取核验；规则库外属性应人工复核。
- 当前输入只含知识库，没有工具执行日志；涉及账户发券等操作声明只能查验其是否获输入证据支持。
- 行覆盖验证不能代替实际业务泛化评估。样本只有 20 条且规则参考了该输入的领域，最终指标是固定样本演示结果，不是盲测或生产验收。
