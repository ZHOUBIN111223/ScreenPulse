// Landing page that explains the research-group MVP and mounts the shared login and registration form.
import { LoginForm } from "../components/login-form";

export default function HomePage() {
  return (
    <main className="app-shell">
      <div className="page-grid">
        <section className="hero">
          <div className="pill">ScreenPulse MVP</div>
          <h1>围绕课题组屏幕共享、邀请码加入和小时级总结的新 MVP 工作流。</h1>
          <p>
            用户登录后先进入“我的课题组”，再在课题组维度发起整屏共享。系统按课题组配置抽帧识别截图内容，并为学生生成小时级总结。
          </p>
        </section>
        <LoginForm />
      </div>
    </main>
  );
}
