// Frontend API contract types and request helpers for the team-based ScreenPulse backend.
export type TeamRole = "admin" | "member";

export type User = {
  id: number;
  email: string;
  name: string;
  current_team_id: number | null;
  is_admin: boolean;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export type Team = {
  id: number;
  name: string;
  created_by_user_id: number;
  created_at: string;
  updated_at: string;
  my_role: TeamRole;
};

export type TeamSetting = {
  frame_interval_seconds: number;
  frame_interval_minutes: number;
  force_screen_share: boolean;
};

export type Session = {
  id: number;
  team_id: number;
  user_id: number;
  status: "active" | "stopped";
  started_at: string;
  ended_at: string | null;
  source_label: string | null;
  source_type: string | null;
  frame_count?: number;
};

export type FrameUploadResult = {
  frame_id: number;
  recognized_content: string;
  activity_description: string;
  summary_text: string;
  frame_interval_seconds: number;
  frame_interval_minutes: number;
};

export type TeamMember = {
  user_id: number;
  email: string;
  name: string;
  role: TeamRole;
  status: string;
  joined_at: string;
  active_session: Session | null;
  latest_summary: string | null;
};

export type InviteCode = {
  id: number;
  team_id: number;
  code: string;
  created_by_user_id: number;
  expires_at: string | null;
  used_count: number;
  max_uses: number | null;
  status: string;
  created_at: string;
};

export type InviteCodeCreateInput = {
  expires_in_hours: number | null;
  max_uses: number | null;
};

export type HourlySummary = {
  id: number;
  team_id: number;
  user_id: number;
  hour_start: string;
  hour_end: string;
  summary_text: string;
  frame_count: number;
  model_name: string;
  created_at: string;
};

export type AuditLog = {
  id: number;
  team_id: number | null;
  actor_user_id: number | null;
  actor_name: string | null;
  actor_email: string | null;
  action: string;
  target_type: string;
  target_id: number | null;
  created_at: string;
};

export type AdminFrame = {
  frame_id: number;
  team_id: number;
  session_id: number;
  user_id: number;
  user_name: string;
  user_email: string;
  captured_at: string;
  width: number;
  height: number;
  created_at: string;
  recognized_content: string | null;
  activity_description: string | null;
  model_name: string | null;
};

export type AdminUser = User;

type MessageOut = {
  message: string;
};

export class ApiError extends Error {
  requestId: string | null;
  status: number;

  constructor(message: string, status: number, requestId: string | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.requestId = requestId;
  }
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8011/api";

const TOKEN_KEY = "screenpulse-token";

export function getToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(TOKEN_KEY, token);
  }
}

export function clearToken() {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(TOKEN_KEY);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const headers = new Headers(init?.headers);

  if (!headers.has("Content-Type") && !(init?.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: "请求失败" }));
    const requestId = response.headers.get("X-Request-ID");
    const detail = data.detail ?? "请求失败";
    const message = requestId ? `${detail} (request id: ${requestId})` : detail;
    throw new ApiError(message, response.status, requestId);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export function register(email: string, name: string, password: string) {
  return request<AuthResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, name, password })
  });
}

export function login(email: string, password: string) {
  return request<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password })
  });
}

export function logout() {
  return request<MessageOut>("/auth/logout", { method: "POST" });
}

export function fetchMe() {
  return request<User>("/auth/me");
}

export function fetchTeams() {
  return request<Team[]>("/teams");
}

export function fetchAdminTeams() {
  return request<Team[]>("/admin/teams");
}

export function createTeam(name: string) {
  return request<Team>("/teams", {
    method: "POST",
    body: JSON.stringify({ name })
  });
}

export function fetchTeam(teamId: number) {
  return setCurrentTeam(teamId);
}

export function fetchCurrentTeam() {
  return request<Team>("/teams/current");
}

export function setCurrentTeam(teamId: number) {
  return request<Team>("/teams/current", {
    method: "PUT",
    body: JSON.stringify({ team_id: teamId })
  });
}

export function fetchAdminUsers() {
  return request<AdminUser[]>("/admin/users");
}

