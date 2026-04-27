"use client";

// Login and registration form that restores a prior session and routes users to the matching workspace.
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { clearToken, fetchMe, login, register, setToken } from "../lib/api";

type AuthMode = "login" | "register";

export function LoginForm() {
  const router = useRouter();
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("admin@example.com");
  const [name, setName] = useState("管理员");
  const [password, setPassword] = useState("secret123");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function routeAfterAuth() {
    const user = await fetchMe();
    router.replace(user.is_admin ? "/admin" : "/research-groups");
  }

  useEffect(() => {
    async function restore() {
      try {
        await fetchMe();
        await routeAfterAuth();
      } catch {
        clearToken();
      }
    }

    void restore();
  }, [router]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");

    try {
      const result =
        mode === "login"
          ? await login(email, password)
          : await register(email, name, password);
      setToken(result.access_token);
      await routeAfterAuth();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "认证失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel">
      <div className="form-grid">
        <div>
          <div className="button-row">
            <button
              className={mode === "login" ? "button button-primary" : "button button-secondary"}
              onClick={() => setMode("login")}
              type="button"
            >
              登录
            </button>
            <button
              className={mode === "register" ? "button button-primary" : "button button-secondary"}
              onClick={() => setMode("register")}
              type="button"
            >
              注册
            </button>
          </div>
          <h2>{mode === "login" ? "进入课题组工作台" : "创建账号"}</h2>
          <p>
            新版 MVP 以课题组为中心。账号登录后先进入“我的课题组”，再选择课题组开始共享、邀请学生或查看总结。
          </p>
        </div>
        <form className="form-grid" onSubmit={onSubmit}>
          {mode === "register" ? (
            <label className="label">
              姓名
              <input
                className="input"
                onChange={(event) => setName(event.target.value)}
                placeholder="张三"
                value={name}
              />
            </label>
          ) : null}
          <label className="label">
            邮箱
            <input
              className="input"
              onChange={(event) => setEmail(event.target.value)}
              placeholder="name@example.com"
              value={email}
            />
          </label>
          <label className="label">
            密码
            <input
              className="input"
              onChange={(event) => setPassword(event.target.value)}
              placeholder="secret123"
              type="password"
              value={password}
            />
          </label>
          {error ? <div className="error">{error}</div> : null}
          <div className="button-row">
            <button className="button button-primary" disabled={loading} type="submit">
              {loading ? "提交中..." : mode === "login" ? "登录" : "注册并进入"}
            </button>
            <button
              className="button button-secondary"
              onClick={() => {
                setMode("register");
                setName("管理员");
                setEmail("admin@example.com");
                setPassword("secret123");
              }}
              type="button"
            >
              填充示例
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
