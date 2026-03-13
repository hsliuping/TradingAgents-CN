# ============================================================================
# Sync Code to Portable Release (Pro Version)
# ============================================================================
# 专业版打包脚本 - 排除课程源码和敏感内容
# ============================================================================

param(
    [switch]$SkipDependencies,
    [switch]$DryRun,
    [switch]$Force
)

# 设置控制台和文件编码为UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
$OutputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$portableDir = Join-Path $root "release\TradingAgentsCN-portable"

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Sync Code to Portable Release (Pro Version)" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $portableDir)) {
    Write-Host "Creating portable directory: $portableDir" -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $portableDir -Force | Out-Null
    Write-Host "✅ Directory created" -ForegroundColor Green
}

Write-Host "Source: $root" -ForegroundColor Green
Write-Host "Target: $portableDir" -ForegroundColor Green
Write-Host ""

# ============================================================================
# Define directories and files to sync
# ============================================================================

$syncDirs = @(
    "core",          # 🔥 v2.0 核心代码（必须同步！）
    "app",
    "tradingagents",
    "migrations",
    # "web",         # ❌ 旧版 Web 界面，不再同步
    # "tests",       # ❌ 测试代码，不需要打包
    "examples",
    "prompts",
    "config",
    "install",       # 🔥 包含数据库配置文件
    "releases"       # 🔥 版本发布目录（升级配置 per-version）
)

# 🔥 注意：docs 目录不再完整同步，改为选择性同步

$syncFiles = @(
    "VERSION",           # Version for update check and display
    "BUILD_INFO",        # Build metadata (build_date, git_commit, etc.)
    "requirements.txt",
    "pyproject.toml",  # 🔥 添加 pyproject.toml（包含 weasyprint 依赖）
    "README.md",
    ".env.example",
    "start_api.py",
    "debug_services.ps1"  # MongoDB和Redis诊断脚本
)

$excludePatterns = @(
    "__pycache__",
    "*.pyc",
    "*.pyd",  # 🔥 排除 Cython 编译的扩展（编译时生成）
    "*.pyo",
    ".pytest_cache",
    ".mypy_cache",
    "*.log",
    ".DS_Store",
    "Thumbs.db",
    "node_modules",
    ".git",
    ".vscode",
    ".idea",
    "*.egg-info",
    "dist",
    "build"
)

# 🔥 新增：排除课程源码和敏感内容
$excludeDirs = @(
    "docs\courses\advanced\expanded",  # 排除24节课程扩写内容
    "docs\courses\advanced\ppt",       # 排除PPT源文件
    "docs\design",                     # 排除设计文档
    "docs\email-to-tradingagents-team.txt"  # 排除邮件模板
)

# 🔥 便携版专属文件/目录（不从开发目录同步，保留便携版中的现有内容）
# 注意：.env 不在此列表中，因为开发环境的 .env 包含私密参数（API密钥等）
#       便携版的 .env 应该手动维护或从 .env.example 复制
$portableSpecific = @(
    ".env",           # 🔐 不同步！便携版保留自己的 .env（避免泄露私密参数）
    "data",
    "logs",
    "temp",
    "runtime",
    "vendors",
    # "venv",  # 排除 venv，使用嵌入式 Python
    "frontend",
    "scripts\import_config_and_create_user.py",
    "scripts\init_mongodb_user.py",
    "start_all.ps1",
    "start_services_clean.ps1",
    "stop_all.ps1",
    "README_STARTUP.txt"
)

$allowedPortableRootEntries = @(
    ".env",
    ".env.example",
    "app",
    "BUILD_INFO",
    "config",
    "core",
    "data",
    "debug_services.ps1",
    "docs",
    "examples",
    "frontend",
    "install",
    "logs",
    "migrations",
    "prompts",
    "pyproject.toml",
    "README.md",
    "README_STARTUP.txt",
    "releases",
    "requirements.txt",
    "restart_all.ps1",
    "runtime",
    "scripts",
    "start_all.ps1",
    "start_services_clean.ps1",
    "stop_all.ps1",
    "temp",
    "tradingagents",
    "vendors",
    "VERSION"
)

# 排除大文件和数据目录（安装时创建）
$excludeDataDirs = @(
    "data\mongodb",
    "data\redis",
    "logs",
    "temp"
)

# ============================================================================
# Helper Functions
# ============================================================================

