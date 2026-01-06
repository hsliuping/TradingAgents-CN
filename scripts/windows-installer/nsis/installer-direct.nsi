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

!define MUI_ICON "${NSISDIR}\Contrib\Graphics\Icons\modern-install.ico"
!define MUI_UNICON "${NSISDIR}\Contrib\Graphics\Icons\modern-uninstall.ico"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
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

 DetailPrint "Configuring ports..."
 nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-Content \"$INSTDIR\.env\") -replace \"BACKEND_PORT=.*\", \"BACKEND_PORT=$BackendPort\" | Set-Content \"$INSTDIR\.env\""'
 nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-Content \"$INSTDIR\.env\") -replace \"MONGO_PORT=.*\", \"MONGO_PORT=$MongoPort\" | Set-Content \"$INSTDIR\.env\""'
 nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-Content \"$INSTDIR\.env\") -replace \"REDIS_PORT=.*\", \"REDIS_PORT=$RedisPort\" | Set-Content \"$INSTDIR\.env\""'
 nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-Content \"$INSTDIR\.env\") -replace \"NGINX_PORT=.*\", \"NGINX_PORT=$NginxPort\" | Set-Content \"$INSTDIR\.env\""'

 WriteUninstaller "$INSTDIR\Uninstall.exe"

 WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayName" "${PRODUCT_NAME}"
 WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "UninstallString" "$INSTDIR\Uninstall.exe"
 WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayVersion" "${PRODUCT_VERSION}"

 CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
 CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk" "$INSTDIR\start_all.ps1"
 CreateShortCut "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\start_all.ps1"
SectionEnd

Section "Uninstall"
 RMDir /r "$INSTDIR"
 RMDir /r "$SMPROGRAMS\${PRODUCT_NAME}"
 Delete "$DESKTOP\${PRODUCT_NAME}.lnk"
 DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
SectionEnd

