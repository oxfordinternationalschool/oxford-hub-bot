"""The "/" command menu. Everyone gets the basic list; admins get their own, longer one."""
import logging
import re

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import (
    BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeChat, MenuButtonDefault, MenuButtonWebApp, WebAppInfo,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.db.models import Role, User
from bot.i18n import t

log = logging.getLogger(__name__)

COMMANDS = {
    "uz": [("start", "Boshlash"), ("help", "Yordam"), ("announce", "E'lon yuborish"),
           ("me", "Mening ma'lumotlarim"), ("lang", "Tilni o'zgartirish"), ("cancel", "Bekor qilish")],
    "ru": [("start", "Начать"), ("help", "Помощь"), ("announce", "Отправить объявление"),
           ("me", "Мои данные"), ("lang", "Сменить язык"), ("cancel", "Отмена")],
    "en": [("start", "Start"), ("help", "Help"), ("announce", "Send an announcement"),
           ("me", "My profile"), ("lang", "Change language"), ("cancel", "Cancel")],
}

ADMIN_COMMANDS = {
    "uz": [("admin", "⚙️ Admin panel"), ("announce", "E'lon yuborish"), ("roles", "Rollar"),
           ("floors", "Qavatlar"), ("staff", "Xodimlar"), ("invite", "Taklif havolasi"),
           ("invites", "Faol havolalar"), ("groups", "Guruhlar"), ("stats", "Statistika"),
           ("help", "Yordam"), ("me", "Mening ma'lumotlarim"), ("lang", "Tilni o'zgartirish"),
           ("cancel", "Bekor qilish")],
    "ru": [("admin", "⚙️ Админ-панель"), ("announce", "Отправить объявление"), ("roles", "Роли"),
           ("floors", "Этажи"), ("staff", "Сотрудники"), ("invite", "Ссылка-приглашение"),
           ("invites", "Активные ссылки"), ("groups", "Группы"), ("stats", "Статистика"),
           ("help", "Помощь"), ("me", "Мои данные"), ("lang", "Сменить язык"),
           ("cancel", "Отмена")],
    "en": [("admin", "⚙️ Admin panel"), ("announce", "Send an announcement"), ("roles", "Roles"),
           ("floors", "Floors"), ("staff", "Staff"), ("invite", "Invite link"),
           ("invites", "Active invite links"), ("groups", "Groups"), ("stats", "Statistics"),
           ("help", "Help"), ("me", "My profile"), ("lang", "Change language"),
           ("cancel", "Cancel")],
}


def as_commands(items: list[tuple[str, str]]) -> list[BotCommand]:
    return [BotCommand(command=c, description=d) for c, d in items]


async def set_user_menu(bot: Bot, user: User, webapp_url: str | None = None) -> None:
    """Admins get the admin command list and, when the Mini App is deployed, a "Panel" button
    next to the message field that opens it. For everyone else those overrides are removed."""
    webapp_url = webapp_url or settings.webapp_url
    scope = BotCommandScopeChat(chat_id=user.id)
    try:
        if user.is_admin:
            await bot.set_my_commands(as_commands(ADMIN_COMMANDS[user.lang]), scope=scope)
            if webapp_url:
                await bot.set_chat_menu_button(user.id, MenuButtonWebApp(
                    text=t(user.lang, "menu_panel"), web_app=WebAppInfo(url=webapp_url),
                ))
        else:
            await bot.delete_my_commands(scope=scope)
            if webapp_url:
                await bot.set_chat_menu_button(user.id, MenuButtonDefault())
    except TelegramAPIError as e:
        log.warning("Cannot update menu for %s: %s", user.id, e)


async def sync_admin_menus(bot: Bot, session: AsyncSession, webapp_url: str | None = None) -> None:
    for admin in (await session.scalars(select(User).where(User.is_admin))).all():
        await set_user_menu(bot, admin, webapp_url)


COMMAND_RE = re.compile(r"^[a-z0-9_]{1,32}$")  # what Telegram accepts as a command name
MAX_COMMANDS = 100


def call_commands(roles: list[Role]) -> list[BotCommand]:
    """The staff-call triggers that can be commands. Ephemeral: picked from the "/" menu in a
    group, the command is seen only by the bot, not by the class."""
    out: list[BotCommand] = []
    seen: set[str] = set()
    for role in roles:
        for word in (w.lower() for w in role.triggers):
            if COMMAND_RE.match(word) and word not in seen:
                seen.add(word)
                out.append(BotCommand(command=word, description=role.title[:256], is_ephemeral=True))
    return out[:MAX_COMMANDS]


async def sync_group_commands(bot: Bot, session: AsyncSession) -> None:
    """Refreshes the group "/" menu; called whenever roles or their trigger words change."""
    roles = list((await session.scalars(select(Role).order_by(Role.id))).all())
    commands = call_commands(roles)
    scope = BotCommandScopeAllGroupChats()
    try:
        if commands:
            await bot.set_my_commands(commands, scope=scope)
        else:
            await bot.delete_my_commands(scope=scope)
    except TelegramAPIError as e:
        log.warning("Cannot update the group command menu: %s", e)
