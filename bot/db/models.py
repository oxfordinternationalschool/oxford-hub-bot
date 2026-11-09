from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from bot.config import utcnow


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    full_name: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(64))
    lang: Mapped[str] = mapped_column(String(2), default="uz")
    lang_chosen: Mapped[bool] = mapped_column(default=False)
    is_admin: Mapped[bool] = mapped_column(default=False)
    can_announce: Mapped[bool] = mapped_column(default=False)
    is_teacher: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Floor(Base):
    __tablename__ = "floors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(32), unique=True)
    emoji: Mapped[str] = mapped_column(String(16), default="👤")
    name: Mapped[str] = mapped_column(String(64))
    # Floor-based roles (e.g. cleaners) are routed to staff assigned to the class's floor.
    floor_based: Mapped[bool] = mapped_column(default=False)
    # Extra trigger words, space-separated: "clean tozalash"
    aliases: Mapped[str] = mapped_column(String(255), default="")

    @property
    def title(self) -> str:
        return f"{self.emoji} {self.name}"

    @property
    def triggers(self) -> list[str]:
        return [self.key, *self.aliases.split()]


class Group(Base):
    __tablename__ = "groups"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    title: Mapped[str] = mapped_column(String(255))
    class_name: Mapped[str | None] = mapped_column(String(16))
    grade: Mapped[int | None]
    floor_id: Mapped[int | None] = mapped_column(ForeignKey("floors.id", ondelete="SET NULL"))
    lang: Mapped[str] = mapped_column(String(2), default="uz")
    is_active: Mapped[bool] = mapped_column(default=True)
    bot_is_admin: Mapped[bool] = mapped_column(default=False)
    # In a group with topics: the topic announcements go to (None: General).
    announce_thread_id: Mapped[int | None] = mapped_column(BigInteger)

    @property
    def label(self) -> str:
        return self.class_name or self.title


class StaffRole(Base):
    __tablename__ = "staff_roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))
    # NULL = works on all floors
    floor_id: Mapped[int | None] = mapped_column(ForeignKey("floors.id", ondelete="CASCADE"))


class Invite(Base):
    __tablename__ = "invites"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    # "admin" | "announcer" | "teacher" | "role"
    kind: Mapped[str] = mapped_column(String(16))
    role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))
    floor_id: Mapped[int | None] = mapped_column(ForeignKey("floors.id", ondelete="SET NULL"))
    uses_left: Mapped[int] = mapped_column(default=1)
    created_by: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    is_active: Mapped[bool] = mapped_column(default=True)


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id", ondelete="SET NULL"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    requester_id: Mapped[int] = mapped_column(BigInteger)
    text: Mapped[str] = mapped_column(Text, default="")
    urgent: Mapped[bool] = mapped_column(default=False)
    # "pending" | "accepted" | "done"
    status: Mapped[str] = mapped_column(String(16), default="pending")
    accepted_by: Mapped[int | None] = mapped_column(BigInteger)
    trigger_message_id: Mapped[int]
    group_message_id: Mapped[int | None]
    # Hidden calls: the class never saw the call (an ephemeral command, or the bot deleted the
    # tag message), and its status is shown only to the teacher, as an ephemeral message.
    hidden: Mapped[bool | None] = mapped_column(default=False)
    status_ephemeral_id: Mapped[int | None]
    thread_id: Mapped[int | None] = mapped_column(BigInteger)  # the topic the call was made in
    escalated: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    accepted_at: Mapped[datetime | None]
    done_at: Mapped[datetime | None]


class CallMessage(Base):
    """A call card delivered to someone's private chat, kept so it can be edited later."""

    __tablename__ = "call_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int]


class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(BigInteger)
    pinned: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    deleted: Mapped[bool] = mapped_column(default=False)
    # First characters of the text, for the history list in the admin Mini App.
    preview: Mapped[str | None] = mapped_column(String(200))
    # Its first photo and text (HTML), so it can also be posted as a story later.
    story_file_id: Mapped[str | None] = mapped_column(String(255))
    story_caption: Mapped[str | None] = mapped_column(Text)
    # Its current text (HTML), so it can be edited; for a slideshow/collage also its layout and
    # media ([[kind, file_id], ...] as JSON), since editing a rich message sends it whole again.
    html: Mapped[str | None] = mapped_column(Text)
    layout: Mapped[str | None] = mapped_column(String(16))
    rich_media: Mapped[str | None] = mapped_column(Text)


