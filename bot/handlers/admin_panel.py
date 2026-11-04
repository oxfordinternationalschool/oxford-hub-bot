"""Button-based admin panel opened with /admin. Every screen edits the same message."""
import contextlib

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from bot.callbacks import AdmCb
from bot.config import settings
from bot.db.models import Floor, Invite, Role, User
from bot.filters import IsAdmin
from bot.handlers.announce import AnnounceSG, active_groups
from bot.i18n import t
from bot.services import admin_views as views
from bot.services.common import q
from bot.services.menus import sync_group_commands

router = Router(name="admin_panel")
router.message.filter(F.chat.type == ChatType.PRIVATE, IsAdmin())
router.callback_query.filter(IsAdmin())

USES_CHOICES = (1, 5, 30, 100)
STATS_CHOICES = (1, 7, 30)
MAX_TEXT = 3800


class AdminSG(StatesGroup):
    add_role = State()
    add_floor = State()


def _fit(lines: list[str], lang: str) -> str:
    """Panel screens are a single message: cut long lists and point to the full command."""
    text = ""
    for i, line in enumerate(lines):
        if len(text) + len(line) + 1 > MAX_TEXT:
            return text + "\n" + t(lang, "list_cut", n=len(lines) - i)
        text = f"{text}\n{line}" if text else line
    return text


def _builder() -> InlineKeyboardBuilder:
    return InlineKeyboardBuilder()


def _back(kb: InlineKeyboardBuilder, lang: str, to: AdmCb, width: int = 2) -> InlineKeyboardMarkup:
    """Lays the screen's buttons out `width` per row and adds a back button on its own row."""
    kb.adjust(width)
    kb.row(InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=to.pack()))
    return kb.as_markup()


async def _show(cb: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None) -> None:
    with contextlib.suppress(TelegramBadRequest):  # "message is not modified"
        await cb.message.edit_text(text, reply_markup=markup)
    await cb.answer()


def home_keyboard(lang: str) -> InlineKeyboardMarkup:
    kb = _builder()
    if settings.webapp_url:
        kb.row(InlineKeyboardButton(text=t(lang, "btn_mini_app"), web_app=WebAppInfo(url=settings.webapp_url)))
    for screen, key in (
        ("roles", "btn_roles"), ("floors", "btn_floors"),
        ("staff", "btn_staff"), ("groups", "btn_groups"),
        ("announce", "btn_announce"), ("stats", "btn_stats"),
    ):
        kb.button(text=t(lang, key), callback_data=AdmCb(s=screen))
    # The Mini App button (if any) gets a row of its own; sections go two per row.
    kb.adjust(*((1, 2) if settings.webapp_url else (2,)))
    return kb.as_markup()


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext, lang: str):
    await state.clear()
    await message.answer(t(lang, "panel_title"), reply_markup=home_keyboard(lang))


@router.callback_query(AdmCb.filter(F.s == "home"))
async def on_home(cb: CallbackQuery, state: FSMContext, lang: str):
    await state.clear()
    await _show(cb, t(lang, "panel_title"), home_keyboard(lang))


# ---------- Roles ----------

