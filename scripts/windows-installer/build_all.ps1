param(
    [string]$Version = "1.0.0",
    [int]$BackendPort = 8000,
    [int]$MongoPort = 27017,
    [int]$RedisPort = 6379,
    [int]$NginxPort = 80,
    [string]$NsisPath,
    [string]$OutputDir = "release\portable",
    [switch]$SkipPortable = $false,
    [switch]$SkipInstaller = $false
)

$ErrorActionPreference = "Stop"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] [$Level] $Message"
}

Write-Log "=========================================="
Write-Log "TradingAgentsCN Windows Installer Build"
Write-Log "=========================================="
Write-Log "Version: $Version"
Write-Log "Backend Port: $BackendPort"
Write-Log "MongoDB Port: $MongoPort"
Write-Log "Redis Port: $RedisPort"
Write-Log "Nginx Port: $NginxPort"
Write-Log "Output Dir: $OutputDir"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Write-Log "Project Root: $root"

if (-not $SkipPortable) {
    Write-Log ""
    Write-Log "========== Step 1: Build Portable Version =========="
    $portableScript = Join-Path $PSScriptRoot "prepare\build_portable.ps1"
    
    if (-not (Test-Path $portableScript)) {
        Write-Log "build_portable.ps1 not found: $portableScript" "ERROR"
        exit 1
    }
    
    try {
        Write-Log "Executing build_portable.ps1..."
        $portableDir = & $portableScript -OutputDir $OutputDir
        Write-Log "Portable version build completed: $portableDir"
    } catch {
        Write-Log "Portable version build failed: $_" "ERROR"
        exit 1
    }
} else {
    Write-Log "Skipping portable version build"
    $portableDir = Join-Path $root $OutputDir
}

if (-not $SkipInstaller) {
    Write-Log ""
    Write-Log "========== Step 2: Build Installer =========="
    $installerScript = Join-Path $PSScriptRoot "build\build_installer.ps1"
    
    if (-not (Test-Path $installerScript)) {
        Write-Log "build_installer.ps1 not found: $installerScript" "ERROR"
        exit 1
    }
    
    try {
        Write-Log "Executing build_installer.ps1..."
        $args = @(
            "-Version", $Version,
            "-BackendPort", $BackendPort,
            "-MongoPort", $MongoPort,
            "-RedisPort", $RedisPort,
            "-NginxPort", $NginxPort
        )
        
        if ($NsisPath) {
            $args += "-NsisPath", $NsisPath
        }
        
        & $installerScript @args
        Write-Log "Installer build completed"
    } catch {
        Write-Log "Installer build failed: $_" "ERROR"
        exit 1
    }
} else {
    Write-Log "Skipping installer build"
}

Write-Log ""
Write-Log "=========================================="
Write-Log "Build Completed!"
Write-Log "=========================================="
Write-Log "Portable Version: $portableDir"
Write-Log "Installer: $(Join-Path $PSScriptRoot "nsis\TradingAgentsCNSetup-$Version.exe")"
