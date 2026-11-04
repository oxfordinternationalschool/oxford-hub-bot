"""Hidden staff calls: the class doesn't see the call; only the teacher sees its status (ephemeral messages)."""
import itertools

from aiogram.methods import DeleteMessage, EditEphemeralMessageText, EditMessageText, SetMyCommands
from sqlalchemy import select

from bot.db.models import Call, PendingDelete
from test_flow import CLEANER2, GROUP, STUDENT, TEACHER, setup_school

PHOTO = [{"file_id": "AgACphoto", "file_unique_id": "u1", "width": 1280, "height": 960}]


def status_messages(h):
    return h.api.sent(GROUP)


async def test_tag_call_is_deleted_and_its_status_shown_to_the_teacher_only(h):
    await setup_school(h)
    h.api.requests.clear()
    msg = await h.group(GROUP, TEACHER, "#cleaner partada suv to'kilgan")

    [deleted] = h.api.sent(GROUP, kind=DeleteMessage)
    assert deleted.message_id == msg["message_id"]
    [status] = status_messages(h)
    assert status.ephemeral_message_parameters.receiver_user_id == TEACHER and "chaqirildi" in status.text
    card = h.api.sent(CLEANER2)[-1].text
    assert "partada suv to'kilgan" in card and "t.me/c/" not in card  # the message is gone, so no link to it

    await h.callback(CLEANER2, "call:acc:1")
    [edit] = h.api.sent(GROUP, kind=EditEphemeralMessageText)
    assert edit.receiver_user_id == TEACHER and edit.ephemeral_message_id == 1 and "qabul qildi" in edit.text
    assert h.api.sent(GROUP, kind=EditMessageText) == []


async def test_menu_command_is_never_seen_by_the_class(h):
    await setup_school(h)
    original = await h.group(GROUP, STUDENT, "Derazasi singan")
    h.api.requests.clear()
    await h.group(GROUP, TEACHER, "/cleaner", ephemeral=True, reply_to=original)

    assert h.api.sent(GROUP, kind=DeleteMessage) == []  # nothing to delete: nobody saw it
    [status] = status_messages(h)
    assert status.reply_parameters.ephemeral_message_id and status.ephemeral_message_parameters.receiver_user_id == TEACHER
    assert "Derazasi singan" in h.api.sent(CLEANER2)[-1].text
    async with h.sessionmaker() as s:
        call = await s.scalar(select(Call))
        assert call.hidden and call.status_ephemeral_id == 1 and call.group_message_id is None


async def test_call_stays_visible_when_the_bot_cannot_delete(h):
    await setup_school(h)
    h.api.reject_delete = True
    h.api.requests.clear()
    msg = await h.group(GROUP, TEACHER, "#cleaner")

    [status] = status_messages(h)
    assert status.ephemeral_message_parameters is None and status.reply_parameters.message_id == msg["message_id"]
    assert "t.me/c/" in h.api.sent(CLEANER2)[-1].text
    await h.callback(CLEANER2, "call:acc:1")
    assert "qabul qildi" in h.api.sent(GROUP, kind=EditMessageText)[-1].text


async def test_call_with_a_photo_stays_in_the_group(h):
    await setup_school(h)
    h.api.requests.clear()
    await h.group(GROUP, TEACHER, "#cleaner shu yer", photo=PHOTO)
    assert h.api.sent(GROUP, kind=DeleteMessage) == []
    assert status_messages(h)[-1].ephemeral_message_parameters is None


async def test_status_is_sent_anew_when_the_old_one_expired(h):
    await setup_school(h)
    await h.group(GROUP, TEACHER, "#cleaner")
    h.api.reject_ephemeral_edit = True
    h.api.requests.clear()
    await h.callback(CLEANER2, "call:acc:1")

    [status] = status_messages(h)
    assert status.ephemeral_message_parameters.receiver_user_id == TEACHER and "qabul qildi" in status.text
    async with h.sessionmaker() as s:
        assert (await s.scalar(select(Call))).status_ephemeral_id == 2


async def test_reused_ephemeral_id_is_not_edited_by_an_older_call(h):
    await setup_school(h)
    await h.group(GROUP, TEACHER, "#cleaner")  # status id 1
    h.api.ephemeral_ids = itertools.repeat(1)  # the first status expired; Telegram reuses its id
    await h.group(GROUP, TEACHER, "#cleaner yana")
    async with h.sessionmaker() as s:
        first, second = (await s.scalars(select(Call).order_by(Call.id))).all()
        assert first.status_ephemeral_id is None and second.status_ephemeral_id == 1


async def test_students_are_told_privately(h):
    await setup_school(h)
    h.api.requests.clear()
    await h.group(GROUP, STUDENT, "#cleaner")
    [notice] = status_messages(h)
    assert notice.ephemeral_message_parameters.receiver_user_id == STUDENT and "o'qituvchilar" in notice.text
    assert h.api.sent(GROUP, kind=DeleteMessage) == []  # a student's message is left alone
    async with h.sessionmaker() as s:
        assert await s.scalar(select(PendingDelete)) is None  # nothing visible to clean up later


async def test_group_menu_has_the_call_commands_as_ephemeral(h):
    await setup_school(h)
    await h.private(1, "/alias cleaner tozalash уборка")

    menus = [r for r in h.api.requests if isinstance(r, SetMyCommands) and r.scope.type == "all_group_chats"]
    commands = {c.command: c for c in menus[-1].commands}
    assert set(commands) == {"cleaner", "tozalash"}  # Cyrillic words can't be commands, they stay #tags
    assert all(c.is_ephemeral for c in commands.values())
    assert commands["cleaner"].description == "🧹 Tozalovchi"
