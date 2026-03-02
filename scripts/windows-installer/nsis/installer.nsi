!include "MUI2.nsh"
!include "nsDialogs.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"

!define PRODUCT_NAME "TradingAgentsCN"
!ifndef PRODUCT_VERSION
  !define PRODUCT_VERSION "1.0.0"
!endif
!ifndef BACKEND_PORT
  !define BACKEND_PORT "8000"
!endif
!ifndef MONGO_PORT
  !define MONGO_PORT "27017"
!endif
!ifndef REDIS_PORT
  !define REDIS_PORT "6379"
!endif
!ifndef NGINX_PORT
  !define NGINX_PORT "80"
!endif
; Worker port removed - Worker is now integrated in Backend process
!ifndef PACKAGE_ZIP
  !define PACKAGE_ZIP "C:\\TradingAgentsCN\\release\\packages\\TradingAgentsCN-Portable-latest.zip"
!endif
!ifndef PACKAGE_7Z
  !define PACKAGE_7Z "C:\\TradingAgentsCN\\release\\packages\\TradingAgentsCN-Portable-latest-installer.7z"
!endif
!ifndef OUTPUT_DIR
  !define OUTPUT_DIR "C:\\TradingAgentsCN\\release\\packages"
!endif
!ifndef PROJECT_ROOT
  !define PROJECT_ROOT "C:\\TradingAgentsCN"
!endif
!ifndef SEVENZIP_DIR
  !define SEVENZIP_DIR "C:\\TradingAgentsCN\\vendors\\7zip"
!endif

Name "${PRODUCT_NAME}"
OutFile "${OUTPUT_DIR}\TradingAgentsCNSetup-${PRODUCT_VERSION}.exe"
InstallDir "C:\TradingAgentsCN"
RequestExecutionLevel admin
SetDatablockOptimize on
; Use zlib for small files (faster), don't compress the 7z package (already compressed)
SetCompressor /SOLID zlib

Var BackendPort
Var MongoPort
Var RedisPort
Var NginxPort
; Worker port removed - Worker is now integrated in Backend process
Var hBackendEdit
Var hMongoEdit
Var hRedisEdit
Var hNginxEdit
; Install mode: 0=fresh, 1=upgrade (preserve config), 2=overwrite (backup then full overwrite)
Var InstallMode
Var hUpgradeRadio
Var hOverwriteRadio

; Generate random 4-digit port in safe range (avoiding common ports)
; Uses ranges: 4100-4999, 5100-5999, 6100-6299, 7100-7999, 9100-9999
; Avoids: 3000, 3306, 5000, 6000, 6379, 7000, 8000-9000, etc.
Function GenerateRandomPort
 Push $0
 Push $1

 ; Get tick count as seed
 System::Call 'kernel32::GetTickCount()i.r0'

 ; Generate random port in range 4100-4999 (900 ports)
 IntOp $1 $0 % 900
 IntOp $1 $1 + 4100

 ; Return value in $0
 StrCpy $0 $1

 Pop $1
 Exch $0
FunctionEnd

Function .onInit
 ; Generate 5 different random ports in safe ranges

 ; Backend: Random port 4100-4999
 System::Call 'kernel32::GetTickCount()i.r0'
 IntOp $0 $0 % 900
 IntOp $BackendPort $0 + 4100

 ; Worker port removed - Worker is now integrated in Backend process

 ; MongoDB: Random port 5100-5999 (avoiding 5000, 5432)
 System::Call 'kernel32::GetTickCount()i.r0'
 IntOp $0 $0 + 100
 IntOp $0 $0 % 900
 IntOp $MongoPort $0 + 5100

 ; Redis: Random port 7100-7999 (avoiding 6379, 7000)
 System::Call 'kernel32::GetTickCount()i.r0'
 IntOp $0 $0 + 200
 IntOp $0 $0 % 900
 IntOp $RedisPort $0 + 7100

 ; Nginx: Random port 9100-9999 (avoiding 8000-9000, 9200, 9300)
 System::Call 'kernel32::GetTickCount()i.r0'
 IntOp $0 $0 + 300
 IntOp $0 $0 % 900
 IntOp $NginxPort $0 + 9100

 ; Default: fresh install
 StrCpy $InstallMode 0
FunctionEnd

Function PortsPage
 nsDialogs::Create 1018
 Pop $0
 ${If} $0 == error
   Abort
${EndIf}

