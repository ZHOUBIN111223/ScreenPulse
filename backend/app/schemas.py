"""Pydantic schemas for the research-group ScreenPulse HTTP contract."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RegisterRequest(BaseModel):
    email: str = Field(description="User email address used for login.")
    name: str = Field(min_length=1, max_length=128, description="Display name shown to mentors and students.")
    password: str = Field(min_length=6, max_length=128, description="Plain text password used to create the account.")


class LoginRequest(BaseModel):
    email: str = Field(description="User email address used for login.")
    password: str = Field(description="Plain text account password.")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="User ID.")
    email: str = Field(description="User email address.")
    name: str = Field(description="User display name.")
    current_research_group_id: int | None = Field(default=None, description="Current research group ID selected by the user.")
    current_team_id: int | None = Field(default=None, description="Legacy current team ID selected by the user.")
    is_admin: bool = Field(default=False, description="Whether the user is a global administrator.")


class AuthResponse(BaseModel):
    access_token: str = Field(description="Bearer token for authenticated API calls.")
    token_type: str = Field(default="bearer", description="Token type used in the Authorization header.")
    user: UserOut = Field(description="Authenticated user profile.")


class MessageOut(BaseModel):
    message: str = Field(description="Human-readable result message.")


class ResearchGroupCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128, description="Research group name.")


class ResearchGroupJoinRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64, description="Invite code used to join a research group.")


class CurrentResearchGroupUpdate(BaseModel):
    research_group_id: int | None = Field(default=None, description="Research group ID to make current for the authenticated user.")
    team_id: int | None = Field(default=None, description="Legacy team ID to make current for the authenticated user.")

    @model_validator(mode="after")
    def normalize_group_id(self) -> "CurrentResearchGroupUpdate":
        if self.research_group_id is None and self.team_id is None:
            raise ValueError("research_group_id is required")
        if self.research_group_id is None:
            self.research_group_id = self.team_id
        if self.team_id is None:
            self.team_id = self.research_group_id
        return self


class ResearchGroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Research group ID.")
    name: str = Field(description="Research group name.")
    created_by_user_id: int = Field(description="User ID of the research group creator.")
    created_at: datetime = Field(description="Research group creation time.")
    updated_at: datetime = Field(description="Last research group update time.")
    my_role: str = Field(description="Current user's role in the research group, such as mentor or student.")


class InviteCodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Invite code record ID.")
    research_group_id: int = Field(description="Research group ID this invite code belongs to.")
    team_id: int | None = Field(default=None, description="Legacy team ID this invite code belongs to.")
    code: str = Field(description="Invite code value users enter to join the team.")
    created_by_user_id: int = Field(description="User ID of the admin who created the invite code.")
    expires_at: datetime | None = Field(description="Time when the invite code expires, or null if it does not expire.")
    used_count: int = Field(description="Number of successful joins that used this invite code.")
    max_uses: int | None = Field(description="Maximum allowed uses, or null for unlimited uses.")
    status: str = Field(description="Invite code status, such as active.")
    created_at: datetime = Field(description="Invite code creation time.")


class InviteCodeCreateRequest(BaseModel):
    expires_in_hours: int | None = Field(
        default=168,
        ge=1,
        le=8760,
        description="Invite code lifetime in hours, or null for no expiry.",
    )
    max_uses: int | None = Field(
        default=None,
        ge=1,
        le=10000,
        description="Maximum allowed uses, or null to use the server default.",
    )


class InviteCodeStatusUpdate(BaseModel):
    status: str = Field(pattern="^(active|disabled)$", description="New invite code status.")


class TeamSettingOut(BaseModel):
    frame_interval_seconds: int = Field(description="Screenshot sampling interval in seconds.")
    frame_interval_minutes: int = Field(description="Screenshot sampling interval rounded up to minutes for legacy clients.")
    force_screen_share: bool = Field(description="Whether members are required to keep screen sharing enabled.")


class TeamSettingUpdate(BaseModel):
    frame_interval_seconds: int | None = Field(
        default=None,
        ge=1,
        le=86400,
        description="New screenshot sampling interval in seconds.",
    )
    frame_interval_minutes: int | None = Field(
        default=None,
        ge=1,
        le=1440,
        description="Legacy screenshot sampling interval in minutes.",
    )
    force_screen_share: bool | None = Field(
        default=None,
        description="Whether members are required to keep screen sharing enabled.",
    )

    @model_validator(mode="after")
    def normalize_interval(self) -> "TeamSettingUpdate":
        if self.frame_interval_seconds is None and self.frame_interval_minutes is None and self.force_screen_share is None:
            raise ValueError("at least one setting is required")
        if self.frame_interval_seconds is None and self.frame_interval_minutes is not None:
            self.frame_interval_seconds = self.frame_interval_minutes * 60
        return self


class CaptureIntervalUpdate(BaseModel):
    frame_interval_seconds: int = Field(
        ge=1,
        le=86400,
        description="New screenshot sampling interval in seconds.",
    )


class SessionStartRequest(BaseModel):
    source_label: str | None = Field(default=None, description="Browser-provided label for the shared screen source.")
    source_type: str | None = Field(default=None, description="Browser-provided source type, such as screen or window.")


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Screen session ID.")
    research_group_id: int = Field(description="Research group ID for this screen session.")
    team_id: int | None = Field(default=None, description="Legacy team ID for this screen session.")
    user_id: int = Field(description="User ID that owns this screen session.")
    status: str = Field(description="Session status, such as active or stopped.")
    started_at: datetime = Field(description="Session start time.")
    ended_at: datetime | None = Field(description="Session end time, or null while active.")
    source_label: str | None = Field(description="Browser-provided label for the shared screen source.")
    source_type: str | None = Field(description="Browser-provided source type, such as screen or window.")
    frame_count: int | None = Field(default=None, description="Number of uploaded frames in this session.")


class FrameUploadResult(BaseModel):
    frame_id: int = Field(description="Stored frame capture ID.")
    recognized_content: str = Field(description="Text or content recognized from the screenshot.")
    activity_description: str = Field(description="Short activity description inferred from the screenshot.")
    summary_text: str = Field(description="Current hourly summary after this frame was processed.")
    frame_interval_seconds: int = Field(description="Current team screenshot sampling interval in seconds.")
    frame_interval_minutes: int = Field(description="Current team screenshot sampling interval rounded up to minutes.")


class TeamMemberOut(BaseModel):
    user_id: int = Field(description="Research group member user ID.")
    email: str = Field(description="Research group member email address.")
    name: str = Field(description="Research group member display name.")
    role: str = Field(description="Research group role, such as mentor or student.")
    status: str = Field(description="Membership status.")
    joined_at: datetime = Field(description="Time when the user joined the team.")
    active_session: SessionOut | None = Field(description="Current active screen session, or null if not sharing.")
    latest_summary: str | None = Field(description="Most recent summary text for this member, or null if none exists.")


class TeamMemberAddRequest(BaseModel):
    email: str = Field(description="Email address of an existing ScreenPulse user to add to the team.")
    role: str = Field(default="student", pattern="^(mentor|student|admin|member)$", description="Role to assign to the new member.")


class TeamMemberUpdate(BaseModel):
    role: str = Field(pattern="^(mentor|student|admin|member)$", description="New role for the active research group member.")


class AdminUserOut(UserOut):
    pass


class AdminFrameOut(BaseModel):
    frame_id: int = Field(description="Stored screenshot frame ID.")
    research_group_id: int = Field(description="Research group ID for this frame.")
    team_id: int | None = Field(default=None, description="Legacy team ID for this frame.")
    session_id: int = Field(description="Screen session ID that produced this frame.")
    user_id: int = Field(description="User ID that uploaded this frame.")
    user_name: str = Field(description="Display name of the user who uploaded this frame.")
    user_email: str = Field(description="Email of the user who uploaded this frame.")
    captured_at: datetime = Field(description="Browser capture timestamp.")
    width: int = Field(description="Screenshot width in pixels.")
    height: int = Field(description="Screenshot height in pixels.")
    created_at: datetime = Field(description="Server storage timestamp.")
    recognized_content: str | None = Field(description="Recognized screenshot content, or null if unavailable.")
    activity_description: str | None = Field(description="Detected activity description, or null if unavailable.")
    model_name: str | None = Field(description="Vision model name, or null if unavailable.")


class HourlySummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Hourly summary ID.")
    research_group_id: int = Field(description="Research group ID for this summary.")
    team_id: int | None = Field(default=None, description="Legacy team ID for this summary.")
    user_id: int = Field(description="User ID this summary describes.")
    hour_start: datetime = Field(description="Start of the summarized hour.")
    hour_end: datetime = Field(description="End of the summarized hour.")
    summary_text: str = Field(description="Generated summary text.")
    frame_count: int = Field(description="Number of frames used to generate the summary.")
    model_name: str = Field(description="Model name used to generate the summary.")
    created_at: datetime = Field(description="Summary creation time.")


class DailyGoalUpsert(BaseModel):
    goal_date: date = Field(description="Date this goal belongs to.")
    main_goal: str = Field(min_length=1, max_length=4000, description="Main study or research goal for the day.")
    planned_tasks: str = Field(default="", max_length=4000, description="Planned tasks for the day.")
    expected_challenges: str = Field(default="", max_length=4000, description="Expected blockers or difficulties.")
    needs_mentor_help: bool = Field(default=False, description="Whether the student needs mentor help today.")


class DailyGoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Daily goal ID.")
    research_group_id: int = Field(description="Research group ID this daily goal belongs to.")
    team_id: int | None = Field(default=None, description="Legacy team ID this daily goal belongs to.")
    user_id: int = Field(description="Student user ID.")
    goal_date: date = Field(description="Date this goal belongs to.")
    main_goal: str = Field(description="Main study or research goal for the day.")
    planned_tasks: str = Field(description="Planned tasks for the day.")
    expected_challenges: str = Field(description="Expected blockers or difficulties.")
    needs_mentor_help: bool = Field(description="Whether the student needs mentor help today.")
    created_at: datetime = Field(description="Goal creation time.")
    updated_at: datetime = Field(description="Goal update time.")


class DailyReportUpsert(BaseModel):
    report_date: date = Field(description="Date this daily report belongs to.")
    completed_work: str = Field(min_length=1, max_length=8000, description="What the student completed today.")
    problems: str = Field(default="", max_length=8000, description="Problems or blockers encountered today.")
    next_plan: str = Field(default="", max_length=8000, description="What the student plans to do tomorrow.")
    needs_mentor_help: bool = Field(default=False, description="Whether the student needs mentor help.")
    notes: str = Field(default="", max_length=8000, description="Additional notes.")


class DailyReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Daily report ID.")
    research_group_id: int = Field(description="Research group ID this report belongs to.")
    team_id: int | None = Field(default=None, description="Legacy team ID this report belongs to.")
    user_id: int = Field(description="Student user ID.")
    report_date: date = Field(description="Date this daily report belongs to.")
    completed_work: str = Field(description="What the student completed today.")
    problems: str = Field(description="Problems or blockers encountered today.")
    next_plan: str = Field(description="What the student plans to do tomorrow.")
    needs_mentor_help: bool = Field(description="Whether the student needs mentor help.")
    notes: str = Field(description="Additional notes.")
    created_at: datetime = Field(description="Report creation time.")
    updated_at: datetime = Field(description="Report update time.")


class MentorFeedbackCreate(BaseModel):
    report_date: date = Field(description="Date of the student report being reviewed.")
    content: str = Field(min_length=1, max_length=8000, description="Mentor feedback content.")
    score: int | None = Field(default=None, ge=0, le=100, description="Optional score from 0 to 100.")
    status_mark: str = Field(
        default="normal",
        pattern="^(normal|needs_attention|needs_revision|needs_meeting|resolved)$",
        description="Mentor status mark for this report.",
    )
    next_step: str = Field(default="", max_length=8000, description="Suggested next step.")
    needs_meeting: bool = Field(default=False, description="Whether a follow-up meeting is needed.")


class MentorFeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Mentor feedback ID.")
    research_group_id: int = Field(description="Research group ID this feedback belongs to.")
    team_id: int | None = Field(default=None, description="Legacy team ID this feedback belongs to.")
    user_id: int = Field(description="Student user ID.")
    mentor_user_id: int = Field(description="Mentor user ID.")
    report_date: date = Field(description="Date of the student report being reviewed.")
    content: str = Field(description="Mentor feedback content.")
    score: int | None = Field(description="Optional score from 0 to 100.")
    status_mark: str = Field(description="Mentor status mark for this report.")
    next_step: str = Field(description="Suggested next step.")
    needs_meeting: bool = Field(description="Whether a follow-up meeting is needed.")
    created_at: datetime = Field(description="Feedback creation time.")


class DailyReportDetailOut(BaseModel):
    student: TeamMemberOut = Field(description="Student membership and status.")
    goal: DailyGoalOut | None = Field(description="Daily goal for this date, or null.")
    report: DailyReportOut | None = Field(description="Student daily report for this date, or null.")
    hourly_summaries: list[HourlySummaryOut] = Field(description="Hourly summaries generated on this date.")
    feedback: list[MentorFeedbackOut] = Field(description="Mentor feedback for this date.")


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Audit log ID.")
    research_group_id: int | None = Field(description="Research group ID for the audit event, or null for global events.")
    team_id: int | None = Field(default=None, description="Legacy team ID for the audit event, or null for global events.")
    actor_user_id: int | None = Field(description="User ID that performed the action, or null for system events.")
    actor_name: str | None = Field(description="Display name of the actor, or null if unavailable.")
    actor_email: str | None = Field(description="Email of the actor, or null if unavailable.")
    action: str = Field(description="Stable audit action name.")
    target_type: str = Field(description="Type of resource affected by the action.")
    target_id: int | None = Field(description="ID of the affected resource, or null if unavailable.")
    created_at: datetime = Field(description="Audit event creation time.")


class LivekitTokenResponse(BaseModel):
    livekit_url: str = Field(description="LiveKit server URL.")
    token: str = Field(description="LiveKit access token for the team room.")


TeamCreateRequest = ResearchGroupCreateRequest
TeamJoinRequest = ResearchGroupJoinRequest
CurrentTeamUpdate = CurrentResearchGroupUpdate
TeamOut = ResearchGroupOut
