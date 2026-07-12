﻿﻿﻿Unicode true
ManifestDPIAware true
; ============================================================================
; TradingAgentsCN Windows Installer (NSIS 3.x)
; 特性：
;   1. 全中文界面
;   2. 端口占用检查（netstat + LISTENING 过滤）
;   3. 安装路径中文/空格检查
;   4. 动态查找 MongoDB 版本目录（不硬编码版本号）
;   5. VC++ Runtime DLL 直接复制（不安装 VC Redist，更稳定）
;   6. 简化安装模式：全新安装 / 升级安装
; ============================================================================

!include "MUI2.nsh"
!include "nsDialogs.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"

;----------------------------------------------------------------------------
; 常量定义（支持外部 /D 覆盖）
;----------------------------------------------------------------------------
!define PRODUCT_NAME "TradingAgentsCN"
!ifndef PRODUCT_VERSION
  !define PRODUCT_VERSION "1.0.0"
!endif
!ifndef PACKAGE_7Z
  !define PACKAGE_7Z "C:\TradingAgentsCN\release\packages\TradingAgentsCN-Portable-latest-installer.7z"
!endif
!ifndef OUTPUT_DIR
  !define OUTPUT_DIR "C:\TradingAgentsCN\release\packages"
!endif
!ifndef PROJECT_ROOT
  !define PROJECT_ROOT "C:\TradingAgentsCN"
!endif
!ifndef SEVENZIP_DIR
  !define SEVENZIP_DIR "C:\TradingAgentsCN\vendors\7zip"
!endif

Name "${PRODUCT_NAME}"
!ifdef TEST_BUILD
  OutFile "${OUTPUT_DIR}\TradingAgentsCNSetup-${PRODUCT_VERSION}-test.exe"
!else
  OutFile "${OUTPUT_DIR}\TradingAgentsCNSetup-${PRODUCT_VERSION}.exe"
!endif
InstallDir "C:\TradingAgentsCN"
RequestExecutionLevel admin
SetDatablockOptimize on
; Use zlib for small files (faster), don't compress the 7z package (already compressed)
SetCompressor /SOLID zlib

;----------------------------------------------------------------------------
; 全局变量
;----------------------------------------------------------------------------
Var BackendPort
Var MongoPort
Var RedisPort
Var NginxPort
; Worker port removed - Worker is now integrated in Backend process
Var hBackendEdit
Var hMongoEdit
Var hRedisEdit
Var hNginxEdit
; 安装模式：0=全新安装，1=升级安装（保留配置和数据）
Var InstallMode
Var hFreshRadio
Var hUpgradeRadio
Var MongoRuntimeOk
Var MongoBinDir

;============================================================================
; 通用函数：检查端口占用
; 输入（栈顶）：端口号字符串
; 输出（栈顶）：0=未占用，1=已占用
; 原理：netstat 列出所有 TCP 连接，findstr 过滤":端口 "，再过滤 LISTENING
;============================================================================
Function CheckPortOccupied
  Exch $0  ; port number
  Push $1
  Push $2

  StrCpy $2 "0"
  nsExec::ExecToStack 'cmd /c netstat -ano -p tcp | findstr /C:":$0 " | findstr LISTENING'
  Pop $1  ; exit code (0 = found match, 1 = no match)
  Pop $0  ; output (discard)

  ${If} $1 == 0
    StrCpy $2 "1"
  ${EndIf}

  StrCpy $0 $2
  Pop $2
  Pop $1
  Exch $0
FunctionEnd

;============================================================================
; 路径合法性校验：只允许盘符:\ + 英文/数字/._-
; 拒绝中文、空格、其他特殊字符（避免 MongoDB/Redis 路径问题）
; 输入（栈顶）：路径字符串
; 输出（栈顶）：0=合法，1=非法
;============================================================================
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

