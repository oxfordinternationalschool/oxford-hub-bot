"""JSON API behind the admin Mini App (public/admin/index.html).

Every request is a POST with the header `Authorization: tma <initData>` and the body
{"op": "<operation>", "args": {...}}. Telegram signs initData with the bot token, so it
proves who opened the app; only admins get any data.
"""
import asyncio
import base64
import contextlib
import html
import json
import logging
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.utils.web_app import safe_parse_webapp_init_data
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.app import request_scope
from bot.config import LANGS, settings, utcnow
from bot.db.models import (
    AccountChat, Announcement, AnnouncementMessage, Call, FlaggedMessage, Floor, ForumTopic, Group, Invite, MediaDraft, Role, StaffRole,
    User, PickedUser,
)
from bot.i18n import t
from bot.services import admin_views as views
from bot.services.announcements import TEXT_LIMIT, edit_announcement, edit_problem, new_preview, text_messages
from bot.services.broadcast import broadcast, delete_announcement, save_announcement
from bot.services.media import (
    ALBUM_FAMILY, CAPTION_LIMIT, LAYOUTS, album_problem, announcement_sender, layout_problem, media_preview, upload_kind, upload_to_owner,
)
from bot.services.calls import message_link, refresh_call, set_status
from bot.services.common import admin_users, find_floor, group_sort_key, parse_class
from bot.services.group_admins import (
    admin_invite, group_status, kick_member, member_invite, member_status, new_request_id, pending_invites, person_name, picked_user,
    picked_users, picker_button,
    set_group_admin,
)
from bot.services import user_account, watch
from bot.services.menus import set_user_menu, sync_group_commands
from bot.services.topics import same_name, topics_by_chat
from bot.services.rich_text import to_telegram_html
from bot.services.roles import is_valid_key, trigger_cache
from bot.services.stories import editor_text, post_story, story_account, story_caption, story_link, story_photo
from bot.services.users import add_staff_role

log = logging.getLogger(__name__)

# Telegram issues fresh initData every time the app is opened; a day covers a long session.
INIT_DATA_MAX_AGE = 24 * 3600


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str = "") -> None:
        super().__init__(code)
        self.status, self.code, self.message = status, code, message


def _plain(html_text: str) -> str:
    return re.sub(r"<[^>]+>", "", html_text)


@dataclass
class Ctx:
    bot: Bot
    session: AsyncSession
    user: User

    @property
    def lang(self) -> str:
        return self.user.lang

    def error(self, key: str, status: int = 400, **kwargs) -> ApiError:
        return ApiError(status, key, _plain(t(self.lang, key, **kwargs)))


Handler = Callable[[Ctx, dict], Awaitable[object]]
OPS: dict[str, Handler] = {}


def op(name: str):
    def register(fn: Handler) -> Handler:
        OPS[name] = fn
        return fn
    return register


# ---------- Argument helpers ----------

def _int(args: dict, key: str, *, optional: bool = False) -> int | None:
    value = args.get(key)
    if value is None and optional:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ApiError(400, "bad_args", f"{key}: integer expected")
    return value


def _str(args: dict, key: str, max_len: int = 255, *, optional: bool = False) -> str | None:
    value = args.get(key)
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise ApiError(400, "bad_args", f"{key}: text expected")
    return value.strip()[:max_len]


def _bool(args: dict, key: str) -> bool:
    value = args.get(key)
    if not isinstance(value, bool):
        raise ApiError(400, "bad_args", f"{key}: true/false expected")
    return value


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() + "Z" if dt else None


async def _get(ctx: Ctx, model, key, error_key: str = "webapp_not_found"):
    obj = await ctx.session.get(model, key) if key is not None else None
    if obj is None:
        raise ctx.error(error_key, status=404)
    return obj


# ---------- Entry point ----------

def verify_init_data(init_data: str) -> int:
    """Returns the Telegram user id if initData is genuine and fresh."""
    try:
        data = safe_parse_webapp_init_data(settings.bot_token, init_data)
    except Exception:
        raise ApiError(401, "unauthorized")
    if data.user is None:
        raise ApiError(401, "unauthorized")
    if time.time() - data.auth_date.timestamp() > INIT_DATA_MAX_AGE:
        raise ApiError(401, "expired")
    return data.user.id


async def handle_api(init_data: str, body: bytes) -> tuple[int, dict]:
    try:
        user_id = verify_init_data(init_data)
        try:
            request = json.loads(body or b"{}")
        except ValueError:
            raise ApiError(400, "bad_json")
        if not isinstance(request, dict) or not isinstance(request.get("args", {}), dict):
            raise ApiError(400, "bad_args")
        handler = OPS.get(request.get("op"))
        if handler is None:
            raise ApiError(404, "unknown_op")

        async with request_scope() as (bot, sessionmaker):
            async with sessionmaker() as session:
                user = await session.get(User, user_id)
                if user is not None and user.id in settings.admin_ids and not user.is_admin:
                    user.is_admin = True
                    await session.commit()
                if user is None or not user.is_admin:
                    lang = user.lang if user else settings.default_lang
                    raise ApiError(403, "forbidden", _plain(t(lang, "webapp_forbidden")))
                data = await handler(Ctx(bot, session, user), request.get("args") or {})
        return 200, {"ok": True, "data": data}
    except ApiError as e:
        return e.status, {"ok": False, "error": e.code, "message": e.message}
    except Exception:
        log.exception("Mini App request failed")
        return 500, {"ok": False, "error": "server_error"}


# ---------- Serializers ----------

def _user_json(user: User, roles: list[StaffRole], me: User) -> dict:
    return {
        "id": user.id,
        "name": user.full_name,
        "username": user.username,
        "is_admin": user.is_admin,
        "can_announce": user.can_announce,
        "is_teacher": user.is_teacher,
        "is_super": user.id in settings.admin_ids,
        "is_me": user.id == me.id,
        "roles": [{"role_id": r.role_id, "floor_id": r.floor_id} for r in roles],
    }


