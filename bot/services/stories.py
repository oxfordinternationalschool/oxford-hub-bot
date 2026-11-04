"""Announcements as stories on the school's Telegram account.

The account connects the bot in its own Telegram settings (Secretary Mode, with the
"Manage stories" right) and an admin approves it; the bot then posts on its behalf.
Telegram doesn't let bots post stories to channels or groups, only to such an account.
"""
import html
import io

from aiogram import Bot
from aiogram.types import BufferedInputFile, InputStoryContentPhoto
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import MediaDraft, StoryAccount

STORY_SIZE = (1080, 1920)  # Telegram accepts story photos of exactly this size
STORY_HOURS = (6, 12, 24, 48)  # the periods Telegram allows
CAPTION_MAX = 2048


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


async def post_story(bot: Bot, account: StoryAccount, file_id: str, caption: str | None, hours: int) -> None:
    file = await bot.get_file(file_id)
    raw = await bot.download_file(file.file_path)
    # `photo` is typed as an "attach://" string; given a file this way, aiogram uploads it under that name.
    content = InputStoryContentPhoto.model_construct(photo=BufferedInputFile(story_image(raw.read()), "story.jpg"))
    await bot.post_story(
        business_connection_id=account.connection_id, content=content, active_period=hours * 3600, caption=caption,
    )