${NSD_CreateLabel} 0 0 100% 12u "Configure Ports for Installation"
${NSD_CreateLabel} 0 14u 100% 24u "Random ports have been generated to avoid conflicts. Modify if needed.$\nPorts must be 4-digit numbers (1024-65535). Ensure all ports are different."

${NSD_CreateLabel} 0 42u 45% 12u "Backend Port (includes Thread Pool Worker)"
 ${NSD_CreateText} 50% 40u 35% 12u "$BackendPort"
 Pop $hBackendEdit

${NSD_CreateLabel} 0 57u 45% 12u "MongoDB Port"
 ${NSD_CreateText} 50% 55u 35% 12u "$MongoPort"
 Pop $hMongoEdit

${NSD_CreateLabel} 0 72u 45% 12u "Redis Port"
 ${NSD_CreateText} 50% 70u 35% 12u "$RedisPort"
 Pop $hRedisEdit

${NSD_CreateLabel} 0 87u 45% 12u "Nginx Port"
 ${NSD_CreateText} 50% 85u 35% 12u "$NginxPort"
 Pop $hNginxEdit

 nsDialogs::Show
FunctionEnd


Function PortsPageLeave
 ${NSD_GetText} $hBackendEdit $BackendPort
 ${NSD_GetText} $hMongoEdit $MongoPort
 ${NSD_GetText} $hRedisEdit $RedisPort
 ${NSD_GetText} $hNginxEdit $NginxPort

 ; Validate port number format
 ${If} $BackendPort == ""
  MessageBox MB_ICONSTOP "Backend port cannot be empty"
  Abort
 ${EndIf}
 ${If} $MongoPort == ""
  MessageBox MB_ICONSTOP "MongoDB port cannot be empty"
  Abort
 ${EndIf}
 ${If} $RedisPort == ""
  MessageBox MB_ICONSTOP "Redis port cannot be empty"
  Abort
 ${EndIf}
 ${If} $NginxPort == ""
  MessageBox MB_ICONSTOP "Nginx port cannot be empty"
  Abort
 ${EndIf}

 ; Validate port range
 ${If} $BackendPort < 1024
  MessageBox MB_ICONSTOP "Backend port must be >= 1024"
  Abort
 ${EndIf}
 ${If} $MongoPort < 1024
  MessageBox MB_ICONSTOP "MongoDB port must be >= 1024"
  Abort
 ${EndIf}
 ${If} $RedisPort < 1024
  MessageBox MB_ICONSTOP "Redis port must be >= 1024"
  Abort
 ${EndIf}
 ${If} $BackendPort > 65535
  MessageBox MB_ICONSTOP "Backend port must be <= 65535"
  Abort
 ${EndIf}
 ${If} $MongoPort > 65535
  MessageBox MB_ICONSTOP "MongoDB port must be <= 65535"
  Abort
 ${EndIf}
 ${If} $RedisPort > 65535
  MessageBox MB_ICONSTOP "Redis port must be <= 65535"
  Abort
 ${EndIf}
 ${If} $NginxPort > 65535
  MessageBox MB_ICONSTOP "Nginx port must be <= 65535"
  Abort
 ${EndIf}

 ; Validate no duplicate ports
 ${If} $BackendPort == $MongoPort
  MessageBox MB_ICONSTOP "Backend port duplicates MongoDB port"
  Abort
 ${EndIf}
 ${If} $BackendPort == $RedisPort
  MessageBox MB_ICONSTOP "Backend port duplicates Redis port"
  Abort
 ${EndIf}
 ${If} $BackendPort == $NginxPort
  MessageBox MB_ICONSTOP "Backend port duplicates Nginx port"
  Abort
 ${EndIf}
 ${If} $MongoPort == $RedisPort
  MessageBox MB_ICONSTOP "MongoDB port duplicates Redis port"
  Abort
 ${EndIf}
 ${If} $MongoPort == $NginxPort
  MessageBox MB_ICONSTOP "MongoDB port duplicates Nginx port"
  Abort
 ${EndIf}
 ${If} $RedisPort == $NginxPort
  MessageBox MB_ICONSTOP "Redis port duplicates Nginx port"
  Abort
 ${EndIf}


 FunctionEnd

; Install mode page: show when existing install detected (after Directory page)
Function InstallModePage
 ; Only show when $INSTDIR exists and has TradingAgentsCN installation
 IfFileExists "$INSTDIR\.env" 0 check_start
 Goto show_mode
