# ScreenPulse

ScreenPulse 是一个面向研究生导师和课题组的科研学习过程管理系统 MVP。

学生主动开始屏幕共享，浏览器按课题组设置的频率抽帧上传；后端保存截图、视觉识别结果和小时级学习总结。学生可以提交今日目标和每日学习记录，导师可以查看课题组内学生状态、学习总结、日报，并进行点评反馈。

系统不保存完整录屏，不保存音频，也不做后台偷偷采集。

## 技术栈

- 前端：Next.js App Router + TypeScript
- 后端：FastAPI + SQLAlchemy + SQLite
- 截图分析：兼容 OpenAI 风格 `/chat/completions` 的多模态接口
- 本地启动：PowerShell 脚本 + Docker Compose

## 当前实现范围

已实现：

- 用户注册、登录、登录状态恢复、退出登录
- 课题组创建、选择当前课题组、邀请码加入课题组
- 课题组内角色：导师对应 `mentor`，学生对应 `student`
- 导师生成邀请码、查看学生、调整抽帧频率、查看学生状态和小时总结
- 学生主动开始/停止整屏共享
- 浏览器本地抽帧上传，后端保存截图、识别结果和小时级总结
- 学生填写今日目标
- 学生填写每日学习记录
- 导师查看学生日报详情并添加点评
- 审计日志记录关键操作
- 全局管理员控制台 `/mentor` 保留用于用户、课题组、截图历史和审计查看
- LiveKit token 签发接口保留为可选能力

暂未实现：

- 周计划、周报、任务/待办
- 研究课题、组会、文献、实验、论文写作进度
- 通知中心、规则化风险提醒
- 原始截图自动过期删除
- 完整录屏、音频采集、后台静默监控

## 核心使用流程

1. 导师注册或登录。
2. 导师创建课题组。
3. 导师生成邀请码并发给学生。
4. 学生注册或登录，使用邀请码加入课题组。
5. 学生填写今日目标。
6. 学生主动开始屏幕共享，系统按频率抽帧并生成小时总结。
7. 学生停止共享后填写每日学习记录。
8. 导师进入课题组工作台，选择学生和日期，查看目标、日报、小时总结。
9. 导师提交点评，学生可以在自己的日报详情中查看反馈。

## 权限边界

- 非课题组学生不能访问课题组数据。
- 学生只能查看和维护自己的目标、日报、总结和反馈。
- 导师只能查看和管理自己课题组内的数据。
- 课题组管理能力由当前课题组 `mentor` 角色决定，不要求用户必须在 `SCREENPULSE_mentor_EMAILS` 中。
- `/mentor/users` 和 `/mentor/teams` 等全局列表能力仍要求全局管理员。
- 所有新增学习过程数据都带 `team_id` 和 `user_id` 边界。

## 本地运行

### 一键启动

```powershell
.\scripts\start-dev.ps1
```

默认启动：

- 前端：[http://localhost:3001](http://localhost:3001)
- 后端 API：[http://localhost:8011/docs](http://localhost:8011/docs)

停止服务：

```powershell
.\scripts\stop-dev.ps1
```

脚本会把运行状态写入 `.codex-run/dev-state.json`，日志写入 `.codex-run/*.log`。

### 手动启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8011
```

### 手动启动前端

```powershell
cd frontend
npm install
npm run dev -- --hostname 127.0.0.1 --port 3001
```

打开 [http://localhost:3001](http://localhost:3001)。

### Docker 启动

```powershell
copy .env.example .env
docker compose up --build
```

## 环境变量

复制根目录 `.env.example` 为 `.env`，至少确认：

- `NEXT_PUBLIC_API_BASE_URL`
- `SCREENPULSE_SECRET_KEY`
- `SCREENPULSE_mentor_EMAILS`
- `SCREENPULSE_MODEL_API_BASE_URL`
- `SCREENPULSE_VISION_MODEL`
- `SCREENPULSE_SUMMARY_MODEL`

如果不配置模型接口，系统仍可运行，但截图识别会退化为基础占位说明。

## 测试和构建

后端测试：

```powershell
cd backend
pytest
```

前端构建：

```powershell
cd frontend
npm run build
```

## API 文档

后端启动后：

- Swagger UI：[http://localhost:8011/docs](http://localhost:8011/docs)
- ReDoc：[http://localhost:8011/redoc](http://localhost:8011/redoc)
- OpenAPI JSON：[http://localhost:8011/openapi.json](http://localhost:8011/openapi.json)

默认 API 前缀是 `/api`，前端请求基地址由 `NEXT_PUBLIC_API_BASE_URL` 控制，默认是 `http://localhost:8011/api`。

受保护接口需要请求头：

```text
Authorization: Bearer <access_token>
```

## 主要接口

用户和课题组：

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /api/research-groups`
- `POST /api/research-groups`
- `POST /api/research-groups/join`
- `GET /api/research-groups/current`
- `PUT /api/research-groups/current`

屏幕共享和总结：

- `GET /api/settings/current`
- `GET /api/sessions/current`
- `POST /api/sessions/start`
- `POST /api/screenshots/upload`
- `POST /api/sessions/stop`
- `GET /api/summaries/my-research-group`
- `GET /api/mentor/students/{user_id}/summaries`

今日目标、日报和导师点评：

- `GET /api/daily-goals/my`
- `PUT /api/daily-goals/my`
- `GET /api/daily-reports/my`
- `GET /api/daily-reports/my/detail`
- `PUT /api/daily-reports/my`
- `GET /api/mentor/students/{user_id}/daily-reports`
- `GET /api/mentor/students/{user_id}/daily-report`
- `POST /api/mentor/students/{user_id}/feedback`

课题组导师管理：

- `GET /api/mentor/settings`
- `PUT /api/mentor/settings`
- `GET /api/mentor/students`
- `POST /api/mentor/students`
- `PATCH /api/mentor/students/{user_id}`
- `DELETE /api/mentor/students/{user_id}`
- `POST /api/mentor/invite-codes`
- `GET /api/mentor/invite-codes`
- `PATCH /api/mentor/invite-codes/{invite_code_id}`
- `GET /api/mentor/audit-logs`
- `GET /api/mentor/frames`

## 后续迭代建议

建议按以下顺序继续扩展：

1. 周计划和周报
2. 任务/待办
3. 学生档案
4. 规则化风险提醒
5. 通知中心
6. 研究课题、组会、文献、实验、论文写作进度
7. 原始截图自动过期删除和更细的数据保留设置
