"""
Meta Webhook endpoints router.

Handles:
1. GET /webhooks: Meta subscription verification challenge (hub.challenge / hub.verify_token)
2. POST /webhooks: Ingestion of incoming Instagram & Facebook event payloads (e.g. comment creation)
"""

import logging
from typing import Set
from fastapi import APIRouter, Request, Query, HTTPException, status, Depends, BackgroundTasks
from fastapi.responses import PlainTextResponse
from app.core.config import Settings, get_settings
from app.core.security import verify_meta_signature
from app.services.meta_service import MetaApiService

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory deduplication set to avoid replying multiple times to the same comment
# Meta strictly allows only ONE private reply per comment.
_processed_comments: Set[str] = set()


async def process_comment_notification(comment_data: dict, settings: Settings):
    """
    Background worker that analyzes a comment, verifies keyword triggers,
    and sends the private reply DM.
    """
    comment_id = comment_data.get("id")
    if not comment_id:
        logger.warning("Comment payload missing 'id'. Skipping.")
        return

    # Check deduplication
    if comment_id in _processed_comments:
        logger.info("Comment [ID: %s] has already been processed. Skipping to avoid duplicate reply.", comment_id)
        return

    from_user = comment_data.get("from", {})
    from_id = from_user.get("id")
    username = from_user.get("username", "Unknown")
    comment_text = comment_data.get("text", "")

    # Prevent replying to comments made by our own account
    if settings.INSTAGRAM_ACCOUNT_ID and from_id == settings.INSTAGRAM_ACCOUNT_ID:
        logger.info("Comment [ID: %s] is from own account. Skipping self-reply.", comment_id)
        return

    logger.info("Processing comment [ID: %s] from @%s: '%s'", comment_id, username, comment_text)

    # Keyword check
    trigger_keyword = settings.AUTO_DM_TRIGGER_KEYWORD
    if trigger_keyword and trigger_keyword.strip():
        clean_keyword = trigger_keyword.strip().lower()
        if clean_keyword not in comment_text.lower():
            logger.info(
                "Comment [ID: %s] text '%s' does not match trigger keyword '%s'. No DM sent.",
                comment_id, comment_text, trigger_keyword
            )
            return

    # Mark as processed
    _processed_comments.add(comment_id)
    if len(_processed_comments) > 10000:
        _processed_comments.clear()

    # Send DM via Meta Graph API
    service = MetaApiService(settings)
    if not service.is_configured():
        logger.warning("Cannot send private reply: META_PAGE_ACCESS_TOKEN is not configured in .env.")
        return

    message = settings.AUTO_DM_RESPONSE_MESSAGE
    result = await service.send_private_reply(comment_id, message)
    if result.get("success"):
        logger.info("Private reply delivered successfully to @%s for comment %s.", username, comment_id)
    else:
        logger.error("Failed to deliver private reply to @%s for comment %s: %s", username, comment_id, result)


@router.get(
    "/webhooks",
    summary="Meta Webhook Verification Challenge",
    description="Endpoint invoked by Meta to verify webhook ownership via hub.challenge.",
    response_class=PlainTextResponse
)
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    settings: Settings = Depends(get_settings)
):
    """
    Handles Meta's one-time webhook verification challenge when subscribing in the Meta App Dashboard.
    Must return the hub.challenge integer/string as plain text with HTTP 200.
    """
    logger.info("Received Meta Webhook verification handshake request.")

    if not settings.META_VERIFY_TOKEN:
        logger.warning("META_VERIFY_TOKEN is not configured in .env. Verification cannot succeed.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="META_VERIFY_TOKEN is not configured in the application environment."
        )

    if hub_mode == "subscribe" and hub_verify_token == settings.META_VERIFY_TOKEN:
        logger.info("Webhook verification challenge passed successfully.")
        return PlainTextResponse(content=hub_challenge, status_code=status.HTTP_200_OK)

    logger.warning("Webhook verification failed: token mismatch or invalid mode.")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Verification token mismatch or invalid hub.mode."
    )


@router.post(
    "/webhooks",
    summary="Meta Webhook Event Ingestion",
    description="Receives real-time Instagram and Facebook events (comments, mentions)."
)
async def handle_webhook_event(
    request: Request,
    background_tasks: BackgroundTasks,
    settings: Settings = Depends(get_settings)
):
    """
    Receives incoming webhook events from Meta.

    1. Validates the X-Hub-Signature-256 header using the Meta App Secret (if set).
    2. Parses the event envelope to identify comment creation on Instagram media.
    3. Queues background tasks to verify keyword triggers and send DM.
    4. Returns 200 OK immediately (within Meta's 20-second timeout policy).
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    # Optional signature check: if META_APP_SECRET is set, verify the signature
    if settings.META_APP_SECRET:
        if not verify_meta_signature(raw_body, signature, settings.META_APP_SECRET):
            logger.warning("Invalid webhook signature detected. Dropping event.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid X-Hub-Signature-256 signature."
            )

    try:
        payload = await request.json()
    except Exception:
        logger.error("Failed to parse incoming webhook JSON body.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")

    obj_type = payload.get("object")
    logger.info("Received webhook event payload for object: %s", obj_type)

    # Process comments in background tasks
    entries = payload.get("entry", [])
    comment_count = 0

    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            field = change.get("field")
            if field in ("comments", "feed"):
                comment_value = change.get("value", {})
                background_tasks.add_task(process_comment_notification, comment_value, settings)
                comment_count += 1

    # Acknowledge receipt immediately to satisfy Meta's 20-second timeout policy
    return {
        "status": "received",
        "object": obj_type,
        "comments_queued": comment_count
    }
