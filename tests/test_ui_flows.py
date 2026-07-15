import base64
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ONE_PIXEL_PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")


class ApiHandler(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *_args):
        return

    def _json(self, status, data):
        body = json.dumps({"data": data}, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("content-length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        self.__class__.calls.append(("POST", self.path, payload, dict(self.headers)))
        if self.path == "/api/diagnoses/extract":
            return self._json(201, {"draftId": "11111111-1111-4111-8111-111111111111", "accessToken": "draft-access", "suggestions": {"schemaVersion": "product-extraction-v1", "suggestions": [{"field": "name", "value": "图片确认产品", "confidence": 0.82, "imageOrdinal": 0, "evidence": "包装正面可见产品名称"}], "missingInformation": ["认证真实性"], "warnings": []}})
        if self.path == "/api/diagnoses":
            return self._json(202, {"diagnosisId": "22222222-2222-4222-8222-222222222222", "accessToken": "report-access", "created": True, "enqueued": True})
        return self._json(201, {"id": "feedback", "createdAt": "2026-07-15T00:00:00Z"})

    def do_GET(self):
        self.__class__.calls.append(("GET", self.path, None, dict(self.headers)))
        if self.path.endswith("/result"):
            return self._json(200, {"diagnosisId": "22222222-2222-4222-8222-222222222222", "reportId": "report", "reportVersion": 1, "contentDigest": "a" * 64, "report": fused_report()})
        return self._json(200, {"diagnosisId": "22222222-2222-4222-8222-222222222222", "status": "SUCCEEDED", "stage": "COMPLETE", "progressPercent": 100, "events": [{"publicMessage": "融合报告已保存", "percent": 100}], "reportId": "report"})


def fused_report():
    claim = {"key": "x", "topic": "机会", "kind": "inference", "statement": "先做小样本验证", "confidence": 0.8, "evidenceRefs": ["rule:v5"], "rationale": "证据约束"}
    return {"schemaVersion": "fused-diagnosis-report-v1", "confidence": {"overall": 0.8, "method": "确定性规则与证据融合"}, "opportunity": [claim], "targetMarkets": [], "channelFit": [], "nextActions": [], "risks": {"red": [], "yellow": []}, "disagreements": [], "missingEvidence": ["认证真实性"], "executionSummary": {}, "productProfile": {}, "financialModel": {}, "sevenDimensionalScores": {}, "platformAnalysis": {}, "opcTasks": [], "sevenDayValidationPath": [], "dataReturnFields": [], "technicalChain": ""}


class UiFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ApiHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        ApiHandler.calls.clear()

    def test_text_sample_keeps_v5_report_and_download(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GRIP_DIAGNOSIS_API_URL", None)
            os.environ.pop("GRIP_DIAGNOSIS_API_TOKEN", None)
            app = AppTest.from_file("app.py", default_timeout=15).run()
            app.selectbox[0].select("案例2：B端工业品｜硬质合金铣刀")
            next(button for button in app.button if button.label == "载入所选样本").click().run()
            next(button for button in app.button if button.label == "生成诊断报告").click().run()
            self.assertFalse(app.exception)
            rendered = "\n".join(str(item.value) for item in app.markdown)
            self.assertIn("产品适配度诊断报告", rendered)
            self.assertIn("执行摘要", rendered)
            self.assertEqual([item.label for item in app.get("download_button")], ["下载完整诊断报告"])

    def test_image_suggestion_confirmation_progress_and_fused_report(self):
        with patch.dict(os.environ, {"GRIP_DIAGNOSIS_API_URL": self.base_url, "GRIP_DIAGNOSIS_API_TOKEN": "test-api-token-1234567890"}):
            app = AppTest.from_file("app.py", default_timeout=15).run()
            app.selectbox[0].select("案例1：C端红海消费品｜车载手机支架")
            next(button for button in app.button if button.label == "载入所选样本").click().run()
            app.get("file_uploader")[0].upload("product.png", ONE_PIXEL_PNG, "image/png").run()
            next(button for button in app.button if button.label == "识别图片并生成待确认建议").click().run()
            suggestion = next(item for item in app.checkbox if item.label.startswith("name → 图片确认产品"))
            suggestion.check().run()
            next(button for button in app.button if button.label == "应用已勾选建议").click().run()
            self.assertEqual(next(item for item in app.text_input if item.label == "产品名称 *").value, "图片确认产品")
            required = {
                "产品类目 *": "汽车用品", "出厂价（人民币）*": "18", "建议海外零售价（美元）*": "9.99",
                "汇率（美元兑人民币）*": "7.2", "平台佣金率 *": "0.15", "估算单件物流费（人民币）*": "18",
                "产品重量（g）*": "200", "包装长度（cm）*": "10", "包装宽度（cm）*": "8", "包装高度（cm）*": "5",
            }
            for label, value in required.items():
                next(item for item in app.text_input if item.label == label).set_value(value)
            next(item for item in app.selectbox if item.label == "目标客户类型 *").select("C端消费者")
            next(item for item in app.selectbox if item.label == "企业诉求 *").select("测品")
            next(button for button in app.button if button.label == "生成诊断报告").click().run()
            self.assertFalse(app.exception)
            rendered = "\n".join(str(item.value) for item in app.markdown)
            self.assertIn("多源融合增量报告", rendered)
            self.assertIn("共识保留，冲突可见，未知不补写", rendered)
            self.assertNotIn("Doubao", rendered)
            self.assertNotIn("DeepSeek", rendered)
            self.assertNotIn("GLM-", rendered)
            paths = [call[1] for call in ApiHandler.calls]
            self.assertIn("/api/diagnoses/extract", paths)
            self.assertIn("/api/diagnoses", paths)
            self.assertIn("/api/diagnoses/22222222-2222-4222-8222-222222222222/result", paths)


if __name__ == "__main__":
    unittest.main()
