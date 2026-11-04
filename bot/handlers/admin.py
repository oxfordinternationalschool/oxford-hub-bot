"""Admin text commands. The same features are also reachable as buttons from /admin (admin_panel.py)."""
from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Invite, User
from bot.filters import IsAdmin
from bot.i18n import t
from bot.services import admin_views as views
from bot.services.common import chunk_lines, find_floor, q, resolve_user, user_link
from bot.services.menus import set_user_menu, sync_group_commands
from bot.services.roles import is_valid_key, trigger_cache
from bot.services.users import user_badges

router = Router(name="admin")
router.message.filter(F.chat.type == ChatType.PRIVATE, IsAdmin())


def _args(command: CommandObject) -> list[str]:
    return (command.args or "").split()


async def _answer_chunks(message: Message, lines: list[str]) -> None:
    for chunk in chunk_lines(lines):
        await message.answer(chunk)


# ---------- Roles ----------

@router.message(Command("roles"))
async def cmd_roles(message: Message, session: AsyncSession, lang: str):
    await _answer_chunks(message, await views.roles_lines(session, lang))


@router.message(Command("addrole"))
async def cmd_addrole(message: Message, command: CommandObject, session: AsyncSession, lang: str, bot: Bot):
    role, text = await views.create_role(session, lang, _args(command))
    if role is not None:
        await sync_group_commands(bot, session)
    await message.answer(text)


@router.message(Command("delrole"))
async def cmd_delrole(message: Message, command: CommandObject, session: AsyncSession, lang: str, bot: Bot):
    args = _args(command)
    role = await views.role_by_key(session, args[0]) if args else None
    if role is None:
        await message.answer(t(lang, "role_not_found"))
        return
    await views.delete_role(session, role)
    await sync_group_commands(bot, session)
    await message.answer(t(lang, "role_deleted", title=q(role.title)))


@router.message(Command("rolefloor"))
async def cmd_rolefloor(message: Message, command: CommandObject, session: AsyncSession, lang: str):
    args = _args(command)
    if len(args) != 2 or args[1].lower() not in ("on", "off"):
        await message.answer(t(lang, "usage_rolefloor"))
        return
    role = await views.role_by_key(session, args[0])
    if role is None:
        await message.answer(t(lang, "role_not_found"))
        return
    role.floor_based = args[1].lower() == "on"
    await session.commit()
    await message.answer(t(lang, "rolefloor_on" if role.floor_based else "rolefloor_off", title=q(role.title)))


@router.message(Command("alias"))
async def cmd_alias(message: Message, command: CommandObject, session: AsyncSession, lang: str, bot: Bot):
    args = _args(command)
    if len(args) < 2:
        await message.answer(t(lang, "usage_alias"))
        return
    role = await views.role_by_key(session, args[0])
    if role is None:
        await message.answer(t(lang, "role_not_found"))
        return
    taken = await trigger_cache.get(session)
    aliases = role.aliases.split()
    for word in (w.lstrip("#/").lower() for w in args[1:]):
        if not is_valid_key(word):
            await message.answer(t(lang, "bad_key", word=q(word)))
            return
        if word in taken or word in aliases:
            await message.answer(t(lang, "key_taken", word=q(word)))
            return
        aliases.append(word)
    role.aliases = " ".join(aliases)
    await session.commit()
    trigger_cache.invalidate()
    await sync_group_commands(bot, session)
    await message.answer(t(lang, "alias_set", title=q(role.title), triggers=views.triggers_text(role)))


@router.message(Command("unalias"))
async def cmd_unalias(message: Message, command: CommandObject, session: AsyncSession, lang: str, bot: Bot):
    args = _args(command)
    if len(args) != 2:
        await message.answer(t(lang, "usage_alias"))
        return
    role = await views.role_by_key(session, args[0])
    if role is None:
        await message.answer(t(lang, "role_not_found"))
        return
    word = args[1].lstrip("#/").lower()
    role.aliases = " ".join(a for a in role.aliases.split() if a != word)
    await session.commit()
    trigger_cache.invalidate()
    await sync_group_commands(bot, session)
    await message.answer(t(lang, "alias_set", title=q(role.title), triggers=views.triggers_text(role)))


# ---------- Floors ----------

@router.message(Command("floors"))
async def cmd_floors(message: Message, session: AsyncSession, lang: str):
    await _answer_chunks(message, await views.floors_lines(session, lang))


