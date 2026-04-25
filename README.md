# ScreenPulse

ScreenPulse 是一个面向员工屏幕共享分析的网页端 MVP：员工主动发起整屏共享，浏览器按频率抓帧上传，后端完成截图识别和小时级摘要，管理员只查看状态与摘要，不查看完整录屏。

## 技术栈

- 前端：Next.js + TypeScript
- 后端：FastAPI + SQLAlchemy + SQLite
- 多模态分析：兼容 OpenAI 风格 `/chat/completions` 接口
- 部署：Docker Compose

## 当前实现边界

- 已实现：员工登录、开始/停止共享、定时抓帧上传、会话管理、识别结果存储、小时摘要、管理员配置抽帧频率、管理员查看历史
- 已实现：LiveKit token 签发接口
- 未把 LiveKit Egress 作为主链路。MVP 主链路是浏览器本地抓帧上传，这样能满足你的验收标准并显著降低复杂度
- 不保存完整录屏，只保留截图和摘要

## 默认账号

- 管理员：`admin / admin123`
- 员工：`employee / employee123`

## 本地运行

### 1. 推荐：一键启动

```powershell
.\scripts\start-dev.ps1
```

默认会启动：

- 前端：[http://localhost:3001](http://localhost:3001)
- 后端 API：[http://localhost:8011/docs](http://localhost:8011/docs)

脚本会把当前运行状态保存到 `.codex-run/dev-state.json`，并把日志写到 `.codex-run/*.log`。停止服务可执行：

```powershell
.\scripts\stop-dev.ps1
```

### 2. 配置环境变量

复制根目录 `.env.example` 为 `.env`，至少确认以下配置：

- `NEXT_PUBLIC_API_BASE_URL`
- `SCREENPULSE_SECRET_KEY`
- `SCREENPULSE_MODEL_API_BASE_URL`
- `SCREENPULSE_VISION_MODEL`
- `SCREENPULSE_SUMMARY_MODEL`

如果不配置模型接口，系统仍可运行，但截图识别会退化为基础占位说明，无法达到真实识别质量。

### 3. 手动启动后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8011
```

### 4. 手动启动前端

```bash
cd frontend
npm install
npm run dev -- --hostname 127.0.0.1 --port 3001
```

打开 [http://localhost:3001](http://localhost:3001)。

## Docker 启动

```bash
copy .env.example .env
docker compose up --build
```

前端默认在 [http://localhost:3001](http://localhost:3001)，后端 API 在 [http://localhost:8011/docs](http://localhost:8011/docs)。

## 测试

```bash
cd backend
pytest
```

## 关键接口

- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/sessions/current`
- `POST /api/sessions/start`
- `POST /api/sessions/{id}/frames`
- `POST /api/sessions/{id}/stop`
- `GET /api/admin/employees`
- `GET /api/admin/users/{id}/sessions`
- `GET /api/admin/users/{id}/summaries`
- `PUT /api/admin/config`
- `POST /api/sessions/livekit-token`

## 后续迭代建议

- 将 LiveKit 真正接入发布流和 Egress
- 增加后台异步任务队列，避免上传请求阻塞在模型调用上
- 加入组织、告警和更细粒度权限
