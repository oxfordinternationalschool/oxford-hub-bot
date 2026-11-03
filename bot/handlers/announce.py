import contextlib

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.callbacks import AnnCb, AnnDelCb
from bot.db.models import Announcement, Group, MediaDraft, User
from bot.filters import CanAnnounce, can_announce, is_admin
from bot.i18n import t
from bot.services.broadcast import broadcast, delete_announcement, save_announcement
from bot.services.common import group_sort_key, q
from bot.services.media import describe_media

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


MEDIA = F.photo | F.video | F.voice | F.audio | F.document | F.video_note | F.animation


@router.message(StateFilter(None), MEDIA, CanAnnounce())
async def save_media_draft(message: Message, session: AsyncSession, user: User, lang: str):
    """Media sent to the bot outside a conversation becomes an attachment for the Mini App."""
    info = describe_media(message)
    session.add(MediaDraft(
        user_id=user.id, chat_id=message.chat.id, message_id=message.message_id,
        kind=info.kind, caption=message.caption, file_name=info.file_name, duration=info.duration,
        file_id=info.file_id, thumb_file_id=info.thumb_file_id,
    ))
    await session.commit()
    await message.reply(t(lang, "draft_saved", kind=t(lang, f"media_{info.kind}")))


@router.message(AnnounceSG.content)
async def on_content(message: Message, state: FSMContext, session: AsyncSession, lang: str):
    if message.text and message.text.startswith("/"):
        await message.answer(t(lang, "ann_send_content"))
        return
    if message.media_group_id:
        data = await state.get_data()
        if data.get("warned_album") != message.media_group_id:
            await state.update_data(warned_album=message.media_group_id)
            await message.answer(t(lang, "ann_no_albums"))
        return
    groups = await active_groups(session)
    preview = message.text or message.caption or "📎"
    await state.update_data(
        src_chat=message.chat.id, src_msg=message.message_id, preview=preview[:200], selected=[], pin=False,
    )
    await state.set_state(AnnounceSG.targets)
    await message.answer(
        t(lang, "ann_choose", n=0),
        reply_markup=_targets_keyboard(lang, groups, set(), False),
    )


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


async def _do_send(status_msg: Message, session: AsyncSession, bot: Bot, user: User, lang: str,
                   data: dict, chat_ids: list[int], pin: bool) -> None:
    result = await broadcast(
        bot, session, chat_ids, pin,
        send=lambda chat_id: bot.copy_message(chat_id, data["src_chat"], data["src_msg"]),
    )
    ann = await save_announcement(session, user.id, pin, data.get("preview", ""), result)

    labels = {g.chat_id: g.label for g in await active_groups(session)}
    lines = [t(lang, "ann_report", sent=result.chats_reached, total=len(chat_ids))]
    if result.failed:
        names = ", ".join(q(labels.get(c, str(c))) for c in result.failed)
        lines.append(t(lang, "ann_failed", names=names))
    if result.pin_failed:
        names = ", ".join(q(labels.get(c, str(c))) for c in result.pin_failed)
        lines.append(t(lang, "ann_pin_failed", names=names))

    kb = InlineKeyboardBuilder()
    if result.sent:
        kb.button(text=t(lang, "ann_delete_all"), callback_data=AnnDelCb(ann_id=ann.id))
    await status_msg.edit_text("\n".join(lines), reply_markup=kb.as_markup() if result.sent else None)


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