;============================================================================
; 动态查找 MongoDB 运行时（不硬编码版本号）
; 用 FindFirst 通配符查找 mongodb-win32-* 目录，验证 mongod.exe 可执行
; 设置：$MongoRuntimeOk（1=正常，0=异常）和 $MongoBinDir
;============================================================================
Function VerifyMongoRuntime
  Push $0
  Push $1
  Push $2

  StrCpy $MongoRuntimeOk "0"
  StrCpy $MongoBinDir ""

  ; 用通配符查找 mongodb-win32-* 目录（避免版本号硬编码）
  ClearErrors
  FindFirst $0 $1 "$INSTDIR\vendors\mongodb\mongodb-win32-*"
  ${If} ${Errors}
    Goto verify_done
  ${EndIf}

  verify_loop:
    ${If} $1 == ""
      Goto verify_close
    ${EndIf}
    ; 检查该目录下是否有 bin\mongod.exe
    ${If} ${FileExists} "$INSTDIR\vendors\mongodb\$1\bin\mongod.exe"
      StrCpy $MongoBinDir "$INSTDIR\vendors\mongodb\$1\bin"
      nsExec::ExecToLog '"$MongoBinDir\mongod.exe" --version'
      Pop $2
      ${If} $2 == 0
        StrCpy $MongoRuntimeOk "1"
      ${EndIf}
      Goto verify_close
    ${EndIf}
    FindNext $0 $1
    Goto verify_loop

  verify_close:
    FindClose $0

  verify_done:
    Pop $2
    Pop $1
    Pop $0
FunctionEnd

;============================================================================
; 目录页离开时的校验：检查路径是否包含中文/空格
;============================================================================
Function DirectoryPageLeave
  Push $INSTDIR
  Call ValidateInstallDirPath
  Pop $0
  ${If} $0 != 0
    MessageBox MB_ICONSTOP "安装路径只能使用英文字母、数字和 . _ - 等字符，不能包含中文、空格或其他特殊字符。$\r$\n$\r$\n请使用类似 C:\TradingAgentsCN 或 D:\TradingAgentsCN 的路径。"
    Abort
  ${EndIf}
FunctionEnd

;============================================================================
; 安装初始化：生成随机端口（避开常见端口，减少冲突）
;============================================================================
Function .onInit
  ; Backend: 随机端口 4100-4999
  System::Call 'kernel32::GetTickCount()i.r0'
  IntOp $0 $0 % 900
  IntOp $BackendPort $0 + 4100

  ; Worker port removed - Worker is now integrated in Backend process

  ; MongoDB: 随机端口 5100-5999（避开 5000、5432）
  System::Call 'kernel32::GetTickCount()i.r0'
  IntOp $0 $0 + 100
  IntOp $0 $0 % 900
  IntOp $MongoPort $0 + 5100

  ; Redis: 随机端口 7100-7999（避开 6379、7000）
  System::Call 'kernel32::GetTickCount()i.r0'
  IntOp $0 $0 + 200
  IntOp $0 $0 % 900
  IntOp $RedisPort $0 + 7100

  ; Nginx: 随机端口 9100-9999（避开 8000-9000、9200、9300）
  System::Call 'kernel32::GetTickCount()i.r0'
  IntOp $0 $0 + 300
  IntOp $0 $0 % 900
  IntOp $NginxPort $0 + 9100

  ; 默认：全新安装
  StrCpy $InstallMode 0
FunctionEnd

