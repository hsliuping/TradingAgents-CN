# ============================================================================
# Fast Install Dependencies for Portable Version
# ============================================================================
# 快速安装便携版的所有依赖包（使用国内镜像源）
# ============================================================================

param(
    [string]$PortableDir = ""
)

$ErrorActionPreference = "Stop"

# Determine portable directory
if (-not $PortableDir) {
    $root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $PortableDir = Join-Path $root "release\TradingAgentsCN-portable"
}

if (-not (Test-Path $PortableDir)) {
    Write-Host "❌ Portable directory not found: $PortableDir" -ForegroundColor Red
    exit 1
}

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Fast Install Dependencies" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

$pythonExe = Join-Path $PortableDir "vendors\python\python.exe"
$requirementsFile = Join-Path $PortableDir "requirements.txt"

if (-not (Test-Path $pythonExe)) {
    Write-Host "❌ Python executable not found: $pythonExe" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $requirementsFile)) {
    Write-Host "❌ requirements.txt not found: $requirementsFile" -ForegroundColor Red
    exit 1
}

# Check pip
Write-Host "📋 Checking pip..." -ForegroundColor Yellow
try {
    $pipVersion = & $pythonExe -m pip --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ pip is not available" -ForegroundColor Red
        Write-Host "Error: $pipVersion" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ pip is available: $pipVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to check pip: $_" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Try multiple mirrors (with progress)
$pipMirrors = @(
    @{Name="Aliyun (阿里云)"; Args=@("-i", "https://mirrors.aliyun.com/pypi/simple/", "--trusted-host", "mirrors.aliyun.com")},
    @{Name="Tsinghua (清华)"; Args=@("-i", "https://pypi.tuna.tsinghua.edu.cn/simple", "--trusted-host", "pypi.tuna.tsinghua.edu.cn")},
    @{Name="Douban (豆瓣)"; Args=@("-i", "https://pypi.douban.com/simple/", "--trusted-host", "pypi.douban.com")},
    @{Name="Default (默认)"; Args=@()}
)

Write-Host "📦 Installing dependencies from requirements.txt..." -ForegroundColor Yellow
Write-Host "  Requirements file: $requirementsFile" -ForegroundColor Gray
Write-Host "  This may take 5-10 minutes, please wait..." -ForegroundColor Gray
Write-Host ""

$installed = $false
foreach ($mirror in $pipMirrors) {
    Write-Host "🔄 Trying $($mirror.Name) mirror..." -ForegroundColor Cyan
    
    try {
        $installArgs = @("-r", $requirementsFile, "--no-warn-script-location", "--upgrade") + $mirror.Args
        
        # 🔥 显示实时输出，不要隐藏
        Write-Host "  Command: pip install -r requirements.txt $($mirror.Args -join ' ')" -ForegroundColor DarkGray
        Write-Host ""
        
        # 执行安装，显示输出
        & $pythonExe -m pip install @installArgs
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "✅ All dependencies installed successfully using $($mirror.Name) mirror!" -ForegroundColor Green
            $installed = $true
            break
        } else {
            Write-Host ""
            Write-Host "⚠️ $($mirror.Name) mirror failed (exit code: $LASTEXITCODE)" -ForegroundColor Yellow
            Write-Host "  Trying next mirror..." -ForegroundColor Gray
            Write-Host ""
        }
    } catch {
        Write-Host ""
        Write-Host "⚠️ $($mirror.Name) mirror error: $_" -ForegroundColor Yellow
        Write-Host "  Trying next mirror..." -ForegroundColor Gray
        Write-Host ""
    }
}

if (-not $installed) {
    Write-Host ""
    Write-Host "❌ All mirrors failed to install dependencies" -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 Manual installation:" -ForegroundColor Yellow
    Write-Host "  cd $PortableDir\vendors\python" -ForegroundColor Cyan
    Write-Host "  .\python.exe -m pip install -r ..\..\requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com" -ForegroundColor Cyan
    exit 1
}

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "✅ Installation completed!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# Verify installation
Write-Host "📋 Verifying installation..." -ForegroundColor Yellow
$packageCount = (& $pythonExe -m pip list 2>&1 | Measure-Object -Line).Lines - 2
Write-Host "  Installed packages: $packageCount" -ForegroundColor Green
Write-Host ""

exit 0