async def _calls_json(session: AsyncSession, calls: list[Call]) -> list[dict]:
    role_ids = {c.role_id for c in calls if c.role_id}
    chat_ids = {c.chat_id for c in calls}
    user_ids = {c.requester_id for c in calls} | {c.accepted_by for c in calls if c.accepted_by}
    roles = {r.id: r for r in (await session.scalars(select(Role).where(Role.id.in_(role_ids)))).all()}
    groups = {g.chat_id: g for g in (await session.scalars(select(Group).where(Group.chat_id.in_(chat_ids)))).all()}
    users = {u.id: u for u in (await session.scalars(select(User).where(User.id.in_(user_ids)))).all()}
    return [{
        "id": c.id,
        "role": roles[c.role_id].title if c.role_id in roles else "❔",
        "class": groups[c.chat_id].label if c.chat_id in groups else str(c.chat_id),
        "status": c.status,
        "urgent": c.urgent,
        "escalated": c.escalated,
        "text": c.text,
        "requester": users[c.requester_id].full_name if c.requester_id in users else None,
        "accepter": users[c.accepted_by].full_name if c.accepted_by in users else None,
        "created_at": _iso(c.created_at),
        "accepted_at": _iso(c.accepted_at),
        "done_at": _iso(c.done_at),
    } for c in calls]


def _group_json(g: Group, topics: list | None = None) -> dict:
    topics = topics or []
    return {
        "topics": [{"id": tp.thread_id, "name": tp.name} for tp in topics],
        "announce_thread_id": g.announce_thread_id,
        "announce_topic": next((tp.name for tp in topics if tp.thread_id == g.announce_thread_id), None)
        if g.announce_thread_id else None,
        "chat_id": g.chat_id,
        "title": g.title,
        "class_name": g.class_name,
        "grade": g.grade,
        "floor_id": g.floor_id,
        "lang": g.lang,
        "bot_is_admin": g.bot_is_admin,
    }


async def _count(session: AsyncSession, model, *where) -> int:
    return await session.scalar(select(func.count()).select_from(model).where(*where))


# ---------- Overview ----------

@op("me")
async def op_me(ctx: Ctx, args: dict):
    me = await ctx.bot.me()
    account = await story_account(ctx.session)
    return {"id": ctx.user.id, "name": ctx.user.full_name, "lang": ctx.user.lang, "bot": me.username,
            "story_account": account.name if account else None, "account_ready": user_account.configured()}


@op("dashboard")
async def op_dashboard(ctx: Ctx, args: dict):
    s = ctx.session
    groups = (await s.scalars(select(Group).where(Group.is_active))).all()
    now = utcnow()
    pending = (await s.scalars(
        select(Call).where(Call.status == "pending").order_by(Call.created_at.desc()).limit(20)
    )).all()
    recent = (await s.scalars(select(Call).order_by(Call.created_at.desc()).limit(8))).all()
    return {
        "groups": len(groups),
        "groups_no_floor": sum(g.floor_id is None for g in groups),
        "groups_no_class": sum(not g.class_name for g in groups),
        "groups_not_admin": sum(not g.bot_is_admin for g in groups),
        "admins": await _count(s, User, User.is_admin),
        "announcers": await _count(s, User, User.can_announce),
        "teachers": await _count(s, User, User.is_teacher),
        "staff": await s.scalar(select(func.count(func.distinct(StaffRole.user_id)))),
        "roles": await _count(s, Role),
        "floors": await _count(s, Floor),
        "calls_day": await _count(s, Call, Call.created_at >= now - timedelta(days=1)),
        "calls_week": await _count(s, Call, Call.created_at >= now - timedelta(days=7)),
        "pending": await _calls_json(s, list(pending)),
        "recent": await _calls_json(s, list(recent)),
    }


# ---------- Roles ----------

@op("roles.list")
async def op_roles_list(ctx: Ctx, args: dict):
    counts = await views.staff_counts(ctx.session)
    return [{
        "id": r.id, "key": r.key, "emoji": r.emoji, "name": r.name,
        "floor_based": r.floor_based, "aliases": r.aliases.split(), "staff_count": counts.get(r.id, 0),
    } for r in await views.all_roles(ctx.session)]


@op("roles.create")
async def op_roles_create(ctx: Ctx, args: dict):
    key = _str(args, "key", 32)
    emoji = _str(args, "emoji", 16, optional=True) or "👤"
    name = _str(args, "name", 64, optional=True) or ""
    parts = [key, emoji] if not any(ch.isalnum() for ch in emoji) else [key]
    role, text = await views.create_role(ctx.session, ctx.lang, parts + name.split())
    if role is None:
        raise ApiError(400, "invalid", _plain(text))
    await sync_group_commands(ctx.bot, ctx.session)
    return {"id": role.id}


@op("roles.update")
async def op_roles_update(ctx: Ctx, args: dict):
    role = await _get(ctx, Role, _int(args, "id"), "role_not_found")
    if "emoji" in args:
        role.emoji = _str(args, "emoji", 16) or "👤"
    if "name" in args:
        role.name = _str(args, "name", 64) or role.key.capitalize()
    if "floor_based" in args:
        role.floor_based = _bool(args, "floor_based")
    if "aliases" in args:
        words = args["aliases"]
        if not isinstance(words, list) or not all(isinstance(w, str) for w in words):
            raise ApiError(400, "bad_args", "aliases: list expected")
        taken = {w for w, rid in (await trigger_cache.get(ctx.session)).items() if rid != role.id}
        clean: list[str] = []
        for word in (w.strip().lstrip("#/").lower() for w in words):
            if not word or word == role.key or word in clean:
                continue
            if not is_valid_key(word):
                raise ctx.error("bad_key", word=word)
            if word in taken:
                raise ctx.error("key_taken", word=word)
            clean.append(word)
        role.aliases = " ".join(clean)
    await ctx.session.commit()
    trigger_cache.invalidate()
    await sync_group_commands(ctx.bot, ctx.session)
    return {"id": role.id}


@op("roles.delete")
async def op_roles_delete(ctx: Ctx, args: dict):
    role = await _get(ctx, Role, _int(args, "id"), "role_not_found")
    await views.delete_role(ctx.session, role)
    await sync_group_commands(ctx.bot, ctx.session)
    return {}


# ---------- Floors ----------

@op("floors.list")
async def op_floors_list(ctx: Ctx, args: dict):
    s = ctx.session
    groups = (await s.scalars(select(Group).where(Group.is_active))).all()
    staff = dict((await s.execute(
        select(StaffRole.floor_id, func.count(func.distinct(StaffRole.user_id))).group_by(StaffRole.floor_id)
    )).all())
    return [{
        "id": f.id,
        "name": f.name,
        "classes": sorted(g.label for g in groups if g.floor_id == f.id),
        "staff_count": staff.get(f.id, 0),
    } for f in await views.all_floors(s)]


