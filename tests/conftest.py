import io
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
    CopyMessage, CopyMessages, CreateChatInviteLink, DeleteMessage, EditEphemeralMessageText, ForwardMessage, ForwardMessages,
    GetChatAdministrators, GetChatMember, SavePreparedKeyboardButton,
    GetFile, GetMe, GetWebhookInfo, PostStory, PromoteChatMember, SendDocument, SendMediaGroup, SendMessage, SendPhoto,
    SendRichMessage, SendVideo, SendVoice,
)
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    Chat, ChatInviteLink, ChatMemberAdministrator, ChatMemberLeft, ChatMemberMember, ChatMemberOwner, Document, File, InputMediaPhoto, Message, MessageId,
    PhotoSize, PreparedKeyboardButton, Story, Update, User, Video, Voice, WebhookInfo,
)
from PIL import Image

from bot.app import get_dispatcher
from bot.db.session import init_db, make_engine, reset_sessionmaker, use_sessionmaker
from bot.services.roles import trigger_cache

BOT_USER = {"id": 999, "is_bot": True, "first_name": "Bot", "username": "school_bot"}


def _jpeg(size=(640, 480)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, (30, 90, 160)).save(out, "JPEG")
    return out.getvalue()


# What every file "downloaded" from the fake Telegram contains: a real (landscape) photo.
FAKE_FILE = _jpeg()
SECRET = "test-secret-0123456789"


