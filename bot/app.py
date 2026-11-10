"""Wiring shared by both ways of running the bot: local polling (`python -m bot`) and Vercel webhooks."""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommandScopeAllPrivateChats, Update
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.config import settings
from bot.db.session import make_engine, reset_sessionmaker, use_sessionmaker
from bot.handlers import admin, admin_panel, announce, calls, groups, start, stories
from bot.middlewares import DbMiddleware, GroupWatcher, TopicLearner
from bot.services.calls import run_periodic
from bot.services.menus import COMMANDS, as_commands
from bot.storage import SqlStorage

# Shown in Telegram before the first /start ("What can this bot do?") and on the bot's profile.
DESCRIPTIONS = {
    "uz": (
        "Oxford Hub — Oxford International School boti.\n\n"
        "📢 Sinf guruhlariga e'lonlar\n"
        "🧹 O'qituvchilar uchun: tozalovchi, shifokor, inspektor va boshqa xodimlarni bitta teg bilan chaqirish\n\n"
        "Boshlash uchun /start ni bosing.",
        "Oxford International School: e'lonlar va xodimlarni chaqirish",
    ),
    "ru": (
        "Oxford Hub — бот Oxford International School.\n\n"
        "📢 Объявления для групп классов\n"
        "🧹 Для учителей: вызов уборщицы, врача, инспектора и других сотрудников одним тегом\n\n"
        "Нажмите /start, чтобы начать.",
        "Oxford International School: объявления и вызов сотрудников",
    ),
    "en": (
        "Oxford Hub — the Oxford International School bot.\n\n"
        "📢 Announcements for class groups\n"
        "🧹 For teachers: call a cleaner, the doctor, an inspector or other staff with one tag\n\n"
        "Press /start to begin.",
        "Oxford International School: announcements and staff calls",
    ),
}

_dispatcher: Dispatcher | None = None


def get_dispatcher() -> Dispatcher:
    # Routers can belong to only one dispatcher, so it is built once per process.
    global _dispatcher
    if _dispatcher is None:
        dp = Dispatcher(storage=SqlStorage())
        dp.update.outer_middleware(DbMiddleware())
        dp.message.outer_middleware(TopicLearner())
        dp.message.outer_middleware(GroupWatcher())
        dp.edited_message.outer_middleware(GroupWatcher())
        # Order matters: the group catch-all (calls) and the private fallback go last.
        dp.include_routers(
            start.router,
            admin.router,
            admin_panel.router,
            announce.router,
            stories.router,
            groups.router,
            calls.router,
            start.fallback_router,
        )
        _dispatcher = dp
    return _dispatcher


def make_bot() -> Bot:
    return Bot(
        settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )


async def set_commands(bot: Bot) -> None:
    """Command menu and profile description, per language (the default language also as fallback)."""
    scope = BotCommandScopeAllPrivateChats()
    for lang, items in COMMANDS.items():
        commands = as_commands(items)
        description, short = DESCRIPTIONS[lang]
        for code in (lang, None) if lang == settings.default_lang else (lang,):
            await bot.set_my_commands(commands, scope=scope, language_code=code)
            await bot.set_my_description(description, language_code=code)
            await bot.set_my_short_description(short, language_code=code)


@asynccontextmanager
async def request_scope() -> AsyncIterator[tuple[Bot, async_sessionmaker]]:
    """Fresh bot + DB engine for one serverless request.

    Nothing is reused between requests: the platform may run each one on a different
    event loop, and aiohttp/asyncpg connections cannot cross loops. The tables are not
    checked here (that costs dozens of queries); `python -m bot.setup_webhook` creates them.
    """
    engine = make_engine(settings.database_url, serverless=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    token = use_sessionmaker(sessionmaker)
    bot = make_bot()
    try:
        yield bot, sessionmaker
    finally:
        reset_sessionmaker(token)
        await bot.session.close()
        await engine.dispose()


async def process_update(payload: dict) -> None:
    async with request_scope() as (bot, _):
        update = Update.model_validate(payload, context={"bot": bot})
        await get_dispatcher().feed_update(bot, update)


async def run_tick() -> None:
    async with request_scope() as (bot, sessionmaker):
        async with sessionmaker() as session:
            await run_periodic(bot, session)
