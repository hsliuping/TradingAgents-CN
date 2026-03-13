# ============================================================================
# Verify and Fix Portable Version Dependencies
# ============================================================================
# 验证便携版的 Python 依赖是否完整，并自动修复缺失的包
# ============================================================================

param(
    [string]$PortableDir = "",
    [switch]$Fix  # 自动修复缺失的依赖
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
Write-Host "  Verify Portable Version Dependencies" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

$pythonExe = Join-Path $PortableDir "vendors\python\python.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Host "❌ Python executable not found: $pythonExe" -ForegroundColor Red
    Write-Host "💡 Please run setup_embedded_python.ps1 first" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Python executable found: $pythonExe" -ForegroundColor Green
Write-Host ""

# ============================================================================
# Define Critical Dependencies
# ============================================================================

$criticalPackages = @(
    @{Import="fastapi"; Pip="fastapi"; Description="FastAPI 框架"},
    @{Import="uvicorn"; Pip="uvicorn[standard]"; Description="ASGI 服务器"},
    @{Import="pymongo"; Pip="pymongo"; Description="MongoDB 驱动"},
    @{Import="motor"; Pip="motor"; Description="异步 MongoDB 驱动"},
    @{Import="redis"; Pip="redis"; Description="Redis 客户端"},
    @{Import="langchain"; Pip="langchain"; Description="LangChain 框架"},
    @{Import="openai"; Pip="openai"; Description="OpenAI SDK"},
    @{Import="google.generativeai"; Pip="google-generativeai"; Description="Google Gemini SDK"},
    @{Import="anthropic"; Pip="anthropic"; Description="Anthropic Claude SDK"},
    @{Import="dashscope"; Pip="dashscope"; Description="阿里云通义千问 SDK"},
    @{Import="langchain_openai"; Pip="langchain-openai"; Description="LangChain OpenAI 集成"},
    @{Import="langchain_google_genai"; Pip="langchain-google-genai"; Description="LangChain Google Gemini 集成"},
    @{Import="langchain_anthropic"; Pip="langchain-anthropic"; Description="LangChain Anthropic 集成"},
    @{Import="pydantic"; Pip="pydantic"; Description="数据验证"},
    @{Import="pydantic_settings"; Pip="pydantic-settings"; Description="设置管理"},
    @{Import="akshare"; Pip="akshare"; Description="AKShare 数据源"},
    @{Import="tushare"; Pip="tushare"; Description="Tushare 数据源"},
    @{Import="baostock"; Pip="baostock"; Description="BaoStock 数据源"},
    @{Import="pdfkit"; Pip="pdfkit"; Description="PDF 生成工具（pdfkit）"},
    @{Import="weasyprint"; Pip="weasyprint"; Description="PDF 生成工具（WeasyPrint，推荐）"},
    @{Import="qdrant_client"; Pip="qdrant-client"; Description="Qdrant 向量数据库（推荐，线程安全）"},
    @{Import="chromadb"; Pip="chromadb"; Description="ChromaDB 向量数据库（保留兼容）"},
    @{Import="pystray"; Pip="pystray"; Description="托盘监控（系统托盘图标）"},
    @{Import="PIL"; Pip="Pillow"; Description="托盘监控图标绘制"}
)

# ============================================================================
# Test Imports
# ============================================================================

Write-Host "📋 Testing critical dependencies..." -ForegroundColor Yellow
Write-Host ""

$passedCount = 0
$failedCount = 0
$failedPackages = @()

foreach ($pkg in $criticalPackages) {
    $importName = $pkg.Import
    $pipName = $pkg.Pip
    $description = $pkg.Description

    Write-Host "  Testing: $description ($importName)..." -NoNewline

    # 使用简单的命令执行，忽略警告
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $output = & $pythonExe -c "import $importName" 2>&1
        $exitCode = $LASTEXITCODE
        $ErrorActionPreference = "Stop"

        if ($exitCode -eq 0) {
            Write-Host " ✅" -ForegroundColor Green
            $passedCount++
        } else {
            Write-Host " ❌" -ForegroundColor Red
            # 提取最后一行错误信息
            if ($output) {
                $errorLines = $output | Where-Object { $_ -match "Error|Exception|ModuleNotFoundError" }
                if ($errorLines) {
                    $errorMsg = ($errorLines | Select-Object -Last 1).ToString().Trim()
                    Write-Host "    Error: $errorMsg" -ForegroundColor DarkGray
                }
            }
            $failedCount++
            $failedPackages += @{Import=$importName; Pip=$pipName; Description=$description; Error=$errorMsg}
        }
    } catch {
        Write-Host " ❌" -ForegroundColor Red
        Write-Host "    Error: $_" -ForegroundColor DarkGray
        $failedCount++
        $failedPackages += @{Import=$importName; Pip=$pipName; Description=$description; Error=$_.Exception.Message}
    }
}

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "📊 Test Results:" -ForegroundColor Cyan
Write-Host "  ✅ Passed: $passedCount" -ForegroundColor Green
Write-Host "  ❌ Failed: $failedCount" -ForegroundColor Red
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# Fix Missing Dependencies
# ============================================================================

