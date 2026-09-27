"""
Security utilities for Meta Webhooks.
Includes cryptographic verification for X-Hub-Signature-256 headers sent by Meta.
"""

import hmac
import hashlib
import logging

logger = logging.getLogger(__name__)


def verify_meta_signature(payload_bytes: bytes, signature_header: str | None, app_secret: str | None) -> bool:
    """
    Verifies that the incoming webhook payload genuinely originated from Meta.

    Meta computes an HMAC-SHA256 signature using your App Secret and provides it in
    the 'X-Hub-Signature-256' header prefixed with 'sha256='.

    Args:
        payload_bytes: The raw request body bytes.
        signature_header: The 'X-Hub-Signature-256' header value from the request.
        app_secret: The META_APP_SECRET from configuration.

    Returns:
        bool: True if the signature matches, False otherwise.
    """
    if not app_secret:
        logger.warning("META_APP_SECRET is not configured; cannot verify webhook signature.")
        return False

    if not signature_header or not signature_header.startswith("sha256="):
        logger.warning("Missing or malformed X-Hub-Signature-256 header.")
        return False

    received_hash = signature_header[len("sha256="):]

    expected_hash = hmac.new(
        key=app_secret.encode("utf-8"),
        msg=payload_bytes,
        digestmod=hashlib.sha256
    ).hexdigest()

    # Use constant-time comparison to protect against timing attacks
    return hmac.compare_digest(received_hash, expected_hash)
