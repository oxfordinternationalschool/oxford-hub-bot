"""Attachments for announcements: photos, videos, voice notes and files, alone or as an album.

Every attachment is a MediaDraft: something the admin sent to the bot, or a file uploaded
from the Mini App (the bot posts it to the admin's own chat once to get Telegram's file_id).
Sending by file_id never re-uploads, so size doesn't matter and a voice note stays a voice note.
"""
import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    BufferedInputFile, InputMediaAudio, InputMediaDocument, InputMediaPhoto, InputMediaVideo, InputRichBlockCollage,
    InputRichBlockPhoto, InputRichBlockSlideshow, InputRichBlockVideo, InputRichMessage, Message,
)

from bot.db.models import MediaDraft
from bot.services.broadcast import Sender
from bot.services.rich_text import to_rich_blocks

log = logging.getLogger(__name__)

# Telegram's caption limit (visible characters); longer text goes in a message after the media.
CAPTION_LIMIT = 1024
ALBUM_MAX = 10
NO_CAPTION = {"video_note"}

# Bot method and its file argument, per kind.
SEND_METHODS = {
    "photo": ("send_photo", "photo"),
    "video": ("send_video", "video"),
    "voice": ("send_voice", "voice"),
    "audio": ("send_audio", "audio"),
    "animation": ("send_animation", "animation"),
    "document": ("send_document", "document"),
    "video_note": ("send_video_note", "video_note"),
}
# Kinds that may share an album: photos and videos together, files only with files, audio with audio.
ALBUM_FAMILY = {"photo": "visual", "video": "visual", "document": "document", "audio": "audio"}
INPUT_MEDIA = {"photo": InputMediaPhoto, "video": InputMediaVideo, "document": InputMediaDocument, "audio": InputMediaAudio}


@dataclass
class MediaInfo:
    kind: str
    file_id: str
    thumb_file_id: str | None
    file_name: str | None
    duration: int | None


def describe_media(message: Message) -> MediaInfo | None:
    if message.photo:
        sizes = message.photo
        # A preview of ~320px is plenty for the Mini App's thumbnails.
        thumb = next((s for s in sizes if max(s.width, s.height) >= 320), sizes[-1])
        return MediaInfo("photo", sizes[-1].file_id, thumb.file_id, None, None)
    if message.animation:  # checked before document: GIFs carry both
        a = message.animation
        return MediaInfo("animation", a.file_id, a.thumbnail and a.thumbnail.file_id, a.file_name, a.duration)
    if message.video:
        v = message.video
        return MediaInfo("video", v.file_id, v.thumbnail and v.thumbnail.file_id, v.file_name, v.duration)
    if message.voice:
        return MediaInfo("voice", message.voice.file_id, None, None, message.voice.duration)
    if message.video_note:
        n = message.video_note
        return MediaInfo("video_note", n.file_id, n.thumbnail and n.thumbnail.file_id, None, n.duration)
    if message.audio:
        a = message.audio
        return MediaInfo("audio", a.file_id, a.thumbnail and a.thumbnail.file_id, a.file_name or a.title, a.duration)
    if message.document:
        d = message.document
        return MediaInfo("document", d.file_id, d.thumbnail and d.thumbnail.file_id, d.file_name, None)
    return None


def upload_kind(mime: str, name: str) -> str:
    mime, name = (mime or "").lower(), (name or "").lower()
    if mime in ("image/jpeg", "image/png", "image/webp"):
        return "photo"
    if mime == "image/gif":
        return "animation"
    if mime == "video/mp4" or name.endswith(".mp4"):
        return "video"
    if mime in ("audio/ogg", "audio/opus") or name.endswith((".ogg", ".oga", ".opus")):
        return "voice"
    if mime.startswith("audio/") or name.endswith((".mp3", ".m4a")):
        return "audio"
    return "document"


async def upload_to_owner(bot: Bot, user_id: int, kind: str, data: bytes, filename: str) -> tuple[Message, MediaInfo]:
    """Posts an uploaded file to the admin's own chat so Telegram stores it and gives a file_id."""
    method, field = SEND_METHODS[kind]
    message = await getattr(bot, method)(user_id, **{field: BufferedInputFile(data, filename)}, disable_notification=True)
    info = describe_media(message)
    if info is None:  # Telegram may store e.g. an odd image as a document
        raise ValueError("unrecognised upload")
    return message, info


