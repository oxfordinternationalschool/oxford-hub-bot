"""Groups with topics: the bot learns the topics, and announcements go to the chosen one."""
from aiogram.methods import SendMessage, SendRichMessage
from sqlalchemy import select

from bot.db.models import Group
from test_flow import ADMIN, GROUP, TEACHER, setup_school
from test_media_announce import GROUP_A, GROUP_B, school
from test_webapp_api import ok

NEWS, HOMEWORK = 40, 41


def sent_to(api, chat_id):
    return [r for r in api.requests if isinstance(r, (SendMessage, SendRichMessage)) and r.chat_id == chat_id]


async def announce(text="Ertaga tadbir"):
    return await ok("announce.send", {"html": text, "chat_ids": [GROUP_A, GROUP_B], "pin": False})


async def test_topics_are_learned_and_one_is_chosen_in_the_mini_app(wh):
    await school(wh)
    await wh.group(GROUP_A, 5, "Salom", title="7-A sinf", topic=(NEWS, "News"))
    await wh.group(GROUP_A, 5, "Uy vazifa", title="7-A sinf", topic=(HOMEWORK, "Homework"))
    await wh.group(GROUP_A, 5, "Yana", title="7-A sinf", topic=(NEWS, "News"))

    group = next(g for g in await ok("groups.list") if g["chat_id"] == GROUP_A)
    assert group["topics"] == [{"id": NEWS, "name": "News"}, {"id": HOMEWORK, "name": "Homework"}]
    assert group["announce_thread_id"] is None
    group = await ok("groups.update", {"chat_id": GROUP_A, "announce_thread_id": NEWS})
    assert group["announce_topic"] == "News"

    wh.api.requests.clear()
    await announce()
    [to_a] = sent_to(wh.api, GROUP_A)
    [to_b] = sent_to(wh.api, GROUP_B)
    assert to_a.message_thread_id == NEWS and to_b.message_thread_id is None  # B has no topic chosen

    status, _ = await __import__("test_webapp_api").api("groups.update", {"chat_id": GROUP_A, "announce_thread_id": 999})
    assert status == 400  # a topic the bot doesn't know


async def test_one_topic_name_for_every_group(wh):
    await school(wh)
    await wh.group(GROUP_A, 5, "a", title="7-A sinf", topic=(NEWS, "News"))
    await wh.group(GROUP_B, 5, "b", title="7-B sinf", topic=(77, "news "))
    await wh.group(GROUP_B, 5, "c", title="7-B sinf", topic=(78, "Homework"))
    r = await ok("groups.topic_all", {"name": "News"})
    assert r["done"] == 2 and r["missing"] == []
    assert {g["chat_id"]: g["announce_thread_id"] for g in r["groups"]} == {GROUP_A: NEWS, GROUP_B: 77}

    r = await ok("groups.topic_all", {"name": "Homework"})
    assert r["done"] == 1 and r["missing"] == ["7-A"]


async def test_deleted_topic_falls_back_to_general(wh):
    await school(wh)
    await wh.group(GROUP_A, 5, "a", title="7-A sinf", topic=(NEWS, "News"))
    await ok("groups.update", {"chat_id": GROUP_A, "announce_thread_id": NEWS})
    wh.api.gone_threads.add(NEWS)
    wh.api.requests.clear()
    result = await announce()
    assert result["sent"] == 2
    assert [m.message_thread_id for m in sent_to(wh.api, GROUP_A)] == [NEWS, None]
    async with wh.sessionmaker() as s:
        assert (await s.get(Group, GROUP_A)).announce_thread_id is None


async def test_settopic_in_a_topic(h):
    await setup_school(h)
    await h.group(GROUP, 5, "x", topic=(NEWS, "News"))
    await h.group(GROUP, ADMIN, "/settopic", topic=(NEWS, "News"))
    assert "«News»" in h.api.sent(GROUP)[-1].text
    await h.group(GROUP, ADMIN, "/settopic")  # in General
    assert "General" in h.api.sent(GROUP)[-1].text
    async with h.sessionmaker() as s:
        assert (await s.get(Group, GROUP)).announce_thread_id is None


async def test_hidden_call_status_stays_in_the_teachers_topic(h):
    await setup_school(h)
    h.api.requests.clear()
    await h.group(GROUP, TEACHER, "#cleaner", topic=(HOMEWORK, "Homework"))
    [status] = h.api.sent(GROUP)
    assert status.ephemeral_message_parameters.receiver_user_id == TEACHER and status.message_thread_id == HOMEWORK
