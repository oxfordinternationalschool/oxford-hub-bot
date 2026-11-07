import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramMigrateToChat, TelegramRetryAfter
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Announcement, AnnouncementMessage, Group
from bot.services.common import migrate_group
from bot.services.topics import announce_threads, stop_announce_threads, topic_gone

log = logging.getLogger(__name__)

# Sends the announcement to one chat and returns the sent message (anything with .message_id),
# or a list of them when it takes several (media, then text that didn't fit in the caption).
Sender = Callable[[int], Awaitable]


class CopySender:
    """Copies a message, or every message of an album, exactly as it is (copy_messages keeps an
    album together). If Telegram won't copy it (protected content, or a kind bots can't copy),
    it forwards it instead and sets `forwarded`."""

    def __init__(self, bot: Bot, from_chat_id: int, message_ids: list[int], kinds: list[str | None] | None = None):
        self.bot, self.from_chat_id, self.ids = bot, from_chat_id, message_ids
        self.forwarded = False
        # Where each copied message has its text ("text"/"caption"/None): Telegram returns only ids.
        self._kinds = kinds or [None] * len(message_ids)

    @property
    def kinds(self) -> list[str | None]:
        return [None] * len(self.ids) if self.forwarded else self._kinds  # forwards can't be edited

    async def __call__(self, chat_id: int):
        if not self.forwarded:
            try:
                if len(self.ids) == 1:
                    return await self.bot.copy_message(chat_id, self.from_chat_id, self.ids[0])
                return await self.bot.copy_messages(chat_id, self.from_chat_id, self.ids)
            except TelegramBadRequest as e:
                # Only a problem with the message itself; a problem with this chat fails as usual.
                if "cop" not in e.message.lower():
                    raise
                self.forwarded = True
        if len(self.ids) == 1:
            return await self.bot.forward_message(chat_id, self.from_chat_id, self.ids[0])
        return await self.bot.forward_messages(chat_id, self.from_chat_id, self.ids)


@dataclass
class BroadcastResult:
    sent: list[tuple[int, int]] = field(default_factory=list)  # (chat_id, message_id), every message
    kinds: dict[tuple[int, int], str] = field(default_factory=dict)  # where a sent message has its text
    failed: list[int] = field(default_factory=list)
    pin_failed: list[int] = field(default_factory=list)

    @property
    def chats_reached(self) -> int:
        return len({chat_id for chat_id, _ in self.sent})


async def broadcast(bot: Bot, session: AsyncSession, chat_ids: list[int], pin: bool, send: Sender) -> BroadcastResult:
    # Groups with topics get it in their chosen announcement topic.
    threads = await announce_threads(bot, session, chat_ids)
    try:
        return await _broadcast(bot, session, chat_ids, pin, send, threads)
    finally:
        stop_announce_threads()


async def _broadcast(bot: Bot, session: AsyncSession, chat_ids: list[int], pin: bool, send: Sender,
                     threads: dict[int, int]) -> BroadcastResult:
    result = BroadcastResult()
    for chat_id in chat_ids:
        target = chat_id
        msg = None
        for _attempt in range(3):
            try:
                msg = await send(target)
                break
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
            except TelegramMigrateToChat as e:
                await migrate_group(session, target, e.migrate_to_chat_id)
                target = e.migrate_to_chat_id
            except TelegramAPIError as e:
                if target in threads and topic_gone(e):
                    # The announcement topic is closed or deleted: send to General instead,
                    # and forget a deleted topic.
                    log.warning("Announcement topic of %s is unavailable: %s", target, e)
                    threads.pop(target)
                    if "not found" in str(e).lower():
                        await session.execute(update(Group).where(Group.chat_id == target).values(announce_thread_id=None))
                        await session.commit()
                    continue
                log.warning("Broadcast to %s failed: %s", target, e)
                break

        if msg is None:
            result.failed.append(chat_id)
            continue
        msgs = msg if isinstance(msg, list) else [msg]
        result.sent.extend((target, m.message_id) for m in msgs)
        known = getattr(send, "kinds", None)
        for i, m in enumerate(msgs):
            kind = text_kind(m) or (known[i] if known and i < len(known) else None)
            if kind:
                result.kinds[(target, m.message_id)] = kind
        if pin:
            try:
                await bot.pin_chat_message(target, msgs[0].message_id)
            except TelegramAPIError:
                result.pin_failed.append(target)
        # Stay well under Telegram's ~30 messages/second limit.
        await asyncio.sleep(0.1)
    return result


@dataclass
class Tagged:
    """A sent message whose kind of text the sender knows (Telegram's reply doesn't say)."""
    message_id: int
    kind: str


def text_kind(message) -> str | None:
    """Where a sent Message has its text; None for a bare MessageId (copies) or no text."""
    if isinstance(message, Tagged):
        return message.kind
    if getattr(message, "rich_message", None):
        return "rich"
    if getattr(message, "text", None):
        return "text"
    if getattr(message, "caption", None):
        return "caption"
    return None


async def save_announcement(
    session: AsyncSession, author_id: int, pin: bool, preview: str, result: BroadcastResult,
    story_file_id: str | None = None, story_caption: str | None = None,
    html: str | None = None, layout: str | None = None, rich_media: str | None = None,
) -> Announcement:
    ann = Announcement(author_id=author_id, pinned=pin, preview=preview[:200],
                       story_file_id=story_file_id, story_caption=story_caption,
                       html=html, layout=layout, rich_media=rich_media)
    session.add(ann)
    await session.flush()
    for chat_id, message_id in result.sent:
        session.add(AnnouncementMessage(announcement_id=ann.id, chat_id=chat_id, message_id=message_id,
                                        text_kind=result.kinds.get((chat_id, message_id))))
    await session.commit()
    return ann


async def delete_announcement(
    bot: Bot, session: AsyncSession, ann: Announcement, chat_ids: list[int] | None = None,
) -> tuple[int, int]:
    """Removes the announcement from the given groups (every group if None).
    Returns (messages deleted, messages tried); it counts as deleted once no group has it."""
    query = select(AnnouncementMessage).where(AnnouncementMessage.announcement_id == ann.id)
    if chat_ids is not None:
        query = query.where(AnnouncementMessage.chat_id.in_(chat_ids))
    msgs = (await session.scalars(query)).all()
    deleted = 0
    for m in msgs:
        try:
            await bot.delete_message(m.chat_id, m.message_id)
            deleted += 1
        except TelegramAPIError:
            pass
        await session.delete(m)  # gone from that group (or already gone)
    await session.flush()
    left = await session.scalar(select(AnnouncementMessage.id).where(AnnouncementMessage.announcement_id == ann.id).limit(1))
    if left is None:
        ann.deleted = True
    await session.commit()
    return deleted, len(msgs)
