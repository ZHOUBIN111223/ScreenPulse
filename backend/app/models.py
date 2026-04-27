"""SQLAlchemy models for research-group users, memberships, screen sessions, reports, analyses, summaries, and audit logs."""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(String(255))
    current_research_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    current_team_id = synonym("current_research_group_id")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    memberships: Mapped[list["ResearchGroupMember"]] = relationship(back_populates="user")
    sessions: Mapped[list["ScreenSession"]] = relationship(back_populates="user")


class ResearchGroup(Base):
    __tablename__ = "research_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator: Mapped[User] = relationship(foreign_keys=[created_by_user_id])
    members: Mapped[list["ResearchGroupMember"]] = relationship(
        back_populates="research_group",
        cascade="all, delete-orphan",
    )
    invite_codes: Mapped[list["InviteCode"]] = relationship(back_populates="research_group", cascade="all, delete-orphan")
    settings: Mapped["ResearchGroupSetting | None"] = relationship(
        back_populates="research_group",
        uselist=False,
        cascade="all, delete-orphan",
        single_parent=True,
    )
    sessions: Mapped[list["ScreenSession"]] = relationship(back_populates="research_group", cascade="all, delete-orphan")
    daily_goals: Mapped[list["DailyGoal"]] = relationship(back_populates="research_group", cascade="all, delete-orphan")
    daily_reports: Mapped[list["DailyReport"]] = relationship(back_populates="research_group", cascade="all, delete-orphan")
    mentor_feedback: Mapped[list["MentorFeedback"]] = relationship(back_populates="research_group", cascade="all, delete-orphan")


