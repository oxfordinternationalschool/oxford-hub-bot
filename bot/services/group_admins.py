"""Making people admins of the class groups, through the bot (which needs the "Add new admins" right there).

They get the rights a teacher needs to keep order in a class group, and only those the bot
itself has (Telegram refuses the rest): delete messages, restrict members, pin, invite,
manage video chats. Not: change the group info, add admins, stay anonymous.
Telegram lets the bot demote only the admins it promoted itself.
"""
import logging

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import ChatMember

log = logging.getLogger(__name__)

GRANTED = ("can_delete_messages", "can_restrict_members", "can_invite_users", "can_pin_messages",
           "can_manage_video_chats")

# Results of set_group_admin; each has a text "gadm_<result>" in i18n.
OK, ALREADY_ADMIN, NOT_ADMIN, OWNER, NOT_MEMBER, NOT_OURS, NO_RIGHT, BASIC_GROUP, ERROR = (
    "ok", "already_admin", "not_admin", "owner", "not_member", "not_ours", "no_right", "basic_group", "error",
)


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
        if make_admin and status in ("admin", "admin_other"):
            return ALREADY_ADMIN
        if not make_admin and status == "member":
            return NOT_ADMIN
        if not make_admin and status == "admin_other":
            return NOT_OURS
        rights = {right: make_admin and bool(getattr(me, right, False)) for right in GRANTED}
        await bot.promote_chat_member(chat_id, user_id, can_manage_chat=make_admin, **rights)
    except TelegramBadRequest as e:
        log.info("Cannot change admin %s in %s: %s", user_id, chat_id, e)
        return _error_result(e)
    except TelegramAPIError as e:
        log.warning("Cannot change admin %s in %s: %s", user_id, chat_id, e)
        return ERROR
    return OK
