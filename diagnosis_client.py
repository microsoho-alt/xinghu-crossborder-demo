import base64
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

import requests


class DiagnosisApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class ImageAsset:
    filename: str
    media_type: str
    content: bytes


class DiagnosisApiClient:
    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None, session=None):
        self.base_url = (base_url or os.getenv("GRIP_DIAGNOSIS_API_URL", "")).rstrip("/")
        self._token = token or os.getenv("GRIP_DIAGNOSIS_API_TOKEN", "") or self._read_token_file()
        self._session = session or requests.Session()

    @property
    def configured(self) -> bool:
        return self.base_url.startswith(("http://", "https://")) and len(self._token) >= 24

    def extract(self, idempotency_key: str, images: Iterable[ImageAsset], context_text: str = "") -> Dict[str, Any]:
        payload = {
            "schemaVersion": "diagnosis-extraction-v1",
            "locale": "zh-CN",
            "contextText": context_text[:2000],
            "images": [self._encode_image(image) for image in images],
        }
        return self._request("POST", "/api/diagnoses/extract", payload, idempotency_key=idempotency_key)["data"]

    def create(self, idempotency_key: str, product: Dict[str, Any], images: Iterable[ImageAsset] = (), draft_id: Optional[str] = None, draft_access_token: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            "schemaVersion": "diagnosis-input-v1",
            "locale": "zh-CN",
            "product": product,
            "images": [] if draft_id else [self._encode_image(image) for image in images],
            "costCeilingMicros": 2_000_000,
        }
        if draft_id:
            payload["extractionDraftId"] = draft_id
        return self._request("POST", "/api/diagnoses", payload, idempotency_key=idempotency_key, access_token=draft_access_token)["data"]

    def status(self, diagnosis_id: str, access_token: str) -> Dict[str, Any]:
        return self._request("GET", f"/api/diagnoses/{diagnosis_id}", access_token=access_token)["data"]

    def result(self, diagnosis_id: str, access_token: str) -> Dict[str, Any]:
        return self._request("GET", f"/api/diagnoses/{diagnosis_id}/result", access_token=access_token)["data"]

    def feedback(self, diagnosis_id: str, access_token: str, usefulness: int, accuracy: int, comment: str, inaccurate_topics=None) -> Dict[str, Any]:
        payload = {"usefulnessScore": usefulness, "accuracyScore": accuracy, "comment": comment[:1000], "inaccurateTopics": list(inaccurate_topics or [])[:20]}
        return self._request("POST", f"/api/diagnoses/{diagnosis_id}/feedback", payload, access_token=access_token)["data"]

    def outcome(self, diagnosis_id: str, access_token: str, observed_at: str, metrics: Dict[str, Any], notes: str = "") -> Dict[str, Any]:
        payload = {"observedAt": observed_at, "metrics": metrics, "notes": notes[:2000]}
        return self._request("POST", f"/api/diagnoses/{diagnosis_id}/outcomes", payload, access_token=access_token)["data"]

    def _request(self, method: str, path: str, payload=None, idempotency_key=None, access_token=None):
        if not self.configured:
            raise DiagnosisApiError("融合诊断服务尚未配置，v5 确定性报告仍可正常生成。")
        headers = {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        if access_token:
            headers["X-Diagnosis-Access-Token"] = access_token
        try:
            response = self._session.request(method, f"{self.base_url}{path}", json=payload, headers=headers, timeout=(3.05, 35))
        except requests.RequestException as exc:
            raise DiagnosisApiError("融合诊断服务暂时不可达，任务资料不会被重复提交。") from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise DiagnosisApiError("融合诊断服务返回了无法识别的响应。") from exc
        if response.status_code >= 400:
            message = body.get("error", {}).get("message") if isinstance(body, dict) else None
            safe = message if isinstance(message, str) and len(message) <= 160 else "融合诊断请求未完成。"
            raise DiagnosisApiError(safe)
        if not isinstance(body, dict) or "data" not in body:
            raise DiagnosisApiError("融合诊断服务响应缺少必要数据。")
        return body

    @staticmethod
    def _encode_image(image: ImageAsset) -> Dict[str, str]:
        return {"filename": image.filename, "mediaType": image.media_type, "base64": base64.b64encode(image.content).decode("ascii")}

    @staticmethod
    def _read_token_file() -> str:
        path = os.getenv("GRIP_DIAGNOSIS_API_TOKEN_FILE", "")
        if not path.startswith("/etc/global-role-intelligence/"):
            return ""
        try:
            return Path(path).read_text(encoding="utf-8").strip()
        except OSError:
            return ""
