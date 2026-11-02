"""Attachments for announcements: media drafts sent to the bot, and files uploaded from the Mini App."""
from aiogram import Bot
from aiogram.types import BufferedInputFile, Message

from bot.db.models import MediaDraft
from bot.services.broadcast import Sender

# Telegram's caption limit; longer text goes in a separate message after the media.
CAPTION_LIMIT = 1024
NO_CAPTION = {"video_note"}

# Sending an upload: Bot method and its file argument, per kind.
UPLOAD_METHODS = {
    "photo": ("send_photo", "photo"),
    "video": ("send_video", "video"),
    "voice": ("send_voice", "voice"),
    "audio": ("send_audio", "audio"),
    "animation": ("send_animation", "animation"),
    "document": ("send_document", "document"),
}


def describe_media(message: Message) -> tuple[str, str | None, int | None] | None:
    """(kind, file name, duration) of a media message, or None for anything else."""
    if message.photo:
        return "photo", None, None
    if message.animation:  # checked before document: GIFs carry both
        return "animation", message.animation.file_name, message.animation.duration
    if message.video:
        return "video", message.video.file_name, message.video.duration
    if message.voice:
        return "voice", None, message.voice.duration
    if message.video_note:
        return "video_note", None, message.video_note.duration
    if message.audio:
        return "audio", message.audio.file_name or message.audio.title, message.audio.duration
    if message.document:
        return "document", message.document.file_name, None
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


def _uses_caption(kind: str, text: str) -> bool:
    return bool(text) and len(text) <= CAPTION_LIMIT and kind not in NO_CAPTION


def draft_sender(bot: Bot, draft: MediaDraft, text: str) -> Sender:
    with_caption = _uses_caption(draft.kind, text)

    async def send(chat_id: int) -> list:
        extra = {"caption": text, "parse_mode": None} if with_caption else {}
        sent = [await bot.copy_message(chat_id, draft.chat_id, draft.message_id, **extra)]
        if text and not with_caption:
            sent.append(await bot.send_message(chat_id, text, parse_mode=None))
        return sent

    return send


def upload_sender(bot: Bot, kind: str, data: bytes, filename: str, text: str) -> Sender:
    """Uploads the file once, then reuses Telegram's file_id for the remaining groups."""
    method, field = UPLOAD_METHODS[kind]
    with_caption = _uses_caption(kind, text)
    file: dict = {"ref": BufferedInputFile(data, filename)}

    async def send(chat_id: int) -> list:
        extra = {"caption": text, "parse_mode": None} if with_caption else {}
        message = await getattr(bot, method)(chat_id, **{field: file["ref"]}, **extra)
        if isinstance(file["ref"], BufferedInputFile):
            media = message.photo[-1] if kind == "photo" and message.photo else getattr(message, kind, None)
            if media is not None:
                file["ref"] = media.file_id
        sent = [message]
        if text and not with_caption:
            sent.append(await bot.send_message(chat_id, text, parse_mode=None))
        return sent

    return send
