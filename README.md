# MarkTheDate

> 基于 Markdown 文档的活动日期管理系统

每个活动 = 一个 Markdown 文档，存放在 `backend/data/events/`。
SQLite 仅作索引加速日历查询；不存原文，原文永远以 `.md` 文件为准。

## 功能特性

### 活动管理

- 活动 CRUD：标题、起止时间、全天/定时、提醒规则、标签、状态、来源 URL、自定义颜色
- 月历视图：自动渲染跨天活动，按月切换浏览
- 活动列表视图：批量浏览、检索、跳转编辑
- Markdown 富文本编辑器（基于 Vditor），支持实时预览

### 智能辅助

- **URL 一键抓取**：粘贴链接自动提取 OG / meta 信息（标题、描述、封面图），失败时使用 LLM 兜底
- **图片自动落地**：抓取或 AI 优化产生的外链图片会下载到本地存储，正文 URL 自动改写为本地路径
- **AI Markdown 优化**：调用 OpenAI 兼容 API 或本地 Ollama，对抓取的原始内容进行结构化重写
- **运行时切换 AI 提供方**：在设置页随时切换 base_url / model / api_key，无需重启

### 提醒系统

- **双通道通知**：浏览器 Web Notification + 邮件 SMTP，可在设置页配置
- **APScheduler 定时扫描**：每分钟扫描待发送邮件，避免重复发送
- **通知去重日志**：每次成功发送的提醒会写入 `notify_log` 表，防止重复打扰
- **定时清理任务**：每 10 分钟清理超过 1 小时的抓取临时 session

### 设置与运维

- 设置页运行时管理 AI 配置、SMTP 配置（保存到 SQLite 设置表）
- CORS 跨域友好配置，开箱即用
- 一键启动脚本（Windows / Linux / macOS / Deepin）
- Docker Compose 一键部署
- 完整 FastAPI 自动文档：`/docs`

## 界面预览

<img src="https://img.huangge1199.cn/mark-the-date/docs/screenshots/calendar.png" alt="月历视图" width="100%" />
<p align="center"><em>月历视图 — 跨天活动自动渲染，按月切换</em></p>

<img src="https://img.huangge1199.cn/mark-the-date/docs/screenshots/events.png" alt="活动列表" width="100%" />
<p align="center"><em>活动列表 — 标题 / 时间 / 标签筛选与编辑入口</em></p>

<img src="https://img.huangge1199.cn/mark-the-date/docs/screenshots/editor.png" alt="活动编辑器" width="100%" />
<p align="center"><em>活动编辑器 — 元数据 + Vditor Markdown 编辑，支持 URL 一键抓取与 AI 优化</em></p>

<img src="https://img.huangge1199.cn/mark-the-date/docs/screenshots/settings.png" alt="设置页" width="100%" />
<p align="center"><em>设置页 — AI 提供方与 SMTP 运行时切换，保存后立即生效</em></p>

## 技术栈

| 层   | 技术                                                                                                 |
| --- | -------------------------------------------------------------------------------------------------- |
| 后端  | Python 3.12 · FastAPI · SQLModel · SQLite · httpx · selectolax · APScheduler · aiosmtplib · loguru |
| 前端  | Vue 3 · TypeScript · Vite · Vue Router · Element Plus · Vditor · dayjs                             |
| 部署  | Docker · docker-compose · Nginx（前端容器内）                                                             |

## 运行环境

请确保本机已安装以下版本（已通过该组合验证）：

| 依赖      | 最低版本 | 推荐版本                                                   | 说明                                                          |
| ------- | ---- | ------------------------------------------------------ | ----------------------------------------------------------- |
| Python  | 3.10 | **3.12**                                               | 3.10 以下缺少部分 typing 语法支持；后端 Dockerfile 使用 `python:3.12-slim` |
| Node.js | 18   | **20 LTS** 或 **22 LTS**                                | 前端构建依赖 Node 18+；Vite 6 / Vue 3.5 推荐 20+                     |
| npm     | 9    | 随 Node 一起                                              | 若使用 pnpm/yarn 也可，注意锁定文件                                     |
| 操作系统    | -    | Windows 10/11 · macOS 12+ · Deepin 20+ · Ubuntu 22.04+ | 跨平台已通过 `start.ps1` / `start.sh` 适配                          |

### 版本检查

```bash
python --version    # 或 python3 --version，应输出 Python 3.10+
node --version      # 应输出 v18.x 或更高
npm --version       # 应输出 9.x 或更高
```

若版本不满足，请前往：

- Python：https://www.python.org/downloads/
- Node.js：https://nodejs.org/ （推荐 LTS）

> 在 Windows 上若同时存在多个 Python 版本，可使用 py launcher：`py -3.12 -m venv .venv`

## 目录结构