def album_problem(drafts: list[MediaDraft]) -> str | None:
    """Why these attachments can't go out together (an i18n key), or None."""
    if len(drafts) <= 1:
        return None
    if len(drafts) > ALBUM_MAX:
        return "webapp_album_max"
    families = {ALBUM_FAMILY.get(d.kind) for d in drafts}
    if None in families or len(families) > 1 or any(not d.file_id for d in drafts):
        return "webapp_album_mix"
    return None


async def _text(bot: Bot, chat_id: int, html_text: str, plain: str) -> Message:
    try:
        return await bot.send_message(chat_id, html_text, parse_mode="HTML")
    except TelegramBadRequest as e:
        if "parse" not in str(e).lower():
            raise
        return await bot.send_message(chat_id, plain, parse_mode=None)


LAYOUTS = ("album", "slideshow", "collage")


def layout_problem(drafts: list[MediaDraft], layout: str) -> str | None:
    """Slideshows and collages take 2–10 photos/videos (an i18n key), or None."""
    if layout == "album":
        return None
    if len(drafts) < 2 or any(ALBUM_FAMILY.get(d.kind) != "visual" or not d.file_id for d in drafts):
        return "webapp_layout_needs_photos"
    return album_problem(drafts)


def _rich_sender(bot: Bot, drafts: list[MediaDraft], html_text: str, layout: str, fallback: Sender) -> Sender:
    """A Telegram rich message: the photos/videos as a slideshow (← →) or collage, then the text.
    Falls back to an ordinary album where Telegram refuses the rich message."""
    def media_block(d: MediaDraft):
        if d.kind == "video":
            return InputRichBlockVideo(video=InputMediaVideo(media=d.file_id))
        return InputRichBlockPhoto(photo=InputMediaPhoto(media=d.file_id))

    container = InputRichBlockSlideshow if layout == "slideshow" else InputRichBlockCollage
    message = InputRichMessage(blocks=[container(blocks=[media_block(d) for d in drafts]), *to_rich_blocks(html_text)])

    async def send(chat_id: int):
        try:
            return await bot.send_rich_message(chat_id, rich_message=message)
        except TelegramBadRequest as e:
            log.warning("Rich message refused in %s (%s); sending an album instead", chat_id, e)
            return await fallback(chat_id)

    return send


def announcement_sender(
    bot: Bot, drafts: list[MediaDraft], html_text: str, plain: str, layout: str = "album",
) -> Sender:
    """Builds the per-group sender for a text, a single attachment, an album, a slideshow or a collage."""
    if layout in ("slideshow", "collage") and len(drafts) >= 2:
        album = announcement_sender(bot, drafts, html_text, plain)
        return _rich_sender(bot, drafts, html_text, layout, fallback=album)
    if not drafts:
        return lambda chat_id: _text(bot, chat_id, html_text, plain)

    caption_fits = bool(plain) and len(plain) <= CAPTION_LIMIT

    if len(drafts) == 1:
        draft = drafts[0]
        with_caption = caption_fits and draft.kind not in NO_CAPTION

        async def send_one(chat_id: int) -> list:
            extra = {"caption": html_text, "parse_mode": "HTML"} if with_caption else {}
            if draft.file_id:
                method, field = SEND_METHODS[draft.kind]
                sent = [await getattr(bot, method)(chat_id, **{field: draft.file_id}, **extra)]
            else:  # drafts saved before file ids were recorded
                sent = [await bot.copy_message(chat_id, draft.chat_id, draft.message_id, **extra)]
            if plain and not with_caption:
                sent.append(await _text(bot, chat_id, html_text, plain))
            return sent

        return send_one

    def album() -> list:
        items = []
        for i, d in enumerate(drafts):
            extra = {"caption": html_text, "parse_mode": "HTML"} if i == 0 and caption_fits else {}
            items.append(INPUT_MEDIA[d.kind](media=d.file_id, **extra))
        return items

    async def send_album(chat_id: int) -> list:
        sent = list(await bot.send_media_group(chat_id, media=album()))
        if plain and not caption_fits:
            sent.append(await _text(bot, chat_id, html_text, plain))
        return sent

    return send_album
