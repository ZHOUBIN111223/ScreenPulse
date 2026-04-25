"""Pydantic schemas for the team-based ScreenPulse HTTP contract."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RegisterRequest(BaseModel):
    email: str = Field(description="User email address used for login.")
    name: str = Field(min_length=1, max_length=128, description="Display name shown to team admins and members.")
    password: str = Field(min_length=6, max_length=128, description="Plain text password used to create the account.")


class LoginRequest(BaseModel):
    email: str = Field(description="User email address used for login.")
    password: str = Field(description="Plain text account password.")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="User ID.")
    email: str = Field(description="User email address.")
    name: str = Field(description="User display name.")


class AuthResponse(BaseModel):
    access_token: str = Field(description="Bearer token for authenticated API calls.")
    token_type: str = Field(default="bearer", description="Token type used in the Authorization header.")
    user: UserOut = Field(description="Authenticated user profile.")


class MessageOut(BaseModel):
    message: str = Field(description="Human-readable result message.")


class TeamCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128, description="Team name.")


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Team ID.")
    name: str = Field(description="Team name.")
    created_by_user_id: int = Field(description="User ID of the team creator.")
    created_at: datetime = Field(description="Team creation time.")
    updated_at: datetime = Field(description="Last team update time.")
    my_role: str = Field(description="Current user's role in the team.")


class InviteCodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Invite code record ID.")
    team_id: int = Field(description="Team ID this invite code belongs to.")
    code: str = Field(description="Invite code value users enter to join the team.")
    created_by_user_id: int = Field(description="User ID of the admin who created the invite code.")
    expires_at: datetime | None = Field(description="Time when the invite code expires, or null if it does not expire.")
    used_count: int = Field(description="Number of successful joins that used this invite code.")
    max_uses: int | None = Field(description="Maximum allowed uses, or null for unlimited uses.")
    status: str = Field(description="Invite code status, such as active.")
    created_at: datetime = Field(description="Invite code creation time.")


class TeamSettingOut(BaseModel):
    frame_interval_seconds: int = Field(description="Screenshot sampling interval in seconds.")
    frame_interval_minutes: int = Field(description="Screenshot sampling interval rounded up to minutes for legacy clients.")


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

    @model_validator(mode="after")
    def normalize_interval(self) -> "TeamSettingUpdate":
        if self.frame_interval_seconds is None and self.frame_interval_minutes is None:
            raise ValueError("frame_interval_seconds is required")
        if self.frame_interval_seconds is None and self.frame_interval_minutes is not None:
            self.frame_interval_seconds = self.frame_interval_minutes * 60
        return self


class SessionStartRequest(BaseModel):
    source_label: str | None = Field(default=None, description="Browser-provided label for the shared screen source.")
    source_type: str | None = Field(default=None, description="Browser-provided source type, such as screen or window.")


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Screen session ID.")
    team_id: int = Field(description="Team ID for this screen session.")
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
    user_id: int = Field(description="Team member user ID.")
    email: str = Field(description="Team member email address.")
    name: str = Field(description="Team member display name.")
    role: str = Field(description="Team role, such as admin or member.")
    status: str = Field(description="Membership status.")
    joined_at: datetime = Field(description="Time when the user joined the team.")
    active_session: SessionOut | None = Field(description="Current active screen session, or null if not sharing.")
    latest_summary: str | None = Field(description="Most recent summary text for this member, or null if none exists.")


class HourlySummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Hourly summary ID.")
    team_id: int = Field(description="Team ID for this summary.")
    user_id: int = Field(description="User ID this summary describes.")
    hour_start: datetime = Field(description="Start of the summarized hour.")
    hour_end: datetime = Field(description="End of the summarized hour.")
    summary_text: str = Field(description="Generated summary text.")
    frame_count: int = Field(description="Number of frames used to generate the summary.")
    model_name: str = Field(description="Model name used to generate the summary.")
    created_at: datetime = Field(description="Summary creation time.")


class LivekitTokenResponse(BaseModel):
    livekit_url: str = Field(description="LiveKit server URL.")
    token: str = Field(description="LiveKit access token for the team room.")
