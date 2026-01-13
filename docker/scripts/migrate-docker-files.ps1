# TradingAgents-CN Pro - Docker 文件迁移脚本
# 将所有 Docker 相关文件移动到 docker/ 目录

param(
    [switch]$DryRun,  # 只显示将要执行的操作，不实际执行
    [switch]$Force    # 强制覆盖已存在的文件
)

$ErrorActionPreference = "Stop"

# 颜色输出函数
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

Write-ColorOutput "========================================" "Blue"
Write-ColorOutput "Docker 文件迁移脚本" "Blue"
Write-ColorOutput "========================================" "Blue"
Write-Host ""

if ($DryRun) {
    Write-ColorOutput "⚠️  DRY RUN 模式 - 只显示操作，不实际执行" "Yellow"
    Write-Host ""
}

# 获取项目根目录
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Write-ColorOutput "📁 项目根目录: $ProjectRoot" "Cyan"
Write-Host ""

# 切换到项目根目录
Set-Location $ProjectRoot

# 定义迁移映射
$FileMappings = @(
    @{ Source = "Dockerfile.backend"; Dest = "docker/Dockerfile.backend" },
    @{ Source = "Dockerfile.backend.compiled"; Dest = "docker/Dockerfile.backend.compiled" },
    @{ Source = "Dockerfile.frontend"; Dest = "docker/Dockerfile.frontend" },
    @{ Source = ".dockerignore"; Dest = "docker/.dockerignore" },
    @{ Source = "docker-compose.yml"; Dest = "docker/docker-compose.yml" },
    @{ Source = "docker-compose.hub.nginx.yml"; Dest = "docker/docker-compose.hub.nginx.yml" },
    @{ Source = "docker-compose.hub.nginx.arm.yml"; Dest = "docker/docker-compose.hub.nginx.arm.yml" },
    @{ Source = ".env.docker"; Dest = "docker/.env.docker" },
    @{ Source = "nginx/nginx.conf"; Dest = "docker/nginx/nginx.conf" },
    @{ Source = "nginx/local.nginx.conf"; Dest = "docker/nginx/local.nginx.conf" }
)

# 创建必要的目录
Write-ColorOutput "📂 创建目录..." "Green"
$Directories = @("docker", "docker/nginx", "docker/scripts")
foreach ($Dir in $Directories) {
    if (-not (Test-Path $Dir)) {
        if ($DryRun) {
            Write-ColorOutput "  [DRY RUN] 创建目录: $Dir" "Yellow"
        } else {
            New-Item -ItemType Directory -Path $Dir -Force | Out-Null
            Write-ColorOutput "  ✅ 创建目录: $Dir" "Green"
        }
    } else {
        Write-ColorOutput "  ⏭️  目录已存在: $Dir" "Gray"
    }
}
Write-Host ""

# 移动文件
Write-ColorOutput "📦 移动文件..." "Green"
$MovedCount = 0
$SkippedCount = 0
$ErrorCount = 0

foreach ($Mapping in $FileMappings) {
    $Source = $Mapping.Source
    $Dest = $Mapping.Dest
    
    if (Test-Path $Source) {
        if ((Test-Path $Dest) -and -not $Force) {
            Write-ColorOutput "  ⚠️  目标文件已存在，跳过: $Source -> $Dest" "Yellow"
            $SkippedCount++
        } else {
            if ($DryRun) {
                Write-ColorOutput "  [DRY RUN] 移动: $Source -> $Dest" "Yellow"
                $MovedCount++
            } else {
                try {
                    Move-Item -Path $Source -Destination $Dest -Force:$Force
                    Write-ColorOutput "  ✅ 移动: $Source -> $Dest" "Green"
                    $MovedCount++
                } catch {
                    Write-ColorOutput "  ❌ 错误: $Source -> $Dest : $_" "Red"
                    $ErrorCount++
                }
            }
        }
    } else {
        Write-ColorOutput "  ⏭️  源文件不存在，跳过: $Source" "Gray"
        $SkippedCount++
    }
}
Write-Host ""

# 复制初始化脚本
Write-ColorOutput "📋 复制初始化脚本..." "Green"
$InitScripts = @(
    @{ Source = "scripts/docker-init.ps1"; Dest = "docker/scripts/init.ps1" },
    @{ Source = "scripts/docker-init.sh"; Dest = "docker/scripts/init.sh" }
)

foreach ($Script in $InitScripts) {
    $Source = $Script.Source
    $Dest = $Script.Dest
    
    if (Test-Path $Source) {
        if ($DryRun) {
            Write-ColorOutput "  [DRY RUN] 复制: $Source -> $Dest" "Yellow"
        } else {
            Copy-Item -Path $Source -Destination $Dest -Force
            Write-ColorOutput "  ✅ 复制: $Source -> $Dest" "Green"
        }
    }
}
Write-Host ""

# 显示统计
Write-ColorOutput "========================================" "Blue"
Write-ColorOutput "迁移统计" "Blue"
Write-ColorOutput "========================================" "Blue"
Write-ColorOutput "  移动文件: $MovedCount" "Green"
Write-ColorOutput "  跳过文件: $SkippedCount" "Yellow"
Write-ColorOutput "  错误: $ErrorCount" "Red"
Write-Host ""

if ($DryRun) {
    Write-ColorOutput "⚠️  这是 DRY RUN 模式，没有实际执行任何操作" "Yellow"
    Write-ColorOutput "要实际执行迁移，请运行:" "Cyan"
    Write-ColorOutput "  .\docker\scripts\migrate-docker-files.ps1" "Yellow"
    Write-Host ""
} else {
    if ($ErrorCount -eq 0) {
        Write-ColorOutput "✅ 迁移完成！" "Green"
        Write-Host ""
        Write-ColorOutput "下一步:" "Cyan"
        Write-ColorOutput "  1. 更新构建脚本中的路径引用" "Yellow"
        Write-ColorOutput "  2. 更新文档中的路径引用" "Yellow"
        Write-ColorOutput "  3. 测试 Docker 构建:" "Yellow"
        Write-ColorOutput "     docker-compose -f docker/docker-compose.hub.nginx.yml build" "Gray"
        Write-Host ""
    } else {
        Write-ColorOutput "⚠️  迁移完成，但有 $ErrorCount 个错误" "Yellow"
        Write-ColorOutput "请检查错误信息并手动处理" "Yellow"
        Write-Host ""
    }
}

