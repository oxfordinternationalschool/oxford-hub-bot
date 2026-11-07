"""Editing an announcement after it was sent: the text changes in every group that has it."""
import asyncio
import json
import logging
from dataclasses import dataclass, field

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Announcement, AnnouncementMessage
from bot.services.media import CAPTION_LIMIT, MEDIA_ICONS, rich_message

log = logging.getLogger(__name__)

TEXT_LIMIT = 4096


@dataclass
class EditResult:
    edited: list[int] = field(default_factory=list)  # chat ids
    failed: list[int] = field(default_factory=list)


async def text_messages(session: AsyncSession, ann: Announcement) -> list[AnnouncementMessage]:
    """The sent messages that hold the announcement's text (one per group, normally)."""
    return list((await session.scalars(select(AnnouncementMessage).where(
        AnnouncementMessage.announcement_id == ann.id, AnnouncementMessage.text_kind.is_not(None),
    ).order_by(AnnouncementMessage.id))).all())


def new_preview(old: str | None, plain: str) -> str:
    """The history line with the new text, keeping the attachment icons in front."""
    icons = set("".join(MEDIA_ICONS.values()) + "📎…️")
    old = old or ""
    i = 0
    while i < len(old) and old[i] in icons:
        i += 1
    return f"{old[:i]} {plain}".strip()


def edit_problem(ann: Announcement, msgs: list[AnnouncementMessage], plain: str) -> str | None:
    """Why this edit can't be done (an i18n key), or None."""
    if ann.deleted or not msgs:
        return "ann_not_editable"
    if not plain:
        return "webapp_text_empty"
    kinds = {m.text_kind for m in msgs}
    if "caption" in kinds and len(plain) > CAPTION_LIMIT:
        return "ann_edit_caption_long"
    if len(plain) > TEXT_LIMIT:
        return "ann_edit_too_long"
    if "rich" in kinds and not (ann.rich_media and ann.layout):
        return "ann_not_editable"
    return None


async def _edit_one(bot: Bot, m: AnnouncementMessage, html_text: str, rich) -> None:
    if m.text_kind == "caption":
        await bot.edit_message_caption(chat_id=m.chat_id, message_id=m.message_id, caption=html_text, parse_mode="HTML")
    elif m.text_kind == "rich":
        await bot.edit_message_text(chat_id=m.chat_id, message_id=m.message_id, rich_message=rich)
    else:
        await bot.edit_message_text(chat_id=m.chat_id, message_id=m.message_id, text=html_text, parse_mode="HTML")


async def edit_announcement(bot: Bot, session: AsyncSession, ann: Announcement, msgs: list[AnnouncementMessage],
                            html_text: str, preview: str) -> EditResult:
    rich = rich_message(json.loads(ann.rich_media), html_text, ann.layout) if ann.rich_media and ann.layout else None
    result = EditResult()
    for m in msgs:
        for _attempt in range(2):
            try:
                await _edit_one(bot, m, html_text, rich)
                result.edited.append(m.chat_id)
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
                continue
            except TelegramAPIError as e:
                if "not modified" in str(e).lower():
                    result.edited.append(m.chat_id)
                else:
                    log.warning("Cannot edit announcement %s in %s: %s", ann.id, m.chat_id, e)
                    result.failed.append(m.chat_id)
            break
    ann.html = html_text
    ann.preview = preview[:200]
    if ann.story_caption is not None:
        ann.story_caption = html_text
    await session.commit()
    return result
