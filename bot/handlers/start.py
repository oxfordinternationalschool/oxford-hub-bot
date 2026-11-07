from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.callbacks import FloorPickCb, LangCb
from bot.db.models import Floor, Invite, Role, User
from bot.filters import can_announce, can_call, is_admin
from bot.i18n import LANG_LABELS, t
from bot.services.common import notify_admins, q, user_link
from bot.services.menus import set_user_menu
from bot.services.users import add_staff_role, user_badges

router = Router(name="start")
router.message.filter(F.chat.type == ChatType.PRIVATE)

# Registered last: answers private messages nothing else handled.
fallback_router = Router(name="fallback")
fallback_router.message.filter(F.chat.type == ChatType.PRIVATE)


def lang_keyboard():
    kb = InlineKeyboardBuilder()
    for code, label in LANG_LABELS.items():
        kb.button(text=label, callback_data=LangCb(code=code))
    kb.adjust(3)
    return kb.as_markup()


async def welcome_text(session: AsyncSession, user: User) -> str:
    lang = user.lang
    lines = [t(lang, "welcome", name=q(user.full_name))]
    badges = await user_badges(session, user, lang)
    if not badges:
        # Most people without a role are students or parents who found the bot in their group:
        # nothing here is for them, and staff join through an invite link anyway.
        lines.append(t(lang, "guest_welcome"))
        return "\n\n".join(lines)
    lines.append(t(lang, "your_roles", roles=", ".join(badges)))
    lines.append(t(lang, "see_admin") if user.is_admin else t(lang, "see_help"))
    return "\n\n".join(lines)


@router.message(CommandStart())
async def cmd_start(
    message: Message, command: CommandObject, session: AsyncSession, user: User, state: FSMContext, bot: Bot
):
    await state.clear()
    await set_user_menu(bot, user)
    if not user.lang_chosen:
        await state.update_data(pending_code=command.args)
        await message.answer(t(user.lang, "choose_lang"), reply_markup=lang_keyboard())
        return
    if command.args:
        await apply_invite(bot, session, user, command.args, message)
    else:
        await message.answer(await welcome_text(session, user))


@router.message(Command("lang"))
async def cmd_lang(message: Message, lang: str):
    await message.answer(t(lang, "choose_lang"), reply_markup=lang_keyboard())


@router.callback_query(LangCb.filter())
async def on_lang(
    cb: CallbackQuery, callback_data: LangCb, session: AsyncSession, user: User, state: FSMContext, bot: Bot
):
    user.lang = callback_data.code
    user.lang_chosen = True
    await session.commit()
    await set_user_menu(bot, user)  # admin menu follows the chosen language
    await cb.message.edit_text(t(user.lang, "lang_set"))
    await cb.answer()

    data = await state.get_data()
    code = data.pop("pending_code", None)
    await state.set_data(data)
    if code:
        await apply_invite(bot, session, user, code, cb.message)
    else:
        await cb.message.answer(await welcome_text(session, user))


async def apply_invite(bot: Bot, session: AsyncSession, user: User, code: str, reply_to: Message) -> None:
    lang = user.lang
    inv = await session.get(Invite, code)
    if inv is None or not inv.is_active or inv.uses_left <= 0:
        await reply_to.answer(t(lang, "inv_invalid"))
        return

    role = None
    if inv.kind == "admin":
        user.is_admin = True
        what = t(lang, "perm_admin")
    elif inv.kind == "announcer":
        user.can_announce = True
        what = t(lang, "perm_announcer")
    elif inv.kind == "teacher":
        user.is_teacher = True
        what = t(lang, "perm_teacher")
    else:
        role = await session.get(Role, inv.role_id) if inv.role_id else None
        if role is None:
            await reply_to.answer(t(lang, "inv_invalid"))
            return
        what = q(role.title)

    inv.uses_left -= 1
    if inv.uses_left <= 0:
        inv.is_active = False

    ask_floor = False
    if role is not None:
        floors = (await session.scalars(select(Floor).order_by(Floor.id))).all()
        if role.floor_based and inv.floor_id is None and floors:
            ask_floor = True
        else:
            await add_staff_role(session, user.id, role.id, inv.floor_id)
    await session.commit()
    if inv.kind == "admin":
        await set_user_menu(bot, user)

    await reply_to.answer(t(lang, "inv_ok", what=what))
    if ask_floor:
        kb = InlineKeyboardBuilder()
        for f in floors:
            kb.button(text=f.name, callback_data=FloorPickCb(role_id=role.id, floor_id=f.id))
        kb.button(text=t(lang, "all_floors"), callback_data=FloorPickCb(role_id=role.id, floor_id=0))
        kb.adjust(3)
        await reply_to.answer(t(lang, "pick_floor", role=q(role.title)), reply_markup=kb.as_markup())
    else:
        await reply_to.answer(await welcome_text(session, user))

    await notify_admins(bot, session, "adm_new_member", user=user_link(user), what=what)


@router.callback_query(FloorPickCb.filter())
async def on_floor_pick(cb: CallbackQuery, callback_data: FloorPickCb, session: AsyncSession, user: User):
    role = await session.get(Role, callback_data.role_id)
    if role is None:
        await cb.answer()
        return
    floor = await session.get(Floor, callback_data.floor_id) if callback_data.floor_id else None
    await add_staff_role(session, user.id, role.id, floor.id if floor else None)
    await session.commit()
    floor_name = q(floor.name) if floor else t(user.lang, "all_floors")
    await cb.message.edit_text(t(user.lang, "floor_picked", role=q(role.title), floor=floor_name))
    await cb.message.answer(await welcome_text(session, user))
    await cb.answer()


@router.message(Command("me"))
async def cmd_me(message: Message, session: AsyncSession, user: User, lang: str):
    badges = await user_badges(session, user, lang)
    await message.answer(t(
        lang, "me",
        name=q(user.full_name),
        id=user.id,
        username=f"@{user.username}" if user.username else "—",
        roles=", ".join(badges) if badges else "—",
    ))


@router.message(Command("help"))
async def cmd_help(message: Message, session: AsyncSession, user: User, lang: str):
    parts = [t(lang, "help_basic")]
    if can_call(user):
        parts.append(t(lang, "help_teacher"))
        roles = (await session.scalars(select(Role).order_by(Role.key))).all()
        if roles:
            triggers = ", ".join(f"{q(r.emoji)} <code>#{r.key}</code>" for r in roles)
            parts.append(t(lang, "help_roles", triggers=triggers))
    if can_announce(user):
        parts.append(t(lang, "help_announcer"))
    if is_admin(user):
        parts.append(t(lang, "help_admin"))
    await message.answer("\n\n".join(parts))


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, lang: str):
    await state.clear()
    await message.answer(t(lang, "cancelled"))


@fallback_router.message()
async def fallback(message: Message, lang: str):
    await message.answer(t(lang, "unknown"))
