"""Making people admins of the class groups, through the bot (which needs the "Add new admins" right there).

They get every admin right the bot itself has, except staying anonymous.
Telegram lets the bot demote only the admins it promoted itself.

The person can be anyone in the group, also someone who never started the bot: the Mini App
lets the admin pick them in Telegram's own people picker (a "prepared keyboard button").
"""
import logging
import secrets
import time
from datetime import timedelta, timezone

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.methods import PromoteChatMember
from aiogram.types import ChatMember, KeyboardButton, KeyboardButtonRequestUsers, UsersShared
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import utcnow
from bot.db.models import PendingAdmin, PickedUser, User

log = logging.getLogger(__name__)

PICK_TTL = timedelta(days=1)
INVITE_TTL = timedelta(days=7)


# Results of set_group_admin; each has a text "gadm_<result>" in i18n.
OK, ALREADY_ADMIN, NOT_ADMIN, OWNER, NOT_MEMBER, NOT_OURS, NO_RIGHT, BASIC_GROUP, ERROR = (
    "ok", "already_admin", "not_admin", "owner", "not_member", "not_ours", "no_right", "basic_group", "error",
)


def _rights(me, value: bool) -> dict[str, bool]:
    """Every admin right the bot itself has (Telegram refuses the rest), all set to `value`."""
    rights = {f: value for f in PromoteChatMember.model_fields if f.startswith("can_") and getattr(me, f, False)}
    rights["can_manage_chat"] = value
    return rights


def member_status(member: ChatMember) -> str:
    """owner | admin (the bot may change them) | admin_other (someone else promoted them) | member | absent"""
    if member.status == ChatMemberStatus.CREATOR:
        return "owner"
    if member.status == ChatMemberStatus.ADMINISTRATOR:
        return "admin" if member.can_be_edited else "admin_other"
    if member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
        return "absent"
    if member.status == ChatMemberStatus.RESTRICTED and not member.is_member:
        return "absent"
    return "member"


async def group_status(bot: Bot, chat_id: int, user_id: int) -> str:
    try:
        return member_status(await bot.get_chat_member(chat_id, user_id))
    except TelegramAPIError as e:
        log.info("Cannot check %s in %s: %s", user_id, chat_id, e)
        return "unknown"


def _error_result(e: TelegramAPIError) -> str:
    text = str(e).lower()
    if "supergroup" in text:
        return BASIC_GROUP
    if "participant" in text or "user not found" in text:
        return NOT_MEMBER
    if "right" in text or "admin_required" in text or "not enough" in text:
        return NO_RIGHT
    return ERROR


async def set_group_admin(bot: Bot, chat_id: int, user_id: int, make_admin: bool) -> str:
    try:
        me = await bot.get_chat_member(chat_id, bot.id)
        if me.status != ChatMemberStatus.ADMINISTRATOR or not me.can_promote_members:
            return NO_RIGHT
        status = member_status(await bot.get_chat_member(chat_id, user_id))
        if status == "owner":
            return OWNER
        if status == "absent":
            return NOT_MEMBER
        if make_admin and status == "admin_other":
            return ALREADY_ADMIN  # (an admin the bot appointed is updated to the full rights)
        if not make_admin and status == "member":
            return NOT_ADMIN
        if not make_admin and status == "admin_other":
            return NOT_OURS
        await bot.promote_chat_member(chat_id, user_id, **_rights(me, make_admin))
    except TelegramBadRequest as e:
        log.info("Cannot change admin %s in %s: %s", user_id, chat_id, e)
        return _error_result(e)
    except TelegramAPIError as e:
        log.warning("Cannot change admin %s in %s: %s", user_id, chat_id, e)
        return ERROR
    return OK


async def kick_member(bot: Bot, chat_id: int, user_id: int) -> str:
    """Removes the person from the group without blocking them: they can come back by a link.
    An admin the bot appointed loses that first; other admins and the owner can't be removed."""
    try:
        me = await bot.get_chat_member(chat_id, bot.id)
        if me.status != ChatMemberStatus.ADMINISTRATOR or not me.can_restrict_members:
            return NO_RIGHT
        status = member_status(await bot.get_chat_member(chat_id, user_id))
        if status == "owner":
            return OWNER
        if status == "absent":
            return NOT_MEMBER
        if status == "admin_other":
            return NOT_OURS
        if status == "admin":
            if not me.can_promote_members:
                return NO_RIGHT
            await bot.promote_chat_member(chat_id, user_id, **_rights(me, False))
        # A short ban, lifted at once: if the lifting failed, it would still run out by itself.
        await bot.ban_chat_member(chat_id, user_id, until_date=int(time.time()) + 60, revoke_messages=False)
        await bot.unban_chat_member(chat_id, user_id, only_if_banned=True)
    except TelegramBadRequest as e:
        log.info("Cannot remove %s from %s: %s", user_id, chat_id, e)
        return _error_result(e)
    except TelegramAPIError as e:
        log.warning("Cannot remove %s from %s: %s", user_id, chat_id, e)
        return ERROR
    return OK


