# ============================================================================
# AITrading Electron 打包脚本（PowerShell）
# 
# 用法：
#   .\build.ps1              - 完整打包（构建前端 + 复制dist + 打包exe）
#   .\build.ps1 -Quick       - 快速打包（跳过前端构建）
#   .\build.ps1 -Dev         - 开发模式
#   .\build.ps1 -Clean       - 清理后重新打包
# ============================================================================

param(
    [switch] $Quick,
    [switch] $Dev,
    [switch] $Clean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT_DIR = Split-Path -Parent $SCRIPT_DIR
$FRONTEND_DIR = Join-Path $ROOT_DIR "frontend"
$ELECTRON_DIR = $SCRIPT_DIR

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "         AITrading Electron 打包脚本 v1.0.1" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ---------- 清理 ----------
if ($Clean) {
    Write-Host "[清理] 删除旧的构建产物..." -ForegroundColor Yellow
    $paths = @(
        (Join-Path $FRONTEND_DIR "dist"),
        (Join-Path $ELECTRON_DIR "dist"),
        (Join-Path $ELECTRON_DIR "release")
    )
    foreach ($p in $paths) {
        if (Test-Path $p) { Remove-Item -Recurse -Force $p; Write-Host "  - $p" }
    }
    Write-Host ""
}

# ---------- 开发模式 ----------
if ($Dev) {
    Write-Host ">>> 开发模式：启动 Electron + Vite 开发服务器" -ForegroundColor Green
    Write-Host ""
    Write-Host "[启动] Vite 开发服务器 (端口 3000)..." -ForegroundColor Cyan
    $viteProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/c cd /d `"$FRONTEND_DIR`" && npx vite --host 0.0.0.0 --port 3000" -PassThru -WindowStyle Minimized
    Write-Host "  Vite PID: $($viteProcess.Id)"
    Write-Host "[等待] 等待 Vite 开发服务器就绪..." -ForegroundColor Cyan
    for ($i = 1; $i -le 30; $i++) {
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:3000" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
            if ($r.StatusCode -eq 200) { break }
        } catch { Start-Sleep -Seconds 1 }
    }
    Write-Host "  Vite 已就绪!" -ForegroundColor Green
    Write-Host "[启动] Electron..." -ForegroundColor Cyan
    Push-Location $ELECTRON_DIR
    try { npx electron . } finally { Pop-Location; Stop-Process -Id $viteProcess.Id -Force -ErrorAction SilentlyContinue }
    exit 0
}

# ---------- 步骤 1：构建前端 ----------
if (-not $Quick) {
    Write-Host "[1/4] 构建 Vue 前端项目..." -ForegroundColor Yellow
    Push-Location $FRONTEND_DIR
    try {
        $result = npx vite build 2>&1
        if ($LASTEXITCODE -ne 0) { throw "前端构建失败（退出码: $LASTEXITCODE）" }
    } finally { Pop-Location }
    Write-Host "  前端构建完成!" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "[1/4] 快速模式：跳过前端构建" -ForegroundColor Yellow
    if (-not (Test-Path (Join-Path $FRONTEND_DIR "dist"))) {
        Write-Host "[错误] 找不到 frontend/dist，请先构建前端" -ForegroundColor Red; exit 1
    }
    Write-Host ""
}

# ---------- 步骤 2：复制前端产物到 app-desktop/dist ----------
Write-Host "[2/4] 复制前端构建产物到 app-desktop/dist..." -ForegroundColor Yellow
$srcDist = Join-Path $FRONTEND_DIR "dist"
$dstDist = Join-Path $ELECTRON_DIR "dist"
if (Test-Path $dstDist) { Remove-Item -Recurse -Force $dstDist }
Copy-Item -Recurse -Force $srcDist $dstDist
Write-Host "  复制完成: $dstDist" -ForegroundColor Green
$fileCount = (Get-ChildItem $dstDist -Recurse -File | Measure-Object).Count
Write-Host "  文件数: $fileCount" -ForegroundColor Gray
Write-Host ""

# ---------- 步骤 3：安装依赖 ----------
Write-Host "[3/4] 检查 Electron 依赖..." -ForegroundColor Yellow
Push-Location $ELECTRON_DIR
try {
    if (-not (Test-Path "node_modules\.package-lock.json")) {
        Write-Host "  正在安装依赖..." -ForegroundColor Gray
        npm install 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "依赖安装失败" }
        Write-Host "  依赖安装完成!" -ForegroundColor Green
    } else {
        Write-Host "  依赖已存在，跳过" -ForegroundColor Green
    }
} finally { Pop-Location }
Write-Host ""

# ---------- 步骤 4：打包 ----------
Write-Host "[4/4] 打包 Electron 应用（portable 单文件 exe）..." -ForegroundColor Yellow
Write-Host "  目标: Windows 64-bit portable (.exe)，请耐心等待..." -ForegroundColor Gray
Write-Host ""
Push-Location $ELECTRON_DIR
try {
    npx electron-builder --win portable --x64 2>&1
    if ($LASTEXITCODE -ne 0) { throw "打包失败（退出码: $LASTEXITCODE）" }
} finally { Pop-Location }

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "           打包完成！" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
$releaseDir = Join-Path $ELECTRON_DIR "release"
$exeFiles = Get-ChildItem -Path $releaseDir -Filter "*.exe" -Recurse -ErrorAction SilentlyContinue
foreach ($exe in $exeFiles) {
    Write-Host "  $($exe.FullName)" -ForegroundColor White
    Write-Host "  大小: $([math]::Round($exe.Length/1MB,1)) MB" -ForegroundColor Gray
}
Write-Host ""
Write-Host "  双击 .exe 即可运行，无需安装！" -ForegroundColor Cyan
Write-Host ""