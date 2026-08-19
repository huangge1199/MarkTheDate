# MarkTheDate — 让每一个重要日期，都值得被记住

你有没有过这样的经历：

> 周末想去看一场心仪已久的演出，却发现早已开票多日；
> 想在朋友生日当天送上祝福，结果第二天才想起来；
> 想关注某个开源项目的发布日，却总是错过那一天……

日程表里塞满了会议，待办清单永远清不完，而真正重要的"那一天"，却总在不经意间溜走。

**MarkTheDate** 就是为了解决这件事而生的：一个把"活动"作为一等公民、用 Markdown 文档来管理的时间管理系统。

---

## 它是什么？

MarkTheDate 是一款**自托管的活动日期管理系统**。

它的核心理念非常简单：

> **每一个活动 = 一个 Markdown 文件**，存放在 `backend/data/events/` 目录下。

你看到的标题、时间、提醒、标签，都是 Markdown 文件的 YAML front matter；活动详情则是 Markdown 正文。SQLite 只做日历查询的索引，不存原文。**一切以 `.md` 文件为准**——可读、可备份、可版本管理、可在任何编辑器里打开。

换句话说：**你永远不会被某个 SaaS 锁住自己的日程数据**。

---

## 核心特性

### 1. Markdown 原生的活动管理

- 完整的活动 CRUD：标题、起止时间、全天/定时、提醒规则、标签、状态、来源 URL、自定义颜色
- 月历视图：跨天活动自动渲染，按月切换浏览
- 活动列表视图：批量浏览、检索、跳转编辑
- 基于 **Vditor** 的 Markdown 富文本编辑器，支持实时预览

### 2. 智能内容辅助

- **URL 一键抓取**：粘贴链接自动提取 OG / meta 信息（标题、描述、封面图），失败时使用 LLM 兜底
- **图片自动落地**：抓取或 AI 优化产生的外链图片会下载到本地存储，正文 URL 自动改写为本地路径
- **AI Markdown 优化**：调用 OpenAI 兼容 API 或本地 Ollama，对抓取的原始内容进行结构化重写
- **运行时切换 AI 提供方**：在设置页随时切换 `base_url` / `model` / `api_key`，无需重启服务

### 3. 双通道提醒系统

- **浏览器 Web Notification** + **邮件 SMTP**，可在设置页自由配置
- **APScheduler** 每分钟扫描待发送邮件，避免重复发送
- **通知去重日志**：每次成功发送的提醒会写入 `notify_log` 表，防止重复打扰
- 配套的定时清理任务，保证服务长时间运行无负担

### 4. 开箱即用的运维体验

- 设置页运行时管理 AI 配置、SMTP 配置（保存到 SQLite 设置表，立即生效）
- CORS 跨域友好配置
- 一键启动脚本：**Windows / Linux / macOS / Deepin** 全平台覆盖
- Docker Compose 一键部署
- 完整 FastAPI 自动文档：`http://localhost:8000/docs`

---

## 界面预览

### 月历视图

跨天活动自动渲染，按月切换浏览。一个屏幕，所有"那一天"尽在掌握。

<img src="https://img.huangge1199.cn/mark-the-date/docs/screenshots/calendar.png" alt="月历视图" width="100%" />

### 活动列表

标题 / 时间 / 标签筛选与编辑入口，批量浏览一目了然。

<img src="https://img.huangge1199.cn/mark-the-date/docs/screenshots/events.png" alt="活动列表" width="100%" />

### 活动编辑器

元数据 + Vditor Markdown 编辑器双栏布局。**粘贴 URL → 自动抓取 → 一键 AI 优化 → 图片落地**，从一条链接到一份结构化活动记录，只需几秒钟。

<img src="https://img.huangge1199.cn/mark-the-date/docs/screenshots/editor.png" alt="活动编辑器" width="100%" />

### 设置页

AI 提供方与 SMTP 运行时切换，保存后立即生效，再也不必为了改个配置重启服务。

