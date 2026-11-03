"""A finished announcement sent or forwarded to the bot, then copied to groups exactly as it is."""
import asyncio

from aiogram.methods import CopyMessage, CopyMessages, EditMessageText, ForwardMessage, PinChatMessage
from sqlalchemy import select

from bot.db.models import MediaDraft
from test_media_announce import GROUP_A, GROUP_B, PHOTO, school
from test_webapp_api import ADMIN, TEACHER, ok

VIDEO = {"file_id": "BAACvideo", "file_unique_id": "uvideo", "width": 640, "height": 360, "duration": 12}


def prompts(wh) -> list[str]:
    """Callback data of the bot's "Send to groups" buttons."""
    out = []
    for m in wh.api.sent(ADMIN):
        rows = getattr(m.reply_markup, "inline_keyboard", None)
        if rows and rows[0][0].callback_data.startswith("fwd:"):
            out.append(rows[0][0].callback_data)
    return out


async def send_to_all(wh, data, reply_to=None):
    await wh.callback(ADMIN, data, reply_to=reply_to)
    await wh.callback(ADMIN, "ann:all:0")
    await wh.callback(ADMIN, "ann:send:0")


async def test_text_sent_to_bot_goes_to_groups_as_is(wh):
    await school(wh)
    wh.api.requests.clear()
    await wh.private(ADMIN, "Ertaga bayram")
    [data] = prompts(wh)
    assert "yuboraymi" in wh.api.sent(ADMIN)[-1].text
    assert wh.api.sent(kind=CopyMessage) == []  # nothing goes out until the admin picks groups

    mid = int(data.split(":")[1])
    original = {"message_id": mid, "date": 0, "chat": {"id": ADMIN, "type": "private"}, "text": "Ertaga bayram"}
    await send_to_all(wh, data, reply_to=original)
    assert "Qaysi guruhlarga" in wh.api.sent(ADMIN, kind=EditMessageText)[0].text
    copies = wh.api.sent(kind=CopyMessage)
    assert [(c.chat_id, c.from_chat_id, c.message_id) for c in copies] == [(GROUP_A, ADMIN, mid), (GROUP_B, ADMIN, mid)]
    [item] = await ok("announce.history")
    assert item["preview"] == "Ertaga bayram" and item["groups"] == 2


async def test_album_sent_to_bot_goes_out_as_one_album(wh):
    await school(wh)
    wh.api.requests.clear()
    # Telegram delivers each item of an album as its own update, possibly at the same time.
    await asyncio.gather(
        wh.private_media(ADMIN, photo=PHOTO, media_group_id="alb1", caption="Tadbir rasmlari"),
        wh.private_media(ADMIN, video=VIDEO, media_group_id="alb1"),
        wh.private_media(ADMIN, photo=PHOTO, media_group_id="alb1"),
    )
    [data] = prompts(wh)  # one offer for the whole album
    await send_to_all(wh, data)

    async with wh.sessionmaker() as s:
        ids = sorted(d.message_id for d in (await s.scalars(select(MediaDraft))).all())
    albums = wh.api.sent(kind=CopyMessages)
    assert [a.chat_id for a in albums] == [GROUP_A, GROUP_B]
    assert all(a.from_chat_id == ADMIN and a.message_ids == ids for a in albums)
    [item] = await ok("announce.history")
    assert item["preview"] == "🖼🎬🖼 Tadbir rasmlari"
    deleted = await ok("announce.delete", {"id": item["id"]})
    assert deleted["total"] == 6  # every photo in both groups


async def test_announce_command_then_album_opens_the_picker(wh):
    await school(wh)
    await wh.private(ADMIN, "/announce")
    wh.api.requests.clear()
    await wh.private_media(ADMIN, photo=PHOTO, media_group_id="alb2", caption="Bayram")
    await wh.private_media(ADMIN, photo=PHOTO, media_group_id="alb2")
    assert [m.text for m in wh.api.sent(ADMIN)] == ["Qaysi guruhlarga yuborilsin? Tanlangan: <b>0</b>"]

    await wh.callback(ADMIN, f"ann:grp:{GROUP_B}")
    await wh.callback(ADMIN, "ann:pin:0")
    await wh.callback(ADMIN, "ann:send:0")
    [album] = wh.api.sent(kind=CopyMessages)
    assert album.chat_id == GROUP_B and len(album.message_ids) == 2
    assert [p.chat_id for p in wh.api.sent(kind=PinChatMessage)] == [GROUP_B]


async def test_message_telegram_wont_copy_is_forwarded(wh):
    await school(wh)
    await wh.private(ADMIN, "Kanaldan forward qilingan post")
    [data] = prompts(wh)
    wh.api.requests.clear()
    wh.api.reject_copy = True
    await send_to_all(wh, data)
    assert len(wh.api.sent(kind=CopyMessage)) == 1  # tried once, then forwarded everywhere
    assert [f.chat_id for f in wh.api.sent(kind=ForwardMessage)] == [GROUP_A, GROUP_B]
    report = wh.api.sent(ADMIN, kind=EditMessageText)[-1].text
    assert "2/2" in report and "forward" in report


async def test_only_announcers_get_the_offer(wh):
    await school(wh)
    await wh.register(TEACHER)
    wh.api.requests.clear()
    await wh.private(TEACHER, "Salom")
    await wh.private(ADMIN, "/nosuchcommand")
    assert "tushunmadim" in wh.api.sent(TEACHER)[-1].text
    assert "tushunmadim" in wh.api.sent(ADMIN)[-1].text
    assert prompts(wh) == []
    await wh.callback(TEACHER, "fwd:5")
    async with wh.sessionmaker() as s:
        assert (await s.scalars(select(MediaDraft))).all() == []
