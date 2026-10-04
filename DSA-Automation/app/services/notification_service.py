"""Sends a Telegram message when a new draft is ready.

Replaces the old Windows-only desktop notification. A hosted server cannot
pop up anything on your laptop, but it can message your phone with a link
to the review page, which works from anywhere.

Setup: create a bot with @BotFather (gives TELEGRAM_BOT_TOKEN), send your bot
any message, then open
https://api.telegram.org/bot<TOKEN>/getUpdates to find your chat id.
"""
import logging
import os

import httpx

logger = logging.getLogger(__name__)


def build_review_url(draft_id: int | None = None) -> str:
    base = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    return f"{base}/review/{draft_id}" if draft_id else f"{base}/review"


async def notify_draft_ready(draft_id: int, problem_title: str) -> bool:
    """Notify that a draft is ready. Never raises: a failed notification
    must not break draft creation. Returns True if a message was sent."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logger.info("Telegram not configured; skipping notification.")
        return False

    text = (
        f"New DSA draft ready: {problem_title}\n"
        f"Review: {build_review_url(draft_id)}"
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
            response.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram notification failed: %s", exc)
        return False
