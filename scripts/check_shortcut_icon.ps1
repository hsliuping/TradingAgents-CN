# Check Windows shortcut icon information
# Usage: .\check_shortcut_icon.ps1 <shortcut_path>

param(
    [string]$ShortcutPath = ""
)

if ([string]::IsNullOrEmpty($ShortcutPath)) {
    # Try to find shortcuts in common locations
    $possiblePaths = @(
        "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\TradingAgents-CN Pro",
        "$env:ALLUSERSPROFILE\Microsoft\Windows\Start Menu\Programs\TradingAgents-CN Pro",
        "C:\ProgramData\Microsoft\Windows\Start Menu\Programs\TradingAgents-CN Pro"
    )
    
    $foundShortcuts = @()
    foreach ($path in $possiblePaths) {
        if (Test-Path $path) {
            $lnkFiles = Get-ChildItem -Path $path -Filter "*.lnk" -ErrorAction SilentlyContinue
            if ($lnkFiles) {
                $foundShortcuts += $lnkFiles
            }
        }
    }
    
    if ($foundShortcuts.Count -eq 0) {
        Write-Host "❌ No shortcuts found in common locations" -ForegroundColor Red
        Write-Host ""
        Write-Host "Usage: .\check_shortcut_icon.ps1 <shortcut_path>" -ForegroundColor Yellow
        Write-Host "Example: .\check_shortcut_icon.ps1 `"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\TradingAgents-CN Pro\Start TradingAgents-CN.lnk`"" -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host "📋 Found $($foundShortcuts.Count) shortcut(s):" -ForegroundColor Cyan
    foreach ($shortcut in $foundShortcuts) {
        Write-Host "   - $($shortcut.Name)" -ForegroundColor Gray
    }
    Write-Host ""
    
    # Check the first shortcut
    $ShortcutPath = $foundShortcuts[0].FullName
    Write-Host "🔍 Checking: $($foundShortcuts[0].Name)" -ForegroundColor Cyan
    Write-Host ""
}

if (-not (Test-Path $ShortcutPath)) {
    Write-Host "❌ File not found: $ShortcutPath" -ForegroundColor Red
    exit 1
}

Write-Host "📁 Shortcut path: $ShortcutPath" -ForegroundColor Yellow
Write-Host ""

try {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($ShortcutPath)
    
    Write-Host "🎯 Target file: $($shortcut.TargetPath)" -ForegroundColor Green
    Write-Host "📝 Arguments: $($shortcut.Arguments)" -ForegroundColor Gray
    Write-Host "💼 Working directory: $($shortcut.WorkingDirectory)" -ForegroundColor Gray
    Write-Host "📋 Description: $($shortcut.Description)" -ForegroundColor Gray
    Write-Host ""
    
    $iconLocation = $shortcut.IconLocation
    Write-Host "🖼️  Icon location: $iconLocation" -ForegroundColor Cyan
    Write-Host ""
    
    if ($iconLocation) {
        # Parse icon location (format: "path,index")
        if ($iconLocation -match '^(.+),(\d+)$') {
            $iconPath = $matches[1]
            $iconIndex = [int]$matches[2]
        } else {
            $iconPath = $iconLocation
            $iconIndex = 0
        }
        
        Write-Host "🔍 Icon details:" -ForegroundColor Yellow
        Write-Host "   Icon file: $iconPath" -ForegroundColor White
        Write-Host "   Icon index: $iconIndex" -ForegroundColor White
        
        if (Test-Path $iconPath) {
            $iconFile = Get-Item $iconPath
            Write-Host "   ✅ Icon file exists" -ForegroundColor Green
            Write-Host "   📦 File size: $($iconFile.Length) bytes" -ForegroundColor Gray
            
            # Check if it's an .ico file
            if ($iconFile.Extension -eq '.ico') {
                Write-Host "   📐 File type: ICO" -ForegroundColor Gray
                Write-Host ""
                Write-Host "💡 Checking icon sizes..." -ForegroundColor Cyan
                
                # Call Python script to check icon sizes
                $checkScript = Join-Path $PSScriptRoot "check_icon_info.py"
                if (Test-Path $checkScript) {
                    $result = & python $checkScript $iconPath 2>&1
                    Write-Host $result
                } else {
                    Write-Host "   ⚠️  check_icon_info.py not found" -ForegroundColor Yellow
                }
            } elseif ($iconFile.Extension -eq '.exe' -or $iconFile.Extension -eq '.dll') {
                Write-Host "   📐 File type: $($iconFile.Extension) (using icon index $iconIndex)" -ForegroundColor Gray
                Write-Host "   💡 This is an executable file, icon index $iconIndex will be used" -ForegroundColor Yellow
            }
        } else {
            Write-Host "   ❌ Icon file does NOT exist!" -ForegroundColor Red
            Write-Host "   💡 This is likely why the icon appears white" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "   Possible reasons:" -ForegroundColor Yellow
            Write-Host "   1. Icon file was not copied during installation" -ForegroundColor Gray
            Write-Host "   2. Icon path is incorrect" -ForegroundColor Gray
            Write-Host "   3. Installation directory is different than expected" -ForegroundColor Gray
        }
    } else {
        Write-Host "   ⚠️  No icon specified (using default icon)" -ForegroundColor Yellow
        Write-Host "   💡 This is why the icon appears white" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "❌ Error checking shortcut: $_" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
