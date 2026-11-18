"""
Background Instagram Comment Poller Service.

Works alongside Meta Webhooks so automated DM replies are delivered reliably
within seconds even when Meta Standard Access / Development Mode suppresses
live webhook delivery for non-tester accounts.

Uses a single Graph API field-expansion request per poll cycle:
  GET /{version}/me/media?fields=id,comments.limit(N){id,text,timestamp,from}&limit=M

Guarantees:
- On startup, all existing comments are seeded into the shared deduplication set
  so historical comments are NEVER spammed.
- Any comment older than the server start time (minus a 30s grace window) is
  skipped even if pagination shifts.
- Shares `_processed_comments` and `process_comment_notification` with webhooks.py
  so Webhook + Poller never send duplicate replies.
- Automatically throttles if Meta's `x-app-usage` approaches rate limits.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from app.api.v1.endpoints.webhooks import _processed_comments, process_comment_notification
from app.core.config import Settings
from app.services.meta_service import MetaApiService

logger = logging.getLogger(__name__)


def _parse_meta_timestamp(ts: Optional[str]) -> Optional[datetime]:
    """Parses Meta ISO-8601 timestamps like '2026-11-18T16:12:19+0000'."""
    if not ts:
        return None
    try:
        # Python's fromisoformat handles +0000 in 3.11+, normalize Z just in case
        normalized = ts.replace("Z", "+00:00")
        if len(normalized) >= 5 and normalized[-5] in ("+", "-") and ":" not in normalized[-5:]:
            normalized = f"{normalized[:-2]}:{normalized[-2:]}"
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


class CommentPoller:
    """Polls Instagram Graph API for new comments and triggers Auto-DM replies."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.meta_service = MetaApiService(settings)
        self.base_url = self.meta_service.base_url
        self.interval = max(5, int(settings.COMMENT_POLL_INTERVAL_SECONDS))
        self.media_limit = max(1, int(settings.COMMENT_POLL_MEDIA_LIMIT))
        self.comments_limit = max(1, int(settings.COMMENT_POLL_COMMENTS_LIMIT))
        self.started_at = datetime.now(timezone.utc) - timedelta(seconds=30)
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def _fetch_recent_media_with_comments(self, client: httpx.AsyncClient, comments_limit: Optional[int] = None) -> tuple[list, int]:
        """
        Fetches recent posts along with their latest comments in a single API call.
        Returns (media_list, suggested_sleep_seconds).
        """
        c_limit = comments_limit or self.comments_limit
        url = f"{self.base_url}/me/media"
        params = {
            "fields": f"id,comments.limit({c_limit}){{id,text,timestamp,from}}",
            "limit": self.media_limit,
        }
        headers = {
            "Authorization": f"Bearer {self.meta_service.access_token}",
        }

        response = await client.get(url, params=params, headers=headers)
        suggested_sleep = self.interval

        # Inspect Meta rate-limit header if present
        usage_raw = response.headers.get("x-app-usage")
        if usage_raw:
            try:
                usage = json.loads(usage_raw)
                call_vol = max(usage.get("call_count", 0), usage.get("call_volume", 0))
                if call_vol >= 75:
                    suggested_sleep = max(self.interval * 3, 30)
                    logger.warning(
                        "Meta API usage high (%s%%). Throttling poll interval to %ss.",
                        call_vol, suggested_sleep
                    )
            except Exception:
                pass

        if response.status_code == 429:
            logger.warning("Meta API rate limit hit (HTTP 429). Backing off for 60s.")
            return [], 60

        if response.status_code >= 400:
            logger.error(
                "Comment poller API error (HTTP %s): %s",
                response.status_code, response.text[:300]
            )
            return [], max(self.interval * 2, 20)

        data = response.json()
        return data.get("data", []), suggested_sleep

    async def seed_existing_comments(self, client: httpx.AsyncClient) -> int:
        """
        Loads existing comment IDs into the deduplication set on startup so
        old comments are never sent duplicate/unwanted DMs.
        """
        media_list, _ = await self._fetch_recent_media_with_comments(client, comments_limit=max(25, self.comments_limit))
        seeded = 0
        for media in media_list:
            comments = media.get("comments", {}).get("data", [])
            for comment in comments:
                cid = comment.get("id")
                if cid:
                    _processed_comments.add(cid)
                    seeded += 1
        logger.info(
            "Comment poller ready: seeded %d existing comments across %d posts. Watching every %ds...",
            seeded, len(media_list), self.interval
        )
        return seeded

    async def poll_once(self, client: httpx.AsyncClient) -> int:
        """
        Runs a single poll cycle. Returns the number of newly processed comments.
        """
        media_list, next_sleep = await self._fetch_recent_media_with_comments(client)
        new_count = 0

        for media in media_list:
            media_id = media.get("id")
            comments = media.get("comments", {}).get("data", [])
            # Process oldest-first among newly discovered comments
            for comment in reversed(comments):
                cid = comment.get("id")
                if not cid or cid in _processed_comments:
                    continue

                # Safety guard: skip historical comments that predated server start
                cmt_dt = _parse_meta_timestamp(comment.get("timestamp"))
                if cmt_dt and cmt_dt < self.started_at:
                    _processed_comments.add(cid)
                    continue

                logger.info(
                    "=== NEW COMMENT DETECTED VIA POLLER (media=%s, comment_id=%s) ===",
                    media_id, cid
                )
                await process_comment_notification(comment, self.settings)
                new_count += 1

        self._next_sleep = next_sleep
        return new_count

    async def _run_loop(self):
        """Main background polling loop."""
        self._next_sleep = self.interval
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                await self.seed_existing_comments(client)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error("Error seeding existing comments on startup: %s", e, exc_info=True)

            while not self._stop_event.is_set():
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self._next_sleep)
                    break  # stop_event was set
                except asyncio.TimeoutError:
                    pass

                try:
                    await self.poll_once(client)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error("Error in comment poller cycle: %s", e, exc_info=True)
                    self._next_sleep = max(self.interval * 2, 20)

    def start(self):
        """Starts the background poller task."""
        if not self.meta_service.is_configured():
            logger.info("Comment poller not started: META_PAGE_ACCESS_TOKEN is not configured.")
            return
        if self._task is None or self._task.done():
            self._stop_event.clear()
            self._task = asyncio.create_task(self._run_loop(), name="instagram-comment-poller")
            logger.info(
                "Started Instagram background comment poller (base_url=%s, interval=%ds).",
                self.base_url, self.interval
            )

    async def stop(self):
        """Stops the background poller task cleanly."""
        if self._task and not self._task.done():
            self._stop_event.set()
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped Instagram background comment poller.")