if ($failedCount -gt 0) {
    Write-Host "❌ Missing Dependencies:" -ForegroundColor Red
    foreach ($pkg in $failedPackages) {
        Write-Host "  - $($pkg.Description) ($($pkg.Pip))" -ForegroundColor Red
    }
    Write-Host ""
    
    if ($Fix) {
        Write-Host "🔧 Attempting to fix missing dependencies..." -ForegroundColor Yellow
        Write-Host ""
        
        $fixedCount = 0
        $fixFailedCount = 0
        
        foreach ($pkg in $failedPackages) {
            Write-Host "  Installing: $($pkg.Pip)..." -ForegroundColor Gray
            
            try {
                $ErrorActionPreference = "Continue"
                $pipOutput = & $pythonExe -m pip install $pkg.Pip --no-warn-script-location 2>&1
                $pipExitCode = $LASTEXITCODE
                if ($pipExitCode -ne 0) {
                    Write-Host "    Retrying with Tsinghua mirror..." -ForegroundColor DarkGray
                    $pipOutput = & $pythonExe -m pip install $pkg.Pip --no-warn-script-location -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn 2>&1
                    $pipExitCode = $LASTEXITCODE
                }
                $ErrorActionPreference = "Stop"
                
                if ($pipExitCode -eq 0) {
                    $ErrorActionPreference = "Continue"
                    $verifyResult = & $pythonExe -c "import $($pkg.Import)" 2>&1
                    $verifyExitCode = $LASTEXITCODE
                    $ErrorActionPreference = "Stop"
                    if ($verifyExitCode -eq 0) {
                        Write-Host "    ✅ Successfully installed and verified" -ForegroundColor Green
                        $fixedCount++
                    } else {
                        Write-Host "    ⚠️ Installed but verification failed" -ForegroundColor Yellow
                        $fixFailedCount++
                    }
                } else {
                    Write-Host "    ❌ Installation failed (exit code: $pipExitCode)" -ForegroundColor Red
                    if ($pipOutput) {
                        $lastErr = (@($pipOutput) | Select-Object -Last 3) -join "`n"
                        Write-Host "    $lastErr" -ForegroundColor DarkGray
                    }
                    $fixFailedCount++
                }
            } catch {
                Write-Host "    ❌ Error: $($_.Exception.Message)" -ForegroundColor Red
                $fixFailedCount++
            }
        }
        
        Write-Host ""
        Write-Host "🔧 Fix Results:" -ForegroundColor Cyan
        Write-Host "  ✅ Fixed: $fixedCount" -ForegroundColor Green
        Write-Host "  ❌ Failed: $fixFailedCount" -ForegroundColor Red
        Write-Host ""

        if ($fixFailedCount -eq 0) {
            Write-Host "✅ All dependencies fixed successfully!" -ForegroundColor Green
            exit 0
        } else {
            Write-Host "⚠️ Some dependencies could not be fixed automatically" -ForegroundColor Yellow
            Write-Host "💡 Please install them manually or check the error messages above" -ForegroundColor Yellow
            exit 1
        }
    } else {
        Write-Host "💡 To automatically fix missing dependencies, run:" -ForegroundColor Yellow
        Write-Host "   .\scripts\deployment\verify_portable_dependencies.ps1 -Fix" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "💡 Or manually install missing packages:" -ForegroundColor Yellow
        Write-Host "   cd $PortableDir\vendors\python" -ForegroundColor Cyan
        foreach ($pkg in $failedPackages) {
            Write-Host "   .\python.exe -m pip install $($pkg.Pip)" -ForegroundColor Cyan
        }
        Write-Host ""
        exit 1
    }
} else {
    Write-Host "✅ All critical dependencies are installed correctly!" -ForegroundColor Green
    Write-Host ""
    Write-Host "💡 The portable version is ready to use." -ForegroundColor Green
    exit 0
}

