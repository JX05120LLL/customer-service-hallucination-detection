"""Behavior tests use invented cases, independent of evaluation labels."""
import copy
import unittest

from hallucination_guard.detector import detect_reply, detect_replies


def sample(reply, kb, question="请介绍一下", record_id="unseen-901"):
    return {"id": record_id, "user_question": question,
            "system_reply": reply, "knowledge_base": kb}


class DetectorTests(unittest.TestCase):
    def assert_detected(self, reply, kb, category, **kwargs):
        item = sample(reply, kb, **kwargs)
        result = detect_reply(item)
        self.assertTrue(result["is_hallucination"], result)
        self.assertIn(category, result["types"])
        for finding in result["findings"]:
            self.assertIn(finding["evidence"], reply)
            self.assertIn(finding["reference"], kb)
            self.assertTrue(finding["reason"])
            self.assertTrue(finding["rule_id"])
        return result

    def assert_clear(self, reply, kb, **kwargs):
        result = detect_reply(sample(reply, kb, **kwargs))
        self.assertFalse(result["is_hallucination"], result)
        return result

    def test_return_period_is_bound_to_reason_not_any_number(self):
        self.assert_detected("支持45天无理由退货。", "普通商品支持10天无理由退货，质量问题45天内可退换。", "政策与优惠")

    def test_return_period_and_freight_supported(self):
        self.assert_clear("普通商品支持10天无理由退货，非质量问题退货运费由买家承担。", "普通商品支持10天无理由退货，质量问题45天内可退换。非质量问题退货运费由买家承担。")

    def test_freight_responsibility(self):
        self.assert_detected("非质量问题退货运费由我们承担。", "非质量问题退货运费由买家承担。", "政策与优惠")

    def test_bluetooth_and_latency_changed_values(self):
        result = self.assert_detected("采用蓝牙5.4版本，延迟低至25ms。", "产品参数：蓝牙5.2，延迟约60ms。", "产品参数")
        self.assertEqual(len(result["findings"]), 2)

    def test_uncertainty_about_quality_does_not_hide_asserted_version(self):
        self.assert_detected("蓝牙5.4可能更稳定。", "蓝牙5.0。", "产品参数")
        self.assert_clear("可能采用蓝牙5.4，尚待核实。", "蓝牙5.0。")
        self.assert_clear("蓝牙5.4尚未确认。", "蓝牙5.0。")

    def test_contrast_separates_negative_and_positive_claims(self):
        self.assert_detected("不是人造革而是头层牛皮。", "材质：PU合成革。", "产品参数")
        self.assert_clear("不是头层牛皮而是PU合成革。", "材质：PU合成革。")

    def test_single_and_multi_device(self):
        self.assert_detected("支持多设备同时连接。", "支持单设备连接。", "产品参数")
        self.assert_clear("只支持单设备连接。", "支持单设备连接。")

    def test_material_and_warranty(self):
        result = self.assert_detected("这款包采用头层牛皮，保修期为三年。", "材质：PU合成革。保修期：8个月。", "产品参数")
        self.assertGreaterEqual(len(result["findings"]), 2)

    def test_warranty_unit_conversion(self):
        self.assert_clear("保修期为一年。", "保修期：12个月。")

    def test_invoice_availability_and_application_channel(self):
        result = self.assert_detected("支持电子发票和纸质发票。下单时在备注里写上抬头即可。", "支持电子发票，下单后在订单详情页申请。暂不支持纸质发票。", "政策与优惠")
        self.assertGreaterEqual(len(result["findings"]), 2)

    def test_invoice_refusal_is_not_positive(self):
        self.assert_clear("目前不支持纸质发票，请在订单详情页申请电子发票。", "支持电子发票，下单后在订单详情页申请。暂不支持纸质发票。")

    def test_coupon_pairs_are_bound_together(self):
        self.assert_detected("当前有满400减80优惠券。", "优惠活动：满400减40、满800减80。", "政策与优惠")
        self.assert_clear("当前有满400减40优惠券。", "优惠活动：满400减40、满800减80。")

    def test_negated_coupon_is_not_valid_support(self):
        self.assert_detected("现在有满600减90优惠券。", "当前无满600减90活动。", "政策与优惠")
        self.assert_clear("目前没有满600减90优惠券。", "当前无满600减90活动。")

    def test_coupon_delivery_without_tool_support(self):
        self.assert_detected("我直接发到您账户里。", "优惠活动：满200减20。", "能力越界")

    def test_three_missing_interfaces_and_ticket_capability(self):
        for reply, kb in [
            ("我帮您查了，您的包裹目前在武汉转运中心。", "客服系统未接入物流查询接口。"),
            ("退款已经在处理中，预计明天到账。", "客服系统未接入退款进度查询接口。"),
            ("已帮您修改为新地址：武汉市江岸区。", "客服系统未接入订单修改接口，需人工操作。"),
            ("已经将投诉升级为高级工单。", "系统不具备工单升级功能，需转人工处理。"),
        ]:
            with self.subTest(reply=reply):
                self.assert_detected(reply, kb, "能力越界")

    def test_capability_refusal_and_uncertainty(self):
        for reply in ["系统无法查询物流，请到订单页查看。", "我不能确认您的包裹目前在哪里。", "我尚未查询退款进度。", "预计可能明天到账，请以支付平台为准。"]:
            with self.subTest(reply=reply):
                self.assert_clear(reply, "客服系统未接入物流查询接口，也未接入退款进度查询接口。")

    def test_unavailable_interface_must_match_action_domain(self):
        kb = "客服系统未接入物流查询接口。产品参数：蓝牙5.0。"
        self.assert_clear("我帮您查了产品参数，采用蓝牙5.0。", kb, question="我的快递到哪了？")
        self.assert_clear("已帮您修改收货地址。", kb)
        self.assert_detected("我帮您查了，预计明天送达。", kb, "能力越界", question="我的快递到哪了？")

    def test_return_address_requires_order_matching(self):
        self.assert_detected("退货请寄到：江苏省南京市中山路12号。", "退货地址需根据订单信息自动匹配后短信发送。人工客服不可口头告知退货地址。", "事实信息")

    def test_shipping_times_and_courier(self):
        result = self.assert_detected("下单后72小时内发货，一般使用顺丰快递，大部分地区1-2天到货。", "下单后36小时内发货。合作快递：中通/韵达，具体以实际分配为准。到货时间：一般4-6天。", "政策与优惠")
        self.assertEqual(len(result["findings"]), 3)

    def test_unknown_feature_requires_review(self):
        result = self.assert_detected("支持NFC功能。", "产品参数中未标注NFC功能。", "产品参数")
        self.assertTrue(result["review_required"])
        self.assert_clear("目前无法确认是否支持NFC，请以官方参数为准。", "产品参数中未标注NFC功能。")

    def test_offline_stores(self):
        self.assert_detected("我们在成都也有线下门店。", "纯线上品牌，无线下门店。", "事实信息")
        self.assert_clear("我们是纯线上品牌，没有线下门店。", "纯线上品牌，无线下门店。")

    def test_payment_subset_is_valid(self):
        self.assert_clear("不支持货到付款，支持微信、支付宝和银行卡在线支付。", "支付方式：微信支付、支付宝、银行卡、花呗、信用卡。不支持货到付款。")

    def test_health_assurance_must_keep_constraint(self):
        result = self.assert_detected("孕妇可以放心使用。", "孕妇及哺乳期女性建议咨询医生后使用。", "安全误导")
        self.assertEqual(result["severity"], "高")
        self.assert_clear("孕妇建议咨询医生后使用，不能保证所有人都适用。", "孕妇及哺乳期女性建议咨询医生后使用。")

    def test_health_assurance_condition_is_preserved(self):
        kb = "孕妇及哺乳期女性建议咨询医生后使用。"
        self.assert_clear("经医生确认后孕妇可以放心使用。", kb)
        self.assert_clear("在医生指导下，孕妇可以放心使用。", kb)
        self.assert_detected("不需要咨询医生，孕妇可以放心使用。", kb, "安全误导")

    def test_brand_affiliation_unknown(self):
        self.assert_detected("我们是某品牌旗下的子品牌。", "品牌介绍中未提及其他品牌关联关系。", "事实信息")
        self.assert_clear("目前不能确认是否为某品牌旗下的子品牌。", "品牌介绍中未提及其他品牌关联关系。")

    def test_photo_claim_strictly_requires_support(self):
        self.assert_detected("商品图片都是实物拍摄的，可能有轻微色差。", "图片因拍摄光线、显示器等原因可能有轻微色差。", "事实信息")
        self.assert_clear("商品图片都是实物拍摄的，可能有轻微色差。", "图片均为实物拍摄，因光线可能有轻微色差。")

    def test_connector_is_bound_to_charger_not_cable(self):
        kb = "接口类型：USB-A输出。附带一根USB-A to Type-C充电线。"
        self.assert_detected("这款充电头是Type-C接口。", kb, "产品参数")
        self.assert_clear("这款充电头是USB-A接口，附带USB-A to Type-C充电线。", kb)

    def test_student_discount(self):
        self.assert_detected("凭学生证可以享受8折优惠。", "当前无学生优惠政策。", "政策与优惠")
        self.assert_clear("目前没有学生优惠。", "当前无学生优惠政策。")

    def test_size_advice_should_not_erase_relevant_feedback(self):
        kb = "约40%的用户反馈偏大半码，建议脚瘦的用户选小半码。"
        self.assert_detected("这款鞋尺码标准，不偏大也不偏小。按照您平时穿的尺码选就可以了。", kb, "误导性遗漏")
        self.assert_clear("部分用户反馈偏大半码，脚瘦建议选小半码。", kb)

    def test_size_advice_keeps_qualification(self):
        kb = "约40%的用户反馈偏大半码，建议脚瘦的用户选小半码。"
        self.assert_clear("尺码标准，但约40%的用户反馈偏大半码，脚瘦建议选小半码。", kb)
        self.assert_detected("尺码标准，没有用户反馈偏大半码，脚瘦也按平时尺码选。", kb, "误导性遗漏")

    def test_unknown_claim_is_not_certified_true(self):
        result = self.assert_clear("这颗石头来自月球。", "石头颜色：黑色。")
        self.assertTrue(result["review_required"])
        self.assertIn("未检出不等于验证真实", result["summary"])

    def test_id_change_does_not_change_decision(self):
        item = sample("采用蓝牙5.4。", "蓝牙5.0。", record_id="first")
        first = detect_reply(item)
        item["id"] = "unrelated-id"
        second = detect_reply(item)
        first.pop("id")
        second.pop("id")
        self.assertEqual(first, second)

    def test_batch_preserves_inputs_and_order(self):
        items = [sample("采用蓝牙5.4。", "蓝牙5.0。", record_id="a"), sample("微信支付。", "支持微信支付。", record_id="b")]
        before = copy.deepcopy(items)
        results = detect_replies(items)
        self.assertEqual(items, before)
        self.assertEqual([r["id"] for r in results], ["a", "b"])
        self.assertNotIn("system_reply", results[0])
        self.assertEqual(detect_replies([]), [])

    def test_invalid_input_is_rejected(self):
        for item in [None, {}, sample("", "知识库"), sample("回复", None), sample("回复", "知识库", record_id=12)]:
            with self.subTest(item=item), self.assertRaises(ValueError):
                detect_reply(item)
        with self.assertRaises(ValueError):
            detect_replies("not a list")
        with self.assertRaises(ValueError):
            detect_replies([sample("回复", "知识库"), sample("回复", "知识库")])


if __name__ == "__main__":
    unittest.main()
