"""Adding people to groups through a real Telegram account.

Telegram doesn't let bots add members, but a normal account can. The account's owner logs in
once on their own computer (`python -m bot.account_login`) and the session goes into the
environment (TG_API_ID, TG_API_HASH, TG_SESSION). Anyone with that session has full access to
the account, so it is never stored in the database or shown in the Mini App.

Telethon needs an "access hash" for every group and person it talks to. A serverless request
starts with an empty cache, so the hashes are kept in the database (a hash only lets this one
account address that peer).
"""
import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import utcnow
from bot.db.models import AccountAddLog, AccountChat, AccountUser, Group

log = logging.getLogger(__name__)

OK, PRIVACY, TOO_MANY, FULL, BANNED, NO_RIGHT, NOT_IN, FLOOD, UNKNOWN_USER, BASIC_GROUP, ERROR = (
    "ok", "privacy", "too_many", "full", "banned", "no_right", "not_in", "flood", "unknown_user", "basic_group", "error",
)
MAX_MEMBERS = 2000
PAUSE = 1.0  # seconds between invites, to stay well within Telegram's limits
NOTICE_EVERY = timedelta(minutes=10)


class AccountOff(Exception):
    """The account isn't configured, or its session was ended."""


def configured() -> bool:
    return all(os.getenv(k) for k in ("TG_API_ID", "TG_API_HASH", "TG_SESSION"))


@asynccontextmanager
async def open_account() -> AsyncIterator:
    """A connected client for one request."""
    if not configured():
        raise AccountOff
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    client = TelegramClient(
        StringSession(os.environ["TG_SESSION"]), int(os.environ["TG_API_ID"]), os.environ["TG_API_HASH"],
        receive_updates=False, flood_sleep_threshold=0,
    )
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise AccountOff
        yield client
    finally:
        await client.disconnect()


def _chat_right(entity) -> str:
    """Whether the account may add members to this supergroup."""
    if entity.creator or (entity.admin_rights and entity.admin_rights.invite_users):
        return OK
    banned = entity.banned_rights or entity.default_banned_rights
    return NO_RIGHT if banned and banned.invite_users else OK


async def refresh_chats(client, session: AsyncSession) -> dict[int, str]:
    """Stores the access hash of every school group the account is in; returns chat_id -> OK/NO_RIGHT."""
    known = set((await session.scalars(select(Group.chat_id).where(Group.is_active))).all())
    found: dict[int, str] = {}
    async for dialog in client.iter_dialogs():
        if dialog.id not in known or not getattr(dialog.entity, "megagroup", False):
            continue
        right = _chat_right(dialog.entity)
        row = await session.get(AccountChat, dialog.id)
        if row is None:
            session.add(AccountChat(chat_id=dialog.id, access_hash=dialog.entity.access_hash, right=right))
        else:
            row.access_hash, row.right = dialog.entity.access_hash, right
        found[dialog.id] = right
    await session.commit()
    return found


def _input_channel(chat_id: int, access_hash: int):
    from telethon.tl.types import InputChannel

    return InputChannel(int(str(chat_id).removeprefix("-100")), access_hash)


async def resolve_user(client, session: AsyncSession, user_id: int, username: str | None, name: str,
                       near_chat_ids: list[int]):
    """The person as this account can address them, or None. By username if they have one,
    otherwise by finding them in a group they are already in."""
    from telethon.errors import RPCError
    from telethon.tl.functions.channels import GetParticipantsRequest
    from telethon.tl.functions.contacts import ResolveUsernameRequest
    from telethon.tl.types import ChannelParticipantsSearch, InputUser

    row = await session.get(AccountUser, user_id)
    if row is not None:
        return InputUser(user_id, row.access_hash)

    found = None
    if username:
        try:
            resolved = await client(ResolveUsernameRequest(username))
            found = next((u for u in resolved.users if u.id == user_id), None)
        except RPCError as e:
            log.info("Cannot resolve @%s: %s", username, e)
    words = [w for w in name.split() if any(c.isalnum() for c in w)]
    if found is None and words:
        for chat_id in near_chat_ids:
            chat = await session.get(AccountChat, chat_id)
            if chat is None:
                continue
            try:
                page = await client(GetParticipantsRequest(
                    _input_channel(chat_id, chat.access_hash), ChannelParticipantsSearch(words[0]), 0, 100, 0,
                ))
            except RPCError as e:
                log.info("Cannot search members of %s: %s", chat_id, e)
                continue
            found = next((u for u in page.users if u.id == user_id), None)
            if found is not None:
                break
    if found is None:
        return None
    session.add(AccountUser(user_id=user_id, access_hash=found.access_hash))
    await session.commit()
    return InputUser(user_id, found.access_hash)


