<#
.SYNOPSIS
    Archive release artifacts to a versioned directory tree and generate upload metadata.
.DESCRIPTION
    Copies final artifacts from release/packages to D:\release\<version>\revNNN\
    and writes BUILD_INFO/manifest snapshots plus a backend upload guide.
.PARAMETER Version
    Base semantic version, such as 2.0.1. If omitted, read from BUILD_INFO.
.PARAMETER FullVersion
    Full build version, such as 2.0.1-build20260312-204340. If omitted, read from BUILD_INFO.
.PARAMETER ArchiveRoot
    Root archive directory. Default: D:\release
.PARAMETER PackagesDir
    Directory containing built artifacts. Default: <project>\release\packages
.PARAMETER ProjectRoot
    Project root directory.
#>

param(
    [string]$Version = "",
    [string]$FullVersion = "",
    [string]$ArchiveRoot = "D:\release",
    [string]$PackagesDir = "",
    [string]$ProjectRoot = "",
    [switch]$CreateGitTag = $true,
    [switch]$ArchiveSourceSnapshot = $true
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] [$Level] $Message"
}

function Get-NextArchiveRevisionName {
    param([string]$VersionRoot)

    if (-not (Test-Path $VersionRoot)) {
        return "rev001"
    }

    $revisions = Get-ChildItem -Path $VersionRoot -Directory |
        ForEach-Object {
            $match = [regex]::Match($_.Name, '^rev(\d{3})$')
            if ($match.Success) {
                [int]$match.Groups[1].Value
            }
        }

    if (-not $revisions) {
        return "rev001"
    }

    $maxRevision = [int](($revisions | Measure-Object -Maximum).Maximum)
    $nextRevision = $maxRevision + 1
    return ('rev{0:D3}' -f $nextRevision)
}

function Get-ArtifactSha256 {
    param(
        [string]$FilePath,
        [string]$ChecksumFile = ""
    )

    if ($ChecksumFile -and (Test-Path $ChecksumFile)) {
        $checksumText = (Get-Content $ChecksumFile -Raw).Trim()
        if ($checksumText -match '^(?<hash>[a-fA-F0-9]{64})\s+') {
            return $Matches.hash.ToLower()
        }
    }

    return (Get-FileHash -Path $FilePath -Algorithm SHA256).Hash.ToLower()
}

function Format-SizeMb {
    param([long]$Bytes)
    return ([math]::Round($Bytes / 1MB, 2)).ToString("0.00")
}

function Get-GitOutput {
    param(
        [string[]]$Arguments,
        [switch]$AllowFailure = $false
    )

    $result = & git -C $ProjectRoot @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        if ($AllowFailure) {
            return ""
        }

        $errorText = ($result | Out-String).Trim()
        throw "Git command failed: git -C $ProjectRoot $($Arguments -join ' ')`n$errorText"
    }

    return ($result | Out-String).TrimEnd()
}

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\.." )).Path
}

if (-not $PackagesDir) {
    $PackagesDir = Join-Path $ProjectRoot "release\packages"
}

$buildInfoPath = Join-Path $ProjectRoot "BUILD_INFO"
if (-not (Test-Path $buildInfoPath)) {
    throw "BUILD_INFO not found: $buildInfoPath"
}

$buildInfo = Get-Content $buildInfoPath -Raw | ConvertFrom-Json

if (-not $Version) {
    $Version = $buildInfo.version
}
if (-not $FullVersion) {
    $FullVersion = $buildInfo.full_version
}

if (-not $Version -or -not $FullVersion) {
    throw "Version or FullVersion is empty. BUILD_INFO is incomplete."
}

$archiveDrive = Split-Path -Path $ArchiveRoot -Qualifier
if ($archiveDrive -and -not (Test-Path $archiveDrive)) {
    throw "Archive drive not available: $archiveDrive"
}

if (-not (Test-Path $PackagesDir)) {
    throw "Packages directory not found: $PackagesDir"
}

if (-not (Test-Path $ArchiveRoot)) {
    New-Item -ItemType Directory -Path $ArchiveRoot -Force | Out-Null
}

$versionRoot = Join-Path $ArchiveRoot $Version
$revisionName = Get-NextArchiveRevisionName -VersionRoot $versionRoot
$archiveDir = Join-Path $versionRoot $revisionName
New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null

$headCommit = ((Get-GitOutput -Arguments @('rev-parse', '--short', 'HEAD')).Trim())
$headCommitFull = ((Get-GitOutput -Arguments @('rev-parse', 'HEAD')).Trim())
$headSubject = ((Get-GitOutput -Arguments @('log', '-1', '--pretty=%s')).Trim())
$gitStatusShort = (Get-GitOutput -Arguments @('status', '--short') -AllowFailure)
$gitTagName = "v$Version-$revisionName"
$gitTagCreated = $false

