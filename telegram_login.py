"""
Telegram First-Time Login Script.
Run this ONCE to authenticate your Telegram account with Telethon.
After successful login, a session file is saved and you never need to run this again.

Usage:
    python telegram_login.py
"""

import asyncio
import os
import sys

# Ensure we can import from project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import config

try:
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError
except ImportError:
    print("ERROR: telethon is not installed.")
    print("Run: pip install telethon")
    sys.exit(1)


SESSION_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "telegram_session")


async def main():
    api_id = config.telegram.api_id
    api_hash = config.telegram.api_hash
    group_name = config.telegram.group_name

    if not api_id or not api_hash:
        print("ERROR: TELEGRAM_API_ID and TELEGRAM_API_HASH not set in .env")
        print("Get them from https://my.telegram.org")
        sys.exit(1)

    print("=" * 60)
    print("  Telegram First-Time Login for ApplyBot")
    print("=" * 60)
    print(f"  API ID: {api_id}")
    print(f"  Group:  {group_name}")
    print()

    client = TelegramClient(SESSION_PATH, int(api_id), api_hash)
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"Already logged in as: {me.first_name} (@{me.username})")
        print("Session file exists. No action needed.")
        await client.disconnect()
        return

    # Phone number login flow
    phone = input("Enter your phone number (with country code, e.g. +919876543210): ").strip()
    await client.send_code_request(phone)
    code = input("Enter the OTP code sent to your Telegram app: ").strip()

    try:
        await client.sign_in(phone, code)
    except SessionPasswordNeededError:
        # 2FA is enabled
        password = input("2FA is enabled. Enter your 2FA password: ").strip()
        await client.sign_in(password=password)

    me = await client.get_me()
    print()
    print(f"Logged in as: {me.first_name} (@{me.username})")
    print(f"Session saved to: {SESSION_PATH}.session")
    print()

    # Verify group access
    try:
        entity = await client.get_entity(group_name)
        print(f"Group '{group_name}' found (ID: {entity.id})")
        print("Everything is set up! You can now use the Telegram auto-ingestion feature.")
    except Exception as e:
        print(f"Warning: Could not find group '{group_name}': {e}")
        print("Make sure you are a member of this group on Telegram.")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
