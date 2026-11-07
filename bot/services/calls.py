import asyncio
import contextlib
import logging
from datetime import timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import EphemeralMessageParameters, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.callbacks import CallCb
from bot.config import local_time, settings, utcnow
from bot.db.models import Call, CallMessage, Floor, Group, PendingDelete, Role, StaffRole, User
from bot.i18n import t
from bot.services.common import admin_users, q

log = logging.getLogger(__name__)

MEDIA_FIELDS = ("photo", "video", "document", "voice", "audio", "video_note", "animation")


def has_media(message: Message) -> bool:
    return any(getattr(message, f) for f in MEDIA_FIELDS)


async def find_recipients(session: AsyncSession, role: Role, group: Group) -> list[User]:
    """Staff of the role; for floor-based roles, those on the class's floor (or on all floors).
    Falls back to every staff member of the role if nobody covers that floor."""
    base = select(User).join(StaffRole, StaffRole.user_id == User.id).where(StaffRole.role_id == role.id)
    if role.floor_based and group.floor_id:
        on_floor = (await session.scalars(
            base.where(or_(StaffRole.floor_id == group.floor_id, StaffRole.floor_id.is_(None)))
        )).unique().all()
        if on_floor:
            return list(on_floor)
    return list((await session.scalars(base)).unique().all())


def message_link(chat_id: int, message_id: int) -> str | None:
    s = str(chat_id)
    if message_id and s.startswith("-100"):
        return f"https://t.me/c/{s[4:]}/{message_id}"
    return None


def render_card(
    lang: str,
    call: Call,
    role: Role | None,
    group: Group | None,
    floor: Floor | None,
    requester: User | None,
    accepter: User | None,
    viewer: User,
) -> tuple[str, InlineKeyboardMarkup | None]:
    role_title = role.title if role else "❔"
    lines = []
    if call.urgent:
        lines.append(t(lang, "card_urgent"))
    lines.append(t(lang, "card_title", role=q(role_title), id=call.id))
    class_line = q(group.label if group else str(call.chat_id))
    if floor:
        class_line += f" ({q(floor.name)})"
    lines.append(t(lang, "card_class", cls=class_line))
    lines.append(t(lang, "card_from", name=q(requester.full_name if requester else "—")))
    lines.append(t(lang, "card_time", time=local_time(call.created_at)))
    if call.text:
        lines.append(f"💬 {q(call.text)}")
    link = None if call.hidden else message_link(call.chat_id, call.trigger_message_id)
    if link:
        lines.append(f'🔗 <a href="{link}">{t(lang, "card_open")}</a>')
    lines.append("")

    kb = InlineKeyboardBuilder()
    accepter_name = q(accepter.full_name) if accepter else "—"
    if call.status == "pending":
        lines.append(t(lang, "st_pending_escalated" if call.escalated else "st_pending"))
        kb.button(text=t(lang, "btn_accept"), callback_data=CallCb(action="acc", call_id=call.id))
        if viewer.is_admin:
            kb.button(text=t(lang, "btn_close"), callback_data=CallCb(action="close", call_id=call.id))
    elif call.status == "accepted":
        time = local_time(call.accepted_at) if call.accepted_at else ""
        if accepter and accepter.id == viewer.id:
            lines.append(t(lang, "st_accepted_you", time=time))
            kb.button(text=t(lang, "btn_done"), callback_data=CallCb(action="done", call_id=call.id))
        else:
            lines.append(t(lang, "st_accepted", name=accepter_name, time=time))
    elif call.status == "done":
        time = local_time(call.done_at) if call.done_at else ""
        lines.append(t(lang, "st_done", name=accepter_name, time=time))
    else:
        lines.append(t(lang, "st_closed"))
    kb.adjust(2)
    markup = kb.as_markup() if kb.buttons else None
    return "\n".join(lines), markup


def render_group_status(lang: str, call: Call, role: Role | None, accepter: User | None) -> str:
    role_title = q(role.title if role else "❔")
    name = q(accepter.full_name) if accepter else "—"
    prefix = "🚨 " if call.urgent else ""
    key = {
        "pending": "grp_pending",
        "accepted": "grp_accepted",
        "done": "grp_done",
    }.get(call.status, "grp_closed")
    return prefix + t(lang, key, role=role_title, name=name)


async def _send_card(bot: Bot, session: AsyncSession, call: Call, user: User, ctx: dict) -> bool:
    text, markup = render_card(user.lang, call, viewer=user, **ctx)
    try:
        sent = await bot.send_message(user.id, text, reply_markup=markup)
    except TelegramAPIError as e:
        log.warning("Cannot deliver call %s to %s: %s", call.id, user.id, e)
        return False
    session.add(CallMessage(call_id=call.id, user_id=user.id, message_id=sent.message_id))
    return True


