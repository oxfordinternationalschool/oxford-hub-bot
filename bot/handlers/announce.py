import contextlib
import html

from aiogram import Bot, F, Router
from aiogram.enums import ChatType, ContentType
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession

from bot.callbacks import AnnCb, AnnDelCb, FwdCb
from bot.db.models import AlbumLead, Announcement, Group, MediaDraft, User
from bot.filters import CanAnnounce, can_announce, is_admin
from bot.handlers.stories import report_keyboard
from bot.i18n import t
from bot.services.broadcast import CopySender, broadcast, delete_announcement, save_announcement
from bot.services.common import group_sort_key, q
from bot.services.media import describe_media, media_preview
from bot.services.stories import story_account, story_caption, story_photo

router = Router(name="announce")
router.message.filter(F.chat.type == ChatType.PRIVATE)


class AnnounceSG(StatesGroup):
    content = State()
    targets = State()


async def active_groups(session: AsyncSession) -> list[Group]:
    return sorted((await session.scalars(select(Group).where(Group.is_active))).all(), key=group_sort_key)


def _targets_keyboard(lang: str, groups: list[Group], selected: set[int], pin: bool):
    kb = InlineKeyboardBuilder()
    sizes = []

    all_ids = {g.chat_id for g in groups}
    mark = "✅ " if all_ids and all_ids <= selected else ""
    kb.button(text=f"{mark}{t(lang, 'ann_all', n=len(groups))}", callback_data=AnnCb(action="all"))
    sizes.append(1)

    grades = sorted({g.grade for g in groups if g.grade})
    for grade in grades:
        ids = {g.chat_id for g in groups if g.grade == grade}
        mark = "✅ " if ids <= selected else ""
        kb.button(text=f"{mark}{t(lang, 'ann_grade', grade=grade)}", callback_data=AnnCb(action="grade", value=grade))
    sizes += [4] * (len(grades) // 4) + ([len(grades) % 4] if len(grades) % 4 else [])

    for g in groups:
        mark = "✅ " if g.chat_id in selected else ""
        kb.button(text=f"{mark}{g.label}", callback_data=AnnCb(action="grp", value=g.chat_id))
    sizes += [4] * (len(groups) // 4) + ([len(groups) % 4] if len(groups) % 4 else [])

    kb.button(text=t(lang, "ann_pin_on" if pin else "ann_pin_off"), callback_data=AnnCb(action="pin"))
    sizes.append(1)
    kb.button(text=t(lang, "ann_send", n=len(selected)), callback_data=AnnCb(action="send"))
    kb.button(text=t(lang, "ann_cancel"), callback_data=AnnCb(action="cancel"))
    sizes.append(2)
    kb.adjust(*sizes)
    return kb.as_markup()


@router.message(Command("announce"), CanAnnounce())
async def cmd_announce(message: Message, state: FSMContext, session: AsyncSession, lang: str):
    if not await active_groups(session):
        await message.answer(t(lang, "groups_empty"))
        return
    await state.clear()
    await state.set_state(AnnounceSG.content)
    await message.answer(t(lang, "ann_send_content"))


MEDIA_KINDS = {
    ContentType.PHOTO, ContentType.VIDEO, ContentType.VOICE, ContentType.AUDIO, ContentType.DOCUMENT,
    ContentType.VIDEO_NOTE, ContentType.ANIMATION,
}
# What an announcement can be: anything a person writes or forwards, but not service messages.
COPYABLE = MEDIA_KINDS | {
    ContentType.TEXT, ContentType.STICKER, ContentType.POLL, ContentType.LOCATION, ContentType.VENUE,
    ContentType.CONTACT, ContentType.RICH_MESSAGE,
}


def _not_command(message: Message) -> bool:
    return not (message.text or "").startswith("/")


@router.message(StateFilter(None, AnnounceSG.content, AnnounceSG.targets), F.content_type.in_(COPYABLE),
                _not_command, CanAnnounce())
async def on_ready_message(message: Message, state: FSMContext, session: AsyncSession, user: User, lang: str):
    """A finished announcement sent or forwarded to the bot goes to groups exactly as it is.

    After /announce the group picker opens at once; otherwise the bot offers a button, so a
    message sent by mistake goes nowhere. Media is also kept as a Mini App attachment."""
    kind = None
    if message.content_type in MEDIA_KINDS:
        info = describe_media(message)
        kind = info.kind
        session.add(MediaDraft(
            user_id=user.id, chat_id=message.chat.id, message_id=message.message_id,
            kind=info.kind, caption=message.caption, file_name=info.file_name, duration=info.duration,
            file_id=info.file_id, thumb_file_id=info.thumb_file_id, media_group_id=message.media_group_id,
        ))
        await session.commit()
    # Only one item of an album answers; the others are found by media_group_id when it's sent.
    if message.media_group_id and not await _album_lead(session, message):
        return

    if await state.get_state() == AnnounceSG.content:
        if not await active_groups(session):
            await state.clear()
            await message.answer(t(lang, "groups_empty"))
            return
        await _open_targets(message, state, session, lang, message.message_id, message.text or message.caption)
        return

    text = t(lang, "fwd_ask")
    if kind:
        text += "\n" + t(lang, "fwd_saved_too", kind=t(lang, f"media_{kind}"))
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "fwd_btn"), callback_data=FwdCb(m=message.message_id))
    await message.reply(text, reply_markup=kb.as_markup())