;============================================================================
; 端口配置页（自定义对话框）
;============================================================================
Function PortsPage
  nsDialogs::Create 1018
  Pop $0
  ${If} $0 == error
    Abort
  ${EndIf}

  ${NSD_CreateLabel} 0 0 100% 12u "配置安装端口"
  ${NSD_CreateLabel} 0 14u 100% 24u "已自动生成随机端口以避免冲突，如需修改请直接编辑。$\n端口范围 1024-65535，且各端口不能重复。点击「下一步」时会自动检查端口占用。"

  ${NSD_CreateLabel} 0 42u 45% 12u "后端端口（含线程池 Worker）"
  ${NSD_CreateText} 50% 40u 35% 12u "$BackendPort"
  Pop $hBackendEdit

  ${NSD_CreateLabel} 0 57u 45% 12u "MongoDB 端口"
  ${NSD_CreateText} 50% 55u 35% 12u "$MongoPort"
  Pop $hMongoEdit

  ${NSD_CreateLabel} 0 72u 45% 12u "Redis 端口"
  ${NSD_CreateText} 50% 70u 35% 12u "$RedisPort"
  Pop $hRedisEdit

  ${NSD_CreateLabel} 0 87u 45% 12u "Nginx 端口"
  ${NSD_CreateText} 50% 85u 35% 12u "$NginxPort"
  Pop $hNginxEdit

  nsDialogs::Show
FunctionEnd


Function PortsPageLeave
  ${NSD_GetText} $hBackendEdit $BackendPort
  ${NSD_GetText} $hMongoEdit $MongoPort
  ${NSD_GetText} $hRedisEdit $RedisPort
  ${NSD_GetText} $hNginxEdit $NginxPort

  ; 校验端口非空
  ${If} $BackendPort == ""
    MessageBox MB_ICONSTOP "后端端口不能为空"
    Abort
  ${EndIf}
  ${If} $MongoPort == ""
    MessageBox MB_ICONSTOP "MongoDB 端口不能为空"
    Abort
  ${EndIf}
  ${If} $RedisPort == ""
    MessageBox MB_ICONSTOP "Redis 端口不能为空"
    Abort
  ${EndIf}
  ${If} $NginxPort == ""
    MessageBox MB_ICONSTOP "Nginx 端口不能为空"
    Abort
  ${EndIf}

  ; 校验端口范围
  ${If} $BackendPort < 1024
    MessageBox MB_ICONSTOP "后端端口必须大于等于 1024"
    Abort
  ${EndIf}
  ${If} $MongoPort < 1024
    MessageBox MB_ICONSTOP "MongoDB 端口必须大于等于 1024"
    Abort
  ${EndIf}
  ${If} $RedisPort < 1024
    MessageBox MB_ICONSTOP "Redis 端口必须大于等于 1024"
    Abort
  ${EndIf}
  ${If} $NginxPort < 1024
    MessageBox MB_ICONSTOP "Nginx 端口必须大于等于 1024"
    Abort
  ${EndIf}
  ${If} $BackendPort > 65535
    MessageBox MB_ICONSTOP "后端端口必须小于等于 65535"
    Abort
  ${EndIf}
  ${If} $MongoPort > 65535
    MessageBox MB_ICONSTOP "MongoDB 端口必须小于等于 65535"
    Abort
  ${EndIf}
  ${If} $RedisPort > 65535
    MessageBox MB_ICONSTOP "Redis 端口必须小于等于 65535"
    Abort
  ${EndIf}
  ${If} $NginxPort > 65535
    MessageBox MB_ICONSTOP "Nginx 端口必须小于等于 65535"
    Abort
  ${EndIf}

  ; 校验端口不重复
  ${If} $BackendPort == $MongoPort
    MessageBox MB_ICONSTOP "后端端口与 MongoDB 端口重复"
    Abort
  ${EndIf}
  ${If} $BackendPort == $RedisPort
    MessageBox MB_ICONSTOP "后端端口与 Redis 端口重复"
    Abort
  ${EndIf}
  ${If} $BackendPort == $NginxPort
    MessageBox MB_ICONSTOP "后端端口与 Nginx 端口重复"
    Abort
  ${EndIf}
  ${If} $MongoPort == $RedisPort
    MessageBox MB_ICONSTOP "MongoDB 端口与 Redis 端口重复"
    Abort
  ${EndIf}
  ${If} $MongoPort == $NginxPort
    MessageBox MB_ICONSTOP "MongoDB 端口与 Nginx 端口重复"
    Abort
  ${EndIf}
  ${If} $RedisPort == $NginxPort
    MessageBox MB_ICONSTOP "Redis 端口与 Nginx 端口重复"
    Abort
  ${EndIf}

  ; 检查端口占用（netstat + LISTENING 过滤）
  DetailPrint "正在检查端口占用情况..."

  Push $BackendPort
  Call CheckPortOccupied
  Pop $0
  ${If} $0 == 1
    MessageBox MB_ICONSTOP "后端端口 $BackendPort 已被其他程序占用，请更换端口后重试。$\r$\n$\r$\n提示：可使用命令 netstat -ano | findstr :$BackendPort 查看占用进程。"
    Abort
  ${EndIf}

  Push $MongoPort
  Call CheckPortOccupied
  Pop $0
  ${If} $0 == 1
    MessageBox MB_ICONSTOP "MongoDB 端口 $MongoPort 已被其他程序占用，请更换端口后重试。$\r$\n$\r$\n提示：可使用命令 netstat -ano | findstr :$MongoPort 查看占用进程。"
    Abort
  ${EndIf}

  Push $RedisPort
  Call CheckPortOccupied
  Pop $0
  ${If} $0 == 1
    MessageBox MB_ICONSTOP "Redis 端口 $RedisPort 已被其他程序占用，请更换端口后重试。$\r$\n$\r$\n提示：可使用命令 netstat -ano | findstr :$RedisPort 查看占用进程。"
    Abort
  ${EndIf}

  Push $NginxPort
  Call CheckPortOccupied
  Pop $0
  ${If} $0 == 1
    MessageBox MB_ICONSTOP "Nginx 端口 $NginxPort 已被其他程序占用，请更换端口后重试。$\r$\n$\r$\n提示：可使用命令 netstat -ano | findstr :$NginxPort 查看占用进程。"
    Abort
  ${EndIf}

  DetailPrint "端口检查通过，所有端口均未被占用"
