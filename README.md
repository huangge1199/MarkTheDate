# MarkTheDate

> 基于 Markdown 文档的活动日期管理系统

每个活动 = 一个 Markdown 文档，存放在 `backend/data/events/`。
SQLite 仅作索引加速日历查询；不存原文，原文永远以 `.md` 文件为准。

## 功能

- 活动 CRUD（标题、时间、提醒、标签、状态、来源 URL）
- 月历视图，自动渲染跨天活动
- URL 自动抓取（OG / meta + LLM 兜底）
- AI 优化 Markdown（OpenAI 兼容 API / Ollama 可切换）
- 双通道提醒：浏览器通知 + 邮件（SMTP）
- 设置页运行时切换 AI 提供方与 SMTP

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.12 · FastAPI · SQLModel · SQLite · httpx · APScheduler · aiosmtplib |
| 前端 | Vue 3 · TypeScript · Vite · Element Plus · Vditor · dayjs |

## 运行环境

请确保本机已安装以下版本（已通过该组合验证）：

| 依赖 | 最低版本 | 推荐版本 | 说明 |
|------|---------|---------|------|
| Python | 3.10 | **3.12** | 3.10 以下缺少部分 typing 语法支持；后端 Dockerfile 使用 `python:3.12-slim` |
| Node.js | 18 | **20 LTS** 或 **22 LTS** | 前端构建依赖 Node 18+；Vite 6 / Vue 3.5 推荐 20+ |
| npm | 9 | 随 Node 一起 | 若使用 pnpm/yarn 也可，注意锁定文件 |
| 操作系统 | - | Windows 10/11 · macOS 12+ · Deepin 20+ · Ubuntu 22.04+ | 跨平台已通过 `start.ps1` / `start.sh` 适配 |

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

## 目录

```
MarkTheDate/
├── backend/          FastAPI 后端
├── frontend/         Vue3 + TS 前端
├── docs/             规划与架构文档
├── docker-compose.yml
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

## API 文档

启动后端后访问 http://localhost:8000/docs

## 许可

MIT