async def _album_lead(session: AsyncSession, message: Message) -> bool:
    """True for the first item of this album to get here."""
    dialect = postgresql if session.bind.dialect.name == "postgresql" else sqlite
    result = await session.execute(
        dialect.insert(AlbumLead)
        .values(chat_id=message.chat.id, media_group_id=message.media_group_id)
        .on_conflict_do_nothing()
    )
    await session.commit()
    return result.rowcount == 1


async def _open_targets(message: Message, state: FSMContext, session: AsyncSession, lang: str,
                        src_msg: int, preview: str | None, edit: bool = False) -> None:
    groups = await active_groups(session)
    await state.set_state(AnnounceSG.targets)
    await state.set_data({
        "src_chat": message.chat.id, "src_msg": src_msg, "preview": (preview or "")[:200], "selected": [], "pin": False,
    })
    markup = _targets_keyboard(lang, groups, set(), False)
    if edit:
        await message.edit_text(t(lang, "ann_choose", n=0), reply_markup=markup)
    else:
        await message.answer(t(lang, "ann_choose", n=0), reply_markup=markup)


@router.callback_query(FwdCb.filter())
async def on_send_to_groups(
    cb: CallbackQuery, callback_data: FwdCb, state: FSMContext, session: AsyncSession, user: User | None, lang: str
):
    if not can_announce(user):
        await cb.answer(t(lang, "cannot_do"), show_alert=True)
        return
    if not await active_groups(session):
        await cb.answer(t(lang, "groups_empty"), show_alert=True)
        return
    # The button sits on the bot's reply to the message, so Telegram hands that message back too.
    src = cb.message.reply_to_message
    await _open_targets(cb.message, state, session, lang, callback_data.m, src and (src.text or src.caption), edit=True)
    await cb.answer()


@router.callback_query(AnnounceSG.targets, AnnCb.filter())
async def on_targets(
    cb: CallbackQuery, callback_data: AnnCb, state: FSMContext, session: AsyncSession, user: User, bot: Bot, lang: str
):
    if not can_announce(user):
        await cb.answer(t(lang, "cannot_do"), show_alert=True)
        return
    data = await state.get_data()
    selected: set[int] = set(data.get("selected", []))
    pin: bool = data.get("pin", False)
    groups = await active_groups(session)
    action = callback_data.action

    if action == "cancel":
        await state.clear()
        await cb.message.edit_text(t(lang, "cancelled"))
        await cb.answer()
        return

    if action == "send":
        if not selected:
            await cb.answer(t(lang, "ann_nothing_selected"), show_alert=True)
            return
        await state.clear()
        await cb.message.edit_text(t(lang, "ann_sending", n=len(selected)))
        await cb.answer()
        await _do_send(cb.message, session, bot, user, lang, data, [g.chat_id for g in groups if g.chat_id in selected], pin)
        return

    if action == "all":
        all_ids = {g.chat_id for g in groups}
        selected = set() if all_ids <= selected else all_ids
    elif action == "grade":
        ids = {g.chat_id for g in groups if g.grade == callback_data.value}
        selected = selected - ids if ids <= selected else selected | ids
    elif action == "grp":
        selected ^= {callback_data.value}
    elif action == "pin":
        pin = not pin

    await state.update_data(selected=list(selected), pin=pin)
    with contextlib.suppress(TelegramAPIError):
        await cb.message.edit_text(
            t(lang, "ann_choose", n=len(selected)),
            reply_markup=_targets_keyboard(lang, groups, selected, pin),
        )
    await cb.answer()


