"""Groups with topics (forums).

Telegram gives bots no list of a group's topics, so the bot learns them as it goes: a message
written in a topic carries the topic's id, and usually the topic's creation message (with its
name) as the message it replies to. Creating or renaming a topic also arrives as a message.

Announcements go to the topic chosen for each group (General if none). While a broadcast runs,
a request middleware on the bot's session adds that topic to every message sent to the group,
so the many ways of sending (copy, album, rich message, text) need no changes of their own.
"""
import logging
from contextvars import ContextVar

from aiogram import Bot
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import utcnow
from bot.db.models import ForumTopic, Group

log = logging.getLogger(__name__)

_known: dict[tuple[int, int], str] = {}  # (chat_id, thread_id) -> name, already in the database
_threads: ContextVar[dict[int, int] | None] = ContextVar("announce_threads", default=None)


def topic_name(message: Message) -> str | None:
    if message.forum_topic_edited and message.forum_topic_edited.name:
        return message.forum_topic_edited.name
    for m in (message, message.reply_to_message):
        if m is not None and m.forum_topic_created:
            return m.forum_topic_created.name
    return None


def message_topic(message: Message) -> int | None:
    """The topic a group message is in; None for General or a group without topics."""
    return message.message_thread_id if message.is_topic_message else None


async def learn_topic(session: AsyncSession, message: Message) -> None:
    thread_id = message_topic(message)
    name = topic_name(message) if thread_id else None
    if not name:
        return
    key = (message.chat.id, thread_id)
    if _known.get(key) == name:
        return
    topic = await session.get(ForumTopic, key)
    if topic is None:
        session.add(ForumTopic(chat_id=message.chat.id, thread_id=thread_id, name=name[:128]))
    elif topic.name != name:
        topic.name, topic.updated_at = name[:128], utcnow()
    await session.commit()
    _known[key] = name


async def topics_by_chat(session: AsyncSession) -> dict[int, list[ForumTopic]]:
    out: dict[int, list[ForumTopic]] = {}
    for t in (await session.scalars(select(ForumTopic).order_by(ForumTopic.thread_id))).all():
        out.setdefault(t.chat_id, []).append(t)
    return out


def same_name(a: str, b: str) -> bool:
    return a.strip().casefold() == b.strip().casefold()


# ---------- Sending announcements into the chosen topic ----------

async def _into_topic(make_request, bot: Bot, method):
    threads = _threads.get()
    chat_id = getattr(method, "chat_id", None)
    if threads and chat_id in threads and "message_thread_id" in type(method).model_fields \
            and getattr(method, "message_thread_id", None) is None:
        method.message_thread_id = threads[chat_id]
    return await make_request(bot, method)


async def announce_threads(bot: Bot, session: AsyncSession, chat_ids: list[int]) -> dict[int, int]:
    """Starts sending into each group's announcement topic; returns chat_id -> topic (editable:
    drop a group from it to send there to General instead)."""
    if not getattr(bot.session, "_topics_middleware", False):
        bot.session.middleware(_into_topic)
        bot.session._topics_middleware = True
    rows = (await session.scalars(select(Group).where(
        Group.chat_id.in_(chat_ids), Group.announce_thread_id.is_not(None),
    ))).all()
    threads = {g.chat_id: g.announce_thread_id for g in rows}
    _threads.set(threads)
    return threads


def stop_announce_threads() -> None:
    _threads.set(None)


def topic_gone(error: Exception) -> bool:
    text = str(error).lower()
    return "thread not found" in text or ("topic" in text and ("not found" in text or "closed" in text or "deleted" in text))
