# ScreenPulse

ScreenPulse 是一个面向员工屏幕共享分析的网页端 MVP：员工主动发起整屏共享，浏览器按频率抓帧上传，后端完成截图识别和小时级摘要，管理员通过独立后台查看状态、摘要、截图识别历史并管理团队配置，不保存完整录屏。

## 技术栈

- 前端：Next.js + TypeScript
- 后端：FastAPI + SQLAlchemy + SQLite
- 多模态分析：兼容 OpenAI 风格 `/chat/completions` 接口
- 部署：Docker Compose

## 当前实现边界

- 已实现：员工登录、开始/停止共享、定时抓帧上传、会话管理、识别结果存储、小时摘要、管理员配置抽帧频率、管理员查看历史
- 已实现：独立管理员面板 `/admin`，可查看实时共享状态、小时级总结、邀请码列表、截图识别历史，并可管理成员角色、移除成员、禁用邀请码和删除截图记录
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
- 管理员面板：[http://localhost:3011/admin](http://localhost:3011/admin)，可通过 `npm run dev:admin` 单独启动
- 后端 API：[http://localhost:8011/docs](http://localhost:8011/docs)

脚本会把当前运行状态保存到 `.codex-run/dev-state.json`，并把日志写到 `.codex-run/*.log`。停止服务可执行：

```powershell
.\scripts\stop-dev.ps1
```

### 2. 配置环境变量

复制根目录 `.env.example` 为 `.env`，至少确认以下配置：

- `NEXT_PUBLIC_API_BASE_URL`
- `SCREENPULSE_SECRET_KEY`
- `SCREENPULSE_ADMIN_EMAILS`
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

管理员界面使用单独端口区分普通用户界面：

```bash
cd frontend
npm run dev:admin
```

打开 [http://localhost:3011/admin](http://localhost:3011/admin)。

## Docker 启动

```bash
copy .env.example .env
docker compose up --build
```

前端默认在 [http://localhost:3001](http://localhost:3001)，管理员面板可在 [http://localhost:3011/admin](http://localhost:3011/admin) 单独运行，后端 API 在 [http://localhost:8011/docs](http://localhost:8011/docs)。

## 测试

```bash
cd backend
pytest
```

## API 文档和接口测试

后端启动后，FastAPI 自动生成的接口文档在：

- Swagger UI：[`http://localhost:8011/docs`](http://localhost:8011/docs)
- ReDoc：[`http://localhost:8011/redoc`](http://localhost:8011/redoc)
- OpenAPI JSON：[`http://localhost:8011/openapi.json`](http://localhost:8011/openapi.json)

默认 API 前缀是 `/api`，前端请求基地址由 `NEXT_PUBLIC_API_BASE_URL` 控制，默认是 `http://localhost:8011/api`。接口测试时先调用 `POST /api/auth/login` 或 `POST /api/auth/register` 获取 `access_token`，后续受保护接口使用请求头：

```text
Authorization: Bearer <access_token>
```

后端请求/响应结构以 Swagger UI 和 `backend/app/schemas.py` 为准；前端调用封装和类型在 `frontend/lib/api.ts`。

### 用户界面使用的接口

用户界面入口是 [`http://localhost:3001`](http://localhost:3001)，主要由 `frontend/components/login-form.tsx` 和 `frontend/components/team-workspace.tsx` 调用这些接口：

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /api/teams`
- `POST /api/teams`
- `POST /api/teams/join`
- `GET /api/teams/current`
- `PUT /api/teams/current`
- `GET /api/settings/current`
- `GET /api/sessions/current`
- `POST /api/sessions/start`
- `POST /api/screenshots/upload`
- `POST /api/sessions/stop`
- `GET /api/summaries/my-team`

其中成员列表、创建邀请码、修改团队设置、查看其他成员摘要等接口需要当前用户在该团队内具备管理员权限。

### 管理员界面使用的接口

管理员界面入口是 [`http://localhost:3011/admin`](http://localhost:3011/admin)，主要由 `frontend/components/admin-panel.tsx` 调用这些接口：

- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /api/admin/users`
- `GET /api/admin/teams`
- `GET /api/admin/sessions`
- `GET /api/admin/summaries`
- `GET /api/admin/settings`
- `PUT /api/admin/settings`
- `PUT /api/admin/settings/capture-interval`
- `GET /api/admin/members`
- `POST /api/admin/members`
- `PATCH /api/admin/members/{user_id}`
- `DELETE /api/admin/members/{user_id}`
- `POST /api/admin/invite-codes`
- `GET /api/admin/invite-codes`
- `PATCH /api/admin/invite-codes/{invite_code_id}`
- `GET /api/admin/audit-logs`
- `GET /api/admin/frames`
- `DELETE /api/admin/frames/{frame_id}`
- `GET /api/admin/members/{user_id}/summaries`
- `DELETE /api/admin/summaries/{summary_id}`

## 后续迭代建议

- 将 LiveKit 真正接入发布流和 Egress
- 增加后台异步任务队列，避免上传请求阻塞在模型调用上
- 加入组织、告警和更细粒度权限