@op("floors.create")
async def op_floors_create(ctx: Ctx, args: dict):
    floor, text = await views.create_floor(ctx.session, ctx.lang, _str(args, "name", 64))
    if floor is None:
        raise ApiError(400, "invalid", _plain(text))
    return {"id": floor.id}


@op("floors.rename")
async def op_floors_rename(ctx: Ctx, args: dict):
    floor = await _get(ctx, Floor, _int(args, "id"), "floor_not_found")
    name = _str(args, "name", 64)
    if not name:
        raise ctx.error("usage_addfloor")
    other = await find_floor(ctx.session, name)
    if other is not None and other.id != floor.id:
        raise ctx.error("floor_exists", name=name)
    floor.name = name
    await ctx.session.commit()
    return {"id": floor.id}


@op("floors.delete")
async def op_floors_delete(ctx: Ctx, args: dict):
    floor = await _get(ctx, Floor, _int(args, "id"), "floor_not_found")
    await views.delete_floor(ctx.session, floor)
    return {}


# ---------- Groups ----------

async def _groups(ctx: Ctx) -> list[dict]:
    groups = (await ctx.session.scalars(select(Group).where(Group.is_active))).all()
    topics = await topics_by_chat(ctx.session)
    return [_group_json(g, topics.get(g.chat_id)) for g in sorted(groups, key=group_sort_key)]


@op("groups.topic_all")
async def op_groups_topic_all(ctx: Ctx, args: dict):
    """Every group that has a topic of this name sends announcements there; the others are listed."""
    name = _str(args, "name", 128)
    topics = await topics_by_chat(ctx.session)
    done, missing = 0, []
    for g in (await ctx.session.scalars(select(Group).where(Group.is_active))).all():
        match = next((tp for tp in topics.get(g.chat_id, []) if same_name(tp.name, name)), None)
        if match is None:
            if topics.get(g.chat_id):
                missing.append(g.label)
            continue
        g.announce_thread_id = match.thread_id
        done += 1
    await ctx.session.commit()
    return {"done": done, "missing": sorted(missing), "groups": await _groups(ctx)}


@op("groups.list")
async def op_groups_list(ctx: Ctx, args: dict):
    return await _groups(ctx)


@op("groups.update")
async def op_groups_update(ctx: Ctx, args: dict):
    group = await _get(ctx, Group, _int(args, "chat_id"))
    if "class_name" in args:
        parsed = parse_class(_str(args, "class_name", 16) or "")
        if parsed is None:
            raise ctx.error("usage_setclass")
        group.grade, group.class_name = parsed
    if "floor_id" in args:
        floor_id = _int(args, "floor_id", optional=True)
        if floor_id is not None:
            await _get(ctx, Floor, floor_id, "floor_not_found")
        group.floor_id = floor_id
    if "lang" in args:
        lang = _str(args, "lang", 2)
        if lang not in LANGS:
            raise ctx.error("usage_grouplang")
        group.lang = lang
    if "announce_thread_id" in args:
        thread_id = _int(args, "announce_thread_id", optional=True)
        if thread_id is not None and await ctx.session.get(ForumTopic, (group.chat_id, thread_id)) is None:
            raise ApiError(400, "bad_args", "announce_thread_id")
        group.announce_thread_id = thread_id
    await ctx.session.commit()
    return _group_json(group, (await topics_by_chat(ctx.session)).get(group.chat_id))


@op("groups.remove")
async def op_groups_remove(ctx: Ctx, args: dict):
    """Takes a group off the bot: the bot leaves it, and it gets no announcements or calls.
    Only the bot leaves; the Telegram group and its messages stay. Its class, floor and
    history are kept, so adding the bot back brings the group back as it was."""
    group = await _get(ctx, Group, _int(args, "chat_id"))
    try:
        await ctx.bot.leave_chat(group.chat_id)
    except TelegramAPIError as e:
        log.info("Leaving %s: %s", group.chat_id, e)  # already out of it: just take it off the list
    group.is_active = False
    await ctx.session.commit()
    return await _groups(ctx)


@op("groups.refresh")
async def op_groups_refresh(ctx: Ctx, args: dict):
    """Re-checks with Telegram whether the bot is still in each group and still an admin."""
    for group in (await ctx.session.scalars(select(Group).where(Group.is_active))).all():
        try:
            member = await ctx.bot.get_chat_member(group.chat_id, ctx.bot.id)
            chat = await ctx.bot.get_chat(group.chat_id)
        except TelegramForbiddenError:
            group.is_active = False
            continue
        except TelegramAPIError as e:
            log.warning("Cannot refresh group %s: %s", group.chat_id, e)
            continue
        group.bot_is_admin = member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR)
        if member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
            group.is_active = False
        if chat.title:
            group.title = chat.title
    await ctx.session.commit()
    return await _groups(ctx)


# ---------- Staff ----------

async def _user_out(ctx: Ctx, user: User) -> dict:
    roles = (await ctx.session.scalars(select(StaffRole).where(StaffRole.user_id == user.id))).all()
    return _user_json(user, list(roles), ctx.user)


@op("staff.list")
async def op_staff_list(ctx: Ctx, args: dict):
    users = (await ctx.session.scalars(select(User).order_by(User.full_name))).all()
    by_user: dict[int, list[StaffRole]] = {}
    for sr in (await ctx.session.scalars(select(StaffRole))).all():
        by_user.setdefault(sr.user_id, []).append(sr)
    return [_user_json(u, by_user.get(u.id, []), ctx.user) for u in users]


@op("staff.set_perm")
async def op_staff_set_perm(ctx: Ctx, args: dict):
    target = await _get(ctx, User, _int(args, "user_id"), "user_not_found")
    perm = _str(args, "perm", 16)
    if perm not in views.PERMS:
        raise ApiError(400, "bad_args", "perm")
    value = _bool(args, "value")
    if perm == "admin" and not value and (target.id == ctx.user.id or target.id in settings.admin_ids):
        raise ctx.error("webapp_cannot_demote")
    setattr(target, views.PERM_COLUMNS[perm].key, value)
    await ctx.session.commit()
    if perm == "admin":
        await set_user_menu(ctx.bot, target)
    return await _user_out(ctx, target)


