!include "MUI2.nsh"
!include "nsDialogs.nsh"
!include "LogicLib.nsh"

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
!ifndef PORTABLE_DIR
  !define PORTABLE_DIR "C:\TradingAgentsCN\release\TradingAgentsCN-portable"
!endif
!ifndef OUTPUT_DIR
  !define OUTPUT_DIR "C:\TradingAgentsCN\release\packages"
!endif

Name "${PRODUCT_NAME}"
OutFile "${OUTPUT_DIR}\TradingAgentsCNSetup-${PRODUCT_VERSION}.exe"
InstallDir "C:\TradingAgentsCN"
RequestExecutionLevel admin
SetDatablockOptimize on
SetCompressor /SOLID lzma
SetCompressorDictSize 64

Var BackendPort
Var MongoPort
Var RedisPort
Var NginxPort
Var hBackendEdit
Var hMongoEdit
Var hRedisEdit
Var hNginxEdit
Var hDetectBtn
Var LaunchCheckbox
Var LaunchCheckboxState
Var VCRedistInstalled
Var VCRedistExitCode
Var MongoRuntimeOk

Function ValidateInstallDirPath
 Exch $0
 Push $1
 Push $2
 Push $3
 Push $4
 Push $5
 Push $6

 StrLen $1 $0
 ${If} $1 < 4
  StrCpy $0 1
  Goto done
 ${EndIf}

 StrCpy $2 $0 1 0
 StrCpy $3 $0 1 1
 StrCpy $4 $0 1 2

 ${If} $3 != ":"
  StrCpy $0 1
  Goto done
 ${EndIf}
 ${If} $4 != "\"
  StrCpy $0 1
  Goto done
 ${EndIf}

 StrCpy $5 "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
 StrCpy $6 0
 drive_letter_loop:
  StrCpy $3 $5 1 $6
  ${If} $3 == ""
   StrCpy $0 1
   Goto done
  ${EndIf}

  ${If} $2 == $3
   Goto validate_path_chars
  ${EndIf}

  IntOp $6 $6 + 1
  Goto drive_letter_loop

 validate_path_chars:
 StrCpy $5 "\ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-"
 StrCpy $6 3
 loop_chars:
  StrCpy $2 $0 1 $6
  ${If} $2 == ""
   StrCpy $0 0
   Goto done
  ${EndIf}

  StrCpy $4 0
 allowed_chars_loop:
   StrCpy $3 $5 1 $4
   ${If} $3 == ""
    StrCpy $0 1
    Goto done
   ${EndIf}

   ${If} $2 == $3
    IntOp $6 $6 + 1
    Goto loop_chars
   ${EndIf}

   IntOp $4 $4 + 1
   Goto allowed_chars_loop

 done:
 Pop $6
 Pop $5
 Pop $4
 Pop $3
 Pop $2
 Pop $1
 Exch $0
FunctionEnd

Function CheckVCRedistX64Installed
 Push $0

 StrCpy $VCRedistInstalled "0"
 SetRegView 64
 ClearErrors
 ReadRegDWORD $0 HKLM "SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" "Installed"
 ${IfNot} ${Errors}
  ${If} $0 == 1
   StrCpy $VCRedistInstalled "1"
  ${EndIf}
 ${EndIf}

 Pop $0
FunctionEnd

Function VerifyMongoRuntime
 Push $0

 StrCpy $MongoRuntimeOk "0"
 ${If} ${FileExists} "$INSTDIR\vendors\mongodb\mongodb-win32-x86_64-windows-8.0.13\bin\mongod.exe"
  nsExec::ExecToLog '"$INSTDIR\vendors\mongodb\mongodb-win32-x86_64-windows-8.0.13\bin\mongod.exe" --version'
  Pop $0
  ${If} $0 == 0
   StrCpy $MongoRuntimeOk "1"
  ${EndIf}
 ${EndIf}

 Pop $0
FunctionEnd

