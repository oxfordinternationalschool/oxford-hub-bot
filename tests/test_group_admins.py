"""School admins make people admins of the class groups through the bot."""
from aiogram.methods import CreateChatInviteLink, DeleteMessage, PromoteChatMember, SavePreparedKeyboardButton

from test_flow import ADMIN, GROUP, STUDENT, TEACHER, setup_school
from test_media_announce import GROUP_A, GROUP_B, school
from test_webapp_api import api, ok

STRANGER = 77  # never started the bot
OTHER_ADMIN = 8


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
    assert promote.can_promote_members and promote.can_change_info and not promote.is_anonymous

    assert "endi guruh admini" in await reply_with(h, ADMIN, "/promote", TEACHER)  # updates the rights
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


async def test_mini_app_shows_and_changes_admin_in_ticked_groups(wh):
    await school(wh)
    await wh.register(TEACHER)
    wh.api.set_member(GROUP_B, TEACHER, "left")

    statuses = {g["chat_id"]: g["status"] for g in await ok("admins.status", {"user_id": TEACHER})}
    assert statuses == {GROUP_A: "member", GROUP_B: "absent"}

    results = {r["chat_id"]: r for r in await ok("admins.set",
                                                  {"user_id": TEACHER, "chat_ids": [GROUP_A, GROUP_B], "value": True})}
    assert results[GROUP_A]["result"] == "ok" and results[GROUP_A]["message"] is None
    assert results[GROUP_B]["result"] == "not_member" and "guruhda yo'q" in results[GROUP_B]["message"]
    assert "User3" in results[GROUP_B]["message"] and "<" not in results[GROUP_B]["message"]
    assert [p.chat_id for p in wh.api.sent(kind=PromoteChatMember)] == [GROUP_A]  # only the groups given
    statuses = {g["chat_id"]: g["status"] for g in await ok("admins.status", {"user_id": TEACHER})}
    assert statuses[GROUP_A] == "admin"

    [r] = await ok("admins.set", {"user_id": TEACHER, "chat_ids": [GROUP_A], "value": False})
    assert r["result"] == "ok"


async def test_anyone_can_be_picked_in_telegram_and_made_admin(wh):
    """The person never started the bot: the admin picks them in Telegram's own people picker."""
    await school(wh)
    await wh.register(OTHER_ADMIN)
    await ok("staff.set_perm", {"user_id": OTHER_ADMIN, "perm": "admin", "value": True})
    button = await ok("admins.pick")
    [saved] = wh.api.sent(kind=SavePreparedKeyboardButton)
    assert saved.user_id == ADMIN and button["id"].startswith("pkb")
    request = saved.button.request_users
    assert request.request_id == button["request_id"] and request.user_is_bot is False and request.max_quantity == 1
    assert await ok("admins.picked", {"request_id": button["request_id"]}) is None  # not chosen yet

    # Telegram reports the choice to the bot, in the admin's private chat.
    await wh.private_media(ADMIN, users_shared={"request_id": button["request_id"], "users": [
        {"user_id": STRANGER, "first_name": "Anvar", "last_name": "Qodirov", "username": "anvar_q"}]})
    assert wh.api.sent(ADMIN, kind=DeleteMessage)  # the "you shared …" note is cleaned up
    person = await ok("admins.picked", {"request_id": button["request_id"]})
    assert person == {"id": STRANGER, "name": "Anvar Qodirov", "username": "anvar_q"}
    assert await ok("admins.picked", {"request_id": button["request_id"]}, uid=OTHER_ADMIN) is None

    wh.api.set_member(GROUP_A, 999, "administrator", can_promote_members=False)
    [r] = await ok("admins.set", {"user_id": STRANGER, "chat_ids": [GROUP_A], "value": True})
    assert r["result"] == "no_right" and "Anvar Qodirov" not in r["message"]  # that text names no one
    [r] = await ok("admins.set", {"user_id": STRANGER, "chat_ids": [GROUP_B], "value": True})
    assert r["result"] == "ok"


