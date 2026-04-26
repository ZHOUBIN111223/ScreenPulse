# ScreenPulse MVP 需求整理

## 一、项目目标

做一个**团队屏幕共享总结系统**。

用户可以创建团队，并通过邀请码邀请其他用户加入。
团队成员主动共享整个显示屏后，系统按固定频率抽帧，识别截图内容，并生成小时级总结。
团队管理员可以查看成员共享状态和总结结果。

---

## 二、核心角色

系统只有一种账号：

## 用户

用户在不同团队中可以有不同角色：

| 团队角色   | 权限                      |
| ------ | ----------------------- |
| admin  | 团队创建者或管理员，可以邀请成员、查看成员总结、管理成员、管理截图识别历史 |
| member | 普通成员，可以共享自己的屏幕          |

---

## 三、核心功能

## 1. 用户功能

* 用户注册
* 用户登录
* 查看我的团队
* 创建团队
* 输入邀请码加入团队

---

## 2. 团队功能

* 创建团队
* 查看团队成员
* 生成邀请码
* 查看和禁用邀请码
* 通过邀请码邀请成员
* 设置抽帧频率
* 默认抽帧频率：5 分钟一次

---

## 3. 屏幕共享功能

* 用户选择团队
* 点击开始共享
* 浏览器弹出屏幕共享授权
* 共享范围为整个显示屏
* 用户可以停止共享
* 页面显示当前共享状态
* 页面显示共享开始时间

---

## 4. 分析总结功能

* 系统按团队设置频率抽帧
* 默认 5 分钟一帧
* 使用视觉模型识别截图内容
* 识别当前软件、页面内容、主要活动
* 使用语言模型生成小时级总结
* 保存识别结果和总结结果

---

## 5. 管理查看功能

admin 可以查看：

* 团队成员列表
* 成员当前是否正在共享
* 成员共享开始时间
* 成员小时级总结
* 成员历史总结
* 邀请码列表与使用状态
* 历史截图和视觉识别结果

admin 可以管理：

* 团队抽帧频率
* 邀请码启用 / 禁用状态
* 团队成员添加、移除和角色修改
* 历史截图和对应识别结果删除

member 可以查看：

* 自己的共享状态
* 自己的历史总结

---

## 四、权限规则

* 用户只能访问自己加入的团队
* admin 可以查看本团队所有成员总结
* member 只能查看自己的总结
* admin 可以生成邀请码
* admin 可以查看和禁用邀请码
* member 不能生成邀请码
* admin 可以修改团队抽帧频率
* member 不能修改配置
* admin 可以添加、移除团队成员并修改成员角色
* admin 不能移除或降级团队内最后一个 active admin
* admin 可以查看和删除本团队截图识别历史
* member 不能查看或删除其他成员截图识别历史

---

## 五、核心流程

## 1. 创建团队流程

```text
用户注册 / 登录
→ 创建团队
→ 系统自动把创建者设为 admin
→ 进入团队首页
```

## 2. 邀请成员流程

```text
admin 生成邀请码
→ 复制邀请码发给别人
→ 用户输入邀请码
→ 加入团队
→ 成为 member
```

## 3. 屏幕共享流程

```text
用户进入团队
→ 点击开始共享
→ 确认授权说明
→ 浏览器弹出共享窗口
→ 用户选择整个显示屏
→ 系统开始记录共享状态
→ 后端开始抽帧分析
```

## 4. 总结生成流程

```text
按频率抽帧
→ 视觉模型识别截图
→ 保存识别结果
→ 每小时聚合识别结果
→ 语言模型生成小时级总结
→ admin 查看总结
```

---

## 六、数据存储需求

需要保存：

* 用户信息
* 团队信息
* 团队成员关系
* 邀请码
* 共享会话
* 抽帧截图
* 视觉识别结果
* 小时级总结
* 团队配置
* 操作日志

需要删除：

* 原始媒体流
* 完整录屏内容

规则：

* 不保存完整录屏
* 原始媒体抽帧后删除

---

## 七、主要数据表

## 1. users

```text
id
email
password_hash
name
created_at
updated_at
```

## 2. teams

```text
id
name
created_by_user_id
created_at
updated_at
```

## 3. team_members

```text
id
team_id
user_id
role
status
joined_at
```

role：

```text
admin
member
```

## 4. invite_codes