Function DirectoryPageLeave
 Push $INSTDIR
 Call ValidateInstallDirPath
 Pop $0
 ${If} $0 != 0
  MessageBox MB_ICONSTOP "Installation path must use English characters only and cannot contain spaces, Chinese characters, or other special characters.$\r$\n$\r$\nPlease use a path such as C:\\TradingAgentsCN or D:\\TradingAgentsCN99."
  Abort
 ${EndIf}
FunctionEnd

Function .onInit
 StrCpy $BackendPort "${BACKEND_PORT}"
 StrCpy $MongoPort "${MONGO_PORT}"
 StrCpy $RedisPort "${REDIS_PORT}"
 StrCpy $NginxPort "${NGINX_PORT}"
 StrCpy $LaunchCheckboxState ${BST_CHECKED}
FunctionEnd

Function PortsPage
 nsDialogs::Create 1018
 Pop $0
 ${If} $0 == error
   Abort
${EndIf}

${NSD_CreateLabel} 0 0 100% 12u "Configure Ports for Installation"

${NSD_CreateLabel} 0 18u 45% 12u "Backend Port (default ${BACKEND_PORT})"
 ${NSD_CreateText} 50% 16u 35% 12u "$BackendPort"
 Pop $hBackendEdit

${NSD_CreateLabel} 0 36u 45% 12u "MongoDB Port (default ${MONGO_PORT})"
 ${NSD_CreateText} 50% 34u 35% 12u "$MongoPort"
 Pop $hMongoEdit

${NSD_CreateLabel} 0 54u 45% 12u "Redis Port (default ${REDIS_PORT})"
 ${NSD_CreateText} 50% 52u 35% 12u "$RedisPort"
 Pop $hRedisEdit

${NSD_CreateLabel} 0 72u 45% 12u "Nginx Port (default ${NGINX_PORT})"
 ${NSD_CreateText} 50% 70u 35% 12u "$NginxPort"
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
FunctionEnd

; Icon configuration
!ifndef PROJECT_ROOT
  !define PROJECT_ROOT "C:\TradingAgentsCN"
!endif
!define MUI_ICON "${PROJECT_ROOT}\frontend\dist\favicon.ico"
!define MUI_UNICON "${PROJECT_ROOT}\frontend\dist\favicon.ico"

!insertmacro MUI_PAGE_WELCOME
!define MUI_PAGE_CUSTOMFUNCTION_LEAVE DirectoryPageLeave
!insertmacro MUI_PAGE_DIRECTORY
!undef MUI_PAGE_CUSTOMFUNCTION_LEAVE
Page custom PortsPage PortsPageLeave
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "SimpChinese"