check_start:
 IfFileExists "$INSTDIR\start_all.ps1" 0 check_vendors
 Goto show_mode
check_vendors:
 IfFileExists "$INSTDIR\vendors" 0 skip_mode
show_mode:
 nsDialogs::Create 1018
 Pop $0
 ${If} $0 == error
   Abort
 ${EndIf}

 ${NSD_CreateLabel} 0 0 100% 12u "Detected existing TradingAgentsCN installation"
 Pop $0
 ${NSD_CreateLabel} 0 14u 100% 36u "The selected directory already contains a TradingAgentsCN installation.$\n$\nChoose installation mode:$\n$\nUpgrade: Preserve your configuration and data, only update program files.$\nOverwrite: Backup current data first, then perform full overwrite (config will use new port settings)."
 Pop $0

 ${NSD_CreateRadioButton} 0 55u 100% 12u "Upgrade install - Preserve configuration and data"
 Pop $hUpgradeRadio
 ${NSD_Check} $hUpgradeRadio

 ${NSD_CreateRadioButton} 0 70u 100% 12u "Overwrite install - Backup data, then full overwrite"
 Pop $hOverwriteRadio

 nsDialogs::Show
 Return
skip_mode:
 ; Fresh install, skip this page
 StrCpy $InstallMode 0
 Abort
FunctionEnd

Function InstallModePageLeave
 ${NSD_GetState} $hUpgradeRadio $0
 ${If} $0 == 1
   StrCpy $InstallMode 1
 ${Else}
   StrCpy $InstallMode 2
 ${EndIf}
FunctionEnd

; Icon configuration
!define MUI_ICON "${PROJECT_ROOT}\frontend\dist\favicon.ico"
!define MUI_UNICON "${PROJECT_ROOT}\frontend\dist\favicon.ico"

!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Launch TradingAgentsCN"
!define MUI_FINISHPAGE_RUN_FUNCTION "LaunchApplication"

Page custom PortsPage PortsPageLeave
!insertmacro MUI_PAGE_DIRECTORY
Page custom InstallModePage InstallModePageLeave
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function LaunchApplication
 ; Launch with admin privileges
 ExecShell "runas" "powershell" '-ExecutionPolicy Bypass -NoExit -File "$INSTDIR\start_all.ps1"'
FunctionEnd

Section
SetOutPath "$INSTDIR"

; Backup existing config and data when upgrade or overwrite (InstallMode 1 or 2)
${If} $InstallMode >= 1
  DetailPrint "Backing up existing configuration and data..."
  nsExec::ExecToLog 'powershell -ExecutionPolicy Bypass -Command "$$instDir = ''$INSTDIR''; $$backupRoot = Join-Path $$instDir ''backup''; $$ts = Get-Date -Format ''yyyyMMdd_HHmmss''; $$backupDir = Join-Path $$backupRoot (''pre_install_'' + $$ts); if (-not (Test-Path $$backupRoot)) { New-Item -ItemType Directory -Path $$backupRoot -Force | Out-Null }; New-Item -ItemType Directory -Path $$backupDir -Force | Out-Null; $$items = @(''.env'', ''runtime'', ''data'', ''logs''); foreach ($$item in $$items) { $$src = Join-Path $$instDir $$item; if (Test-Path $$src) { $$dst = Join-Path $$backupDir $$item; Copy-Item -Path $$src -Destination $$dst -Recurse -Force -ErrorAction SilentlyContinue; Write-Host (''Backed up: '' + $$item) } }; Write-Host (''Backup completed: '' + $$backupDir)"'
  Pop $0
  DetailPrint "Backup completed to backup\pre_install_*"
${EndIf}

; Copy 7z.exe and 7z.dll to temp directory for extraction
DetailPrint "Preparing extraction tools..."
SetOutPath "$TEMP\TradingAgentsCN-Install"
File "${SEVENZIP_DIR}\7z.exe"
File "${SEVENZIP_DIR}\7z.dll"

; Extract the portable package 7z file (stored without compression)
DetailPrint "Extracting portable package..."
SetOutPath "$INSTDIR"
SetCompress off
File /oname=package.7z "${PACKAGE_7Z}"
SetCompress auto

; Extract 7z using 7z.exe
DetailPrint "Unpacking files (this may take a few minutes)..."
nsExec::ExecToLog '"$TEMP\TradingAgentsCN-Install\7z.exe" x "$INSTDIR\package.7z" -o"$INSTDIR" -y'
Pop $0

