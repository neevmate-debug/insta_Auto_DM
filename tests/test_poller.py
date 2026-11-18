"""
Unit tests for the background Instagram CommentPoller service.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.v1.endpoints.webhooks import _processed_comments
from app.core.config import Settings
from app.services.comment_poller import CommentPoller


def _make_mock_response(payload: dict, status_code: int = 200, headers: dict | None = None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    resp.text = str(payload)
    resp.headers = headers or {}
    return resp


def test_poller_seeds_old_comments_and_replies_only_to_new():
    _processed_comments.clear()

    settings = Settings(
        META_PAGE_ACCESS_TOKEN="IGAA_test_token",
        INSTAGRAM_ACCOUNT_ID="17841406703162572",
        AUTO_DM_TRIGGER_KEYWORD="",
        AUTO_DM_RESPONSE_MESSAGE="Hello from Auto-DM!",
        COMMENT_POLL_INTERVAL_SECONDS=10,
    )
    poller = CommentPoller(settings)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000")

    old_payload = {
        "data": [
            {
                "id": "media_1",
                "comments": {
                    "data": [
                        {
                            "id": "old_cmt_1",
                            "text": "Old comment",
                            "timestamp": "2026-01-01T10:00:00+0000",
                            "from": {"id": "user_1", "username": "old_user"},
                        }
                    ]
                },
            }
        ]
    }

    new_payload = {
        "data": [
            {
                "id": "media_1",
                "comments": {
                    "data": [
                        {
                            "id": "new_cmt_2",
                            "text": "Test reply",
                            "timestamp": now_iso,
                            "from": {"id": "user_2", "username": "gorkha.boy.319"},
                        },
                        {
                            "id": "own_cmt_3",
                            "text": "Own comment",
                            "timestamp": now_iso,
                            "from": {"id": "17841406703162572", "username": "mr._yadav_100"},
                        },
                        {
                            "id": "old_cmt_1",
                            "text": "Old comment",
                            "timestamp": "2026-01-01T10:00:00+0000",
                            "from": {"id": "user_1", "username": "old_user"},
                        },
                    ]
                },
            }
        ]
    }

    mock_client = AsyncMock()
    mock_client.get.side_effect = [
        _make_mock_response(old_payload),
        _make_mock_response(new_payload),
        _make_mock_response(new_payload),
    ]

    with patch("app.services.meta_service.MetaApiService.send_private_reply", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"success": True, "status_code": 200, "data": {"message_id": "m_1"}}

        async def run_flow():
            seeded = await poller.seed_existing_comments(mock_client)
            assert seeded == 1
            assert "old_cmt_1" in _processed_comments
            assert mock_send.call_count == 0

            # First poll detects new_cmt_2 (sends DM) and own_cmt_3 (skipped as self-comment)
            await poller.poll_once(mock_client)
            assert mock_send.call_count == 1
            mock_send.assert_called_with("new_cmt_2", "Hello from Auto-DM!")

            # Second poll with same comments must NOT send any duplicate DM
            await poller.poll_once(mock_client)
            assert mock_send.call_count == 1

        asyncio.run(run_flow())


def test_meta_api_service_normalizes_malformed_base_url():
    from app.services.meta_service import MetaApiService

    for bad_url in [
        "",
        "   ",
        "graph.instagram.com",
        "graph.instgram.com",
        "17841406703162572",
        "META_GRAPH_API_BASE_URL=https://graph.instagram.com",
        " https://graph.facebook.com ",
        '"graph.instagram.com/"',
    ]:
        s = Settings(
            META_PAGE_ACCESS_TOKEN=" IGAA_test_token ",
            META_GRAPH_API_BASE_URL=bad_url,
            META_GRAPH_API_VERSION="v21.0",
        )
        svc = MetaApiService(s)
        assert svc.base_url == "https://graph.instagram.com/v21.0", f"Failed for {bad_url!r}: got {svc.base_url!r}"
        assert svc.access_token == "IGAA_test_token"