async def _context(session: AsyncSession, call: Call) -> dict:
    group = await session.get(Group, call.chat_id)
    return {
        "role": await session.get(Role, call.role_id) if call.role_id else None,
        "group": group,
        "floor": await session.get(Floor, group.floor_id) if group and group.floor_id else None,
        "requester": await session.get(User, call.requester_id),
        "accepter": await session.get(User, call.accepted_by) if call.accepted_by else None,
    }


async def dispatch_call(
    bot: Bot,
    session: AsyncSession,
    *,
    message: Message,
    group: Group,
    role: Role,
    text: str,
    urgent: bool,
    hidden: bool = False,
) -> None:
    reply = message.reply_to_message
    if reply and not reply.forum_topic_created:
        quoted = (reply.text or reply.caption or "").strip()
        if quoted:
            text = (text + "\n" if text else "") + "↩️ " + quoted[:300]

    call = Call(
        role_id=role.id,
        chat_id=group.chat_id,
        requester_id=message.from_user.id,
        text=text,
        urgent=urgent,
        trigger_message_id=message.message_id,
        hidden=hidden,
        thread_id=message.message_thread_id if message.is_topic_message else None,
    )
    session.add(call)
    await session.commit()

    recipients = await find_recipients(session, role, group)
    ctx = await _context(session, call)

    # Photos/files attached to the call (or to the message replied to) go along with the card.
    # An ephemeral message has no regular id (0) and can't be copied.
    media_sources = [m.message_id for m in (message, reply) if m is not None and m.message_id and has_media(m)]

    delivered = 0
    for user in recipients:
        for src in media_sources:
            try:
                await bot.copy_message(user.id, group.chat_id, src)
            except TelegramAPIError:
                pass
        if await _send_card(bot, session, call, user, ctx):
            delivered += 1
        await asyncio.sleep(0.05)

    if delivered:
        status = render_group_status(group.lang, call, role, None)
    else:
        status = t(group.lang, "grp_nostaff", role=q(role.title))
        call.escalated = True
    await _post_status(bot, session, message, call, status)
    await session.commit()

    if not delivered:
        await _escalate(bot, session, call, ctx, reason_key="esc_nostaff")


def to_user(user_id: int) -> EphemeralMessageParameters:
    """Makes a group message visible only to this user (and the bot)."""
    return EphemeralMessageParameters(receiver_user_id=user_id)


async def _remember_status(session: AsyncSession, call: Call, ephemeral_id: int | None) -> None:
    # Telegram reuses an ephemeral message's id once it expires; an older call holding the
    # same id must then stop editing it, or it would overwrite this call's status.
    if ephemeral_id is not None:
        await session.execute(update(Call).where(
            Call.chat_id == call.chat_id, Call.requester_id == call.requester_id,
            Call.status_ephemeral_id == ephemeral_id, Call.id != call.id,
        ).values(status_ephemeral_id=None))
    call.status_ephemeral_id = ephemeral_id


async def _post_status(bot: Bot, session: AsyncSession, message: Message, call: Call, text: str) -> None:
    """The call's status line: for a hidden call, shown to the teacher only; otherwise a reply in the group."""
    ephemeral_command = message.ephemeral_message_id is not None
    attempts = []
    if ephemeral_command:
        attempts.append(lambda: message.reply(text))  # a reply to an ephemeral message is ephemeral too
    if call.hidden:
        # The bot, as a group admin, may send an ephemeral message at any time.
        attempts.append(lambda: bot.send_message(call.chat_id, text, message_thread_id=call.thread_id,
                                                 ephemeral_message_parameters=to_user(call.requester_id)))
    for attempt in attempts:
        try:
            sent = await attempt()
        except TelegramAPIError as e:
            log.info("No ephemeral status for call %s: %s", call.id, e)
            continue
        await _remember_status(session, call, sent.ephemeral_message_id)
        return
    if ephemeral_command:
        return  # nobody else saw the call, so it isn't announced to the class either
    try:
        # A hidden call's tag message is already deleted, so there is nothing to reply to.
        sent = await (bot.send_message(call.chat_id, text, message_thread_id=call.thread_id) if call.hidden else message.reply(text))
        call.group_message_id = sent.message_id
    except TelegramAPIError as e:
        log.warning("Cannot reply in group %s: %s", call.chat_id, e)