FunctionEnd

;============================================================================
; 安装模式选择页：检测到旧安装时显示（全新/升级）
;============================================================================
Function InstallModePage
  ; 只在选择目录已有 TradingAgentsCN 安装时显示
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

  ${NSD_CreateLabel} 0 0 100% 12u "检测到现有的 TradingAgentsCN 安装"
  Pop $0
  ${NSD_CreateLabel} 0 14u 100% 56u "所选目录已存在 TradingAgentsCN 安装。$\n$\n重要提示：继续前请先运行 stop_all.ps1 停止所有服务，否则部分文件可能无法更新。$\n$\n请选择安装模式：$\n$\n  全新安装 — 备份当前数据后完全覆盖（配置将使用新的端口设置）。$\n$\n  升级安装 — 保留你的配置和数据，只更新程序文件。"
  Pop $0

  ${NSD_CreateRadioButton} 0 72u 100% 12u "全新安装 — 备份数据后完全覆盖"
  Pop $hFreshRadio
  ${NSD_Check} $hFreshRadio

  ${NSD_CreateRadioButton} 0 87u 100% 12u "升级安装 — 保留配置和数据"
  Pop $hUpgradeRadio

  nsDialogs::Show
  Return
skip_mode:
  ; 全新安装，跳过此页
  StrCpy $InstallMode 0
  Abort
FunctionEnd

Function InstallModePageLeave
  ${NSD_GetState} $hFreshRadio $0
  ${If} $0 == 1
    StrCpy $InstallMode 0
  ${Else}
    StrCpy $InstallMode 1
  ${EndIf}
FunctionEnd

;----------------------------------------------------------------------------
; 图标配置
;----------------------------------------------------------------------------
!define MUI_ICON "${PROJECT_ROOT}\frontend\dist\favicon.ico"
!define MUI_UNICON "${PROJECT_ROOT}\frontend\dist\favicon.ico"