${If} $0 != 0
  MessageBox MB_ICONSTOP "Failed to extract package. Error code: $0"
  Abort
${EndIf}

; Remove the 7z file and temp tools after extraction
Delete "$INSTDIR\package.7z"
Delete "$TEMP\TradingAgentsCN-Install\7z.exe"
Delete "$TEMP\TradingAgentsCN-Install\7z.dll"
RMDir "$TEMP\TradingAgentsCN-Install"

; Restore config and data when upgrade (InstallMode 1)
${If} $InstallMode == 1
  DetailPrint "Restoring configuration and data (upgrade mode)..."
  nsExec::ExecToLog 'powershell -ExecutionPolicy Bypass -Command "$$instDir = ''$INSTDIR''; $$backupRoot = Join-Path $$instDir ''backup''; $$latest = Get-ChildItem -Path $$backupRoot -Directory -Filter ''pre_install_*'' | Sort-Object CreationTime -Descending | Select-Object -First 1; if ($$latest) { $$items = @(''.env'', ''runtime'', ''data'', ''logs''); foreach ($$item in $$items) { $$src = Join-Path $$latest.FullName $$item; $$dst = Join-Path $$instDir $$item; if (Test-Path $$src) { if (Test-Path $$dst) { Remove-Item -Path $$dst -Recurse -Force -ErrorAction SilentlyContinue }; Copy-Item -Path $$src -Destination $$dst -Recurse -Force; Write-Host (''Restored: '' + $$item) } }; Write-Host (''Restore completed from '' + $$latest.Name) }"'
  Pop $0
  DetailPrint "Configuration and data restored"
${EndIf}

; Install Visual C++ Redistributable (required by MongoDB 8.0)
DetailPrint "Installing Visual C++ Redistributable..."
nsExec::ExecToLog '"$INSTDIR\vendors\mongodb\mongodb-win32-x86_64-windows-8.0.13\bin\vc_redist.x64.exe" /quiet /norestart'
Pop $0
${If} $0 == 0
  DetailPrint "Visual C++ Redistributable installed successfully"
${ElseIf} $0 == 3010
  DetailPrint "Visual C++ Redistributable installed (reboot may be needed)"
${Else}
  DetailPrint "Visual C++ Redistributable returned code: $0 (may already be installed)"
${EndIf}

; Install PDF/Word export dependencies (GTK3, wkhtmltopdf, Pandoc) - silent install if bundled
; .exe: NSIS installer uses /S ; .msi: msiexec /i path /quiet
DetailPrint "Installing PDF/Word export dependencies..."
StrCpy $0 "$INSTDIR\vendors\pdf"
${If} ${FileExists} "$0"
  nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -Command "$$d = ''$INSTDIR\vendors\pdf''; if (Test-Path $$d) { Get-ChildItem $$d -File | Where-Object { $$_.Extension -in ''.exe'',''.msi'' } | ForEach-Object { Write-Host (''Running: '' + $$_.Name); if ($$_.Extension -eq ''.msi'') { $$p = Start-Process msiexec.exe -ArgumentList ''/i'',$$_.FullName,''/quiet'' -Wait -PassThru } else { $$p = Start-Process -FilePath $$_.FullName -ArgumentList ''/S'' -Wait -PassThru }; Write-Host (''Exit: '' + $$p.ExitCode) } }"'
  Pop $0
  DetailPrint "PDF/Word dependencies install completed"
${Else}
  DetailPrint "No bundled PDF/Word dependencies (vendors\pdf empty or missing)"
${EndIf}