class FakeSession(BaseSession):
    """Records every Bot API call instead of sending it to Telegram."""

    def __init__(self):
        super().__init__()
        self.requests = []
        self._ids = itertools.count(1000)
        self.reject_rich = False  # simulate a chat where Telegram refuses rich messages
        self.reject_copy = False  # simulate a message Telegram won't let bots copy
        self.reject_delete = False  # simulate a group where the bot may not delete messages
        self.reject_ephemeral_edit = False  # simulate an ephemeral message that has expired
        self.reject_ephemeral = False  # simulate Telegram refusing ephemeral messages
        self.reject_invite = False  # simulate a group where the bot may not invite users
        self.ephemeral_ids = itertools.count(1)
        # (chat_id, user_id) -> chat member fields; the bot is an admin with every right, others are members.
        self.members: dict[tuple[int, int], dict] = {}

    async def make_request(self, bot, method, timeout=None):
        self.requests.append(method)
        if isinstance(method, GetMe):
            return User(**BOT_USER)
        if isinstance(method, GetWebhookInfo):
            return WebhookInfo(url="", has_custom_certificate=False, pending_update_count=0)
        if isinstance(method, SendMessage):
            if method.ephemeral_message_parameters or (method.reply_parameters and method.reply_parameters.ephemeral_message_id):
                if self.reject_ephemeral:
                    raise TelegramBadRequest(method=method, message="Bad Request: not enough rights to send ephemeral messages")
                return Message(message_id=0, ephemeral_message_id=next(self.ephemeral_ids), date=datetime.now(),
                               chat=Chat(id=method.chat_id, type="supergroup"), text=method.text)
            return Message(
                message_id=next(self._ids),
                date=datetime.now(),
                chat=Chat(id=method.chat_id, type="private"),
                text=method.text,
            )
        if isinstance(method, DeleteMessage) and self.reject_delete:
            raise TelegramBadRequest(method=method, message="Bad Request: message can't be deleted")
        if isinstance(method, EditEphemeralMessageText) and self.reject_ephemeral_edit:
            raise TelegramBadRequest(method=method, message="Bad Request: message to edit not found")
        if isinstance(method, GetChatMember):
            return self.member(method.chat_id, method.user_id)
        if isinstance(method, GetChatAdministrators):
            ids = [BOT_USER["id"]] + [uid for (cid, uid), m in self.members.items()
                                      if cid == method.chat_id and m["status"] in ("administrator", "creator")]
            return [self.member(method.chat_id, uid) for uid in ids]
        if isinstance(method, CreateChatInviteLink):
            if self.reject_invite:
                raise TelegramBadRequest(method=method, message="Bad Request: not enough rights to invite users")
            return ChatInviteLink(invite_link=f"https://t.me/+link{next(self._ids)}", creator=User(**BOT_USER),
                                  creates_join_request=False, is_primary=False, is_revoked=False, name=method.name,
                                  member_limit=method.member_limit, expire_date=method.expire_date)
        if isinstance(method, SavePreparedKeyboardButton):
            return PreparedKeyboardButton(id=f"pkb{next(self._ids)}")
        if isinstance(method, PromoteChatMember):
            self.set_member(method.chat_id, method.user_id, "administrator" if method.can_manage_chat else "member",
                            can_be_edited=True)
        if isinstance(method, (SendPhoto, SendVoice, SendDocument, SendVideo)):
            return self._media_message(method.chat_id, type(method).__name__[4:].lower())
        if isinstance(method, SendRichMessage):
            if self.reject_rich:
                raise TelegramBadRequest(method=method, message="Bad Request: rich messages are not allowed")
            return Message(message_id=next(self._ids), date=datetime.now(), chat=Chat(id=method.chat_id, type="group"))
        if isinstance(method, SendMediaGroup):
            return [self._media_message(method.chat_id, "photo" if isinstance(m, InputMediaPhoto) else "video")
                    for m in method.media]
        if isinstance(method, GetFile):
            return File(file_id=method.file_id, file_unique_id="u", file_path=f"thumbs/{method.file_id}.jpg")
        if isinstance(method, (CopyMessage, CopyMessages)) and self.reject_copy:
            raise TelegramBadRequest(method=method, message="Bad Request: message can't be copied")
        if isinstance(method, CopyMessage):
            return MessageId(message_id=next(self._ids))
        if isinstance(method, (CopyMessages, ForwardMessages)):
            return [MessageId(message_id=next(self._ids)) for _ in method.message_ids]
        if isinstance(method, PostStory):
            return Story(chat=Chat(id=77, type="private"), id=next(self._ids))
        if isinstance(method, ForwardMessage):
            return Message(message_id=next(self._ids), date=datetime.now(), chat=Chat(id=method.chat_id, type="group"))
        return True

    def set_member(self, chat_id, user_id, status, **fields):
        self.members[(chat_id, user_id)] = {"status": status, **fields}

    def member(self, chat_id, user_id):
        info = dict(self.members.get((chat_id, user_id)) or {})
        if not info:
            info = {"status": "administrator", "can_promote_members": True} if user_id == BOT_USER["id"] else {"status": "member"}
        status = info.pop("status")
        user = User(**BOT_USER) if user_id == BOT_USER["id"] else User(id=user_id, is_bot=False, first_name=f"User{user_id}")
        if status == "administrator":
            rights = dict.fromkeys((
                "can_be_edited", "is_anonymous", "can_manage_chat", "can_delete_messages", "can_manage_video_chats",
                "can_restrict_members", "can_promote_members", "can_change_info", "can_invite_users",
                "can_post_stories", "can_edit_stories", "can_delete_stories", "can_send_welcome_messages",
                "can_pin_messages",
            ), True)
            rights.update(is_anonymous=False, can_be_edited=False)
            rights.update(info)
            return ChatMemberAdministrator(user=user, **rights)
        if status == "left":
            return ChatMemberLeft(user=user)
        if status == "creator":
            return ChatMemberOwner(user=user, is_anonymous=False)
        return ChatMemberMember(user=user)

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
        yield FAKE_FILE

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

    async def group(self, chat_id, uid, text, title="7-B sinf", reply_to=None, ephemeral=False, **media):
        """A group message; `ephemeral` is a command picked from the "/" menu, which only the bot sees.
        With media (e.g. photo=[...]) the text becomes the caption."""
        msg = {
            "message_id": next(self._ids), "date": int(time.time()),
            "chat": {"id": chat_id, "type": "supergroup", "title": title},
            "from": self._user(uid), **({"caption": text, **media} if media else {"text": text}),
        }
        if ephemeral:
            msg["ephemeral_message_id"], msg["message_id"] = msg["message_id"], 0
        if reply_to:
            msg["reply_to_message"] = reply_to
        await self._send("message", msg)
        return msg

    async def callback(self, uid, data, message_id=1, reply_to=None):
        message = {
            "message_id": message_id, "date": int(time.time()),
            "chat": {"id": uid, "type": "private"}, "from": BOT_USER, "text": "…",
        }
        if reply_to:
            message["reply_to_message"] = reply_to
        await self._send("callback_query", {
            "id": str(next(self._ids)), "from": self._user(uid), "chat_instance": "ci", "data": data, "message": message,
        })

    async def business_connection(self, uid, conn_id="bc1", enabled=True, stories=True):
        """`uid` connects the bot in their Telegram settings (Secretary Mode)."""
        await self._send("business_connection", {
            "id": conn_id, "user": self._user(uid), "user_chat_id": uid, "date": int(time.time()),
            "is_enabled": enabled, "rights": {"can_manage_stories": stories},
        })

    async def bot_added(self, chat_id, by_uid, title="7-B sinf", status="member"):
        await self._send("my_chat_member", {
            "chat": {"id": chat_id, "type": "supergroup", "title": title},
            "from": self._user(by_uid), "date": int(time.time()),
            "old_chat_member": {"status": "left", "user": BOT_USER},
            "new_chat_member": {"status": status, "user": BOT_USER},
        })

    async def joined(self, chat_id, uid, link=None, title="7-B sinf"):
        """`uid` joins the group, through `link` if given (a chat_member update)."""
        body = {
            "chat": {"id": chat_id, "type": "supergroup", "title": title},
            "from": self._user(uid), "date": int(time.time()),
            "old_chat_member": {"status": "left", "user": self._user(uid)},
            "new_chat_member": {"status": "member", "user": self._user(uid)},
        }
        if link:
            body["invite_link"] = {"invite_link": link, "creator": BOT_USER, "creates_join_request": False,
                                   "is_primary": False, "is_revoked": False}
        self.api.members.pop((chat_id, uid), None)  # a member from now on
        await self._send("chat_member", body)

    async def register(self, uid, start_arg=""):
        """/start + pick Uzbek, as a real user would."""
        await self.private(uid, f"/start {start_arg}".strip())
        await self.callback(uid, "lang:uz")


async def call_asgi(app, headers: dict[str, str], body: bytes = b"", method: str = "POST", query: str = "",
                    raw: bool = False):
    """(status, body text), or with `raw` (status, body bytes, content type)."""
    sent = []

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http", "method": method, "path": "/api", "query_string": query.encode(),
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    await app(scope, receive, send)
    if raw:
        return sent[0]["status"], sent[1]["body"], dict(sent[0]["headers"])[b"content-type"].decode()
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
    import bot.services.stories as stories_module
    import bot.webhook as webhook_module

    db_url = f"sqlite+aiosqlite:///{tmp_path / 'vercel.db'}"
    patched = dataclasses.replace(app_module.settings, database_url=db_url, webhook_secret=SECRET)
    monkeypatch.setattr(app_module, "settings", patched)
    monkeypatch.setattr(webhook_module, "settings", patched)
    monkeypatch.setattr(stories_module, "settings", patched)
    api = FakeSession()
    monkeypatch.setattr(app_module, "make_bot", lambda: Bot("999:TEST", session=api))

    engine = make_engine(db_url)
    sessionmaker = await init_db(engine)
    yield WebhookHarness(None, api, sessionmaker)
    await engine.dispose()
