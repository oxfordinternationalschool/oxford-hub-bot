"""Connects the Telegram account that adds people to groups. Run it yourself, on your computer:

    python -m bot.account_login          log in and save the session to .env
    python -m bot.account_login --copy   copy the saved session to the clipboard, for Vercel

You type everything here yourself. The session gives full access to the account, so it is
never printed. It can be ended at any time in Telegram: Settings > Devices.
"""
import asyncio
import getpass
import os
import subprocess
import sys
from pathlib import Path

from dotenv import set_key
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.config import settings
from bot.db.models import Group
from bot.db.session import ensure_schema, make_engine
from bot.services.user_account import NO_RIGHT, refresh_chats

ENV = Path(__file__).resolve().parent.parent / ".env"


def copy_session() -> None:
    session = os.getenv("TG_SESSION", "")
    if not session:
        sys.exit("Avval login qiling: python -m bot.account_login")
    subprocess.run("clip", input=session.encode("utf-16-le"), check=True)
    print("Kalit nusxalandi. Vercel'da TG_SESSION qiymatiga joylang (Ctrl+V).")


async def login() -> None:
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    print("my.telegram.org > API development tools sahifasidagi qiymatlar:")
    api_id = int(input("App api_id: ").strip())
    api_hash = getpass.getpass("App api_hash (yozganingiz ko'rinmaydi): ").strip()

    client = TelegramClient(StringSession(), api_id, api_hash, receive_updates=False)
    await client.start(
        phone=lambda: input("Telefon raqam (+998...): ").strip(),
        code_callback=lambda: input("Telegram yuborgan kod: ").strip(),
        password=lambda: getpass.getpass("Ikki bosqichli parol (yozganingiz ko'rinmaydi): "),
    )
    me = await client.get_me()
    for key, value in (("TG_API_ID", str(api_id)), ("TG_API_HASH", api_hash), ("TG_SESSION", client.session.save())):
        set_key(str(ENV), key, value)
    print(f"\nKirildi: {me.first_name}. Kalit .env fayliga saqlandi.")

    print("Guruhlar tekshirilmoqda...")
    engine = make_engine(settings.database_url, serverless=True)
    await ensure_schema(engine)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        found = await refresh_chats(client, session)
        groups = (await session.scalars(select(Group).where(Group.is_active))).all()
    await engine.dispose()
    await client.disconnect()

    missing = [g.label for g in groups if g.chat_id not in found]
    no_right = [g.label for g in groups if found.get(g.chat_id) == NO_RIGHT]
    print(f"Tayyor guruhlar: {len(found) - len(no_right)} / {len(groups)}")
    if missing:
        print("Akkaunt a'zo emas: " + ", ".join(missing))
    if no_right:
        print("Odam qo'shish huquqi yo'q: " + ", ".join(no_right))
    print("\nKeyingi qadam: python -m bot.account_login --copy")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--copy" in sys.argv:
        copy_session()
    else:
        asyncio.run(login())
