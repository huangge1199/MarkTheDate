<#
.SYNOPSIS
  MarkTheDate 本地一键启动脚本（Windows PowerShell 5.1+ 兼容）。

.DESCRIPTION
  - 创建后端虚拟环境并安装依赖（首次运行）
  - 复制 .env.example 为 .env（若不存在）
  - 后台启动后端 (uvicorn :8000) 与前端 (vite :5173)
  - 自动打开浏览器到前端页面
  - 在脚本退出时干净关闭两个子进程

.EXAMPLE
  PS> .\start.ps1
#>

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$backendDir  = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$venvDir     = Join-Path $backendDir ".venv"
$venvPython  = Join-Path $venvDir "Scripts\python.exe"
$venvUvicorn = Join-Path $venvDir "Scripts\uvicorn.exe"
$frontendUrl = "http://localhost:5173"
$backendUrl  = "http://localhost:8000"

# ---- 颜色输出 ----
function Write-Step { param($msg) Write-Host ("[*] " + $msg) -ForegroundColor Cyan }
function Write-Ok   { param($msg) Write-Host ("[+] " + $msg) -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host ("[!] " + $msg) -ForegroundColor Yellow }
function Write-Err  { param($msg) Write-Host ("[x] " + $msg) -ForegroundColor Red }

# ---- 获取版本字符串 ----
function Get-ToolVersion {
    param($binPath)
    if (-not $binPath) { return "" }
    $out = & $binPath --version 2>$null
    if ($out -is [array]) { return ($out[0] -as [string]) }
    return ($out -as [string])
}

# ---- 解析主版本号 ----
function Get-MajorVersion {
    param($ver)
    if (-not $ver) { return 0 }
    $clean = $ver -replace '[^0-9.]', ''
    if (-not $clean) { return 0 }
    return [int]($clean.Split('.')[0])
}

# ---- 检查 Python / Node ----
Write-Step "检查环境..."
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
$node   = (Get-Command node   -ErrorAction SilentlyContinue).Source
$npm    = (Get-Command npm    -ErrorAction SilentlyContinue).Source

if (-not $python) { Write-Err "未检测到 python，请先安装 Python 3.10+"; exit 1 }
if (-not $node)   { Write-Err "未检测到 node，请先安装 Node.js 18+";   exit 1 }
if (-not $npm)    { Write-Err "未检测到 npm，请先安装 Node.js 18+";    exit 1 }

# ---- 版本检查 ----
$pyVer = Get-ToolVersion -binPath $python
$pyMaj = Get-MajorVersion -ver $pyVer
$pyMin = & $python -c "import sys;print(sys.version_info.minor)" 2>$null
if (-not $pyMin) { $pyMin = 0 }

if ($pyMaj -lt 3 -or ($pyMaj -eq 3 -and $pyMin -lt 10)) {
    Write-Err ("Python version too old: " + $pyVer + " (need 3.10+)")
    exit 1
}
Write-Ok ("Python : " + $pyVer)

$nodeVer = Get-ToolVersion -binPath $node
$nodeMaj = Get-MajorVersion -ver $nodeVer
if ($nodeMaj -lt 18) {
    Write-Err ("Node version too old: " + $nodeVer + " (need 18+)")
    exit 1
}
Write-Ok ("Node   : " + $nodeVer)
Write-Ok ("npm    : " + (Get-ToolVersion -binPath $npm))

# ---- 后端虚拟环境 ----
Write-Step "准备后端虚拟环境..."
if (-not (Test-Path $venvPython)) {
    Write-Step ("创建虚拟环境 " + $venvDir + " ...")
    & $python -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { Write-Err "创建虚拟环境失败"; exit 1 }
}

if (-not (Test-Path $venvUvicorn)) {
    Write-Step "安装后端依赖（首次会比较慢）..."
    & $venvPython -m pip install --upgrade pip --quiet
    if ($LASTEXITCODE -ne 0) { Write-Err "pip 升级失败"; exit 1 }
    & $venvPython -m pip install -r (Join-Path $backendDir "requirements.txt") --quiet
    if ($LASTEXITCODE -ne 0) { Write-Err "安装后端依赖失败"; exit 1 }
    Write-Ok "后端依赖安装完成"
} else {
    Write-Ok "后端依赖已就绪"
}

