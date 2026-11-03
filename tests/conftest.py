import itertools
import json
import os
import time
from datetime import datetime

# Must be set before bot.config is imported.
os.environ["BOT_TOKEN"] = "999:TEST"
os.environ["ADMIN_IDS"] = "1"
os.environ["DEFAULT_LANG"] = "uz"

import pytest
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import (
    CopyMessage, GetFile, GetMe, GetWebhookInfo, SendDocument, SendMediaGroup, SendMessage, SendPhoto, SendVideo, SendVoice,
)
from aiogram.types import (
    Chat, Document, File, InputMediaPhoto, Message, MessageId, PhotoSize, Update, User, Video, Voice, WebhookInfo,
)

from bot.app import get_dispatcher
from bot.db.session import init_db, make_engine, reset_sessionmaker, use_sessionmaker
from bot.services.roles import trigger_cache

BOT_USER = {"id": 999, "is_bot": True, "first_name": "Bot", "username": "school_bot"}
SECRET = "test-secret-0123456789"


class FakeSession(BaseSession):
    """Records every Bot API call instead of sending it to Telegram."""

    def __init__(self):
        super().__init__()
        self.requests = []
        self._ids = itertools.count(1000)

    async def make_request(self, bot, method, timeout=None):
        self.requests.append(method)
        if isinstance(method, GetMe):
            return User(**BOT_USER)
        if isinstance(method, GetWebhookInfo):
            return WebhookInfo(url="", has_custom_certificate=False, pending_update_count=0)
        if isinstance(method, SendMessage):
            return Message(
                message_id=next(self._ids),
                date=datetime.now(),
                chat=Chat(id=method.chat_id, type="private"),
                text=method.text,
            )
        if isinstance(method, (SendPhoto, SendVoice, SendDocument, SendVideo)):
            return self._media_message(method.chat_id, type(method).__name__[4:].lower())
        if isinstance(method, SendMediaGroup):
            return [self._media_message(method.chat_id, "photo" if isinstance(m, InputMediaPhoto) else "video")
                    for m in method.media]
        if isinstance(method, GetFile):
            return File(file_id=method.file_id, file_unique_id="u", file_path=f"thumbs/{method.file_id}.jpg")
        if isinstance(method, CopyMessage):
            return MessageId(message_id=next(self._ids))
        return True

    def _media_message(self, chat_id, kind):
        n = next(self._ids)
        fid, uid = f"{kind}{n}", f"u{n}"
        media = {
            "photo": {"photo": [PhotoSize(file_id=f"small{n}", file_unique_id=uid, width=90, height=90),
                                PhotoSize(file_id=fid, file_unique_id=uid, width=800, height=600)]},
            "voice": {"voice": Voice(file_id=fid, file_unique_id=uid, duration=1)},
            "document": {"document": Document(file_id=fid, file_unique_id=uid)},
            "video": {"video": Video(file_id=fid, file_unique_id=uid, width=1, height=1, duration=1)},
        }[kind]
        return Message(message_id=n, date=datetime.now(), chat=Chat(id=chat_id, type="group"), **media)

    async def stream_content(self, *args, **kwargs):
        yield b"tiny jpeg bytes"

    async def close(self):
        pass

    def sent(self, chat_id=None, kind=SendMessage):
        return [r for r in self.requests if isinstance(r, kind) and (chat_id is None or r.chat_id == chat_id)]