function Test-ShouldExclude {
    param([string]$Path)

    foreach ($pattern in $excludePatterns) {
        if ($Path -like "*$pattern*") {
            return $true
        }
    }
    
    # 🔥 检查是否在排除目录中
    foreach ($excludeDir in $excludeDirs) {
        $normalized = $excludeDir -replace '\\', '/'
        $pathNormalized = $Path -replace '\\', '/'
        if ($pathNormalized -like "*$normalized*") {
            return $true
        }
    }
    
    return $false
}

function Test-IsPortableSpecific {
    param([string]$RelativePath)

    foreach ($specific in $portableSpecific) {
        $normalized = $specific -replace '\\', '/'
        $relNormalized = $RelativePath -replace '\\', '/'

        if ($relNormalized -eq $normalized -or $relNormalized -like "$normalized/*") {
            return $true
        }
    }
    return $false
}

function Copy-WithProgress {
    param(
        [string]$Source,
        [string]$Destination,
        [string]$Description
    )

    if ($DryRun) {
        Write-Host "  [DRY RUN] Will copy: $Description" -ForegroundColor Yellow
        return
    }

    try {
        $destDir = Split-Path -Parent $Destination
        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        }

        Copy-Item -Path $Source -Destination $Destination -Force
        Write-Host "  OK: $Description" -ForegroundColor Green
    } catch {
        Write-Host "  FAILED: $Description - $_" -ForegroundColor Red
    }
}

# ============================================================================
# Start Sync
# ============================================================================

$syncCount = 0
$skipCount = 0

Write-Host "Cleaning stale items in portable root..." -ForegroundColor Yellow
Write-Host ""

Get-ChildItem -Path $portableDir -Force | ForEach-Object {
    if ($allowedPortableRootEntries -contains $_.Name) {
        return
    }

    if ($DryRun) {
        Write-Host "  [DRY RUN] Will remove stale item: $($_.Name)" -ForegroundColor Yellow
        return
    }

    try {
        Remove-Item -Path $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "  🗑️  Removed stale item: $($_.Name)" -ForegroundColor Gray
    } catch {
        Write-Host "  ❌ FAILED to remove stale item: $($_.Name) - $_" -ForegroundColor Red
    }
}

Write-Host ""

Write-Host "Syncing directories..." -ForegroundColor Yellow
Write-Host ""

foreach ($dir in $syncDirs) {
    $sourcePath = Join-Path $root $dir
    $destPath = Join-Path $portableDir $dir

    if (-not (Test-Path $sourcePath)) {
        Write-Host "  SKIP: $dir (not found)" -ForegroundColor Yellow
        continue
    }

    Write-Host "Processing: $dir" -ForegroundColor Cyan

    # 🔥 简化逻辑：直接复制整个目录
    if ($DryRun) {
        Write-Host "  [DRY RUN] Will copy entire directory: $dir" -ForegroundColor Yellow
    } else {
        try {
            # 删除目标目录（如果存在）
            if (Test-Path $destPath) {
                Remove-Item -Path $destPath -Recurse -Force
            }

            # 复制整个目录
            Copy-Item -Path $sourcePath -Destination $destPath -Recurse -Force
            Write-Host "  ✅ Copied entire directory" -ForegroundColor Green

            # 删除 __pycache__ 目录
            $pycacheDirs = Get-ChildItem -Path $destPath -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue
            foreach ($pycacheDir in $pycacheDirs) {
                Remove-Item -Path $pycacheDir.FullName -Recurse -Force
                Write-Host "  🗑️  Removed: $($pycacheDir.FullName.Replace($portableDir, ''))" -ForegroundColor Gray
            }

            # 删除 .pyc 文件
            $pycFiles = Get-ChildItem -Path $destPath -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue
            foreach ($pycFile in $pycFiles) {
                Remove-Item -Path $pycFile.FullName -Force
                Write-Host "  🗑️  Removed: $($pycFile.FullName.Replace($portableDir, ''))" -ForegroundColor Gray
            }

            $syncCount++
        } catch {
            Write-Host "  ❌ FAILED: $dir - $_" -ForegroundColor Red
        }
    }

    Write-Host ""
}

# ============================================================================
# Sync individual files
# ============================================================================

Write-Host "Syncing individual files..." -ForegroundColor Yellow
Write-Host ""