Section "Install"
 SetOutPath "$INSTDIR"

 DetailPrint "Installing TradingAgentsCN files..."

 File /r /x "__pycache__" /x "*.pyc" /x "venv" /x "env" /x "logs" /x "temp" /x "data" /x ".git" "${PORTABLE_DIR}\*.*"

 DetailPrint "Creating directories..."
 CreateDirectory "$INSTDIR\logs"
 CreateDirectory "$INSTDIR\temp"
 CreateDirectory "$INSTDIR\data"
 CreateDirectory "$INSTDIR\data\mongodb"
 CreateDirectory "$INSTDIR\data\redis"

 DetailPrint "Checking Visual C++ Redistributable (x64) for MongoDB 8.0..."
 Call CheckVCRedistX64Installed
 ${If} $VCRedistInstalled == "1"
  DetailPrint "Visual C++ Redistributable (x64) already installed"
 ${Else}
  DetailPrint "Installing Visual C++ Redistributable (x64)..."
  ExecWait '"$INSTDIR\vendors\mongodb\mongodb-win32-x86_64-windows-8.0.13\bin\vc_redist.x64.exe" /quiet /norestart' $VCRedistExitCode
  ${If} $VCRedistExitCode == 0
   DetailPrint "Visual C++ Redistributable installed successfully"
  ${ElseIf} $VCRedistExitCode == 3010
   DetailPrint "Visual C++ Redistributable installed, but Windows restart is required"
  ${ElseIf} $VCRedistExitCode == 1638
   DetailPrint "Visual C++ Redistributable reported another version is already installed; verifying runtime state"
  ${Else}
   MessageBox MB_ICONSTOP "Microsoft Visual C++ Redistributable (x64) installation failed. Exit code: $VCRedistExitCode.$\r$\n$\r$\nPlease restart Windows and run the installer again, or manually run:$\r$\n$INSTDIR\vendors\mongodb\mongodb-win32-x86_64-windows-8.0.13\bin\vc_redist.x64.exe"
   Abort
  ${EndIf}
 ${EndIf}

 DetailPrint "Re-checking Visual C++ Redistributable (x64) installation state..."
 Call CheckVCRedistX64Installed
 ${If} $VCRedistInstalled != "1"
  MessageBox MB_ICONSTOP "Microsoft Visual C++ Redistributable (x64) is still not detected after installation.$\r$\n$\r$\nPlease restart Windows and run the installer again, or manually run:$\r$\n$INSTDIR\vendors\mongodb\mongodb-win32-x86_64-windows-8.0.13\bin\vc_redist.x64.exe"
  Abort
 ${EndIf}

 DetailPrint "Verifying MongoDB runtime dependencies..."
 Call VerifyMongoRuntime
 ${If} $MongoRuntimeOk != "1"
  ${If} $VCRedistExitCode == 3010
   MessageBox MB_ICONSTOP "MongoDB runtime verification failed because Windows restart is still required after installing Microsoft Visual C++ Redistributable.$\r$\n$\r$\nPlease restart Windows first, then run TradingAgentsCN again."
  ${Else}
   MessageBox MB_ICONSTOP "MongoDB runtime verification failed after installing Microsoft Visual C++ Redistributable.$\r$\n$\r$\nPlease manually run:$\r$\n$INSTDIR\vendors\mongodb\mongodb-win32-x86_64-windows-8.0.13\bin\vc_redist.x64.exe$\r$\n$\r$\nThen restart Windows and try the installer again."
  ${EndIf}
  Abort
 ${EndIf}
 DetailPrint "MongoDB runtime verification passed"

 DetailPrint "Configuring ports..."
 nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -Command "$$envFile = \"$INSTDIR\.env\"; if (Test-Path $$envFile) { $$content = Get-Content $$envFile -Raw -Encoding UTF8; $$content = $$content -replace \"PORT=.*\", \"PORT=$BackendPort\"; $$content = $$content -replace \"API_PORT=.*\", \"API_PORT=$BackendPort\"; $$content = $$content -replace \"MONGODB_PORT=.*\", \"MONGODB_PORT=$MongoPort\"; $$content = $$content -replace \"REDIS_PORT=.*\", \"REDIS_PORT=$RedisPort\"; $$content = $$content -replace \"NGINX_PORT=.*\", \"NGINX_PORT=$NginxPort\"; $$utf8 = New-Object System.Text.UTF8Encoding $$false; [System.IO.File]::WriteAllText($$envFile, $$content, $$utf8) }"'

 WriteUninstaller "$INSTDIR\Uninstall.exe"

 WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayName" "${PRODUCT_NAME}"
 WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "UninstallString" "$INSTDIR\Uninstall.exe"
 WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayVersion" "${PRODUCT_VERSION}"

 CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
 CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk" "$INSTDIR\start_all.ps1" "" "$INSTDIR\frontend\dist\favicon.ico"
 CreateShortCut "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\start_all.ps1" "" "$INSTDIR\frontend\dist\favicon.ico"
SectionEnd

Section "Uninstall"
 RMDir /r "$INSTDIR"
 RMDir /r "$SMPROGRAMS\${PRODUCT_NAME}"
 Delete "$DESKTOP\${PRODUCT_NAME}.lnk"
 DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
SectionEnd

