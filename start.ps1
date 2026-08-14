<#
.SYNOPSIS
  MarkTheDate one-click launcher (Windows PowerShell 5.1+).

.DESCRIPTION
  - Creates a backend virtual environment and installs dependencies (first run)
  - Copies .env.example to .env (if missing)
  - Starts backend (uvicorn :8000) and frontend (vite :5173) as background jobs
  - Opens the browser to the frontend
  - Cleans up child processes on exit

  NOTE: This script uses ASCII-only output strings to remain compatible with
  Windows PowerShell 5.1, which does NOT honor UTF-8 BOM and decodes .ps1 files
  using the system OEM code page. Chinese comments above are informational and
  do not affect runtime.

.EXAMPLE
  PS> .\start.ps1
#>

$ErrorActionPreference = "Stop"

# Force UTF-8 for console output so any Chinese in dynamic strings prints cleanly.
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    chcp 65001 | Out-Null
} catch {}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$backendDir  = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$venvDir     = Join-Path $backendDir ".venv"
$venvPython  = Join-Path $venvDir "Scripts\python.exe"
$venvUvicorn = Join-Path $venvDir "Scripts\uvicorn.exe"
$frontendUrl = "http://localhost:5173"
$backendUrl  = "http://localhost:8000"

# ---- Output helpers (ASCII-only strings) ----
function Write-Step { param($msg) Write-Host ("[*] " + $msg) -ForegroundColor Cyan }
function Write-Ok   { param($msg) Write-Host ("[+] " + $msg) -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host ("[!] " + $msg) -ForegroundColor Yellow }
function Write-Err  { param($msg) Write-Host ("[x] " + $msg) -ForegroundColor Red }

# ---- Get version string ----
function Get-ToolVersion {
    param($binPath)
    if (-not $binPath) { return "" }
    $out = & $binPath --version 2>$null
    if ($out -is [array]) { return ($out[0] -as [string]) }
    return ($out -as [string])
}

# ---- Parse major version ----
function Get-MajorVersion {
    param($ver)
    if (-not $ver) { return 0 }
    $clean = $ver -replace '[^0-9.]', ''
    if (-not $clean) { return 0 }
    return [int]($clean.Split('.')[0])
}

# ---- Check Python / Node ----
Write-Step "Checking environment..."
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
$node   = (Get-Command node   -ErrorAction SilentlyContinue).Source
$npm    = (Get-Command npm    -ErrorAction SilentlyContinue).Source

if (-not $python) { Write-Err "python not found, please install Python 3.10+"; exit 1 }
if (-not $node)   { Write-Err "node not found, please install Node.js 18+";     exit 1 }
if (-not $npm)    { Write-Err "npm not found, please install Node.js 18+";      exit 1 }

# ---- Version checks ----
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

# ---- Backend virtual environment ----
Write-Step "Preparing backend virtual environment..."
if (-not (Test-Path $venvPython)) {
    Write-Step ("Creating venv at " + $venvDir + " ...")
    & $python -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { Write-Err "Failed to create venv"; exit 1 }
}

if (-not (Test-Path $venvUvicorn)) {
    Write-Step "Installing backend dependencies (slow on first run)..."
    & $venvPython -m pip install --upgrade pip --quiet
    if ($LASTEXITCODE -ne 0) { Write-Err "pip upgrade failed"; exit 1 }
    & $venvPython -m pip install -r (Join-Path $backendDir "requirements.txt") --quiet
    if ($LASTEXITCODE -ne 0) { Write-Err "Failed to install backend deps"; exit 1 }
    Write-Ok "Backend dependencies installed"
} else {
    Write-Ok "Backend dependencies ready"
}

# ---- .env ----
$envExample = Join-Path $backendDir ".env.example"
$envFile    = Join-Path $backendDir ".env"
if (-not (Test-Path $envFile) -and (Test-Path $envExample)) {
    Copy-Item $envExample $envFile
    Write-Warn "Created backend\.env from .env.example, please fill AI key / SMTP"
}

# ---- Frontend dependencies ----
$nodeModules = Join-Path $frontendDir "node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Step "Installing frontend dependencies (slow on first run)..."
    Push-Location $frontendDir
    & npm install --no-audit --no-fund
    Pop-Location
    if ($LASTEXITCODE -ne 0) { Write-Err "Failed to install frontend deps"; exit 1 }
    Write-Ok "Frontend dependencies installed"
} else {
    Write-Ok "Frontend dependencies ready"
}

# ---- Start backend ----
Write-Step ("Starting backend (" + $backendUrl + ") ...")
$backendJob = Start-Job -ScriptBlock {
    param($dir, $exe)
    Set-Location $dir
    & $exe uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
} -ArgumentList $backendDir, $venvUvicorn

# ---- Start frontend ----
Write-Step ("Starting frontend (" + $frontendUrl + ") ...")
$frontendJob = Start-Job -ScriptBlock {
    param($dir)
    Set-Location $dir
    & npm run dev
} -ArgumentList $frontendDir

# ---- Wait for HTTP ready ----
function Wait-Http {
    param($url, $name, $timeoutSec)
    if (-not $timeoutSec) { $timeoutSec = 60 }
    Write-Step ("Waiting for " + $name + " (" + $url + ") ...")
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
            Write-Ok ($name + " ready")
            $ready = $true
            break
        }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) {
        Write-Warn ($name + " not responding in " + $timeoutSec + "s, continuing (check logs)")
    }
    return $ready
}

$backendReady  = Wait-Http -url ($backendUrl + "/docs") -name "backend"
$frontendReady = Wait-Http -url $frontendUrl            -name "frontend"

# ---- Open browser ----
Write-Step "Opening browser..."
try {
    Start-Process $frontendUrl
} catch {
    Write-Warn ("Could not auto-open browser, please visit " + $frontendUrl + " manually")
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " MarkTheDate is running" -ForegroundColor Green
Write-Host ("   Frontend : " + $frontendUrl) -ForegroundColor Green
Write-Host ("   Backend  : " + $backendUrl)  -ForegroundColor Green
Write-Host ("   API docs : " + $backendUrl + "/docs") -ForegroundColor Green
Write-Host " Press Ctrl+C to stop, processes will be cleaned up" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""

# ---- Cleanup on exit ----
$jobs = @($backendJob, $frontendJob)

function Cleanup {
    Write-Host ""
    Write-Step "Stopping backend and frontend..."
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
    Write-Ok "exited"
}

try {
    while ($true) {
        Start-Sleep -Seconds 2
        $alive = $jobs | Where-Object { $_.State -eq 'Running' }
        if (-not $alive) {
            Write-Warn "All child processes exited, script ending"
            break
        }
    }
} finally {
    Cleanup
}