;----------------------------------------------------------------------------
; 完成页配置：启动程序选项
;----------------------------------------------------------------------------
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "立即启动 TradingAgentsCN"
!define MUI_FINISHPAGE_RUN_FUNCTION "LaunchApplication"

;----------------------------------------------------------------------------
; 页面定义（顺序即向导顺序）
;----------------------------------------------------------------------------
Page custom PortsPage PortsPageLeave
!define MUI_PAGE_CUSTOMFUNCTION_LEAVE DirectoryPageLeave
!insertmacro MUI_PAGE_DIRECTORY
Page custom InstallModePage InstallModePageLeave
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

;============================================================================
; 安装完成后启动程序
;============================================================================
Function LaunchApplication
  ; 以管理员权限启动
  ExecShell "runas" "powershell" '-ExecutionPolicy Bypass -NoExit -File "$INSTDIR\start_all.ps1"'
FunctionEnd

;============================================================================
; 安装主流程
;============================================================================
Section
SetOutPath "$INSTDIR"

; 备份现有配置和数据（检测到旧安装时，无论全新还是升级模式都先备份）
IfFileExists "$INSTDIR\.env" 0 skip_backup
  DetailPrint "备份现有配置和数据..."
  nsExec::ExecToLog 'powershell -ExecutionPolicy Bypass -Command "$$instDir = ''$INSTDIR''; $$backupRoot = Join-Path $$instDir ''backup''; $$ts = Get-Date -Format ''yyyyMMdd_HHmmss''; $$backupDir = Join-Path $$backupRoot (''pre_install_'' + $$ts); if (-not (Test-Path $$backupRoot)) { New-Item -ItemType Directory -Path $$backupRoot -Force | Out-Null }; New-Item -ItemType Directory -Path $$backupDir -Force | Out-Null; $$items = @(''.env'', ''runtime'', ''data'', ''logs''); foreach ($$item in $$items) { $$src = Join-Path $$instDir $$item; if (Test-Path $$src) { $$dst = Join-Path $$backupDir $$item; Copy-Item -Path $$src -Destination $$dst -Recurse -Force -ErrorAction SilentlyContinue; Write-Host (''Backed up: '' + $$item) } }; Write-Host (''Backup completed: '' + $$backupDir)"'
  Pop $0
  DetailPrint "备份完成：backup\pre_install_*"
skip_backup:

; 准备 7z 解压工具
DetailPrint "准备解压工具..."
SetOutPath "$TEMP\TradingAgentsCN-Install"
File "${SEVENZIP_DIR}\7z.exe"
File "${SEVENZIP_DIR}\7z.dll"

; 解压便携版 7z 包（已压缩，zlib 不会重复压缩）
DetailPrint "正在解压程序包..."
SetOutPath "$INSTDIR"
File /oname=package.7z "${PACKAGE_7Z}"

; 使用 7z.exe 解压（-aoa = 覆盖所有已存在文件，确保旧文件被替换）
DetailPrint "正在释放文件（可能需要几分钟）..."
nsExec::ExecToLog '"$TEMP\TradingAgentsCN-Install\7z.exe" x "$INSTDIR\package.7z" -o"$INSTDIR" -y -aoa'
Pop $0

${If} $0 != 0
  MessageBox MB_ICONSTOP "解压程序包失败。错误码：$0$\r$\n$\r$\n请检查安装包是否完整，或联系技术支持。"
  Abort
${EndIf}

; 清理 7z 临时文件
Delete "$INSTDIR\package.7z"
Delete "$TEMP\TradingAgentsCN-Install\7z.exe"
Delete "$TEMP\TradingAgentsCN-Install\7z.dll"
RMDir "$TEMP\TradingAgentsCN-Install"