if ($CreateGitTag) {
    $existingTagCommit = (Get-GitOutput -Arguments @('rev-parse', '-q', '--verify', "refs/tags/$gitTagName^{commit}") -AllowFailure).Trim()
    if (-not $existingTagCommit) {
        Get-GitOutput -Arguments @('tag', '-a', $gitTagName, '-m', "Release $Version $revisionName ($FullVersion)", $headCommitFull) | Out-Null
        $gitTagCreated = $true
    } elseif ($existingTagCommit -ne $headCommitFull) {
        throw "Git tag $gitTagName already exists on commit $existingTagCommit, expected $headCommitFull"
    }
}

$installerFile = Join-Path $PackagesDir "TradingAgentsCNSetup-$FullVersion.exe"
$updateZipFile = Join-Path $PackagesDir "update-$FullVersion.zip"
$updateShaFile = Join-Path $PackagesDir "update-$FullVersion.sha256"
$portableArchive = Join-Path $PackagesDir "TradingAgentsCN-Portable-$FullVersion-installer.7z"
$manifestPath = Join-Path $ProjectRoot "releases\$Version\manifest.json"
$releaseNotesPath = Join-Path $ProjectRoot "RELEASE_NOTES_v$Version.md"

$releaseDate = ""
if (Test-Path $manifestPath) {
    try {
        $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
        $releaseDate = $manifest.release_date
    } catch {
        $releaseDate = ""
    }
}
if (-not $releaseDate) {
    $releaseDate = ([string]$buildInfo.build_date).Substring(0, 10)
}

$artifacts = @()

if (Test-Path $installerFile) {
    Copy-Item -Path $installerFile -Destination (Join-Path $archiveDir (Split-Path $installerFile -Leaf)) -Force
    $installerInfo = Get-Item $installerFile
    $installerHash = Get-ArtifactSha256 -FilePath $installerFile
    $artifacts += [pscustomobject]@{
        type = "installer"
        file_name = $installerInfo.Name
        bytes = [int64]$installerInfo.Length
        size_mb = Format-SizeMb -Bytes $installerInfo.Length
        sha256 = $installerHash
        package_type = "installer"
        download_url = "https://www.tradingagentscn.com/downloads/$($installerInfo.Name)"
    }
}

if (Test-Path $updateZipFile) {
    Copy-Item -Path $updateZipFile -Destination (Join-Path $archiveDir (Split-Path $updateZipFile -Leaf)) -Force
    if (Test-Path $updateShaFile) {
        Copy-Item -Path $updateShaFile -Destination (Join-Path $archiveDir (Split-Path $updateShaFile -Leaf)) -Force
    }

    $updateInfo = Get-Item $updateZipFile
    $updateHash = Get-ArtifactSha256 -FilePath $updateZipFile -ChecksumFile $updateShaFile
    $artifacts += [pscustomobject]@{
        type = "update"
        file_name = $updateInfo.Name
        bytes = [int64]$updateInfo.Length
        size_mb = Format-SizeMb -Bytes $updateInfo.Length
        sha256 = $updateHash
        package_type = "update"
        download_url = "https://www.tradingagentscn.com/downloads/$($updateInfo.Name)"
    }
}

if (Test-Path $portableArchive) {
    Copy-Item -Path $portableArchive -Destination (Join-Path $archiveDir (Split-Path $portableArchive -Leaf)) -Force
}

$archivedBuildInfoName = "BUILD_INFO-$FullVersion.json"
Copy-Item -Path $buildInfoPath -Destination (Join-Path $archiveDir $archivedBuildInfoName) -Force

if (Test-Path $manifestPath) {
    Copy-Item -Path $manifestPath -Destination (Join-Path $archiveDir "manifest-$Version.json") -Force
}

if (Test-Path $releaseNotesPath) {
    Copy-Item -Path $releaseNotesPath -Destination (Join-Path $archiveDir (Split-Path $releaseNotesPath -Leaf)) -Force
}

$gitShowPath = Join-Path $archiveDir "GIT_COMMIT_INFO.txt"
Get-GitOutput -Arguments @('show', '--stat', '--summary', '--no-patch', $headCommitFull) | Set-Content -Path $gitShowPath -Encoding UTF8

$gitStatusPath = Join-Path $archiveDir "GIT_STATUS.txt"
if (($gitStatusShort | Out-String).Trim()) {
    ($gitStatusShort | Out-String).TrimEnd() | Set-Content -Path $gitStatusPath -Encoding UTF8
} else {
    "Working tree clean at archive time." | Set-Content -Path $gitStatusPath -Encoding UTF8
}

$sourceSnapshotFileName = "TradingAgentsCN-source-$FullVersion.zip"
if ($ArchiveSourceSnapshot) {
    $sourceSnapshotPath = Join-Path $archiveDir $sourceSnapshotFileName
    & git -C $ProjectRoot archive --format=zip --output=$sourceSnapshotPath $headCommitFull 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create source snapshot: $sourceSnapshotPath"
    }
}

