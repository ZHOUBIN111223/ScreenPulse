"use client";

// Admin-only team console for member, invite, settings, audit, summary, and frame-history management.
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AdminFrame,
  AuditLog,
  HourlySummary,
  InviteCode,
  Team,
  TeamMember,
  TeamRole,
  TeamSetting,
  addTeamMember,
  clearToken,
  createInviteCode,
  deleteAdminFrame,
  deleteHourlySummary,
  fetchAdminFrames,
  fetchAdminTeams,
  fetchAuditLogs,
  fetchInviteCodes,
  fetchMe,
  fetchMemberSummaries,
  fetchTeamMembers,
  fetchTeamSettings,
  fetchTeamSummaries,
  getToken,
  logout,
  removeTeamMember,
  updateInviteCodeStatus,
  updateTeamMemberRole,
  updateTeamSettings
} from "../lib/api";

type AdminTab = "team" | "settings" | "invites" | "audit" | "monitor" | "data";
type IntervalUnit = "seconds" | "minutes" | "hours";

const tabs: { value: AdminTab; label: string }[] = [
  { value: "team", label: "团队管理" },
  { value: "settings", label: "设置管理" },
  { value: "invites", label: "邀请码管理" },
  { value: "audit", label: "审计日志" },
  { value: "monitor", label: "共享与总结监控" },
  { value: "data", label: "数据管理" }
];

const intervalUnits: { value: IntervalUnit; label: string; multiplier: number }[] = [
  { value: "seconds", label: "秒", multiplier: 1 },
  { value: "minutes", label: "分钟", multiplier: 60 },
  { value: "hours", label: "小时", multiplier: 3600 }
];

const auditActions = [
  "team.created",
  "team.joined",
  "team_member.added",
  "team_member.role_updated",
  "team_member.removed",
  "team_settings.updated",
  "invite_code.created",
  "invite_code.status_updated",
  "screen_session.started",
  "screen_session.stopped",
  "frame_capture.deleted",
  "hourly_summary.deleted"
];

function formatDateTime(value: string | null) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString("zh-CN");
}

function toIsoOrUndefined(value: string) {
  return value ? new Date(value).toISOString() : undefined;
}

function preferredIntervalUnit(seconds: number): IntervalUnit {
  if (seconds >= 3600 && seconds % 3600 === 0) {
    return "hours";
  }
  if (seconds >= 60 && seconds % 60 === 0) {
    return "minutes";
  }
  return "seconds";
}

function intervalDisplayValue(seconds: number, unit: IntervalUnit) {
  const option = intervalUnits.find((item) => item.value === unit) ?? intervalUnits[0];
  return Math.max(1, Math.round(seconds / option.multiplier));
}

function intervalToSeconds(value: number, unit: IntervalUnit) {
  const option = intervalUnits.find((item) => item.value === unit) ?? intervalUnits[0];
  return Math.max(1, Math.floor(value) || 1) * option.multiplier;
}

function formatInterval(seconds: number) {
  const unit = preferredIntervalUnit(seconds);
  const option = intervalUnits.find((item) => item.value === unit) ?? intervalUnits[0];
  return `${intervalDisplayValue(seconds, unit)} ${option.label}`;
}