@router.message(Command("addfloor"))
async def cmd_addfloor(message: Message, command: CommandObject, session: AsyncSession, lang: str):
    _, text = await views.create_floor(session, lang, command.args or "")
    await message.answer(text)


@router.message(Command("delfloor"))
async def cmd_delfloor(message: Message, command: CommandObject, session: AsyncSession, lang: str):
    floor = await find_floor(session, command.args or "")
    if floor is None:
        await message.answer(t(lang, "floor_not_found"))
        return
    await views.delete_floor(session, floor)
    await message.answer(t(lang, "floor_deleted", name=q(floor.name)))


# ---------- Invites & staff ----------

@router.message(Command("invite"))
async def cmd_invite(message: Message, command: CommandObject, session: AsyncSession, user: User, bot: Bot, lang: str):
    args = _args(command)
    target = await views.parse_target(session, args[0]) if args else None
    if target is None:
        await message.answer(t(lang, "usage_invite"))
        return
    kind, role = target
    uses = 1
    if len(args) > 1:
        if not args[1].isdigit() or not 1 <= int(args[1]) <= 1000:
            await message.answer(t(lang, "usage_invite"))
            return
        uses = int(args[1])
    floor = None
    if len(args) > 2:
        floor = await find_floor(session, " ".join(args[2:]))
        if floor is None:
            await message.answer(t(lang, "floor_not_found"))
            return
    await message.answer(await views.create_invite(session, bot, user.id, lang, kind, role, floor, uses))


@router.message(Command("invites"))
async def cmd_invites(message: Message, session: AsyncSession, lang: str):
    await _answer_chunks(message, await views.invites_lines(session, lang))


@router.message(Command("revoke"))
async def cmd_revoke(message: Message, command: CommandObject, session: AsyncSession, lang: str):
    inv = await session.get(Invite, (command.args or "").strip())
    if inv is None:
        await message.answer(t(lang, "inv_invalid"))
        return
    inv.is_active = False
    await session.commit()
    await message.answer(t(lang, "invite_revoked"))


@router.message(Command("staff"))
async def cmd_staff(message: Message, command: CommandObject, session: AsyncSession, lang: str):
    args = _args(command)
    kind, role = None, None
    if args:
        target = await views.parse_target(session, args[0])
        if target is None:
            await message.answer(t(lang, "role_not_found"))
            return
        kind, role = target
    users = await views.staff_users(session, kind, role)
    await _answer_chunks(message, await views.staff_lines(session, lang, users))


async def _assign_args(message: Message, command: CommandObject, session: AsyncSession, lang: str):
    args = _args(command)
    if len(args) < 2:
        await message.answer(t(lang, "usage_assign"))
        return None
    target_user = await resolve_user(session, args[0])
    if target_user is None:
        await message.answer(t(lang, "user_not_found"))
        return None
    target = await views.parse_target(session, args[1])
    if target is None:
        await message.answer(t(lang, "role_not_found"))
        return None
    floor = None
    if len(args) > 2:
        floor = await find_floor(session, " ".join(args[2:]))
        if floor is None:
            await message.answer(t(lang, "floor_not_found"))
            return None
    return target_user, target[0], target[1], floor


@router.message(Command("assign", "unassign"))
async def cmd_assign(message: Message, command: CommandObject, session: AsyncSession, bot: Bot, lang: str):
    parsed = await _assign_args(message, command, session, lang)
    if parsed is None:
        return
    target_user, kind, role, floor = parsed
    action = views.grant if command.command == "assign" else views.revoke
    await action(session, target_user, kind, role, floor)
    if kind == "admin":
        await set_user_menu(bot, target_user)
    badges = ", ".join(await user_badges(session, target_user, lang)) or "—"
    await message.answer(t(lang, "assigned", user=user_link(target_user), roles=badges))


# ---------- Groups & stats ----------

@router.message(Command("groups"))
async def cmd_groups(message: Message, session: AsyncSession, lang: str):
    await _answer_chunks(message, await views.groups_lines(session, lang))


@router.message(Command("stats"))
async def cmd_stats(message: Message, command: CommandObject, session: AsyncSession, lang: str):
    days = int(command.args) if command.args and command.args.strip().isdigit() else 7
    await _answer_chunks(message, await views.stats_lines(session, lang, days))
