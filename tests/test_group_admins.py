"""School admins make people admins of the class groups through the bot."""
from aiogram.methods import PromoteChatMember

from test_flow import ADMIN, GROUP, STUDENT, TEACHER, setup_school
from test_media_announce import GROUP_A, GROUP_B, school
from test_webapp_api import ok


async def reply_with(h, uid, command, target_uid):
    original = await h.group(GROUP, target_uid, "Salom")
    await h.group(GROUP, uid, command, reply_to=original)
    return h.api.sent(GROUP)[-1].text


async def test_promote_and_demote_by_reply(h):
    await setup_school(h)
    h.api.requests.clear()

    assert "endi guruh admini" in await reply_with(h, ADMIN, "/promote", TEACHER)
    [promote] = h.api.sent(kind=PromoteChatMember)
    assert promote.chat_id == GROUP and promote.user_id == TEACHER
    assert promote.can_manage_chat and promote.can_delete_messages and promote.can_restrict_members
    assert not promote.can_promote_members and not promote.can_change_info and not promote.is_anonymous

    assert "allaqachon admin" in await reply_with(h, ADMIN, "/promote", TEACHER)
    assert "admin emas" in await reply_with(h, ADMIN, "/demote", TEACHER)
    demote = h.api.sent(kind=PromoteChatMember)[-1]
    assert not demote.can_manage_chat and not demote.can_delete_messages


async def test_only_the_rights_the_bot_has_are_given(h):
    await setup_school(h)
    h.api.set_member(GROUP, 999, "administrator", can_promote_members=True, can_restrict_members=False)
    await reply_with(h, ADMIN, "/promote", TEACHER)
    promote = h.api.sent(kind=PromoteChatMember)[-1]
    assert promote.can_delete_messages and not promote.can_restrict_members


async def test_promote_explains_what_is_wrong(h):
    await setup_school(h)
    h.api.requests.clear()
    await h.group(GROUP, ADMIN, "/promote")
    assert "javob (reply)" in h.api.sent(GROUP)[-1].text  # not a reply

    h.api.set_member(GROUP, TEACHER, "administrator", can_be_edited=False)  # promoted by someone else
    assert "boshqa admin tayinlagan" in await reply_with(h, ADMIN, "/demote", TEACHER)
    h.api.set_member(GROUP, STUDENT, "creator")
    assert "guruh egasi" in await reply_with(h, ADMIN, "/demote", STUDENT)
    h.api.set_member(GROUP, STUDENT, "left")
    assert "guruhda yo'q" in await reply_with(h, ADMIN, "/promote", STUDENT)
    h.api.set_member(GROUP, 999, "administrator", can_promote_members=False)
    assert "Yangi admin qo'shish" in await reply_with(h, ADMIN, "/promote", STUDENT)
    assert h.api.sent(kind=PromoteChatMember) == []


async def test_teachers_cannot_promote(h):
    await setup_school(h)
    h.api.requests.clear()
    original = await h.group(GROUP, STUDENT, "Salom")
    await h.group(GROUP, TEACHER, "/promote", reply_to=original)
    assert h.api.sent(kind=PromoteChatMember) == [] and h.api.sent(GROUP) == []


async def test_mini_app_shows_and_changes_admin_in_groups(wh):
    await school(wh)
    await wh.register(TEACHER)
    wh.api.set_member(GROUP_B, TEACHER, "left")

    statuses = {g["chat_id"]: g["status"] for g in await ok("staff.group_admin", {"user_id": TEACHER})}
    assert statuses == {GROUP_A: "member", GROUP_B: "absent"}

    results = {r["chat_id"]: r for r in await ok("staff.set_group_admin",
                                                  {"user_id": TEACHER, "chat_ids": [GROUP_A, GROUP_B], "value": True})}
    assert results[GROUP_A]["result"] == "ok" and results[GROUP_A]["message"] is None
    assert results[GROUP_B]["result"] == "not_member" and "guruhda yo'q" in results[GROUP_B]["message"]
    assert "<" not in results[GROUP_B]["message"]
    statuses = {g["chat_id"]: g["status"] for g in await ok("staff.group_admin", {"user_id": TEACHER})}
    assert statuses[GROUP_A] == "admin"

    [r] = await ok("staff.set_group_admin", {"user_id": TEACHER, "chat_ids": [GROUP_A], "value": False})
    assert r["result"] == "ok"