class ResearchGroupMember(Base):
    __tablename__ = "research_group_members"
    __table_args__ = (
        UniqueConstraint("research_group_id", "user_id", name="uq_research_group_member"),
        Index("ix_research_group_members_group_status_joined", "research_group_id", "status", "joined_at"),
        Index("ix_research_group_members_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    research_group_id: Mapped[int] = mapped_column(ForeignKey("research_groups.id", ondelete="CASCADE"), index=True)
    team_id = synonym("research_group_id")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    research_group: Mapped[ResearchGroup] = relationship(back_populates="members")
    team = synonym("research_group")
    user: Mapped[User] = relationship(back_populates="memberships")


class InviteCode(Base):
    __tablename__ = "invite_codes"
    __table_args__ = (
        Index("ix_invite_codes_research_group_status_created", "research_group_id", "status", "created_at"),
        Index("ix_invite_codes_status_expires", "status", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    research_group_id: Mapped[int] = mapped_column(ForeignKey("research_groups.id", ondelete="CASCADE"), index=True)
    team_id = synonym("research_group_id")
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    max_uses: Mapped[int | None] = mapped_column(Integer, default=25, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    research_group: Mapped[ResearchGroup] = relationship(back_populates="invite_codes")
    team = synonym("research_group")


class ResearchGroupSetting(Base):
    __tablename__ = "research_group_settings"
    __table_args__ = (UniqueConstraint("research_group_id", name="uq_research_group_setting_group"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    research_group_id: Mapped[int] = mapped_column(ForeignKey("research_groups.id", ondelete="CASCADE"), index=True)
    team_id = synonym("research_group_id")
    frame_interval_seconds: Mapped[int] = mapped_column(Integer, default=300)
    frame_interval_minutes: Mapped[int] = mapped_column(Integer, default=5)
    force_screen_share: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    research_group: Mapped[ResearchGroup] = relationship(back_populates="settings")
    team = synonym("research_group")


class ScreenSession(Base):
    __tablename__ = "screen_sessions"
    __table_args__ = (
        Index("ix_screen_sessions_research_group_user_status", "research_group_id", "user_id", "status"),
        Index("ix_screen_sessions_research_group_status_started", "research_group_id", "status", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    research_group_id: Mapped[int] = mapped_column(ForeignKey("research_groups.id", ondelete="CASCADE"), index=True)
    team_id = synonym("research_group_id")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    source_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    research_group: Mapped[ResearchGroup] = relationship(back_populates="sessions")
    team = synonym("research_group")
    user: Mapped[User] = relationship(back_populates="sessions")
    frames: Mapped[list["FrameCapture"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class FrameCapture(Base):
    __tablename__ = "frame_captures"
    __table_args__ = (
        Index("ix_frame_captures_session_captured", "session_id", "captured_at"),
        Index("ix_frame_captures_research_group_user_captured", "research_group_id", "user_id", "captured_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    research_group_id: Mapped[int] = mapped_column(ForeignKey("research_groups.id", ondelete="CASCADE"), index=True)
    team_id = synonym("research_group_id")
    session_id: Mapped[int] = mapped_column(ForeignKey("screen_sessions.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    image_path: Mapped[str] = mapped_column(String(255))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped[ScreenSession] = relationship(back_populates="frames")
    vision_result: Mapped["VisionResult | None"] = relationship(
        back_populates="frame",
        uselist=False,
        cascade="all, delete-orphan",
        single_parent=True,
    )


class VisionResult(Base):
    __tablename__ = "vision_results"
    __table_args__ = (
        UniqueConstraint("frame_id", name="uq_vision_result_frame"),
        Index("ix_vision_results_research_group_user_created", "research_group_id", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    research_group_id: Mapped[int] = mapped_column(ForeignKey("research_groups.id", ondelete="CASCADE"), index=True)
    team_id = synonym("research_group_id")
    frame_id: Mapped[int] = mapped_column(ForeignKey("frame_captures.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    recognized_content: Mapped[str] = mapped_column(Text)
    activity_description: Mapped[str] = mapped_column(Text)
    model_name: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    frame: Mapped[FrameCapture] = relationship(back_populates="vision_result")


class HourlySummary(Base):
    __tablename__ = "hourly_summaries"
    __table_args__ = (
        UniqueConstraint("research_group_id", "user_id", "hour_start", name="uq_summary_research_group_user_hour"),
        Index("ix_hourly_summaries_research_group_hour", "research_group_id", "hour_start"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    research_group_id: Mapped[int] = mapped_column(ForeignKey("research_groups.id", ondelete="CASCADE"), index=True)
    team_id = synonym("research_group_id")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    hour_start: Mapped[datetime] = mapped_column(DateTime, index=True)
    hour_end: Mapped[datetime] = mapped_column(DateTime)
    summary_text: Mapped[str] = mapped_column(Text)
    frame_count: Mapped[int] = mapped_column(Integer, default=0)
    model_name: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DailyGoal(Base):
    __tablename__ = "daily_goals"
    __table_args__ = (
        UniqueConstraint("research_group_id", "user_id", "goal_date", name="uq_daily_goal_research_group_user_date"),
        Index("ix_daily_goals_research_group_user_date", "research_group_id", "user_id", "goal_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    research_group_id: Mapped[int] = mapped_column(ForeignKey("research_groups.id", ondelete="CASCADE"), index=True)
    team_id = synonym("research_group_id")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    goal_date: Mapped[date] = mapped_column(Date, index=True)
    main_goal: Mapped[str] = mapped_column(Text)
    planned_tasks: Mapped[str] = mapped_column(Text, default="")
    expected_challenges: Mapped[str] = mapped_column(Text, default="")
    needs_mentor_help: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    research_group: Mapped[ResearchGroup] = relationship(back_populates="daily_goals")
    team = synonym("research_group")


class DailyReport(Base):
    __tablename__ = "daily_reports"
    __table_args__ = (
        UniqueConstraint("research_group_id", "user_id", "report_date", name="uq_daily_report_research_group_user_date"),
        Index("ix_daily_reports_research_group_user_date", "research_group_id", "user_id", "report_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    research_group_id: Mapped[int] = mapped_column(ForeignKey("research_groups.id", ondelete="CASCADE"), index=True)
    team_id = synonym("research_group_id")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    completed_work: Mapped[str] = mapped_column(Text)
    problems: Mapped[str] = mapped_column(Text, default="")
    next_plan: Mapped[str] = mapped_column(Text, default="")
    needs_mentor_help: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    research_group: Mapped[ResearchGroup] = relationship(back_populates="daily_reports")
    team = synonym("research_group")


class MentorFeedback(Base):
    __tablename__ = "mentor_feedback"
    __table_args__ = (Index("ix_mentor_feedback_research_group_user_date", "research_group_id", "user_id", "report_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    research_group_id: Mapped[int] = mapped_column(ForeignKey("research_groups.id", ondelete="CASCADE"), index=True)
    team_id = synonym("research_group_id")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    mentor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    content: Mapped[str] = mapped_column(Text)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status_mark: Mapped[str] = mapped_column(String(32), default="normal")
    next_step: Mapped[str] = mapped_column(Text, default="")
    needs_meeting: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    research_group: Mapped[ResearchGroup] = relationship(back_populates="mentor_feedback")
    team = synonym("research_group")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_research_group_created", "research_group_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    research_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_groups.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    team_id = synonym("research_group_id")
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(128))
    target_type: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


Team = ResearchGroup
TeamMember = ResearchGroupMember
TeamSetting = ResearchGroupSetting
