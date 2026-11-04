"""One-time setup for Vercel + Supabase, run from your computer:

    python -m bot.setup_webhook https://your-project.vercel.app

Uses BOT_TOKEN, DATABASE_URL (Supabase) and WEBHOOK_SECRET from .env and:
  1. creates the tables in Supabase (with RLS on, so the public REST API can't read them);
  2. points Telegram at the Vercel URL;
  3. schedules Supabase Cron to call the bot every minute (escalations, cleanup).
"""
import asyncio
import re
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.app import get_dispatcher, make_bot, set_commands
from bot.config import settings
from bot.db.session import ensure_schema, make_engine
from bot.services.menus import sync_admin_menus, sync_group_commands

CRON_JOB = "oxford-bot-tick"
SECRET_RE = re.compile(r"^[A-Za-z0-9_-]{16,256}$")


def cron_command(api_url: str) -> str:
    return (
        "select net.http_post("
        f"url := '{api_url}', "
        f"headers := jsonb_build_object('Authorization', 'Bearer {settings.webhook_secret}'), "
        "body := '{}'::jsonb, "
        "timeout_milliseconds := 30000)"
    )


async def setup_cron(engine, api_url: str) -> bool:
    steps = [
        ("create extension if not exists pg_cron with schema pg_catalog", {}),
        ("create extension if not exists pg_net with schema extensions", {}),
        ("select cron.schedule(:name, '* * * * *', :cmd)", {"name": CRON_JOB, "cmd": cron_command(api_url)}),
    ]
    for sql, params in steps:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(sql), params)
        except Exception as e:
            print(f"   ⚠️  {sql.split('(')[0]}: {e}")
            return False
    return True


async def main(base_url: str) -> None:
    base_url = base_url.rstrip("/")
    if not re.match(r"^https://[\w.-]+(:\d+)?$", base_url):
        sys.exit("Manzil shunday bo'lishi kerak: https://loyiha-nomi.vercel.app")
    if not settings.bot_token:
        sys.exit(".env da BOT_TOKEN yo'q")
    if not SECRET_RE.match(settings.webhook_secret):
        sys.exit(".env da WEBHOOK_SECRET kamida 16 belgili bo'lishi kerak (faqat harf, raqam, _ va -)")
    if not settings.database_url.startswith("postgresql"):
        sys.exit(".env da DATABASE_URL Supabase manziliga o'rnatilmagan (hozir SQLite)")

    api_url = f"{base_url}/api"

    print("1) Supabase'da jadvallar yaratilmoqda...")
    engine = make_engine(settings.database_url, serverless=True)
    await ensure_schema(engine)
    print("   ✅ tayyor")

    print("2) Telegram webhook o'rnatilmoqda...")
    bot = make_bot()
    try:
        await bot.set_webhook(
            api_url,
            secret_token=settings.webhook_secret,
            allowed_updates=get_dispatcher().resolve_used_update_types(),
        )
        await set_commands(bot)
        async with async_sessionmaker(engine)() as session:
            # Gives every admin the "Panel" button that opens the Mini App.
            await sync_admin_menus(bot, session, webapp_url=f"{base_url}/admin/")
            # Staff-call commands in the groups' "/" menu, hidden from the class (ephemeral).
            await sync_group_commands(bot, session)
        info = await bot.get_webhook_info()
        me = await bot.me()
        print(f"   ✅ @{me.username} → {info.url}")
    finally:
        await bot.session.close()

    print("3) Supabase Cron (har daqiqada) sozlanmoqda...")
    if await setup_cron(engine, api_url):
        print("   ✅ tayyor")
    else:
        sql_file = Path(__file__).resolve().parent.parent / "supabase" / "cron.sql"
        print(
            "   ❌ Avtomatik bo'lmadi. Supabase Dashboard → Database → Extensions bo'limida\n"
            "      pg_cron va pg_net ni yoqing, so'ng SQL Editor'da quyidagi fayldagi so'rovni bajaring:\n"
            f"      {sql_file}"
        )
    await engine.dispose()
    print("\nTayyor! Botga Telegram'da /start yozib tekshiring.")


if __name__ == "__main__":
    # The Windows console defaults to cp1251, which can't print the ✅/❌ marks below.
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        sys.exit("Foydalanish: python -m bot.setup_webhook https://loyiha-nomi.vercel.app")
    asyncio.run(main(sys.argv[1]))
