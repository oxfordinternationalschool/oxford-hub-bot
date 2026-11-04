"""The Vercel path: HTTP requests into the ASGI app, a fresh engine per request, state in the DB."""
import re
from datetime import timedelta

from aiogram.methods import CopyMessage, DeleteMessage
from sqlalchemy import select

from bot.config import utcnow
from bot.db.models import FsmState, PendingDelete
from bot.webhook import app
from conftest import SECRET, call_asgi

ADMIN, TEACHER, STUDENT = 1, 3, 4
GROUP = -1001234500


async def test_rejects_wrong_secret(wh):
    status, _ = await call_asgi(app, {"X-Telegram-Bot-Api-Secret-Token": "wrong"}, b"{}")
    assert status == 403
    status, _ = await call_asgi(app, {"Authorization": "Bearer wrong"})
    assert status == 403
    assert wh.api.requests == []


async def test_health_check(wh):
    status, body = await call_asgi(app, {}, method="GET")
    assert status == 200 and "running" in body


async def test_announcement_draft_survives_between_requests(wh):
    await wh.register(ADMIN)
    await wh.bot_added(GROUP, ADMIN)
    await wh.private(ADMIN, "/announce")
    await wh.private(ADMIN, "Ertaga dars yo'q")
    async with wh.sessionmaker() as s:
        assert (await s.scalar(select(FsmState))).state == "AnnounceSG:targets"

    await wh.callback(ADMIN, "ann:all:0")
    await wh.callback(ADMIN, "ann:send:0")
    assert [c.chat_id for c in wh.api.sent(kind=CopyMessage)] == [GROUP]
    async with wh.sessionmaker() as s:
        # Finished conversation leaves no rows behind.
        assert (await s.scalars(select(FsmState))).all() == []


async def test_full_call_over_webhook(wh):
    await wh.register(ADMIN)
    await wh.private(ADMIN, "/addrole doctor 🩺 Shifokor")
    await wh.private(ADMIN, "/invite doctor")
    code = re.search(r"start=([\w-]+)", wh.api.sent(ADMIN)[-1].text).group(1)
    await wh.register(7, code)
    await wh.private(ADMIN, "/invite teacher 5")
    code = re.search(r"start=([\w-]+)", wh.api.sent(ADMIN)[-1].text).group(1)
    await wh.register(TEACHER, code)
    await wh.bot_added(GROUP, ADMIN)

    await wh.group(GROUP, TEACHER, "#doctor! bola yiqildi")
    card = wh.api.sent(7)[-1]
    assert "bola yiqildi" in card.text and "SHOSHILINCH" in card.text


async def test_cron_tick_deletes_due_notices(wh):
    await wh.register(ADMIN)
    await wh.private(ADMIN, "/addrole cleaner 🧹 Tozalovchi")
    await wh.bot_added(GROUP, ADMIN)
    wh.api.reject_ephemeral = True  # no private notice possible, so a visible one that is deleted later
    await wh.group(GROUP, STUDENT, "#cleaner")
    async with wh.sessionmaker() as s:
        pending = await s.scalar(PendingDelete.__table__.select())
        assert pending is not None
        await s.execute(PendingDelete.__table__.update().values(delete_at=utcnow() - timedelta(seconds=1)))
        await s.commit()

    status, _ = await call_asgi(app, {"Authorization": f"Bearer {SECRET}"})
    assert status == 200
    assert len(wh.api.sent(kind=DeleteMessage)) == 1
    async with wh.sessionmaker() as s:
        assert (await s.scalars(PendingDelete.__table__.select())).all() == []
