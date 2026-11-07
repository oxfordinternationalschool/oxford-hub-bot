import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Chat, TelegramObject
from aiogram.types import User as TgUser

from bot.config import LANGS, settings
from bot.db.models import User
from bot.db.session import get_sessionmaker
from bot.services.topics import learn_topic

log = logging.getLogger(__name__)


class DbMiddleware(BaseMiddleware):
    """Opens a DB session per update and loads the sender as `user` (+ their `lang`).

    Users are created only when they write to the bot privately; in groups we just
    look them up, so 800 chatting students don't each get a row.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with get_sessionmaker()() as session:
            data["session"] = session
            tg_user: TgUser | None = data.get("event_from_user")
            chat: Chat | None = data.get("event_chat")
            user = None
            if tg_user and not tg_user.is_bot:
                user = await session.get(User, tg_user.id)
                if user is None and chat is not None and chat.type == "private":
                    lang = (tg_user.language_code or "")[:2]
                    user = User(
                        id=tg_user.id,
                        full_name=tg_user.full_name,
                        username=tg_user.username,
                        lang=lang if lang in LANGS else settings.default_lang,
                    )
                    session.add(user)
                    await session.commit()
                if user is not None:
                    changed = False
                    if user.full_name != tg_user.full_name or user.username != tg_user.username:
                        user.full_name, user.username = tg_user.full_name, tg_user.username
                        changed = True
                    if user.id in settings.admin_ids and not user.is_admin:
                        user.is_admin = True
                        changed = True
                    if changed:
                        await session.commit()
            data["user"] = user
            data["lang"] = user.lang if user else settings.default_lang
            return await handler(event, data)


class TopicLearner(BaseMiddleware):
    """Remembers the topics of groups with topics from the messages written in them
    (Telegram has no way for bots to list them). Runs before the handlers, for every message."""

    async def __call__(self, handler, event, data):
        session = data.get("session")
        if session is not None and getattr(event, "chat", None) is not None and event.chat.type == "supergroup":
            try:
                await learn_topic(session, event)
            except Exception:
                log.exception("Could not remember a topic")
                await session.rollback()
        return await handler(event, data)
