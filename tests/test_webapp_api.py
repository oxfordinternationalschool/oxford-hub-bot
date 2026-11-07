"""The admin Mini App API: signed Telegram initData in, JSON out."""
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from aiogram.methods import DeleteMessage, SendMessage
from sqlalchemy import select

from bot.db.models import Call, Role
from bot.webhook import app
from conftest import call_asgi

ADMIN, TEACHER, CLEANER = 1, 3, 5
GROUP = -1001234500


def init_data(user_id: int, token: str = "999:TEST", auth_date: int | None = None) -> str:
    """initData exactly as Telegram builds and signs it."""
    fields = {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "AAHtest",
        "user": json.dumps({"id": user_id, "first_name": f"User{user_id}"}, separators=(",", ":")),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


async def api(op: str, args: dict | None = None, uid: int = ADMIN, raw_init: str | None = None):
    status, body = await call_asgi(
        app,
        {"Authorization": f"tma {raw_init if raw_init is not None else init_data(uid)}"},
        json.dumps({"op": op, "args": args or {}}).encode(),
    )
    return status, json.loads(body)


async def ok(op: str, args: dict | None = None, uid: int = ADMIN):
    status, body = await api(op, args, uid)
    assert status == 200 and body["ok"], body
    return body["data"]


async def test_rejects_forged_expired_and_non_admin(wh):
    await wh.register(ADMIN)
    await wh.register(TEACHER)

    status, body = await api("dashboard", raw_init=init_data(ADMIN, token="111:OTHER"))
    assert status == 401 and body["error"] == "unauthorized"
    status, body = await api("dashboard", raw_init=init_data(ADMIN, auth_date=int(time.time()) - 3 * 86400))
    assert status == 401 and body["error"] == "expired"
    status, body = await api("dashboard", uid=TEACHER)
    assert status == 403 and "admin" in body["message"]
    status, body = await api("dashboard", uid=777)  # never started the bot
    assert status == 403
    status, body = await api("no.such.op")
    assert status == 404


async def test_me_and_dashboard(wh):
    await wh.register(ADMIN)
    assert (await ok("me"))["id"] == ADMIN
    dash = await ok("dashboard")
    assert dash["admins"] == 1 and dash["groups"] == 0 and dash["pending"] == []


async def test_roles_crud(wh):
    await wh.register(ADMIN)
    role_id = (await ok("roles.create", {"key": "cleaner", "emoji": "🧹", "name": "Tozalovchi"}))["id"]
    status, body = await api("roles.create", {"key": "cleaner", "name": "x"})
    assert status == 400 and "band" in body["message"]

    await ok("roles.update", {"id": role_id, "floor_based": True, "aliases": ["clean", "#tozalash", "clean"]})
    [role] = await ok("roles.list")
    assert role["floor_based"] and role["aliases"] == ["clean", "tozalash"] and role["emoji"] == "🧹"

    status, body = await api("roles.update", {"id": role_id, "aliases": ["help"]})
    assert status == 400

    await ok("roles.delete", {"id": role_id})
    assert await ok("roles.list") == []


async def test_floors_and_groups(wh):
    await wh.register(ADMIN)
    floor_id = (await ok("floors.create", {"name": "2-qavat"}))["id"]
    await ok("floors.rename", {"id": floor_id, "name": "Ikkinchi qavat"})
    await wh.bot_added(GROUP, ADMIN, title="Guruh nomi")

    [group] = await ok("groups.list")
    assert group["class_name"] is None
    updated = await ok("groups.update", {"chat_id": GROUP, "class_name": "7b", "floor_id": floor_id, "lang": "ru"})
    assert (updated["class_name"], updated["grade"], updated["floor_id"], updated["lang"]) == ("7-B", 7, floor_id, "ru")
    [floor] = await ok("floors.list")
    assert floor["name"] == "Ikkinchi qavat" and floor["classes"] == ["7-B"]

    status, _ = await api("groups.update", {"chat_id": GROUP, "class_name": "salom"})
    assert status == 400
    await ok("groups.update", {"chat_id": GROUP, "floor_id": None})
    assert (await ok("groups.list"))[0]["floor_id"] is None


async def test_staff_permissions_and_roles(wh):
    await wh.register(ADMIN)
    await wh.register(CLEANER)
    role_id = (await ok("roles.create", {"key": "cleaner", "emoji": "🧹", "name": "Tozalovchi"}))["id"]
    floor_id = (await ok("floors.create", {"name": "2-qavat"}))["id"]

    user = await ok("staff.add_role", {"user_id": CLEANER, "role_id": role_id, "floor_id": floor_id})
    assert user["roles"] == [{"role_id": role_id, "floor_id": floor_id}]
    user = await ok("staff.set_perm", {"user_id": CLEANER, "perm": "teacher", "value": True})
    assert user["is_teacher"]
    user = await ok("staff.remove_role", {"user_id": CLEANER, "role_id": role_id, "floor_id": floor_id})
    assert user["roles"] == []

    status, body = await api("staff.set_perm", {"user_id": ADMIN, "perm": "admin", "value": False})
    assert status == 400 and body["error"] == "webapp_cannot_demote"
    users = await ok("staff.list")
    assert {u["id"] for u in users} == {ADMIN, CLEANER}
    assert next(u for u in users if u["id"] == ADMIN)["is_me"]


async def test_invites(wh):
    await wh.register(ADMIN)
    created = await ok("invites.create", {"kind": "teacher", "uses": 40})
    assert created["link"] == f"https://t.me/school_bot?start={created['code']}"
    [inv] = await ok("invites.list")
    assert inv["uses_left"] == 40 and inv["kind"] == "teacher"
    status, _ = await api("invites.create", {"kind": "teacher", "uses": 5000})
    assert status == 400
    await ok("invites.revoke", {"code": created["code"]})
    assert await ok("invites.list") == []


async def test_announcement_send_history_delete(wh):
    await wh.register(ADMIN)
    await wh.bot_added(GROUP, ADMIN)
    wh.api.requests.clear()

    result = await ok("announce.send", {"text": "Ertaga <b>dars</b> yo'q", "chat_ids": [GROUP, -999], "pin": True})
    assert (result["sent"], result["total"]) == (1, 1)
    msg = wh.api.sent(GROUP)[-1]
    # Plain `text` is shown literally: its "<b>" is escaped, not treated as formatting.
    assert msg.text == "Ertaga &lt;b&gt;dars&lt;/b&gt; yo'q" and msg.parse_mode == "HTML"

    [item] = await ok("announce.history")
    assert item["preview"].startswith("Ertaga") and item["groups"] == 1 and item["pinned"]

    deleted = await ok("announce.delete", {"id": item["id"]})
    assert deleted == {"deleted": 1, "total": 1, "all_gone": True}
    assert any(isinstance(r, DeleteMessage) and r.chat_id == GROUP for r in wh.api.requests)

    status, _ = await api("announce.send", {"text": "  ", "chat_ids": [GROUP], "pin": False})
    assert status == 400


async def test_calls_list_close_and_stats(wh):
    await wh.register(ADMIN)
    await ok("roles.create", {"key": "doctor", "emoji": "🩺", "name": "Shifokor"})
    await wh.bot_added(GROUP, ADMIN)
    await wh.group(GROUP, ADMIN, "#doctor! bola yiqildi")

    [call] = await ok("calls.list", {"status": "pending"})
    assert call["urgent"] and call["text"] == "bola yiqildi" and call["class"] == "7-B"
    assert (await ok("dashboard"))["pending"][0]["id"] == call["id"]

    await ok("calls.close", {"id": call["id"]})
    async with wh.sessionmaker() as s:
        assert (await s.get(Call, call["id"])).status == "closed"
    status, _ = await api("calls.close", {"id": call["id"]})
    assert status == 400

    stats = await ok("stats", {"days": 30})
    assert stats["total"] == 1 and stats["per_role"][0]["title"] == "🩺 Shifokor"


async def test_admin_panel_shows_mini_app_button_when_configured(h, monkeypatch):
    import dataclasses

    import bot.handlers.admin_panel as panel

    monkeypatch.setattr(panel, "settings", dataclasses.replace(panel.settings, webapp_url="https://x.example/admin/"))
    await h.register(ADMIN)
    await h.private(ADMIN, "/admin")
    first = h.api.sent(ADMIN)[-1].reply_markup.inline_keyboard[0][0]
    assert first.web_app is not None and first.web_app.url == "https://x.example/admin/"