<img src="https://img.huangge1199.cn/mark-the-date/docs/screenshots/settings.png" alt="设置页" width="100%" />

---

## 技术栈

| 层   | 技术                                                                                                 |
| --- | -------------------------------------------------------------------------------------------------- |
| 后端  | Python 3.12 · FastAPI · SQLModel · SQLite · httpx · selectolax · APScheduler · aiosmtplib · loguru |
| 前端  | Vue 3 · TypeScript · Vite · Vue Router · Element Plus · Vditor · dayjs                             |
| 部署  | Docker · docker-compose · Nginx（前端容器内）                                                             |

没有花哨的中间件，没有重型的数据库。**一个 Python 进程 + 一个静态站点**，就是你需要的一切。

---

## 谁适合用它？

- **开发者 / 开源爱好者**：跟踪版本发布、RFC 截止日、社区会议
- **产品 / 运营**：管理运营活动、版本节点、营销日历
- **学生 / 研究者**：跟踪学术会议、论文截稿、答辩安排
- **任何愿意用 Markdown 管理日程的人**：你只需要一个会写 Markdown 的工具人

---

## 快速开始

### 方式一：一键脚本（推荐）

```bash
# Windows
.\start.ps1

# Linux / macOS / Deepin / WSL
chmod +x start.sh
./start.sh
```

### 方式二：Docker

```bash
cp .env.example .env       # 填入 AI key / SMTP
docker compose up -d --build
# 前端 http://localhost:3000  后端 http://localhost:8000
```

启动后访问 `http://localhost:3000`，打开 `http://localhost:8000/docs` 查看完整 API 文档。

---

## 一个活动文件长什么样？

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
---

# 产品发布会

这里是活动的详细 Markdown 描述…
```

活动自带的图片、附件会落在 `backend/data/events/<年>/<slug>_files/` 目录下，正文通过相对路径引用。**所有数据都在你本地，git push 也能备份**。

---

## 为什么选择自托管？

- **数据私有**：你的日程，只属于你
- **长期可读**：`.md` 文件十年后依旧能用任何编辑器打开
- **可版本管理**：扔进 Git，每一次修改都可追溯
- **零依赖**：不需要账号、不需要订阅、不需要看广告

## 灵活的存储后端

活动文件不强制落在本地。MarkTheDate 内置了一套 `Storage` 抽象层，支持在配置中自由切换：

- **本地文件系统**（默认）：`backend/data/events/`，适合单机开发与备份入 Git
- **S3 兼容对象存储**：开箱即用支持 **AWS S3 / MinIO / rustfs / 阿里云 OSS / 腾讯云 COS** 等所有 S3 协议存储

S3 模式下，只需在 `.env` 中填入 `STORAGE_BACKEND=s3` 及 `S3_ENDPOINT_URL` / `S3_ACCESS_KEY` / `S3_SECRET_KEY` / `S3_BUCKET` 等信息即可启用；当对象存储不可达时，系统会自动回落到本地目录，CRUD 不会因为网络抖动而失败。配合可选的 CDN / 公开桶，图片附件还能走预签名 URL 直接对外分发。

> 想要 Git 控版本，就用本地；想要多机共享 / 异地备份，就切到 S3——一套代码，两种姿势。

---

## Star & Fork

如果 MarkTheDate 对你有帮助，欢迎在 GitHub / Gitee 上点个 Star，或者提交 Issue / PR：

- GitHub: <https://github.com/huangge1199/MarkTheDate>
- Gitee: <https://gitee.com/huangge1199_admin/MarkTheDate>

也欢迎在 Issue 区留下你的使用场景、想法与建议——你的每一条反馈都会让这个项目变得更好。

---

## 许可

本项目基于 [MIT](LICENSE) 协议开源，你可以随意使用、修改、商用。

> **MarkTheDate — 让重要的那一天，不再错过。**