; 升级模式：恢复配置和数据
${If} $InstallMode == 1
  DetailPrint "恢复配置和数据（升级模式）..."
  nsExec::ExecToLog 'powershell -ExecutionPolicy Bypass -File "$INSTDIR\scripts\installer\restore_backup.ps1" -InstallDir "$INSTDIR"'
  Pop $0
  DetailPrint "配置和数据已恢复 (exit code: $0)"
${EndIf}

;----------------------------------------------------------------------------
; 复制 VC++ 运行库 DLL 到 MongoDB bin 目录（替代 VC Redist 安装）
; 从 vendors\vcredist\ 或系统 System32 复制 vcruntime140.dll 等到 MongoDB bin
;----------------------------------------------------------------------------
DetailPrint "复制 VC++ 运行库文件到 MongoDB 目录..."
nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -Command "$$mongoDir = \"$INSTDIR\vendors\mongodb\"; $$binDir = $$null; if (Test-Path $$mongoDir) { $$dir = Get-ChildItem -Path $$mongoDir -Directory -Filter \"mongodb-win32-*\" -ErrorAction SilentlyContinue | Select-Object -First 1; if ($$dir) { $$binDir = Join-Path $$dir.FullName \"bin\" } }; if ($$binDir -and (Test-Path $$binDir)) { $$vcDir = \"$INSTDIR\vendors\vcredist\"; $$system32 = Join-Path $$env:SystemRoot \"System32\"; $$dlls = @(\"vcruntime140.dll\", \"vcruntime140_1.dll\", \"msvcp140.dll\"); $$copied = 0; foreach ($$dll in $$dlls) { $$src = Join-Path $$vcDir $$dll; if (-not (Test-Path -LiteralPath $$src)) { $$src = Join-Path $$system32 $$dll }; if (Test-Path -LiteralPath $$src) { Copy-Item -LiteralPath $$src -Destination (Join-Path $$binDir $$dll) -Force; $$copied++ } }; Write-Host (\"已复制 $$copied 个 VC 运行库到: \" + $$binDir) } else { Write-Host \"警告：未找到 MongoDB bin 目录，跳过 VC DLL 复制\" }"'
Pop $0

;----------------------------------------------------------------------------
; 验证 MongoDB 运行时（动态查找版本目录，不硬编码）
;----------------------------------------------------------------------------
DetailPrint "验证 MongoDB 运行时依赖..."
Call VerifyMongoRuntime
${If} $MongoRuntimeOk != "1"
  MessageBox MB_ICONSTOP "MongoDB 运行时验证失败。$\r$\n$\r$\n可能原因：$\r$\n  1. VC++ 运行库 DLL 缺失或损坏$\r$\n  2. MongoDB 程序文件不完整$\r$\n$\r$\n请检查 $INSTDIR\vendors\mongodb 目录，或联系技术支持。"
  Abort
${EndIf}
DetailPrint "MongoDB 运行时验证通过：$MongoBinDir"

;----------------------------------------------------------------------------
; 安装 PDF/Word 导出依赖（GTK3、wkhtmltopdf、Pandoc）
; .exe 用 /S 静默安装；.msi 用 msiexec /quiet
;----------------------------------------------------------------------------
DetailPrint "安装 PDF/Word 导出依赖..."
StrCpy $0 "$INSTDIR\vendors\pdf"
${If} ${FileExists} "$0"
  nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -Command "$$d = ''$INSTDIR\vendors\pdf''; if (Test-Path $$d) { Get-ChildItem $$d -File | Where-Object { $$_.Extension -in ''.exe'',''.msi'' } | ForEach-Object { Write-Host (''Running: '' + $$_.Name); if ($$_.Extension -eq ''.msi'') { $$p = Start-Process msiexec.exe -ArgumentList ''/i'',$$_.FullName,''/quiet'' -Wait -PassThru } else { $$p = Start-Process -FilePath $$_.FullName -ArgumentList ''/S'' -Wait -PassThru }; Write-Host (''Exit: '' + $$p.ExitCode) } }"'
  Pop $0
  DetailPrint "PDF/Word 依赖安装完成"
