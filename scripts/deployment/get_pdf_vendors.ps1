<#
下载 PDF 导出所需依赖（GTK3 运行时、wkhtmltopdf）
用于打包进安装程序，实现离线安装 PDF 导出功能。

用法:
  powershell -ExecutionPolicy Bypass -File scripts/deployment/get_pdf_vendors.ps1 -TargetDir install/vendors/pdf
  # 或使用离线方式：将 gtk3*.exe、wkhtmltox*.exe 放入 install/vendors/pdf/ 后运行 stage_local_vendors
#>

[CmdletBinding()]
param(
  [string]$TargetDir = "install/vendors/pdf",
  [switch]$Force
)

$ErrorActionPreference = "Stop"

function Ensure-Dir([string]$path) {
  if (-not (Test-Path -LiteralPath $path)) { New-Item -ItemType Directory -Path $path -Force | Out-Null }
}

function Download-File {
  param([string]$Name, [string]$Url, [string]$OutPath)
  if ((Test-Path -LiteralPath $OutPath) -and -not $Force) {
    Write-Host "$Name 已存在: $OutPath (使用 -Force 重新下载)" -ForegroundColor Yellow
    return $true
  }
  Write-Host "下载 $Name..." -ForegroundColor Cyan
  try {
    Invoke-WebRequest -Uri $Url -OutFile $OutPath -UseBasicParsing
    Write-Host "  $Name 下载完成" -ForegroundColor Green
    return $true
  } catch {
    Write-Host "  下载失败: $($_.Exception.Message)" -ForegroundColor Red
    return $false
  }
}

$root = (Resolve-Path ".").Path
$absTarget = if ([System.IO.Path]::IsPathRooted($TargetDir)) { $TargetDir } else { Join-Path $root $TargetDir }
Ensure-Dir $absTarget

# GTK3 运行时（WeasyPrint 依赖 libcairo、libgobject 等）
$gtk3Url = "https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases/download/2022-01-04/gtk3-runtime-3.24.31-2022-01-04-ts-win64.exe"
$gtk3Path = Join-Path $absTarget "gtk3-runtime-3.24.31-2022-01-04-ts-win64.exe"
Download-File -Name "GTK3 运行时" -Url $gtk3Url -OutPath $gtk3Path | Out-Null

# wkhtmltopdf（pdfkit 备选方案）
$wkhtmlUrl = "https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox-0.12.6.1-3.msvc2015-win64.exe"
$wkhtmlPath = Join-Path $absTarget "wkhtmltox-0.12.6.1-3.msvc2015-win64.exe"
Download-File -Name "wkhtmltopdf" -Url $wkhtmlUrl -OutPath $wkhtmlPath | Out-Null

Write-Host ""
Write-Host "PDF 依赖下载完成: $absTarget" -ForegroundColor Green
Write-Host "  可将此目录打包进安装程序，install_pdf_dependencies.ps1 将自动静默安装" -ForegroundColor Gray
