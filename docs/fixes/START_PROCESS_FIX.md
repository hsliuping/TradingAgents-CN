# Start-Process 参数冲突修复

## 问题描述

在 Windows 安装包安装后，运行 `start_all.ps1` 时出现以下错误：

```
Start-Process : Parameters "-NoNewWindow" and "-WindowStyle" cannot be specified at the same time.
At C:\TradingAgentsCN111f\start_all.ps1:476 char:23
+     $backendProcess = Start-Process -FilePath $pythonExe `
+                       ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (:) [Start-Process], InvalidOperationException
    + FullyQualifiedErrorId : InvalidOperationException,Microsoft.PowerShell.Commands.StartProcessCommand
```

## 根本原因

PowerShell 的 `Start-Process` 命令不允许同时使用以下两个参数：
- `-WindowStyle Hidden` - 隐藏窗口
- `-NoNewWindow` - 在当前窗口运行

这两个参数是互斥的。

## 修复内容

### 1. 修复 `scripts/installer/start_all.ps1`

**位置**: 第 475-484 行

**修复前**:
```powershell
$backendProcess = Start-Process -FilePath $pythonExe `
    -ArgumentList "`"$appMain`"" `
    -WorkingDirectory $root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $backendLog `
    -RedirectStandardError $backendErrorLog `
    -PassThru `
    -NoNewWindow  # ❌ 与 -WindowStyle 冲突
```

**修复后**:
```powershell
# 注意：-WindowStyle 和 -NoNewWindow 不能同时使用
# 使用 -WindowStyle Hidden 来隐藏后台进程窗口
$backendProcess = Start-Process -FilePath $pythonExe `
    -ArgumentList "`"$appMain`"" `
    -WorkingDirectory $root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $backendLog `
    -RedirectStandardError $backendErrorLog `
    -PassThru  # ✅ 移除了 -NoNewWindow
```

### 2. 更新 `scripts/windows-installer/prepare/build_portable.ps1`

添加了将启动脚本复制到根目录的逻辑，确保 Windows 安装包能够正确找到 `start_all.ps1`：

```powershell
# Copy startup scripts to root directory (for Windows installer)
Write-Log "Copying startup scripts to root directory..."
$startupScripts = @(
    "start_all.ps1",
    "start_services_clean.ps1",
    "stop_all.ps1"
)

foreach ($script in $startupScripts) {
    $sourceScript = Join-Path $root "scripts\installer\$script"
    $destScript = Join-Path $out $script
    
    if (Test-Path $sourceScript) {
        Copy-Item -Path $sourceScript -Destination $destScript -Force
        Write-Log "Copied $script to root directory"
    } else {
        Write-Log "WARNING: $script not found at $sourceScript" "WARNING"
    }
}
```

## 验证方法

运行测试脚本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test_start_process_fix.ps1
```

预期输出：
```
========================================
测试 Start-Process 参数修复
========================================

检查文件: scripts\installer\start_all.ps1
  ✅ 通过检查

检查文件: scripts\installer\start_services_clean.ps1
  ✅ 通过检查

========================================
测试结果汇总
========================================
总测试数: 7
通过: 2
失败: 0

🎉 所有测试通过！
```

## 重新构建安装包

修复后需要重新构建 Windows 安装包：

```powershell
# 1. 更新版本号（可选）
echo "1.0.3" > VERSION

# 2. 构建 Windows 安装包
.\scripts\windows-installer\build\build_installer.ps1
```

## 影响范围

- ✅ Windows 安装包（`.exe`）
- ✅ 便携版（`.7z`）
- ❌ Docker 部署（不受影响）

## 相关文件

- `scripts/installer/start_all.ps1` - 主启动脚本
- `scripts/installer/start_services_clean.ps1` - 服务启动脚本
- `scripts/windows-installer/prepare/build_portable.ps1` - 便携版构建脚本
- `scripts/windows-installer/nsis/installer.nsi` - NSIS 安装脚本
- `scripts/test_start_process_fix.ps1` - 测试脚本

## 参考资料

- [PowerShell Start-Process 文档](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/start-process)
- `-WindowStyle`: 指定窗口样式（Normal, Hidden, Minimized, Maximized）
- `-NoNewWindow`: 在当前控制台窗口中启动进程（不能与 `-WindowStyle` 同时使用）

---

**修复日期**: 2026-01-16  
**修复版本**: v1.0.3+  
**修复人员**: TradingAgents-CN Team

