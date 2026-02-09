param(
    [string]$Version = "",
    [int]$BackendPort = 8000,
    [int]$MongoPort = 27017,
    [int]$RedisPort = 6379,
    [int]$NginxPort = 80,
    [string]$NsisPath,
    [switch]$SkipPortablePackage = $false,
    [switch]$Verbose = $false,
    [switch]$Interactive = $false  # 🔥 交互模式：每步后确认
)

$ErrorActionPreference = "Stop"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] [$Level] $Message"
}

function Confirm-NextStep {
    param([string]$StepName)

    if (-not $Interactive) {
        return $true
    }

    Write-Host ""
    Write-Host "============================================================================" -ForegroundColor Yellow
    Write-Host "  Step completed: $StepName" -ForegroundColor Yellow
    Write-Host "============================================================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Please verify the results above." -ForegroundColor Cyan
    Write-Host ""

    $response = Read-Host "Continue to next step? (Y/n)"

    if ($response -eq "" -or $response -eq "Y" -or $response -eq "y") {
        Write-Host ""
        return $true
    } else {
        Write-Host ""
        Write-Log "Build stopped by user." "WARNING"
        exit 0
    }
}

$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path

# Read version from VERSION file if not specified
if ([string]::IsNullOrEmpty($Version)) {
    $versionFile = Join-Path $root "VERSION"
    if (Test-Path $versionFile) {
        $Version = (Get-Content $versionFile -Raw).Trim()
        Write-Log "Read version from VERSION file: $Version"
    } else {
        Write-Log "VERSION file not found, using default: 1.0.0" "WARNING"
        $Version = "1.0.0"
    }
}

Write-Log "=========================================="
Write-Log "Windows Installer Build"
Write-Log "=========================================="
Write-Log "Version: $Version"
Write-Log "Backend Port: $BackendPort"
Write-Log "MongoDB Port: $MongoPort"
Write-Log "Redis Port: $RedisPort"
Write-Log "Nginx Port: $NginxPort"

# 生成构建信息
Write-Log ""
Write-Log "Generating build info..."
$buildInfoScript = Join-Path $root "scripts\build\generate_build_info.ps1"
if (Test-Path $buildInfoScript) {
    & powershell -ExecutionPolicy Bypass -File $buildInfoScript -BuildType "installer" -ProjectRoot $root
    # 读取BUILD_INFO获取完整版本号
    $buildInfoFile = Join-Path $root "BUILD_INFO"
    if (Test-Path $buildInfoFile) {
        $buildInfo = Get-Content $buildInfoFile -Raw | ConvertFrom-Json
        $FullVersion = $buildInfo.full_version
        if ($FullVersion) {
            $Version = $FullVersion
            Write-Log "Using full version: $Version"
        }
    }
} else {
    Write-Log "Warning: Build info script not found: $buildInfoScript" "WARNING"
}
Write-Log ""

if ($Interactive) {
    Write-Host "🔧 Interactive mode enabled - will prompt after each step" -ForegroundColor Cyan
}

$nsi = Join-Path $PSScriptRoot "..\nsis\installer.nsi"