@op("staff.add_role")
async def op_staff_add_role(ctx: Ctx, args: dict):
    target = await _get(ctx, User, _int(args, "user_id"), "user_not_found")
    role = await _get(ctx, Role, _int(args, "role_id"), "role_not_found")
    floor_id = _int(args, "floor_id", optional=True)
    if floor_id is not None:
        await _get(ctx, Floor, floor_id, "floor_not_found")
    await add_staff_role(ctx.session, target.id, role.id, floor_id)
    await ctx.session.commit()
    return await _user_out(ctx, target)


@op("staff.remove_role")
async def op_staff_remove_role(ctx: Ctx, args: dict):
    target = await _get(ctx, User, _int(args, "user_id"), "user_not_found")
    role_id = _int(args, "role_id")
    floor_id = _int(args, "floor_id", optional=True)
    await ctx.session.execute(delete(StaffRole).where(
        StaffRole.user_id == target.id,
        StaffRole.role_id == role_id,
        StaffRole.floor_id.is_(None) if floor_id is None else StaffRole.floor_id == floor_id,
    ))
    await ctx.session.commit()
    return await _user_out(ctx, target)


async def _for_groups(groups: list[Group], fn, limit: int) -> list:
    """Runs fn(group) for every group, a few at a time (only Telegram calls, no database)."""
    gate = asyncio.Semaphore(limit)

    async def one(group: Group):
        async with gate:
            return await fn(group)

    return await asyncio.gather(*(one(g) for g in groups))


async def _active_groups(ctx: Ctx) -> list[Group]:
    return sorted((await ctx.session.scalars(select(Group).where(Group.is_active))).all(), key=group_sort_key)


# ---------- Group admins ----------
# The person may be anyone in the group: picked from the bot's users, or in Telegram's own
# people picker (admins.pick), so they don't have to have started the bot.

def _user_id(args: dict) -> int:
    user_id = _int(args, "user_id")
    if user_id <= 0:
        raise ApiError(400, "bad_args", "user_id")
    return user_id


@op("admins.pick")
async def op_admins_pick(ctx: Ctx, args: dict):
    """A button for the Mini App's WebApp.requestChat(): it opens Telegram's people picker."""
    request_id = new_request_id()
    many = bool(args.get("many"))
    button = picker_button(_plain(t(ctx.lang, "pick_people" if many else "pick_person")), request_id, many)
    prepared = await ctx.bot.save_prepared_keyboard_button(ctx.user.id, button)
    return {"id": prepared.id, "request_id": request_id}


@op("admins.picked")
async def op_admins_picked(ctx: Ctx, args: dict):
    """The person picked with that button, once Telegram has told the bot (null until then).
    With "many", everyone picked, as a list."""
    if args.get("many"):
        people = await picked_users(ctx.session, ctx.user.id, _int(args, "request_id"))
        return [{"id": p.user_id, "name": p.name, "username": p.username} for p in people] or None
    picked = await picked_user(ctx.session, ctx.user.id, _int(args, "request_id"))
    if picked is None:
        return None
    return {"id": picked.user_id, "name": picked.name, "username": picked.username}


@op("admins.status")
async def op_admins_status(ctx: Ctx, args: dict):
    """Where the person is an admin, a member, or absent, in every class group."""
    user_id = _user_id(args)
    groups = await _active_groups(ctx)
    statuses = await _for_groups(groups, lambda g: group_status(ctx.bot, g.chat_id, user_id), limit=8)
    invites = await pending_invites(ctx.session, user_id)
    return [{
        "chat_id": g.chat_id, "label": g.label, "status": s,
        "invite": invites[g.chat_id].invite_link if s == "absent" and g.chat_id in invites else None,
    } for g, s in zip(groups, statuses)]


@op("admins.invite")
async def op_admins_invite(ctx: Ctx, args: dict):
    """A one-use invite link for someone not in the group yet; they become an admin as they join
    (or join as an ordinary member, with "as_admin": false)."""
    user_id = _user_id(args)
    group = await _get(ctx, Group, _int(args, "chat_id"))
    name = await person_name(ctx.session, user_id)
    if args.get("as_admin") is False:
        link = await member_invite(ctx.bot, group.chat_id, name)
        if link is None:
            raise ctx.error("gadm_invite_failed")
        return {"link": link, "expires_at": None}
    pending = await admin_invite(ctx.bot, ctx.session, group.chat_id, user_id, name, by=ctx.user.id)
    if pending is None:
        raise ctx.error("gadm_invite_failed")
    return {"link": pending.invite_link, "expires_at": _iso(pending.expires_at)}


@op("admins.set")
async def op_admins_set(ctx: Ctx, args: dict):
    """Makes the person an admin (value: true) or not, in exactly the groups given."""
    user_id = _user_id(args)
    make_admin = _bool(args, "value")
    chat_ids = args.get("chat_ids")
    if not isinstance(chat_ids, list) or not chat_ids or not all(isinstance(c, int) for c in chat_ids):
        raise ApiError(400, "bad_args", "chat_ids")
    groups = [g for g in await _active_groups(ctx) if g.chat_id in set(chat_ids)]
    results = await _for_groups(groups, lambda g: set_group_admin(ctx.bot, g.chat_id, user_id, make_admin), limit=5)
    name = html.escape(await person_name(ctx.session, user_id))
    return [{
        "chat_id": g.chat_id, "label": g.label, "result": r,
        "message": None if r == "ok" else html.unescape(_plain(t(ctx.lang, f"gadm_{r}", name=name))),
    } for g, r in zip(groups, results)]


