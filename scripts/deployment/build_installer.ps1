# ============================================================================
# Build Windows Installer for TradingAgents-CN Pro
# ============================================================================
# 此脚本用于构建Windows安装程序（.exe）
# 需要先安装NSIS: https://nsis.sourceforge.io/Download
# ============================================================================

# UTF-8编码设置
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
$OutputEncoding = [System.Text.Encoding]::UTF8

param(
    [switch]$SkipBuild,
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Build TradingAgents-CN Pro Installer" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# Step 1: 检查NSIS是否安装
# ============================================================================

Write-Host "[1/5] Checking NSIS installation..." -ForegroundColor Yellow
Write-Host ""

$nsisPath = $null
$possiblePaths = @(
    "${env:ProgramFiles}\NSIS\makensis.exe",
    "${env:ProgramFiles(x86)}\NSIS\makensis.exe",
    "C:\Program Files\NSIS\makensis.exe",
    "C:\Program Files (x86)\NSIS\makensis.exe"
)

foreach ($path in $possiblePaths) {
    if (Test-Path $path) {
        $nsisPath = $path
        break
    }
}

if (-not $nsisPath) {
    Write-Host "ERROR: NSIS not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install NSIS from: https://nsis.sourceforge.io/Download" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Installation steps:" -ForegroundColor White
    Write-Host "  1. Download NSIS 3.x from the link above" -ForegroundColor Gray
    Write-Host "  2. Run the installer" -ForegroundColor Gray
    Write-Host "  3. Install to default location (C:\Program Files\NSIS)" -ForegroundColor Gray
    Write-Host "  4. Run this script again" -ForegroundColor Gray
    Write-Host ""
    exit 1
}

Write-Host "  ✅ NSIS found: $nsisPath" -ForegroundColor Green
Write-Host ""

# ============================================================================
# Step 2: 构建Pro版（如果需要）
# ============================================================================

if (-not $SkipBuild) {
    Write-Host "[2/5] Building Pro version..." -ForegroundColor Yellow
    Write-Host ""
    
    $buildScript = Join-Path $PSScriptRoot "build_pro_package.ps1"
    
    if ($Version) {
        & powershell -ExecutionPolicy Bypass -File $buildScript -Version $Version
    } else {
        & powershell -ExecutionPolicy Bypass -File $buildScript
    }
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Pro version build failed" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "  ✅ Pro version built successfully" -ForegroundColor Green
} else {
    Write-Host "[2/5] Skipping Pro version build (using existing files)..." -ForegroundColor Yellow
}

Write-Host ""

# ============================================================================
# Step 3: 准备安装程序资源
# ============================================================================

Write-Host "[3/5] Preparing installer resources..." -ForegroundColor Yellow
Write-Host ""

$installerDir = Join-Path $root "installer"
$portableDir = Join-Path $root "release\TradingAgentsCN-portable"
$licenseFile = Join-Path $root "LICENSE"

# 检查必要文件
if (-not (Test-Path $portableDir)) {
    Write-Host "ERROR: Portable directory not found: $portableDir" -ForegroundColor Red
    Write-Host "Please run build_pro_package.ps1 first" -ForegroundColor Yellow
    exit 1
}

# 创建LICENSE文件（如果不存在）
if (-not (Test-Path $licenseFile)) {
    Write-Host "  Creating LICENSE file..." -ForegroundColor Gray
    @"
MIT License

Copyright (c) 2024 TradingAgents Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"@ | Out-File -FilePath $licenseFile -Encoding UTF8
}

Write-Host "  ✅ Resources prepared" -ForegroundColor Green
Write-Host ""

# ============================================================================
# Step 4: 编译NSIS脚本
# ============================================================================

Write-Host "[4/5] Compiling NSIS script..." -ForegroundColor Yellow
Write-Host ""

$nsiScript = Join-Path $installerDir "installer.nsi"

if (-not (Test-Path $nsiScript)) {
    Write-Host "ERROR: NSIS script not found: $nsiScript" -ForegroundColor Red
    exit 1
}

Write-Host "  NSIS script: $nsiScript" -ForegroundColor Gray
Write-Host "  Compiling..." -ForegroundColor Gray
Write-Host ""

# 运行NSIS编译器
$nsisArgs = @(
    "/V4",  # 详细输出
    $nsiScript
)

$process = Start-Process -FilePath $nsisPath -ArgumentList $nsisArgs -Wait -PassThru -NoNewWindow

if ($process.ExitCode -ne 0) {
    Write-Host "ERROR: NSIS compilation failed with exit code: $($process.ExitCode)" -ForegroundColor Red
    exit 1
}

Write-Host "  ✅ NSIS compilation completed" -ForegroundColor Green
Write-Host ""

# ============================================================================
# Step 5: 验证安装程序
# ============================================================================

Write-Host "[5/5] Verifying installer..." -ForegroundColor Yellow
Write-Host ""

# 读取版本号
$versionFile = Join-Path $root "VERSION"
if (Test-Path $versionFile) {
    $installerVersion = Get-Content $versionFile -Raw
    $installerVersion = $installerVersion.Trim()
} else {
    $installerVersion = "1.0.0-preview"
}

$installerPath = Join-Path $root "release\packages\TradingAgentsCN-Setup-$installerVersion.exe"

if (Test-Path $installerPath) {
    $installerSize = (Get-Item $installerPath).Length
    $installerSizeMB = [math]::Round($installerSize / 1MB, 2)
    
    Write-Host "  ✅ Installer created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Installer Information:" -ForegroundColor White
    Write-Host "  File: TradingAgentsCN-Setup-$installerVersion.exe" -ForegroundColor Cyan
    Write-Host "  Size: $installerSizeMB MB" -ForegroundColor Cyan
    Write-Host "  Path: $installerPath" -ForegroundColor Cyan
} else {
    Write-Host "ERROR: Installer not found at expected location" -ForegroundColor Red
    exit 1
}

Write-Host ""

# ============================================================================
# 完成
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Green
Write-Host "  Installer Build Completed!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""

Write-Host "Next Steps:" -ForegroundColor White
Write-Host "  1. Test the installer on a clean Windows machine" -ForegroundColor Gray
Write-Host "  2. Run the installer: $installerPath" -ForegroundColor Gray
Write-Host "  3. Verify all features work correctly" -ForegroundColor Gray
Write-Host "  4. Distribute to users" -ForegroundColor Gray
Write-Host ""

Write-Host "Installation Features:" -ForegroundColor White
Write-Host "  ✅ Professional installation wizard" -ForegroundColor Green
Write-Host "  ✅ License agreement display" -ForegroundColor Green
Write-Host "  ✅ Custom installation directory" -ForegroundColor Green
Write-Host "  ✅ Start menu shortcuts" -ForegroundColor Green
Write-Host "  ✅ Desktop shortcut" -ForegroundColor Green
Write-Host "  ✅ Complete uninstaller" -ForegroundColor Green
Write-Host ""

