import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.types import ChatMemberUpdated, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import LANGS
from bot.db.models import Floor, ForumTopic, User
from bot.filters import IsAdmin, is_admin
from bot.i18n import t
from bot.services.common import ensure_group, find_floor, migrate_group, notify_admins, parse_class, q
from bot.services.group_admins import OK, invite_used, person_name, set_group_admin
from bot.services.topics import message_topic

log = logging.getLogger(__name__)

GROUP_TYPES = {ChatType.GROUP, ChatType.SUPERGROUP}

router = Router(name="groups")
router.message.filter(F.chat.type.in_(GROUP_TYPES))

GONE = {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}


@router.my_chat_member(F.chat.type.in_(GROUP_TYPES))
async def on_bot_membership(event: ChatMemberUpdated, session: AsyncSession, user: User | None, bot: Bot):
    old, new = event.old_chat_member.status, event.new_chat_member.status

    if new in GONE:
        group = await ensure_group(session, event.chat)
        group.is_active = False
        await session.commit()
        await notify_admins(bot, session, "adm_group_removed", title=q(group.title))
        return

    joined = old in GONE
    if joined and not is_admin(user):
        # Only school admins may add the bot, otherwise any random group would land in the broadcast list.
        try:
            await bot.send_message(event.chat.id, t("uz", "only_admin_can_add"))
            await bot.leave_chat(event.chat.id)
        except Exception as e:
            log.warning("Could not leave %s: %s", event.chat.id, e)
        return

    group = await ensure_group(session, event.chat)
    group.is_active = True
    group.bot_is_admin = new in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR)
    await session.commit()

    if joined:
        await notify_admins(
            bot, session, "adm_group_added",
            title=q(group.title),
            cls=q(group.class_name or "—"),
        )
        if not group.bot_is_admin:
            await bot.send_message(event.chat.id, t(group.lang, "make_me_admin"))
    elif not group.bot_is_admin:
        await notify_admins(bot, session, "adm_group_not_admin", title=q(group.title))


@router.chat_member(F.chat.type.in_(GROUP_TYPES), F.invite_link)
async def on_join_by_link(event: ChatMemberUpdated, session: AsyncSession, bot: Bot):
    """Someone joined through an admin invite made in the Mini App: they become an admin.
    The link is for one person; if someone else got hold of it, they stay a plain member."""
    joined = event.old_chat_member.status in GONE and event.new_chat_member.status not in GONE
    if not joined:
        return
    pending = await invite_used(session, event.chat.id, event.invite_link.invite_link)
    if pending is None:
        return
    group = await ensure_group(session, event.chat)
    person = event.new_chat_member.user
    expected = q(await person_name(session, pending.user_id))
    admin = await session.get(User, pending.created_by)
    lang = admin.lang if admin else group.lang
    if person.id != pending.user_id:
        text = t(lang, "gadm_wrong_person", name=expected, group=q(group.label), who=q(person.full_name))
    else:
        result = await set_group_admin(bot, event.chat.id, person.id, True)
        text = (t(lang, "gadm_joined", name=q(person.full_name), group=q(group.label)) if result == OK else
                t(lang, "gadm_joined_failed", name=q(person.full_name), group=q(group.label),
                  reason=t(lang, f"gadm_{result}", name=q(person.full_name))))
    try:
        await bot.send_message(pending.created_by, text)
    except TelegramAPIError as e:
        log.info("Cannot tell admin %s about the join: %s", pending.created_by, e)


@router.message(F.migrate_to_chat_id)
async def on_migrate(message: Message, session: AsyncSession):
    await migrate_group(session, message.chat.id, message.migrate_to_chat_id)


@router.message(Command("setclass"), IsAdmin())
async def cmd_setclass(message: Message, command: CommandObject, session: AsyncSession):
    group = await ensure_group(session, message.chat)
    parsed = parse_class(command.args or "")
    if parsed is None:
        await message.reply(t(group.lang, "usage_setclass"))
        return
    group.grade, group.class_name = parsed
    await session.commit()
    await message.reply(t(group.lang, "class_set", cls=group.class_name))


@router.message(Command("setfloor"), IsAdmin())
async def cmd_setfloor(message: Message, command: CommandObject, session: AsyncSession):
    group = await ensure_group(session, message.chat)
    name = (command.args or "").strip()
    floor = await find_floor(session, name) if name else None
    if floor is None:
        await message.reply(t(group.lang, "floor_not_found"))
        return
    group.floor_id = floor.id
    await session.commit()
    await message.reply(t(group.lang, "floor_set", cls=q(group.label), floor=q(floor.name)))


@router.message(Command("grouplang"), IsAdmin())
async def cmd_grouplang(message: Message, command: CommandObject, session: AsyncSession):
    group = await ensure_group(session, message.chat)
    code = (command.args or "").strip().lower()
    if code not in LANGS:
        await message.reply(t(group.lang, "usage_grouplang"))
        return
    group.lang = code
    await session.commit()
    await message.reply(t(group.lang, "lang_set"))


@router.message(Command("promote", "demote"), IsAdmin())
async def cmd_promote(message: Message, command: CommandObject, session: AsyncSession, bot: Bot):
    """A school admin replies to someone's message with /promote (or /demote)."""
    group = await ensure_group(session, message.chat)
    reply = message.reply_to_message
    target = reply.from_user if reply and not reply.forum_topic_created else None
    if target is None or target.id == bot.id:
        await message.reply(t(group.lang, "gadm_usage"))
        return
    make_admin = command.command.lower() == "promote"
    result = await set_group_admin(bot, message.chat.id, target.id, make_admin)
    key = ("gadm_promoted" if make_admin else "gadm_demoted") if result == OK else f"gadm_{result}"
    await message.reply(t(group.lang, key, name=q(target.full_name)))


@router.message(Command("settopic"), IsAdmin())
async def cmd_settopic(message: Message, session: AsyncSession):
    """Written in a topic: announcements to this group go there (written in General: back to General)."""
    group = await ensure_group(session, message.chat)
    group.announce_thread_id = message_topic(message)
    await session.commit()
    if group.announce_thread_id is None:
        await message.reply(t(group.lang, "topic_set_general"))
        return
    topic = await session.get(ForumTopic, (message.chat.id, group.announce_thread_id))
    await message.reply(t(group.lang, "topic_set", topic=q(topic.name if topic else "#" + str(group.announce_thread_id))))


@router.message(Command("groupinfo"), IsAdmin())
async def cmd_groupinfo(message: Message, session: AsyncSession, bot: Bot):
    group = await ensure_group(session, message.chat)
    member = await bot.get_chat_member(message.chat.id, bot.id)
    group.bot_is_admin = member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR)
    await session.commit()
    floor = await session.get(Floor, group.floor_id) if group.floor_id else None
    await message.reply(t(
        group.lang, "groupinfo",
        title=q(group.title),
        cls=q(group.class_name or "—"),
        floor=q(floor.name) if floor else "—",
        lang=group.lang,
        admin="✅" if group.bot_is_admin else "❌",
        id=group.chat_id,
    ))