```text
id
team_id
code
created_by_user_id
expires_at
used_count
max_uses
status
created_at
```

## 5. team_settings

```text
id
team_id
frame_interval_seconds
frame_interval_minutes
created_at
updated_at
```

## 6. screen_sessions

```text
id
team_id
user_id
status
started_at
ended_at
created_at
```

## 7. frame_captures

```text
id
team_id
session_id
user_id
captured_at
image_path
width
height
created_at
```

## 8. vision_results

```text
id
team_id
frame_id
user_id
recognized_content
activity_description
model_name
created_at
```

## 9. hourly_summaries

```text
id
team_id
user_id
hour_start
hour_end
summary_text
frame_count
model_name
created_at
```

## 10. audit_logs

```text
id
team_id
actor_user_id
action
target_type
target_id
created_at
```

---

## 八、页面需求

## 1. 登录 / 注册页

* 注册
* 登录

## 2. 我的团队页

* 显示已加入团队
* 创建团队
* 输入邀请码加入团队

## 3. 团队首页

* 团队名称
* 我的角色
* 当前共享状态
* 开始共享
* 停止共享
* 成员列表入口
* 总结入口

## 4. 成员列表页

admin 可查看：

* 成员姓名
* 邮箱
* 角色
* 是否正在共享
* 共享开始时间
* 查看总结

## 5. 总结页

* 按成员查看总结
* 按日期查看总结
* 查看小时级摘要
* 查看历史摘要

## 6. 团队设置页

admin 可配置：

* 抽帧频率
* 默认 5 分钟一次

## 7. 管理员专属面板

admin 通过独立 `/admin` 页面和单独前端端口访问，便于与普通用户工作台区分。

管理员面板应包含：

* 实时共享状态。
* 全队和单成员小时级总结。
* 团队抽帧设置。
* 邀请码生成、查看、启用和禁用。
* 历史截图与识别结果查看和删除。
* 成员添加、移除和角色修改。

---

## 九、接口需求

## 认证接口

```text
POST /auth/register
POST /auth/login
GET  /auth/me
POST /auth/logout
```

## 团队接口

```text
POST /teams
GET  /teams
GET  /teams/{team_id}
GET  /teams/{team_id}/members
POST /teams/{team_id}/members
PATCH /teams/{team_id}/members/{user_id}
DELETE /teams/{team_id}/members/{user_id}
```

## 邀请码接口

```text
POST /teams/{team_id}/invite-codes
GET  /teams/{team_id}/invite-codes
PATCH /teams/{team_id}/invite-codes/{invite_code_id}
POST /invite-codes/{code}/join
```

## 设置接口

```text
GET   /teams/{team_id}/settings
PATCH /teams/{team_id}/settings
```

## 屏幕共享接口

```text
POST /teams/{team_id}/screen-sessions/start
POST /teams/{team_id}/screen-sessions/{session_id}/stop
GET  /teams/{team_id}/screen-sessions/current
```

## LiveKit 接口

```text
POST /teams/{team_id}/livekit/token
```

## 总结接口

```text
GET /teams/{team_id}/summaries/me
GET /teams/{team_id}/summaries
GET /teams/{team_id}/members/{user_id}/summaries
```

## 截图识别历史接口

```text
GET    /teams/{team_id}/frames
DELETE /teams/{team_id}/frames/{frame_id}
```

---

## 十、非功能需求

* 支持网页端使用
* 支持 Docker 部署
* 支持基础日志
* 支持用户权限校验
* 支持团队数据隔离
* 支持后续替换视觉模型和语言模型
* 不保存完整录屏
* 原始媒体抽帧后删除

---

## 十一、MVP 验收标准

MVP 完成后需要满足：

* 用户可以注册和登录
* 用户可以创建团队
* 用户可以通过邀请码加入团队
* 创建团队的用户自动成为 admin
* admin 可以查看团队成员
* 成员可以开始共享整个显示屏
* 成员可以停止共享
* 系统可以记录共享状态
* 系统可以按 5 分钟一次抽帧
* 系统可以识别截图内容
* 系统可以生成小时级总结
* admin 可以查看团队成员总结
* admin 可以在独立管理员面板查看所有成员实时共享状态
* admin 可以管理邀请码、成员角色和截图识别历史
* member 只能查看自己的总结
* 不保存完整录屏
* 原始媒体抽帧后删除
