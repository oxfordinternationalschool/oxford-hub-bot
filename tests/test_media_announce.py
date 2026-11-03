"""Announcements with formatting, a photo/file/voice note, or an album, from the Mini App."""
import base64

from aiogram.methods import CopyMessage, DeleteMessage, SendMediaGroup, SendMessage, SendPhoto, SendRichMessage, SendVoice
from aiogram.types import BufferedInputFile
from sqlalchemy import select

from bot.db.models import MediaDraft
from bot.services.rich_text import to_telegram_html
from test_webapp_api import ADMIN, TEACHER, api, ok

GROUP_A, GROUP_B = -1001234500, -1001234501
VOICE = {"file_id": "AwACvoice", "file_unique_id": "uvoice", "duration": 7}
PHOTO = [{"file_id": "small", "file_unique_id": "u1", "width": 90, "height": 90},
         {"file_id": "AgACphoto", "file_unique_id": "u1", "width": 1280, "height": 960}]


async def school(wh):
    await wh.register(ADMIN)
    await wh.bot_added(GROUP_A, ADMIN, title="7-A sinf")
    await wh.bot_added(GROUP_B, ADMIN, title="7-B sinf")


async def upload(name, mime, raw=b"\x89PNG fake image bytes"):
    return await ok("media.upload", {"name": name, "mime": mime, "data": base64.b64encode(raw).decode()})


def test_sanitizer_keeps_only_telegram_formatting():
    html, plain = to_telegram_html(
        '<div><b>Diqqat</b> <i>ota-onalar</i><br><a href="https://oxford.uz" onclick="x()">sayt</a> '
        '<a href="javascript:alert(1)">yomon</a><script>bad()</script> <span style="color:red">5 &lt; 6</span>'
        '<blockquote>Iqtibos <b>qalin</b></blockquote><u>tagi</u></div>'
    )
    assert html == ('<b>Diqqat</b> <i>ota-onalar</i>\n<a href="https://oxford.uz">sayt</a> yomonbad() 5 &lt; 6'
                    '<blockquote>Iqtibos <b>qalin</b></blockquote><u>tagi</u>')
    assert plain.startswith("Diqqat ota-onalar\nsayt yomon") and "<" not in plain.replace("5 < 6", "")


async def test_formatted_text_announcement(wh):
    await school(wh)
    wh.api.requests.clear()
    await ok("announce.send", {"html": "<b>Ertaga</b> dars <i>yo'q</i>", "chat_ids": [GROUP_A], "pin": False})
    msg = wh.api.sent(GROUP_A)[-1]
    assert msg.text == "<b>Ertaga</b> dars <i>yo'q</i>" and msg.parse_mode == "HTML"
    [item] = await ok("announce.history")
    assert item["preview"] == "Ertaga dars yo'q"


async def test_plain_text_is_escaped(wh):
    await school(wh)
    wh.api.requests.clear()
    await ok("announce.send", {"text": "5 < 6 & <b>", "chat_ids": [GROUP_A], "pin": False})
    assert wh.api.sent(GROUP_A)[-1].text == "5 &lt; 6 &amp; &lt;b&gt;"


async def test_voice_sent_to_bot_becomes_a_draft_and_goes_out_as_voice(wh):
    await school(wh)
    await wh.private_media(ADMIN, voice=VOICE, caption="Ertalabki xabar")
    assert "saqlandi" in wh.api.sent(ADMIN)[-1].text
    [draft] = await ok("media.list")
    assert (draft["kind"], draft["duration"], draft["album_ok"]) == ("voice", 7, False)

    wh.api.requests.clear()
    result = await ok("announce.send", {"html": "<b>Diqqat!</b>", "chat_ids": [GROUP_A, GROUP_B], "pin": False,
                                        "media_ids": [draft["id"]]})
    assert (result["sent"], result["total"]) == (2, 2)
    voices = wh.api.sent(kind=SendVoice)
    assert [v.chat_id for v in voices] == [GROUP_A, GROUP_B]
    assert all(v.voice == "AwACvoice" and v.caption == "<b>Diqqat!</b>" for v in voices)
    [item] = await ok("announce.history")
    assert item["preview"] == "🎤 Diqqat!" and item["groups"] == 2