foreach ($file in $syncFiles) {
    $sourcePath = Join-Path $root $file
    $destPath = Join-Path $portableDir $file

    if (Test-Path $sourcePath) {
        Copy-WithProgress -Source $sourcePath -Destination $destPath -Description $file
        $syncCount++
    } else {
        Write-Host "  SKIP: $file (not found)" -ForegroundColor Yellow
    }
}

Write-Host ""

# ============================================================================
# 🔥 同步 docs 目录
# ============================================================================

Write-Host "Syncing docs..." -ForegroundColor Yellow
Write-Host ""

$docsSource = Join-Path $root "docs\release_v2.0"
$docsDest = Join-Path $portableDir "docs"

if (Test-Path $docsSource) {
    if ($DryRun) {
        Write-Host "  [DRY RUN] Will copy release docs directory: docs\\release_v2.0 -> docs" -ForegroundColor Yellow
    } else {
        try {
            # 删除目标目录（如果存在）
            if (Test-Path $docsDest) {
                Remove-Item -Path $docsDest -Recurse -Force
            }

            New-Item -ItemType Directory -Path $docsDest -Force | Out-Null

            # 仅复制面向发布的用户文档
            Copy-Item -Path (Join-Path $docsSource "*") -Destination $docsDest -Recurse -Force
            Write-Host "  ✅ Copied release_v2.0 user docs only" -ForegroundColor Green

            # 删除 __pycache__ 目录
            $pycacheDirs = Get-ChildItem -Path $docsDest -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue
            foreach ($pycacheDir in $pycacheDirs) {
                Remove-Item -Path $pycacheDir.FullName -Recurse -Force
            }

            # 删除 .pyc 文件
            $pycFiles = Get-ChildItem -Path $docsDest -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue
            foreach ($pycFile in $pycFiles) {
                Remove-Item -Path $pycFile.FullName -Force
            }

            $syncCount++
        } catch {
            Write-Host "  ❌ FAILED: docs - $_" -ForegroundColor Red
        }
    }
} else {
    Write-Host "  ❌ FAILED: docs\\release_v2.0 not found" -ForegroundColor Red
}

Write-Host ""

# ============================================================================
# 🔥 选择性同步 scripts 目录（只同步便携版需要的脚本）
# ============================================================================

Write-Host "Syncing essential scripts..." -ForegroundColor Yellow
Write-Host ""

# 定义需要同步的脚本文件
$essentialScripts = @(
    "scripts\import_config_and_create_user.py",  # 🔥 导入数据库配置和创建用户
    "scripts\apply_upgrade_config.py",           # 🔥 升级配置增量导入（升级安装后首次启动）
    "scripts\init_mongodb_user.py",              # 🔥 初始化 MongoDB 用户
    "scripts\import_mongodb_config.py",          # 🔥 导入 MongoDB 配置
    "scripts\init_mongodb.ps1",                  # 🔥 初始化 MongoDB (PowerShell)
    "scripts\portable\stop_all.ps1",             # 停止所有服务
    "scripts\portable\stop_all_services.bat",    # 停止服务（批处理）
    "scripts\portable\README.md",                # 便携版说明
    # 🔥 installer 脚本
    "scripts\installer\start_all.py",            # 🔥 Python 启动脚本（包含退出日志功能）
    "scripts\installer\start_all.ps1",           # PowerShell 启动脚本
    "scripts\installer\stop_all.ps1",            # 停止服务脚本
    "scripts\installer\start_services_clean.ps1", # MongoDB/Redis 服务启动脚本
    "scripts\installer\collect_service_logs.ps1", # 错误日志收集脚本（诊断包）
    "scripts\installer\restart_all.ps1",         # Restart all services (for tray menu)
    # 🔥 进程监控脚本
    "scripts\monitor\process_monitor.py",        # 进程监控守护进程（包含退出报告功能）
    "scripts\monitor\start_monitor.ps1",         # 启动监控脚本
    "scripts\monitor\stop_monitor.ps1",          # 停止监控脚本
    "scripts\monitor\view_monitor.ps1",          # 查看监控日志脚本
    "scripts\monitor\monitor_status.ps1",        # 监控状态查看脚本
    "scripts\monitor\tray_monitor.py",            # 托盘监控主程序
    "scripts\monitor\tray_start.ps1",             # 托盘监控启动脚本
    "scripts\monitor\README.md",                 # 监控脚本说明
    # 🔥 测试和示例程序
    "scripts\test_batch_import_apis.py"          # 批量导入API测试程序
)