```
MarkTheDate/
├── backend/              FastAPI 后端
│   ├── app/
│   │   ├── routers/      events / calendar / fetch / ai / notify / settings
│   │   ├── services/     file_manager / ai_service / notifier / storage / fs_ops
│   │   ├── schemas/      Pydantic 数据模型
│   │   ├── models/       SQLModel 数据库模型
│   │   ├── config.py     配置加载（.env）
│   │   ├── database.py   SQLite 初始化与 Session
│   │   └── main.py       FastAPI 入口（含 APScheduler 生命周期）
│   ├── data/
│   │   └── events/       活动 Markdown 文件存储（按年份分目录）
│   ├── .env.example
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/             Vue3 + TS 前端
│   ├── src/
│   │   ├── views/        CalendarView / EventListView / EventEditorView / SettingsView
│   │   ├── components/   AppHeader / MarkdownEditor / NotificationCenter
│   │   ├── composables/  useBrowserNotify
│   │   ├── api/          axios 封装与各模块 API
│   │   └── router/       Vue Router 路由表
│   ├── Dockerfile
│   ├── nginx.conf
│   └── package.json
├── docs/
│   └── architecture.md   系统架构详细说明
├── docker-compose.yml
├── start.ps1             Windows 一键启动脚本
├── start.sh              Linux/macOS 一键启动脚本
├── LICENSE
└── README.md
```

详细架构见 [docs/architecture.md](docs/architecture.md)。

## 快速开始

### 方式一：本地开发（推荐日常用）

一键启动脚本会自动准备虚拟环境、安装依赖、启动前后端并打开浏览器：

- **Windows**（PowerShell 5+）：
  
  ```powershell
  .\start.ps1
  ```
- **Linux / macOS / Deepin / WSL**：
  
  ```bash
  chmod +x start.sh
  ./start.sh
  ```

启动后控制台会显示：

```
============================================
 MarkTheDate 已在运行
   前端: http://localhost:3000
   后端: http://localhost:8000
   API 文档: http://localhost:8000/docs
 按 Ctrl+C 退出，进程将被清理
============================================
```

日志输出到 `.run/backend.log` 和 `.run/frontend.log`（Linux/macOS）。

### 方式二：手动启动

```bash
# 后端
cd backend
python -m venv .venv && . .venv/Scripts/activate  # Windows
pip install -r requirements.txt
cp .env.example .env       # 填入 AI key
uvicorn app.main:app --reload --port 8000

# 前端（新终端）
cd frontend
npm install
npm run dev
# 打开 http://localhost:3000
```

### 方式三：Docker

```bash
cp .env.example .env       # 填入 AI key / SMTP
docker compose up -d --build
# 前端 http://localhost:3000  后端 http://localhost:8000
```

## 数据存储示例

每个活动对应一个 Markdown 文件：

`backend/data/events/2026/2026-08-15_产品发布会.md`

```markdown
---
id: 01HX...
title: 产品发布会
start: 2026-08-15T09:00:00+08:00
end: 2026-08-17T18:00:00+08:00
all_day: false
reminders:
  - { type: browser, offset_minutes: 60 }
  - { type: email, offset_minutes: 1440, email: you@example.com }
tags: [产品, 发布]
status: planned
color: "#3b82f6"
source_url: https://...
created_at: 2026-08-14T10:00:00+08:00
updated_at: 2026-08-14T10:00:00+08:00
---

# 产品发布会

这里是活动的详细 Markdown 描述…
```

活动自带的图片、附件会落在 `backend/data/events/<年>/<slug>_files/` 目录下，正文中通过相对路径引用。

## API 文档

启动后端后访问 http://localhost:8000/docs

主要端点：

- `GET/POST/PUT/DELETE /api/events` — 活动 CRUD
- `GET /api/calendar?year=YYYY&month=MM` — 日历视图聚合
- `POST /api/fetch` — URL 抓取并落图
- `POST /api/ai/optimize` — AI Markdown 优化
- `GET /api/notifications` — 通知日志查询
- `GET/PUT /api/settings` — 运行时配置管理
- `GET /api/event-files/...` — 活动静态资产

## 配置项（.env / 设置页）

| 项                                                         | 说明                     |
| --------------------------------------------------------- | ---------------------- |
| `AI_PROVIDER`                                             | `openai` 或 `ollama`    |
| `AI_BASE_URL`                                             | OpenAI 兼容 API base URL |
| `AI_API_KEY`                                              | API 密钥（可留空走 Ollama）    |
| `AI_MODEL`                                                | 模型名称                   |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` | 邮件发送配置                 |
| `CORS_ORIGINS`                                            | 允许跨域来源，逗号分隔            |

上述配置除 `CORS_ORIGINS` 外都可在 **设置页** 运行时修改并立即生效。

## 许可

[MIT](LICENSE)
