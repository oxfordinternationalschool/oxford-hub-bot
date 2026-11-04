"""The school's Telegram account connecting the bot (Secretary Mode), and announcements as stories."""
import contextlib
import logging

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BusinessConnection, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.callbacks import AnnDelCb, StoryAccCb, StoryCb
from bot.config import utcnow
from bot.db.models import Announcement, StoryAccount, User
from bot.filters import can_announce, is_admin
from bot.i18n import t
from bot.services.common import admin_users, q
from bot.services.stories import STORY_HOURS, post_story, story_account

log = logging.getLogger(__name__)
router = Router(name="stories")


def report_keyboard(lang: str, ann_id: int, story: str | None = None, deletable: bool = True):
    """Buttons under an announcement report: the story offer ("offer") or its duration choice
    ("pick"), and deleting it from every group."""
    kb = InlineKeyboardBuilder()
    if story == "offer":
        kb.button(text=t(lang, "story_btn"), callback_data=StoryCb(ann=ann_id))
    elif story == "pick":
        for hours in STORY_HOURS:
            kb.button(text=t(lang, "story_hours", h=hours), callback_data=StoryCb(ann=ann_id, h=hours))
    if deletable:
        kb.button(text=t(lang, "ann_delete_all"), callback_data=AnnDelCb(ann_id=ann_id))
    kb.adjust(len(STORY_HOURS) if story == "pick" else 1, 1)
    return kb.as_markup() if story or deletable else None


async def _right_line(bot: Bot, lang: str, account: StoryAccount) -> str:
    if account.can_post:
        return t(lang, "story_right_yes")
    return t(lang, "story_right_no", bot=(await bot.me()).username)


async def _tell_admins(bot: Bot, session: AsyncSession, key: str, account: StoryAccount, ask: bool = False) -> None:
    for admin in await admin_users(session):
        kb = None
        if ask:
            b = InlineKeyboardBuilder()
            b.button(text=t(admin.lang, "story_acc_yes"), callback_data=StoryAccCb(a="ok", id=account.id))
            b.button(text=t(admin.lang, "story_acc_no"), callback_data=StoryAccCb(a="no", id=account.id))
            kb = b.as_markup()
        text = t(admin.lang, key, name=q(account.name), right=await _right_line(bot, admin.lang, account))
        try:
            await bot.send_message(admin.id, text, reply_markup=kb)
        except TelegramAPIError as e:
            log.warning("Cannot notify admin %s: %s", admin.id, e)


@router.business_connection()
async def on_connection(conn: BusinessConnection, session: AsyncSession, bot: Bot):
    """Someone connected, changed or removed the bot in their Telegram settings."""
    account = await session.scalar(select(StoryAccount).where(StoryAccount.connection_id == conn.id))
    before = (account.is_enabled, account.can_post) if account else None
    if account is None:
        account = StoryAccount(connection_id=conn.id)
        session.add(account)
    account.user_id = conn.user.id
    account.name = conn.user.full_name + (f" (@{conn.user.username})" if conn.user.username else "")
    account.can_post = bool(conn.rights and conn.rights.can_manage_stories)
    account.is_enabled = conn.is_enabled
    account.updated_at = utcnow()
    await session.commit()

    if before == (account.is_enabled, account.can_post):
        return  # only rights the bot doesn't use changed
    if not account.is_enabled:
        if account.approved:
            await _tell_admins(bot, session, "story_disconnected", account)
    elif account.approved:
        await _tell_admins(bot, session, "story_status", account)
    else:
        await _tell_admins(bot, session, "story_connected", account, ask=True)


@router.callback_query(StoryAccCb.filter())
async def on_account_answer(
    cb: CallbackQuery, callback_data: StoryAccCb, session: AsyncSession, user: User | None, bot: Bot, lang: str
):
    if not is_admin(user):
        await cb.answer(t(lang, "cannot_do"), show_alert=True)
        return
    account = await session.get(StoryAccount, callback_data.id)
    if account is None:
        await cb.answer(t(lang, "expired"), show_alert=True)
        return
    if callback_data.a == "ok":
        for other in (await session.scalars(select(StoryAccount))).all():
            other.approved = other.id == account.id  # one school account at a time
        text = t(lang, "story_approved", name=q(account.name))
        if not account.can_post:
            text += "\n\n" + await _right_line(bot, lang, account)
    else:
        account.approved = False
        text = t(lang, "story_rejected", name=q(account.name))
    await session.commit()
    with contextlib.suppress(TelegramAPIError):
        await cb.message.edit_text(text)
    await cb.answer()


@router.callback_query(StoryCb.filter())
async def on_story(cb: CallbackQuery, callback_data: StoryCb, session: AsyncSession, user: User | None, bot: Bot,
                   lang: str):
    ann = await session.get(Announcement, callback_data.ann)
    if ann is None or not can_announce(user) or (ann.author_id != user.id and not is_admin(user)):
        await cb.answer(t(lang, "cannot_do"), show_alert=True)
        return
    account = await story_account(session)
    if account is None or not ann.story_file_id:
        await cb.answer(t(lang, "story_unavailable"), show_alert=True)
        return
    if callback_data.h not in STORY_HOURS:  # first tap: ask how long it should stay up
        with contextlib.suppress(TelegramAPIError):
            await cb.message.edit_reply_markup(reply_markup=report_keyboard(lang, ann.id, "pick", not ann.deleted))
        await cb.answer()
        return

    await cb.answer(t(lang, "story_posting"))
    try:
        await post_story(bot, account, ann.story_file_id, ann.story_caption, callback_data.h)
    except (TelegramAPIError, OSError) as e:  # OSError: a photo Pillow can't read
        log.warning("Story for announcement %s failed: %s", ann.id, e)
        await cb.message.answer(t(lang, "story_failed", error=q(str(e))))
        return
    with contextlib.suppress(TelegramAPIError):
        await cb.message.edit_text(
            cb.message.html_text + "\n" + t(lang, "story_done", name=q(account.name), h=callback_data.h),
            reply_markup=report_keyboard(lang, ann.id, None, not ann.deleted),
        )