@router.callback_query(AnnCb.filter())
async def on_stale_targets(cb: CallbackQuery, lang: str):
    # Buttons of a draft whose state is gone (finished, cancelled or bot restarted).
    with contextlib.suppress(TelegramAPIError):
        await cb.message.edit_reply_markup(reply_markup=None)
    await cb.answer(t(lang, "expired"), show_alert=True)


async def _source(session: AsyncSession, user: User, chat_id: int, msg_id: int) -> tuple[list[int], list[MediaDraft]]:
    """The messages to copy (the message itself, or every item of its album) and their drafts."""
    draft = await session.scalar(select(MediaDraft).where(
        MediaDraft.user_id == user.id, MediaDraft.chat_id == chat_id, MediaDraft.message_id == msg_id,
    ))
    if draft is None or not draft.media_group_id:
        return [msg_id], [draft] if draft else []
    album = (await session.scalars(select(MediaDraft).where(
        MediaDraft.user_id == user.id, MediaDraft.chat_id == chat_id, MediaDraft.media_group_id == draft.media_group_id,
    ).order_by(MediaDraft.message_id))).all()
    return [d.message_id for d in album], list(album)


async def _do_send(status_msg: Message, session: AsyncSession, bot: Bot, user: User, lang: str,
                   data: dict, chat_ids: list[int], pin: bool) -> None:
    ids, drafts = await _source(session, user, data["src_chat"], data["src_msg"])
    send = CopySender(bot, data["src_chat"], ids)
    result = await broadcast(bot, session, chat_ids, pin, send=send)
    photo = story_photo(drafts)
    caption = next((d.caption for d in drafts if d.caption), "")
    ann = await save_announcement(session, user.id, pin, media_preview(drafts, data.get("preview", "")), result,
                                  story_file_id=photo, story_caption=story_caption(html.escape(caption, quote=False), caption))

    labels = {g.chat_id: g.label for g in await active_groups(session)}
    lines = [t(lang, "ann_report", sent=result.chats_reached, total=len(chat_ids))]
    if result.failed:
        names = ", ".join(q(labels.get(c, str(c))) for c in result.failed)
        lines.append(t(lang, "ann_failed", names=names))
    if result.pin_failed:
        names = ", ".join(q(labels.get(c, str(c))) for c in result.pin_failed)
        lines.append(t(lang, "ann_pin_failed", names=names))
    if send.forwarded:
        lines.append(t(lang, "ann_forwarded"))

    markup = None
    if result.sent:
        story = "offer" if photo and await story_account(session) else None
        markup = report_keyboard(lang, ann.id, story)
    await status_msg.edit_text("\n".join(lines), reply_markup=markup)


@router.callback_query(AnnDelCb.filter())
async def on_delete_announcement(
    cb: CallbackQuery, callback_data: AnnDelCb, session: AsyncSession, user: User | None, bot: Bot, lang: str
):
    ann = await session.get(Announcement, callback_data.ann_id)
    if ann is None or user is None or (ann.author_id != user.id and not is_admin(user)):
        await cb.answer(t(lang, "cannot_do"), show_alert=True)
        return
    if ann.deleted:
        await cb.answer(t(lang, "ann_already_deleted"), show_alert=True)
        return
    await cb.answer()
    deleted, total = await delete_announcement(bot, session, ann)
    await cb.message.edit_text(t(lang, "ann_deleted", n=deleted, total=total))