async def test_group_sheet_lists_its_admins(wh):
    await school(wh)
    wh.api.set_member(GROUP_A, 50, "creator")
    wh.api.set_member(GROUP_A, 51, "administrator", can_be_edited=False)
    await ok("admins.set", {"user_id": 52, "chat_ids": [GROUP_A], "value": True})

    admins = await ok("groups.admins", {"chat_id": GROUP_A})
    assert [(a["id"], a["status"]) for a in admins] == [(50, "owner"), (52, "admin"), (51, "admin_other")]  # no bots


async def pick(wh, uid=STRANGER, first="Anvar", last="Qodirov"):
    """The admin picks `uid` in Telegram's people picker."""
    button = await ok("admins.pick")
    await wh.private_media(ADMIN, users_shared={"request_id": button["request_id"], "users": [
        {"user_id": uid, "first_name": first, "last_name": last}]})
    return await ok("admins.picked", {"request_id": button["request_id"]})


async def test_invite_link_makes_the_person_an_admin_as_they_join(wh):
    await school(wh)
    person = await pick(wh)
    wh.api.set_member(GROUP_A, STRANGER, "left")

    link = (await ok("admins.invite", {"user_id": STRANGER, "chat_id": GROUP_A}))["link"]
    [created] = wh.api.sent(kind=CreateChatInviteLink)
    assert created.chat_id == GROUP_A and created.member_limit == 1 and created.name == "Admin: Anvar Qodirov"
    assert (await ok("admins.invite", {"user_id": STRANGER, "chat_id": GROUP_A}))["link"] == link  # the same one again
    assert len(wh.api.sent(kind=CreateChatInviteLink)) == 1
    status = {g["chat_id"]: g for g in await ok("admins.status", {"user_id": person["id"]})}
    assert status[GROUP_A]["status"] == "absent" and status[GROUP_A]["invite"] == link
    assert status[GROUP_B]["invite"] is None

    wh.api.requests.clear()
    await wh.joined(GROUP_A, STRANGER, link, title="7-A sinf")
    [promote] = wh.api.sent(kind=PromoteChatMember)
    assert promote.chat_id == GROUP_A and promote.user_id == STRANGER and promote.can_manage_chat
    assert "admin qilindi" in wh.api.sent(ADMIN)[-1].text and "7-A" in wh.api.sent(ADMIN)[-1].text

    await wh.joined(GROUP_A, STRANGER, link)  # the link works once
    assert len(wh.api.sent(kind=PromoteChatMember)) == 1


async def test_someone_else_with_the_link_stays_a_member(wh):
    await school(wh)
    await pick(wh)
    wh.api.set_member(GROUP_A, STRANGER, "left")
    link = (await ok("admins.invite", {"user_id": STRANGER, "chat_id": GROUP_A}))["link"]
    await wh.joined(GROUP_A, 88, link)
    assert wh.api.sent(kind=PromoteChatMember) == []
    assert "boshqa odam kirdi: User88" in wh.api.sent(ADMIN)[-1].text


async def test_ordinary_joins_are_ignored(wh):
    await school(wh)
    wh.api.requests.clear()
    await wh.joined(GROUP_A, 88)
    await wh.joined(GROUP_A, 89, "https://t.me/+someone_elses")
    assert wh.api.sent(kind=PromoteChatMember) == [] and wh.api.sent(ADMIN) == []


async def test_invite_needs_the_invite_right(wh):
    await school(wh)
    wh.api.reject_invite = True
    status, body = await api("admins.invite", {"user_id": STRANGER, "chat_id": GROUP_A})
    assert status == 400 and "taklif qilish" in body["message"]


async def test_admin_removes_a_group_from_the_bot(wh):
    from aiogram.methods import LeaveChat
    await school(wh)
    groups = await ok("groups.remove", {"chat_id": GROUP_A})
    assert [g["chat_id"] for g in groups] == [GROUP_B]
    [leave] = wh.api.sent(kind=LeaveChat)
    assert leave.chat_id == GROUP_A

    # Adding the bot back brings the group back.
    await wh.bot_added(GROUP_A, ADMIN, title="7-A sinf")
    assert {g["chat_id"] for g in await ok("groups.list")} == {GROUP_A, GROUP_B}