class StoryAccount(Base):
    """A Telegram account that connected the bot in its settings (Secretary Mode). Once an admin
    approves it as the school's account, announcements can be posted there as stories."""

    __tablename__ = "story_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    connection_id: Mapped[str] = mapped_column(String(128), unique=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(String(255))
    can_post: Mapped[bool] = mapped_column(default=False)  # the account gave the "Manage stories" right
    is_enabled: Mapped[bool] = mapped_column(default=True)
    approved: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)


class ForumTopic(Base):
    """A topic of a group with topics. Telegram doesn't let bots list them, so the bot learns
    each one from messages written in it (or from its creation and renaming)."""

    __tablename__ = "forum_topics"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    thread_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(128))
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)


class AccountChat(Base):
    """A school group as the connected Telegram account can address it (see services/user_account.py)."""

    __tablename__ = "account_chats"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    access_hash: Mapped[int] = mapped_column(BigInteger)
    right: Mapped[str] = mapped_column(String(16))  # "ok": the account may add members


class AccountUser(Base):
    """A person as the connected Telegram account can address them."""

    __tablename__ = "account_users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    access_hash: Mapped[int] = mapped_column(BigInteger)


class AccountAddLog(Base):
    """Who added whom to which group through the connected account."""

    __tablename__ = "account_add_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    result: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class PickedUser(Base):
    """A person an admin picked in Telegram's own people picker, opened from the Mini App.
    Telegram tells the bot in a private message; the Mini App reads it back by the request id.
    The person doesn't have to have started the bot."""

    __tablename__ = "picked_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int] = mapped_column(BigInteger)
    request_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class PendingAdmin(Base):
    """A one-person invite link to a group: whoever it was made for becomes an admin as soon
    as they join through it (the bot sees the join as a chat_member update)."""

    __tablename__ = "pending_admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    invite_link: Mapped[str] = mapped_column(String(255), index=True)
    created_by: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime]
    used: Mapped[bool | None] = mapped_column(default=False)


class FsmState(Base):
    """Conversation state (e.g. an announcement draft). Kept in the DB because on Vercel
    each update may be handled by a different short-lived process."""

    __tablename__ = "fsm_states"

    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    state: Mapped[str | None] = mapped_column(String(128))
    data: Mapped[str] = mapped_column(Text, default="{}")


class PendingDelete(Base):
    """A bot message to remove later; processed by the periodic tick."""

    __tablename__ = "pending_deletes"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int]
    delete_at: Mapped[datetime]


class MediaDraft(Base):
    """A photo/video/voice/file an announcer sent to the bot privately, to attach in the Mini App.

    Kept as (chat_id, message_id) so it can be re-sent with copy_message, which preserves the
    type exactly (a voice note stays a voice note) and has no upload size limit."""

    __tablename__ = "media_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int]
    # "photo" | "video" | "voice" | "audio" | "document" | "video_note" | "animation"
    kind: Mapped[str] = mapped_column(String(16))
    caption: Mapped[str | None] = mapped_column(Text)
    file_name: Mapped[str | None] = mapped_column(String(255))
    duration: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    # Telegram's ids for the file and a small preview; with file_id several drafts can go out as one album.
    file_id: Mapped[str | None] = mapped_column(String(255))
    thumb_file_id: Mapped[str | None] = mapped_column(String(255))
    # Set for an item of an album sent to the bot, so the whole album can be copied to groups.
    media_group_id: Mapped[str | None] = mapped_column(String(64))


class AlbumLead(Base):
    """The first item of an album that reached the bot. Each item of an album is its own update,
    possibly handled in parallel; the primary key lets exactly one of them answer."""

    __tablename__ = "album_leads"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    media_group_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class AnnouncementMessage(Base):
    __tablename__ = "announcement_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    announcement_id: Mapped[int] = mapped_column(
        ForeignKey("announcements.id", ondelete="CASCADE")
    )
    chat_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int]
    # Where its text is, for editing: "text", "caption", "rich", or None (no text, or forwarded).
    text_kind: Mapped[str | None] = mapped_column(String(8))
