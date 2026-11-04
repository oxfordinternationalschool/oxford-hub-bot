"""Announcements as stories on the school's Telegram account.

The account connects the bot in its own Telegram settings (Secretary Mode, with the
"Manage stories" right) and an admin approves it; the bot then posts on its behalf.
Telegram doesn't let bots post stories to channels or groups, only to such an account.
For those, the Mini App opens Telegram's own story editor with the picture from a signed
link (`story_link`), and the admin posts it wherever Telegram lets them.
"""
import hashlib
import hmac
import html
import io
import re
import time

from aiogram import Bot
from aiogram.types import BufferedInputFile, InputStoryContentPhoto
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.db.models import Announcement, MediaDraft, StoryAccount

STORY_SIZE = (1080, 1920)  # Telegram accepts story photos of exactly this size
STORY_HOURS = (6, 12, 24, 48)  # the periods Telegram allows
CAPTION_MAX = 2048
EDITOR_TEXT_MAX = 200  # Telegram's story editor allows 200 characters without Premium
LINK_TTL = 6 * 3600  # long enough for a Mini App screen left open a while


async def story_account(session: AsyncSession) -> StoryAccount | None:
    """The approved school account, if it is connected and lets the bot post stories."""
    return await session.scalar(
        select(StoryAccount)
        .where(StoryAccount.approved, StoryAccount.is_enabled, StoryAccount.can_post)
        .order_by(StoryAccount.updated_at.desc())
        .limit(1)
    )


def story_photo(drafts: list[MediaDraft]) -> str | None:
    """file_id of the first photo among the attachments; videos would need re-encoding for stories."""
    return next((d.file_id for d in drafts if d.kind == "photo" and d.file_id), None)


def story_caption(html_text: str, plain: str) -> str | None:
    """The announcement text for the story; story captions are shorter than messages, so long text is cut."""
    if not plain:
        return None
    if len(plain) <= CAPTION_MAX:
        return html_text
    return html.escape(plain[: CAPTION_MAX - 1] + "…", quote=False)


def story_image(raw: bytes) -> bytes:
    """Fits a photo of any shape into the 1080x1920 story frame, over a blurred, darker copy of itself."""
    with Image.open(io.BytesIO(raw)) as src:
        img = ImageOps.exif_transpose(src).convert("RGB")
    frame = ImageOps.fit(img, STORY_SIZE).filter(ImageFilter.GaussianBlur(40))
    frame = ImageEnhance.Brightness(frame).enhance(0.55)
    photo = ImageOps.contain(img, STORY_SIZE)
    frame.paste(photo, ((STORY_SIZE[0] - photo.width) // 2, (STORY_SIZE[1] - photo.height) // 2))
    out = io.BytesIO()
    frame.save(out, "JPEG", quality=90)
    return out.getvalue()


async def _story_picture(bot: Bot, file_id: str) -> bytes:
    file = await bot.get_file(file_id)
    raw = await bot.download_file(file.file_path)
    return story_image(raw.read())


async def post_story(bot: Bot, account: StoryAccount, file_id: str, caption: str | None, hours: int) -> None:
    # `photo` is typed as an "attach://" string; given a file this way, aiogram uploads it under that name.
    picture = BufferedInputFile(await _story_picture(bot, file_id), "story.jpg")
    content = InputStoryContentPhoto.model_construct(photo=picture)
    await bot.post_story(
        business_connection_id=account.connection_id, content=content, active_period=hours * 3600, caption=caption,
    )


def _sign(ann_id: int, expires: int) -> str:
    return hmac.new(settings.webhook_secret.encode(), f"story:{ann_id}:{expires}".encode(), hashlib.sha256).hexdigest()[:32]


def story_link(ann_id: int) -> str | None:
    """Path of the announcement's story picture. Telegram's story editor fetches it without
    logging in, so the link is signed and expires instead."""
    if not settings.webhook_secret:
        return None
    expires = int(time.time()) + LINK_TTL
    return f"/api?story={ann_id}.{expires}.{_sign(ann_id, expires)}"


def story_link_target(token: str) -> int | None:
    """The announcement a link points to, if the link is genuine and hasn't expired."""
    try:
        ann_id, expires, sig = token.split(".")
        ann_id, expires = int(ann_id), int(expires)
    except ValueError:
        return None
    if not settings.webhook_secret or expires < time.time() or not hmac.compare_digest(sig, _sign(ann_id, expires)):
        return None
    return ann_id


async def story_picture(bot: Bot, session: AsyncSession, ann_id: int) -> bytes | None:
    ann = await session.get(Announcement, ann_id)
    if ann is None or not ann.story_file_id:
        return None
    return await _story_picture(bot, ann.story_file_id)


def editor_text(caption_html: str | None) -> str:
    """The announcement text for Telegram's story editor: no formatting, and short enough."""
    text = html.unescape(re.sub(r"<[^>]+>", "", caption_html or "")).strip()
    return text if len(text) <= EDITOR_TEXT_MAX else text[: EDITOR_TEXT_MAX - 1] + "…"
