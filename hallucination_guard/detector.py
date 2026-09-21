"""Small, deterministic Chinese customer-service evidence checker.

Rules compare claims with the supplied knowledge base; no labels, sample IDs,
files, network requests, or external model responses participate in decisions.
This is a domain-specific baseline, not a general semantic entailment model.
"""
import re

VERSION = "rules-v1"
_SEVERITY = {"无": 0, "低": 1, "中": 2, "高": 3}
_UNCERTAIN = re.compile(
    r"不确定|无法确认|不能确认|未确认|未标注|未提及|需核实|待核实|请核实|未知|"
    r"尚未|未查询|不能保证|不保证|不一定|可能|不支持|暂不|没有|并非|不是|"
    r"无法|不能|不具备|未接入|不提供|不享受|不可以|暂无|无满"
)


def _clauses(text):
    """Keep exact substrings so every finding can be located in its source."""
    return [part.strip() for part in re.split(r"[，,。！？；;\n]|而是|但是|不过", text) if part.strip()]


def _find(text, pattern, affirmative=False):
    for clause in _clauses(text):
        match = re.search(pattern, clause, re.I)
        if match:
            # A qualification about subsequent benefits does not qualify the
            # already asserted value (e.g. "蓝牙5.4可能更稳定").
            negated = _UNCERTAIN.search(clause[:match.end()])
            pending = re.match(r"\s*(?:尚未确认|未确认|尚未核实|待确认|待核实|不确定)", clause[match.end():])
            if not affirmative or not (negated or pending):
                return clause
    return None


def _warranty_months(value, unit):
    chinese = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
               "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    number = int(value) if value.isdigit() else chinese.get(value)
    return None if number is None else number * (12 if unit == "年" else 1)