# ---- .env ----
$envExample = Join-Path $backendDir ".env.example"
$envFile    = Join-Path $backendDir ".env"
if (-not (Test-Path $envFile) -and (Test-Path $envExample)) {
    Copy-Item $envExample $envFile
    Write-Warn "已生成 backend\.env，请按需填入 AI Key / SMTP 配置"
}

# ---- 前端依赖 ----
$nodeModules = Join-Path $frontendDir "node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Step "安装前端依赖（首次会比较慢）..."
    Push-Location $frontendDir
    & npm install --no-audit --no-fund
    Pop-Location
    if ($LASTEXITCODE -ne 0) { Write-Err "安装前端依赖失败"; exit 1 }
    Write-Ok "前端依赖安装完成"
} else {
    Write-Ok "前端依赖已就绪"
}

# ---- 启动后端 ----
Write-Step ("启动后端 (" + $backendUrl + ") ...")
$backendJob = Start-Job -ScriptBlock {
    param($dir, $exe)
    Set-Location $dir
    & $exe uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
} -ArgumentList $backendDir, $venvUvicorn

# ---- 启动前端 ----
Write-Step ("启动前端 (" + $frontendUrl + ") ...")
$frontendJob = Start-Job -ScriptBlock {
    param($dir)
    Set-Location $dir
    & npm run dev
} -ArgumentList $frontendDir

# ---- 等待服务就绪 ----
function Wait-Http {
    param($url, $name, $timeoutSec)
    if (-not $timeoutSec) { $timeoutSec = 60 }
    Write-Step ("等待 " + $name + " 就绪 (" + $url + ") ...")
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $ready = $false
    while ($sw.Elapsed.TotalSeconds -lt $timeoutSec) {
        $ok = $false
        try {
            $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
            if ($resp.StatusCode -lt 500) { $ok = $true }
        } catch {
            $ok = $false
        }
        if ($ok) {
            Write-Ok ($name + " 已就绪")
            $ready = $true
            break
        }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) {
        Write-Warn ($name + " 在 " + $timeoutSec + " 秒内未响应，脚本将继续 (可查看日志排查)")
    }
    return $ready
}

$backendReady  = Wait-Http -url ($backendUrl + "/docs") -name "后端"
$frontendReady = Wait-Http -url $frontendUrl            -name "前端"

# ---- 打开浏览器 ----
Write-Step "打开浏览器..."
try {
    Start-Process $frontendUrl
} catch {
    Write-Warn ("无法自动打开浏览器，请手动访问 " + $frontendUrl)
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " MarkTheDate 已在运行" -ForegroundColor Green
Write-Host ("   前端: " + $frontendUrl) -ForegroundColor Green
Write-Host ("   后端: " + $backendUrl)  -ForegroundColor Green
Write-Host ("   API 文档: " + $backendUrl + "/docs") -ForegroundColor Green
Write-Host " 按 Ctrl+C 退出，进程将被清理" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""

# ---- 监听 Ctrl+C，清理子进程 ----
$jobs = @($backendJob, $frontendJob)

function Cleanup {
    Write-Host ""
    Write-Step "正在关闭后端与前端进程..."
    foreach ($j in $jobs) {
        if ($j -and $j.State -ne 'Completed') {
            Stop-Job $j -Force -ErrorAction SilentlyContinue
            Remove-Job $j -Force -ErrorAction SilentlyContinue
        }
    }
    $pyProcs = Get-Process python -ErrorAction SilentlyContinue
    foreach ($p in $pyProcs) {
        $cmd = ""
        try { $cmd = $p.CommandLine } catch { $cmd = "" }
        if ($cmd -like '*uvicorn*') {
            try { $p.Kill() } catch {}
        }
    }
    $nodeProcs = Get-Process node -ErrorAction SilentlyContinue
    foreach ($p in $nodeProcs) {
        $cmd = ""
        try { $cmd = $p.CommandLine } catch { $cmd = "" }
        if ($cmd -like '*vite*') {
            try { $p.Kill() } catch {}
        }
    }
    Write-Ok "已退出"
}

try {
    while ($true) {
        Start-Sleep -Seconds 2
        $alive = $jobs | Where-Object { $_.State -eq 'Running' }
        if (-not $alive) {
            Write-Warn "所有子进程已退出，脚本结束"
            break
        }
    }
} finally {
    Cleanup
}