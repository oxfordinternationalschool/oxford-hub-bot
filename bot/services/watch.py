"""Watching the class groups.

Insulting words: the message is saved at once (text, writer, link) and sent to the chosen admins,
forwarded as well, so it stays as proof even if the writer deletes it. Nothing appears in the
group, so the writer doesn't know. Telegram doesn't let a bot stop someone deleting their own
message; the saved copy is what counts.

Replies to an announcement: its author is told, with a button to that reply in the group.
"""
import html
import json
import logging
import re
import time

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.db.models import Announcement, AnnouncementMessage, FlaggedMessage, Group, Setting, User
from bot.i18n import t
from bot.services.calls import message_link

log = logging.getLogger(__name__)

# A word matches as written; a word ending in * matches anything starting with it.
# Cyrillic and Latin spellings are compared alike (see normalize), so one spelling is enough.
DEFAULT_WORDS = [
    # Russian
    "хуй", "хуйн*", "хуе*", "нахуй", "нахуя", "похуй*", "пизд*", "ебат*", "ебан*", "ебал*", "ебл*", "ебуч*",
    "уеб*", "выеб*", "заеб*", "долбоеб*", "долбаеб*", "бля*", "сука", "суки", "сучк*", "мудак*", "мудил*",
    "пидор*", "пидар*", "гандон*", "шлюх*", "залуп*", "дебил*", "сволоч*", "тварь", "урод*",
    # Uzbek
    "jalab*", "qanjiq*", "kanjik*", "itvachcha*", "haromi", "haromzoda*", "qo'taq*", "dalbayob*", "dalbaeb*", "dolbayob*",
    "sikay*", "sikaman", "sikib*", "sikdim", "sikvor*",
    # English
    "fuck*", "motherf*", "bitch*", "asshole*",
]

_CYR = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "j", "з": "z", "и": "i", "й": "y",
    "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "", "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "ў": "o", "қ": "q", "ғ": "g", "ҳ": "x", "і": "i",
})
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "@": "a", "$": "s"})


def normalize(text: str) -> str:
    """Lower case, Cyrillic as Latin, h/kh as x, no apostrophes, look-alike digits as letters,
    and no doubled letters ("suuuka" -> "suka")."""
    s = text.lower().translate(_CYR)
    s = re.sub(r"[ʻʼ'’`‘]", "", s)
    s = s.replace("kh", "x").replace("h", "x").translate(_LEET)
    return re.sub(r"(.)\1+", r"\1", s)


def compile_words(words: list[str]) -> list[tuple[str, bool, str]]:
    """(normalized stem, is a prefix, the word as the admin wrote it)."""
    out = []
    for w in words:
        w = w.strip()
        prefix = w.endswith("*")
        stem = normalize(w.rstrip("*").strip())
        if len(stem) >= 2:
            out.append((stem, prefix, w))
    return out


def find_words(text: str, patterns: list[tuple[str, bool, str]]) -> list[str]:
    """The listed words found in the text, as the admin wrote them."""
    tokens = set(re.findall(r"[a-z]+", normalize(text)))
    found = []
    for stem, prefix, word in patterns:
        if any(tok.startswith(stem) if prefix else tok == stem for tok in tokens):
            found.append(word)
    return found


# ---------- Settings (kept in the database; read at most once a minute per process) ----------

ABUSE_ON, ABUSE_WORDS, ABUSE_TO = "abuse_on", "abuse_words", "abuse_to"
_cache: dict = {"at": 0.0}
CACHE_SECONDS = 60


async def get_setting(session: AsyncSession, key: str, default=None):
    row = await session.get(Setting, key)
    return json.loads(row.value) if row else default


async def set_setting(session: AsyncSession, key: str, value) -> None:
    row = await session.get(Setting, key)
    if row is None:
        session.add(Setting(key=key, value=json.dumps(value, ensure_ascii=False)))
    else:
        row.value = json.dumps(value, ensure_ascii=False)
    await session.commit()
    _cache["at"] = 0.0


def forget_settings() -> None:
    _cache["at"] = 0.0


async def abuse_settings(session: AsyncSession) -> dict:
    """{on, words, patterns, to}: `to` is the list of admins told (default: the main admins)."""
    if time.monotonic() - _cache["at"] > CACHE_SECONDS:
        words = await get_setting(session, ABUSE_WORDS)
        to = await get_setting(session, ABUSE_TO)
        _cache.update(
            at=time.monotonic(), on=await get_setting(session, ABUSE_ON, True),
            words=words if words is not None else DEFAULT_WORDS,
            to=to if to is not None else sorted(settings.admin_ids),
        )
        _cache["patterns"] = compile_words(_cache["words"])
    return _cache


# ---------- Watching messages ----------

def _who(message: Message) -> tuple[int | None, str, str | None]:
    if message.from_user and not (message.sender_chat and message.sender_chat.id == message.chat.id):
        return message.from_user.id, message.from_user.full_name, message.from_user.username
    chat = message.sender_chat or message.chat
    return None, chat.title or "—", getattr(chat, "username", None)