; Update configuration files with user-selected ports (skip when upgrade - InstallMode 1)
${If} $InstallMode != 1
  DetailPrint "Updating configuration..."

  ; Create .env from .env.example if .env does not exist (fresh install or overwrite)
  nsExec::ExecToLog 'powershell -ExecutionPolicy Bypass -Command "$$envFile = \"$INSTDIR\.env\"; $$envExample = \"$INSTDIR\.env.example\"; if (-not (Test-Path $$envFile) -and (Test-Path $$envExample)) { Copy-Item -Path $$envExample -Destination $$envFile -Force; Write-Host (''Created .env from .env.example'') }"'
  Pop $0

  ; Update .env file (update port configurations)
  ; Note: MONGODB_CONNECTION_STRING will be auto-built from MONGODB_HOST/PORT, no need to update it
  ; Note: WORKER_PORT removed - Worker now runs inside Backend process
  nsExec::ExecToLog 'powershell -ExecutionPolicy Bypass -Command "$$envFile = \"$INSTDIR\.env\"; if (Test-Path $$envFile) { $$content = Get-Content $$envFile -Raw -Encoding UTF8; $$content = $$content -replace \"PORT=.*\", \"PORT=$BackendPort\"; $$content = $$content -replace \"API_PORT=.*\", \"API_PORT=$BackendPort\"; $$content = $$content -replace \"MONGODB_PORT=.*\", \"MONGODB_PORT=$MongoPort\"; $$content = $$content -replace \"REDIS_PORT=.*\", \"REDIS_PORT=$RedisPort\"; $$content = $$content -replace \"NGINX_PORT=.*\", \"NGINX_PORT=$NginxPort\"; $$utf8 = New-Object System.Text.UTF8Encoding $$false; [System.IO.File]::WriteAllText($$envFile, $$content, $$utf8) }"'

  ; Update Redis configuration
  DetailPrint "Updating Redis configuration..."
  nsExec::ExecToLog 'powershell -ExecutionPolicy Bypass -Command "$$redisConf = \"$INSTDIR\runtime\redis.conf\"; if (Test-Path $$redisConf) { $$content = Get-Content $$redisConf -Raw -Encoding UTF8; $$content = $$content -replace \"^port\\s+\\d+\", \"port $RedisPort\"; $$utf8 = New-Object System.Text.UTF8Encoding $$false; [System.IO.File]::WriteAllText($$redisConf, $$content, $$utf8) }"'

  ; Update MongoDB configuration
  DetailPrint "Updating MongoDB configuration..."
  nsExec::ExecToLog 'powershell -ExecutionPolicy Bypass -Command "$$mongoConf = \"$INSTDIR\runtime\mongodb.conf\"; if (Test-Path $$mongoConf) { $$content = Get-Content $$mongoConf -Raw -Encoding UTF8; $$content = $$content -replace \"port:\\s*\\d+\", \"port: $MongoPort\"; $$utf8 = New-Object System.Text.UTF8Encoding $$false; [System.IO.File]::WriteAllText($$mongoConf, $$content, $$utf8) }"'

  ; Update Nginx configuration (listen port and backend proxy_pass)
  DetailPrint "Updating Nginx configuration..."
  nsExec::ExecToLog 'powershell -ExecutionPolicy Bypass -Command "$$nginxConf = \"$INSTDIR\runtime\nginx.conf\"; if (Test-Path $$nginxConf) { $$content = Get-Content $$nginxConf -Raw -Encoding UTF8; $$content = $$content -replace \"listen\\s+\\d+;\", \"listen       $NginxPort;\"; $$content = $$content -replace \"proxy_pass http://127\\.0\\.0\\.1:\\d+\", \"proxy_pass http://127.0.0.1:$BackendPort\"; $$utf8 = New-Object System.Text.UTF8Encoding $$false; [System.IO.File]::WriteAllText($$nginxConf, $$content, $$utf8) }"'
${Else}
  DetailPrint "Skipping port config update (upgrade mode - preserving existing configuration)"
${EndIf}

; Create shortcuts with admin privileges
DetailPrint "Creating shortcuts..."
CreateDirectory "$SMPROGRAMS\TradingAgentsCN"
Pop $0

; Method 1: Use NSIS native CreateShortcut command (more reliable)
DetailPrint "Creating Start Menu shortcuts..."
CreateShortcut "$SMPROGRAMS\TradingAgentsCN\Start TradingAgentsCN.lnk" \
  "powershell.exe" \
  '-ExecutionPolicy Bypass -NoExit -Command "Set-Location \"$INSTDIR\"; & \".\start_all.ps1\""' \
  "$INSTDIR\frontend\dist\favicon.ico" \
  0 \
  SW_SHOWNORMAL \
  "" \
  "Start TradingAgentsCN"

CreateShortcut "$SMPROGRAMS\TradingAgentsCN\Stop TradingAgentsCN.lnk" \
  "powershell.exe" \
  '-ExecutionPolicy Bypass -NoExit -Command "Set-Location \"$INSTDIR\"; & \".\stop_all.ps1\""' \
  "$INSTDIR\frontend\dist\favicon.ico" \
  0 \
  SW_SHOWNORMAL \
  "" \
  "Stop TradingAgentsCN"

