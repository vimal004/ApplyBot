"""
Telegram First-Time Login Script.
Run this ONCE locally to authenticate your Telegram account with Telethon.

Usage:
    python telegram_login.py

After successful login this script will print a TELEGRAM_SESSION_STRING value.
Add it to your Render environment variables so the cloud bot never touches a
session file (which would cause AuthKeyDuplicatedError on every re-deploy).
"""

import asyncio
import os
import sys

# Ensure we can import from project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import config

try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.errors import SessionPasswordNeededError
except ImportError:
    print("ERROR: telethon is not installed.")
    print("Run: pip install telethon")
    sys.exit(1)


# Keep the file session path for local fallback / legacy support
FILE_SESSION_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "telegram_session")


async def main():
    api_id = config.telegram.api_id
    api_hash = config.telegram.api_hash
    group_name = config.telegram.group_name

    if not api_id or not api_hash:
        print("ERROR: TELEGRAM_API_ID and TELEGRAM_API_HASH not set in .env")
        print("Get them from https://my.telegram.org")
        sys.exit(1)

    print("=" * 60)
    print("  Telegram Login for ApplyBot")
    print("=" * 60)
    print(f"  API ID: {api_id}")
    print(f"  Group:  {group_name}")
    print()

    # ── Check if TELEGRAM_SESSION_STRING is already set ────────────────
    existing_string = os.environ.get("TELEGRAM_SESSION_STRING", "").strip()
    if existing_string:
        print("[Info] TELEGRAM_SESSION_STRING is already set in environment.")
        client = TelegramClient(StringSession(existing_string), int(api_id), api_hash)
        await client.connect()
        if await client.is_user_authorized():
            me = await client.get_me()
            print(f"Already logged in as: {me.first_name} (@{me.username})")
            print("No action needed — your session string is valid.")
            await client.disconnect()
            return
        else:
            print("[Warning] Existing session string is not authorized. Re-logging in...")
            await client.disconnect()

    # ── Fresh login with StringSession ────────────────────────────────
    # (The old file session's auth key is likely invalidated — doing a fresh login)
    client = TelegramClient(StringSession(), int(api_id), api_hash)
    await client.connect()

    phone = input("Enter your phone number (with country code, e.g. +919876543210): ").strip()
    await client.send_code_request(phone)
    code = input("Enter the OTP code sent to your Telegram app: ").strip()

    try:
        await client.sign_in(phone, code)
    except SessionPasswordNeededError:
        password = input("2FA is enabled. Enter your 2FA password: ").strip()
        await client.sign_in(password=password)

    me = await client.get_me()
    session_string = client.session.save()
    await client.disconnect()

    print(f"\nLogged in as: {me.first_name} (@{me.username})")

    # Verify group access
    verify_client = TelegramClient(StringSession(session_string), int(api_id), api_hash)
    await verify_client.connect()
    try:
        entity = await verify_client.get_entity(group_name)
        print(f"Group '{group_name}' found (ID: {entity.id}) ✓")
    except Exception as e:
        print(f"Warning: Could not find group '{group_name}': {e}")
        print("Make sure you are a member of this group on Telegram.")
    finally:
        await verify_client.disconnect()

    _print_session_instructions(session_string)


def _print_session_instructions(session_string: str):
    print()
    print("=" * 60)
    print("  ACTION REQUIRED: Add this to Render Environment Variables")
    print("=" * 60)
    print()
    print("  Variable name:  TELEGRAM_SESSION_STRING")
    print(f"  Variable value: {session_string}")
    print()
    print("  Steps:")
    print("  1. Go to your Render service → Environment")
    print("  2. Add the variable above")
    print("  3. Redeploy — the bot will use this instead of a session file")
    print()
    print("  NOTE: Do NOT commit this string to git.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
