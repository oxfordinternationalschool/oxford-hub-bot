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


class AnnouncementMessage(Base):
    __tablename__ = "announcement_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    announcement_id: Mapped[int] = mapped_column(
        ForeignKey("announcements.id", ondelete="CASCADE")
    )
    chat_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int]