$gitMetadataPath = Join-Path $archiveDir "git_release_info.json"
([ordered]@{
    tag_name = $gitTagName
    tag_created = $gitTagCreated
    head_commit = $headCommit
    head_commit_full = $headCommitFull
    head_subject = $headSubject
    working_tree_clean = -not (($gitStatusShort | Out-String).Trim())
    source_snapshot = $(if ($ArchiveSourceSnapshot) { $sourceSnapshotFileName } else { "" })
} | ConvertTo-Json -Depth 4) | Set-Content -Path $gitMetadataPath -Encoding UTF8

$metadata = [ordered]@{
    archive_root = $ArchiveRoot
    archive_version_dir = $versionRoot
    archive_dir = $archiveDir
    archive_revision = $revisionName
    version = $Version
    full_version = $FullVersion
    build_type = $buildInfo.build_type
    build_timestamp = $buildInfo.build_timestamp
    build_date = $buildInfo.build_date
    git_commit = $buildInfo.git_commit
    git_tag = $gitTagName
    git_tag_created = $gitTagCreated
    git_head_subject = $headSubject
    source_snapshot = $(if ($ArchiveSourceSnapshot) { $sourceSnapshotFileName } else { "" })
    release_date = $releaseDate
    artifacts = $artifacts
}

$metadataPath = Join-Path $archiveDir "release_metadata.json"
$metadata | ConvertTo-Json -Depth 6 | Set-Content -Path $metadataPath -Encoding UTF8

$installerArtifact = $artifacts | Where-Object { $_.type -eq "installer" } | Select-Object -First 1
$updateArtifact = $artifacts | Where-Object { $_.type -eq "update" } | Select-Object -First 1

$markdownLines = @(
    "# Release Upload Guide",
    "",
    "- Archive root: $ArchiveRoot",
    "- Version: $Version",
    "- Archive revision: $revisionName",
    "- Full version: $FullVersion",
    "- Build type: $($buildInfo.build_type)",
    "- Build timestamp: $($buildInfo.build_timestamp)",
    "- Build date (UTC): $($buildInfo.build_date)",
    "- Git commit: $($buildInfo.git_commit)",
    "- Git tag: $gitTagName",
    "- Git tag created this run: $(if ($gitTagCreated) { 'yes' } else { 'no' })",
    "- Source snapshot: $(if ($ArchiveSourceSnapshot) { $sourceSnapshotFileName } else { 'disabled' })",
    "- Release date: $releaseDate",
    "",
    "## Archived Files",
    ""
)

foreach ($artifact in $artifacts) {
    $markdownLines += "- $($artifact.type): $($artifact.file_name)"
    $markdownLines += "  - Bytes: $($artifact.bytes)"
    $markdownLines += "  - Size MB: $($artifact.size_mb)"
    $markdownLines += "  - SHA256: $($artifact.sha256)"
    $markdownLines += "  - Download URL: $($artifact.download_url)"
}

$markdownLines += ""
$markdownLines += "## Website Backend Draft"
$markdownLines += ""

if ($installerArtifact) {
    $installerPayload = [ordered]@{
        version = $Version
        channel = "stable"
        package_type = "installer"
        build_type = "installer"
        download_url = $installerArtifact.download_url
        file_size = $installerArtifact.bytes
        sha256 = $installerArtifact.sha256
        release_date = $releaseDate
        is_mandatory = $false
        min_version = ""
    }
    $markdownLines += "### Installer"
    $markdownLines += '```json'
    $markdownLines += (($installerPayload | ConvertTo-Json -Depth 4) -split "`r?`n")
    $markdownLines += '```'
    $markdownLines += ""
}

if ($updateArtifact) {
    $updatePayload = [ordered]@{
        version = $Version
        channel = "stable"
        package_type = "update"
        build_type = "installer"
        download_url = $updateArtifact.download_url
        file_size = $updateArtifact.bytes
        sha256 = $updateArtifact.sha256
        release_date = $releaseDate
        is_mandatory = $false
        min_version = ""
    }
    $markdownLines += "### Update Package"
    $markdownLines += '```json'
    $markdownLines += (($updatePayload | ConvertTo-Json -Depth 4) -split "`r?`n")
    $markdownLines += '```'
    $markdownLines += ""
}

$markdownLines += "## Notes"
$markdownLines += ""
$markdownLines += "- file_size uses exact byte counts for backend entry."
$markdownLines += "- min_version and is_mandatory should be confirmed before publishing."
$markdownLines += "- Update package is for in-app upgrade flow; installer is the public Windows download."
$markdownLines += "- Each revNNN archive is bound to a git tag and a source snapshot for reverse lookup."

$guidePath = Join-Path $archiveDir "RELEASE_UPLOAD_INFO.md"
$markdownLines | Set-Content -Path $guidePath -Encoding UTF8

Write-Log "Release artifacts archived to: $archiveDir"
Write-Log "Upload guide written: $guidePath"
Write-Host "ARCHIVE_DIR=$archiveDir"
