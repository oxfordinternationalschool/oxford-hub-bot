"""End-to-end: real dispatcher, routers and SQLite; only the Telegram API is faked."""
import re
from datetime import timedelta

from aiogram.methods import CopyMessage, EditEphemeralMessageText, EditMessageText, LeaveChat, SendMessage
from sqlalchemy import select, update

from bot.config import utcnow
from bot.db.models import Call, Group
from bot.services.calls import escalate_overdue

ADMIN, CLEANER2, TEACHER, STUDENT, CLEANER3 = 1, 2, 3, 4, 5
GROUP = -1001234500


def invite_code(h, admin_id=ADMIN) -> str:
    text = h.api.sent(admin_id)[-1].text
    return re.search(r"start=([\w-]+)", text).group(1)


async def setup_school(h):
    await h.register(ADMIN)
    await h.private(ADMIN, "/addrole cleaner 🧹 Tozalovchi")
    await h.private(ADMIN, "/rolefloor cleaner on")
    await h.private(ADMIN, "/addfloor 2-qavat")
    await h.private(ADMIN, "/addfloor 3-qavat")

    await h.private(ADMIN, "/invite cleaner 1 2-qavat")
    await h.register(CLEANER2, invite_code(h))
    await h.private(ADMIN, "/invite cleaner 1 3-qavat")
    await h.register(CLEANER3, invite_code(h))
    await h.private(ADMIN, "/invite teacher 50")
    await h.register(TEACHER, invite_code(h))

    await h.bot_added(GROUP, ADMIN)
    await h.group(GROUP, ADMIN, "/setfloor 2-qavat")


async def test_call_routed_by_floor_and_status_updates(h):
    await setup_school(h)
    h.api.requests.clear()

    await h.group(GROUP, TEACHER, "#cleaner partada suv to'kilgan")

    cards = h.api.sent(CLEANER2)
    assert len(cards) == 1
    assert "partada suv to'kilgan" in cards[0].text and "7-B" in cards[0].text
    assert cards[0].reply_markup.inline_keyboard[0][0].callback_data == "call:acc:1"
    assert h.api.sent(CLEANER3) == []  # different floor
    assert "chaqirildi" in h.api.sent(GROUP)[-1].text

    await h.callback(CLEANER2, "call:acc:1")
    group_edit = [r for r in h.api.requests if isinstance(r, EditEphemeralMessageText) and r.chat_id == GROUP]
    assert "qabul qildi" in group_edit[-1].text

    # Someone else cannot finish it.
    await h.callback(CLEANER3, "call:done:1")
    async with h.sessionmaker() as s:
        assert (await s.get(Call, 1)).status == "accepted"

    await h.callback(CLEANER2, "call:done:1")
    async with h.sessionmaker() as s:
        assert (await s.get(Call, 1)).status == "done"


async def test_floor_fallback_when_nobody_on_floor(h):
    await setup_school(h)
    await h.group(GROUP, ADMIN, "/setfloor 3-qavat")
    async with h.sessionmaker() as s:
        await s.execute(update(Group).values(floor_id=None))
        await s.commit()
    h.api.requests.clear()
    await h.group(GROUP, TEACHER, "#cleaner")
    # No floor on the class -> every cleaner gets it.
    assert len(h.api.sent(CLEANER2)) == 1 and len(h.api.sent(CLEANER3)) == 1


async def test_students_cannot_call(h):
    await setup_school(h)
    h.api.requests.clear()
    await h.group(GROUP, STUDENT, "#cleaner")
    assert h.api.sent(CLEANER2) == []
    assert "o'qituvchilar" in h.api.sent(GROUP)[-1].text


async def test_reply_with_command_includes_quoted_text(h):
    await setup_school(h)
    original = await h.group(GROUP, ADMIN, "Derazasi singan")
    h.api.requests.clear()
    await h.group(GROUP, TEACHER, "/cleaner", reply_to=original)
    assert "Derazasi singan" in h.api.sent(CLEANER2)[-1].text


async def test_unanswered_call_escalates_to_admin(h):
    await setup_school(h)
    await h.group(GROUP, TEACHER, "#cleaner!")
    async with h.sessionmaker() as s:
        await s.execute(update(Call).values(created_at=utcnow() - timedelta(minutes=10)))
        await s.commit()
    h.api.requests.clear()
    async with h.sessionmaker() as s:
        await escalate_overdue(h.bot, s)
        assert (await s.scalar(select(Call))).escalated
    admin_msgs = [m.text for m in h.api.sent(ADMIN)]
    assert any("hech kim qabul qilmadi" in m for m in admin_msgs)
    assert any("SHOSHILINCH" in m for m in admin_msgs)


async def test_role_without_staff_notifies_admin(h):
    await setup_school(h)
    await h.private(ADMIN, "/addrole doctor 🩺 Shifokor")
    h.api.requests.clear()
    await h.group(GROUP, TEACHER, "#doctor")
    assert "biriktirilmagan" in h.api.sent(GROUP)[-1].text
    assert any("xodim yo'q" in m.text for m in h.api.sent(ADMIN))


async def test_announcement_to_all_groups(h):
    await setup_school(h)
    await h.bot_added(-1009999, ADMIN, title="9-A sinf")
    await h.private(ADMIN, "/announce")
    await h.private(ADMIN, "Ertaga darslar 9:00 da boshlanadi")
    h.api.requests.clear()
    await h.callback(ADMIN, "ann:grade:9")
    await h.callback(ADMIN, "ann:send:0")
    copies = h.api.sent(kind=CopyMessage)
    assert [c.chat_id for c in copies] == [-1009999]

    await h.private(ADMIN, "/announce")
    await h.private(ADMIN, "Hammaga")
    h.api.requests.clear()
    await h.callback(ADMIN, "ann:all:0")
    await h.callback(ADMIN, "ann:send:0")
    assert {c.chat_id for c in h.api.sent(kind=CopyMessage)} == {GROUP, -1009999}


async def test_teacher_cannot_announce_or_admin(h):
    await setup_school(h)
    h.api.requests.clear()
    await h.private(TEACHER, "/announce")
    await h.private(TEACHER, "/addrole hacker")
    texts = [m.text for m in h.api.sent(TEACHER)]
    assert all("tushunmadim" in tx for tx in texts)


async def test_non_admin_adding_bot_makes_it_leave(h):
    await setup_school(h)
    await h.bot_added(-100777, TEACHER, title="Random group")
    assert any(isinstance(r, LeaveChat) for r in h.api.requests)
    async with h.sessionmaker() as s:
        assert await s.get(Group, -100777) is None


async def test_invite_single_use(h):
    await h.register(ADMIN)
    await h.private(ADMIN, "/invite announcer")
    code = invite_code(h)
    await h.register(10, code)
    await h.register(11, code)
    assert "yaroqsiz" in h.api.sent(11)[-1].text or any("yaroqsiz" in m.text for m in h.api.sent(11))


async def test_someone_without_a_role_is_told_the_bot_is_for_staff(h):
    await h.register(9)
    text = h.api.sent(9)[-1].text
    assert "sinfingiz guruhida" in text and "xodim" not in text
    assert "ID" not in text and "/help" not in text