async def test_person_is_removed_from_ticked_groups_only(wh):
    from aiogram.methods import BanChatMember, UnbanChatMember
    await school(wh)
    await wh.register(OTHER_ADMIN)
    await ok("staff.set_perm", {"user_id": OTHER_ADMIN, "perm": "admin", "value": True})
    wh.api.requests.clear()

    [r] = await ok("admins.kick", {"user_id": STRANGER, "chat_ids": [GROUP_A]})
    assert r["result"] == "ok" and r["message"] is None
    [ban] = wh.api.sent(kind=BanChatMember)
    [unban] = wh.api.sent(kind=UnbanChatMember)
    assert ban.chat_id == unban.chat_id == GROUP_A and ban.user_id == STRANGER and unban.only_if_banned
    assert ban.revoke_messages is False
    assert "chiqardi" in wh.api.sent(OTHER_ADMIN)[-1].text  # the other admins are told
    assert wh.api.sent(ADMIN) == []  # the one who did it isn't
    statuses = {g["chat_id"]: g["status"] for g in await ok("admins.status", {"user_id": STRANGER})}
    assert statuses == {GROUP_A: "absent", GROUP_B: "member"}


async def test_an_admin_the_bot_made_is_demoted_then_removed(wh):
    from aiogram.methods import BanChatMember
    await school(wh)
    await ok("admins.set", {"user_id": STRANGER, "chat_ids": [GROUP_A], "value": True})
    wh.api.requests.clear()
    [r] = await ok("admins.kick", {"user_id": STRANGER, "chat_ids": [GROUP_A]})
    assert r["result"] == "ok"
    assert isinstance(wh.api.requests[2], PromoteChatMember) and not wh.api.requests[2].can_manage_chat
    assert len(wh.api.sent(kind=BanChatMember)) == 1


async def test_who_cannot_be_removed(wh):
    from aiogram.methods import BanChatMember
    await school(wh)
    wh.api.set_member(GROUP_A, 50, "creator")
    wh.api.set_member(GROUP_A, 51, "administrator", can_be_edited=False)
    wh.api.set_member(GROUP_A, 52, "left")
    expected = {50: "owner", 51: "not_ours", 52: "not_member"}
    for uid, result in expected.items():
        [r] = await ok("admins.kick", {"user_id": uid, "chat_ids": [GROUP_A]})
        assert r["result"] == result and r["message"]
    status, body = await api("admins.kick", {"user_id": ADMIN, "chat_ids": [GROUP_A]})
    assert status == 400 and "bosh admin" in body["message"]
    wh.api.set_member(GROUP_A, 999, "administrator", can_restrict_members=False)
    [r] = await ok("admins.kick", {"user_id": STRANGER, "chat_ids": [GROUP_A]})
    assert r["result"] == "no_right"
    assert wh.api.sent(kind=BanChatMember) == []


async def test_several_people_are_picked_at_once(wh):
    await school(wh)
    button = await ok("admins.pick", {"many": True})
    [saved] = wh.api.sent(kind=SavePreparedKeyboardButton)
    assert saved.button.request_users.max_quantity == 10
    assert await ok("admins.picked", {"request_id": button["request_id"], "many": True}) is None
    await wh.private_media(ADMIN, users_shared={"request_id": button["request_id"], "users": [
        {"user_id": STRANGER, "first_name": "Anvar"}, {"user_id": 78, "first_name": "Bobur", "username": "bobur"}]})
    people = await ok("admins.picked", {"request_id": button["request_id"], "many": True})
    assert [(p["id"], p["name"], p["username"]) for p in people] == [(STRANGER, "Anvar", None), (78, "Bobur", "bobur")]


async def test_member_invite_does_not_make_an_admin(wh):
    await school(wh)
    await pick(wh)
    r = await ok("admins.invite", {"user_id": STRANGER, "chat_id": GROUP_A, "as_admin": False})
    [created] = wh.api.sent(kind=CreateChatInviteLink)
    assert created.member_limit == 1 and r["link"] and r["expires_at"] is None
    status = {g["chat_id"]: g for g in await ok("admins.status", {"user_id": STRANGER})}
    assert status[GROUP_A]["invite"] is None  # no pending admin