export function fetchAdminSessions(filters?: { team_id?: number; user_id?: number; status?: string }) {
  const params = new URLSearchParams();
  if (filters?.team_id !== undefined) {
    params.set("team_id", String(filters.team_id));
  }
  if (filters?.user_id !== undefined) {
    params.set("user_id", String(filters.user_id));
  }
  if (filters?.status) {
    params.set("status", filters.status);
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return request<Session[]>(`/admin/sessions${suffix}`);
}

export async function fetchTeamMembers(teamId: number) {
  await setCurrentTeam(teamId);
  return request<TeamMember[]>("/admin/members");
}

export async function addTeamMember(teamId: number, email: string, role: TeamRole) {
  await setCurrentTeam(teamId);
  return request<TeamMember>("/admin/members", {
    method: "POST",
    body: JSON.stringify({ email, role })
  });
}

export async function updateTeamMemberRole(teamId: number, userId: number, role: TeamRole) {
  await setCurrentTeam(teamId);
  return request<TeamMember>(`/admin/members/${userId}`, {
    method: "PATCH",
    body: JSON.stringify({ role })
  });
}

export async function removeTeamMember(teamId: number, userId: number) {
  await setCurrentTeam(teamId);
  return request<void>(`/admin/members/${userId}`, {
    method: "DELETE"
  });
}

export async function createInviteCode(teamId: number, input?: InviteCodeCreateInput) {
  await setCurrentTeam(teamId);
  return request<InviteCode>("/admin/invite-codes", {
    method: "POST",
    body: JSON.stringify(input ?? {})
  });
}

export async function fetchInviteCodes(teamId: number) {
  await setCurrentTeam(teamId);
  return request<InviteCode[]>("/admin/invite-codes");
}

export async function updateInviteCodeStatus(teamId: number, inviteCodeId: number, status: "active" | "disabled") {
  await setCurrentTeam(teamId);
  return request<InviteCode>(`/admin/invite-codes/${inviteCodeId}`, {
    method: "PATCH",
    body: JSON.stringify({ status })
  });
}

export function joinTeamByCode(code: string) {
  return request<Team>("/teams/join", {
    method: "POST",
    body: JSON.stringify({ code })
  });
}

export async function fetchTeamSettings(teamId: number) {
  await setCurrentTeam(teamId);
  return request<TeamSetting>("/settings/current");
}

export async function updateTeamSettings(teamId: number, frame_interval_seconds: number, force_screen_share: boolean) {
  await setCurrentTeam(teamId);
  return request<TeamSetting>("/admin/settings", {
    method: "PUT",
    body: JSON.stringify({ frame_interval_seconds, force_screen_share })
  });
}

export async function fetchCurrentSession(teamId: number) {
  await setCurrentTeam(teamId);
  return request<Session | null>("/sessions/current");
}

export async function startSession(teamId: number, source_label: string | null, source_type: string | null) {
  await setCurrentTeam(teamId);
  return request<Session>("/sessions/start", {
    method: "POST",
    body: JSON.stringify({ source_label, source_type })
  });
}

export async function stopSession(teamId: number, sessionId: number) {
  await setCurrentTeam(teamId);
  void sessionId;
  return request<Session>("/sessions/stop", {
    method: "POST"
  });
}

export async function uploadFrame(
  teamId: number,
  sessionId: number,
  file: Blob,
  capturedAt: string
) {
  await setCurrentTeam(teamId);
  void sessionId;
  const formData = new FormData();
  formData.append("file", file, "frame.png");
  formData.append("captured_at", capturedAt);

  return request<FrameUploadResult>("/screenshots/upload", {
    method: "POST",
    body: formData
  });
}

export async function fetchMySummaries(teamId: number) {
  await setCurrentTeam(teamId);
  return request<HourlySummary[]>("/summaries/my-team");
}

export async function fetchTeamSummaries(teamId: number) {
  await setCurrentTeam(teamId);
  return request<HourlySummary[]>(`/admin/summaries?team_id=${teamId}`);
}

export async function fetchMemberSummaries(teamId: number, userId: number) {
  await setCurrentTeam(teamId);
  return request<HourlySummary[]>(`/admin/members/${userId}/summaries`);
}

export async function deleteHourlySummary(teamId: number, summaryId: number) {
  await setCurrentTeam(teamId);
  return request<void>(`/admin/summaries/${summaryId}`, {
    method: "DELETE"
  });
}

export async function fetchAdminFrames(teamId: number) {
  await setCurrentTeam(teamId);
  return request<AdminFrame[]>("/admin/frames");
}

export async function deleteAdminFrame(teamId: number, frameId: number) {
  await setCurrentTeam(teamId);
  return request<void>(`/admin/frames/${frameId}`, {
    method: "DELETE"
  });
}

export async function fetchAuditLogs(teamId: number, filters?: { action?: string; start_date?: string; end_date?: string }) {
  await setCurrentTeam(teamId);
  const params = new URLSearchParams();
  if (filters?.action) {
    params.set("action", filters.action);
  }
  if (filters?.start_date) {
    params.set("start_date", filters.start_date);
  }
  if (filters?.end_date) {
    params.set("end_date", filters.end_date);
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return request<AuditLog[]>(`/admin/audit-logs${suffix}`);
}