@op("admins.add")
async def op_admins_add(ctx: Ctx, args: dict):
    """Adds the person to the given groups through the connected Telegram account (a few at a
    time: the Mini App calls this repeatedly and shows the progress)."""
    user_id = _user_id(args)
    chat_ids = args.get("chat_ids")
    if not isinstance(chat_ids, list) or not 1 <= len(chat_ids) <= 6 or not all(isinstance(c, int) for c in chat_ids):
        raise ApiError(400, "bad_args", "chat_ids")
    near = [c for c in (args.get("near") or []) if isinstance(c, int)][:3]
    groups = {g.chat_id: g for g in await _active_groups(ctx) if g.chat_id in set(chat_ids)}

    known = await ctx.session.get(User, user_id)
    picked = await ctx.session.scalar(
        select(PickedUser).where(PickedUser.user_id == user_id).order_by(PickedUser.id.desc()).limit(1)
    )
    username = (known.username if known else None) or (picked.username if picked else None)
    name = await person_name(ctx.session, user_id)
    try:
        async with user_account.open_account() as client:
            cached = (await ctx.session.scalars(select(AccountChat.chat_id).where(AccountChat.chat_id.in_(groups)))).all()
            if len(cached) < len(groups):  # a group added since the last check
                await user_account.refresh_chats(client, ctx.session)
            target = await user_account.resolve_user(client, ctx.session, user_id, username, name, near)
            if target is None:
                results = dict.fromkeys(groups, user_account.UNKNOWN_USER)
            else:
                results = await user_account.add_to_chats(client, ctx.session, target, list(groups))
            owner = await client.get_me()
    except user_account.AccountOff as e:
        raise ApiError(409, f"uadd_off:{e}", _plain(t(ctx.lang, "uadd_off")))

    tell_owner = await user_account.record(ctx.session, ctx.user.id, user_id, results)
    if tell_owner and owner.id != ctx.user.id:
        owner_user = await ctx.session.get(User, owner.id)
        with contextlib.suppress(TelegramAPIError):
            await ctx.bot.send_message(owner.id, t(
                owner_user.lang if owner_user else settings.default_lang, "uadd_notice",
                actor=html.escape(ctx.user.full_name), name=html.escape(name),
            ))
    return {
        "stop": user_account.FLOOD in results.values(),
        "results": [{
            "chat_id": c, "label": groups[c].label, "result": r,
            "message": None if r == user_account.OK else html.unescape(_plain(t(ctx.lang, f"uadd_{r}"))),
        } for c, r in results.items()],
    }


@op("people.search")
async def op_people_search(ctx: Ctx, args: dict):
    """Finds people by name or @username in every class group (through the connected account)."""
    query = (_str(args, "q", 64) or "").lstrip("@")
    if len(query) < 2:
        raise ApiError(400, "bad_args", "q: 2 letters at least")
    try:
        async with user_account.open_account() as client:
            people = await user_account.search_people(client, ctx.session, query)
    except user_account.AccountOff as e:
        raise ApiError(409, f"uadd_off:{e}", _plain(t(ctx.lang, "uadd_off")))
    groups = {g.chat_id: g for g in await _active_groups(ctx)}
    order = {g.chat_id: i for i, g in enumerate(groups.values())}
    for person in people:
        person["groups"] = sorted(({**x, "label": groups[x["chat_id"]].label} for x in person["groups"] if x["chat_id"] in groups),
                                  key=lambda x: order[x["chat_id"]])
    return people[:50]


@op("groups.deleted")
async def op_groups_deleted(ctx: Ctx, args: dict):
    """Deleted accounts still listed in each class group (only groups that have some)."""
    groups = await _active_groups(ctx)
    try:
        async with user_account.open_account() as client:
            out = []
            for g in groups:
                ids = await user_account.deleted_members(client, ctx.session, g.chat_id)
                if ids:
                    out.append({"chat_id": g.chat_id, "label": g.label, "user_ids": ids})
    except user_account.AccountOff as e:
        raise ApiError(409, f"uadd_off:{e}", _plain(t(ctx.lang, "uadd_off")))
    return out


@op("groups.deleted_clean")
async def op_groups_deleted_clean(ctx: Ctx, args: dict):
    """Removes the given deleted accounts from one group (the bot does it)."""
    group = await _get(ctx, Group, _int(args, "chat_id"))
    ids = args.get("user_ids")
    if not isinstance(ids, list) or not 1 <= len(ids) <= 25 or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids):
        raise ApiError(400, "bad_args", "user_ids")
    ids = [i for i in ids if i not in settings.admin_ids and i != ctx.bot.id]
    gate = asyncio.Semaphore(5)

    async def one(user_id: int) -> str:
        async with gate:
            return await kick_member(ctx.bot, group.chat_id, user_id)

    results = await asyncio.gather(*(one(i) for i in ids))
    return {"removed": sum(r == "ok" for r in results), "total": len(ids)}


# ---------- Insults in groups ----------

@op("abuse.get")
async def op_abuse_get(ctx: Ctx, args: dict):
    """The insult watch: on/off, the word list, who is told, and the saved messages (newest first)."""
    conf = await watch.abuse_settings(ctx.session)
    admins = (await ctx.session.scalars(select(User).where(User.is_admin).order_by(User.full_name))).all()
    rows = (await ctx.session.scalars(select(FlaggedMessage).order_by(FlaggedMessage.id.desc()).limit(100))).all()
    labels = {g.chat_id: g.label for g in (await ctx.session.scalars(
        select(Group).where(Group.chat_id.in_({r.chat_id for r in rows})))).all()}
    return {
        "on": conf["on"], "words": conf["words"], "default_words": conf["words"] == watch.DEFAULT_WORDS,
        "admins": [{"id": a.id, "name": a.full_name, "on": a.id in conf["to"]} for a in admins],
        "log": [{
            "id": r.id, "chat": labels.get(r.chat_id, str(r.chat_id)), "name": r.user_name, "username": r.username,
            "user_id": r.user_id, "text": r.text, "words": r.words, "edited": r.edited, "at": _iso(r.created_at),
            "link": message_link(r.chat_id, r.message_id),
        } for r in rows],
    }


@op("abuse.save")
async def op_abuse_save(ctx: Ctx, args: dict):
    if "on" in args:
        await watch.set_setting(ctx.session, watch.ABUSE_ON, _bool(args, "on"))
    if "words" in args:
        words = args["words"]
        if words == "default":
            row = await ctx.session.get(watch.Setting, watch.ABUSE_WORDS)
            if row is not None:
                await ctx.session.delete(row)
                await ctx.session.commit()
            watch.forget_settings()
        else:
            if not isinstance(words, list) or len(words) > 500 or not all(isinstance(w, str) for w in words):
                raise ApiError(400, "bad_args", "words")
            clean = list(dict.fromkeys(w.strip()[:64] for w in words if w.strip()))
            await watch.set_setting(ctx.session, watch.ABUSE_WORDS, clean)
    if "to" in args:
        to = args["to"]
        if not isinstance(to, list) or not all(isinstance(i, int) and not isinstance(i, bool) for i in to):
            raise ApiError(400, "bad_args", "to")
        admins = set((await ctx.session.scalars(select(User.id).where(User.is_admin))).all())
        await watch.set_setting(ctx.session, watch.ABUSE_TO, [i for i in to if i in admins])
    return await op_abuse_get(ctx, {})