# Define startup scripts to copy to portable root
$startupScripts = @(
    @{ Source = 'scripts\installer\start_all.ps1'; Dest = 'start_all.ps1'; Description = 'Start all' },
    @{ Source = 'scripts\installer\start_services_clean.ps1'; Dest = 'start_services_clean.ps1'; Description = 'MongoDB/Redis' },
    @{ Source = 'scripts\installer\stop_all.ps1'; Dest = 'stop_all.ps1'; Description = 'Stop all' },
    @{ Source = 'scripts\installer\restart_all.ps1'; Dest = 'restart_all.ps1'; Description = 'Restart all' },
    @{ Source = 'debug_services.ps1'; Dest = 'debug_services.ps1'; Description = 'Debug services' }
)

foreach ($scriptPath in $essentialScripts) {
    $sourcePath = Join-Path $root $scriptPath
    $relativePath = $scriptPath
    $destPath = Join-Path $portableDir $relativePath

    if (Test-Path $sourcePath) {
        # 确保目标目录存在
        $destDir = Split-Path -Parent $destPath
        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        }

        Copy-WithProgress -Source $sourcePath -Destination $destPath -Description $relativePath
        $syncCount++
    } else {
        Write-Host "  SKIP: $scriptPath (not found)" -ForegroundColor Yellow
    }
}

# 复制启动脚本到便携版根目录
foreach ($script in $startupScripts) {
    $sourcePath = Join-Path $root $script.Source
    $destPath = Join-Path $portableDir $script.Dest

    if (Test-Path $sourcePath) {
        Copy-WithProgress -Source $sourcePath -Destination $destPath -Description $script.Description
        $syncCount++
    } else {
        Write-Host "  SKIP: $($script.Source) (not found)" -ForegroundColor Yellow
    }
}

Write-Host ""

# ============================================================================
# Copy runtime directory (nginx.conf, etc.)
# ============================================================================

Write-Host ""
Write-Host "Copying runtime directory..." -ForegroundColor Yellow

$sourceRuntimeDir = Join-Path $root "runtime"
$destRuntimeDir = Join-Path $portableDir "runtime"

if (Test-Path $sourceRuntimeDir) {
    # Ensure destination runtime directory exists
    if (-not (Test-Path $destRuntimeDir)) {
        New-Item -ItemType Directory -Path $destRuntimeDir -Force | Out-Null
    }

    # Copy nginx.conf
    $sourceNginxConf = Join-Path $sourceRuntimeDir "nginx.conf"
    $destNginxConf = Join-Path $destRuntimeDir "nginx.conf"
    if (Test-Path $sourceNginxConf) {
        Copy-Item -Path $sourceNginxConf -Destination $destNginxConf -Force
        Write-Host "  ✓ nginx.conf copied" -ForegroundColor Green
        $syncCount++
    } else {
        Write-Host "  ⚠ nginx.conf not found at $sourceNginxConf" -ForegroundColor Yellow
    }

    # Copy mime.types (required by nginx.conf)
    $sourceMimeTypes = Join-Path $sourceRuntimeDir "mime.types"
    $destMimeTypes = Join-Path $destRuntimeDir "mime.types"
    if (Test-Path $sourceMimeTypes) {
        Copy-Item -Path $sourceMimeTypes -Destination $destMimeTypes -Force
        Write-Host "  ✓ mime.types copied" -ForegroundColor Green
        $syncCount++
    } else {
        Write-Host "  ⚠ mime.types not found at $sourceMimeTypes" -ForegroundColor Yellow
    }

    # Copy redis.conf if exists
    $sourceRedisConf = Join-Path $sourceRuntimeDir "redis.conf"
    $destRedisConf = Join-Path $destRuntimeDir "redis.conf"
    if (Test-Path $sourceRedisConf) {
        Copy-Item -Path $sourceRedisConf -Destination $destRedisConf -Force
        Write-Host "  ✓ redis.conf copied" -ForegroundColor Green
        $syncCount++
    }
} else {
    Write-Host "  ⚠ Source runtime directory not found: $sourceRuntimeDir" -ForegroundColor Yellow
}

# ============================================================================
# Copy vendors directory from release/portable
# ============================================================================

Write-Host ""
Write-Host "Copying vendors directory (MongoDB, Redis, Nginx)..." -ForegroundColor Yellow

$sourceVendorsDir = Join-Path $root "release\portable\vendors"
$destVendorsDir = Join-Path $portableDir "vendors"