async def test_non_announcer_media_is_not_saved(wh):
    await school(wh)
    await wh.register(TEACHER)
    await wh.private_media(TEACHER, voice=VOICE)
    async with wh.sessionmaker() as s:
        assert (await s.scalars(select(MediaDraft))).all() == []


async def test_upload_goes_to_owner_chat_once_then_by_file_id(wh):
    await school(wh)
    wh.api.requests.clear()
    draft = await upload("e'lon.png", "image/png")
    assert draft["kind"] == "photo" and draft["has_thumb"] and draft["album_ok"]
    [staged] = wh.api.sent(ADMIN, kind=SendPhoto)
    assert isinstance(staged.photo, BufferedInputFile)
    assert any(isinstance(r, DeleteMessage) and r.chat_id == ADMIN for r in wh.api.requests)

    await ok("announce.send", {"html": "", "chat_ids": [GROUP_A, GROUP_B], "pin": False, "media_ids": [draft["id"]]})
    to_groups = [r for r in wh.api.sent(kind=SendPhoto) if r.chat_id in (GROUP_A, GROUP_B)]
    assert len(to_groups) == 2 and all(isinstance(r.photo, str) for r in to_groups)


async def test_album_of_photos_and_video(wh):
    await school(wh)
    await wh.private_media(ADMIN, photo=PHOTO)
    a = await upload("1.jpg", "image/jpeg")
    b = await upload("2.mp4", "video/mp4")
    ids = [d["id"] for d in await ok("media.list")]
    wh.api.requests.clear()

    await ok("announce.send", {"html": "Tadbir <b>rasmlari</b>", "chat_ids": [GROUP_A], "pin": True,
                               "media_ids": [a["id"], b["id"], ids[-1]]})
    [album] = wh.api.sent(GROUP_A, kind=SendMediaGroup)
    assert len(album.media) == 3
    assert album.media[0].caption == "Tadbir <b>rasmlari</b>" and album.media[1].caption is None
    [item] = await ok("announce.history")
    assert item["groups"] == 1 and item["preview"].startswith("🖼🎬🖼")
    deleted = await ok("announce.delete", {"id": item["id"]})
    assert deleted["total"] == 3  # every message of the album is removed


async def test_long_text_follows_the_album(wh):
    await school(wh)
    a, b = await upload("1.jpg", "image/jpeg"), await upload("2.jpg", "image/jpeg")
    wh.api.requests.clear()
    text = "Uzun matn. " * 120  # > 1024 characters: too long for a caption
    await ok("announce.send", {"text": text, "chat_ids": [GROUP_A], "pin": False, "media_ids": [a["id"], b["id"]]})
    [album] = wh.api.sent(GROUP_A, kind=SendMediaGroup)
    assert album.media[0].caption is None
    assert wh.api.sent(GROUP_A)[-1].text == text.strip()


async def test_album_rules(wh):
    await school(wh)
    await wh.private_media(ADMIN, voice=VOICE)
    voice = (await ok("media.list"))[0]
    photo = await upload("1.jpg", "image/jpeg")
    doc = await upload("jadval.pdf", "application/pdf", b"%PDF")
    for ids in ([voice["id"], photo["id"]], [photo["id"], doc["id"]]):
        status, body = await api("announce.send", {"html": "x", "chat_ids": [GROUP_A], "pin": False, "media_ids": ids})
        assert status == 400 and body["error"] == "webapp_album_mix"
    many = [(await upload(f"{i}.jpg", "image/jpeg"))["id"] for i in range(11)]
    status, body = await api("announce.send", {"html": "x", "chat_ids": [GROUP_A], "pin": False, "media_ids": many})
    assert status == 400 and body["error"] == "webapp_album_max"


