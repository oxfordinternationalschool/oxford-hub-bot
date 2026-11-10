"""Watching the class groups: insulting words reach the admins (with a saved copy), and replies to
an announcement reach its author."""
from aiogram.methods import ForwardMessage
from sqlalchemy import select

from bot.db.models import AnnouncementMessage, FlaggedMessage
from bot.services.watch import DEFAULT_WORDS, compile_words, find_words
from conftest import BOT_USER
from test_media_announce import GROUP_A, GROUP_B, school
from test_webapp_api import ADMIN, ok

STUDENT = 501
WORDS = compile_words(DEFAULT_WORDS)


def test_spellings_are_caught_alike():
    assert find_words("Ты сука", WORDS) == ["сука"]
    assert find_words("suuuka blyat", WORDS) == ["бля*", "сука"]
    assert find_words("SEN JALABSAN", WORDS) == ["jalab*"]
    assert find_words("qo‘taq", WORDS) == ["qo'taq*"]
    assert find_words("ДАЛБАЁБ", WORDS) == ["dalbaeb*"]
    assert find_words("f*ck you", WORDS) == []


def test_ordinary_words_are_not_caught():
    for text in ("Ertaga soat 9 da", "Siqilyapman, uyga vazifa ko'p", "Мандарины и сукно", "Fe'l-atvori yaxshi",
                 "Суббота", "Hayot go'zal", "Классный час"):
        assert find_words(text, WORDS) == [], text


async def test_insult_is_reported_quietly_and_kept(wh):
    await school(wh)
    before = len(wh.api.requests)
    msg = await wh.group(GROUP_A, STUDENT, "sen jalab", title="7-A sinf")
    new = wh.api.requests[before:]
    assert not [r for r in new if getattr(r, "chat_id", None) == GROUP_A]  # nothing in the group
    [fwd] = [r for r in new if isinstance(r, ForwardMessage)]
    assert fwd.chat_id == ADMIN and fwd.from_chat_id == GROUP_A and fwd.message_id == msg["message_id"]
    alert = wh.api.sent(ADMIN)[-1]
    assert "Haqoratli" in alert.text and "jalab" in alert.text and "User501" in alert.text and "7-A" in alert.text
    assert alert.reply_markup.inline_keyboard[0][0].url.endswith(f"/{msg['message_id']}")

    async with wh.sessionmaker() as s:
        [row] = (await s.scalars(select(FlaggedMessage))).all()
    assert row.text == "sen jalab" and row.user_id == STUDENT and row.chat_id == GROUP_A
    got = await ok("abuse.get")
    assert got["log"][0]["text"] == "sen jalab" and got["log"][0]["chat"] == "7-A"


async def test_an_edit_into_an_insult_is_caught(wh):
    await school(wh)
    await wh._send("edited_message", {
        "message_id": 77, "date": 1, "edit_date": 2, "chat": {"id": GROUP_A, "type": "supergroup", "title": "7-A sinf"},
        "from": wh._user(STUDENT), "text": "сука",
    })
    assert "tahrirlangan" in wh.api.sent(ADMIN)[-1].text


async def test_words_and_recipients_are_set_in_the_mini_app(wh):
    await school(wh)
    got = await ok("abuse.save", {"words": ["ahmoq*"], "to": [ADMIN]})
    assert got["words"] == ["ahmoq*"] and not got["default_words"] and got["admins"][0]["on"]
    await wh.group(GROUP_A, STUDENT, "sen jalab")  # no longer listed
    await wh.group(GROUP_A, STUDENT, "Ahmoqona gap")
    async with wh.sessionmaker() as s:
        assert [r.words for r in (await s.scalars(select(FlaggedMessage))).all()] == ["ahmoq*"]

    await ok("abuse.save", {"on": False})
    await wh.group(GROUP_A, STUDENT, "ahmoq")
    async with wh.sessionmaker() as s:
        assert len((await s.scalars(select(FlaggedMessage))).all()) == 1
    assert (await ok("abuse.save", {"words": "default", "on": True}))["default_words"]


async def test_reply_to_an_announcement_reaches_its_author(wh):
    await school(wh)
    await ok("announce.send", {"html": "Ertaga yig'ilish", "chat_ids": [GROUP_A, GROUP_B], "pin": False})
    async with wh.sessionmaker() as s:
        from bot.db.models import AnnouncementMessage
        msg_id = (await s.scalars(select(AnnouncementMessage.message_id).where(AnnouncementMessage.chat_id == GROUP_A))).first()
    before = len(wh.api.sent(ADMIN))
    reply = await wh.group(GROUP_A, STUDENT, "Soat nechida?", reply_to={
        "message_id": msg_id, "date": 1, "chat": {"id": GROUP_A, "type": "supergroup"},
        "from": {"id": BOT_USER["id"], "is_bot": True, "first_name": "Hub"}, "text": "Ertaga yig'ilish"})
    [note] = wh.api.sent(ADMIN)[before:]
    assert "E'loningizga javob" in note.text and "Soat nechida?" in note.text and "Ertaga yig" in note.text
    assert note.reply_markup.inline_keyboard[0][0].url.endswith(f"/{reply['message_id']}")

    # a reply to some other message of the bot tells no one
    await wh.group(GROUP_A, STUDENT, "?", reply_to={
        "message_id": 99999, "date": 1, "chat": {"id": GROUP_A, "type": "supergroup"},
        "from": {"id": BOT_USER["id"], "is_bot": True, "first_name": "Hub"}, "text": "x"})
    assert len(wh.api.sent(ADMIN)) == before + 1


async def test_whom_it_was_aimed_at_is_kept(wh):
    await school(wh)
    teacher_msg = {"message_id": 5, "date": 1, "chat": {"id": GROUP_A, "type": "supergroup"},
                   "from": {"id": 3, "is_bot": False, "first_name": "Dilnoza", "username": "dilnoza"}, "text": "Uyga vazifa bor"}
    await wh._send("message", {
        "message_id": 6, "date": 2, "chat": {"id": GROUP_A, "type": "supergroup", "title": "7-A sinf"},
        "from": wh._user(STUDENT), "text": "jalab @bobur", "reply_to_message": teacher_msg,
        "entities": [{"type": "mention", "offset": 6, "length": 6}]})
    assert "Kimga: Dilnoza (@dilnoza), @bobur" in wh.api.sent(ADMIN)[-1].text
    [item] = (await ok("abuse.get"))["log"]
    assert item["to"] == "Dilnoza (@dilnoza), @bobur" and item["to_user_id"] == 3 and item["reply_text"] == "Uyga vazifa bor"
