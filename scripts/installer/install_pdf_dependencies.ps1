# ============================================================================
# PDF 导出依赖安装脚本
# ============================================================================
# 此脚本用于在 Windows 安装版中自动安装 PDF 导出所需的依赖
# ============================================================================

$ErrorActionPreference = 'Stop'

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  PDF 导出依赖安装" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# 获取 Python 可执行文件路径
$pythonExe = $null
$possiblePaths = @(
    "python.exe",
    "python3.exe",
    "$PSScriptRoot\..\..\runtime\python\python.exe",
    "$PSScriptRoot\..\python.exe"
)

foreach ($path in $possiblePaths) {
    if (Test-Path $path) {
        $pythonExe = $path
        break
    }
    # 尝试从 PATH 查找
    $fullPath = Get-Command $path -ErrorAction SilentlyContinue
    if ($fullPath) {
        $pythonExe = $fullPath.Source
        break
    }
}

if (-not $pythonExe) {
    Write-Host "❌ 未找到 Python 可执行文件" -ForegroundColor Red
    Write-Host "请确保 Python 已正确安装并添加到 PATH" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ 找到 Python: $pythonExe" -ForegroundColor Green
Write-Host ""

# 1. 安装 pdfkit（Python 包）
Write-Host "[1/2] 安装 pdfkit..." -ForegroundColor Cyan
try {
    $result = & $pythonExe -m pip install pdfkit --quiet --disable-pip-version-check
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ pdfkit 安装成功" -ForegroundColor Green
    } else {
        Write-Host "⚠️ pdfkit 安装可能失败，但将继续..." -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️ pdfkit 安装失败: $_" -ForegroundColor Yellow
    Write-Host "   您可以稍后手动运行: pip install pdfkit" -ForegroundColor Gray
}

Write-Host ""

# 2. 检查并安装 wkhtmltopdf
Write-Host "[2/2] 检查 wkhtmltopdf..." -ForegroundColor Cyan

# 检查是否已安装
$wkhtmltopdfInstalled = $false
try {
    $version = & wkhtmltopdf --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ wkhtmltopdf 已安装: $($version[0])" -ForegroundColor Green
        $wkhtmltopdfInstalled = $true
    }
} catch {
    # 未找到，继续安装流程
}

if (-not $wkhtmltopdfInstalled) {
    Write-Host "⚠️ wkhtmltopdf 未安装" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "wkhtmltopdf 需要手动安装:" -ForegroundColor Yellow
    Write-Host "  1. 访问: https://wkhtmltopdf.org/downloads.html" -ForegroundColor Cyan
    Write-Host "  2. 下载 Windows 版本安装包" -ForegroundColor Cyan
    Write-Host "  3. 运行安装程序" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "或者，您可以使用 WeasyPrint（推荐，无需外部工具）:" -ForegroundColor Yellow
    Write-Host "  运行: $pythonExe -m pip install weasyprint" -ForegroundColor Cyan
    Write-Host ""
    
    # 询问是否尝试自动下载（可选）
    $downloadUrl = "https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox-0.12.6.1-3.msvc2015-win64.exe"
    Write-Host "💡 提示: 您可以手动下载并安装 wkhtmltopdf" -ForegroundColor Gray
    Write-Host "   下载地址: $downloadUrl" -ForegroundColor Gray
}

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  安装完成" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📝 说明:" -ForegroundColor Yellow
Write-Host "  - pdfkit: Python 包，已安装" -ForegroundColor White
if ($wkhtmltopdfInstalled) {
    Write-Host "  - wkhtmltopdf: 已安装 ✅" -ForegroundColor Green
} else {
    Write-Host "  - wkhtmltopdf: 需要手动安装 ⚠️" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "💡 替代方案: 使用 WeasyPrint（无需外部工具）" -ForegroundColor Cyan
    Write-Host "   运行: $pythonExe -m pip install weasyprint" -ForegroundColor White
}
Write-Host ""