class Harness:
    """Feeds fake Telegram updates straight into the dispatcher (local/polling path)."""

    def __init__(self, bot, api, sessionmaker):
        self.bot, self.api, self.sessionmaker = bot, api, sessionmaker
        self._ids = itertools.count(1)

    def _user(self, uid):
        return {"id": uid, "is_bot": False, "first_name": f"User{uid}", "username": f"user{uid}"}

    async def feed(self, payload: dict):
        token = use_sessionmaker(self.sessionmaker)
        try:
            update = Update.model_validate(payload, context={"bot": self.bot})
            await get_dispatcher().feed_update(self.bot, update)
        finally:
            reset_sessionmaker(token)

    async def _send(self, kind: str, body: dict):
        await self.feed({"update_id": next(self._ids), kind: body})

    async def private(self, uid, text):
        await self._send("message", {
            "message_id": next(self._ids), "date": int(time.time()),
            "chat": {"id": uid, "type": "private"}, "from": self._user(uid), "text": text,
        })

    async def private_media(self, uid, **media):
        """A private media message, e.g. voice={"file_id": "v", "file_unique_id": "u", "duration": 3}."""
        await self._send("message", {
            "message_id": next(self._ids), "date": int(time.time()),
            "chat": {"id": uid, "type": "private"}, "from": self._user(uid), **media,
        })

    async def group(self, chat_id, uid, text, title="7-B sinf", reply_to=None):
        msg = {
            "message_id": next(self._ids), "date": int(time.time()),
            "chat": {"id": chat_id, "type": "supergroup", "title": title},
            "from": self._user(uid), "text": text,
        }
        if reply_to:
            msg["reply_to_message"] = reply_to
        await self._send("message", msg)
        return msg

    async def callback(self, uid, data, message_id=1):
        await self._send("callback_query", {
            "id": str(next(self._ids)), "from": self._user(uid), "chat_instance": "ci", "data": data,
            "message": {
                "message_id": message_id, "date": int(time.time()),
                "chat": {"id": uid, "type": "private"}, "from": BOT_USER, "text": "…",
            },
        })

    async def bot_added(self, chat_id, by_uid, title="7-B sinf", status="member"):
        await self._send("my_chat_member", {
            "chat": {"id": chat_id, "type": "supergroup", "title": title},
            "from": self._user(by_uid), "date": int(time.time()),
            "old_chat_member": {"status": "left", "user": BOT_USER},
            "new_chat_member": {"status": status, "user": BOT_USER},
        })

    async def register(self, uid, start_arg=""):
        """/start + pick Uzbek, as a real user would."""
        await self.private(uid, f"/start {start_arg}".strip())
        await self.callback(uid, "lang:uz")


async def call_asgi(app, headers: dict[str, str], body: bytes = b"", method: str = "POST"):
    sent = []

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http", "method": method, "path": "/api",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    await app(scope, receive, send)
    return sent[0]["status"], sent[1]["body"].decode()


class WebhookHarness(Harness):
    """Same helpers, but every update goes through the Vercel ASGI app as an HTTP request,
    each with its own engine and bot — like separate serverless invocations."""

    async def feed(self, payload: dict):
        from bot.webhook import app

        status, _ = await call_asgi(
            app, {"X-Telegram-Bot-Api-Secret-Token": SECRET}, json.dumps(payload).encode()
        )
        assert status == 200


@pytest.fixture(autouse=True)
def _fresh_trigger_cache():
    trigger_cache.invalidate()


@pytest.fixture
async def h(tmp_path):
    engine = make_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    sessionmaker = await init_db(engine)
    api = FakeSession()
    yield Harness(Bot("999:TEST", session=api), api, sessionmaker)
    await engine.dispose()


@pytest.fixture
async def wh(tmp_path, monkeypatch):
    import dataclasses

    import bot.app as app_module
    import bot.webhook as webhook_module

    db_url = f"sqlite+aiosqlite:///{tmp_path / 'vercel.db'}"
    patched = dataclasses.replace(app_module.settings, database_url=db_url, webhook_secret=SECRET)
    monkeypatch.setattr(app_module, "settings", patched)
    monkeypatch.setattr(webhook_module, "settings", patched)
    api = FakeSession()
    monkeypatch.setattr(app_module, "make_bot", lambda: Bot("999:TEST", session=api))

    engine = make_engine(db_url)
    sessionmaker = await init_db(engine)
    yield WebhookHarness(None, api, sessionmaker)
    await engine.dispose()
