"""
Telegram Watcher - Automated Job Posting Ingestion from Telegram Groups.
Uses Telethon (Client API / MTProto) to read messages from groups
the user is already a member of, without needing a Bot API key.

Supports:
- Real-time listener (processes new messages as they arrive)
- Catch-up fetch (fetches messages missed while offline)
- Message filtering (skip non-job messages)
- Deduplication via checkpoint persistence
"""

import os
import json
import asyncio
import datetime
import threading
import re
import time
from typing import Dict, Any, List, Optional

# Telethon is imported lazily to avoid crashing if not installed
_telethon_available = False
try:
    from telethon import TelegramClient, events
    from telethon.errors import SessionPasswordNeededError
    _telethon_available = True
except ImportError:
    pass

from config import config

# Checkpoint file path for tracking last processed message
CHECKPOINT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "outputs", "telegram_checkpoint.json"
)
# Queue file for storing auto-ingested job postings
QUEUE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "outputs", "telegram_queue.json"
)

# Job posting detection keywords (message must contain at least 3)
JOB_KEYWORDS = [
    "company", "role", "batch", "stipend", "salary", "ctc",
    "location", "how to apply", "requirements", "eligibility",
    "referral alert", "job details", "skills required"
]


class TelegramWatcher:
    """
    Automated Telegram group message watcher.
    Connects via Telethon Client API, filters job postings,
    and queues them for processing by ApplyBot.
    """

    def __init__(self):
        self._client: Optional[Any] = None
        self._listener_task: Optional[Any] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._connected = False
        self._status_message = "Not initialized"
        self._session_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "telegram_session"
        )

    # ── Public Properties ──────────────────────────────────────────────

    @property
    def is_available(self) -> bool:
        """Check if Telethon is installed and credentials are configured."""
        return (
            _telethon_available
            and bool(config.telegram.api_id)
            and bool(config.telegram.api_hash)
        )

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def status(self) -> Dict[str, Any]:
        return {
            "available": self.is_available,
            "connected": self._connected,
            "listening": self._running,
            "group": config.telegram.group_name,
            "message": self._status_message,
            "telethon_installed": _telethon_available,
            "has_credentials": bool(config.telegram.api_id and config.telegram.api_hash),
        }

    @staticmethod
    def _resolve_group_id():
        """Resolve the group identifier — numeric IDs are converted to int."""
        group = config.telegram.group_name
        try:
            return int(group)
        except (ValueError, TypeError):
            return group

    @staticmethod
    def clean_old_resumes_and_queue():
        """
        Removes generated PDFs and TeX files older than 7 days to save space,
        and triggers a queue save to prune messages older than 2 days.
        """
        # 1. Prune the queue
        queue = TelegramWatcher._load_queue()
        TelegramWatcher._save_queue(queue)

        # 2. Clean old files from the outputs directory
        output_dir = config.output_dir
        if not os.path.exists(output_dir):
            return

        now = time.time()
        one_week_seconds = 7 * 24 * 60 * 60
        cleaned_count = 0

        for filename in os.listdir(output_dir):
            if filename.endswith(".pdf") or filename.endswith(".tex"):
                filepath = os.path.join(output_dir, filename)
                try:
                    # Check modification time
                    mtime = os.path.getmtime(filepath)
                    if (now - mtime) > one_week_seconds:
                        os.remove(filepath)
                        cleaned_count += 1
                except Exception as e:
                    print(f"[Cleanup] Error removing {filename}: {e}")

        if cleaned_count > 0:
            print(f"[Cleanup] Auto-removed {cleaned_count} old resume/LaTeX files (> 7 days old).")


    # ── Checkpoint Persistence ─────────────────────────────────────────

    @staticmethod
    def _load_checkpoint() -> Dict[str, Any]:
        if os.path.exists(CHECKPOINT_PATH):
            try:
                with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"last_message_id": 0, "last_fetch_time": None}

    @staticmethod
    def _save_checkpoint(last_msg_id: int):
        os.makedirs(os.path.dirname(CHECKPOINT_PATH), exist_ok=True)
        data = {
            "last_message_id": last_msg_id,
            "last_fetch_time": datetime.datetime.now().isoformat()
        }
        with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # ── Queue Management ───────────────────────────────────────────────

    @staticmethod
    def _load_queue() -> List[Dict[str, Any]]:
        if os.path.exists(QUEUE_PATH):
            try:
                with open(QUEUE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    @staticmethod
    def _save_queue(queue: List[Dict[str, Any]]):
        os.makedirs(os.path.dirname(QUEUE_PATH), exist_ok=True)
        # Automatically keep only messages from the last 2 days (48 hours)
        cutoff = datetime.datetime.now() - datetime.timedelta(days=2)
        pruned_queue = []
        for item in queue:
            ingested_str = item.get("ingested_at")
            if ingested_str:
                try:
                    ingested_dt = datetime.datetime.strptime(ingested_str, "%Y-%m-%d %H:%M")
                    if ingested_dt >= cutoff:
                        pruned_queue.append(item)
                except Exception:
                    # Fallback to keep if date format doesn't match
                    pruned_queue.append(item)
            else:
                pruned_queue.append(item)

        with open(QUEUE_PATH, "w", encoding="utf-8") as f:
            json.dump(pruned_queue, f, indent=2, ensure_ascii=False)

    @staticmethod
    def get_queue() -> List[Dict[str, Any]]:
        """Public method to read the current queue."""
        return TelegramWatcher._load_queue()

    @staticmethod
    def remove_from_queue(queue_id: str) -> bool:
        """Remove a specific item from the queue by its ID."""
        queue = TelegramWatcher._load_queue()
        original_len = len(queue)
        queue = [item for item in queue if item.get("id") != queue_id]
        if len(queue) < original_len:
            TelegramWatcher._save_queue(queue)
            return True
        return False

    @staticmethod
    def clear_queue():
        """Clear all items from the queue."""
        TelegramWatcher._save_queue([])

    # ── Message Filtering ──────────────────────────────────────────────

    @staticmethod
    def _is_job_posting(text: str) -> bool:
        """
        Determine if a Telegram message is a job posting
        by checking for common job-related keywords.
        Must match at least 3 keywords to be considered a job posting.
        """
        if not text or len(text) < 50:
            return False

        text_lower = text.lower()
        matched = sum(1 for kw in JOB_KEYWORDS if kw in text_lower)
        return matched >= 3

    @staticmethod
    def _is_duplicate(msg_text: str, queue: List[Dict[str, Any]]) -> bool:
        """Check if a similar message is already in the queue."""
        # Extract company + role fingerprint for dedup
        text_lower = msg_text.lower().strip()
        for item in queue:
            existing_text = item.get("raw_text", "").lower().strip()
            # Simple similarity: if >80% of chars match, consider duplicate
            if existing_text and text_lower == existing_text:
                return True
            # Also check company+role combo
            if (item.get("company", "").lower() in text_lower and
                    item.get("role", "").lower() in text_lower):
                return True
        return False

    # ── Message Processing ─────────────────────────────────────────────

    @staticmethod
    def _process_message(msg_text: str, msg_id: int, msg_date: Any) -> Optional[Dict[str, Any]]:
        """
        Parse a Telegram message into a structured job posting
        and add it to the queue.
        """
        from parser import TelegramJobParser

        try:
            # Parse the message using the existing parser
            parsed = TelegramJobParser.parse_message(msg_text)

            queue = TelegramWatcher._load_queue()

            # Deduplication check
            if TelegramWatcher._is_duplicate(msg_text, queue):
                print(f"[Telegram] Skipping duplicate: {parsed.get('company', 'Unknown')} - {parsed.get('role', 'Unknown')}")
                return None

            # Create queue entry
            entry = {
                "id": f"tg_{msg_id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
                "telegram_msg_id": msg_id,
                "ingested_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "message_date": str(msg_date) if msg_date else "",
                "company": parsed.get("company", "Unknown"),
                "role": parsed.get("role", "Unknown"),
                "batch": parsed.get("batch", ""),
                "salary": parsed.get("salary", ""),
                "location": parsed.get("location", ""),
                "apply_target": parsed.get("apply_target", ""),
                "apply_mode": parsed.get("apply_mode", "UNKNOWN"),
                "is_eligible": parsed.get("is_eligible", False),
                "requirements": parsed.get("requirements", []),
                "raw_text": msg_text,
                "status": "queued"  # queued | processed | skipped
            }

            queue.insert(0, entry)
            TelegramWatcher._save_queue(queue)

            print(f"[Telegram] Queued: {entry['company']} - {entry['role']} (eligible={entry['is_eligible']})")
            return entry

        except Exception as e:
            print(f"[Telegram] Failed to process message {msg_id}: {e}")
            return None

    # ── Fetch (Catch-up) ───────────────────────────────────────────────

    async def _async_fetch(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch recent messages from the configured group."""
        if not self._client or not self._client.is_connected():
            raise RuntimeError("Telegram client is not connected")

        group_id = self._resolve_group_id()
        checkpoint = self._load_checkpoint()
        last_msg_id = checkpoint.get("last_message_id", 0)

        results = []
        max_id_seen = last_msg_id

        try:
            # Resolve the group entity
            entity = await self._client.get_entity(group_id)

            # Fetch messages newer than our checkpoint
            async for message in self._client.iter_messages(
                entity, limit=limit, min_id=last_msg_id
            ):
                if message.id > max_id_seen:
                    max_id_seen = message.id

                if not message.text:
                    continue

                if not self._is_job_posting(message.text):
                    continue

                entry = self._process_message(
                    message.text, message.id, message.date
                )
                if entry:
                    results.append(entry)

            # Update checkpoint
            if max_id_seen > last_msg_id:
                self._save_checkpoint(max_id_seen)

        except Exception as e:
            print(f"[Telegram] Fetch error: {e}")
            self._status_message = f"Fetch error: {e}"
            raise

        self._status_message = f"Fetched {len(results)} new job postings"
        return results

    def fetch_messages(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Synchronous wrapper for fetching messages."""
        if not self.is_available:
            return []

        if self._loop and self._loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                self._async_fetch(limit), self._loop
            )
            return future.result(timeout=30)
        else:
            # Create a temporary event loop
            loop = asyncio.new_event_loop()
            try:
                # Connect first if needed
                if not self._client or not self._client.is_connected():
                    self._client = TelegramClient(
                        self._session_path,
                        int(config.telegram.api_id),
                        config.telegram.api_hash
                    )
                    loop.run_until_complete(self._client.connect())
                    if not loop.run_until_complete(self._client.is_user_authorized()):
                        self._status_message = "Not authorized. Run the listener first to complete login."
                        return []
                    self._connected = True

                return loop.run_until_complete(self._async_fetch(limit))
            finally:
                if self._client and self._client.is_connected():
                    loop.run_until_complete(self._client.disconnect())
                loop.close()

    # ── Real-time Listener ─────────────────────────────────────────────

    async def _start_listener(self):
        """Start the real-time event listener on the Telegram group."""
        group_id = self._resolve_group_id()

        self._client = TelegramClient(
            self._session_path,
            int(config.telegram.api_id),
            config.telegram.api_hash
        )

        await self._client.connect()

        if not await self._client.is_user_authorized():
            self._status_message = (
                "Session not authorized. Please run the first-time login script: "
                "python telegram_login.py"
            )
            self._connected = False
            return

        self._connected = True
        self._running = True
        self._status_message = f"Listening on group {group_id}"

        print(f"[Telegram] Connected and listening on group {group_id}")

        # Register new message handler
        @self._client.on(events.NewMessage(chats=group_id))
        async def on_new_message(event):
            if not event.text:
                return

            if not self._is_job_posting(event.text):
                return

            entry = self._process_message(
                event.text, event.message.id, event.message.date
            )
            if entry:
                # Update checkpoint
                checkpoint = self._load_checkpoint()
                if event.message.id > checkpoint.get("last_message_id", 0):
                    self._save_checkpoint(event.message.id)

        # Do a catch-up fetch first
        try:
            results = await self._async_fetch(limit=100)
            if results:
                print(f"[Telegram] Catch-up: found {len(results)} missed job postings")
        except Exception as e:
            print(f"[Telegram] Catch-up fetch warning: {e}")

        # Keep running until disconnected
        await self._client.run_until_disconnected()

        self._running = False
        self._connected = False
        self._status_message = "Listener stopped"

    def start_listener_thread(self):
        """Start the Telegram listener in a background thread."""
        if not self.is_available:
            self._status_message = "Telegram not configured. Add TELEGRAM_API_ID and TELEGRAM_API_HASH to .env"
            return False

        if self._running:
            self._status_message = "Listener is already running"
            return True

        def _run():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            try:
                self._loop.run_until_complete(self._start_listener())
            except Exception as e:
                print(f"[Telegram] Listener thread error: {e}")
                self._status_message = f"Listener error: {e}"
                self._running = False
                self._connected = False
            finally:
                self._loop.close()

        self._thread = threading.Thread(target=_run, daemon=True, name="TelegramWatcher")
        self._thread.start()
        return True

    def stop_listener(self):
        """Stop the real-time listener."""
        if self._client and self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._client.disconnect(), self._loop
            )
        self._running = False
        self._status_message = "Listener stopped"


# Singleton instance
telegram_watcher = TelegramWatcher()
