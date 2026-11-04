"""Announcements as stories on the school's Telegram account, connected in its settings (Secretary Mode)."""
import io

from aiogram.methods import EditMessageReplyMarkup, EditMessageText, PostStory
from aiogram.types import BufferedInputFile
from PIL import Image

from bot.services.stories import story_image
from test_forward_announce import prompts, send_to_all
from test_media_announce import GROUP_A, PHOTO, school, upload
from test_webapp_api import ADMIN, TEACHER, ok

SCHOOL = 500  # the school's own Telegram account


def buttons(msg) -> list[str]:
    rows = getattr(msg.reply_markup, "inline_keyboard", None) or []
    return [b.callback_data for row in rows for b in row]


async def connect_school(wh, stories=True) -> str:
    """The school account connects the bot; returns the admin's "approve" button."""
    await wh.business_connection(SCHOOL, stories=stories)
    return next(d for d in buttons(wh.api.sent(ADMIN)[-1]) if d.startswith("storyacc:ok"))


def test_story_image_fills_the_story_frame():
    for size in ((1600, 900), (600, 1200), (1080, 1920)):
        raw = io.BytesIO()
        Image.new("RGB", size, "red").save(raw, "JPEG")
        with Image.open(io.BytesIO(story_image(raw.getvalue()))) as img:
            assert img.size == (1080, 1920) and img.format == "JPEG"


async def test_school_account_is_approved_by_an_admin(wh):
    await school(wh)
    await wh.register(TEACHER)
    approve = await connect_school(wh)
    assert "User500" in wh.api.sent(ADMIN)[-1].text and "ruxsati bor" in wh.api.sent(ADMIN)[-1].text

    await wh.callback(TEACHER, approve)  # only admins decide
    assert (await ok("me"))["story_account"] is None
    await wh.callback(ADMIN, approve)
    assert "maktab akkaunti" in wh.api.sent(ADMIN, kind=EditMessageText)[-1].text
    assert (await ok("me"))["story_account"] == "User500 (@user500)"

    await wh.business_connection(SCHOOL, enabled=False)
    assert "uzdi" in wh.api.sent(ADMIN)[-1].text
    assert (await ok("me"))["story_account"] is None


async def test_missing_story_right_is_explained(wh):
    await school(wh)
    await wh.business_connection(SCHOOL, stories=False)
    card = wh.api.sent(ADMIN)[-1].text
    assert "Manage stories" in card and "@school_bot" in card


async def test_photo_announcement_goes_out_as_a_story(wh):
    await school(wh)
    await wh.callback(ADMIN, await connect_school(wh))
    await wh.private_media(ADMIN, photo=PHOTO, caption="Bayram <tabrigi>")
    [data] = prompts(wh)
    wh.api.requests.clear()
    await send_to_all(wh, data)

    [offer] = [d for d in buttons(wh.api.sent(ADMIN, kind=EditMessageText)[-1]) if d.startswith("story:")]
    await wh.callback(ADMIN, offer)
    picks = [d for d in buttons(wh.api.sent(ADMIN, kind=EditMessageReplyMarkup)[-1]) if d.startswith("story:")]
    ann = offer.split(":")[1]
    assert picks == [f"story:{ann}:{h}" for h in (6, 12, 24, 48)]

    await wh.callback(ADMIN, picks[2])
    [story] = wh.api.sent(kind=PostStory)
    assert story.business_connection_id == "bc1" and story.active_period == 24 * 3600
    assert story.caption == "Bayram &lt;tabrigi&gt;"
    assert isinstance(story.content.photo, BufferedInputFile)
    with Image.open(io.BytesIO(story.content.photo.data)) as img:
        assert img.size == (1080, 1920)
    assert "Story qo'yildi" in wh.api.sent(ADMIN, kind=EditMessageText)[-1].text


async def test_no_story_offer_without_an_approved_account(wh):
    await school(wh)
    await connect_school(wh)  # connected, but nobody approved it
    await wh.private_media(ADMIN, photo=PHOTO)
    [data] = prompts(wh)
    await send_to_all(wh, data)
    assert not [d for d in buttons(wh.api.sent(ADMIN, kind=EditMessageText)[-1]) if d.startswith("story:")]


async def test_mini_app_can_add_a_24h_story(wh):
    await school(wh)
    await wh.callback(ADMIN, await connect_school(wh))
    photo = await upload("tadbir.jpg", "image/jpeg")
    result = await ok("announce.send", {"html": "<b>Tadbir</b>", "chat_ids": [GROUP_A], "pin": False,
                                        "media_ids": [photo["id"]], "story": True})
    assert result["story"] == "ok"
    [story] = wh.api.sent(kind=PostStory)
    assert story.caption == "<b>Tadbir</b>" and story.active_period == 24 * 3600

    result = await ok("announce.send", {"html": "Faqat matn", "chat_ids": [GROUP_A], "pin": False, "story": True})
    assert result["story"] == "unavailable"
    result = await ok("announce.send", {"html": "Story so'ralmagan", "chat_ids": [GROUP_A], "pin": False,
                                        "media_ids": [photo["id"]]})
    assert result["story"] is None and len(wh.api.sent(kind=PostStory)) == 1