${Else}
  DetailPrint "未找到 PDF/Word 依赖包（vendors\pdf 为空或不存在）"
${EndIf}

;----------------------------------------------------------------------------
; 更新配置文件端口（升级模式跳过，保留旧配置）
;----------------------------------------------------------------------------
${If} $InstallMode != 1
  DetailPrint "更新配置文件端口..."

  ; 调用外部 PowerShell 脚本更新所有端口配置（避免 NSIS 转义问题）
  nsExec::ExecToLog 'powershell -ExecutionPolicy Bypass -File "$INSTDIR\scripts\installer\update_ports.ps1" -InstallDir "$INSTDIR" -BackendPort $BackendPort -MongoPort $MongoPort -RedisPort $RedisPort -NginxPort $NginxPort'
${Else}
  DetailPrint "升级模式：跳过端口配置更新（保留现有配置）"
${EndIf}

;----------------------------------------------------------------------------
; 创建快捷方式（带管理员权限标志）
;----------------------------------------------------------------------------
DetailPrint "创建快捷方式..."
CreateDirectory "$SMPROGRAMS\TradingAgentsCN"
Pop $0

; 开始菜单快捷方式
DetailPrint "创建开始菜单快捷方式..."
CreateShortcut "$SMPROGRAMS\TradingAgentsCN\启动 TradingAgentsCN.lnk" \
  "powershell.exe" \
  '-ExecutionPolicy Bypass -NoExit -Command "Set-Location \"$INSTDIR\"; & \".\start_all.ps1\""' \
  "$INSTDIR\frontend\dist\favicon.ico" \
  0 \
  SW_SHOWNORMAL \
  "" \
  "启动 TradingAgentsCN"

CreateShortcut "$SMPROGRAMS\TradingAgentsCN\停止 TradingAgentsCN.lnk" \
  "powershell.exe" \
  '-ExecutionPolicy Bypass -NoExit -Command "Set-Location \"$INSTDIR\"; & \".\stop_all.ps1\""' \
  "$INSTDIR\frontend\dist\favicon.ico" \
  0 \
  SW_SHOWNORMAL \
  "" \
  "停止 TradingAgentsCN"

CreateShortcut "$SMPROGRAMS\TradingAgentsCN\重启 TradingAgentsCN.lnk" \
  "powershell.exe" \
  '-ExecutionPolicy Bypass -NoExit -Command "Set-Location \"$INSTDIR\"; & \".\restart_all.ps1\""' \
  "$INSTDIR\frontend\dist\favicon.ico" \
  0 \
  SW_SHOWNORMAL \
  "" \
  "重启 TradingAgentsCN"

CreateShortcut "$SMPROGRAMS\TradingAgentsCN\卸载.lnk" \
  "$INSTDIR\Uninstall.exe" \
  "" \
  "$INSTDIR\frontend\dist\favicon.ico" \
  0 \
  SW_SHOWNORMAL \
  "" \
  "卸载 TradingAgentsCN"

; 桌面快捷方式
DetailPrint "创建桌面快捷方式..."
CreateShortcut "$DESKTOP\TradingAgentsCN.lnk" \
  "powershell.exe" \
  '-ExecutionPolicy Bypass -NoExit -Command "Set-Location \"$INSTDIR\"; & \".\start_all.ps1\""' \
  "$INSTDIR\frontend\dist\favicon.ico" \
  0 \
  SW_SHOWNORMAL \
  "" \
  "启动 TradingAgentsCN"

; 设置快捷方式管理员权限标志（修改 .lnk 字节 0x15 的 bit 0x20）
DetailPrint "设置快捷方式管理员权限..."
nsExec::ExecToLog 'powershell -ExecutionPolicy Bypass -Command "try { $$lnkPath = \"$SMPROGRAMS\TradingAgentsCN\启动 TradingAgentsCN.lnk\"; if (Test-Path $$lnkPath) { $$bytes = [System.IO.File]::ReadAllBytes($$lnkPath); $$bytes[0x15] = $$bytes[0x15] -bor 0x20; [System.IO.File]::WriteAllBytes($$lnkPath, $$bytes); Write-Host \"启动快捷方式管理员标志已设置\" } } catch { Write-Host \"Error: $$_\" }"'
Pop $0