@op("groups.members")
async def op_groups_members(ctx: Ctx, args: dict):
    """Everyone in the group, listed through the connected account (bots can't list members)."""
    group = await _get(ctx, Group, _int(args, "chat_id"))
    try:
        async with user_account.open_account() as client:
            members = await user_account.list_members(client, ctx.session, group.chat_id)
    except user_account.AccountOff as e:
        raise ApiError(409, f"uadd_off:{e}", _plain(t(ctx.lang, "uadd_off")))
    if members is None:
        raise ctx.error("uadd_not_in")
    return members


@op("admins.kick")
async def op_admins_kick(ctx: Ctx, args: dict):
    """Removes the person from exactly the groups given. Done by the bot itself."""
    user_id = _user_id(args)
    chat_ids = args.get("chat_ids")
    if not isinstance(chat_ids, list) or not chat_ids or not all(isinstance(c, int) for c in chat_ids):
        raise ApiError(400, "bad_args", "chat_ids")
    if user_id in settings.admin_ids or user_id == ctx.bot.id:
        raise ctx.error("gadm_protected")
    groups = [g for g in await _active_groups(ctx) if g.chat_id in set(chat_ids)]
    results = await _for_groups(groups, lambda g: kick_member(ctx.bot, g.chat_id, user_id), limit=5)

    person = await person_name(ctx.session, user_id)
    if person.startswith("ID "):  # picked from a group's member list: the bot may not know them
        person = _str(args, "name", 255, optional=True) or person
    await user_account.record(ctx.session, ctx.user.id, user_id, {g.chat_id: f"kick_{r}"[:16] for g, r in zip(groups, results)})
    removed = [g.label for g, r in zip(groups, results) if r == "ok"]
    if removed:  # every other admin is told: this can't be undone by the bot
        for admin in await admin_users(ctx.session):
            if admin.id != ctx.user.id:
                with contextlib.suppress(TelegramAPIError):
                    await ctx.bot.send_message(admin.id, t(admin.lang, "kick_notice", actor=html.escape(ctx.user.full_name),
                                                           name=html.escape(person), groups=html.escape(", ".join(removed))))
    name = html.escape(person)
    return [{
        "chat_id": g.chat_id, "label": g.label, "result": r,
        "message": None if r == "ok" else html.unescape(_plain(t(ctx.lang, f"gadm_{r}", name=name))),
    } for g, r in zip(groups, results)]


@op("groups.admins")
async def op_groups_admins(ctx: Ctx, args: dict):
    """The group's current admins (people, not bots); "admin" ones the bot appointed and may remove."""
    group = await _get(ctx, Group, _int(args, "chat_id"))
    try:
        members = await ctx.bot.get_chat_administrators(group.chat_id)
    except TelegramAPIError as e:
        log.info("Cannot list admins of %s: %s", group.chat_id, e)
        raise ctx.error("gadm_error", name="")
    order = {"owner": 0, "admin": 1, "admin_other": 2}
    out = [{
        "id": m.user.id, "name": m.user.full_name, "username": m.user.username, "status": member_status(m),
    } for m in members if not m.user.is_bot]
    return sorted(out, key=lambda a: (order.get(a["status"], 3), a["name"].lower()))


# ---------- Invites ----------

@op("invites.list")
async def op_invites_list(ctx: Ctx, args: dict):
    floors = {f.id: f.name for f in await views.all_floors(ctx.session)}
    out = []
    for inv, role in await views.active_invites(ctx.session):
        out.append({
            "code": inv.code,
            "kind": inv.kind,
            "label": role.title if role else _plain(t(ctx.lang, f"perm_{inv.kind}")),
            "floor": floors.get(inv.floor_id),
            "uses_left": inv.uses_left,
            "link": await views.invite_link(ctx.bot, inv.code),
        })
    return out


@op("invites.create")
async def op_invites_create(ctx: Ctx, args: dict):
    kind = _str(args, "kind", 16)
    role = floor = None
    if kind == "role":
        role = await _get(ctx, Role, _int(args, "role_id"), "role_not_found")
        floor_id = _int(args, "floor_id", optional=True)
        floor = await _get(ctx, Floor, floor_id, "floor_not_found") if floor_id is not None else None
    elif kind not in views.PERMS:
        raise ApiError(400, "bad_args", "kind")
    uses = _int(args, "uses")
    if not 1 <= uses <= 1000:
        raise ApiError(400, "bad_args", "uses: 1–1000")
    inv = await views.new_invite(ctx.session, ctx.user.id, kind, role, floor, uses)
    return {"code": inv.code, "link": await views.invite_link(ctx.bot, inv.code)}


@op("invites.revoke")
async def op_invites_revoke(ctx: Ctx, args: dict):
    inv = await _get(ctx, Invite, _str(args, "code", 32), "inv_invalid")
    inv.is_active = False
    await ctx.session.commit()
    return {}


# ---------- Announcements ----------

# Vercel accepts request bodies up to 4.5 MB; base64 adds a third on top of the file.
MAX_UPLOAD = 3 * 1024 * 1024


def _draft_json(d: MediaDraft) -> dict:
    return {
        "id": d.id, "kind": d.kind, "caption": d.caption, "file_name": d.file_name,
        "duration": d.duration, "created_at": _iso(d.created_at), "has_thumb": bool(d.thumb_file_id),
        "album_ok": bool(d.file_id) and d.kind in ALBUM_FAMILY,
    }


async def _own_drafts(ctx: Ctx, ids: list) -> list[MediaDraft]:
    """The admin's own drafts, in the order given."""
    if not all(isinstance(i, int) and not isinstance(i, bool) for i in ids):
        raise ApiError(400, "bad_args", "ids")
    found = {d.id: d for d in (await ctx.session.scalars(
        select(MediaDraft).where(MediaDraft.id.in_(ids), MediaDraft.user_id == ctx.user.id)
    )).all()}
    if len(found) != len(set(ids)):
        raise ctx.error("webapp_not_found", status=404)
    return [found[i] for i in dict.fromkeys(ids)]


