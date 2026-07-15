import unittest

import app


def product_from_sample(sample: dict) -> app.ProductInput:
    return app.ProductInput(
        name=sample["name"],
        category=sample["category"],
        factory_price_cny=float(sample["factory_price_cny"]),
        retail_price_usd=float(sample["retail_price_usd"]),
        exchange_rate=float(sample["exchange_rate"]),
        platform_commission_rate=float(sample["platform_commission_rate"]),
        estimated_logistics_cny=float(sample["estimated_logistics_cny"]),
        weight_g=float(sample["weight_g"]),
        length_cm=float(sample["length_cm"]),
        width_cm=float(sample["width_cm"]),
        height_cm=float(sample["height_cm"]),
        material=sample["material"],
        has_battery=sample["has_battery"],
        has_magnet=sample["has_magnet"],
        is_liquid_or_powder=sample["is_liquid_or_powder"],
        is_fragile=sample["is_fragile"],
        certifications=sample["certifications"],
        customer_type=sample["customer_type"],
        business_goal=sample["business_goal"],
        product_description=sample["product_description"],
    )


GOLDEN = {
    "案例1：C端红海消费品｜车载手机支架": {
        "scores": {"市场需求适配度": 12, "平台销售适配度": 11, "利润空间适配度": 16, "物流履约适配度": 15, "合规风险可控度": 6, "内容传播适配度": 9, "竞争强度修正值": 2},
        "platform_scores": {"Amazon": 50, "AliExpress": 75, "TikTok Shop": 68, "独立站": 57, "B2B平台": 25},
        "total": 71,
        "level": "谨慎测试，先做小样本验证",
        "platforms": ["AliExpress", "TikTok Shop", "独立站"],
        "markets": ["欧洲", "拉美", "中东", "东南亚", "美国"],
        "finance": [71.93, 10.79, 25.14, 0.35, 0.2],
        "tasks": ["合规核查", "竞争破局", "平台测试", "Listing冷启动", "素材标准化", "小预算验证", "数据回流"],
    },
    "案例2：B端工业品｜硬质合金铣刀": {
        "scores": {"市场需求适配度": 15, "平台销售适配度": 12, "利润空间适配度": 20, "物流履约适配度": 13, "合规风险可控度": 6, "内容传播适配度": 5, "竞争强度修正值": 5},
        "platform_scores": {"Amazon": 65, "AliExpress": 75, "TikTok Shop": 56, "独立站": 65, "B2B平台": 78},
        "total": 76,
        "level": "适合测试，但需优化资料",
        "platforms": ["B2B平台", "AliExpress", "Amazon"],
        "markets": ["美国", "欧洲", "拉美", "中东"],
        "finance": [208.73, 16.7, 135.03, 0.647, 0.08],
        "tasks": ["合规核查", "内容补强", "平台测试", "Listing冷启动", "素材标准化", "小预算验证", "数据回流"],
    },
    "案例3：带电小家电｜便携式迷你吸尘器": {
        "scores": {"市场需求适配度": 12, "平台销售适配度": 11, "利润空间适配度": 16, "物流履约适配度": 10, "合规风险可控度": 5, "内容传播适配度": 9, "竞争强度修正值": 5},
        "platform_scores": {"Amazon": 60, "AliExpress": 65, "TikTok Shop": 62, "独立站": 75, "B2B平台": 25},
        "total": 68,
        "level": "谨慎测试，先做小样本验证",
        "platforms": ["独立站", "AliExpress", "TikTok Shop"],
        "markets": ["欧洲", "拉美", "中东", "东南亚", "美国", "优先选择物流和清关路径成熟的市场"],
        "finance": [215.93, 32.39, 77.54, 0.359, 0.85],
        "tasks": ["合规核查", "物流验证", "平台测试", "Listing冷启动", "素材标准化", "小预算验证", "数据回流"],
    },
}


class V5GoldenParityTests(unittest.TestCase):
    def test_all_authoritative_samples_and_outputs_are_preserved(self):
        self.assertEqual(list(app.SAMPLE_CASES), list(GOLDEN))
        for case_name, expected in GOLDEN.items():
            product = product_from_sample(app.SAMPLE_CASES[case_name])
            report = app.evaluate_product(product)
            vector = report["vector"]
            self.assertEqual(report["scores"], expected["scores"], case_name)
            self.assertEqual({name: value["匹配分"] for name, value in report["platform_match"].items()}, expected["platform_scores"], case_name)
            self.assertEqual(report["total_score"], expected["total"], case_name)
            self.assertEqual(report["level"], expected["level"], case_name)
            self.assertEqual(report["platforms"], expected["platforms"], case_name)
            self.assertEqual(report["markets"], expected["markets"], case_name)
            self.assertEqual(
                [vector["海外零售价人民币口径"], vector["估算平台佣金"], vector["估算单件利润"], vector["扣费后利润率"], vector["计费重量kg"]],
                expected["finance"],
                case_name,
            )
            self.assertEqual([task["模块"] for task in report["tasks"]], expected["tasks"], case_name)

    def test_export_keeps_every_v5_delivery_section(self):
        product = product_from_sample(next(iter(app.SAMPLE_CASES.values())))
        markdown = app.generate_markdown_report(product, app.evaluate_product(product))
        for title in [
            "一、执行摘要", "二、产品基础画像", "三、经营测算模型", "四、七维评分矩阵",
            "五、平台适配与渠道建议", "六、风险提示与补强方向", "七、OPC运营任务拆解",
            "八、7天小样本验证路径", "九、数据回流字段", "十、技术链路",
        ]:
            self.assertIn(title, markdown)

    def test_manual_input_contract_keeps_every_v5_field(self):
        self.assertEqual(
            list(app.ProductInput.__dataclass_fields__),
            ["name", "category", "factory_price_cny", "retail_price_usd", "exchange_rate", "platform_commission_rate", "estimated_logistics_cny", "weight_g", "length_cm", "width_cm", "height_cm", "material", "has_battery", "has_magnet", "is_liquid_or_powder", "is_fragile", "certifications", "customer_type", "business_goal", "product_description"],
        )


if __name__ == "__main__":
    unittest.main()
