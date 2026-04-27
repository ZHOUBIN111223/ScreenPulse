// Frontend API contract types and request helpers for the research-group ScreenPulse backend.
export type ResearchGroupRole = "mentor" | "student";
export type TeamRole = ResearchGroupRole;

export type User = {
  id: number;
  email: string;
  name: string;
  current_research_group_id: number | null;
  current_team_id?: number | null;
  is_admin: boolean;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export type ResearchGroup = {
  id: number;
  name: string;
  created_by_user_id: number;
  created_at: string;
  updated_at: string;
  my_role: ResearchGroupRole;
};

export type Team = ResearchGroup;

export type ResearchGroupSetting = {
  frame_interval_seconds: number;
  frame_interval_minutes: number;
  force_screen_share: boolean;
};

export type TeamSetting = ResearchGroupSetting;

export type Session = {
  id: number;
  research_group_id: number;
  team_id?: number;
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

export type ResearchGroupMember = {
  user_id: number;
  email: string;
  name: string;
  role: ResearchGroupRole;
  status: string;
  joined_at: string;
  active_session: Session | null;
  latest_summary: string | null;
};

export type TeamMember = ResearchGroupMember;

export type InviteCode = {
  id: number;
  research_group_id: number;
  team_id?: number;
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
  research_group_id: number;
  team_id?: number;
  user_id: number;
  hour_start: string;
  hour_end: string;
  summary_text: string;
  frame_count: number;
  model_name: string;
  created_at: string;
};

export type DailyGoalInput = {
  goal_date: string;
  main_goal: string;
  planned_tasks: string;
  expected_challenges: string;
  needs_mentor_help: boolean;
};

export type DailyGoal = DailyGoalInput & {
  id: number;
  research_group_id: number;
  team_id?: number;
  user_id: number;
  created_at: string;
  updated_at: string;
};

export type DailyReportInput = {
  report_date: string;
  completed_work: string;
  problems: string;
  next_plan: string;
  needs_mentor_help: boolean;
  notes: string;
};

export type DailyReport = DailyReportInput & {
  id: number;
  research_group_id: number;
  team_id?: number;
  user_id: number;
  created_at: string;
  updated_at: string;
};

export type MentorFeedbackInput = {
  report_date: string;
  content: string;
  score: number | null;
  status_mark: "normal" | "needs_attention" | "needs_revision" | "needs_meeting" | "resolved";
  next_step: string;
  needs_meeting: boolean;
};

export type MentorFeedback = MentorFeedbackInput & {
  id: number;
  research_group_id: number;
  team_id?: number;
  user_id: number;
  mentor_user_id: number;
  created_at: string;
};

export type DailyReportDetail = {
  student: ResearchGroupMember;
  goal: DailyGoal | null;
  report: DailyReport | null;
  hourly_summaries: HourlySummary[];
  feedback: MentorFeedback[];
};

export type AuditLog = {
  id: number;
  research_group_id: number | null;
  team_id?: number | null;
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
  research_group_id: number;
  team_id?: number;
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

export function fetchResearchGroups() {
  return request<ResearchGroup[]>("/research-groups");
}

export function fetchAdminResearchGroups() {
  return request<ResearchGroup[]>("/admin/research-groups");
}

export function createResearchGroup(name: string) {
  return request<ResearchGroup>("/research-groups", {
    method: "POST",
    body: JSON.stringify({ name })
  });
}

export function fetchResearchGroup(researchGroupId: number) {
  return setCurrentResearchGroup(researchGroupId);
}

export function fetchCurrentResearchGroup() {
  return request<ResearchGroup>("/research-groups/current");
}

export function setCurrentResearchGroup(researchGroupId: number) {
  return request<ResearchGroup>("/research-groups/current", {
    method: "PUT",
    body: JSON.stringify({ research_group_id: researchGroupId })
  });
}

export const fetchTeams = fetchResearchGroups;
export const fetchAdminTeams = fetchAdminResearchGroups;
export const createTeam = createResearchGroup;
export const fetchTeam = fetchResearchGroup;
export const fetchCurrentTeam = fetchCurrentResearchGroup;
export const setCurrentTeam = setCurrentResearchGroup;

export function fetchAdminUsers() {
  return request<AdminUser[]>("/admin/users");
}

export function fetchAdminSessions(filters?: { research_group_id?: number; team_id?: number; user_id?: number; status?: string }) {
  const params = new URLSearchParams();
  const researchGroupId = filters?.research_group_id ?? filters?.team_id;
  if (researchGroupId !== undefined) {
    params.set("research_group_id", String(researchGroupId));
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

export async function fetchResearchGroupMembers(researchGroupId: number) {
  await setCurrentResearchGroup(researchGroupId);
  return request<ResearchGroupMember[]>("/mentor/members");
}

export async function addResearchGroupMember(researchGroupId: number, email: string, role: ResearchGroupRole) {
  await setCurrentResearchGroup(researchGroupId);
  return request<ResearchGroupMember>("/mentor/members", {
    method: "POST",
    body: JSON.stringify({ email, role })
  });
}

export async function updateResearchGroupMemberRole(researchGroupId: number, userId: number, role: ResearchGroupRole) {
  await setCurrentResearchGroup(researchGroupId);
  return request<ResearchGroupMember>(`/mentor/members/${userId}`, {
    method: "PATCH",
    body: JSON.stringify({ role })
  });
}

export async function removeResearchGroupMember(researchGroupId: number, userId: number) {
  await setCurrentResearchGroup(researchGroupId);
  return request<void>(`/mentor/members/${userId}`, {
    method: "DELETE"
  });
}

export async function createInviteCode(researchGroupId: number, input?: InviteCodeCreateInput) {
  await setCurrentResearchGroup(researchGroupId);
  return request<InviteCode>("/mentor/invite-codes", {
    method: "POST",
    body: JSON.stringify(input ?? {})
  });
}

export async function fetchInviteCodes(researchGroupId: number) {
  await setCurrentResearchGroup(researchGroupId);
  return request<InviteCode[]>("/mentor/invite-codes");
}

export async function updateInviteCodeStatus(researchGroupId: number, inviteCodeId: number, status: "active" | "disabled") {
  await setCurrentResearchGroup(researchGroupId);
  return request<InviteCode>(`/mentor/invite-codes/${inviteCodeId}`, {
    method: "PATCH",
    body: JSON.stringify({ status })
  });
}

export function joinResearchGroupByCode(code: string) {
  return request<ResearchGroup>("/research-groups/join", {
    method: "POST",
    body: JSON.stringify({ code })
  });
}

export const joinTeamByCode = joinResearchGroupByCode;

export async function fetchResearchGroupSettings(researchGroupId: number) {
  await setCurrentResearchGroup(researchGroupId);
  return request<TeamSetting>("/settings/current");
}

export async function updateResearchGroupSettings(researchGroupId: number, frame_interval_seconds: number, force_screen_share: boolean) {
  await setCurrentResearchGroup(researchGroupId);
  return request<TeamSetting>("/mentor/settings", {
    method: "PUT",
    body: JSON.stringify({ frame_interval_seconds, force_screen_share })
  });
}

export const fetchTeamMembers = fetchResearchGroupMembers;
export const addTeamMember = addResearchGroupMember;
export const updateTeamMemberRole = updateResearchGroupMemberRole;
export const removeTeamMember = removeResearchGroupMember;
export const fetchTeamSettings = fetchResearchGroupSettings;
export const updateTeamSettings = updateResearchGroupSettings;

export async function fetchCurrentSession(researchGroupId: number) {
  await setCurrentResearchGroup(researchGroupId);
  return request<Session | null>("/sessions/current");
}

export async function startSession(researchGroupId: number, source_label: string | null, source_type: string | null) {
  await setCurrentResearchGroup(researchGroupId);
  return request<Session>("/sessions/start", {
    method: "POST",
    body: JSON.stringify({ source_label, source_type })
  });
}

export async function stopSession(researchGroupId: number, sessionId: number) {
  await setCurrentResearchGroup(researchGroupId);
  void sessionId;
  return request<Session>("/sessions/stop", {
    method: "POST"
  });
}

export async function uploadFrame(
  researchGroupId: number,
  sessionId: number,
  file: Blob,
  capturedAt: string
) {
  await setCurrentResearchGroup(researchGroupId);
  void sessionId;
  const formData = new FormData();
  formData.append("file", file, "frame.png");
  formData.append("captured_at", capturedAt);

  return request<FrameUploadResult>("/screenshots/upload", {
    method: "POST",
    body: formData
  });
}

export async function fetchMySummaries(researchGroupId: number) {
  await setCurrentResearchGroup(researchGroupId);
  return request<HourlySummary[]>("/summaries/my-research-group");
}

export async function fetchMyDailyGoal(researchGroupId: number, goalDate: string) {
  await setCurrentResearchGroup(researchGroupId);
  return request<DailyGoal | null>(`/daily-goals/my?goal_date=${encodeURIComponent(goalDate)}`);
}

export async function saveMyDailyGoal(researchGroupId: number, input: DailyGoalInput) {
  await setCurrentResearchGroup(researchGroupId);
  return request<DailyGoal>("/daily-goals/my", {
    method: "PUT",
    body: JSON.stringify(input)
  });
}

export async function fetchMyDailyReports(researchGroupId: number) {
  await setCurrentResearchGroup(researchGroupId);
  return request<DailyReport[]>("/daily-reports/my");
}

export async function fetchMyDailyReportDetail(researchGroupId: number, reportDate: string) {
  await setCurrentResearchGroup(researchGroupId);
  return request<DailyReportDetail>(`/daily-reports/my/detail?report_date=${encodeURIComponent(reportDate)}`);
}

export async function saveMyDailyReport(researchGroupId: number, input: DailyReportInput) {
  await setCurrentResearchGroup(researchGroupId);
  return request<DailyReport>("/daily-reports/my", {
    method: "PUT",
    body: JSON.stringify(input)
  });
}

export async function fetchStudentDailyReports(researchGroupId: number, userId: number) {
  await setCurrentResearchGroup(researchGroupId);
  return request<DailyReport[]>(`/mentor/students/${userId}/daily-reports`);
}

export async function fetchStudentDailyReportDetail(researchGroupId: number, userId: number, reportDate: string) {
  await setCurrentResearchGroup(researchGroupId);
  return request<DailyReportDetail>(
    `/mentor/students/${userId}/daily-report?report_date=${encodeURIComponent(reportDate)}`
  );
}

export async function createStudentFeedback(researchGroupId: number, userId: number, input: MentorFeedbackInput) {
  await setCurrentResearchGroup(researchGroupId);
  return request<MentorFeedback>(`/mentor/students/${userId}/feedback`, {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export async function fetchResearchGroupSummaries(researchGroupId: number) {
  await setCurrentResearchGroup(researchGroupId);
  return request<HourlySummary[]>(`/mentor/summaries?research_group_id=${researchGroupId}`);
}

export async function fetchMemberSummaries(researchGroupId: number, userId: number) {
  await setCurrentResearchGroup(researchGroupId);
  return request<HourlySummary[]>(`/mentor/members/${userId}/summaries`);
}

export const fetchTeamSummaries = fetchResearchGroupSummaries;

export async function deleteHourlySummary(researchGroupId: number, summaryId: number) {
  await setCurrentResearchGroup(researchGroupId);
  return request<void>(`/mentor/summaries/${summaryId}`, {
    method: "DELETE"
  });
}

export async function fetchAdminFrames(researchGroupId: number) {
  await setCurrentResearchGroup(researchGroupId);
  return request<AdminFrame[]>("/mentor/frames");
}

export async function deleteAdminFrame(researchGroupId: number, frameId: number) {
  await setCurrentResearchGroup(researchGroupId);
  return request<void>(`/mentor/frames/${frameId}`, {
    method: "DELETE"
  });
}

export async function fetchAuditLogs(researchGroupId: number, filters?: { action?: string; start_date?: string; end_date?: string }) {
  await setCurrentResearchGroup(researchGroupId);
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
  return request<AuditLog[]>(`/mentor/audit-logs${suffix}`);
}