if (Test-Path $sourceVendorsDir) {
    # Ensure destination vendors directory exists
    if (-not (Test-Path $destVendorsDir)) {
        New-Item -ItemType Directory -Path $destVendorsDir -Force | Out-Null
    }

    # Copy MongoDB
    $sourceMongoDB = Join-Path $sourceVendorsDir "mongodb"
    $destMongoDB = Join-Path $destVendorsDir "mongodb"
    if (Test-Path $sourceMongoDB) {
        Write-Host "  Copying MongoDB..." -ForegroundColor Gray
        Copy-Item -Path $sourceMongoDB -Destination $destMongoDB -Recurse -Force
        Write-Host "  ✓ MongoDB copied" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ MongoDB not found at $sourceMongoDB" -ForegroundColor Yellow
    }

    # Copy Redis
    $sourceRedis = Join-Path $sourceVendorsDir "redis"
    $destRedis = Join-Path $destVendorsDir "redis"
    if (Test-Path $sourceRedis) {
        Write-Host "  Copying Redis..." -ForegroundColor Gray
        Copy-Item -Path $sourceRedis -Destination $destRedis -Recurse -Force
        Write-Host "  ✓ Redis copied" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ Redis not found at $sourceRedis" -ForegroundColor Yellow
    }

    # Copy Nginx
    $sourceNginx = Join-Path $sourceVendorsDir "nginx"
    $destNginx = Join-Path $destVendorsDir "nginx"
    if (Test-Path $sourceNginx) {
        Write-Host "  Copying Nginx..." -ForegroundColor Gray
        Copy-Item -Path $sourceNginx -Destination $destNginx -Recurse -Force
        Write-Host "  ✓ Nginx copied" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ Nginx not found at $sourceNginx" -ForegroundColor Yellow
    }

    # 🔥 Copy Python (embedded Python with DLLs)
    $sourcePython = Join-Path $sourceVendorsDir "python"
    $destPython = Join-Path $destVendorsDir "python"
    if (Test-Path $sourcePython) {
        Write-Host "  Copying Python (embedded)..." -ForegroundColor Gray
        Copy-Item -Path $sourcePython -Destination $destPython -Recurse -Force
        Write-Host "  ✓ Python copied (including DLLs)" -ForegroundColor Green
        
        # Verify DLLs directory exists
        $dllsDir = Join-Path $destPython "DLLs"
        if (Test-Path $dllsDir) {
            $pydCount = (Get-ChildItem -Path $dllsDir -Filter "*.pyd" -ErrorAction SilentlyContinue).Count
            Write-Host "    DLLs directory: $pydCount .pyd files" -ForegroundColor DarkGray
        } else {
            Write-Host "    ⚠ DLLs directory not found after copy!" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  ⚠ Python not found at $sourcePython" -ForegroundColor Yellow
        Write-Host "    💡 Python will be set up by setup_embedded_python.ps1 if needed" -ForegroundColor Gray
    }

    # Copy PDF dependencies (GTK3, wkhtmltopdf) - for WeasyPrint/PDF export
    $sourcePdf = Join-Path $sourceVendorsDir "pdf"
    $destPdf = Join-Path $destVendorsDir "pdf"
    if (Test-Path $sourcePdf) {
        Write-Host "  Copying PDF dependencies (GTK3, wkhtmltopdf)..." -ForegroundColor Gray
        if (-not (Test-Path $destPdf)) { New-Item -ItemType Directory -Path $destPdf -Force | Out-Null }
        Copy-Item -Path (Join-Path $sourcePdf "*") -Destination $destPdf -Recurse -Force
        $pdfCount = (Get-ChildItem -Path $destPdf -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -in '.exe','.msi' }).Count
        Write-Host "  ✓ PDF/Word dependencies copied ($pdfCount files)" -ForegroundColor Green
    } else {
        # Fallback: copy from install/vendors/pdf if release/portable/vendors/pdf not present
        $installPdf = Join-Path $root "install\vendors\pdf"
        if (Test-Path $installPdf) {
            Write-Host "  Copying PDF dependencies from install/vendors/pdf..." -ForegroundColor Gray
            if (-not (Test-Path $destPdf)) { New-Item -ItemType Directory -Path $destPdf -Force | Out-Null }
            Copy-Item -Path (Join-Path $installPdf "*") -Destination $destPdf -Recurse -Force
            Write-Host "  ✓ PDF dependencies copied" -ForegroundColor Green
        }
    }
} else {
    Write-Host "  ⚠ Source vendors directory not found: $sourceVendorsDir" -ForegroundColor Yellow
    Write-Host "  Please ensure release/portable exists with vendors directory" -ForegroundColor Yellow
}

