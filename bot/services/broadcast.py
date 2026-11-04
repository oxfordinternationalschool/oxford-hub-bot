import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramMigrateToChat, TelegramRetryAfter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Announcement, AnnouncementMessage
from bot.services.common import migrate_group

log = logging.getLogger(__name__)

# Sends the announcement to one chat and returns the sent message (anything with .message_id),
# or a list of them when it takes several (media, then text that didn't fit in the caption).
Sender = Callable[[int], Awaitable]


class CopySender:
    """Copies a message, or every message of an album, exactly as it is (copy_messages keeps an
    album together). If Telegram won't copy it (protected content, or a kind bots can't copy),
    it forwards it instead and sets `forwarded`."""

    def __init__(self, bot: Bot, from_chat_id: int, message_ids: list[int]):
        self.bot, self.from_chat_id, self.ids = bot, from_chat_id, message_ids
        self.forwarded = False

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
    failed: list[int] = field(default_factory=list)
    pin_failed: list[int] = field(default_factory=list)

    @property
    def chats_reached(self) -> int:
        return len({chat_id for chat_id, _ in self.sent})


async def broadcast(bot: Bot, session: AsyncSession, chat_ids: list[int], pin: bool, send: Sender) -> BroadcastResult:
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
                log.warning("Broadcast to %s failed: %s", target, e)
                break

        if msg is None:
            result.failed.append(chat_id)
            continue
        msgs = msg if isinstance(msg, list) else [msg]
        result.sent.extend((target, m.message_id) for m in msgs)
        if pin:
            try:
                await bot.pin_chat_message(target, msgs[0].message_id)
            except TelegramAPIError:
                result.pin_failed.append(target)
        # Stay well under Telegram's ~30 messages/second limit.
        await asyncio.sleep(0.1)
    return result


async def save_announcement(
    session: AsyncSession, author_id: int, pin: bool, preview: str, result: BroadcastResult,
    story_file_id: str | None = None, story_caption: str | None = None,
) -> Announcement:
    ann = Announcement(author_id=author_id, pinned=pin, preview=preview[:200],
                       story_file_id=story_file_id, story_caption=story_caption)
    session.add(ann)
    await session.flush()
    for chat_id, message_id in result.sent:
        session.add(AnnouncementMessage(announcement_id=ann.id, chat_id=chat_id, message_id=message_id))
    await session.commit()
    return ann


async def delete_announcement(bot: Bot, session: AsyncSession, ann: Announcement) -> tuple[int, int]:
    """Removes the announcement from every group. Returns (deleted, total)."""
    msgs = (await session.scalars(
        select(AnnouncementMessage).where(AnnouncementMessage.announcement_id == ann.id)
    )).all()
    deleted = 0
    for m in msgs:
        try:
            await bot.delete_message(m.chat_id, m.message_id)
            deleted += 1
        except TelegramAPIError:
            pass
    ann.deleted = True
    await session.commit()
    return deleted, len(msgs)
