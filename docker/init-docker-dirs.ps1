# ============================================================================
# Docker 目录初始化脚本 (PowerShell)
# ============================================================================
# 用途：创建 docker-compose.compiled.yml 需要的本地目录
# 
# 使用方法：
#   cd docker
#   .\init-docker-dirs.ps1
# ============================================================================

$ErrorActionPreference = "Stop"

# 颜色输出函数
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

# 打印标题
Write-ColorOutput "`n========================================" "Cyan"
Write-ColorOutput "  Docker 目录初始化" "Cyan"
Write-ColorOutput "========================================`n" "Cyan"

# 获取当前目录
$currentDir = Get-Location
Write-ColorOutput "📁 当前目录: $currentDir" "Gray"

# 检查是否在 docker 目录下
if (-not (Test-Path "docker-compose.compiled.yml")) {
    Write-ColorOutput "`n❌ 错误：请在 docker 目录下运行此脚本" "Red"
    Write-ColorOutput "   cd docker" "Yellow"
    Write-ColorOutput "   .\init-docker-dirs.ps1`n" "Yellow"
    exit 1
}

# 需要创建的目录列表
$directories = @(
    "logs",
    "data",
    "runtime",
    "nginx"
)

Write-ColorOutput "`n📂 创建必需的目录...`n" "Yellow"

$createdCount = 0
$existingCount = 0

foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-ColorOutput "  ✅ 创建目录: $dir" "Green"
        $createdCount++
    } else {
        Write-ColorOutput "  📁 目录已存在: $dir" "Gray"
        $existingCount++
    }
}

Write-ColorOutput "`n📊 统计信息:" "Cyan"
Write-ColorOutput "  - 新创建: $createdCount 个目录" "Green"
Write-ColorOutput "  - 已存在: $existingCount 个目录" "Gray"

# 创建 .gitkeep 文件（保持目录结构在 Git 中）
Write-ColorOutput "`n📝 创建 .gitkeep 文件...`n" "Yellow"

$gitkeepDirs = @("logs", "data", "runtime")
foreach ($dir in $gitkeepDirs) {
    $gitkeepFile = Join-Path $dir ".gitkeep"
    if (-not (Test-Path $gitkeepFile)) {
        New-Item -ItemType File -Path $gitkeepFile -Force | Out-Null
        Write-ColorOutput "  ✅ 创建: $gitkeepFile" "Green"
    }
}

Write-ColorOutput "`n✅ 目录初始化完成！`n" "Green"
Write-ColorOutput "📋 下一步操作：" "Cyan"
Write-ColorOutput "  1. 配置环境变量：复制 .env.example 为 .env 并编辑" "White"
Write-ColorOutput "  2. 下载 Nginx 配置：运行 .\deploy.ps1 或手动下载" "White"
Write-ColorOutput "  3. 启动服务：docker-compose -f docker-compose.compiled.yml up -d`n" "White"