# ============================================================================
# Summary
# ============================================================================

# ============================================================================
# 🔥 清理缓存文件（确保打包时不包含旧的字节码）
# ============================================================================
# 🔥 临时禁用清理逻辑，用于排查问题
# ============================================================================

# Write-Host ""
# Write-Host "Cleaning Python cache files..." -ForegroundColor Yellow
# 
# $cleanedCacheDirs = 0
# $cleanedPycFiles = 0
# 
# # 清理目标目录中的 __pycache__ 目录
# $cacheDirs = Get-ChildItem -Path $portableDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue
# if ($cacheDirs) {
#     $cleanedCacheDirs = ($cacheDirs | Measure-Object).Count
#     $cacheDirs | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
#     Write-Host "  ✅ Cleaned $cleanedCacheDirs __pycache__ directories" -ForegroundColor Green
# }
# 
# # 🔥 只清理源文件的缓存 .pyc 文件，保留编译后的字节码
# # 编译后的 .pyc 文件位置：
# # - core/other/ 目录中的 .pyc（编译后的字节码，应该保留）
# # - app/ 目录中的 .pyc（编译后的字节码，应该保留）
# # - vendors/python/DLLs/ 目录中的 .pyd 文件（Python扩展模块，必须保留）
# # - 其他位置的 .pyc（源文件的缓存，应该删除）
# $pycFiles = Get-ChildItem -Path $portableDir -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue | Where-Object {
#     $fullPath = $_.FullName
#     # 排除编译后的字节码目录和 Python DLLs 目录
#     $fullPath -notlike "*\core\other\*" -and
#     $fullPath -notlike "*\app\*" -and
#     $fullPath -notlike "*\vendors\python\DLLs\*"
# }
# if ($pycFiles) {
#     $cleanedPycFiles = ($pycFiles | Measure-Object).Count
#     $pycFiles | Remove-Item -Force -ErrorAction SilentlyContinue
#     Write-Host "  ✅ Cleaned $cleanedPycFiles source cache .pyc files" -ForegroundColor Green
#     Write-Host "    ✅ Preserved compiled bytecode in core/other/ and app/" -ForegroundColor DarkGray
# }
# 
# # 清理目标目录中的 .pyo 文件
# $pyoFiles = Get-ChildItem -Path $portableDir -Recurse -Filter "*.pyo" -ErrorAction SilentlyContinue
# if ($pyoFiles) {
#     $cleanedPyoFiles = ($pyoFiles | Measure-Object).Count
#     $pyoFiles | Remove-Item -Force -ErrorAction SilentlyContinue
#     Write-Host "  ✅ Cleaned $cleanedPyoFiles .pyo files" -ForegroundColor Green
# }
# 
# if ($cleanedCacheDirs -eq 0 -and $cleanedPycFiles -eq 0 -and $cleanedPyoFiles -eq 0) {
#     Write-Host "  ✅ No cache files found (already clean)" -ForegroundColor Green
# } else {
#     Write-Host "  ✅ Compiled bytecode (.pyc in core/other/ and app/) preserved" -ForegroundColor Green
# }
# 
# Write-Host ""

Write-Host ""
Write-Host "⚠️  Cache cleaning DISABLED for debugging..." -ForegroundColor Yellow
Write-Host ""
Write-Host "============================================================================" -ForegroundColor Green
Write-Host "  Sync Completed!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Files synced: $syncCount" -ForegroundColor Cyan
Write-Host "Files skipped: $skipCount" -ForegroundColor Yellow
Write-Host ""
Write-Host "Excluded content:" -ForegroundColor White
Write-Host "  - docs/courses/advanced/expanded/ (24节课程源码)" -ForegroundColor Gray
Write-Host "  - docs/courses/advanced/ppt/ (PPT源文件)" -ForegroundColor Gray
Write-Host "  - docs/design/ (设计文档)" -ForegroundColor Gray
Write-Host "  - __pycache__/ and *.pyc files (Python cache)" -ForegroundColor Gray
Write-Host ""
Write-Host "Next: Run build_portable_package.ps1 to package" -ForegroundColor Cyan
Write-Host ""

