"""Fixing a sent announcement: new text in every group, or deleting it from some groups only."""
from aiogram.methods import DeleteMessage, EditMessageCaption, EditMessageText

from test_forward_announce import prompts, send_to_all
from test_media_announce import GROUP_A, GROUP_B, school, upload
from test_webapp_api import ADMIN, api, ok

BOTH = [GROUP_A, GROUP_B]


async def send(html, **extra):
    return (await ok("announce.send", {"html": html, "chat_ids": BOTH, "pin": False, **extra}))["id"]


def edits(wh, kind=EditMessageText):
    return [r for r in wh.api.requests if isinstance(r, kind) and r.chat_id in BOTH]


async def test_text_is_changed_in_every_group(wh):
    await school(wh)
    ann = await send("Ertaga <b>soat 9</b> da")
    got = await ok("announce.get", {"id": ann})
    assert got["editable"] and got["html"] == "Ertaga <b>soat 9</b> da" and got["limit"] == 4096
    assert [g["chat_id"] for g in got["groups"]] == BOTH

    r = await ok("announce.edit", {"id": ann, "html": "Ertaga <b>soat 10</b> da"})
    assert r == {"edited": 2, "total": 2, "failed": []}
    assert {(e.chat_id, e.text) for e in edits(wh)} == {(c, "Ertaga <b>soat 10</b> da") for c in BOTH}
    [item] = await ok("announce.history")
    assert item["preview"] == "Ertaga soat 10 da"
    assert (await ok("announce.get", {"id": ann}))["html"] == "Ertaga <b>soat 10</b> da"


async def test_photo_caption_is_changed(wh):
    await school(wh)
    photo = await upload("tadbir.jpg", "image/jpeg")
    ann = await send("Tadbir", media_ids=[photo["id"]])
    assert (await ok("announce.get", {"id": ann}))["limit"] == 1024
    await ok("announce.edit", {"id": ann, "html": "Tadbir ko'chirildi"})
    assert {e.caption for e in edits(wh, EditMessageCaption)} == {"Tadbir ko'chirildi"}
    assert edits(wh) == []
    [item] = await ok("announce.history")
    assert item["preview"].endswith("Tadbir ko'chirildi") and item["preview"] != "Tadbir ko'chirildi"  # icon kept

    status, body = await api("announce.edit", {"id": ann, "html": "x" * 1100})
    assert status == 400 and "1024" in body["message"]


async def test_slideshow_is_sent_again_with_the_new_text(wh):
    await school(wh)
    a, b = await upload("a.jpg", "image/jpeg"), await upload("b.jpg", "image/jpeg")
    ann = await send("Galereya", media_ids=[a["id"], b["id"]], layout="slideshow")
    await ok("announce.edit", {"id": ann, "html": "Yangi galereya"})
    [one, two] = edits(wh)
    assert one.rich_message is not None and one.text is None


async def test_announcement_sent_through_the_bot_can_be_edited(wh):
    await school(wh)
    await wh.private(ADMIN, "Ertaga bayram")
    [data] = prompts(wh)
    original = {"message_id": int(data.split(":")[1]), "date": 0, "chat": {"id": ADMIN, "type": "private"}, "text": "Ertaga bayram"}
    await send_to_all(wh, data, reply_to=original)
    [item] = await ok("announce.history")
    got = await ok("announce.get", {"id": item["id"]})
    assert got["editable"] and got["html"] == "Ertaga bayram"
    r = await ok("announce.edit", {"id": item["id"], "html": "Indinga bayram"})
    assert r["edited"] == 2 and {e.text for e in edits(wh)} == {"Indinga bayram"}


async def test_delete_from_some_groups_only(wh):
    await school(wh)
    ann = await send("Faqat 7-A uchun emas edi")
    r = await ok("announce.delete", {"id": ann, "chat_ids": [GROUP_A]})
    assert r["deleted"] == 1 and not r["all_gone"]
    assert [d.chat_id for d in wh.api.sent(kind=DeleteMessage)] == [GROUP_A]
    assert [g["chat_id"] for g in (await ok("announce.get", {"id": ann}))["groups"]] == [GROUP_B]
    [item] = await ok("announce.history")
    assert item["groups"] == 1 and not item["deleted"]

    await ok("announce.edit", {"id": ann, "html": "Tuzatildi"})
    assert [e.chat_id for e in edits(wh)] == [GROUP_B]  # only where it still is

    r = await ok("announce.delete", {"id": ann, "chat_ids": [GROUP_B]})
    assert r["all_gone"]
    [item] = await ok("announce.history")
    assert item["deleted"]