CreateShortcut "$SMPROGRAMS\TradingAgentsCN\Uninstall.lnk" \
  "$INSTDIR\Uninstall.exe" \
  "" \
  "$INSTDIR\frontend\dist\favicon.ico" \
  0 \
  SW_SHOWNORMAL \
  "" \
  "Uninstall TradingAgentsCN"

DetailPrint "Creating Desktop shortcut..."
CreateShortcut "$DESKTOP\TradingAgentsCN.lnk" \
  "powershell.exe" \
  '-ExecutionPolicy Bypass -NoExit -Command "Set-Location \"$INSTDIR\"; & \".\start_all.ps1\""' \
  "$INSTDIR\frontend\dist\favicon.ico" \
  0 \
  SW_SHOWNORMAL \
  "" \
  "Start TradingAgentsCN"

; Method 2: Use PowerShell to set admin privilege flag (optional)
DetailPrint "Setting admin privileges for shortcuts..."
nsExec::ExecToLog 'powershell -ExecutionPolicy Bypass -Command "try { $lnkPath = \"$SMPROGRAMS\TradingAgentsCN\Start TradingAgentsCN.lnk\"; if (Test-Path $lnkPath) { $bytes = [System.IO.File]::ReadAllBytes($lnkPath); $bytes[0x15] = $bytes[0x15] -bor 0x20; [System.IO.File]::WriteAllBytes($lnkPath, $bytes); Write-Host \"Start shortcut admin flag set\" } } catch { Write-Host \"Error: $_\" }"'
Pop $0

nsExec::ExecToLog 'powershell -ExecutionPolicy Bypass -Command "try { $lnkPath = \"$SMPROGRAMS\TradingAgentsCN\Stop TradingAgentsCN.lnk\"; if (Test-Path $lnkPath) { $bytes = [System.IO.File]::ReadAllBytes($lnkPath); $bytes[0x15] = $bytes[0x15] -bor 0x20; [System.IO.File]::WriteAllBytes($lnkPath, $bytes); Write-Host \"Stop shortcut admin flag set\" } } catch { Write-Host \"Error: $_\" }"'
Pop $0

nsExec::ExecToLog 'powershell -ExecutionPolicy Bypass -Command "try { $lnkPath = \"$DESKTOP\TradingAgentsCN.lnk\"; if (Test-Path $lnkPath) { $bytes = [System.IO.File]::ReadAllBytes($lnkPath); $bytes[0x15] = $bytes[0x15] -bor 0x20; [System.IO.File]::WriteAllBytes($lnkPath, $bytes); Write-Host \"Desktop shortcut admin flag set\" } } catch { Write-Host \"Error: $_\" }"'
Pop $0

DetailPrint "Shortcuts created successfully!"

; Write uninstaller
WriteUninstaller "$INSTDIR\Uninstall.exe"

; Registry entries for Control Panel uninstall
WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\TradingAgentsCN" "DisplayName" "TradingAgentsCN"
WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\TradingAgentsCN" "UninstallString" "$INSTDIR\Uninstall.exe"
WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\TradingAgentsCN" "DisplayVersion" "${PRODUCT_VERSION}"
WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\TradingAgentsCN" "InstallLocation" "$INSTDIR"

DetailPrint "Installation completed!"

; Port configuration has already been saved to .env file (line 268)
; Installation completed - user can manually start services using shortcuts
DetailPrint "Installation completed successfully!"
DetailPrint "Use the desktop shortcut or Start Menu to launch TradingAgentsCN"

SectionEnd

Section "Uninstall"
 DetailPrint "Removing shortcuts..."
 Delete "$SMPROGRAMS\TradingAgentsCN\Start TradingAgentsCN.lnk"
 Delete "$SMPROGRAMS\TradingAgentsCN\Stop TradingAgentsCN.lnk"
 Delete "$SMPROGRAMS\TradingAgentsCN\Uninstall.lnk"
 RMDir  "$SMPROGRAMS\TradingAgentsCN"
 Delete "$DESKTOP\TradingAgentsCN.lnk"

 DetailPrint "Removing registry entries..."
 DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\TradingAgentsCN"

 DetailPrint "Removing installation files..."
 Delete "$INSTDIR\Uninstall.exe"
 RMDir /r "$INSTDIR"

 DetailPrint "Uninstallation completed!"
SectionEnd