@op("media.list")
async def op_media_list(ctx: Ctx, args: dict):
    """Media this admin recently sent to the bot or uploaded, ready to attach to an announcement."""
    since = utcnow() - timedelta(days=3)
    drafts = (await ctx.session.scalars(
        select(MediaDraft).where(MediaDraft.user_id == ctx.user.id, MediaDraft.created_at >= since)
        .order_by(MediaDraft.created_at.desc()).limit(30)
    )).all()
    return [_draft_json(d) for d in drafts]


@op("media.upload")
async def op_media_upload(ctx: Ctx, args: dict):
    """One file from the phone (3 MB max per file). The bot stores it in Telegram via the admin's
    own chat, deletes that message, and keeps the file_id as a draft."""
    name = _str(args, "name", 100) or "file"
    try:
        data = base64.b64decode(_str(args, "data", 6 * 1024 * 1024) or "", validate=True)
    except ValueError:
        raise ApiError(400, "bad_args", "data")
    if not data:
        raise ApiError(400, "bad_args", "data")
    if len(data) > MAX_UPLOAD:
        raise ctx.error("webapp_media_too_big")
    kind = upload_kind(_str(args, "mime", 100, optional=True) or "", name)
    try:
        message, info = await upload_to_owner(ctx.bot, ctx.user.id, kind, data, name)
    except (TelegramAPIError, ValueError) as e:
        log.warning("Upload to Telegram failed: %s", e)
        raise ctx.error("webapp_upload_failed")
    with contextlib.suppress(TelegramAPIError):
        await ctx.bot.delete_message(ctx.user.id, message.message_id)
    draft = MediaDraft(
        user_id=ctx.user.id, chat_id=ctx.user.id, message_id=message.message_id, kind=info.kind,
        file_name=name, duration=info.duration, file_id=info.file_id, thumb_file_id=info.thumb_file_id,
    )
    ctx.session.add(draft)
    await ctx.session.commit()
    return _draft_json(draft)


@op("media.thumbs")
async def op_media_thumbs(ctx: Ctx, args: dict):
    """Small previews of the admin's drafts as data URLs, keyed by draft id."""
    ids = args.get("ids")
    if not isinstance(ids, list) or len(ids) > 30:
        raise ApiError(400, "bad_args", "ids")
    drafts = [d for d in await _own_drafts(ctx, ids) if d.thumb_file_id]

    async def fetch(d: MediaDraft):
        try:
            file = await ctx.bot.get_file(d.thumb_file_id)
            buf = await ctx.bot.download_file(file.file_path)
            return str(d.id), "data:image/jpeg;base64," + base64.b64encode(buf.read()).decode()
        except TelegramAPIError:
            return str(d.id), None

    return {k: v for k, v in await asyncio.gather(*(fetch(d) for d in drafts)) if v}


@op("announce.send")
async def op_announce_send(ctx: Ctx, args: dict):
    # `html` is the editor's formatted text; `text` (plain) is still accepted on its own.
    raw = _str(args, "html", 20000, optional=True)
    if raw is None:
        raw = html.escape(_str(args, "text", 4096, optional=True) or "", quote=False)
    html_text, plain = to_telegram_html(raw)
    if len(plain) > 4096:
        raise ApiError(400, "bad_args", "text: 4096 max")
    media_ids = args.get("media_ids") or []
    if not isinstance(media_ids, list):
        raise ApiError(400, "bad_args", "media_ids")
    drafts = await _own_drafts(ctx, media_ids) if media_ids else []
    # Two languages: `html_ru` goes to the groups whose language is Russian, `html` to the rest.
    raw_ru = _str(args, "html_ru", 20000, optional=True)
    html_ru, plain_ru = to_telegram_html(raw_ru) if raw_ru is not None else (None, "")
    if len(plain_ru) > 4096:
        raise ApiError(400, "bad_args", "html_ru: 4096 max")
    layout = _str(args, "layout", 16, optional=True) or "album"
    if layout not in LAYOUTS:
        raise ApiError(400, "bad_args", "layout")
    if problem := (layout_problem(drafts, layout) or album_problem(drafts)):
        raise ctx.error(problem)
    pin = _bool(args, "pin")
    ids = args.get("chat_ids")
    if not isinstance(ids, list) or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids):
        raise ApiError(400, "bad_args", "chat_ids")
    groups = {g.chat_id: g for g in (await ctx.session.scalars(select(Group).where(Group.is_active))).all()}
    chat_ids = [cid for cid in dict.fromkeys(ids) if cid in groups]
    if not chat_ids:
        raise ctx.error("ann_nothing_selected")
    ru_ids = {cid for cid in chat_ids if groups[cid].lang == "ru"} if html_ru is not None else set()
    if len(ru_ids) < len(chat_ids) and not plain and not drafts:
        raise ctx.error("webapp_text_empty")
    if ru_ids and not plain_ru and not drafts:
        raise ctx.error("ann_need_ru")

    preview = media_preview(drafts, plain or plain_ru)
    send = announcement_sender(ctx.bot, drafts, html_text, plain, layout)
    if ru_ids:
        send_main, send_ru = send, announcement_sender(ctx.bot, drafts, html_ru, plain_ru, layout)

        def send(chat_id: int):
            return (send_ru if chat_id in ru_ids else send_main)(chat_id)
    result = await broadcast(ctx.bot, ctx.session, chat_ids, pin, send=send)
    photo = story_photo(drafts)
    rich = layout in ("slideshow", "collage") and len(drafts) >= 2
    ann = await save_announcement(ctx.session, ctx.user.id, pin, preview, result,
                                  story_file_id=photo, story_caption=story_caption(html_text, plain),
                                  html=html_text if plain else None, layout=layout if rich else None,
                                  html_ru=html_ru if ru_ids and plain_ru else None,
                                  rich_media=json.dumps([[d.kind, d.file_id] for d in drafts]) if rich else None)
    # Optionally also a 24-hour story on the school's account (the photo only; Telegram has no channel stories for bots).
    story = None
    if args.get("story") is True:
        account = await story_account(ctx.session)
        story = "unavailable"
        if account and photo and result.sent:
            try:
                await post_story(ctx.bot, account, photo, ann.story_caption, 24)
                story = "ok"
            except (TelegramAPIError, OSError):
                log.exception("Story for announcement %s failed", ann.id)
                story = "failed"

    def labels(cids: list[int]) -> list[str]:
        return [groups[c].label if c in groups else str(c) for c in cids]

    return {
        "id": ann.id,
        "sent": result.chats_reached,
        "total": len(chat_ids),
        "failed": labels(result.failed),
        "pin_failed": labels(result.pin_failed),
        "story": story,
    }