async def test_thumbnails_and_limits(wh):
    await school(wh)
    photo = await upload("1.jpg", "image/jpeg")
    thumbs = await ok("media.thumbs", {"ids": [photo["id"]]})
    assert thumbs[str(photo["id"])].startswith("data:image/jpeg;base64,")

    big = base64.b64encode(b"x" * (3 * 1024 * 1024 + 1)).decode()
    status, body = await api("media.upload", {"name": "big.bin", "mime": "", "data": big})
    assert status == 400 and body["error"] == "webapp_media_too_big"

    status, _ = await api("announce.send", {"html": "", "chat_ids": [GROUP_A], "pin": False})
    assert status == 400

    async with wh.sessionmaker() as s:
        s.add(MediaDraft(user_id=999, chat_id=999, message_id=1, kind="photo"))
        await s.commit()
        foreign = (await s.scalar(select(MediaDraft).where(MediaDraft.user_id == 999))).id
    status, _ = await api("announce.send", {"html": "x", "chat_ids": [GROUP_A], "pin": False, "media_ids": [foreign]})
    assert status == 404


async def test_old_drafts_without_file_id_still_send_by_copy(wh):
    await school(wh)
    async with wh.sessionmaker() as s:
        s.add(MediaDraft(user_id=ADMIN, chat_id=ADMIN, message_id=55, kind="voice"))
        await s.commit()
    [draft] = await ok("media.list")
    wh.api.requests.clear()
    await ok("announce.send", {"html": "", "chat_ids": [GROUP_A], "pin": False, "media_ids": [draft["id"]]})
    [copy] = wh.api.sent(kind=CopyMessage)
    assert (copy.chat_id, copy.from_chat_id, copy.message_id) == (GROUP_A, ADMIN, 55)
    assert wh.api.sent(GROUP_A, kind=SendMessage) == []


async def test_slideshow_is_a_rich_message(wh):
    await school(wh)
    a, b = await upload("1.jpg", "image/jpeg"), await upload("2.mp4", "video/mp4")
    wh.api.requests.clear()
    await ok("announce.send", {"html": "<b>Tadbir</b>\n• Soat 9:00", "chat_ids": [GROUP_A], "pin": True,
                               "media_ids": [a["id"], b["id"]], "layout": "slideshow"})
    [rich] = wh.api.sent(GROUP_A, kind=SendRichMessage)
    show, para, bullets = rich.rich_message.blocks
    assert show.type == "slideshow" and [blk.type for blk in show.blocks] == ["photo", "video"]
    assert show.blocks[0].photo.media.startswith("photo") and para.text.text == "Tadbir"
    assert bullets.type == "list" and bullets.items[0].blocks[0].text == "Soat 9:00"
    assert wh.api.sent(GROUP_A, kind=SendMediaGroup) == []

    await ok("announce.send", {"html": "", "chat_ids": [GROUP_A], "pin": False,
                               "media_ids": [a["id"], b["id"]], "layout": "collage"})
    assert wh.api.sent(GROUP_A, kind=SendRichMessage)[-1].rich_message.blocks[0].type == "collage"


async def test_rich_refused_falls_back_to_album(wh):
    await school(wh)
    a, b = await upload("1.jpg", "image/jpeg"), await upload("2.jpg", "image/jpeg")
    wh.api.requests.clear()
    wh.api.reject_rich = True
    result = await ok("announce.send", {"html": "x", "chat_ids": [GROUP_A], "pin": False,
                                        "media_ids": [a["id"], b["id"]], "layout": "slideshow"})
    assert result["sent"] == 1 and len(wh.api.sent(GROUP_A, kind=SendMediaGroup)) == 1


async def test_layout_rules(wh):
    await school(wh)
    a = await upload("1.jpg", "image/jpeg")
    doc = await upload("a.pdf", "application/pdf", b"%PDF")
    for ids in ([a["id"]], [a["id"], doc["id"]]):
        status, body = await api("announce.send", {"html": "x", "chat_ids": [GROUP_A], "pin": False,
                                                   "media_ids": ids, "layout": "slideshow"})
        assert status == 400 and body["error"] == "webapp_layout_needs_photos"
    status, _ = await api("announce.send", {"html": "x", "chat_ids": [GROUP_A], "pin": False, "layout": "carousel"})
    assert status == 400