def detect_reply(item: dict) -> dict:
    """Return explainable risks; an unflagged answer is not a truth certificate."""
    required = ("id", "user_question", "system_reply", "knowledge_base")
    if not isinstance(item, dict) or any(
        not isinstance(item.get(key), str) or not item[key].strip() for key in required
    ):
        raise ValueError("每条记录必须包含非空字符串 id/user_question/system_reply/knowledge_base")

    reply, kb = item["system_reply"], item["knowledge_base"]
    findings = []
    uncertain_evidence = False

    def add(rule_id, category, severity, evidence, reference, reason, unsupported=False):
        nonlocal uncertain_evidence
        if evidence and reference:
            findings.append({"type": category, "severity": severity,
                             "evidence": evidence, "reference": reference,
                             "reason": reason, "rule_id": rule_id})
            uncertain_evidence = uncertain_evidence or unsupported

    def compare(rule_id, field, pattern, category, severity="中"):
        evidence = _find(reply, pattern, affirmative=True)
        reference = _find(kb, pattern, affirmative=True)
        if evidence and reference:
            actual = re.search(pattern, evidence, re.I).group(1)
            expected = re.search(pattern, reference, re.I).group(1)
            if actual.replace(" ", "").lower() != expected.replace(" ", "").lower():
                add(rule_id, category, severity, evidence, reference,
                    f"{field}不一致：回复为 {actual}，知识库为 {expected}。")

    compare("return.days", "无理由退货期限", r"(\d+)天(?:内)?无理由退货", "政策与优惠", "高")
    add("return.scope", "政策与优惠", "高",
        _find(reply, r"(?:全品类|所有商品|全部商品).{0,10}(?:无理由|退货)", True),
        _find(kb, r"普通商品.{0,10}无理由退货"), "将限定商品的退货政策扩展到全部商品。")
    add("return.freight", "政策与优惠", "高",
        _find(reply, r"(?:运费.{0,8}(?:我们|卖家|商家).{0,4}承担|包退货运费)", True),
        _find(kb, r"非质量问题.{0,12}买家承担"), "知识库规定非质量退货运费由买家承担，回复改为商家承担。")

    compare("spec.bluetooth", "蓝牙版本", r"蓝牙\s*(\d+(?:\.\d+)?)", "产品参数")
    compare("spec.latency", "延迟(ms)", r"延迟[^\d，。]{0,6}(\d+)\s*ms", "产品参数")
    add("spec.connection", "产品参数", "中", _find(reply, r"多设备.{0,6}连接", True),
        _find(kb, r"单设备连接"), "将单设备连接描述成多设备同时连接。")
    add("spec.material", "产品参数", "高", _find(reply, r"头层牛皮|真皮|天然皮革", True),
        _find(kb, r"PU|合成革|人造革"), "将合成材料描述为天然皮革，可能影响购买决策。")
    warranty = r"保修期[：:为是]*\s*([一二两三四五六七八九十\d]+)\s*(年|个月|月)"
    warranty_claim = _find(reply, warranty, True)
    warranty_reference = _find(kb, warranty, True)
    if warranty_claim and warranty_reference:
        actual = _warranty_months(*re.search(warranty, warranty_claim).groups())
        expected = _warranty_months(*re.search(warranty, warranty_reference).groups())
        if actual is not None and expected is not None and actual != expected:
            add("policy.warranty", "政策与优惠", "中", warranty_claim, warranty_reference,
                f"保修期限不一致：回复折合 {actual} 个月，知识库为 {expected} 个月。")

    add("invoice.paper", "政策与优惠", "中", _find(reply, r"支持.{0,12}纸质发票", True),
        _find(kb, r"(?:不支持|无).{0,4}纸质发票"), "回复提供了知识库明确不支持的纸质发票。")
    add("invoice.channel", "政策与优惠", "中", _find(reply, r"备注.{0,12}(?:抬头|税号)", True),
        _find(kb, r"订单详情页申请"), "发票申请入口与知识库不一致，备注不等于提交申请。")

    coupon_pattern = r"满\s*(\d+)\s*减\s*(\d+)"
    supported_coupons = set()
    for clause in _clauses(kb):
        if not _UNCERTAIN.search(clause) and not re.search(r"(?:无|取消|已结束).{0,4}满", clause):
            supported_coupons.update(re.findall(coupon_pattern, clause))
    if re.search(r"优惠|活动|满\d+减", kb):
        for clause in _clauses(reply):
            if _UNCERTAIN.search(clause):
                continue
            for minimum, reduction in re.findall(coupon_pattern, clause):
                if (minimum, reduction) not in supported_coupons:
                    add("policy.coupon", "政策与优惠", "高", clause,
                        _find(kb, r"优惠|活动|满\d+减"),
                        f"未找到满{minimum}减{reduction}这一完整优惠组合的有效依据。", True)
    add("capability.coupon", "能力越界", "高", _find(reply, r"(?:我|已).{0,8}发到.{0,5}账户", True),
        kb if not re.search(r"(?:支持|可).{0,6}(?:发券|发放优惠券|发到.*账户)", kb) else None,
        "宣称给账户发放优惠券，但输入知识库没有该操作能力或执行结果。", True)

    capability_rules = (
        (r"未接入.{0,4}物流.*接口", r"物流|快递|包裹|送达|转运|到货",
         r"我帮.{0,5}查|已.{0,8}查询|目前在|预计.{0,8}(?:送达|到货)"),
        (r"未接入.{0,4}退款.*接口", r"退款|到账",
         r"我帮.{0,5}查|已.{0,8}(?:查询|处理)|在处理中|预计.{0,8}到账"),
        (r"未接入.{0,4}订单修改.*接口", r"订单|地址",
         r"已.{0,10}修改|修改成功"),
        (r"不具备.{0,6}工单升级.*功能", r"投诉|工单",
         r"已.{0,12}升级|升级成功"),
    )
    for missing, topic, action in capability_rules:
        no_interface = _find(kb, missing)
        if not no_interface:
            continue
        for clause in _clauses(reply):
            asserted_action = _find(clause, action, True)
            if not asserted_action:
                continue
            # Only borrow the question's topic for an omitted object; an
            # explicit different object ("查了产品参数") must not inherit it.
            omitted_object = re.search(r"(?:查(?:了一下|了)?|(?:修改|升级)(?:了)?)$", clause)
            bound = re.search(topic, clause) or (omitted_object and re.search(topic, reply + item["user_question"]))
            if bound:
                add("capability.unavailable", "能力越界", "高", asserted_action, no_interface,
                    "知识库明确系统没有该业务接口或功能，回复却声称已查询、已执行或给出个人业务状态。")
                break

    add("fact.return_address", "事实信息", "高", _find(reply, r"(?:寄到|寄往|退货地址[是为：:]).{3,}", True),
        _find(kb, r"不可口头告知退货地址|自动匹配.*短信"),
        "退货地址须依据订单匹配，回复直接给出未经匹配验证的具体地址。")
    compare("fact.dispatch", "发货承诺(小时)", r"(\d+)小时内发货", "政策与优惠")
    compare("fact.delivery", "到货时间范围(天)", r"(\d+\s*[-~至]\s*\d+)天", "政策与优惠")
    courier_names = r"顺丰|中通|韵达|圆通|申通|极兔|京东|邮政|EMS"
    courier_reference = _find(kb, r"合作快递|配送快递|承运商")
    if courier_reference:
        approved = set(re.findall(courier_names, courier_reference, re.I))
        for clause in _clauses(reply):
            names = set(re.findall(courier_names, clause, re.I))
            if names - approved and not _UNCERTAIN.search(clause):
                add("fact.courier", "政策与优惠", "中", clause, courier_reference,
                    "回复指定了知识库合作快递清单之外的承运商。")

    add("spec.unknown_nfc", "产品参数", "中", _find(reply, r"支持.{0,6}NFC|具备.{0,6}NFC", True),
        _find(kb, r"未标注.{0,6}NFC|未提及.{0,6}NFC"),
        "知识库未确认 NFC 功能，回复却肯定支持；这是缺乏支持，不代表已证实不支持。", True)
    add("fact.offline_store", "事实信息", "中", _find(reply, r"有.{0,8}线下(?:门店|体验店)|到店试穿", True),
        _find(kb, r"无线下门店|没有线下门店"), "知识库明确无线下门店，回复却给出门店或到店服务。")

    medical_constraint = _find(kb, r"孕妇.*咨询医生|哺乳期.*咨询医生")
    health_assurance = _find(reply, r"孕妇.{0,8}(?:放心|可以使用|可以用|能用)|放心使用", True)
    if medical_constraint and health_assurance:
        context = next(sentence for sentence in re.split(r"[。！？；;\n]", reply) if health_assurance in sentence)
        condition = _find(context, r"咨询医生后|医生(?:确认|评估|同意)后|医生指导下", True)
        if not condition or re.search(r"无需|不用|不必|不需要|不经", condition):
            add("safety.pregnancy", "安全误导", "高", health_assurance, medical_constraint,
                "知识库要求特殊人群咨询医生，回复给出无条件安全保证；本规则只核对该限定，不作医学判断。")
    add("fact.social_proof", "事实信息", "中", _find(reply, r"很多孕妈.{0,8}回购", True),
        kb if "回购" not in kb else None, "提供了知识库没有支持的具体人群回购事实。", True)
    add("fact.brand_affiliation", "事实信息", "中", _find(reply, r"旗下|子品牌|共享.{0,8}供应链", True),
        _find(kb, r"未提及.{0,10}品牌关联|未确认.{0,10}品牌关联"),
        "品牌关联关系未得到知识库支持，不能据此肯定存在隶属关系。", True)
    add("fact.real_photos", "事实信息", "中", _find(reply, r"(?:都是|均为|全部|均是)?实物拍摄", True),
        kb if "图片" in kb and "实物拍摄" not in kb else None,
        "知识库只说明图片可能有色差，没有证明所有图片均为实物拍摄；按严格事实核验标记待复核。", True)

    connector_reference = _find(kb, r"(?:接口类型|输出接口)[：:为是]*\s*(?:USB-A|Type-C|USB-C)")
    connector_claim = _find(reply, r"(?:充电头|充电器|输出接口|接口类型|接口[是为]).{0,12}(?:USB-A|Type-C|USB-C)", True)
    if connector_reference and connector_claim:
        actual = re.search(r"USB-A|Type-C|USB-C", connector_claim, re.I).group().lower().replace("usb-c", "type-c")
        expected = re.search(r"USB-A|Type-C|USB-C", connector_reference, re.I).group().lower().replace("usb-c", "type-c")
        if actual != expected:
            add("spec.connector", "产品参数", "中", connector_claim, connector_reference,
                "充电头输出接口与知识库不一致；附赠线缆的另一端接口不等于充电头接口。")

    add("policy.student", "政策与优惠", "中", _find(reply, r"学生证.{0,12}(?:折|优惠)|学生认证|有学生优惠", True),
        _find(kb, r"无学生优惠|不支持学生优惠"), "回复承诺了知识库明确不存在的学生优惠。")
    size_reference = _find(kb, r"用户.{0,6}反馈偏[大小]|建议.{0,8}选[大小]半码")
    direction = re.search(r"偏[大小]", kb)
    preserved_feedback = direction and _find(reply, r"(?:用户|反馈|部分).{0,10}" + direction.group(), True)
    if not preserved_feedback:
        add("omission.sizing", "误导性遗漏", "中", _find(reply, r"不偏大也不偏小|尺码标准|按照.{0,8}平时穿的尺码", True),
            size_reference, "知识库存在与选码有关的偏码反馈，回复用无条件标准尺码建议抹去该限制。")

    types = list(dict.fromkeys(finding["type"] for finding in findings))
    severity = max((finding["severity"] for finding in findings), key=_SEVERITY.get, default="无")
    return {"id": item["id"], "is_hallucination": bool(findings), "types": types,
            "severity": severity, "findings": findings,
            "review_required": uncertain_evidence or not findings,
            "summary": f"检出 {len(findings)} 处风险，建议按证据复核。" if findings else "未命中已实现规则；未检出不等于验证真实，建议人工抽检。",
            "detector_version": VERSION}


def detect_replies(records: list) -> list:
    """Process a batch without mutating inputs and reject ambiguous duplicate IDs."""
    if not isinstance(records, list):
        raise ValueError("records 必须是列表")
    results = [detect_reply(record) for record in records]
    if len({result["id"] for result in results}) != len(results):
        raise ValueError("记录 id 不可重复")
    return results
