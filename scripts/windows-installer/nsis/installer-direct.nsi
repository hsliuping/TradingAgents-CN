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

Function ValidateInstallDirPath
 Exch $0
 Push $1
 Push $2
 Push $3
 Push $4

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

 ${If} $2 >= "A"
 ${AndIf} $2 <= "Z"
 ${OrIf} $2 >= "a"
 ${AndIf} $2 <= "z"
 ${Else}
  StrCpy $0 1
  Goto done
 ${EndIf}

 StrCpy $4 3
 loop_chars:
  ${If} $4 >= $1
    StrCpy $0 0
    Goto done
  ${EndIf}

  StrCpy $2 $0 1 $4
  ${If} $2 == "\\"
  ${OrIf} $2 == "_"
  ${OrIf} $2 == "-"
  ${OrIf} $2 == "."
  ${OrIf} $2 >= "0"
  ${AndIf} $2 <= "9"
  ${OrIf} $2 >= "A"
  ${AndIf} $2 <= "Z"
  ${OrIf} $2 >= "a"
  ${AndIf} $2 <= "z"
    IntOp $4 $4 + 1
    Goto loop_chars
  ${EndIf}

  StrCpy $0 1

 done:
 Pop $4
 Pop $3
 Pop $2
 Pop $1
 Exch $0
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
 CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk" "$INSTDIR\start_all.ps1" "" "$INSTDIR\frontend\dist\favicon.ico"
 CreateShortCut "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\start_all.ps1" "" "$INSTDIR\frontend\dist\favicon.ico"
SectionEnd

Section "Uninstall"
 RMDir /r "$INSTDIR"
 RMDir /r "$SMPROGRAMS\${PRODUCT_NAME}"
 Delete "$DESKTOP\${PRODUCT_NAME}.lnk"
 DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
SectionEnd

