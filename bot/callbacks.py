from aiogram.filters.callback_data import CallbackData


class LangCb(CallbackData, prefix="lang"):
    code: str


class FloorPickCb(CallbackData, prefix="fpick"):
    role_id: int
    floor_id: int  # 0 = all floors


class CallCb(CallbackData, prefix="call"):
    action: str  # "acc" | "done" | "close"
    call_id: int


class AnnCb(CallbackData, prefix="ann"):
    action: str  # "all" | "grade" | "grp" | "pin" | "send" | "cancel"
    value: int = 0


class FwdCb(CallbackData, prefix="fwd"):
    """"Send to groups" under a message an announcer sent to the bot."""

    m: int  # that message's id


class StoryCb(CallbackData, prefix="story"):
    ann: int  # announcement id
    h: int = 0  # hours the story stays up; 0 = ask


class StoryAccCb(CallbackData, prefix="storyacc"):
    """An admin's answer to "is this the school's account?"."""

    a: str  # "ok" | "no"
    id: int  # StoryAccount id


class AnnDelCb(CallbackData, prefix="anndel"):
    ann_id: int


class AdmCb(CallbackData, prefix="adm"):
    """Admin panel navigation. `s` is the screen; the rest carry what that screen needs."""

    s: str
    a: str = ""  # kind ("teacher", "role", …) or an invite code
    v: int = 0   # role / floor id
    w: int = 0   # number of uses, or days for stats
    f: int = 0   # floor id for an invite (0 = staff member picks)