nsExec::ExecToLog 'powershell -ExecutionPolicy Bypass -Command "try { $$lnkPath = \"$SMPROGRAMS\TradingAgentsCN\停止 TradingAgentsCN.lnk\"; if (Test-Path $$lnkPath) { $$bytes = [System.IO.File]::ReadAllBytes($$lnkPath); $$bytes[0x15] = $$bytes[0x15] -bor 0x20; [System.IO.File]::WriteAllBytes($$lnkPath, $$bytes); Write-Host \"停止快捷方式管理员标志已设置\" } } catch { Write-Host \"Error: $$_\" }"'
Pop $0

nsExec::ExecToLog 'powershell -ExecutionPolicy Bypass -Command "try { $$lnkPath = \"$SMPROGRAMS\TradingAgentsCN\重启 TradingAgentsCN.lnk\"; if (Test-Path $$lnkPath) { $$bytes = [System.IO.File]::ReadAllBytes($$lnkPath); $$bytes[0x15] = $$bytes[0x15] -bor 0x20; [System.IO.File]::WriteAllBytes($$lnkPath, $$bytes); Write-Host \"重启快捷方式管理员标志已设置\" } } catch { Write-Host \"Error: $$_\" }"'
Pop $0

nsExec::ExecToLog 'powershell -ExecutionPolicy Bypass -Command "try { $$lnkPath = \"$DESKTOP\TradingAgentsCN.lnk\"; if (Test-Path $$lnkPath) { $$bytes = [System.IO.File]::ReadAllBytes($$lnkPath); $$bytes[0x15] = $$bytes[0x15] -bor 0x20; [System.IO.File]::WriteAllBytes($$lnkPath, $$bytes); Write-Host \"桌面快捷方式管理员标志已设置\" } } catch { Write-Host \"Error: $$_\" }"'
Pop $0

DetailPrint "快捷方式创建完成"

;----------------------------------------------------------------------------
; 写入卸载程序和注册表
;----------------------------------------------------------------------------
WriteUninstaller "$INSTDIR\Uninstall.exe"

; 控制面板卸载注册表项
WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\TradingAgentsCN" "DisplayName" "TradingAgentsCN"
WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\TradingAgentsCN" "UninstallString" "$INSTDIR\Uninstall.exe"
WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\TradingAgentsCN" "DisplayVersion" "${PRODUCT_VERSION}"
WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\TradingAgentsCN" "InstallLocation" "$INSTDIR"
WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\TradingAgentsCN" "Publisher" "TradingAgents Team"

DetailPrint "安装完成！"
DetailPrint "请使用桌面快捷方式或开始菜单启动 TradingAgentsCN"

SectionEnd

;============================================================================
; 卸载流程
;============================================================================
Section "Uninstall"
  DetailPrint "正在删除快捷方式..."
  Delete "$SMPROGRAMS\TradingAgentsCN\启动 TradingAgentsCN.lnk"
  Delete "$SMPROGRAMS\TradingAgentsCN\停止 TradingAgentsCN.lnk"
  Delete "$SMPROGRAMS\TradingAgentsCN\卸载.lnk"
  RMDir  "$SMPROGRAMS\TradingAgentsCN"
  Delete "$DESKTOP\TradingAgentsCN.lnk"

  DetailPrint "正在删除注册表项..."
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\TradingAgentsCN"

  DetailPrint "正在删除安装文件..."
  Delete "$INSTDIR\Uninstall.exe"
  RMDir /r "$INSTDIR"

  DetailPrint "卸载完成"
SectionEnd
