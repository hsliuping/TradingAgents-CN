# Quick script to check installed shortcuts and their icons
# Run this after installation to verify icon paths

Write-Host "🔍 Checking installed shortcuts..." -ForegroundColor Cyan
Write-Host ""

# Common shortcut locations
$locations = @(
    "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\TradingAgents-CN Pro",
    "$env:ALLUSERSPROFILE\Microsoft\Windows\Start Menu\Programs\TradingAgents-CN Pro",
    "C:\ProgramData\Microsoft\Windows\Start Menu\Programs\TradingAgents-CN Pro"
)

$foundAny = $false

foreach ($location in $locations) {
    if (Test-Path $location) {
        Write-Host "📁 Checking: $location" -ForegroundColor Yellow
        $shortcuts = Get-ChildItem -Path $location -Filter "*.lnk" -ErrorAction SilentlyContinue
        
        if ($shortcuts) {
            $foundAny = $true
            foreach ($shortcut in $shortcuts) {
                Write-Host ""
                Write-Host "  📋 $($shortcut.Name)" -ForegroundColor Green
                
                try {
                    $shell = New-Object -ComObject WScript.Shell
                    $lnk = $shell.CreateShortcut($shortcut.FullName)
                    
                    Write-Host "     Target: $($lnk.TargetPath)" -ForegroundColor Gray
                    Write-Host "     Icon: $($lnk.IconLocation)" -ForegroundColor Cyan
                    
                    # Parse icon location
                    $iconLocation = $lnk.IconLocation
                    if ($iconLocation) {
                        if ($iconLocation -match '^(.+),(\d+)$') {
                            $iconPath = $matches[1]
                            $iconIndex = [int]$matches[2]
                        } else {
                            $iconPath = $iconLocation
                            $iconIndex = 0
                        }
                        
                        Write-Host "     Icon file: $iconPath" -ForegroundColor White
                        Write-Host "     Icon index: $iconIndex" -ForegroundColor White
                        
                        if (Test-Path $iconPath) {
                            $iconFile = Get-Item $iconPath
                            Write-Host "     ✅ Icon file EXISTS ($($iconFile.Length) bytes)" -ForegroundColor Green
                            
                            if ($iconFile.Extension -eq '.ico') {
                                Write-Host "     📐 Type: ICO file" -ForegroundColor Gray
                            }
                        } else {
                            Write-Host "     ❌ Icon file NOT FOUND!" -ForegroundColor Red
                            Write-Host "     💡 This is why the icon appears white" -ForegroundColor Yellow
                        }
                    } else {
                        Write-Host "     ⚠️  No icon specified (using default)" -ForegroundColor Yellow
                    }
                } catch {
                    Write-Host "     ❌ Error: $_" -ForegroundColor Red
                }
            }
        }
    }
}

if (-not $foundAny) {
    Write-Host "❌ No shortcuts found in common locations" -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 If you installed the application, shortcuts should be in one of:" -ForegroundColor Yellow
    foreach ($location in $locations) {
        Write-Host "   - $location" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "💡 To check a specific shortcut manually:" -ForegroundColor Cyan
Write-Host '   $shell = New-Object -ComObject WScript.Shell' -ForegroundColor Gray
Write-Host '   $shortcut = $shell.CreateShortcut("<path_to_lnk_file>")' -ForegroundColor Gray
Write-Host '   $shortcut.IconLocation' -ForegroundColor Gray