async def _escalate(bot: Bot, session: AsyncSession, call: Call, ctx: dict, reason_key: str) -> None:
    for admin in await admin_users(session):
        already = await session.scalar(
            select(CallMessage.id).where(CallMessage.call_id == call.id, CallMessage.user_id == admin.id)
        )
        if already:
            continue
        try:
            await bot.send_message(admin.id, t(admin.lang, reason_key, minutes=_limit(call)))
        except TelegramAPIError:
            continue
        await _send_card(bot, session, call, admin, ctx)
    await session.commit()


def _limit(call: Call) -> int:
    return settings.urgent_escalate_minutes if call.urgent else settings.escalate_minutes


async def refresh_call(bot: Bot, session: AsyncSession, call: Call) -> None:
    """Re-render every delivered card and the status line in the class group."""
    ctx = await _context(session, call)
    msgs = (await session.scalars(select(CallMessage).where(CallMessage.call_id == call.id))).all()
    for cm in msgs:
        viewer = await session.get(User, cm.user_id)
        if viewer is None:
            continue
        text, markup = render_card(viewer.lang, call, viewer=viewer, **ctx)
        try:
            await bot.edit_message_text(text, chat_id=cm.user_id, message_id=cm.message_id, reply_markup=markup)
        except TelegramBadRequest as e:
            if "not modified" not in str(e):
                log.warning("Cannot edit card %s: %s", cm.id, e)
        except TelegramAPIError as e:
            log.warning("Cannot edit card %s: %s", cm.id, e)

    group = ctx["group"]
    if group is None:
        return
    status = render_group_status(group.lang, call, ctx["role"], ctx["accepter"])
    if call.status_ephemeral_id:
        try:
            await bot.edit_ephemeral_message_text(
                chat_id=call.chat_id, receiver_user_id=call.requester_id,
                ephemeral_message_id=call.status_ephemeral_id, text=status,
            )
        except TelegramAPIError as e:
            if "not modified" in str(e):
                return
            # Gone (ephemeral messages expire, or vanish when the app restarts): send the news anew.
            log.info("Cannot edit ephemeral status of call %s: %s", call.id, e)
            try:
                sent = await bot.send_message(call.chat_id, status, message_thread_id=call.thread_id,
                                             ephemeral_message_parameters=to_user(call.requester_id))
            except TelegramAPIError as e:
                log.warning("Cannot send ephemeral status of call %s: %s", call.id, e)
                return
            await _remember_status(session, call, sent.ephemeral_message_id)
            await session.commit()
    elif call.group_message_id:
        try:
            await bot.edit_message_text(status, chat_id=call.chat_id, message_id=call.group_message_id)
        except TelegramAPIError as e:
            if "not modified" not in str(e):
                log.warning("Cannot edit group status for call %s: %s", call.id, e)


async def set_status(session: AsyncSession, call_id: int, *, expect: str, by: int | None = None, **values) -> bool:
    """Atomic status change: only one of several people pressing at once wins."""
    stmt = update(Call).where(Call.id == call_id, Call.status == expect)
    if by is not None:
        stmt = stmt.where(Call.accepted_by == by)
    result = await session.execute(stmt.values(**values))
    await session.commit()
    return result.rowcount > 0


async def escalate_overdue(bot: Bot, session: AsyncSession) -> None:
    now = utcnow()
    pending = (await session.scalars(
        select(Call).where(Call.status == "pending", Call.escalated.is_(False))
    )).all()
    for call in pending:
        if call.created_at > now - timedelta(minutes=_limit(call)):
            continue
        call.escalated = True
        await session.commit()
        await _escalate(bot, session, call, await _context(session, call), reason_key="esc_timeout")
        await refresh_call(bot, session, call)


async def schedule_delete(session: AsyncSession, chat_id: int, message_id: int, after_seconds: int) -> None:
    session.add(PendingDelete(
        chat_id=chat_id, message_id=message_id, delete_at=utcnow() + timedelta(seconds=after_seconds),
    ))
    await session.commit()


async def delete_due_messages(bot: Bot, session: AsyncSession) -> None:
    due = (await session.scalars(select(PendingDelete).where(PendingDelete.delete_at <= utcnow()))).all()
    for item in due:
        with contextlib.suppress(TelegramAPIError):
            await bot.delete_message(item.chat_id, item.message_id)
        await session.delete(item)
    await session.commit()


async def run_periodic(bot: Bot, session: AsyncSession) -> None:
    """Everything time-based. Locally a loop calls it; on Vercel, Supabase Cron does (every minute)."""
    await escalate_overdue(bot, session)
    await delete_due_messages(bot, session)


async def periodic_loop(bot: Bot, sessionmaker: async_sessionmaker) -> None:
    while True:
        await asyncio.sleep(20)
        try:
            async with sessionmaker() as session:
                await run_periodic(bot, session)
        except Exception:
            log.exception("Periodic check failed")