async def list_members(client, session: AsyncSession, chat_id: int) -> list[dict] | None:
    """Everyone in the group (not bots), owner and admins first; None if the account isn't in it.
    Bots can't list members, but an account can."""
    from telethon.tl.functions.channels import GetParticipantsRequest
    from telethon.tl.types import ChannelParticipantsSearch

    chat = await session.get(AccountChat, chat_id)
    if chat is None:
        await refresh_chats(client, session)
        chat = await session.get(AccountChat, chat_id)
        if chat is None:
            return None
    channel = _input_channel(chat_id, chat.access_hash)
    people: dict[int, dict] = {}
    roles: dict[int, str] = {}
    offset = 0
    while offset < MAX_MEMBERS:
        page = await client(GetParticipantsRequest(channel, ChannelParticipantsSearch(""), offset, 200, 0))
        for p in page.participants:
            kind = type(p).__name__
            roles[p.user_id] = "owner" if "Creator" in kind else "admin" if "Admin" in kind else "member"
        for u in page.users:
            if not u.bot and not u.deleted:
                name = " ".join(filter(None, (u.first_name, u.last_name))) or (u.username or str(u.id))
                people[u.id] = {"id": u.id, "name": name, "username": u.username}
        offset += len(page.participants)
        if not page.participants or offset >= page.count:
            break
    order = {"owner": 0, "admin": 1, "member": 2}
    out = [{**p, "status": roles.get(uid, "member")} for uid, p in people.items()]
    return sorted(out, key=lambda m: (order[m["status"]], m["name"].lower()))


def _error_result(e: Exception) -> str:
    from telethon import errors as er

    pairs = (
        ((er.FloodWaitError, er.PeerFloodError), FLOOD),
        ((er.UserPrivacyRestrictedError, er.UserNotMutualContactError), PRIVACY),
        ((er.UserChannelsTooMuchError,), TOO_MANY),
        ((er.UsersTooMuchError,), FULL),
        ((er.UserKickedError, er.UserBannedInChannelError), BANNED),
        ((er.ChatAdminRequiredError, er.ChatWriteForbiddenError), NO_RIGHT),
        ((er.ChannelPrivateError,), NOT_IN),
    )
    return next((result for kinds, result in pairs if isinstance(e, kinds)), ERROR)


async def add_to_chats(client, session: AsyncSession, target, chat_ids: list[int]) -> dict[int, str]:
    """Adds the person to each group, in order. Stops at Telegram's first rate limit."""
    from telethon.errors import RPCError
    from telethon.tl.functions.channels import InviteToChannelRequest

    results: dict[int, str] = {}
    for i, chat_id in enumerate(chat_ids):
        if not str(chat_id).startswith("-100"):
            results[chat_id] = BASIC_GROUP
            continue
        chat = await session.get(AccountChat, chat_id)
        if chat is None:
            results[chat_id] = NOT_IN
            continue
        if chat.right != OK:
            results[chat_id] = NO_RIGHT
            continue
        if i:
            await asyncio.sleep(PAUSE)
        try:
            sent = await client(InviteToChannelRequest(_input_channel(chat_id, chat.access_hash), [target]))
            results[chat_id] = PRIVACY if getattr(sent, "missing_invitees", None) else OK
        except RPCError as e:
            log.info("Cannot add to %s: %s", chat_id, e)
            results[chat_id] = _error_result(e)
            if results[chat_id] == FLOOD:
                results.update({c: FLOOD for c in chat_ids if c not in results})
                break
    return results


async def record(session: AsyncSession, actor_id: int, user_id: int, results: dict[int, str]) -> bool:
    """Writes the audit log; True if the account's owner should be told (once per burst)."""
    recent = await session.scalar(select(AccountAddLog.id).where(
        AccountAddLog.actor_id == actor_id, AccountAddLog.user_id == user_id,
        AccountAddLog.created_at > utcnow() - NOTICE_EVERY,
    ).limit(1))
    session.add_all(AccountAddLog(actor_id=actor_id, user_id=user_id, chat_id=c, result=r) for c, r in results.items())
    await session.commit()
    return recent is None