def _aimed_at(message: Message) -> tuple[int | None, str | None, str | None]:
    """(id, name, text replied to) of whom the message was aimed at: the person it replies to
    (not a topic's opening message), plus anyone @mentioned."""
    names, to_id, reply_text = [], None, None
    reply = message.reply_to_message
    if reply is not None and reply.forum_topic_created is None:
        if reply.from_user is not None:
            to_id = reply.from_user.id
            names.append(reply.from_user.full_name + (f" (@{reply.from_user.username})" if reply.from_user.username else ""))
        elif reply.sender_chat is not None:
            names.append(reply.sender_chat.title or "—")
        reply_text = reply.text or reply.caption
    text = message.text or message.caption or ""
    for e in (message.entities or message.caption_entities or []):
        if e.type == "mention":
            names.append(e.extract_from(text))
        elif e.type == "text_mention" and e.user is not None:
            to_id = to_id or e.user.id
            names.append(e.user.full_name)
    return to_id, ", ".join(dict.fromkeys(names))[:255] or None, reply_text


def _who_text(user_id: int | None, name: str, username: str | None) -> str:
    parts = [html.escape(name)]
    if username:
        parts.append("@" + username)
    if user_id:
        parts.append(f"ID {user_id}")
    return " · ".join(parts)


def _link_button(lang: str, chat_id: int, message_id: int) -> InlineKeyboardMarkup | None:
    url = message_link(chat_id, message_id)
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "go_to_message"), url=url)]]) if url else None


async def _group_label(session: AsyncSession, message: Message) -> str:
    group = await session.get(Group, message.chat.id)
    return group.label if group else (message.chat.title or str(message.chat.id))


async def check_abuse(bot: Bot, session: AsyncSession, message: Message, edited: bool = False) -> bool:
    text = message.text or message.caption or ""
    if not text or (message.from_user and message.from_user.id == bot.id):
        return False
    conf = await abuse_settings(session)
    if not conf["on"]:
        return False
    found = find_words(text, conf["patterns"])
    if not found:
        return False

    user_id, name, username = _who(message)
    to_id, to_name, reply_text = _aimed_at(message)
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.video or message.document:
        file_id = (message.video or message.document).file_id
    session.add(FlaggedMessage(
        chat_id=message.chat.id, message_id=message.message_id, user_id=user_id, user_name=name[:255],
        username=username, text=text, words=", ".join(found)[:255], edited=edited, file_id=file_id,
        to_user_id=to_id, to_name=to_name, reply_text=reply_text,
    ))
    await session.commit()

    group = await _group_label(session, message)
    for admin_id in conf["to"]:
        admin = await session.get(User, admin_id)
        lang = admin.lang if admin else settings.default_lang
        try:
            forwarded = None
            try:  # the original, so who wrote it and what stays visible even once it is deleted
                forwarded = await bot.forward_message(admin_id, message.chat.id, message.message_id)
            except TelegramAPIError as e:  # e.g. the group forbids forwarding: the text below still has it
                log.info("Cannot forward flagged message: %s", e)
            await bot.send_message(
                admin_id,
                t(lang, "abuse_alert_edited" if edited else "abuse_alert", group=html.escape(group),
                  who=_who_text(user_id, name, username), words=html.escape(", ".join(found)), text=html.escape(text[:3000]),
                  to="\n" + t(lang, "abuse_to", to=html.escape(to_name)) if to_name else ""),
                reply_markup=_link_button(lang, message.chat.id, message.message_id),
                reply_to_message_id=forwarded.message_id if forwarded else None,
            )
        except TelegramAPIError as e:
            log.warning("Cannot alert %s about a flagged message: %s", admin_id, e)
    return True


async def notify_reply(bot: Bot, session: AsyncSession, message: Message) -> bool:
    """Someone answered an announcement in a group: its author gets the reply and a link to it."""
    reply = message.reply_to_message
    if reply is None or reply.from_user is None or reply.from_user.id != bot.id or message.from_user is None:
        return False
    if message.from_user.id == bot.id:
        return False
    sent = await session.scalar(select(AnnouncementMessage).where(
        AnnouncementMessage.chat_id == message.chat.id, AnnouncementMessage.message_id == reply.message_id,
    ).limit(1))
    if sent is None:
        return False
    ann = await session.get(Announcement, sent.announcement_id)
    if ann is None or ann.author_id == message.from_user.id:
        return False
    author = await session.get(User, ann.author_id)
    lang = author.lang if author else settings.default_lang
    user_id, name, username = _who(message)
    text = message.text or message.caption or "📎"
    try:
        await bot.send_message(
            ann.author_id,
            t(lang, "ann_reply", group=html.escape(await _group_label(session, message)),
              who=_who_text(user_id, name, username), ann=html.escape((ann.preview or "")[:120]), text=html.escape(text[:3000])),
            reply_markup=_link_button(lang, message.chat.id, message.message_id),
        )
    except TelegramAPIError as e:
        log.warning("Cannot tell %s about a reply: %s", ann.author_id, e)
        return False
    return True
