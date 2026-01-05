# ============================================================================
# Install NSIS (Nullsoft Scriptable Install System)
# ============================================================================
# 此脚本自动下载并安装NSIS
# ============================================================================

# UTF-8编码设置
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
$OutputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = "Stop"

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Install NSIS" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# 检查是否已安装
# ============================================================================

Write-Host "[1/4] Checking existing installation..." -ForegroundColor Yellow
Write-Host ""

$nsisPath = $null
$possiblePaths = @(
    "${env:ProgramFiles}\NSIS\makensis.exe",
    "${env:ProgramFiles(x86)}\NSIS\makensis.exe"
)

foreach ($path in $possiblePaths) {
    if (Test-Path $path) {
        $nsisPath = $path
        break
    }
}

if ($nsisPath) {
    Write-Host "  ✅ NSIS already installed: $nsisPath" -ForegroundColor Green
    Write-Host ""
    Write-Host "No installation needed!" -ForegroundColor Green
    exit 0
}

Write-Host "  NSIS not found, will install..." -ForegroundColor Gray
Write-Host ""

# ============================================================================
# 下载NSIS
# ============================================================================

Write-Host "[2/4] Downloading NSIS..." -ForegroundColor Yellow
Write-Host ""

$nsisVersion = "3.10"
$nsisUrl = "https://sourceforge.net/projects/nsis/files/NSIS%203/$nsisVersion/nsis-$nsisVersion-setup.exe/download"
$downloadPath = Join-Path $env:TEMP "nsis-$nsisVersion-setup.exe"

Write-Host "  Version: $nsisVersion" -ForegroundColor Gray
Write-Host "  URL: $nsisUrl" -ForegroundColor Gray
Write-Host "  Downloading to: $downloadPath" -ForegroundColor Gray
Write-Host ""

try {
    # 使用Invoke-WebRequest下载
    Write-Host "  Downloading... (this may take a few minutes)" -ForegroundColor Gray
    Invoke-WebRequest -Uri $nsisUrl -OutFile $downloadPath -UseBasicParsing
    
    if (Test-Path $downloadPath) {
        $fileSize = (Get-Item $downloadPath).Length / 1MB
        Write-Host "  ✅ Downloaded successfully ($([math]::Round($fileSize, 2)) MB)" -ForegroundColor Green
    } else {
        throw "Download failed"
    }
} catch {
    Write-Host "  ❌ Download failed: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please download NSIS manually:" -ForegroundColor Yellow
    Write-Host "  1. Visit: https://nsis.sourceforge.io/Download" -ForegroundColor Gray
    Write-Host "  2. Download NSIS 3.x" -ForegroundColor Gray
    Write-Host "  3. Run the installer" -ForegroundColor Gray
    exit 1
}

Write-Host ""

# ============================================================================
# 安装NSIS
# ============================================================================

Write-Host "[3/4] Installing NSIS..." -ForegroundColor Yellow
Write-Host ""

Write-Host "  Running installer..." -ForegroundColor Gray
Write-Host "  Please follow the installation wizard" -ForegroundColor Yellow
Write-Host ""

try {
    # 运行安装程序（静默安装）
    $installArgs = @(
        "/S",  # 静默安装
        "/D=C:\Program Files\NSIS"  # 安装目录
    )
    
    $process = Start-Process -FilePath $downloadPath -ArgumentList $installArgs -Wait -PassThru
    
    if ($process.ExitCode -eq 0) {
        Write-Host "  ✅ Installation completed" -ForegroundColor Green
    } else {
        throw "Installation failed with exit code: $($process.ExitCode)"
    }
} catch {
    Write-Host "  ❌ Installation failed: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install NSIS manually:" -ForegroundColor Yellow
    Write-Host "  1. Run: $downloadPath" -ForegroundColor Gray
    Write-Host "  2. Follow the installation wizard" -ForegroundColor Gray
    Write-Host "  3. Install to default location" -ForegroundColor Gray
    exit 1
}

Write-Host ""

# ============================================================================
# 验证安装
# ============================================================================

Write-Host "[4/4] Verifying installation..." -ForegroundColor Yellow
Write-Host ""

$nsisExe = "C:\Program Files\NSIS\makensis.exe"

if (Test-Path $nsisExe) {
    Write-Host "  ✅ NSIS installed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Installation path: $nsisExe" -ForegroundColor Cyan
    
    # 获取版本信息
    try {
        $versionOutput = & $nsisExe /VERSION 2>&1
        Write-Host "Version: $versionOutput" -ForegroundColor Cyan
    } catch {
        # 忽略版本获取错误
    }
} else {
    Write-Host "  ❌ Verification failed" -ForegroundColor Red
    Write-Host ""
    Write-Host "NSIS executable not found at: $nsisExe" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# 清理下载文件
if (Test-Path $downloadPath) {
    Remove-Item $downloadPath -Force
    Write-Host "  Cleaned up temporary files" -ForegroundColor Gray
}

Write-Host ""

# ============================================================================
# 完成
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Green
Write-Host "  NSIS Installation Completed!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""

Write-Host "Next Steps:" -ForegroundColor White
Write-Host "  1. Run: .\scripts\deployment\build_installer.ps1" -ForegroundColor Gray
Write-Host "  2. This will create a Windows installer (.exe)" -ForegroundColor Gray
Write-Host ""