@op("announce.history")
async def op_announce_history(ctx: Ctx, args: dict):
    s = ctx.session
    anns = (await s.scalars(select(Announcement).order_by(Announcement.created_at.desc()).limit(30))).all()
    counts = dict((await s.execute(
        select(AnnouncementMessage.announcement_id, func.count(func.distinct(AnnouncementMessage.chat_id)))
        .where(AnnouncementMessage.announcement_id.in_([a.id for a in anns]))
        .group_by(AnnouncementMessage.announcement_id)
    )).all())
    authors = {u.id: u for u in (await s.scalars(
        select(User).where(User.id.in_({a.author_id for a in anns}))
    )).all()}
    return [{
        "id": a.id,
        "created_at": _iso(a.created_at),
        "author": authors[a.author_id].full_name if a.author_id in authors else None,
        "preview": a.preview,
        "groups": counts.get(a.id, 0),
        "pinned": a.pinned,
        "deleted": a.deleted,
        # For Telegram's story editor (channels and groups, where the bot can't post stories itself).
        "story_url": story_link(a.id) if a.story_file_id else None,
        "story_text": editor_text(a.story_caption) if a.story_file_id else None,
    } for a in anns]


def _chat_ids(args: dict, key: str = "chat_ids", optional: bool = False) -> list[int] | None:
    ids = args.get(key)
    if ids is None and optional:
        return None
    if not isinstance(ids, list) or not ids or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids):
        raise ApiError(400, "bad_args", key)
    return ids


@op("announce.get")
async def op_announce_get(ctx: Ctx, args: dict):
    """One sent announcement: its text (to edit) and the groups that still have it."""
    ann = await _get(ctx, Announcement, _int(args, "id"))
    chat_ids = (await ctx.session.scalars(select(func.distinct(AnnouncementMessage.chat_id))
                                          .where(AnnouncementMessage.announcement_id == ann.id))).all()
    groups = {g.chat_id: g for g in (await ctx.session.scalars(select(Group).where(Group.chat_id.in_(chat_ids)))).all()}
    msgs = await text_messages(ctx.session, ann)
    kinds = {m.text_kind for m in msgs}
    return {
        "id": ann.id, "html": ann.html or "", "html_ru": ann.html_ru, "deleted": ann.deleted,
        "editable": bool(msgs) and not ann.deleted and ("rich" not in kinds or bool(ann.rich_media)),
        "limit": CAPTION_LIMIT if "caption" in kinds else TEXT_LIMIT,
        "groups": sorted(({"chat_id": c, "label": groups[c].label if c in groups else str(c),
                           "lang": groups[c].lang if c in groups else None} for c in chat_ids),
                         key=lambda g: group_sort_key(groups[g["chat_id"]]) if g["chat_id"] in groups else (99, g["label"])),
    }


@op("announce.edit")
async def op_announce_edit(ctx: Ctx, args: dict):
    """New text for an announcement, changed in every group that has it. For a two-language one,
    `lang` says which text: "ru" for the Russian groups, otherwise the rest."""
    ann = await _get(ctx, Announcement, _int(args, "id"))
    html_text, plain = to_telegram_html(_str(args, "html", 20000) or "")
    msgs = await text_messages(ctx.session, ann)
    lang = "ru" if args.get("lang") == "ru" else "uz"
    if ann.html_ru is not None:
        ru = set((await ctx.session.scalars(select(Group.chat_id).where(
            Group.chat_id.in_({m.chat_id for m in msgs}), Group.lang == "ru"))).all())
        msgs = [m for m in msgs if (m.chat_id in ru) == (lang == "ru")]
    elif lang == "ru":
        raise ApiError(400, "bad_args", "lang")
    if problem := edit_problem(ann, msgs, plain):
        raise ctx.error(problem)
    result = await edit_announcement(ctx.bot, ctx.session, ann, msgs, html_text, new_preview(ann.preview, plain), lang)
    labels = {g.chat_id: g.label for g in (await ctx.session.scalars(select(Group).where(Group.chat_id.in_(result.failed)))).all()}
    return {"edited": len(set(result.edited)), "total": len({m.chat_id for m in msgs}),
            "failed": [labels.get(c, str(c)) for c in dict.fromkeys(result.failed)]}


@op("announce.delete")
async def op_announce_delete(ctx: Ctx, args: dict):
    """Deletes the announcement from the given groups (`chat_ids`), or from every group."""
    ann = await _get(ctx, Announcement, _int(args, "id"))
    if ann.deleted:
        raise ctx.error("ann_already_deleted")
    deleted, total = await delete_announcement(ctx.bot, ctx.session, ann, _chat_ids(args, optional=True))
    return {"deleted": deleted, "total": total, "all_gone": ann.deleted}


# ---------- Calls & stats ----------

@op("calls.list")
async def op_calls_list(ctx: Ctx, args: dict):
    stmt = select(Call).order_by(Call.created_at.desc()).limit(50)
    if args.get("status") == "pending":
        stmt = stmt.where(Call.status == "pending")
    return await _calls_json(ctx.session, list((await ctx.session.scalars(stmt)).all()))


@op("calls.close")
async def op_calls_close(ctx: Ctx, args: dict):
    call_id = _int(args, "id")
    if not await set_status(ctx.session, call_id, expect="pending", status="closed"):
        raise ctx.error("cannot_do")
    call = await ctx.session.get(Call, call_id, populate_existing=True)
    await refresh_call(ctx.bot, ctx.session, call)
    return {}


@op("stats")
async def op_stats(ctx: Ctx, args: dict):
    days = _int(args, "days", optional=True) or 7
    return await views.stats_data(ctx.session, max(1, min(days, 365)))
