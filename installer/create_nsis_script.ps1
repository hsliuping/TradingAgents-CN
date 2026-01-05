# Create NSIS script with proper encoding (ANSI)

$nsisContent = @'
; TradingAgents-CN Pro Version Installer
; NSIS Installer Script

!include "MUI2.nsh"
!include "FileFunc.nsh"

; Application Info
!define PRODUCT_NAME "TradingAgents-CN Pro"
!define PRODUCT_VERSION "1.0.0-preview"
!define PRODUCT_PUBLISHER "TradingAgents Team"
!define PRODUCT_WEB_SITE "https://github.com/yourusername/TradingAgentsCN"

; Installer Settings
Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "..\release\packages\TradingAgentsCN-Setup-${PRODUCT_VERSION}.exe"
InstallDir "$PROGRAMFILES64\TradingAgentsCN"
InstallDirRegKey HKLM "Software\${PRODUCT_NAME}" "InstallDir"

; Request Admin Rights
RequestExecutionLevel admin

; Compression Settings
SetCompressor /SOLID lzma
SetCompressorDictSize 64

; Modern UI Settings
!define MUI_ABORTWARNING
!define MUI_ICON "${NSISDIR}\Contrib\Graphics\Icons\modern-install.ico"
!define MUI_UNICON "${NSISDIR}\Contrib\Graphics\Icons\modern-uninstall.ico"

; Welcome Page
!define MUI_WELCOMEPAGE_TITLE "Welcome to ${PRODUCT_NAME} Setup"
!define MUI_WELCOMEPAGE_TEXT "This wizard will guide you through the installation of ${PRODUCT_NAME}.$\r$\n$\r$\n${PRODUCT_NAME} is an AI-powered quantitative trading platform based on multi-agent systems.$\r$\n$\r$\nClick Next to continue."

; License Page
!define MUI_LICENSEPAGE_TEXT_TOP "Please review the license agreement below."
!define MUI_LICENSEPAGE_TEXT_BOTTOM "If you accept the terms of the agreement, click I Agree to continue."

; Directory Page
!define MUI_DIRECTORYPAGE_TEXT_TOP "Setup will install ${PRODUCT_NAME} in the following folder.$\r$\n$\r$\nTo install in a different folder, click Browse and select another folder."

; Finish Page
!define MUI_FINISHPAGE_TITLE "Completing ${PRODUCT_NAME} Setup"
!define MUI_FINISHPAGE_TEXT "${PRODUCT_NAME} has been installed on your computer.$\r$\n$\r$\nClick Finish to close this wizard."
!define MUI_FINISHPAGE_RUN "$INSTDIR\start_all.bat"
!define MUI_FINISHPAGE_RUN_TEXT "Launch TradingAgents-CN"
!define MUI_FINISHPAGE_SHOWREADME "$INSTDIR\README.md"
!define MUI_FINISHPAGE_SHOWREADME_TEXT "View README"

; Installer Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; Uninstaller Pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; Language Settings
!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"

; Installation Section
Section "Main Program" SEC01
  SectionIn RO
  
  SetOutPath "$INSTDIR"
  SetOverwrite on
  
  DetailPrint "Installing ${PRODUCT_NAME}..."
  
  File /r "..\release\TradingAgentsCN-portable\*.*"
  
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  
  WriteRegStr HKLM "Software\${PRODUCT_NAME}" "InstallDir" "$INSTDIR"
  WriteRegStr HKLM "Software\${PRODUCT_NAME}" "Version" "${PRODUCT_VERSION}"
  
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayIcon" "$INSTDIR\start_all.bat"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "Publisher" "${PRODUCT_PUBLISHER}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "NoRepair" 1
  
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "EstimatedSize" "$0"
  
SectionEnd

Section "Start Menu Shortcuts" SEC02
  CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Start TradingAgents-CN.lnk" "$INSTDIR\start_all.bat" "" "$INSTDIR\start_all.bat" 0
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Stop TradingAgents-CN.lnk" "$INSTDIR\stop_all.bat" "" "$INSTDIR\stop_all.bat" 0
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Open Web Interface.lnk" "http://localhost" "" "" 0
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Uninstall.lnk" "$INSTDIR\Uninstall.exe" "" "$INSTDIR\Uninstall.exe" 0
SectionEnd

Section "Desktop Shortcut" SEC03
  CreateShortCut "$DESKTOP\TradingAgents-CN.lnk" "$INSTDIR\start_all.bat" "" "$INSTDIR\start_all.bat" 0
SectionEnd

; Uninstallation Section
Section "Uninstall"
  RMDir /r "$INSTDIR"
  RMDir /r "$SMPROGRAMS\${PRODUCT_NAME}"
  Delete "$DESKTOP\TradingAgents-CN.lnk"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
  DeleteRegKey HKLM "Software\${PRODUCT_NAME}"
SectionEnd

; Section Descriptions
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC01} "Install ${PRODUCT_NAME} main program files."
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC02} "Create shortcuts in Start Menu."
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC03} "Create shortcut on Desktop."
!insertmacro MUI_FUNCTION_DESCRIPTION_END

!insertmacro GetSize
'@

# Write with ANSI encoding
$nsisPath = Join-Path $PSScriptRoot "installer.nsi"
[System.IO.File]::WriteAllText($nsisPath, $nsisContent, [System.Text.Encoding]::Default)

Write-Host "NSIS script created with ANSI encoding: $nsisPath" -ForegroundColor Green

