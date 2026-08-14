#!/usr/bin/env bash
# MarkTheDate 本地一键启动脚本（Linux / macOS / Deepin / WSL 通用）
#
# 功能：
#   - 创建后端虚拟环境并安装依赖（首次）
#   - 复制 .env.example 为 .env（首次）
#   - 后台启动后端 (uvicorn :8000) 与前端 (vite :3000)
#   - 自动打开浏览器到前端页面
#   - Ctrl+C 退出时清理子进程
#
# 用法：./start.sh

set -euo pipefail

# ---- 颜色 ----
if [[ -t 1 ]]; then
  C_CYAN=$'\033[36m'
  C_GREEN=$'\033[32m'
  C_YELLOW=$'\033[33m'
  C_RED=$'\033[31m'
  C_RST=$'\033[0m'
else
  C_CYAN=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_RST=""
fi
step() { echo "${C_CYAN}[*]${C_RST} $*"; }
ok()   { echo "${C_GREEN}[+]${C_RST} $*"; }
warn() { echo "${C_YELLOW}[!]${C_RST} $*"; }
err()  { echo "${C_RED}[x]${C_RST} $*" >&2; }

# ---- 路径 ----
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
VENV_DIR="$BACKEND_DIR/.venv"
VENV_BIN="$VENV_DIR/bin"
PY="$VENV_BIN/python"
UVICORN="$VENV_BIN/uvicorn"
BACKEND_URL="http://localhost:8000"
FRONTEND_URL="http://localhost:3000"

# ---- 检查 Python / Node ----
step "检查环境..."

# 版本号提取（取第一个数字段）
ver_major() {
  local v
  v="$("$1" --version 2>&1 | head -n1)"
  echo "$v" | grep -oE '[0-9]+' | head -n1
}

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  err "未检测到 python/python3，请先安装 Python 3.10+"; exit 1
fi
if ! command -v node >/dev/null 2>&1; then
  err "未检测到 node，请先安装 Node.js 18+"; exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  err "未检测到 npm，请先安装 Node.js 18+"; exit 1
fi

# 选择 python 命令
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  PYTHON_BIN="$(command -v python)"
fi

# ---- 版本号校验 ----
PY_MAJOR="$(ver_major "$PYTHON_BIN")"
NODE_MAJOR="$(ver_major "$(command -v node)")"
if [[ -z "$PY_MAJOR" || "$PY_MAJOR" -lt 3 ]]; then
  err "Python 版本过低（需要 3.10+），当前: $("$PYTHON_BIN" --version 2>&1)"; exit 1
