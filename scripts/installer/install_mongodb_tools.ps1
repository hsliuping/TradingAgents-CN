# ============================================================================
# MongoDB Database Tools 安装脚本
# ============================================================================
# 用于安装 MongoDB Database Tools（mongodump, mongorestore 等）
# ============================================================================

# UTF-8编码设置
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
$OutputEncoding = [System.Text.Encoding]::UTF8

param(
    [string]$InstallDir = "",
    [switch]$AddToPath = $true
)

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  MongoDB Database Tools 安装脚本" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# 检测操作系统架构
$arch = if ([Environment]::Is64BitOperatingSystem) { "x86_64" } else { "i386" }
$os = "windows"

Write-Host "📋 系统信息：" -ForegroundColor Yellow
Write-Host "  操作系统: Windows" -ForegroundColor Gray
Write-Host "  架构: $arch" -ForegroundColor Gray
Write-Host ""

# MongoDB Database Tools 下载信息
# 注意：这里使用固定版本，也可以改为自动检测最新版本
$version = "100.9.4"  # MongoDB Database Tools 版本
$baseUrl = "https://fastdl.mongodb.org/tools/db"
$filename = "mongodb-database-tools-windows-$arch-$version.zip"
$downloadUrl = "$baseUrl/$filename"

# 确定安装目录
if ([string]::IsNullOrEmpty($InstallDir)) {
    # 默认安装到应用目录下的 tools/mongodb-tools
    $scriptDir = Split-Path -Parent $PSScriptRoot
    $rootDir = Split-Path -Parent $scriptDir
    $InstallDir = Join-Path $rootDir "tools\mongodb-tools"
}

Write-Host "📦 安装配置：" -ForegroundColor Yellow
Write-Host "  下载地址: $downloadUrl" -ForegroundColor Gray
Write-Host "  安装目录: $InstallDir" -ForegroundColor Gray
Write-Host "  添加到 PATH: $AddToPath" -ForegroundColor Gray
Write-Host ""

# 创建临时下载目录
$tempDir = Join-Path $env:TEMP "mongodb-tools-install"
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

$zipPath = Join-Path $tempDir $filename

try {
    # 下载 MongoDB Database Tools
    Write-Host "⬇️  正在下载 MongoDB Database Tools..." -ForegroundColor Yellow
    Write-Host "   文件: $filename" -ForegroundColor Gray
    
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath -UseBasicParsing
    
    if (-not (Test-Path $zipPath)) {
        throw "下载失败：文件不存在"
    }
    
    $fileSize = (Get-Item $zipPath).Length / 1MB
    Write-Host "   ✅ 下载完成 ($([math]::Round($fileSize, 2)) MB)" -ForegroundColor Green
    Write-Host ""
    
    # 解压文件
    Write-Host "📂 正在解压文件..." -ForegroundColor Yellow
    $extractDir = Join-Path $tempDir "extracted"
    Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force
    
    # 查找 bin 目录
    $binDirs = Get-ChildItem -Path $extractDir -Directory -Recurse -Filter "bin" | Where-Object {
        Test-Path (Join-Path $_.FullName "mongodump.exe")
    }
    
    if ($binDirs.Count -eq 0) {
        throw "解压后未找到 bin 目录"
    }
    
    $sourceBinDir = $binDirs[0].FullName
    Write-Host "   ✅ 解压完成" -ForegroundColor Green
    Write-Host ""
    
    # 创建安装目录
    Write-Host "📁 正在安装到: $InstallDir" -ForegroundColor Yellow
    if (Test-Path $InstallDir) {
        Write-Host "   ⚠️  目录已存在，将覆盖" -ForegroundColor Yellow
        Remove-Item $InstallDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    
    # 复制文件
    Copy-Item -Path "$sourceBinDir\*" -Destination $InstallDir -Recurse -Force
    Write-Host "   ✅ 安装完成" -ForegroundColor Green
    Write-Host ""
    
    # 验证安装
    $mongodumpPath = Join-Path $InstallDir "mongodump.exe"
    if (Test-Path $mongodumpPath) {
        Write-Host "✅ 验证安装..." -ForegroundColor Yellow
        $versionOutput = & $mongodumpPath --version 2>&1
        Write-Host "   MongoDB Database Tools 版本:" -ForegroundColor Gray
        Write-Host "   $versionOutput" -ForegroundColor Gray
        Write-Host ""
    } else {
        throw "安装验证失败：mongodump.exe 不存在"
    }
    
    # 添加到 PATH（可选）
    if ($AddToPath) {
        Write-Host "🔧 添加到系统 PATH..." -ForegroundColor Yellow
        
        $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
        if ($currentPath -notlike "*$InstallDir*") {
            $newPath = "$currentPath;$InstallDir"
            [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
            Write-Host "   ✅ 已添加到用户 PATH" -ForegroundColor Green
            Write-Host "   ⚠️  请重新打开命令行窗口或重启应用以使 PATH 生效" -ForegroundColor Yellow
        } else {
            Write-Host "   ℹ️  PATH 中已包含此目录" -ForegroundColor Gray
        }
        Write-Host ""
    }
    
    Write-Host "============================================================================" -ForegroundColor Green
    Write-Host "  ✅ MongoDB Database Tools 安装成功！" -ForegroundColor Green
    Write-Host "============================================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "📋 安装信息：" -ForegroundColor Yellow
    Write-Host "  安装目录: $InstallDir" -ForegroundColor Gray
    Write-Host "  工具路径: $mongodumpPath" -ForegroundColor Gray
    Write-Host ""
    Write-Host "💡 使用提示：" -ForegroundColor Yellow
    Write-Host "  - 如果已添加到 PATH，可以直接使用 mongodump 和 mongorestore 命令" -ForegroundColor Gray
    Write-Host "  - 如果未添加到 PATH，请使用完整路径：" -ForegroundColor Gray
    Write-Host "    $mongodumpPath" -ForegroundColor Gray
    Write-Host ""
    
} catch {
    Write-Host ""
    Write-Host "============================================================================" -ForegroundColor Red
    Write-Host "  ❌ 安装失败" -ForegroundColor Red
    Write-Host "============================================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "错误信息: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 解决方案：" -ForegroundColor Yellow
    Write-Host "  1. 检查网络连接" -ForegroundColor Gray
    Write-Host "  2. 手动下载并安装 MongoDB Database Tools：" -ForegroundColor Gray
    Write-Host "     https://www.mongodb.com/try/download/database-tools" -ForegroundColor Gray
    Write-Host "  3. 或者使用 Python 实现的备份功能（速度较慢）" -ForegroundColor Gray
    Write-Host ""
    exit 1
} finally {
    # 清理临时文件
    if (Test-Path $tempDir) {
        Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
