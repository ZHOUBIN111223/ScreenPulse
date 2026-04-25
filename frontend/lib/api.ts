// Frontend API contract types and request helpers for the team-based ScreenPulse backend.
export type TeamRole = "admin" | "member";

export type User = {
  id: number;
  email: string;
  name: string;
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

type MessageOut = {
  message: string;
};

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
    throw new Error(data.detail ?? "请求失败");
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

export function createTeam(name: string) {
  return request<Team>("/teams", {
    method: "POST",
    body: JSON.stringify({ name })
  });
}

export function fetchTeam(teamId: number) {
  return request<Team>(`/teams/${teamId}`);
}

export function fetchTeamMembers(teamId: number) {
  return request<TeamMember[]>(`/teams/${teamId}/members`);
}

export function createInviteCode(teamId: number) {
  return request<InviteCode>(`/teams/${teamId}/invite-codes`, {
    method: "POST"
  });
}

export function joinTeamByCode(code: string) {
  return request<Team>(`/invite-codes/${code}/join`, {
    method: "POST"
  });
}

export function fetchTeamSettings(teamId: number) {
  return request<TeamSetting>(`/teams/${teamId}/settings`);
}

export function updateTeamSettings(teamId: number, frame_interval_seconds: number) {
  return request<TeamSetting>(`/teams/${teamId}/settings`, {
    method: "PATCH",
    body: JSON.stringify({ frame_interval_seconds })
  });
}

export function fetchCurrentSession(teamId: number) {
  return request<Session | null>(`/teams/${teamId}/screen-sessions/current`);
}

export function startSession(teamId: number, source_label: string | null, source_type: string | null) {
  return request<Session>(`/teams/${teamId}/screen-sessions/start`, {
    method: "POST",
    body: JSON.stringify({ source_label, source_type })
  });
}

export function stopSession(teamId: number, sessionId: number) {
  return request<Session>(`/teams/${teamId}/screen-sessions/${sessionId}/stop`, {
    method: "POST"
  });
}

export function uploadFrame(
  teamId: number,
  sessionId: number,
  file: Blob,
  capturedAt: string
) {
  const formData = new FormData();
  formData.append("file", file, "frame.png");
  formData.append("captured_at", capturedAt);

  return request<FrameUploadResult>(`/teams/${teamId}/screen-sessions/${sessionId}/frames`, {
    method: "POST",
    body: formData
  });
}

export function fetchMySummaries(teamId: number) {
  return request<HourlySummary[]>(`/teams/${teamId}/summaries/me`);
}

export function fetchTeamSummaries(teamId: number) {
  return request<HourlySummary[]>(`/teams/${teamId}/summaries`);
}

export function fetchMemberSummaries(teamId: number, userId: number) {
  return request<HourlySummary[]>(`/teams/${teamId}/members/${userId}/summaries`);
}