export function AdminPanel() {
  const router = useRouter();
  const [teams, setTeams] = useState<Team[]>([]);
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null);
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [summaries, setSummaries] = useState<HourlySummary[]>([]);
  const [settings, setSettings] = useState<TeamSetting>({
    frame_interval_seconds: 300,
    frame_interval_minutes: 5,
    force_screen_share: false
  });
  const [inviteCodes, setInviteCodes] = useState<InviteCode[]>([]);
  const [frames, setFrames] = useState<AdminFrame[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [selectedMemberId, setSelectedMemberId] = useState<number | "all">("all");
  const [frameMemberFilter, setFrameMemberFilter] = useState<number | "all">("all");
  const [frameDateFilter, setFrameDateFilter] = useState("");
  const [summaryDateFilter, setSummaryDateFilter] = useState("");
  const [auditActionFilter, setAuditActionFilter] = useState("");
  const [auditStartDate, setAuditStartDate] = useState("");
  const [auditEndDate, setAuditEndDate] = useState("");
  const [activeTab, setActiveTab] = useState<AdminTab>("team");
  const [newMemberEmail, setNewMemberEmail] = useState("");
  const [newMemberRole, setNewMemberRole] = useState<TeamRole>("member");
  const [intervalUnit, setIntervalUnit] = useState<IntervalUnit>("minutes");
  const [intervalValue, setIntervalValue] = useState(5);
  const [forceScreenShare, setForceScreenShare] = useState(false);
  const [inviteExpiresValue, setInviteExpiresValue] = useState(7);
  const [inviteExpiresUnit, setInviteExpiresUnit] = useState<"hours" | "days">("days");
  const [inviteMaxUses, setInviteMaxUses] = useState(25);
  const [statusMessage, setStatusMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const selectedTeam = useMemo(
    () => teams.find((team) => team.id === selectedTeamId) ?? null,
    [selectedTeamId, teams]
  );
  const adminTeams = useMemo(() => teams.filter((team) => team.my_role === "admin"), [teams]);
  const liveMembers = members.filter((member) => member.active_session);
  const totalFrames = frames.length;
  const recognizedFrames = frames.filter((frame) => frame.recognized_content || frame.activity_description).length;

  const filteredFrames = useMemo(
    () =>
      frames.filter((frame) => {
        const memberMatches = frameMemberFilter === "all" || frame.user_id === frameMemberFilter;
        const dateMatches = !frameDateFilter || frame.captured_at.slice(0, 10) === frameDateFilter;
        return memberMatches && dateMatches;
      }),
    [frameDateFilter, frameMemberFilter, frames]
  );

  const filteredSummaries = useMemo(
    () => summaries.filter((summary) => !summaryDateFilter || summary.hour_start.slice(0, 10) === summaryDateFilter),
    [summaries, summaryDateFilter]
  );

  useEffect(() => {
    async function bootstrap() {
      if (!getToken()) {
        router.replace("/");
        return;
      }

      try {
        const user = await fetchMe();
        if (!user.is_admin) {
          router.replace("/teams");
          return;
        }
        const currentTeams = await fetchAdminTeams();
        setTeams(currentTeams);
        setSelectedTeamId(currentTeams[0]?.id ?? null);
      } catch {
        clearToken();
        router.replace("/");
      } finally {
        setLoading(false);
      }
    }

    void bootstrap();
  }, [router]);

  useEffect(() => {
    if (!selectedTeamId) {
      setMembers([]);
      setSummaries([]);
      setInviteCodes([]);
      setFrames([]);
      setAuditLogs([]);
      return;
    }

    void loadAdminData(selectedTeamId);
  }, [selectedTeamId]);

  useEffect(() => {
    if (!selectedTeamId || activeTab !== "monitor") {
      return;
    }

    const handle = window.setInterval(() => {
      void loadMonitorData(selectedTeamId);
    }, 10000);
    return () => window.clearInterval(handle);
  }, [activeTab, selectedTeamId]);

  async function loadMembers(teamId: number) {
    setMembers(await fetchTeamMembers(teamId));
  }

  async function loadSummaries(teamId: number, memberId: number | "all") {
    if (memberId === "all") {
      setSummaries(await fetchTeamSummaries(teamId));
    } else {
      setSummaries(await fetchMemberSummaries(teamId, memberId));
    }
  }

  async function loadAuditData(teamId: number) {
    const logs = await fetchAuditLogs(teamId, {
      action: auditActionFilter || undefined,
      start_date: toIsoOrUndefined(auditStartDate),
      end_date: toIsoOrUndefined(auditEndDate)
    });
    setAuditLogs(logs);
  }

  async function loadMonitorData(teamId: number) {
    const [nextMembers, nextFrames] = await Promise.all([fetchTeamMembers(teamId), fetchAdminFrames(teamId)]);
    setMembers(nextMembers);
    setFrames(nextFrames);
  }

  async function loadAdminData(teamId: number) {
    setError("");
    setStatusMessage("");

    try {
      const [nextMembers, nextSettings, nextInvites, nextFrames, nextAuditLogs] = await Promise.all([
        fetchTeamMembers(teamId),
        fetchTeamSettings(teamId),
        fetchInviteCodes(teamId),
        fetchAdminFrames(teamId),
        fetchAuditLogs(teamId)
      ]);
      const nextUnit = preferredIntervalUnit(nextSettings.frame_interval_seconds);
      setMembers(nextMembers);
      setSettings(nextSettings);
      setIntervalUnit(nextUnit);
      setIntervalValue(intervalDisplayValue(nextSettings.frame_interval_seconds, nextUnit));
      setForceScreenShare(nextSettings.force_screen_share);
      setInviteCodes(nextInvites);
      setFrames(nextFrames);
      setAuditLogs(nextAuditLogs);
      await loadSummaries(teamId, selectedMemberId);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "加载管理员数据失败");
    }
  }

  async function refreshCurrentTeam() {
    if (selectedTeamId) {
      await loadAdminData(selectedTeamId);
      setStatusMessage("数据已刷新");
    }
  }

  async function handleLogout() {
    try {
      await logout();
    } catch {
      // Client-side token cleanup still completes logout for this MVP.
    } finally {
      clearToken();
      router.replace("/");
    }
  }

  async function handleSaveSettings() {
    if (!selectedTeamId || !window.confirm("确认保存团队共享设置？")) {
      return;
    }

    try {
      const seconds = intervalToSeconds(intervalValue, intervalUnit);
      const nextSettings = await updateTeamSettings(selectedTeamId, seconds, forceScreenShare);
      const nextUnit = preferredIntervalUnit(nextSettings.frame_interval_seconds);
      setSettings(nextSettings);
      setIntervalUnit(nextUnit);
      setIntervalValue(intervalDisplayValue(nextSettings.frame_interval_seconds, nextUnit));
      setForceScreenShare(nextSettings.force_screen_share);
      await loadAuditData(selectedTeamId);
      setStatusMessage("团队设置已更新");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "保存团队设置失败");
    }
  }

  async function handleCreateInvite() {
    if (!selectedTeamId) {
      return;
    }

    try {
      const expiresInHours = inviteExpiresUnit === "days" ? inviteExpiresValue * 24 : inviteExpiresValue;
      const invite = await createInviteCode(selectedTeamId, {
        expires_in_hours: Math.max(1, Math.floor(expiresInHours) || 1),
        max_uses: Math.max(1, Math.floor(inviteMaxUses) || 1)
      });
      setInviteCodes((current) => [invite, ...current]);
      await loadAuditData(selectedTeamId);
      setStatusMessage("邀请码已生成");
    } catch (inviteError) {
      setError(inviteError instanceof Error ? inviteError.message : "生成邀请码失败");
    }
  }

  async function handleInviteStatus(inviteId: number, status: "active" | "disabled") {
    if (!selectedTeamId || !window.confirm(`确认${status === "active" ? "启用" : "禁用"}这个邀请码？`)) {
      return;
    }

    const invite = await updateInviteCodeStatus(selectedTeamId, inviteId, status);
    setInviteCodes((current) => current.map((item) => (item.id === invite.id ? invite : item)));
    await loadAuditData(selectedTeamId);
  }

  async function handleAddMember() {
    if (!selectedTeamId || !newMemberEmail.trim()) {
      return;
    }

    try {
      await addTeamMember(selectedTeamId, newMemberEmail.trim(), newMemberRole);
      setNewMemberEmail("");
      setNewMemberRole("member");
      await loadMembers(selectedTeamId);
      await loadAuditData(selectedTeamId);
      setStatusMessage("成员已添加");
    } catch (memberError) {
      setError(memberError instanceof Error ? memberError.message : "添加成员失败");
    }
  }

  async function handleRoleChange(userId: number, role: TeamRole) {
    if (!selectedTeamId || !window.confirm(`确认将该成员角色修改为 ${role}？`)) {
      return;
    }

    await updateTeamMemberRole(selectedTeamId, userId, role);
    await loadMembers(selectedTeamId);
    await loadAuditData(selectedTeamId);
    setStatusMessage("成员角色已更新");
  }

  async function handleRemoveMember(userId: number) {
    if (!selectedTeamId || !window.confirm("确认移除该成员？活跃共享会话也会被停止。")) {
      return;
    }

    await removeTeamMember(selectedTeamId, userId);
    await loadMembers(selectedTeamId);
    await loadAuditData(selectedTeamId);
    setStatusMessage("成员已移除");
  }

  async function handleDeleteFrame(frameId: number) {
    if (!selectedTeamId || !window.confirm("确认删除这条截图和识别结果？相关小时总结会重新计算。")) {
      return;
    }

    await deleteAdminFrame(selectedTeamId, frameId);
    setFrames((current) => current.filter((frame) => frame.frame_id !== frameId));
    await loadSummaries(selectedTeamId, selectedMemberId);
    await loadAuditData(selectedTeamId);
    setStatusMessage("截图记录已删除");
  }

  async function handleDeleteSummary(summaryId: number) {
    if (!selectedTeamId || !window.confirm("确认删除这条工作总结？")) {
      return;
    }

    await deleteHourlySummary(selectedTeamId, summaryId);
    setSummaries((current) => current.filter((summary) => summary.id !== summaryId));
    await loadAuditData(selectedTeamId);
    setStatusMessage("工作总结已删除");
  }

  async function handleSummaryMemberChange(value: string) {
    if (!selectedTeamId) {
      return;
    }

    const nextMemberId = value === "all" ? "all" : Number(value);
    setSelectedMemberId(nextMemberId);
    await loadSummaries(selectedTeamId, nextMemberId);
  }

  async function handleViewMemberSummaries(userId: number) {
    if (!selectedTeamId) {
      return;
    }

    setSelectedMemberId(userId);
    await loadSummaries(selectedTeamId, userId);
    setActiveTab("team");
  }

  async function handleApplyAuditFilters() {
    if (selectedTeamId) {
      await loadAuditData(selectedTeamId);
    }
  }

  if (loading) {
    return (
      <main className="admin-shell">
        <section className="admin-card">正在加载管理员控制台...</section>
      </main>
    );
  }

  return (
    <main className="admin-shell">
      <aside className="admin-sidebar">
        <div>
          <div className="admin-brand">ScreenPulse Admin</div>
          <p className="admin-sidebar-note">团队共享、总结、设置与审计集中管理</p>
        </div>
        <nav className="admin-nav" aria-label="管理员功能导航">
          {tabs.map((tab) => (
            <button
              className={activeTab === tab.value ? "admin-nav-item active" : "admin-nav-item"}
              key={tab.value}
              onClick={() => setActiveTab(tab.value)}
              type="button"
            >
              {tab.label}
            </button>
          ))}
        </nav>
        <div className="admin-sidebar-actions">
          <button className="button button-danger" onClick={() => void handleLogout()} type="button">
            退出
          </button>
        </div>
      </aside>

      <section className="admin-main">
        <header className="admin-topbar">
          <div>
            <p className="admin-kicker">管理员控制台</p>
            <h1>{selectedTeam?.name ?? "请选择团队"}</h1>
          </div>
          <div className="admin-topbar-controls">
            <label className="label">
              管理团队
              <select
                className="input"
                onChange={(event) => setSelectedTeamId(Number(event.target.value))}
                value={selectedTeamId ?? ""}
              >
                {adminTeams.map((team) => (
                  <option key={team.id} value={team.id}>
                    {team.name}
                  </option>
                ))}
              </select>
            </label>
            <button className="button button-primary" onClick={() => void refreshCurrentTeam()} type="button">
              刷新
            </button>
          </div>
        </header>

        {adminTeams.length === 0 ? <div className="admin-card">当前账号还没有任何团队的 admin 权限。</div> : null}
        {statusMessage ? <div className="success admin-alert">{statusMessage}</div> : null}
        {error ? <div className="error admin-alert">{error}</div> : null}

        {selectedTeam ? (
          <>
            <section className="admin-metrics">
              <div className="admin-metric">
                <span>实时共享</span>
                <strong>{liveMembers.length}</strong>
              </div>
              <div className="admin-metric">
                <span>成员总数</span>
                <strong>{members.length}</strong>
              </div>
              <div className="admin-metric">
                <span>抽帧频率</span>
                <strong>{formatInterval(settings.frame_interval_seconds)}</strong>
              </div>
              <div className="admin-metric">
                <span>截图识别</span>
                <strong>
                  {recognizedFrames}/{totalFrames}
                </strong>
              </div>
            </section>

            {activeTab === "team" ? (
              <section className="admin-section-grid">
                <div className="admin-card">
                  <div className="section-heading">
                    <div>
                      <h2>团队成员</h2>
                      <p>查看共享状态、开始时间，并执行总结查看、角色修改和移除操作。</p>
                    </div>
                  </div>
                  <div className="admin-member-form">
                    <input
                      className="input"
                      onChange={(event) => setNewMemberEmail(event.target.value)}
                      placeholder="成员邮箱"
                      value={newMemberEmail}
                    />
                    <select
                      className="input"
                      onChange={(event) => setNewMemberRole(event.target.value as TeamRole)}
                      value={newMemberRole}
                    >
                      <option value="member">member</option>
                      <option value="admin">admin</option>
                    </select>
                    <button className="button button-primary" onClick={() => void handleAddMember()} type="button">
                      添加成员
                    </button>
                  </div>
                  <div className="admin-table">
                    {members.map((member) => (
                      <div className="admin-row" key={member.user_id}>
                        <div>
                          <strong>{member.name}</strong>
                          <span>{member.email}</span>
                        </div>
                        <span className={member.active_session ? "pill" : "pill pill-warning"}>
                          {member.active_session ? "共享中" : "未共享"}
                        </span>
                        <span>{formatDateTime(member.active_session?.started_at ?? null)}</span>
                        <select
                          className="input compact-input"
                          onChange={(event) => void handleRoleChange(member.user_id, event.target.value as TeamRole)}
                          value={member.role}
                        >
                          <option value="member">member</option>
                          <option value="admin">admin</option>
                        </select>
                        <div className="button-row">
                          <button
                            className="button button-secondary"
                            onClick={() => void handleViewMemberSummaries(member.user_id)}
                            type="button"
                          >
                            查看总结
                          </button>
                          <button
                            className="button button-danger"
                            onClick={() => void handleRemoveMember(member.user_id)}
                            type="button"
                          >
                            移除
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="admin-card">
                  <div className="section-heading">
                    <div>
                      <h2>历史小时总结</h2>
                      <p>按成员查看历史总结，便于快速回溯工作内容。</p>
                    </div>
                    <select
                      className="input compact-input"
                      onChange={(event) => void handleSummaryMemberChange(event.target.value)}
                      value={selectedMemberId}
                    >
                      <option value="all">全部成员</option>
                      {members.map((member) => (
                        <option key={member.user_id} value={member.user_id}>
                          {member.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="admin-list">
                    {summaries.length === 0 ? <div className="note">暂无小时总结。</div> : null}
                    {summaries.slice(0, 8).map((summary) => (
                      <article className="admin-list-item" key={summary.id}>
                        <strong>{formatDateTime(summary.hour_start)}</strong>
                        <p>{summary.summary_text}</p>
                        <span className="note">用户 ID：{summary.user_id}，帧数：{summary.frame_count}</span>
                      </article>
                    ))}
                  </div>
                </div>
              </section>
            ) : null}

            {activeTab === "settings" ? (
              <section className="admin-card">
                <div className="section-heading">
                  <div>
                    <h2>设置管理</h2>
                    <p>配置团队抽帧频率和共享要求。抽帧频率支持秒、分钟和小时。</p>
                  </div>
                </div>
                <div className="admin-form-grid">
                  <label className="label">
                    抽帧频率
                    <input
                      className="input"
                      min={1}
                      onChange={(event) => setIntervalValue(Math.max(1, Number(event.target.value) || 1))}
                      type="number"
                      value={intervalValue}
                    />
                  </label>
                  <label className="label">
                    单位
                    <select
                      className="input"
                      onChange={(event) => setIntervalUnit(event.target.value as IntervalUnit)}
                      value={intervalUnit}
                    >
                      {intervalUnits.map((unit) => (
                        <option key={unit.value} value={unit.value}>
                          {unit.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="admin-toggle">
                    <input
                      checked={forceScreenShare}
                      onChange={(event) => setForceScreenShare(event.target.checked)}
                      type="checkbox"
                    />
                    强制开启显示屏共享
                  </label>
                  <button className="button button-primary" onClick={() => void handleSaveSettings()} type="button">
                    保存设置
                  </button>
                </div>
              </section>
            ) : null}

            {activeTab === "invites" ? (
              <section className="admin-section-grid">
                <div className="admin-card">
                  <h2>生成邀请码</h2>
                  <div className="admin-form-grid">
                    <label className="label">
                      有效期
                      <input
                        className="input"
                        min={1}
                        onChange={(event) => setInviteExpiresValue(Math.max(1, Number(event.target.value) || 1))}
                        type="number"
                        value={inviteExpiresValue}
                      />
                    </label>
                    <label className="label">
                      有效期单位
                      <select
                        className="input"
                        onChange={(event) => setInviteExpiresUnit(event.target.value as "hours" | "days")}
                        value={inviteExpiresUnit}
                      >
                        <option value="hours">小时</option>
                        <option value="days">天</option>
                      </select>
                    </label>
                    <label className="label">
                      使用次数
                      <input
                        className="input"
                        min={1}
                        onChange={(event) => setInviteMaxUses(Math.max(1, Number(event.target.value) || 1))}
                        type="number"
                        value={inviteMaxUses}
                      />
                    </label>
                    <button className="button button-primary" onClick={() => void handleCreateInvite()} type="button">
                      生成邀请码
                    </button>
                  </div>
                </div>
                <div className="admin-card">
                  <h2>已生成的邀请码</h2>
                  <div className="admin-list">
                    {inviteCodes.map((invite) => (
                      <article className="admin-list-item" key={invite.id}>
                        <div className="invite-code-line">
                          <strong className="mono">{invite.code}</strong>
                          <span className={invite.status === "active" ? "pill" : "pill pill-warning"}>
                            {invite.status}
                          </span>
                        </div>
                        <span>使用次数：{invite.used_count} / {invite.max_uses ?? "不限"}</span>
                        <span>过期时间：{formatDateTime(invite.expires_at)}</span>
                        <div className="button-row">
                          <button
                            className="button button-secondary"
                            onClick={() => void handleInviteStatus(invite.id, "active")}
                            type="button"
                          >
                            启用
                          </button>
                          <button
                            className="button button-danger"
                            onClick={() => void handleInviteStatus(invite.id, "disabled")}
                            type="button"
                          >
                            禁用
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                </div>
              </section>
            ) : null}

            {activeTab === "audit" ? (
              <section className="admin-card">
                <div className="section-heading">
                  <div>
                    <h2>审计日志</h2>
                    <p>查看团队创建、成员加入、设置修改、邀请码和数据删除等操作记录。</p>
                  </div>
                </div>
                <div className="admin-filter-bar">
                  <label className="label">
                    操作类型
                    <select
                      className="input"
                      onChange={(event) => setAuditActionFilter(event.target.value)}
                      value={auditActionFilter}
                    >
                      <option value="">全部操作</option>
                      {auditActions.map((action) => (
                        <option key={action} value={action}>
                          {action}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="label">
                    开始日期
                    <input
                      className="input"
                      onChange={(event) => setAuditStartDate(event.target.value)}
                      type="datetime-local"
                      value={auditStartDate}
                    />
                  </label>
                  <label className="label">
                    结束日期
                    <input
                      className="input"
                      onChange={(event) => setAuditEndDate(event.target.value)}
                      type="datetime-local"
                      value={auditEndDate}
                    />
                  </label>
                  <button className="button button-primary" onClick={() => void handleApplyAuditFilters()} type="button">
                    筛选
                  </button>
                </div>
                <div className="admin-list">
                  {auditLogs.length === 0 ? <div className="note">暂无审计日志。</div> : null}
                  {auditLogs.map((log) => (
                    <article className="admin-list-item audit-item" key={log.id}>
                      <strong>{log.action}</strong>
                      <span>{formatDateTime(log.created_at)}</span>
                      <span>
                        操作人：{log.actor_name ?? "系统"} {log.actor_email ? `(${log.actor_email})` : ""}
                      </span>
                      <span className="note">
                        目标：{log.target_type} #{log.target_id ?? "-"}
                      </span>
                    </article>
                  ))}
                </div>
              </section>
            ) : null}

            {activeTab === "monitor" ? (
              <section className="admin-section-grid">
                <div className="admin-card">
                  <h2>屏幕共享状态</h2>
                  <div className="admin-list">
                    {members.map((member) => (
                      <article className="admin-list-item" key={member.user_id}>
                        <div className="invite-code-line">
                          <strong>{member.name}</strong>
                          <span className={member.active_session ? "pill" : "pill pill-warning"}>
                            {member.active_session ? "共享中" : "未共享"}
                          </span>
                        </div>
                        <span>{member.email}</span>
                        <span>开始时间：{formatDateTime(member.active_session?.started_at ?? null)}</span>
                        <span>上传帧数：{member.active_session?.frame_count ?? 0}</span>
                        <p className="note">最近总结：{member.latest_summary ?? "暂无"}</p>
                      </article>
                    ))}
                  </div>
                </div>
                <div className="admin-card">
                  <h2>截图上传与识别结果</h2>
                  <div className="admin-list">
                    {frames.slice(0, 10).map((frame) => (
                      <article className="admin-list-item" key={frame.frame_id}>
                        <strong>{frame.user_name}</strong>
                        <span>{formatDateTime(frame.captured_at)}</span>
                        <span>{frame.width}x{frame.height}，模型：{frame.model_name ?? "-"}</span>
                        <p>{frame.activity_description ?? "暂无活动描述"}</p>
                        <button
                          className="button button-secondary"
                          onClick={() => {
                            setFrameMemberFilter(frame.user_id);
                            setActiveTab("data");
                          }}
                          type="button"
                        >
                          查看详细记录
                        </button>
                      </article>
                    ))}
                  </div>
                </div>
              </section>
            ) : null}

            {activeTab === "data" ? (
              <section className="admin-section-grid">
                <div className="admin-card">
                  <div className="section-heading">
                    <div>
                      <h2>历史截图与识别结果</h2>
                      <p>按成员和日期筛选，并删除不再需要的截图识别记录。</p>
                    </div>
                  </div>
                  <div className="admin-filter-bar">
                    <label className="label">
                      成员
                      <select
                        className="input"
                        onChange={(event) =>
                          setFrameMemberFilter(event.target.value === "all" ? "all" : Number(event.target.value))
                        }
                        value={frameMemberFilter}
                      >
                        <option value="all">全部成员</option>
                        {members.map((member) => (
                          <option key={member.user_id} value={member.user_id}>
                            {member.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="label">
                      日期
                      <input
                        className="input"
                        onChange={(event) => setFrameDateFilter(event.target.value)}
                        type="date"
                        value={frameDateFilter}
                      />
                    </label>
                  </div>
                  <div className="admin-list">
                    {filteredFrames.length === 0 ? <div className="note">暂无匹配的截图识别记录。</div> : null}
                    {filteredFrames.map((frame) => (
                      <article className="admin-list-item" key={frame.frame_id}>
                        <strong>{formatDateTime(frame.captured_at)}</strong>
                        <span>
                          {frame.user_name} ({frame.user_email})
                        </span>
                        <span className="note">
                          {frame.width}x{frame.height}，模型：{frame.model_name ?? "-"}
                        </span>
                        <p>{frame.activity_description ?? "暂无活动描述"}</p>
                        <p className="note">{frame.recognized_content ?? "暂无识别内容"}</p>
                        <button
                          className="button button-danger"
                          onClick={() => void handleDeleteFrame(frame.frame_id)}
                          type="button"
                        >
                          删除截图和识别结果
                        </button>
                      </article>
                    ))}
                  </div>
                </div>
                <div className="admin-card">
                  <div className="section-heading">
                    <div>
                      <h2>工作总结管理</h2>
                      <p>查看、筛选和删除历史小时总结。</p>
                    </div>
                  </div>
                  <div className="admin-filter-bar">
                    <label className="label">
                      成员
                      <select
                        className="input"
                        onChange={(event) => void handleSummaryMemberChange(event.target.value)}
                        value={selectedMemberId}
                      >
                        <option value="all">全部成员</option>
                        {members.map((member) => (
                          <option key={member.user_id} value={member.user_id}>
                            {member.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="label">
                      日期
                      <input
                        className="input"
                        onChange={(event) => setSummaryDateFilter(event.target.value)}
                        type="date"
                        value={summaryDateFilter}
                      />
                    </label>
                  </div>
                  <div className="admin-list">
                    {filteredSummaries.length === 0 ? <div className="note">暂无匹配的工作总结。</div> : null}
                    {filteredSummaries.map((summary) => (
                      <article className="admin-list-item" key={summary.id}>
                        <strong>{formatDateTime(summary.hour_start)}</strong>
                        <p>{summary.summary_text}</p>
                        <span className="note">用户 ID：{summary.user_id}，帧数：{summary.frame_count}</span>
                        <button
                          className="button button-danger"
                          onClick={() => void handleDeleteSummary(summary.id)}
                          type="button"
                        >
                          删除总结
                        </button>
                      </article>
                    ))}
                  </div>
                </div>
              </section>
            ) : null}
          </>
        ) : null}
      </section>
    </main>
  );
}