# ---------- An invite link that makes its person an admin on joining ----------

async def admin_invite(bot: Bot, session: AsyncSession, chat_id: int, user_id: int, name: str, by: int) -> PendingAdmin | None:
    """A one-use invite link for `user_id`, who isn't in the group yet (the same one again while it is valid).
    None if Telegram refuses (the bot needs the right to invite users)."""
    now = utcnow()
    pending = await session.scalar(select(PendingAdmin).where(
        PendingAdmin.chat_id == chat_id, PendingAdmin.user_id == user_id,
        PendingAdmin.used.is_not(True), PendingAdmin.expires_at > now + timedelta(hours=1),
    ).order_by(PendingAdmin.id.desc()).limit(1))
    if pending is not None:
        return pending
    expires = now + INVITE_TTL
    try:
        link = await bot.create_chat_invite_link(
            chat_id, name=f"Admin: {name}"[:32], member_limit=1, expire_date=expires.replace(tzinfo=timezone.utc),
        )
    except TelegramAPIError as e:
        log.info("Cannot create an admin invite for %s in %s: %s", user_id, chat_id, e)
        return None
    pending = PendingAdmin(chat_id=chat_id, user_id=user_id, invite_link=link.invite_link, created_by=by, expires_at=expires)
    session.add(pending)
    await session.commit()
    return pending


async def pending_invites(session: AsyncSession, user_id: int) -> dict[int, PendingAdmin]:
    """chat_id -> the person's valid admin invite there."""
    rows = (await session.scalars(select(PendingAdmin).where(
        PendingAdmin.user_id == user_id, PendingAdmin.used.is_not(True), PendingAdmin.expires_at > utcnow(),
    ).order_by(PendingAdmin.id))).all()
    return {p.chat_id: p for p in rows}


async def invite_used(session: AsyncSession, chat_id: int, link: str) -> PendingAdmin | None:
    """The pending admin invite someone just joined through, marked used (each link works once)."""
    pending = await session.scalar(select(PendingAdmin).where(
        PendingAdmin.chat_id == chat_id, PendingAdmin.invite_link == link, PendingAdmin.used.is_not(True),
    ))
    if pending is not None:
        pending.used = True
        await session.commit()
    return pending


# ---------- Picking a person in Telegram's own picker (from the Mini App) ----------

def new_request_id() -> int:
    return secrets.randbelow(2**31 - 2) + 1  # Telegram wants a signed 32-bit number


def picker_button(text: str, request_id: int) -> KeyboardButton:
    return KeyboardButton(text=text, request_users=KeyboardButtonRequestUsers(
        request_id=request_id, user_is_bot=False, max_quantity=1, request_name=True, request_username=True,
    ))


async def save_picked(session: AsyncSession, admin_id: int, shared: UsersShared) -> None:
    await session.execute(delete(PickedUser).where(PickedUser.created_at < utcnow() - PICK_TTL))
    for u in shared.users:
        name = " ".join(filter(None, (u.first_name, u.last_name))) or (f"@{u.username}" if u.username else str(u.user_id))
        session.add(PickedUser(admin_id=admin_id, request_id=shared.request_id, user_id=u.user_id,
                               name=name[:255], username=u.username))
    await session.commit()


async def picked_user(session: AsyncSession, admin_id: int, request_id: int) -> PickedUser | None:
    return await session.scalar(select(PickedUser).where(
        PickedUser.admin_id == admin_id, PickedUser.request_id == request_id,
    ).order_by(PickedUser.id.desc()).limit(1))


async def person_name(session: AsyncSession, user_id: int) -> str:
    """The name to show: from the bot's users, else from a recent pick, else the ID."""
    user = await session.get(User, user_id)
    if user is not None:
        return user.full_name
    picked = await session.scalar(
        select(PickedUser.name).where(PickedUser.user_id == user_id).order_by(PickedUser.id.desc()).limit(1)
    )
    return picked or f"ID {user_id}"
