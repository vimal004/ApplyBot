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

# Settings file path for watcher preferences
SETTINGS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "outputs", "telegram_settings.json"
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
        settings = self._load_settings()
        self.auto_send_email = settings.get("auto_send_email", True)
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
            "auto_send_email": self.auto_send_email,
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

    # ── Settings Persistence ───────────────────────────────────────────

    @staticmethod
    def _load_settings() -> Dict[str, Any]:
        env_auto_send = os.environ.get("AUTO_SEND_EMAIL", "true").lower() in ("true", "1", "yes")
        if os.path.exists(SETTINGS_PATH):
            try:
                with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "auto_send_email" in data:
                        return data
            except Exception:
                pass
        return {"auto_send_email": env_auto_send}

    def set_auto_send_email(self, value: bool):
        self.auto_send_email = value
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        try:
            settings = TelegramWatcher._load_settings()
            settings["auto_send_email"] = value
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            print(f"[TelegramWatcher] Error saving settings: {e}")

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
    def _process_message(msg_text: str, msg_id: int, msg_date: Any) -> List[Dict[str, Any]]:
        """
        Parse a Telegram message (which may contain multiple jobs)
        and add them to the queue. Returns a list of queued entries.
        """
        from parser import TelegramJobParser

        try:
            # Parse the message using the updated parser (returns a list of job dicts)
            parsed_jobs = TelegramJobParser.parse_message(msg_text)

            queue = TelegramWatcher._load_queue()
            added_entries = []

            for idx, parsed in enumerate(parsed_jobs):
                # Unique ID per job in the message
                job_id = f"tg_{msg_id}_{idx}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Check for duplicates (using company & role combo)
                is_dup = False
                for item in queue:
                    if (item.get("company", "").lower() == parsed.get("company", "").lower() and
                            item.get("role", "").lower() == parsed.get("role", "").lower()):
                        is_dup = True
                        break
                
                if is_dup:
                    print(f"[Telegram] Skipping duplicate: {parsed.get('company', 'Unknown')} - {parsed.get('role', 'Unknown')}")
                    continue

                apply_mode = parsed.get("apply_mode", "UNKNOWN")
                status = "queued"
                status_msg = ""
                is_eligible = parsed.get("is_eligible", False)

                # Automate mail sending ONLY if job requires email application AND is 2025/2026 eligible AND auto_send_email is enabled
                if apply_mode == "EMAIL" and telegram_watcher.auto_send_email and is_eligible:
                    print(f"[Telegram Auto-Send] Direct EMAIL job detected for {parsed.get('company')} - {parsed.get('role')} (Batch: {parsed.get('batch')}). Auto-sending email...")
                    try:
                        from telegram_bot import ApplyBotPipeline
                        from app import _log_application
                        result = ApplyBotPipeline.process_referral(msg_text, superfast_mode=True, job_dict=parsed)
                        _log_application(result)
                        action_res = result.get("action_result", {})
                        if action_res.get("sent"):
                            status = "auto_sent"
                            status_msg = action_res.get("status", "Email sent automatically")
                            print(f"[Telegram Auto-Send Success] {status_msg}")
                        else:
                            status = "error"
                            status_msg = action_res.get("status", "Failed to auto-send email")
                            print(f"[Telegram Auto-Send Error] {status_msg}")
                    except Exception as exc:
                        status = "error"
                        status_msg = str(exc)
                        print(f"[Telegram Auto-Send Exception] {exc}")
                elif apply_mode == "EMAIL" and not is_eligible:
                    status_msg = f"Auto-send skipped: Batch '{parsed.get('batch')}' is not eligible for 2025/2026"
                    print(f"[Telegram Auto-Send Skipped] {parsed.get('company')} - {parsed.get('role')} (Batch: '{parsed.get('batch')}') is not eligible for 2025/2026.")

                entry = {
                    "id": job_id,
                    "telegram_msg_id": msg_id,
                    "ingested_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "message_date": str(msg_date) if msg_date else "",
                    "company": parsed.get("company", "Unknown"),
                    "role": parsed.get("role", "Unknown"),
                    "batch": parsed.get("batch", ""),
                    "salary": parsed.get("salary", ""),
                    "location": parsed.get("location", ""),
                    "apply_target": parsed.get("apply_target", ""),
                    "apply_mode": apply_mode,
                    "subject_line": parsed.get("subject_line", ""),
                    "is_eligible": parsed.get("is_eligible", False),
                    "requirements": parsed.get("requirements", []),
                    "raw_text": msg_text,
                    "status": status,
                    "status_msg": status_msg
                }

                queue.insert(0, entry)
                added_entries.append(entry)
                print(f"[Telegram] Queued ({status}): {entry['company']} - {entry['role']} (eligible={entry['is_eligible']})")

            if added_entries:
                TelegramWatcher._save_queue(queue)

            return added_entries

        except Exception as e:
            print(f"[Telegram] Failed to process message {msg_id}: {e}")
            return []

    # ── Fetch (Catch-up) ───────────────────────────────────────────────

    async def _async_fetch(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch recent messages from the configured group."""
        if not self._client or not self._client.is_connected():
            print("[Telegram] Error: Client not connected during fetch.")
            return []

        group_id = self._resolve_group_id()
        checkpoint = self._load_checkpoint()
        last_msg_id = checkpoint.get("last_message_id", 0)

        results = []
        max_id_seen = last_msg_id

        try:
            entity = await self._client.get_entity(group_id)
            async for message in self._client.iter_messages(
                entity, limit=limit, min_id=last_msg_id
            ):
                if message.id > max_id_seen:
                    max_id_seen = message.id
                if not message.text or not self._is_job_posting(message.text):
                    continue
                entries = self._process_message(message.text, message.id, message.date)
                if entries:
                    results.extend(entries)

            if max_id_seen > last_msg_id:
                self._save_checkpoint(max_id_seen)
            self._status_message = f"Successfully fetched {len(results)} jobs."
            return results
        except Exception as e:
            error_msg = f"Fetch failed: {str(e)}"
            print(f"[Telegram] {error_msg}")
            self._status_message = error_msg
            return []

    def fetch_messages(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Synchronous wrapper for fetching messages."""
        if not self.is_available:
            return []

        if self._loop and self._loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                self._async_fetch(limit), self._loop
            )
            try:
                return future.result(timeout=30)
            except Exception as e:
                print(f"[Telegram] Error in threadsafe fetch: {e}")
                return []
        else:
            loop = asyncio.new_event_loop()
            try:
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

        # Always create a fresh client; the caller must ensure the previous
        # client (if any) has been disconnected and nulled out before calling.
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

        listener_start_time = datetime.datetime.now(datetime.timezone.utc)

        # Register new message handler
        @self._client.on(events.NewMessage(chats=group_id))
        async def on_new_message(event):
            if not event.text:
                return

            # Strict time filter: ignore old cached messages delivered on startup connection
            msg_date = event.message.date
            if msg_date:
                if msg_date.tzinfo is None:
                    msg_date = msg_date.replace(tzinfo=datetime.timezone.utc)
                if msg_date < listener_start_time:
                    return

            if not self._is_job_posting(event.text):
                return

            entries = self._process_message(
                event.text, event.message.id, event.message.date
            )
            if entries:
                # Update checkpoint
                checkpoint = self._load_checkpoint()
                if event.message.id > checkpoint.get("last_message_id", 0):
                    self._save_checkpoint(event.message.id)

        # Real-time listener: process incoming messages as they arrive
        # (Disabled historical catch-up on startup to avoid auto-sending emails to past backlog messages)
        print(f"[Telegram] Real-time listener ready for new incoming posts on group {group_id}.")

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

        async def _run_with_reconnect():
            """
            Async reconnect loop that lives entirely within ONE event loop.
            Using asyncio.sleep (not time.sleep) keeps the loop alive between
            retries, so Telethon never encounters a 'bound to different event
            loop' error on reconnect.
            """
            while True:
                try:
                    await self._start_listener()
                except Exception as e:
                    print(f"[Telegram Watcher] Connection dropped ({e}). Auto-reconnecting in 10s...")
                    self._status_message = f"Reconnecting after error: {e}"
                    self._running = False
                    self._connected = False
                finally:
                    # Always cleanly disconnect and discard the old client so
                    # the next TelegramClient() gets a fresh session slot and
                    # avoids AuthKeyDuplicatedError ("used under two IPs").
                    if self._client is not None:
                        try:
                            await self._client.disconnect()
                        except Exception:
                            pass
                        self._client = None

                # Backoff delay before auto-reconnecting (runs inside the loop)
                await asyncio.sleep(10)

        def _run():
            """
            Thread entry point: create ONE event loop for the lifetime of the
            thread and run the async reconnect coroutine inside it.
            Recreating the loop on every iteration (the old approach) caused
            Telethon's internal asyncio primitives (Event, Queue) to become
            bound to the wrong loop after the first reconnect.
            """
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            try:
                loop.run_until_complete(_run_with_reconnect())
            finally:
                try:
                    loop.close()
                except Exception:
                    pass
                self._loop = None

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