# Step 1: Build portable package if not skipped
if (-not $SkipPortablePackage) {
    Write-Log ""
    Write-Log "Step 1a: Building Pro package (compile code)..."
    # 🔥 Step 1a: 使用 Pro 版脚本编译代码
    $proScript = Join-Path $root "scripts\deployment\build_pro_package.ps1"

    if (-not (Test-Path $proScript)) {
        Write-Log "Pro package script not found: $proScript" "ERROR"
        throw "Pro package script not found"
    }

    try {
        if ($Interactive) {
            & powershell -ExecutionPolicy Bypass -File $proScript -Version $Version -Interactive
        } else {
            & powershell -ExecutionPolicy Bypass -File $proScript -Version $Version
        }
        if ($LASTEXITCODE -ne 0) {
            Write-Log "Pro package build failed with exit code $LASTEXITCODE" "ERROR"
            throw "Pro package build failed"
        }
        Write-Log "Pro package built successfully (code compiled)"
    } catch {
        Write-Log "Pro package build failed: $_" "ERROR"
        throw
    }

    # 🔧 交互式确认
    Confirm-NextStep "Build Pro package (compile code)" | Out-Null

    # Step 1b: Ensure PDF dependencies (GTK3, wkhtmltopdf) in portable dir before packaging
    Write-Log ""
    Write-Log "Step 1b: Ensuring PDF dependencies in portable package..."
    $portableDir = Join-Path $root "release\TradingAgentsCN-portable"
    $destPdf = Join-Path $portableDir "vendors\pdf"
    $sources = @(
        (Join-Path $root "release\portable\vendors\pdf"),
        (Join-Path $root "install\vendors\pdf")
    )
    $pdfCopied = $false
    foreach ($src in $sources) {
        $hasInstaller = (Get-ChildItem $src -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -in '.exe','.msi' })
        if ((Test-Path $src) -and $hasInstaller) {
            if (-not (Test-Path $destPdf)) { New-Item -ItemType Directory -Path $destPdf -Force | Out-Null }
            Copy-Item -Path (Join-Path $src "*") -Destination $destPdf -Recurse -Force
            Write-Log "PDF dependencies copied from $src"
            $pdfCopied = $true
            break
        }
    }
    if (-not $pdfCopied -and (Test-Path $destPdf)) {
        Write-Log "Using existing vendors\pdf in portable"
    } elseif (-not $pdfCopied) {
        Write-Log "No PDF/Word deps found. Place gtk3*.exe, wkhtmltox*.exe, pandoc*.msi in install/vendors/pdf or release/portable/vendors/pdf" "WARNING"
    }

    Write-Log ""
    Write-Log "Step 1c: Packaging into 7z archive..."
    # 🔥 Step 1b: 打包成 .7z 文件（用于 NSIS 安装包）
    $packageScript = Join-Path $root "scripts\deployment\build_portable_package.ps1"

    if (-not (Test-Path $packageScript)) {
        Write-Log "Package script not found: $packageScript" "ERROR"
        throw "Package script not found"
    }

    try {
        # 跳过同步和编译，只打包成 .7z
        & powershell -ExecutionPolicy Bypass -File $packageScript -SkipSync -SkipEmbeddedPython -SkipFrontendBuild -Format "7z" -Version $Version
        if ($LASTEXITCODE -ne 0) {
            Write-Log "Packaging failed with exit code $LASTEXITCODE" "ERROR"
            throw "Packaging failed"
        }
        Write-Log "Packaging completed successfully"
    } catch {
        Write-Log "Packaging failed: $_" "ERROR"
        throw
    }

    # 🔧 交互式确认
    Confirm-NextStep "Package into 7z archive" | Out-Null
} else {
    Write-Log "Skipping portable package build (using existing package)"
}

# Find the latest portable package for installer (7z format, without vendors/7zip)
$packagesDir = Join-Path $root "release\packages"
if (-not (Test-Path $packagesDir)) {
    Write-Log "Packages directory not found: $packagesDir" "ERROR"
    throw "Packages directory not found"
}

# Look for -installer.7z files first (preferred for NSIS)
$latestPackage = Get-ChildItem -Path $packagesDir -Filter "*-installer.7z" | Sort-Object LastWriteTime -Descending | Select-Object -First 1

if (-not $latestPackage) {
    Write-Log "No installer package (*-installer.7z) found in $packagesDir" "ERROR"
    Write-Log "Please run: .\scripts\deployment\build_portable_package.ps1 -Format 7z" "ERROR"
    throw "No installer package found"
}

Write-Log "Using portable package: $($latestPackage.Name)"
$package7z = $latestPackage.FullName

# Create a copy with a fixed name for NSIS (if not already named correctly)
$fixedPackageName = Join-Path $packagesDir "TradingAgentsCN-Portable-latest-installer.7z"
if ($package7z -ne $fixedPackageName) {
    Copy-Item -Path $package7z -Destination $fixedPackageName -Force
    Write-Log "Created fixed-name package: TradingAgentsCN-Portable-latest-installer.7z"
} else {
    Write-Log "Package already has correct name: TradingAgentsCN-Portable-latest-installer.7z"
}

# Check if 7z.exe exists
$7zExe = Join-Path $root "vendors\7zip\7z.exe"
$7zDll = Join-Path $root "vendors\7zip\7z.dll"
if (-not (Test-Path $7zExe)) {
    Write-Log "7z.exe not found at $7zExe" "ERROR"
    Write-Log "Please copy 7z.exe and 7z.dll from C:\7-Zip to vendors\7zip\" "ERROR"
    throw "7z.exe not found"
}
if (-not (Test-Path $7zDll)) {
    Write-Log "7z.dll not found at $7zDll" "WARNING"
    Write-Log "7z.exe may not work without 7z.dll" "WARNING"
}
Write-Log "7-Zip tools found: 7z.exe and 7z.dll"

