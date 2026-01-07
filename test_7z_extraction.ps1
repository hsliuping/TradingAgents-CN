# Test 7z extraction speed

$7zFile = "release\packages\TradingAgentsCN-Portable-1.0.2-20260107-215121.7z"
$zipFile = "release\packages\TradingAgentsCN-Portable-latest.zip"
$testDir = "$env:TEMP\7z_test"

# Clean up test directory
if (Test-Path $testDir) {
    Remove-Item -Path $testDir -Recurse -Force
}
New-Item -ItemType Directory -Path $testDir -Force | Out-Null

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "7-Zip Extraction Speed Test" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Test 1: Extract 7z file
Write-Host "Test 1: Extracting 7z file (230 MB)..." -ForegroundColor Yellow
$7zExtractDir = Join-Path $testDir "7z_extract"
New-Item -ItemType Directory -Path $7zExtractDir -Force | Out-Null

$startTime = Get-Date
& "vendors\7zip\7z.exe" x $7zFile -o"$7zExtractDir" -y | Out-Null
$endTime = Get-Date
$7zDuration = ($endTime - $startTime).TotalSeconds

Write-Host "  Extraction completed in $([math]::Round($7zDuration, 2)) seconds" -ForegroundColor Green
Write-Host ""

# Test 2: Extract ZIP file
Write-Host "Test 2: Extracting ZIP file (396 MB)..." -ForegroundColor Yellow
$zipExtractDir = Join-Path $testDir "zip_extract"
New-Item -ItemType Directory -Path $zipExtractDir -Force | Out-Null

$startTime = Get-Date
Expand-Archive -Path $zipFile -DestinationPath $zipExtractDir -Force
$endTime = Get-Date
$zipDuration = ($endTime - $startTime).TotalSeconds

Write-Host "  Extraction completed in $([math]::Round($zipDuration, 2)) seconds" -ForegroundColor Green
Write-Host ""

# Summary
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Summary" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "7z file:" -ForegroundColor White
Write-Host "  Size: 230 MB" -ForegroundColor Gray
Write-Host "  Time: $([math]::Round($7zDuration, 2)) seconds" -ForegroundColor Gray
Write-Host ""
Write-Host "ZIP file:" -ForegroundColor White
Write-Host "  Size: 396 MB" -ForegroundColor Gray
Write-Host "  Time: $([math]::Round($zipDuration, 2)) seconds" -ForegroundColor Gray
Write-Host ""

$speedup = $zipDuration / $7zDuration
$timeSaved = $zipDuration - $7zDuration

Write-Host "Results:" -ForegroundColor Green
Write-Host "  File size reduction: 41.8% smaller" -ForegroundColor Green
Write-Host "  Speed improvement: $([math]::Round($speedup, 2))x faster" -ForegroundColor Green
Write-Host "  Time saved: $([math]::Round($timeSaved, 2)) seconds" -ForegroundColor Green
Write-Host ""

# Clean up
Write-Host "Cleaning up test directory..." -ForegroundColor Gray
Remove-Item -Path $testDir -Recurse -Force
Write-Host "Done!" -ForegroundColor Green

