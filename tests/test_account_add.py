"""Adding people to groups through the connected Telegram account (Telethon is faked)."""
from contextlib import asynccontextmanager
from types import SimpleNamespace as NS

import pytest
from sqlalchemy import select
from telethon import errors
from telethon.tl.functions.channels import GetParticipantsRequest, InviteToChannelRequest
from telethon.tl.functions.contacts import ResolveUsernameRequest

from bot.db.models import AccountAddLog
from bot.services import user_account
from test_media_announce import GROUP_A, GROUP_B, school
from test_webapp_api import ADMIN, TEACHER, api, ok

OWNER, PERSON = 3, 77  # the account belongs to user 3; ADMIN presses the button


def channel_id(chat_id):
    return int(str(chat_id).removeprefix("-100"))


class FakeClient:
    def __init__(self):
        self.invited = []
        self.errors = {}  # channel id -> exception
        self.usernames = {"anvar_q": PERSON}
        self.members = {}  # search word -> user ids
        self.everyone, self.roles = [], []  # the group's member list

    async def iter_dialogs(self):
        for chat_id in (GROUP_A, GROUP_B):
            yield NS(id=chat_id, entity=NS(megagroup=True, access_hash=chat_id * -2, creator=True, admin_rights=None,
                                           banned_rights=None, default_banned_rights=None))

    async def get_me(self):
        return NS(id=OWNER)

    async def __call__(self, request):
        if isinstance(request, ResolveUsernameRequest):
            uid = self.usernames.get(request.username)
            return NS(users=[NS(id=uid, access_hash=555)] if uid else [])
        if isinstance(request, GetParticipantsRequest):
            if request.filter.q == "":
                return NS(users=self.everyone[request.offset:request.offset + request.limit],
                          participants=self.roles[request.offset:request.offset + request.limit], count=len(self.everyone))
            return NS(users=[NS(id=u, access_hash=666) for u in self.members.get(request.filter.q, [])])
        assert isinstance(request, InviteToChannelRequest)
        error = self.errors.get(request.channel.channel_id)
        if error:
            raise error
        self.invited.append((request.channel.channel_id, request.channel.access_hash, request.users[0].user_id, request.users[0].access_hash))
        return NS(missing_invitees=[])


@pytest.fixture
def account(monkeypatch):
    client = FakeClient()

    @asynccontextmanager
    async def open_account():
        yield client

    monkeypatch.setattr(user_account, "open_account", open_account)
    monkeypatch.setattr(user_account, "configured", lambda: True)
    monkeypatch.setattr(user_account, "PAUSE", 0)
    return client


async def pick(wh, username="anvar_q", first="Anvar"):
    button = await ok("admins.pick")
    user = {"user_id": PERSON, "first_name": first}
    if username:
        user["username"] = username
    await wh.private_media(ADMIN, users_shared={"request_id": button["request_id"], "users": [user]})


async def add(*chat_ids, **extra):
    return await ok("admins.add", {"user_id": PERSON, "chat_ids": list(chat_ids), **extra})


async def test_person_is_added_to_every_group_and_the_owner_told_once(wh, account):
    await school(wh)
    await wh.register(OWNER)
    await pick(wh)
    assert (await ok("me"))["account_ready"] is True
    wh.api.requests.clear()

    r = await add(GROUP_A, GROUP_B)
    assert not r["stop"] and [x["result"] for x in r["results"]] == ["ok", "ok"]
    assert account.invited == [(channel_id(GROUP_A), GROUP_A * -2, PERSON, 555), (channel_id(GROUP_B), GROUP_B * -2, PERSON, 555)]
    assert "orqali Anvar" in wh.api.sent(OWNER)[-1].text and "User1" in wh.api.sent(OWNER)[-1].text

    await add(GROUP_A)  # the next batch of the same run
    assert len(wh.api.sent(OWNER)) == 1
    async with wh.sessionmaker() as s:
        assert len((await s.scalars(select(AccountAddLog))).all()) == 3


async def test_person_settings_are_reported_per_group(wh, account):
    await school(wh)
    await pick(wh)
    account.errors[channel_id(GROUP_A)] = errors.UserPrivacyRestrictedError(request=None)
    r = await add(GROUP_A, GROUP_B)
    results = {x["chat_id"]: x for x in r["results"]}
    assert results[GROUP_A]["result"] == "privacy" and "havola" in results[GROUP_A]["message"]
    assert results[GROUP_B]["result"] == "ok"


async def test_telegram_limit_stops_the_run(wh, account):
    await school(wh)
    await pick(wh)
    account.errors[channel_id(GROUP_A)] = errors.PeerFloodError(request=None)
    r = await add(GROUP_A, GROUP_B)
    assert r["stop"] and {x["result"] for x in r["results"]} == {"flood"}
    assert account.invited == []


async def test_person_without_username_is_found_in_a_shared_group(wh, account):
    await school(wh)
    await pick(wh, username=None)
    r = await add(GROUP_B)  # first batch: nowhere to look for them yet
    assert r["results"][0]["result"] == "unknown_user" and account.invited == []

    account.members["Anvar"] = [PERSON]
    r = await add(GROUP_B, near=[GROUP_A])
    assert r["results"][0]["result"] == "ok" and account.invited[0][3] == 666


async def test_not_connected(wh):
    await school(wh)
    assert (await ok("me"))["account_ready"] is False
    status, body = await api("admins.add", {"user_id": PERSON, "chat_ids": [GROUP_A]})
    assert status == 409 and "ulanmagan" in body["message"]


async def test_only_admins_can_add(wh, account):
    await school(wh)
    await wh.register(TEACHER)
    status, _ = await api("admins.add", {"user_id": PERSON, "chat_ids": [GROUP_A]}, uid=TEACHER)
    assert status == 403 and account.invited == []


class ChannelParticipantCreator:
    def __init__(self, user_id):
        self.user_id = user_id


class ChannelParticipant(ChannelParticipantCreator):
    pass


def person(uid, first, username=None, bot=False):
    return NS(id=uid, first_name=first, last_name=None, username=username, bot=bot, deleted=False)


async def test_group_members_are_listed_through_the_account(wh, account):
    await school(wh)
    account.everyone = [person(10, "Zafar", "zafar"), person(11, "Owner"), person(12, "SomeBot", bot=True)]
    account.roles = [ChannelParticipant(10), ChannelParticipantCreator(11), ChannelParticipant(12)]
    members = await ok("groups.members", {"chat_id": GROUP_A})
    assert [(m["id"], m["status"]) for m in members] == [(11, "owner"), (10, "member")]  # no bots, owner first

    [r] = await ok("admins.kick", {"user_id": 10, "chat_ids": [GROUP_A], "name": "Zafar"})
    assert r["result"] == "ok"


async def test_members_need_the_account(wh):
    await school(wh)
    status, body = await api("groups.members", {"chat_id": GROUP_A})
    assert status == 409 and "ulanmagan" in body["message"]