Write-Log ""
Write-Log "Step 2: Building NSIS installer..."

Write-Log "Checking installer.nsi..."
if (-not (Test-Path -LiteralPath $nsi)) {
    Write-Log "installer.nsi not found: $nsi" "ERROR"
    throw "installer.nsi not found"
}
Write-Log "installer.nsi found"

Write-Log "Searching for NSIS installation..."
if (-not $NsisPath) {
    $candidates = @()
    if ($env:ProgramFiles) { $candidates += (Join-Path $env:ProgramFiles 'NSIS') }
    $pf86 = ${env:ProgramFiles(x86)}
    if ($pf86) { $candidates += (Join-Path $pf86 'NSIS') }

    foreach ($p in $candidates) {
        Write-Log "Checking NSIS path: $p"
        $exe = Join-Path $p 'makensis.exe'
        if (Test-Path -LiteralPath $exe) {
            $NsisPath = $p
            Write-Log "Found NSIS: $NsisPath"
            break
        }
    }
}

if (-not $NsisPath) {
    Write-Log "NSIS not found. Please install NSIS or provide -NsisPath parameter" "ERROR"
    throw "NSIS not found. Please install NSIS and provide -NsisPath."
}

$makensis = Join-Path $NsisPath "makensis.exe"
if (-not (Test-Path -LiteralPath $makensis)) {
    Write-Log "makensis.exe not found: $makensis" "ERROR"
    throw "makensis.exe not found under $NsisPath"
}
Write-Log "makensis.exe found: $makensis"

Write-Log "Preparing compilation parameters..."
$sevenzipDir = Join-Path $root "vendors\7zip"
# Escape backslashes for NSIS
$packagesDirEscaped = $packagesDir -replace '\\', '\\'
$rootEscaped = $root -replace '\\', '\\'
$sevenzipDirEscaped = $sevenzipDir -replace '\\', '\\'
$fixedPackageNameEscaped = $fixedPackageName -replace '\\', '\\'

Write-Log "Compilation parameters:"
Write-Log "  PRODUCT_VERSION=$Version"
Write-Log "  BACKEND_PORT=$BackendPort"
Write-Log "  MONGO_PORT=$MongoPort"
Write-Log "  REDIS_PORT=$RedisPort"
Write-Log "  NGINX_PORT=$NginxPort"

Write-Log "Starting NSIS compilation..."
$env:PRODUCT_VERSION = $Version

# Build the command line arguments
$nsisArgs = @(
    "/DPRODUCT_VERSION=$Version"
    "/DBACKEND_PORT=$BackendPort"
    "/DMONGO_PORT=$MongoPort"
    "/DREDIS_PORT=$RedisPort"
    "/DNGINX_PORT=$NginxPort"
    "/DPACKAGE_7Z=$fixedPackageNameEscaped"
    "/DOUTPUT_DIR=$packagesDirEscaped"
    "/DPROJECT_ROOT=$rootEscaped"
    "/DSEVENZIP_DIR=$sevenzipDirEscaped"
    $nsi
)

try {
    # Use Start-Process to properly handle arguments
    $process = Start-Process -FilePath $makensis -ArgumentList $nsisArgs -Wait -NoNewWindow -PassThru

    if ($process.ExitCode -ne 0) {
        Write-Log "NSIS compilation failed with exit code $($process.ExitCode)" "ERROR"
        throw "NSIS compilation failed"
    }
    Write-Log "Installer compilation completed"

    # Show output file location
    $outputFile = Join-Path $packagesDir "TradingAgentsCNSetup-$Version.exe"
    if (Test-Path $outputFile) {
        $fileSize = (Get-Item $outputFile).Length / 1MB
        Write-Log ""
        Write-Log "=========================================="
        Write-Log "Installer created successfully!"
        Write-Log "=========================================="
        Write-Log "File: $outputFile"
        Write-Log "Size: $([Math]::Round($fileSize, 2)) MB"
    } else {
        Write-Log "Warning: Expected output file not found: $outputFile" "WARNING"
    }

    # 🔧 交互式确认
    Confirm-NextStep "Build NSIS installer" | Out-Null
} catch {
    Write-Log "Compilation failed: $_" "ERROR"
    throw
}