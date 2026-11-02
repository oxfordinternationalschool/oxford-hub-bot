"""Announcements with a photo, file or voice note from the Mini App."""
import base64

from aiogram.methods import CopyMessage, SendMessage, SendPhoto
from aiogram.types import BufferedInputFile
from sqlalchemy import select

from bot.db.models import MediaDraft
from test_webapp_api import ADMIN, TEACHER, api, ok

GROUP_A, GROUP_B = -1001234500, -1001234501
VOICE = {"file_id": "AwACvoice", "file_unique_id": "uvoice", "duration": 7}


async def school(wh):
    await wh.register(ADMIN)
    await wh.bot_added(GROUP_A, ADMIN, title="7-A sinf")
    await wh.bot_added(GROUP_B, ADMIN, title="7-B sinf")


async def test_voice_sent_to_bot_becomes_a_draft(wh):
    await school(wh)
    await wh.private_media(ADMIN, voice=VOICE, caption="Ertalabki xabar")
    assert "saqlandi" in wh.api.sent(ADMIN)[-1].text
    [draft] = await ok("media.list")
    assert (draft["kind"], draft["duration"], draft["caption"]) == ("voice", 7, "Ertalabki xabar")


async def test_non_announcer_media_is_not_saved(wh):
    await school(wh)
    await wh.register(TEACHER)
    await wh.private_media(TEACHER, voice=VOICE)
    async with wh.sessionmaker() as s:
        assert (await s.scalars(select(MediaDraft))).all() == []


async def test_send_draft_voice_with_caption(wh):
    await school(wh)
    await wh.private_media(ADMIN, voice=VOICE)
    [draft] = await ok("media.list")
    wh.api.requests.clear()

    result = await ok("announce.send", {"text": "Diqqat!", "chat_ids": [GROUP_A, GROUP_B], "pin": False,
                                        "media": {"draft_id": draft["id"]}})
    assert (result["sent"], result["total"]) == (2, 2)
    copies = wh.api.sent(kind=CopyMessage)
    assert [c.chat_id for c in copies] == [GROUP_A, GROUP_B]
    assert all(c.from_chat_id == ADMIN and c.caption == "Diqqat!" for c in copies)
    [item] = await ok("announce.history")
    assert item["preview"].startswith("🎤") and item["groups"] == 2


async def test_upload_photo_once_then_reuse_file_id(wh):
    await school(wh)
    wh.api.requests.clear()
    data = base64.b64encode(b"\x89PNG fake image bytes").decode()
    await ok("announce.send", {"text": "", "chat_ids": [GROUP_A, GROUP_B], "pin": False,
                               "media": {"upload": {"name": "e'lon.png", "mime": "image/png", "data": data}}})
    first, second = wh.api.sent(kind=SendPhoto)
    assert isinstance(first.photo, BufferedInputFile) and first.chat_id == GROUP_A
    assert isinstance(second.photo, str) and second.photo.startswith("photo")  # Telegram's file_id
    assert wh.api.sent(kind=SendMessage) == [] or all(m.chat_id == ADMIN for m in wh.api.sent(kind=SendMessage))


async def test_long_text_goes_after_the_media(wh):
    await school(wh)
    wh.api.requests.clear()
    data = base64.b64encode(b"%PDF-1.4 fake").decode()
    text = "Uzun matn. " * 120  # > 1024 characters: too long for a caption
    await ok("announce.send", {"text": text, "chat_ids": [GROUP_A], "pin": True,
                               "media": {"upload": {"name": "jadval.pdf", "mime": "application/pdf", "data": data}}})
    texts = [m for m in wh.api.sent(GROUP_A)]
    assert len(texts) == 1 and texts[0].text == text.strip()
    [item] = await ok("announce.history")
    assert item["groups"] == 1


async def test_upload_limits_and_foreign_drafts(wh):
    await school(wh)
    big = base64.b64encode(b"x" * (3 * 1024 * 1024 + 1)).decode()
    status, body = await api("announce.send", {"text": "", "chat_ids": [GROUP_A], "pin": False,
                                               "media": {"upload": {"name": "big.bin", "mime": "", "data": big}}})
    assert status == 400 and body["error"] == "webapp_media_too_big"

    status, _ = await api("announce.send", {"text": "", "chat_ids": [GROUP_A], "pin": False})
    assert status == 400

    async with wh.sessionmaker() as s:
        s.add(MediaDraft(user_id=999, chat_id=999, message_id=1, kind="photo"))
        await s.commit()
        foreign = (await s.scalar(select(MediaDraft))).id
    status, _ = await api("announce.send", {"text": "x", "chat_ids": [GROUP_A], "pin": False, "media": {"draft_id": foreign}})
    assert status == 404