fi
# 精确：3.10+ 需要同时比较主版本+次版本
PY_MINOR="$("$PYTHON_BIN" -c 'import sys;print(sys.version_info.minor)' 2>/dev/null || echo 0)"
if [[ "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 10 ]]; then
  err "Python 版本过低（需要 3.10+），当前: $("$PYTHON_BIN" --version 2>&1)"; exit 1
fi

if [[ -z "$NODE_MAJOR" || "$NODE_MAJOR" -lt 18 ]]; then
  err "Node 版本过低（需要 18+），当前: $(node --version 2>&1)"; exit 1
fi

ok "Python : $("$PYTHON_BIN" --version 2>&1)"
ok "Node   : $(node --version 2>&1)"
ok "npm    : $(npm --version 2>&1)"

# ---- 后端虚拟环境 ----
step "准备后端虚拟环境..."
if [[ ! -x "$PY" ]]; then
  step "创建虚拟环境 $VENV_DIR ..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

if [[ ! -x "$UVICORN" ]]; then
  step "安装后端依赖（首次会比较慢）..."
  "$PY" -m pip install --upgrade pip --quiet
  "$PY" -m pip install -r "$BACKEND_DIR/requirements.txt" --quiet
  ok "后端依赖安装完成"
else
  ok "后端依赖已就绪"
fi

# ---- .env ----
if [[ ! -f "$BACKEND_DIR/.env" && -f "$BACKEND_DIR/.env.example" ]]; then
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
  warn "已生成 backend/.env，请按需填入 AI Key / SMTP 配置"
fi

# ---- 前端依赖 ----
if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  step "安装前端依赖（首次会比较慢）..."
  ( cd "$FRONTEND_DIR" && npm install --no-audit --no-fund )
  ok "前端依赖安装完成"
else
  ok "前端依赖已就绪"
fi

# ---- 启动子进程 ----
LOG_DIR="$ROOT/.run"
mkdir -p "$LOG_DIR"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

step "启动后端 ($BACKEND_URL) ..."
( cd "$BACKEND_DIR" && "$UVICORN" app.main:app --host 0.0.0.0 --port 8000 --reload ) \
  > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

step "启动前端 ($FRONTEND_URL) ..."
( cd "$FRONTEND_DIR" && npm run dev -- --host 0.0.0.0 ) \
  > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

cleanup() {
  echo ""
  step "正在关闭后端与前端进程..."
  # 杀进程组
  kill -TERM "$BACKEND_PID" 2>/dev/null || true
  kill -TERM "$FRONTEND_PID" 2>/dev/null || true
  sleep 1
  kill -KILL "$BACKEND_PID" 2>/dev/null || true
  kill -KILL "$FRONTEND_PID" 2>/dev/null || true
  # 兜底：按端口清理
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti tcp:8000 2>/dev/null | xargs -r kill -KILL 2>/dev/null || true
    lsof -ti tcp:3000 2>/dev/null | xargs -r kill -KILL 2>/dev/null || true
  fi
  ok "已退出"
}
trap cleanup EXIT INT TERM

# ---- 等待服务就绪 ----
wait_http() {
  local url="$1" name="$2" timeout="${3:-60}"
  step "等待 $name 就绪 ($url) ..."
  local i=0
  while (( i < timeout )); do
    if command -v curl >/dev/null 2>&1; then
      if curl -sf -o /dev/null -m 2 "$url"; then
        ok "$name 已就绪"
        return 0
      fi
    else
      # 退化：用 /dev/tcp 探测
      if (echo > /dev/tcp/127.0.0.1/${url##*:}) 2>/dev/null; then
        ok "$name 端口已监听（未做 HTTP 探测）"
        return 0
      fi
    fi
    sleep 1
    i=$((i+1))
  done
  warn "$name 在 ${timeout}s 内未响应，可查看日志：$LOG_DIR"
  return 1
}

wait_http "$BACKEND_URL/docs" "后端" 60 || true
wait_http "$FRONTEND_URL/"    "前端" 60 || true

# ---- 打开浏览器 ----
step "打开浏览器..."
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$FRONTEND_URL" >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then
  open "$FRONTEND_URL" >/dev/null 2>&1 || true
elif command -v wslview >/dev/null 2>&1; then
  wslview "$FRONTEND_URL" >/dev/null 2>&1 || true
else
  warn "未找到 xdg-open / open / wslview，请手动访问 $FRONTEND_URL"
fi

echo ""
echo "${C_GREEN}============================================${C_RST}"
echo "${C_GREEN} MarkTheDate 已在运行${C_RST}"
echo "${C_GREEN}   前端: $FRONTEND_URL${C_RST}"
echo "${C_GREEN}   后端: $BACKEND_URL${C_RST}"
echo "${C_GREEN}   API 文档: $BACKEND_URL/docs${C_RST}"
echo "${C_GREEN} 日志: $LOG_DIR/{backend,frontend}.log${C_RST}"
echo "${C_GREEN} 按 Ctrl+C 退出，进程将被清理${C_RST}"
echo "${C_GREEN}============================================${C_RST}"
echo ""

# 阻塞等待子进程
wait "$BACKEND_PID" "$FRONTEND_PID" || true