async def _roles_screen(session: AsyncSession, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    kb = _builder()
    for role in await views.all_roles(session):
        kb.button(text=role.title, callback_data=AdmCb(s="role", v=role.id))
    kb.button(text=t(lang, "btn_add_role"), callback_data=AdmCb(s="role_add"))
    return _fit(await views.roles_lines(session, lang), lang), _back(kb, lang, AdmCb(s="home"))


@router.callback_query(AdmCb.filter(F.s == "roles"))
async def on_roles(cb: CallbackQuery, session: AsyncSession, state: FSMContext, lang: str):
    await state.clear()
    await _show(cb, *await _roles_screen(session, lang))


async def _role_screen(session: AsyncSession, lang: str, role: Role) -> tuple[str, InlineKeyboardMarkup]:
    counts = await views.staff_counts(session)
    text = t(
        lang, "role_detail",
        title=q(role.title), triggers=views.triggers_text(role), n=counts.get(role.id, 0),
        mode=t(lang, "role_mode_floor" if role.floor_based else "role_mode_all"),
    )
    kb = _builder()
    kb.button(text=t(lang, "btn_floor_on" if role.floor_based else "btn_floor_off"),
              callback_data=AdmCb(s="role_floor", v=role.id))
    kb.button(text=t(lang, "btn_invite"), callback_data=AdmCb(s="inv_u", a="role", v=role.id))
    kb.button(text=t(lang, "btn_staff_list"), callback_data=AdmCb(s="staff_list", a="role", v=role.id))
    kb.button(text=t(lang, "btn_delete"), callback_data=AdmCb(s="role_del", v=role.id))
    return text, _back(kb, lang, AdmCb(s="roles"))


@router.callback_query(AdmCb.filter(F.s == "role"))
async def on_role(cb: CallbackQuery, callback_data: AdmCb, session: AsyncSession, lang: str):
    role = await session.get(Role, callback_data.v)
    if role is None:
        await _show(cb, *await _roles_screen(session, lang))
        return
    await _show(cb, *await _role_screen(session, lang, role))


@router.callback_query(AdmCb.filter(F.s == "role_floor"))
async def on_role_floor(cb: CallbackQuery, callback_data: AdmCb, session: AsyncSession, lang: str):
    role = await session.get(Role, callback_data.v)
    if role is None:
        await _show(cb, *await _roles_screen(session, lang))
        return
    role.floor_based = not role.floor_based
    await session.commit()
    await _show(cb, *await _role_screen(session, lang, role))


@router.callback_query(AdmCb.filter(F.s == "role_del"))
async def on_role_delete(cb: CallbackQuery, callback_data: AdmCb, session: AsyncSession, lang: str):
    role = await session.get(Role, callback_data.v)
    if role is None:
        await _show(cb, *await _roles_screen(session, lang))
        return
    kb = _builder()
    kb.button(text=t(lang, "btn_confirm_delete"), callback_data=AdmCb(s="role_del_ok", v=role.id))
    await _show(cb, t(lang, "confirm_delete_role", title=q(role.title)), _back(kb, lang, AdmCb(s="role", v=role.id)))


@router.callback_query(AdmCb.filter(F.s == "role_del_ok"))
async def on_role_delete_ok(cb: CallbackQuery, callback_data: AdmCb, session: AsyncSession, lang: str, bot: Bot):
    role = await session.get(Role, callback_data.v)
    if role is not None:
        await views.delete_role(session, role)
        await sync_group_commands(bot, session)
    await _show(cb, *await _roles_screen(session, lang))


@router.callback_query(AdmCb.filter(F.s == "role_add"))
async def on_role_add(cb: CallbackQuery, state: FSMContext, lang: str):
    await state.set_state(AdminSG.add_role)
    await _show(cb, t(lang, "ask_role_input"), _back(_builder(), lang, AdmCb(s="roles")))


@router.message(AdminSG.add_role, F.text)
async def on_role_input(message: Message, state: FSMContext, session: AsyncSession, lang: str, bot: Bot):
    role, text = await views.create_role(session, lang, message.text.split())
    if role is None:
        await message.answer(text + "\n\n" + t(lang, "ask_role_input"))
        return
    await sync_group_commands(bot, session)
    await state.clear()
    kb = _builder()
    kb.button(text=role.title, callback_data=AdmCb(s="role", v=role.id))
    await message.answer(text, reply_markup=_back(kb, lang, AdmCb(s="roles")))


# ---------- Floors ----------

async def _floors_screen(session: AsyncSession, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    kb = _builder()
    for floor in await views.all_floors(session):
        kb.button(text=f"🗑 {floor.name}", callback_data=AdmCb(s="floor_del", v=floor.id))
    kb.button(text=t(lang, "btn_add_floor"), callback_data=AdmCb(s="floor_add"))
    return _fit(await views.floors_lines(session, lang), lang), _back(kb, lang, AdmCb(s="home"))


@router.callback_query(AdmCb.filter(F.s == "floors"))
async def on_floors(cb: CallbackQuery, session: AsyncSession, state: FSMContext, lang: str):
    await state.clear()
    await _show(cb, *await _floors_screen(session, lang))


@router.callback_query(AdmCb.filter(F.s == "floor_del"))
async def on_floor_delete(cb: CallbackQuery, callback_data: AdmCb, session: AsyncSession, lang: str):
    floor = await session.get(Floor, callback_data.v)
    if floor is None:
        await _show(cb, *await _floors_screen(session, lang))
        return
    kb = _builder()
    kb.button(text=t(lang, "btn_confirm_delete"), callback_data=AdmCb(s="floor_del_ok", v=floor.id))
    await _show(cb, t(lang, "confirm_delete_floor", name=q(floor.name)), _back(kb, lang, AdmCb(s="floors")))


@router.callback_query(AdmCb.filter(F.s == "floor_del_ok"))
async def on_floor_delete_ok(cb: CallbackQuery, callback_data: AdmCb, session: AsyncSession, lang: str):
    floor = await session.get(Floor, callback_data.v)
    if floor is not None:
        await views.delete_floor(session, floor)
    await _show(cb, *await _floors_screen(session, lang))


@router.callback_query(AdmCb.filter(F.s == "floor_add"))
async def on_floor_add(cb: CallbackQuery, state: FSMContext, lang: str):
    await state.set_state(AdminSG.add_floor)
    await _show(cb, t(lang, "ask_floor_input"), _back(_builder(), lang, AdmCb(s="floors")))


@router.message(AdminSG.add_floor, F.text)
async def on_floor_input(message: Message, state: FSMContext, session: AsyncSession, lang: str):
    floor, text = await views.create_floor(session, lang, message.text)
    if floor is None:
        await message.answer(text + "\n\n" + t(lang, "ask_floor_input"))
        return
    await state.clear()
    kb = _builder()
    kb.button(text=t(lang, "btn_add_floor"), callback_data=AdmCb(s="floor_add"))
    await message.answer(text, reply_markup=_back(kb, lang, AdmCb(s="floors")))


# ---------- Staff & invites ----------

@router.callback_query(AdmCb.filter(F.s == "staff"))
async def on_staff(cb: CallbackQuery, session: AsyncSession, state: FSMContext, lang: str):
    await state.clear()
    kb = _builder()
    for kind in views.PERMS:
        n = len(await views.staff_users(session, kind))
        kb.button(text=f"{t(lang, f'perm_{kind}')} ({n})", callback_data=AdmCb(s="staff_list", a=kind))
    counts = await views.staff_counts(session)
    for role in await views.all_roles(session):
        kb.button(text=f"{role.title} ({counts.get(role.id, 0)})",
                  callback_data=AdmCb(s="staff_list", a="role", v=role.id))
    kb.button(text=t(lang, "btn_invite"), callback_data=AdmCb(s="inv"))
    kb.button(text=t(lang, "btn_invites"), callback_data=AdmCb(s="invites"))
    await _show(cb, t(lang, "staff_menu"), _back(kb, lang, AdmCb(s="home")))


@router.callback_query(AdmCb.filter(F.s == "staff_list"))
async def on_staff_list(cb: CallbackQuery, callback_data: AdmCb, session: AsyncSession, lang: str):
    role = await session.get(Role, callback_data.v) if callback_data.a == "role" else None
    users = await views.staff_users(session, callback_data.a, role)
    lines = await views.staff_lines(session, lang, users) + ["", t(lang, "staff_remove_hint")]
    await _show(cb, _fit(lines, lang), _back(_builder(), lang, AdmCb(s="staff")))


async def _invites_screen(session: AsyncSession, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    kb = _builder()
    for inv, role in await views.active_invites(session):
        label = role.title if role else t(lang, f"perm_{inv.kind}")
        kb.button(text=f"❌ {label} · {inv.code[:6]}", callback_data=AdmCb(s="inv_rev", a=inv.code))
    return _fit(await views.invites_lines(session, lang), lang), _back(kb, lang, AdmCb(s="staff"))


@router.callback_query(AdmCb.filter(F.s == "invites"))
async def on_invites(cb: CallbackQuery, session: AsyncSession, lang: str):
    await _show(cb, *await _invites_screen(session, lang))


@router.callback_query(AdmCb.filter(F.s == "inv_rev"))
async def on_invite_revoke(cb: CallbackQuery, callback_data: AdmCb, session: AsyncSession, lang: str):
    inv = await session.get(Invite, callback_data.a)
    if inv is not None:
        inv.is_active = False
        await session.commit()
    await _show(cb, *await _invites_screen(session, lang))


@router.callback_query(AdmCb.filter(F.s == "inv"))
async def on_invite_target(cb: CallbackQuery, session: AsyncSession, lang: str):
    kb = _builder()
    for kind in ("teacher", "announcer", "admin"):
        kb.button(text=t(lang, f"perm_{kind}"), callback_data=AdmCb(s="inv_u", a=kind))
    for role in await views.all_roles(session):
        kb.button(text=role.title, callback_data=AdmCb(s="inv_u", a="role", v=role.id))
    await _show(cb, t(lang, "inv_pick_target"), _back(kb, lang, AdmCb(s="staff")))


async def _invite_target(session: AsyncSession, data: AdmCb) -> tuple[str, Role | None] | None:
    if data.a == "role":
        role = await session.get(Role, data.v)
        return ("role", role) if role else None
    return (data.a, None) if data.a in views.PERMS else None


@router.callback_query(AdmCb.filter(F.s == "inv_u"))
async def on_invite_uses(cb: CallbackQuery, callback_data: AdmCb, session: AsyncSession, lang: str):
    target = await _invite_target(session, callback_data)
    if target is None:
        await on_invite_target(cb, session, lang)
        return
    kind, role = target
    pick_floor = role is not None and role.floor_based and await views.all_floors(session)
    kb = _builder()
    for n in USES_CHOICES:
        kb.button(
            text=t(lang, "inv_uses_n", n=n),
            callback_data=AdmCb(s="inv_f" if pick_floor else "inv_go", a=kind, v=callback_data.v, w=n),
        )
    what = views.target_label(lang, kind, role)
    await _show(cb, t(lang, "inv_pick_uses", what=what), _back(kb, lang, AdmCb(s="inv")))


@router.callback_query(AdmCb.filter(F.s == "inv_f"))
async def on_invite_floor(cb: CallbackQuery, callback_data: AdmCb, session: AsyncSession, lang: str):
    target = await _invite_target(session, callback_data)
    if target is None:
        await on_invite_target(cb, session, lang)
        return
    kb = _builder()
    for floor in await views.all_floors(session):
        kb.button(text=floor.name, callback_data=AdmCb(s="inv_go", a="role", v=callback_data.v,
                                                         w=callback_data.w, f=floor.id))
    kb.button(text=t(lang, "inv_floor_any"),
              callback_data=AdmCb(s="inv_go", a="role", v=callback_data.v, w=callback_data.w))
    what = views.target_label(lang, *target)
    await _show(cb, t(lang, "inv_pick_floor", what=what),
                _back(kb, lang, AdmCb(s="inv_u", a="role", v=callback_data.v)))


@router.callback_query(AdmCb.filter(F.s == "inv_go"))
async def on_invite_create(
    cb: CallbackQuery, callback_data: AdmCb, session: AsyncSession, user: User, bot: Bot, lang: str
):
    target = await _invite_target(session, callback_data)
    if target is None or callback_data.w not in USES_CHOICES:
        await on_invite_target(cb, session, lang)
        return
    floor = await session.get(Floor, callback_data.f) if callback_data.f else None
    text = await views.create_invite(session, bot, user.id, lang, *target, floor, callback_data.w)
    kb = _builder()
    kb.button(text=t(lang, "btn_more_invite"), callback_data=AdmCb(s="inv"))
    await _show(cb, text, _back(kb, lang, AdmCb(s="home")))


# ---------- Groups, announcements, stats ----------

@router.callback_query(AdmCb.filter(F.s == "groups"))
async def on_groups(cb: CallbackQuery, session: AsyncSession, state: FSMContext, lang: str):
    await state.clear()
    kb = _builder()
    kb.button(text=t(lang, "btn_refresh"), callback_data=AdmCb(s="groups"))
    await _show(cb, _fit(await views.groups_lines(session, lang), lang), _back(kb, lang, AdmCb(s="home")))


@router.callback_query(AdmCb.filter(F.s == "announce"))
async def on_announce(cb: CallbackQuery, session: AsyncSession, state: FSMContext, lang: str):
    if not await active_groups(session):
        await cb.answer(t(lang, "groups_empty"), show_alert=True)
        return
    await state.clear()
    await state.set_state(AnnounceSG.content)
    await _show(cb, t(lang, "ann_send_content"), None)


@router.callback_query(AdmCb.filter(F.s == "stats"))
async def on_stats(cb: CallbackQuery, callback_data: AdmCb, session: AsyncSession, state: FSMContext, lang: str):
    await state.clear()
    days = callback_data.w if callback_data.w in STATS_CHOICES else 7
    kb = _builder()
    for d in STATS_CHOICES:
        mark = "✅ " if d == days else ""
        kb.button(text=mark + t(lang, "stats_days", n=d), callback_data=AdmCb(s="stats", w=d))
    text = _fit(await views.stats_lines(session, lang, days), lang)
    await _show(cb, text, _back(kb, lang, AdmCb(s="home"), width=3))
