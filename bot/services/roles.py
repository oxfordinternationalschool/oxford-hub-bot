import re
import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Role

# Bot commands that a role key or alias must not shadow.
RESERVED = frozenset({
    "start", "help", "me", "lang", "cancel", "announce", "admin",
    "roles", "addrole", "delrole", "rolefloor", "alias", "unalias",
    "floors", "addfloor", "delfloor",
    "invite", "invites", "revoke", "staff", "assign", "unassign",
    "groups", "stats", "setclass", "setfloor", "grouplang", "groupinfo",
    "teacher", "announcer", "promote", "demote", "settopic",
})

KEY_RE = re.compile(r"^[^\W\d_]\w{1,31}$")
# "#cleaner", "/cleaner", "/cleaner@SchoolBot", "#doctor!" (urgent).
# Must start the text or follow whitespace, so URLs like site.com/path never match.
TRIGGER_RE = re.compile(r"(?<!\S)[#/]([^\W\d_]\w{0,31})(?:@\w+)?(!?)")


def is_valid_key(word: str) -> bool:
    return bool(KEY_RE.match(word)) and word.lower() not in RESERVED


@dataclass
class ParsedCall:
    role_ids: list[int]
    urgent: bool
    text: str


def parse_triggers(text: str, trigger_map: dict[str, int]) -> ParsedCall:
    role_ids: list[int] = []
    urgent = False

    def _strip(m: re.Match) -> str:
        nonlocal urgent
        role_id = trigger_map.get(m.group(1).lower())
        if role_id is None:
            return m.group(0)
        if role_id not in role_ids:
            role_ids.append(role_id)
        urgent = urgent or bool(m.group(2))
        return ""

    cleaned = TRIGGER_RE.sub(_strip, text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    return ParsedCall(role_ids=role_ids, urgent=urgent, text=cleaned)


class TriggerCache:
    """trigger word -> role id. Rebuilt after a role change in this process, and at least
    every TTL seconds so that other processes (several Vercel instances) pick changes up."""

    TTL = 60

    def __init__(self) -> None:
        self._map: dict[str, int] | None = None
        self._loaded_at = 0.0

    def invalidate(self) -> None:
        self._map = None

    async def get(self, session: AsyncSession) -> dict[str, int]:
        if self._map is None or time.monotonic() - self._loaded_at > self.TTL:
            roles = (await session.scalars(select(Role))).all()
            self._map = {trig.lower(): r.id for r in roles for trig in r.triggers}
            self._loaded_at = time.monotonic()
        return self._map


trigger_cache = TriggerCache()
