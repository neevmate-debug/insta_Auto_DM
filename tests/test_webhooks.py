"""
Automated unit tests for Meta Webhooks verification and comment ingestion.
"""

from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from app.main import app
from app.core.config import get_settings

client = TestClient(app)


def test_webhook_verification_success():
    settings = get_settings()
    token = settings.META_VERIFY_TOKEN

    response = client.get(
        f"/api/v1/webhooks?hub.mode=subscribe&hub.challenge=1158201444&hub.verify_token={token}"
    )
    assert response.status_code == 200
    assert response.text == "1158201444"


def test_webhook_verification_invalid_token():
    response = client.get(
        "/api/v1/webhooks?hub.mode=subscribe&hub.challenge=1158201444&hub.verify_token=wrong_token"
    )
    assert response.status_code == 403


import json
import hmac
import hashlib

@patch("app.services.meta_service.MetaApiService.send_private_reply", new_callable=AsyncMock)
def test_webhook_comment_event_ingestion(mock_send):
    mock_send.return_value = {"success": True, "data": {"recipient_id": "123", "message_id": "mid_456"}}
    settings = get_settings()

    sample_payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "17841400000000000",
                "time": 1720000000,
                "changes": [
                    {
                        "field": "comments",
                        "value": {
                            "id": "comment_99999",
                            "text": "Please send LINK",
                            "from": {
                                "id": "user_888",
                                "username": "test_user"
                            }
                        }
                    }
                ]
            }
        ]
    }

    raw_bytes = json.dumps(sample_payload, separators=(',', ':')).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if settings.META_APP_SECRET:
        sig = hmac.new(
            key=settings.META_APP_SECRET.encode("utf-8"),
            msg=raw_bytes,
            digestmod=hashlib.sha256
        ).hexdigest()
        headers["X-Hub-Signature-256"] = f"sha256={sig}"

    response = client.post("/api/v1/webhooks", content=raw_bytes, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert data["comments_queued"] == 1
