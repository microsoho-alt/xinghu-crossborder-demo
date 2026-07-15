import unittest

import app


class DecisionExperienceTests(unittest.TestCase):
    def test_v2_cockpit_view_requires_top_three_and_plain_language_decision(self):
        report = app.normalize_decision_report(app.sample_v2_report())
        self.assertEqual(report["decisionCockpit"]["label"], "满足条件后验证")
        self.assertEqual(len(report["opportunities"]), 3)
        self.assertEqual(len(report["blockingRisks"]), 3)
        self.assertEqual(len(report["actions"]), 3)
        self.assertEqual(len(report["decisionModules"]), 12)

    def test_v1_reload_has_an_explicit_compatibility_cockpit(self):
        legacy = {"schemaVersion": "fused-diagnosis-report-v1", "executionSummary": {"totalScore": 71, "conclusion": "谨慎测试"}, "confidence": {"overall": 0.5}, "missingEvidence": ["需求证据"]}
        normalized = app.normalize_decision_report(legacy)
        self.assertEqual(normalized["sourceSchemaVersion"], "fused-diagnosis-report-v1")
        self.assertEqual(normalized["decisionCockpit"]["label"], "满足条件后验证")
        self.assertIn("历史报告", normalized["decisionCockpit"]["reason"])

    def test_user_scenario_payload_does_not_mutate_authoritative_baseline(self):
        baseline = {"retailPriceUsd": 9.99, "estimatedLogisticsCny": 18, "platformCommissionRate": 0.15}
        scenario = app.build_scenario_payload("降本方案", baseline, retail_price_usd=12.99, logistics_cny=10, commission_rate=0.12, ad_allowance_cny=6, return_reserve_cny=2, market="东南亚", channel="TikTok Shop")
        self.assertEqual(baseline["retailPriceUsd"], 9.99)
        self.assertEqual(scenario["schemaVersion"], "diagnosis-scenario-v1")
        self.assertEqual(scenario["retailPriceUsd"], 12.99)
        self.assertEqual(scenario["marketAssumption"], "东南亚")

    def test_persisted_v2_profile_restores_v5_context_without_provider_work(self):
        profile = {
            "name": "恢复样品", "category": "工业刀具", "factoryPriceCny": 45, "retailPriceUsd": 28.99,
            "exchangeRate": 7.2, "platformCommissionRate": .08, "estimatedLogisticsCny": 12,
            "weightG": 80, "lengthCm": 12, "widthCm": 3, "heightCm": 3, "customerType": "工厂客户",
            "businessGoal": "找订单", "material": "钨钢", "description": "恢复用确定性产品档案",
            "hasBattery": False, "hasMagnet": False, "isLiquidOrPowder": False, "isFragile": True,
            "certifications": [],
        }
        self.assertTrue(app.restore_local_v5_context({"productProfile": profile}))


if __name__ == "__main__":
    unittest.main()
