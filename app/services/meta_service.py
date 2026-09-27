"""
Meta Graph API Service Layer.

This module outlines the service interface for interacting with Meta's official APIs:
1. Instagram Graph API (for reading comments/media)
2. Messenger API for Instagram (for sending automated private replies to comments)

OFFICIAL POLICY & INTEGRATION SPECIFICATION:
- Endpoint: POST https://graph.facebook.com/{version}/{comment-id}/messages
  Or POST https://graph.facebook.com/{version}/me/messages
     Body: {
       "recipient": {"comment_id": "<COMMENT_ID>"},
       "message": {"text": "<PREDEFINED_MESSAGE>"}
     }
- Rules & Limitations:
  1. A private reply can only be sent within 7 days of the comment creation timestamp.
  2. Only ONE automated private reply is allowed per comment by Meta's policy.
  3. Subsequent messaging requires the user to reply back in the DM, opening a 24-hour window.
  4. Requires a valid Meta Page Access Token with 'instagram_manage_messages' permissions.

NOTE: Real network calls and mock tokens are intentionally omitted until Phase 2 credentials are provided.
"""

import logging
from typing import Dict, Any, Optional
from app.core.config import Settings

logger = logging.getLogger(__name__)


class MetaApiService:
    """
    Client interface for Meta Graph API calls.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.api_version = settings.META_GRAPH_API_VERSION
        self.base_url = f"{settings.META_GRAPH_API_BASE_URL}/{self.api_version}"

    def is_configured(self) -> bool:
        """
        Validates whether necessary Meta credentials to send a message have been populated.
        """
        return bool(self.settings.META_PAGE_ACCESS_TOKEN)

    async def send_private_reply(self, comment_id: str, message_text: str) -> Dict[str, Any]:
        """
        Sends an automated private message (DM) in response to a post or reel comment.

        Args:
            comment_id: Unique ID of the comment received from the webhook.
            message_text: The message/link to send to the commenter.

        Returns:
            Dict containing API response details or operational status.

        Raises:
            RuntimeError: If META_PAGE_ACCESS_TOKEN is not configured in .env.
        """
        if not self.is_configured():
            logger.warning(
                "Attempted to send private reply, but META_PAGE_ACCESS_TOKEN is not configured in environment."
            )
            raise RuntimeError(
                "META_PAGE_ACCESS_TOKEN is not configured. Please supply a valid token in your .env file."
            )

        url = f"{self.base_url}/me/messages"
        headers = {
            "Authorization": f"Bearer {self.settings.META_PAGE_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {
            "recipient": {
                "comment_id": comment_id
            },
            "message": {
                "text": message_text
            }
        }

        logger.info("Sending private reply to comment [ID: %s] via %s", comment_id, url)

        import httpx
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                try:
                    data = response.json()
                except Exception:
                    data = {"text": response.text}

                if response.status_code >= 400:
                    logger.error(
                        "Meta API error (HTTP %s) sending private reply for comment %s: %s",
                        response.status_code, comment_id, data
                    )
                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "error": data
                    }

                logger.info("Successfully sent private reply for comment %s. Response: %s", comment_id, data)
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "data": data
                }
            except Exception as e:
                logger.error("Network or execution error sending private reply to comment %s: %s", comment_id, str(e), exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
