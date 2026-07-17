[CmdletBinding()]
param(
    [string]$Registry = "hsliup",
    [string]$VersionTag = "",
    [string]$BaseTag = "python3.10-bookworm",
    [string]$Platforms = "linux/amd64,linux/arm64",
    [switch]$SkipBackend = $false,
    [switch]$SkipFrontend = $false,
    [switch]$SkipLatestAlias = $false
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path

function Invoke-DockerCommand {
    param(
        [string[]]$Arguments,
        [string]$Description
    )

    Write-Host $Description -ForegroundColor Cyan
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed: docker $($Arguments -join ' ')"
    }
}

if (-not $VersionTag) {
    $versionFile = Join-Path $projectRoot "VERSION"
    if (-not (Test-Path $versionFile)) {
        throw "VERSION file not found: $versionFile"
    }

    $VersionTag = (Get-Content $versionFile -Raw).Trim()
}

if (-not $VersionTag) {
    throw "VersionTag is empty. Provide -VersionTag or populate VERSION."
}

$backendVersionImage = "$Registry/tradingagents-pro-backend:$VersionTag"
$frontendVersionImage = "$Registry/tradingagents-pro-frontend:$VersionTag"
$backendBaseImage = "$Registry/tradingagents-pro-backend-base:$BaseTag"
$backendLatestImage = "$Registry/tradingagents-pro-backend:3-latest"
$frontendLatestImage = "$Registry/tradingagents-pro-frontend:3-latest"

Write-Host "========================================" -ForegroundColor Yellow
Write-Host "Docker Release" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
Write-Host "Registry: $Registry"
Write-Host "Version : $VersionTag"
Write-Host "BaseTag : $BaseTag"
Write-Host "Platforms: $Platforms"
Write-Host ""

Push-Location $projectRoot
try {
    $null = & docker buildx inspect multiarch 2>$null
    if ($LASTEXITCODE -ne 0) {
        Invoke-DockerCommand -Arguments @("buildx", "create", "--name", "multiarch", "--use") -Description "Creating buildx builder: multiarch"
    } else {
        Invoke-DockerCommand -Arguments @("buildx", "use", "multiarch") -Description "Using buildx builder: multiarch"
    }

    Invoke-DockerCommand -Arguments @("buildx", "inspect", "--bootstrap") -Description "Bootstrapping buildx builder"

    if (-not $SkipBackend) {
        Invoke-DockerCommand \
            -Arguments @(
                "buildx", "build",
                "--platform", $Platforms,
                "-f", "docker/Dockerfile.backend.compiled.ubuntu",
                "--build-arg", "BASE_IMAGE=$backendBaseImage",
                "-t", $backendVersionImage,
                "--push",
                "."
            ) \
            -Description "Building and pushing backend image: $backendVersionImage"
    }

    if (-not $SkipFrontend) {
        Invoke-DockerCommand \
            -Arguments @(
                "buildx", "build",
                "--platform", $Platforms,
                "-f", "docker/Dockerfile.frontend",
                "-t", $frontendVersionImage,
                "--push",
                "."
            ) \
            -Description "Building and pushing frontend image: $frontendVersionImage"
    }

    if (-not $SkipLatestAlias) {
        if (-not $SkipBackend) {
            Invoke-DockerCommand \
                -Arguments @( "buildx", "imagetools", "create", "-t", $backendLatestImage, $backendVersionImage ) \
                -Description "Updating backend latest alias: $backendLatestImage -> $backendVersionImage"
        }

        if (-not $SkipFrontend) {
            Invoke-DockerCommand \
                -Arguments @( "buildx", "imagetools", "create", "-t", $frontendLatestImage, $frontendVersionImage ) \
                -Description "Updating frontend latest alias: $frontendLatestImage -> $frontendVersionImage"
        }
    }

    if (-not $SkipBackend) {
        Invoke-DockerCommand -Arguments @( "buildx", "imagetools", "inspect", $backendVersionImage ) -Description "Inspecting backend image: $backendVersionImage"
    }

    if (-not $SkipFrontend) {
        Invoke-DockerCommand -Arguments @( "buildx", "imagetools", "inspect", $frontendVersionImage ) -Description "Inspecting frontend image: $frontendVersionImage"
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "Release complete." -ForegroundColor Green
Write-Host "Deploy with IMAGE_TAG=$VersionTag in docker/.env or deployment env file." -ForegroundColor Green