# MarkTheDate 项目规划

> 活动日期管理：每个活动 = 一个 Markdown 文档，配日历视图、智能提醒与 AI 优化。

## 一、目录结构

```
MarkTheDate/
├── backend/                          # Python + FastAPI
│   ├── app/
│   │   ├── main.py                   # FastAPI 入口
│   │   ├── config.py                 # 配置管理 (.env)
│   │   ├── database.py               # SQLite 初始化
│   │   ├── models/event.py
│   │   ├── schemas/event.py
│   │   ├── routers/
│   │   │   ├── events.py             # 活动 CRUD
│   │   │   ├── calendar.py           # 日历查询
│   │   │   ├── fetch.py              # URL 抓取
│   │   │   ├── ai.py                 # AI 优化
│   │   │   ├── notify.py             # 提醒检查
│   │   │   └── settings.py
│   │   ├── services/
│   │   │   ├── file_manager.py       # Markdown 文件读写
│   │   │   ├── scraper.py            # 抓取 (meta + LLM 兜底)
│   │   │   ├── ai_service.py         # AI (OpenAI 兼容 / Ollama)
│   │   │   └── notifier.py           # 邮件通知
│   │   └── utils/
│   ├── data/
│   │   ├── events/                   # Markdown 存储
│   │   └── markthedate.db
│   ├── tests/
│   ├── .env.example
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                         # Vue3 + TS + Vite
│   ├── src/
│   │   ├── api/
│   │   ├── views/
│   │   │   ├── CalendarView.vue
│   │   │   ├── EventListView.vue
│   │   │   ├── EventEditorView.vue
│   │   │   └── SettingsView.vue
│   │   ├── components/
│   │   │   ├── CalendarGrid.vue
│   │   │   ├── EventDialog.vue
│   │   │   ├── MarkdownEditor.vue
│   │   │   └── NotificationCenter.vue
│   │   ├── stores/                   # Pinia
│   │   ├── composables/useBrowserNotify.ts
│   │   ├── router/
│   │   └── types/
│   ├── public/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml
└── README.md
```

## 二、技术栈

### 后端
- FastAPI + SQLModel + SQLite
- python-frontmatter 解析 Markdown YAML
- httpx + selectolax 抓取
- openai SDK（兼容 OpenAI / DeepSeek / 硅基流动）
- ollama SDK（本地）
- APScheduler + aiosmtplib

### 前端
- Vue 3 + TypeScript + Vite
- Element Plus（UI）
- Vditor（Markdown 编辑器）
- Pinia / Vue Router 4 / Axios
- FullCalendar（日历，支持跨天）

## 四、存储方案：文件 + SQLite 索引

- Markdown 文件为单一事实源：`data/events/YYYY/YYYY-MM-DD_slug.md`
- YAML front matter 存元数据
- SQLite 仅作索引（id、时间、状态、提醒），加速日历/筛选

### Front matter 示例
```yaml
---
id: 01HX...
title: 产品发布会
start: 2026-08-15T09:00:00+08:00
end: 2026-08-17T18:00:00+08:00
all_day: false
reminders:
  - { type: browser, offset_minutes: 60 }
  - { type: email, offset_minutes: 1440, email: user@example.com }
tags: [产品, 发布]
source_url: https://...
color: "#3b82f6"
status: planned
created_at: 2026-08-14T10:00:00+08:00
updated_at: 2026-08-14T10:00:00+08:00
---
```

## 五、SQLite 索引

```sql
CREATE TABLE events (
    id TEXT PRIMARY KEY,
    file_path TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    start_at TIMESTAMP NOT NULL,
    end_at TIMESTAMP,
    all_day BOOLEAN DEFAULT 0,
    status TEXT DEFAULT 'planned',
    reminders_json TEXT,
    source_url TEXT,
    tags_json TEXT,
    updated_at TIMESTAMP
);
CREATE INDEX idx_events_start ON events(start_at);
CREATE INDEX idx_events_status ON events(status);

CREATE TABLE notify_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT,
    channel TEXT,
    sent_at TIMESTAMP,
    success BOOLEAN
);

CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
```

## 六、API

- `GET/POST/PUT/DELETE /api/events`
- `GET /api/calendar?year=&month=`
- `POST /api/fetch {url}` URL 抓取
- `POST /api/ai/optimize {event_id, instruction?}` AI 优化
- `GET /api/notifications/pending` 待提醒
- `POST /api/notifications/{id}/ack`
- `GET/PUT /api/settings`

## 七、流程

### URL 自动获取
meta 标签解析 → 信息不足 → LLM 兜底 → 返回草稿 → 用户确认 → 写入。

### AI 优化 Markdown
读取 .md → 调 AI（OpenAI 兼容 / Ollama 可切）→ diff 预览 → 确认写入。

### 提醒（双重）
- 前端：轮询 `/api/notifications/pending` + Notification API
- 后端：APScheduler 扫描 → SMTP 发送 → 写日志（24h 内不重复）

## 八、环境变量 `.env.example`

```
AI_PROVIDER=openai
AI_BASE_URL=https://api.openai.com/v1
AI_API_KEY=sk-xxxx
AI_MODEL=gpt-4o-mini
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
SMTP_HOST=
SMTP_PORT=465
SMTP_USER=
SMTP_PASS=
SMTP_FROM=
EVENTS_DIR=./data/events
DB_PATH=./data/markthedate.db
```

## 九、实施步骤

| 阶段 | 内容 |
|------|------|
| P0 | 后端骨架、配置、SQLite |
| P1 | 活动 CRUD（文件 + API） |
| P2 | 前端骨架 + 列表/编辑 |
| P3 | 日历视图（FullCalendar 跨天） |
| P4 | URL 抓取（meta + LLM 兜底） |
| P5 | AI 优化（OpenAI/Ollama 可切） |
| P6 | 浏览器通知 |
| P7 | 邮件通知 |
| P8 | 设置页、Docker、样式打磨 |