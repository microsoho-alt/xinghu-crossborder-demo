import json
import unittest

from diagnosis_client import DiagnosisApiClient, DiagnosisApiError, ImageAsset


class FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body or {"data": {}}

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, responses=None):
        self.responses = list(responses or [FakeResponse()])
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


class DiagnosisClientTests(unittest.TestCase):
    def test_images_are_encoded_and_secrets_stay_in_headers(self):
        session = FakeSession([FakeResponse(201, {"data": {"draftId": "id", "accessToken": "access", "suggestions": {}}})])
        client = DiagnosisApiClient("http://127.0.0.1:9999", "a" * 24, session)
        client.extract("idem-12345678", [ImageAsset("产品.png", "image/png", b"image-bytes")], "context")
        method, url, request = session.calls[0]
        self.assertEqual(method, "POST")
        self.assertNotIn("a" * 24, url)
        self.assertEqual(request["headers"]["Authorization"], f"Bearer {'a' * 24}")
        self.assertEqual(request["headers"]["Idempotency-Key"], "idem-12345678")
        self.assertEqual(request["json"]["images"][0]["base64"], "aW1hZ2UtYnl0ZXM=")

    def test_result_reload_is_get_only_and_never_submits_models(self):
        session = FakeSession([FakeResponse(200, {"data": {"report": {"snapshot": True}}})])
        client = DiagnosisApiClient("http://127.0.0.1:9999", "a" * 24, session)
        client.result("diagnosis-id", "opaque-access")
        method, url, request = session.calls[0]
        self.assertEqual((method, url), ("GET", "http://127.0.0.1:9999/api/diagnoses/diagnosis-id/result"))
        self.assertIsNone(request["json"])
        self.assertEqual(request["headers"]["X-Diagnosis-Access-Token"], "opaque-access")

    def test_api_errors_are_bounded(self):
        session = FakeSession([FakeResponse(500, {"error": {"message": "x" * 1000, "raw": "secret"}})])
        client = DiagnosisApiClient("http://127.0.0.1:9999", "a" * 24, session)
        with self.assertRaisesRegex(DiagnosisApiError, "融合诊断请求未完成"):
            client.status("id", "access")


if __name__ == "__main__":
    unittest.main()

