# ============================================================================
# Build Windows Installer for TradingAgents-CN Pro
# ============================================================================
# 此脚本用于构建Windows安装程序（.exe）
# 需要先安装NSIS: https://nsis.sourceforge.io/Download
# ============================================================================

# UTF-8编码设置
param(
    [switch]$SkipBuild,
    [switch]$SkipExport,
    [switch]$Test,
    [string]$Version = "",
    [string]$ArchiveRoot = "D:\release"
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
$OutputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

# ============================================================================
# 临时目录优化：优先使用 D 盘，避免 C 盘空间不足导致打包失败
# ============================================================================
try {
    $dDrive = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='D:'" -ErrorAction SilentlyContinue
    if ($dDrive -and $dDrive.FreeSpace -gt 20GB) {
        $tempDir = "D:\Temp"
        if (-not (Test-Path $tempDir)) {
            New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
        }
        $env:TEMP = $tempDir
        $env:TMP = $tempDir
        Write-Host "  📝 临时目录已切换到 D 盘: $tempDir" -ForegroundColor Gray
    } else {
        Write-Host "  📝 D 盘空间不足或未找到，继续使用默认临时目录: $env:TEMP" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  📝 临时目录切换失败，使用默认值: $env:TEMP" -ForegroundColor Yellow
}

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
# Step 1.5: 导出演示数据库到 install 目录
# ============================================================================

if (-not $SkipExport) {
    $modeLabel = if ($Test) { "测试" } else { "正式" }
    Write-Host "[1.5/6] 导出演示数据库（$modeLabel 模式）..." -ForegroundColor Yellow
    Write-Host ""

    $exportScript = Join-Path $PSScriptRoot "export_database.py"
    $venvPython = Join-Path $root "env\Scripts\python.exe"
    $pythonCmd = if (Test-Path $venvPython) { $venvPython } else { "python" }

    if ($Test) {
        # 测试模式：生成带日期的文件（不覆盖稳定版）
        & $pythonCmd $exportScript --test
    } else {
        # 正式模式：生成稳定版（覆盖旧文件）
        & $pythonCmd $exportScript
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: 数据库导出失败" -ForegroundColor Red
        Write-Host "如需跳过导出，请使用 -SkipExport 参数" -ForegroundColor Yellow
        exit 1
    }

    # 测试模式：找最新的日期版文件，临时覆盖稳定版用于打包（构建后恢复原文件）
    $script:testStableBackup = $null
    $script:testStableExisted = $false
    if ($Test) {
        $installDir = Join-Path $root "install"
        $datedFiles = Get-ChildItem -Path $installDir -Filter "database_export_config_*.json" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
        if ($datedFiles) {
            $latestDatedFile = $datedFiles[0].FullName
            $stableFile = Join-Path $installDir "database_export_config.json"
            $script:testStableBackup = Join-Path $installDir "database_export_config.json.testbak"
            Write-Host "  测试模式：使用日期版数据: $($datedFiles[0].Name)" -ForegroundColor Cyan
            Write-Host "  临时覆盖稳定版用于打包（构建完成后自动恢复原稳定版）" -ForegroundColor Gray

            # 备份原稳定版（如果存在），然后用日期版覆盖稳定版
            if (Test-Path $stableFile) {
                $script:testStableExisted = $true
                Copy-Item -LiteralPath $stableFile -Destination $script:testStableBackup -Force
            }
            Copy-Item -LiteralPath $latestDatedFile -Destination $stableFile -Force
        } else {
            Write-Host "  WARNING: 未找到日期版数据文件，使用现有稳定版" -ForegroundColor Yellow
        }
    }

    Write-Host "  ✅ 演示数据库导出完成" -ForegroundColor Green
} else {
    Write-Host "[1.5/6] 跳过数据库导出 (-SkipExport)" -ForegroundColor Yellow
}

Write-Host ""

# 测试模式恢复函数：构建完成后恢复原稳定版文件
function Restore-TestStableBackup {
    if (-not $script:testStableBackup) { return }

    $installDir = Join-Path $root "install"
    $stableFile = Join-Path $installDir "database_export_config.json"

    if (Test-Path $script:testStableBackup) {
        # 有备份：恢复原稳定版
        Move-Item -LiteralPath $script:testStableBackup -Destination $stableFile -Force
        Write-Host "  测试模式：已恢复原稳定版文件" -ForegroundColor Cyan
    } elseif (-not $script:testStableExisted) {
        # 原本没有稳定版：删除临时创建的稳定版
        if (Test-Path $stableFile) {
            Remove-Item -LiteralPath $stableFile -Force
            Write-Host "  测试模式：已删除临时稳定版文件（原无稳定版）" -ForegroundColor Cyan
        }
    }
    $script:testStableBackup = $null
}

# ============================================================================
# Step 2-6: 构建安装包（包装在 try/finally 中，确保测试模式能恢复稳定版文件）
# ============================================================================

$script:buildFailed = $false

try {
    # ========================================================================
    # Step 2: 构建Pro版（如果需要）
    # ========================================================================

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
            throw "Pro version build failed"
        }

        Write-Host "  ✅ Pro version built successfully" -ForegroundColor Green
    } else {
        Write-Host "[2/5] Skipping Pro version build (using existing files)..." -ForegroundColor Yellow
    }

    Write-Host ""

    # ========================================================================
    # Step 3: 构建安装器内容包（portable 7z）
    # ========================================================================

    Write-Host "[3/5] Building installer payload package..." -ForegroundColor Yellow
    Write-Host ""

    $portablePackageScript = Join-Path $PSScriptRoot "build_portable_package.ps1"
    if (-not (Test-Path $portablePackageScript)) {
        throw "Portable package script not found: $portablePackageScript"
    }

    if ($Version) {
        & powershell -ExecutionPolicy Bypass -File $portablePackageScript -Version $Version -SkipSync -SkipEmbeddedPython -SkipFrontendBuild -Format 7z
    } else {
        & powershell -ExecutionPolicy Bypass -File $portablePackageScript -SkipSync -SkipEmbeddedPython -SkipFrontendBuild -Format 7z
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Portable package build failed"
    }

    Write-Host "  ✅ Installer payload package built successfully" -ForegroundColor Green
    Write-Host ""

    # ========================================================================
    # Step 4: 准备安装程序资源
    # ========================================================================

    Write-Host "[4/6] Preparing installer resources..." -ForegroundColor Yellow
    Write-Host ""

    $installerDir = Join-Path $root "scripts\windows-installer\nsis"
    $portableDir = Join-Path $root "release\TradingAgentsCN-portable"
    $packagesDir = Join-Path $root "release\packages"
    $licenseFile = Join-Path $root "LICENSE"

    # 检查必要文件
    if (-not (Test-Path $portableDir)) {
        Write-Host "ERROR: Portable directory not found: $portableDir" -ForegroundColor Red
        Write-Host "Please run build_pro_package.ps1 first" -ForegroundColor Yellow
        throw "Portable directory not found"
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

    # ========================================================================
    # Step 5: 编译NSIS脚本
    # ========================================================================

    Write-Host "[5/6] Compiling NSIS script..." -ForegroundColor Yellow
    Write-Host ""

    $nsiScript = Join-Path $installerDir "installer.nsi"

    if (-not (Test-Path $nsiScript)) {
        Write-Host "ERROR: NSIS script not found: $nsiScript" -ForegroundColor Red
        throw "NSIS script not found"
    }

    if (-not $Version) {
        $versionFile = Join-Path $root "VERSION"
        if (Test-Path $versionFile) {
            $Version = (Get-Content $versionFile -Raw).Trim()
        } else {
            $Version = "1.0.0"
        }
    }

    $buildInfoFile = Join-Path $root "BUILD_INFO"
    $portablePackagePath = Join-Path $packagesDir "TradingAgentsCN-Portable-latest-installer.7z"
    $portableZipPath = Join-Path $packagesDir "TradingAgentsCN-Portable-latest.zip"

    if (Test-Path $buildInfoFile) {
        try {
            $buildInfo = Get-Content $buildInfoFile -Raw | ConvertFrom-Json
            if ($buildInfo.full_version) {
                $candidate7z = Join-Path $packagesDir "TradingAgentsCN-Portable-$($buildInfo.full_version)-installer.7z"
                if (Test-Path $candidate7z) {
                    $portablePackagePath = $candidate7z
                }

                $candidateZip = Join-Path $packagesDir "TradingAgentsCN-Portable-$($buildInfo.full_version).zip"
                if (Test-Path $candidateZip) {
                    $portableZipPath = $candidateZip
                }
            }
        } catch {
            Write-Host "  Warning: Failed to parse BUILD_INFO, falling back to latest package aliases" -ForegroundColor Yellow
        }
    }

    if (-not (Test-Path $portablePackagePath)) {
        Write-Host "ERROR: Portable installer package not found: $portablePackagePath" -ForegroundColor Red
        throw "Portable installer package not found"
    }

    Write-Host "  NSIS script: $nsiScript" -ForegroundColor Gray
    Write-Host "  Installer payload: $portablePackagePath" -ForegroundColor Gray
    Write-Host "  Compiling..." -ForegroundColor Gray
    Write-Host ""

    # 运行NSIS编译器
    $nsisArgs = @(
        "/V4",  # 详细输出
        "/DPRODUCT_VERSION=$Version",
        "/DPROJECT_ROOT=$root",
        "/DPACKAGE_7Z=$portablePackagePath",
        $nsiScript
    )

    if (Test-Path $portableZipPath) {
        $nsisArgs = @(
            "/V4",
            "/DPRODUCT_VERSION=$Version",
            "/DPROJECT_ROOT=$root",
            "/DPACKAGE_ZIP=$portableZipPath",
            "/DPACKAGE_7Z=$portablePackagePath",
            $nsiScript
        )
    }

    # 测试模式：添加 TEST_BUILD 定义
    if ($Test) {
        $nsisArgs = @("/DTEST_BUILD") + $nsisArgs
        Write-Host "  测试模式：安装包文件名将带 -test 后缀" -ForegroundColor Cyan
    }

    $process = Start-Process -FilePath $nsisPath -ArgumentList $nsisArgs -Wait -PassThru -NoNewWindow

    if ($process.ExitCode -ne 0) {
        Write-Host "ERROR: NSIS compilation failed with exit code: $($process.ExitCode)" -ForegroundColor Red
        throw "NSIS compilation failed"
    }

    Write-Host "  ✅ NSIS compilation completed" -ForegroundColor Green
    Write-Host ""

    # ========================================================================
    # Step 6: 验证安装程序
    # ========================================================================

    Write-Host "[6/6] Verifying installer..." -ForegroundColor Yellow
    Write-Host ""

    $installerVersion = $Version
    if ($Test) {
        $installerVersion = "$Version-test"
    }

    $installerPath = Join-Path $root "release\packages\TradingAgentsCNSetup-$installerVersion.exe"

    if (Test-Path $installerPath) {
        $installerSize = (Get-Item $installerPath).Length
        $installerSizeMB = [math]::Round($installerSize / 1MB, 2)

        Write-Host "  ✅ Installer created successfully!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Installer Information:" -ForegroundColor White
        Write-Host "  File: TradingAgentsCNSetup-$installerVersion.exe" -ForegroundColor Cyan
        Write-Host "  Size: $installerSizeMB MB" -ForegroundColor Cyan
        Write-Host "  Path: $installerPath" -ForegroundColor Cyan
    } else {
        Write-Host "ERROR: Installer not found at expected location" -ForegroundColor Red
        throw "Installer not found at expected location"
    }

    Write-Host ""

    # ========================================================================
    # 完成
    # ========================================================================

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

} catch {
    Write-Host "ERROR: $_" -ForegroundColor Red
    $script:buildFailed = $true
} finally {
    # 测试模式：恢复原稳定版文件（无论成功或失败都执行）
    Restore-TestStableBackup
}

if ($script:buildFailed) {
    exit 1
}

