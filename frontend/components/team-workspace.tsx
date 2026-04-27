"use client";

// Research-group workspace that combines group selection, screen sharing, invite management, settings, and summary review.
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  DailyReportDetail,
  HourlySummary,
  InviteCode,
  MentorFeedbackInput,
  Session,
  Team,
  TeamMember,
  TeamSetting,
  clearToken,
  createStudentFeedback,
  createInviteCode,
  createTeam,
  fetchCurrentSession,
  fetchMe,
  fetchMyDailyGoal,
  fetchMyDailyReportDetail,
  fetchMemberSummaries,
  fetchMySummaries,
  fetchStudentDailyReportDetail,
  fetchTeam,
  fetchTeamMembers,
  fetchTeamSettings,
  fetchTeams,
  getToken,
  joinTeamByCode,
  logout,
  saveMyDailyGoal,
  saveMyDailyReport,
  startSession,
  stopSession,
  updateTeamSettings,
  uploadFrame
} from "../lib/api";

function formatDateTime(value: string | null) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString("zh-CN");
}

function toDateKey(value: string) {
  const date = new Date(value);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function todayDateKey() {
  return toDateKey(new Date().toISOString());
}

function roleLabel(role: string) {
  if (role === "mentor") {
    return "导师";
  }
  if (role === "student") {
    return "学生";
  }
  return role;
}

type IntervalUnit = "seconds" | "minutes" | "hours";

const intervalUnitOptions: { value: IntervalUnit; label: string }[] = [
  { value: "seconds", label: "秒" },
  { value: "minutes", label: "分钟" },
  { value: "hours", label: "小时" }
];

function intervalSecondsToDisplayValue(seconds: number, unit: IntervalUnit) {
  if (unit === "hours") {
    return Math.max(1, Math.round(seconds / 3600));
  }
  if (unit === "minutes") {
    return Math.max(1, Math.round(seconds / 60));
  }
  return Math.max(1, seconds);
}

function displayValueToIntervalSeconds(value: number, unit: IntervalUnit) {
  const normalizedValue = Math.max(1, Math.floor(value) || 1);
  if (unit === "hours") {
    return normalizedValue * 3600;
  }
  if (unit === "minutes") {
    return normalizedValue * 60;
  }
  return normalizedValue;
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

function formatInterval(seconds: number) {
  const unit = preferredIntervalUnit(seconds);
  const label = intervalUnitOptions.find((item) => item.value === unit)?.label ?? "秒";
  return `${intervalSecondsToDisplayValue(seconds, unit)} ${label} / 帧`;
}

export function TeamWorkspace() {
  const router = useRouter();
  const [me, setMe] = useState<{ name: string; email: string; is_admin: boolean } | null>(null);
  const [teams, setTeams] = useState<Team[]>([]);
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null);
  const [selectedTeam, setSelectedTeam] = useState<Team | null>(null);
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [summaries, setSummaries] = useState<HourlySummary[]>([]);
  const [selectedMemberId, setSelectedMemberId] = useState<number | null>(null);
  const [settings, setSettings] = useState<TeamSetting>({
    frame_interval_seconds: 300,
    frame_interval_minutes: 5,
    force_screen_share: false
  });
  const [intervalUnit, setIntervalUnit] = useState<IntervalUnit>("minutes");
  const [session, setSession] = useState<Session | null>(null);
  const [createTeamName, setCreateTeamName] = useState("");
  const [joinCode, setJoinCode] = useState("");
  const [latestInviteCode, setLatestInviteCode] = useState<InviteCode | null>(null);
  const [statusMessage, setStatusMessage] = useState("");
  const [error, setError] = useState("");
  const [lastObservation, setLastObservation] = useState("");
  const [lastActivity, setLastActivity] = useState("");
  const [lastUploadAt, setLastUploadAt] = useState<string | null>(null);
  const [monitorWarning, setMonitorWarning] = useState("");
  const [dateFilter, setDateFilter] = useState("");
  const [reportDate, setReportDate] = useState(todayDateKey());
  const [dailyDetail, setDailyDetail] = useState<DailyReportDetail | null>(null);
  const [dailyGoalForm, setDailyGoalForm] = useState({
    main_goal: "",
    planned_tasks: "",
    expected_challenges: "",
    needs_mentor_help: false
  });
  const [dailyReportForm, setDailyReportForm] = useState({
    completed_work: "",
    problems: "",
    next_plan: "",
    needs_mentor_help: false,
    notes: ""
  });
  const [feedbackForm, setFeedbackForm] = useState({
    content: "",
    score: "",
    status_mark: "normal" as MentorFeedbackInput["status_mark"],
    next_step: "",
    needs_meeting: false
  });
  const [loadingWorkspace, setLoadingWorkspace] = useState(true);
  const [isCreatingTeam, setIsCreatingTeam] = useState(false);
  const [isJoiningTeam, setIsJoiningTeam] = useState(false);
  const [isGeneratingInvite, setIsGeneratingInvite] = useState(false);
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [isSavingDailyGoal, setIsSavingDailyGoal] = useState(false);
  const [isSavingDailyReport, setIsSavingDailyReport] = useState(false);
  const [isSavingFeedback, setIsSavingFeedback] = useState(false);

  const streamRef = useRef<MediaStream | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const timerRef = useRef<number | null>(null);
  const sessionRef = useRef<Session | null>(null);
  const settingsRef = useRef<TeamSetting>({
    frame_interval_seconds: 300,
    frame_interval_minutes: 5,
    force_screen_share: false
  });

  const isAdmin = selectedTeam?.my_role === "mentor";
  const isSharing = session?.status === "active";
  const selectedMember =
    selectedMemberId === null ? null : members.find((item) => item.user_id === selectedMemberId) ?? null;
  const visibleSummaries = summaries.filter((item) =>
    dateFilter ? toDateKey(item.hour_start) === dateFilter : true
  );

  useEffect(() => {
    sessionRef.current = session;
  }, [session]);

  useEffect(() => {
    settingsRef.current = settings;
  }, [settings]);

  useEffect(() => {
    async function bootstrap() {
      if (!getToken()) {
        router.replace("/");
        return;
      }

      try {
        const [currentUser, currentTeams] = await Promise.all([fetchMe(), fetchTeams()]);
        setMe(currentUser);
        setTeams(currentTeams);
        setSelectedTeamId((current) => current ?? currentTeams[0]?.id ?? null);
      } catch {
        clearToken();
        router.replace("/");
      } finally {
        setLoadingWorkspace(false);
      }
    }

    void bootstrap();

    return () => {
      clearCaptureTimer();
      stopTracks();
    };
  }, [router]);

  useEffect(() => {
    if (selectedTeamId === null) {
      setSelectedTeam(null);
      setMembers([]);
      setSummaries([]);
      setSession(null);
      return;
    }

    void loadTeamWorkspace(selectedTeamId);
  }, [selectedTeamId]);

  useEffect(() => {
    if (!selectedTeamId) {
      return;
    }

    const handle = window.setInterval(async () => {
      try {
        const [nextSession, nextTeams] = await Promise.all([
          fetchCurrentSession(selectedTeamId),
          fetchTeams()
        ]);
        setSession(nextSession);
        setTeams(nextTeams);

        if (selectedTeam?.my_role === "mentor") {
          const nextMembers = await fetchTeamMembers(selectedTeamId);
          setMembers(nextMembers);
        }
      } catch {
        // keep the last successful state
      }
    }, 15000);

    return () => window.clearInterval(handle);
  }, [selectedTeam?.my_role, selectedTeamId]);

  async function loadTeamWorkspace(teamId: number) {
    setError("");
    setStatusMessage("");
    setLatestInviteCode(null);

    try {
      const team = await fetchTeam(teamId);
      const [teamSettings, currentSession] = await Promise.all([
        fetchTeamSettings(teamId),
        fetchCurrentSession(teamId)
      ]);

      setSelectedTeam(team);
      setSettings(teamSettings);
      setIntervalUnit(preferredIntervalUnit(teamSettings.frame_interval_seconds));
      setSession(currentSession);

      if (team.my_role === "mentor") {
        const teamMembers = await fetchTeamMembers(teamId);
        setMembers(teamMembers);
        const defaultMemberId =
          selectedMemberId && teamMembers.some((item) => item.user_id === selectedMemberId)
            ? selectedMemberId
            : teamMembers[0]?.user_id ?? null;
        setSelectedMemberId(defaultMemberId);
        if (defaultMemberId !== null) {
          setSummaries(await fetchMemberSummaries(teamId, defaultMemberId));
        } else {
          setSummaries([]);
        }
      } else {
        setMembers([]);
        setSelectedMemberId(null);
        setSummaries(await fetchMySummaries(teamId));
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "加载课题组失败");
    }
  }

  async function loadDailyDetail(teamId: number, role: Team["my_role"], memberId: number | null, day: string) {
    if (role === "mentor") {
      if (memberId === null) {
        setDailyDetail(null);
        return;
      }
      setDailyDetail(await fetchStudentDailyReportDetail(teamId, memberId, day));
      return;
    }

    const [goal, detail] = await Promise.all([
      fetchMyDailyGoal(teamId, day),
      fetchMyDailyReportDetail(teamId, day)
    ]);
    setDailyDetail(detail);
    setDailyGoalForm({
      main_goal: goal?.main_goal ?? "",
      planned_tasks: goal?.planned_tasks ?? "",
      expected_challenges: goal?.expected_challenges ?? "",
      needs_mentor_help: goal?.needs_mentor_help ?? false
    });
    setDailyReportForm({
      completed_work: detail.report?.completed_work ?? "",
      problems: detail.report?.problems ?? "",
      next_plan: detail.report?.next_plan ?? "",
      needs_mentor_help: detail.report?.needs_mentor_help ?? false,
      notes: detail.report?.notes ?? ""
    });
  }

  useEffect(() => {
    if (!selectedTeamId || !isAdmin || selectedMemberId === null) {
      return;
    }

    void (async () => {
      try {
        setSummaries(await fetchMemberSummaries(selectedTeamId, selectedMemberId));
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "加载成员总结失败");
      }
    })();
  }, [isAdmin, selectedMemberId, selectedTeamId]);

  useEffect(() => {
    if (!selectedTeamId || !selectedTeam) {
      setDailyDetail(null);
      return;
    }

    void (async () => {
      try {
        await loadDailyDetail(selectedTeamId, selectedTeam.my_role, selectedMemberId, reportDate);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "鍔犺浇鏃ユ姤澶辫触");
      }
    })();
  }, [reportDate, selectedMemberId, selectedTeam, selectedTeamId]);

  function clearCaptureTimer() {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }

  function stopTracks() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  }

  async function refreshTeamsAndSelect(teamId: number) {
    const currentTeams = await fetchTeams();
    setTeams(currentTeams);
    setSelectedTeamId(teamId);
  }

  async function handleCreateTeam() {
    if (!createTeamName.trim()) {
      setError("请输入课题组名称");
      return;
    }

    setIsCreatingTeam(true);
    setError("");
    setStatusMessage("");

    try {
      const team = await createTeam(createTeamName.trim());
      setCreateTeamName("");
      setStatusMessage("课题组已创建，你已自动成为导师。");
      await refreshTeamsAndSelect(team.id);
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "创建课题组失败");
    } finally {
      setIsCreatingTeam(false);
    }
  }

  async function handleJoinTeam() {
    if (!joinCode.trim()) {
      setError("请输入邀请码");
      return;
    }

    setIsJoiningTeam(true);
    setError("");
    setStatusMessage("");

    try {
      const team = await joinTeamByCode(joinCode.trim().toUpperCase());
      setJoinCode("");
      setStatusMessage("已加入课题组。");
      await refreshTeamsAndSelect(team.id);
    } catch (joinError) {
      setError(joinError instanceof Error ? joinError.message : "加入课题组失败");
    } finally {
      setIsJoiningTeam(false);
    }
  }

  async function handleGenerateInviteCode() {
    if (!selectedTeamId) {
      return;
    }

    setIsGeneratingInvite(true);
    setError("");
    setStatusMessage("");

    try {
      const inviteCode = await createInviteCode(selectedTeamId);
      setLatestInviteCode(inviteCode);
      setStatusMessage("邀请码已生成。");
    } catch (inviteError) {
      setError(inviteError instanceof Error ? inviteError.message : "生成邀请码失败");
    } finally {
      setIsGeneratingInvite(false);
    }
  }

  async function handleSaveSettings() {
    if (!selectedTeamId) {
      return;
    }

    setIsSavingSettings(true);
    setError("");
    setStatusMessage("");

    try {
      const nextSettings = await updateTeamSettings(
        selectedTeamId,
        settings.frame_interval_seconds,
        settings.force_screen_share
      );
      setSettings(nextSettings);
      setIntervalUnit(preferredIntervalUnit(nextSettings.frame_interval_seconds));
      setStatusMessage("课题组抽帧频率已更新。");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "保存课题组设置失败");
    } finally {
      setIsSavingSettings(false);
    }
  }

  async function handleSaveDailyGoal() {
    if (!selectedTeamId || !dailyGoalForm.main_goal.trim()) {
      setError("Please fill in today's main goal.");
      return;
    }

    setIsSavingDailyGoal(true);
    setError("");
    try {
      await saveMyDailyGoal(selectedTeamId, {
        goal_date: reportDate,
        ...dailyGoalForm,
        main_goal: dailyGoalForm.main_goal.trim()
      });
      await loadDailyDetail(selectedTeamId, "student", null, reportDate);
      setStatusMessage("今日目标已保存。");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "保存今日目标失败。");
    } finally {
      setIsSavingDailyGoal(false);
    }
  }

  async function handleSaveDailyReport() {
    if (!selectedTeamId || !dailyReportForm.completed_work.trim()) {
      setError("Please fill in what you completed today.");
      return;
    }

    setIsSavingDailyReport(true);
    setError("");
    try {
      await saveMyDailyReport(selectedTeamId, {
        report_date: reportDate,
        ...dailyReportForm,
        completed_work: dailyReportForm.completed_work.trim()
      });
      await loadDailyDetail(selectedTeamId, "student", null, reportDate);
      setStatusMessage("日报已保存。");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "保存日报失败。");
    } finally {
      setIsSavingDailyReport(false);
    }
  }

  async function handleCreateFeedback() {
    if (!selectedTeamId || selectedMemberId === null || !feedbackForm.content.trim()) {
      setError("Please fill in feedback content.");
      return;
    }

    setIsSavingFeedback(true);
    setError("");
    try {
      await createStudentFeedback(selectedTeamId, selectedMemberId, {
        report_date: reportDate,
        content: feedbackForm.content.trim(),
        score: feedbackForm.score ? Number(feedbackForm.score) : null,
        status_mark: feedbackForm.status_mark,
        next_step: feedbackForm.next_step,
        needs_meeting: feedbackForm.needs_meeting
      });
      setFeedbackForm({
        content: "",
        score: "",
        status_mark: "normal",
        next_step: "",
        needs_meeting: false
      });
      await loadDailyDetail(selectedTeamId, "mentor", selectedMemberId, reportDate);
      setStatusMessage("导师反馈已保存。");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "保存反馈失败。");
    } finally {
      setIsSavingFeedback(false);
    }
  }

  async function handleLogout() {
    try {
      await logout();
    } catch {
      // ignore server-side logout errors for stateless tokens
    } finally {
      clearToken();
      router.replace("/");
    }
  }

  async function captureFrame() {
    const activeTeamId = selectedTeamId;
    const activeStream = streamRef.current;
    const activeSession = sessionRef.current;
    const video = videoRef.current;

    if (!activeTeamId || !activeStream || !activeSession || !video) {
      return;
    }

    if (video.readyState < 2) {
      return;
    }

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext("2d");

    if (!context) {
      return;
    }

    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/png", 0.92)
    );

    if (!blob) {
      return;
    }

    const result = await uploadFrame(activeTeamId, activeSession.id, blob, new Date().toISOString());
    setLastObservation(result.recognized_content);
    setLastActivity(result.activity_description);
    setLastUploadAt(new Date().toISOString());
    setSettings({
      frame_interval_seconds: result.frame_interval_seconds,
      frame_interval_minutes: result.frame_interval_minutes,
      force_screen_share: settingsRef.current.force_screen_share
    });
    setStatusMessage("最新截图已上传并完成识别。");

    if (selectedTeam?.my_role === "mentor" && selectedMemberId !== null) {
      setSummaries(await fetchMemberSummaries(activeTeamId, selectedMemberId));
      setMembers(await fetchTeamMembers(activeTeamId));
    } else {
      setSummaries(await fetchMySummaries(activeTeamId));
    }
  }

  function scheduleNextCapture(delaySeconds: number) {
    clearCaptureTimer();
    timerRef.current = window.setTimeout(async () => {
      try {
        await captureFrame();
      } catch (captureError) {
        setError(captureError instanceof Error ? captureError.message : "上传截图失败");
      } finally {
        if (sessionRef.current?.status === "active") {
          scheduleNextCapture(settingsRef.current.frame_interval_seconds);
        }
      }
    }, delaySeconds * 1000);
  }

  async function handleStartSharing() {
    if (!selectedTeamId) {
      return;
    }

    setIsStarting(true);
    setError("");
    setStatusMessage("");
    setMonitorWarning("");

    try {
      const mediaStream = await navigator.mediaDevices.getDisplayMedia({
        video: {
          displaySurface: "monitor"
        } as MediaTrackConstraints,
        audio: false
      });

      const track = mediaStream.getVideoTracks()[0];
      const trackSettings = track.getSettings() as MediaTrackSettings & {
        displaySurface?: string;
      };

      if (trackSettings.displaySurface && trackSettings.displaySurface !== "monitor") {
        track.stop();
        throw new Error("请选择“整个屏幕”，不要只共享单个窗口或标签页。");
      }

      if (!trackSettings.displaySurface) {
        setMonitorWarning("当前浏览器没有返回共享源类型，请确认你选择的是整个显示屏。");
      }

      const createdSession = await startSession(
        selectedTeamId,
        track.label ?? null,
        trackSettings.displaySurface ?? null
      );

      track.onended = () => {
        void handleStopSharing(true);
      };

      streamRef.current = mediaStream;
      setSession(createdSession);
      setStatusMessage("共享已开始，浏览器会按课题组设置定时抽帧。");

      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
        await videoRef.current.play();
      }

      await captureFrame();
      scheduleNextCapture(settingsRef.current.frame_interval_seconds);
    } catch (startError) {
      stopTracks();
      setError(startError instanceof Error ? startError.message : "启动共享失败");
    } finally {
      setIsStarting(false);
    }
  }

  async function handleStopSharing(silent = false) {
    if (!selectedTeamId) {
      return;
    }

    setIsStopping(true);
    setError("");

    try {
      const activeSession = sessionRef.current;
      if (activeSession?.status === "active") {
        const stoppedSession = await stopSession(selectedTeamId, activeSession.id);
        setSession(stoppedSession);
      }
      clearCaptureTimer();
      stopTracks();
      if (!silent) {
        setStatusMessage("共享已停止。");
      }
    } catch (stopError) {
      setError(stopError instanceof Error ? stopError.message : "停止共享失败");
    } finally {
      setIsStopping(false);
    }
  }

  if (loadingWorkspace) {
    return (
      <main className="app-shell">
        <div className="page-grid">
          <section className="panel">
          <p>正在加载课题组工作台...</p>
          </section>
        </div>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <div className="page-grid">
        <section className="hero">
          <div className="pill">课题组工作台</div>
          <h1>围绕课题组、邀请码和组内角色组织屏幕共享总结流程。</h1>
          <p>
            当前登录账号：{me?.name ?? "-"}（{me?.email ?? "-"}）。先选择课题组，再开始整屏共享、邀请学生、查看学生状态和小时级总结。
          </p>
        </section>

        <section className="panel-grid">
          <section className="panel">
            <div className="form-grid">
              <div>
                <h2>我的课题组</h2>
                <p>你只能访问自己已经加入的课题组。</p>
              </div>
              <div className="list">
                {teams.length === 0 ? <div className="note">你还没有加入任何课题组。</div> : null}
                {teams.map((team) => (
                  <button
                    className={team.id === selectedTeamId ? "button button-primary" : "button button-secondary"}
                    disabled={Boolean(streamRef.current)}
                    key={team.id}
                    onClick={() => setSelectedTeamId(team.id)}
                    type="button"
                  >
                    {team.name} · {roleLabel(team.my_role)}
                  </button>
                ))}
              </div>
            </div>
          </section>

          <section className="panel">
            <div className="form-grid">
              <div>
                <h2>创建课题组</h2>
                <p>创建者会自动成为课题组导师。</p>
              </div>
              <label className="label">
                课题组名称
                <input
                  className="input"
                  onChange={(event) => setCreateTeamName(event.target.value)}
                  placeholder="例如：多模态学习课题组"
                  value={createTeamName}
                />
              </label>
              <button
                className="button button-primary"
                disabled={isCreatingTeam}
                onClick={() => void handleCreateTeam()}
                type="button"
              >
                {isCreatingTeam ? "创建中..." : "创建课题组"}
              </button>
            </div>
          </section>

          <section className="panel">
            <div className="form-grid">
              <div>
                <h2>加入课题组</h2>
                <p>输入导师生成的邀请码即可加入课题组。</p>
              </div>
              <label className="label">
                邀请码
                <input
                  className="input mono"
                  onChange={(event) => setJoinCode(event.target.value)}
                  placeholder="AB12CD34"
                  value={joinCode}
                />
              </label>
              <button
                className="button button-primary"
                disabled={isJoiningTeam}
                onClick={() => void handleJoinTeam()}
                type="button"
              >
                {isJoiningTeam ? "加入中..." : "加入课题组"}
              </button>
            </div>
          </section>
        </section>

        {selectedTeam ? (
          <>
            <section className="panel">
              <div className="stats-grid">
                <div className="stat-card">
                  当前课题组
                  <strong>{selectedTeam.name}</strong>
                </div>
                <div className="stat-card">
                  我的角色
                  <strong>{roleLabel(selectedTeam.my_role)}</strong>
                </div>
                <div className="stat-card">
                  共享状态
                  <strong>{isSharing ? "共享中" : "未共享"}</strong>
                </div>
                <div className="stat-card">
                  抽帧频率
                  <strong>{formatInterval(settings.frame_interval_seconds)}</strong>
                </div>
                <div className="stat-card">
                  开始时间
                  <strong>{formatDateTime(session?.started_at ?? null)}</strong>
                </div>
              </div>
            </section>

            <section className="panel-grid">
              <section className="panel">
                <div className="form-grid">
                  <div>
                    <h2>屏幕共享</h2>
                    <p>仅允许主动共享整个显示屏。系统只保存截图和文字总结，不保存完整录屏。</p>
                  </div>
                  <div className="button-row">
                    <button
                      className="button button-primary"
                      disabled={isSharing || isStarting}
                      onClick={() => void handleStartSharing()}
                      type="button"
                    >
                      {isStarting ? "启动中..." : "开始共享"}
                    </button>
                    <button
                      className="button button-danger"
                      disabled={!isSharing || isStopping}
                      onClick={() => void handleStopSharing()}
                      type="button"
                    >
                      {isStopping ? "停止中..." : "停止共享"}
                    </button>
                    <button className="button button-secondary" onClick={() => void handleLogout()} type="button">
                      退出登录
                    </button>
                  </div>
                  {statusMessage ? <div className="success">{statusMessage}</div> : null}
                  {monitorWarning ? <div className="note">{monitorWarning}</div> : null}
                  {error ? <div className="error">{error}</div> : null}
                  <div className="note">
                    最近上传时间：{lastUploadAt ? formatDateTime(lastUploadAt) : "暂无"}
                  </div>
                  <div className="list-item">
                    <strong>最近识别内容</strong>
                    <span>{lastObservation || "首次上传截图后显示。"}</span>
                  </div>
                  <div className="list-item">
                    <strong>最近活动描述</strong>
                    <span>{lastActivity || "首次上传截图后显示。"}</span>
                  </div>
                </div>
              </section>

              {isAdmin ? (
                <section className="panel">
                  <div className="form-grid">
                    <div>
                  <h2>课题组管理</h2>
                  <p>导师可以生成邀请码并修改课题组抽帧频率。</p>
                    </div>
                    <div className="button-row">
                      <button
                        className="button button-primary"
                        disabled={isGeneratingInvite}
                        onClick={() => void handleGenerateInviteCode()}
                        type="button"
                      >
                        {isGeneratingInvite ? "生成中..." : "生成邀请码"}
                      </button>
                    </div>
                    {latestInviteCode ? (
                      <div className="list-item">
                        <strong className="mono">{latestInviteCode.code}</strong>
                        <span>过期时间：{formatDateTime(latestInviteCode.expires_at)}</span>
                      </div>
                    ) : null}
                    <label className="label">
                      抽帧频率
                      <div className="button-row">
                        <input
                          className="input"
                          min={1}
                          onChange={(event) =>
                            setSettings((current) => {
                              const nextSeconds = displayValueToIntervalSeconds(Number(event.target.value), intervalUnit);
                              return {
                                ...current,
                                frame_interval_seconds: nextSeconds,
                                frame_interval_minutes: Math.max(1, Math.ceil(nextSeconds / 60))
                              };
                            })
                          }
                          type="number"
                          value={intervalSecondsToDisplayValue(settings.frame_interval_seconds, intervalUnit)}
                        />
                        <select
                          className="input"
                          onChange={(event) => {
                            const nextUnit = event.target.value as IntervalUnit;
                            const currentDisplayValue = intervalSecondsToDisplayValue(
                              settings.frame_interval_seconds,
                              intervalUnit
                            );
                            const nextSeconds = displayValueToIntervalSeconds(currentDisplayValue, nextUnit);
                            setIntervalUnit(nextUnit);
                            setSettings((current) => ({
                              ...current,
                              frame_interval_seconds: nextSeconds,
                              frame_interval_minutes: Math.max(1, Math.ceil(nextSeconds / 60))
                            }));
                          }}
                          value={intervalUnit}
                        >
                          {intervalUnitOptions.map((item) => (
                            <option key={item.value} value={item.value}>
                              {item.label}
                            </option>
                          ))}
                        </select>
                      </div>
                    </label>
                    <button
                      className="button button-secondary"
                      disabled={isSavingSettings}
                      onClick={() => void handleSaveSettings()}
                      type="button"
                    >
                      {isSavingSettings ? "保存中..." : "保存设置"}
                    </button>
                  </div>
                </section>
              ) : null}
            </section>

            <section className="panel-grid">
              <section className="panel">
                <div className="form-grid">
                  <div>
                    <h2>{isAdmin ? "学生日报" : "我的每日计划"}</h2>
                    <p>{isAdmin ? "查看所选学生的目标、日报、生成总结和反馈。" : "保存当前课题组的今日目标和每日学习记录。"}</p>
                  </div>
                  <label className="label">
                    日期
                    <input
                      className="input"
                      onChange={(event) => setReportDate(event.target.value)}
                      type="date"
                      value={reportDate}
                    />
                  </label>

                  {!isAdmin ? (
                    <>
                      <label className="label">
                        今日主要目标
                        <textarea
                          className="input"
                          onChange={(event) => setDailyGoalForm((current) => ({ ...current, main_goal: event.target.value }))}
                          rows={3}
                          value={dailyGoalForm.main_goal}
                        />
                      </label>
                      <label className="label">
                        计划任务
                        <textarea
                          className="input"
                          onChange={(event) => setDailyGoalForm((current) => ({ ...current, planned_tasks: event.target.value }))}
                          rows={3}
                          value={dailyGoalForm.planned_tasks}
                        />
                      </label>
                      <label className="label">
                        预期困难
                        <textarea
                          className="input"
                          onChange={(event) => setDailyGoalForm((current) => ({ ...current, expected_challenges: event.target.value }))}
                          rows={3}
                          value={dailyGoalForm.expected_challenges}
                        />
                      </label>
                      <label className="checkbox-row">
                        <input
                          checked={dailyGoalForm.needs_mentor_help}
                          onChange={(event) => setDailyGoalForm((current) => ({ ...current, needs_mentor_help: event.target.checked }))}
                          type="checkbox"
                        />
                        今天需要导师帮助
                      </label>
                      <button
                        className="button button-secondary"
                        disabled={isSavingDailyGoal}
                        onClick={() => void handleSaveDailyGoal()}
                        type="button"
                      >
                        {isSavingDailyGoal ? "保存中..." : "保存今日目标"}
                      </button>
                    </>
                  ) : (
                    <div className="list">
                      <div className="list-item">
                        <strong>今日目标</strong>
                        <span>{dailyDetail?.goal?.main_goal ?? "尚未提交目标。"}</span>
                        <span className="note">{dailyDetail?.goal?.planned_tasks ?? ""}</span>
                      </div>
                      <div className="list-item">
                        <strong>每日报告</strong>
                        <span>{dailyDetail?.report?.completed_work ?? "尚未提交日报。"}</span>
                        <span className="note">{dailyDetail?.report?.problems ?? ""}</span>
                      </div>
                    </div>
                  )}
                </div>
              </section>

              <section className="panel">
                <div className="form-grid">
                  <div>
                    <h2>{isAdmin ? "导师反馈" : "每日报告"}</h2>
                    <p>{isAdmin ? "为所选学生的日报填写反馈。" : "记录完成事项、阻塞问题和明日计划。"}</p>
                  </div>

                  {!isAdmin ? (
                    <>
                      <label className="label">
                        完成事项
                        <textarea
                          className="input"
                          onChange={(event) => setDailyReportForm((current) => ({ ...current, completed_work: event.target.value }))}
                          rows={4}
                          value={dailyReportForm.completed_work}
                        />
                      </label>
                      <label className="label">
                        问题和阻塞
                        <textarea
                          className="input"
                          onChange={(event) => setDailyReportForm((current) => ({ ...current, problems: event.target.value }))}
                          rows={3}
                          value={dailyReportForm.problems}
                        />
                      </label>
                      <label className="label">
                        明日计划
                        <textarea
                          className="input"
                          onChange={(event) => setDailyReportForm((current) => ({ ...current, next_plan: event.target.value }))}
                          rows={3}
                          value={dailyReportForm.next_plan}
                        />
                      </label>
                      <label className="checkbox-row">
                        <input
                          checked={dailyReportForm.needs_mentor_help}
                          onChange={(event) => setDailyReportForm((current) => ({ ...current, needs_mentor_help: event.target.checked }))}
                          type="checkbox"
                        />
                        需要导师帮助
                      </label>
                      <button
                        className="button button-primary"
                        disabled={isSavingDailyReport}
                        onClick={() => void handleSaveDailyReport()}
                        type="button"
                      >
                        {isSavingDailyReport ? "保存中..." : "保存日报"}
                      </button>
                    </>
                  ) : (
                    <>
                      <label className="label">
                        反馈内容
                        <textarea
                          className="input"
                          onChange={(event) => setFeedbackForm((current) => ({ ...current, content: event.target.value }))}
                          rows={4}
                          value={feedbackForm.content}
                        />
                      </label>
                      <label className="label">
                        状态
                        <select
                          className="input"
                          onChange={(event) => setFeedbackForm((current) => ({ ...current, status_mark: event.target.value as MentorFeedbackInput["status_mark"] }))}
                          value={feedbackForm.status_mark}
                        >
                          <option value="normal">正常</option>
                          <option value="needs_attention">需要关注</option>
                          <option value="needs_revision">需要修改</option>
                          <option value="needs_meeting">需要会议</option>
                          <option value="resolved">已解决</option>
                        </select>
                      </label>
                      <label className="label">
                        下一步
                        <textarea
                          className="input"
                          onChange={(event) => setFeedbackForm((current) => ({ ...current, next_step: event.target.value }))}
                          rows={3}
                          value={feedbackForm.next_step}
                        />
                      </label>
                      <button
                        className="button button-primary"
                        disabled={isSavingFeedback || selectedMemberId === null}
                        onClick={() => void handleCreateFeedback()}
                        type="button"
                      >
                        {isSavingFeedback ? "保存中..." : "保存反馈"}
                      </button>
                    </>
                  )}
                </div>
              </section>
            </section>

            <section className="panel">
              <div className="form-grid">
                <div>
                  <h2>当日依据</h2>
                  <p>所选日期的生成总结和导师反馈。</p>
                </div>
                <div className="list">
                  {(dailyDetail?.hourly_summaries ?? []).map((summary) => (
                    <div className="list-item" key={summary.id}>
                      <strong>{formatDateTime(summary.hour_start)}</strong>
                      <span>{summary.summary_text}</span>
                    </div>
                  ))}
                  {dailyDetail?.hourly_summaries.length === 0 ? <div className="note">该日期暂无小时总结。</div> : null}
                  {(dailyDetail?.feedback ?? []).map((feedback) => (
                    <div className="list-item" key={feedback.id}>
                      <strong>{feedback.status_mark}</strong>
                      <span>{feedback.content}</span>
                      <span className="note">{feedback.next_step}</span>
                    </div>
                  ))}
                  {dailyDetail?.feedback.length === 0 ? <div className="note">该日期暂无导师反馈。</div> : null}
                </div>
              </div>
            </section>

            {isAdmin ? (
              <section className="split">
                <section className="panel">
                  <div className="form-grid">
                    <div>
                      <h2>成员列表</h2>
                      <p>可查看成员角色、是否正在共享以及最近总结。</p>
                    </div>
                    <div className="list">
                      {members.map((member) => (
                        <div className="list-item" key={member.user_id}>
                          <strong>{member.name}</strong>
                          <span>{member.email}</span>
                          <span className={member.active_session ? "pill" : "pill pill-warning"}>
                            {member.active_session ? "共享中" : "未共享"}
                          </span>
                          <span>角色：{roleLabel(member.role)}</span>
                          <span>开始时间：{formatDateTime(member.active_session?.started_at ?? null)}</span>
                          <span className="note">
                            最近总结：{member.latest_summary ?? "暂无小时级总结"}
                          </span>
                          <button
                            className="button button-secondary"
                            onClick={() => setSelectedMemberId(member.user_id)}
                            type="button"
                          >
                            查看总结
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                </section>

                <section className="panel">
                  <div className="form-grid">
                    <div>
                      <h2>总结查看</h2>
                      <p>
              当前对象：{selectedMember ? `${selectedMember.name}（${selectedMember.email}）` : "未选择学生"}
                      </p>
                    </div>
                    <label className="label">
                      按日期筛选
                      <input
                        className="input"
                        onChange={(event) => setDateFilter(event.target.value)}
                        type="date"
                        value={dateFilter}
                      />
                    </label>
                    <div className="list">
                      {visibleSummaries.length === 0 ? <div className="note">暂无符合条件的小时级总结。</div> : null}
                      {visibleSummaries.map((summary) => (
                        <div className="list-item" key={summary.id}>
                          <strong>{formatDateTime(summary.hour_start)}</strong>
                          <span>{summary.summary_text}</span>
                          <span className="note">帧数：{summary.frame_count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </section>
              </section>
            ) : (
              <section className="panel">
                <div className="form-grid">
                  <div>
                    <h2>我的历史总结</h2>
              <p>学生只能查看自己的小时级总结。</p>
                  </div>
                  <label className="label">
                    按日期筛选
                    <input
                      className="input"
                      onChange={(event) => setDateFilter(event.target.value)}
                      type="date"
                      value={dateFilter}
                    />
                  </label>
                  <div className="list">
                    {visibleSummaries.length === 0 ? <div className="note">暂无符合条件的小时级总结。</div> : null}
                    {visibleSummaries.map((summary) => (
                      <div className="list-item" key={summary.id}>
                        <strong>{formatDateTime(summary.hour_start)}</strong>
                        <span>{summary.summary_text}</span>
                        <span className="note">帧数：{summary.frame_count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </section>
            )}
          </>
        ) : null}
      </div>
      <video ref={videoRef} playsInline style={{ display: "none" }} />
    </main>
  );
}
