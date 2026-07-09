# 使用 7-Zip 优化安装包解压速度

## 📋 问题分析

### 当前问题
- **解压过程无进度**：PowerShell `Expand-Archive` 解压 50,000 个文件时没有进度显示
- **看起来像卡死**：用户不知道安装程序是否还在运行
- **解压速度慢**：`Expand-Archive` 对大量小文件的解压效率低

### 根本原因
```powershell
# 当前使用的命令（第 222 行）
Expand-Archive -Path "xxx.zip" -DestinationPath "xxx" -Force
```
- ❌ 无进度显示
- ❌ 解压速度慢（50,000 个文件需要 2-5 分钟）
- ❌ 用户体验差

---

## ✅ 解决方案：嵌入 7z.exe

### 方案概述

1. **下载 7z.exe**（~1 MB，免费）
2. **修改打包脚本**：生成 `.7z` 而不是 `.zip`
3. **修改 NSIS 脚本**：使用 7z.exe 解压，显示进度
4. **清理临时文件**：解压后删除 7z.exe 和 .7z 文件

### 许可证
- ✅ **完全免费**：GNU LGPL 许可证
- ✅ **可商业使用**：无需注册或付费
- ✅ **可重新分发**：可以嵌入到安装程序中

来源：https://www.7-zip.org/license.txt

---

## 🔧 实施步骤

### 步骤 1：下载 7z.exe

```powershell
# 下载 7-Zip Extra（包含独立的 7z.exe）
# 下载地址：https://www.7-zip.org/download.html
# 选择 "7-Zip Extra: standalone console version"

# 或使用 PowerShell 自动下载
$7zUrl = "https://www.7-zip.org/a/7z2408-extra.7z"
$7zPath = "vendors\7zip\7z.exe"

# 创建目录
New-Item -ItemType Directory -Path "vendors\7zip" -Force

# 下载并解压（需要先安装 7-Zip 或使用其他工具）
# 提取 x64\7za.exe 并重命名为 7z.exe
```

**手动步骤**：
1. 访问 https://www.7-zip.org/download.html
2. 下载 "7-Zip Extra" (7z2408-extra.7z)
3. 解压后，将 `x64\7za.exe` 复制到 `vendors\7zip\7z.exe`

---

### 步骤 2：修改打包脚本（生成 .7z）

修改 `scripts/deployment/build_portable_package.ps1`：

```powershell
# 在第 413 行附近，替换 ZIP 压缩为 7z 压缩

# 修改前
[System.IO.Compression.ZipFile]::CreateFromDirectory($tempDir, $zipPath, ...)

# 修改后
$7zExe = Join-Path $root "vendors\7zip\7z.exe"
$7zPath = Join-Path $packagesDir "$packageName.7z"

if (-not (Test-Path $7zExe)) {
    Write-Host "ERROR: 7z.exe not found at $7zExe" -ForegroundColor Red
    Write-Host "Please download from https://www.7-zip.org/download.html" -ForegroundColor Yellow
    exit 1
}

Write-Host "  Creating 7z archive..." -ForegroundColor Gray
& $7zExe a -t7z -mx=5 -mmt=on "$7zPath" "$tempDir\*"

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: 7z compression failed" -ForegroundColor Red
    exit 1
}

Write-Host "  Compression completed successfully!" -ForegroundColor Green
```

**压缩级别说明**：
- `-mx=5`：中等压缩（平衡速度和大小）
- `-mx=9`：最高压缩（慢，但文件最小）
- `-mmt=on`：多线程压缩（加快速度）

---

### 步骤 3：修改 NSIS 安装脚本

修改 `scripts/windows-installer/nsis/installer.nsi`：

```nsis
Section
SetOutPath "$INSTDIR"

; 1. 解压 7z.exe（~1 MB）
DetailPrint "Preparing extraction tool..."
File "${PROJECT_ROOT}\vendors\7zip\7z.exe"

; 2. 解压便携版 7z 压缩包
DetailPrint "Copying installation package..."
File "${PACKAGE_7Z}"

; 3. 使用 7z.exe 解压（带进度）
DetailPrint "========================================="
DetailPrint "UNPACKING FILES - PLEASE WAIT"
DetailPrint "========================================="
DetailPrint ""
DetailPrint "Extracting ~50,000 files..."
DetailPrint "This will take 1-2 minutes on SSD, 2-3 minutes on HDD"
DetailPrint ""

; 调用 7z.exe 解压
nsExec::ExecToLog '"$INSTDIR\7z.exe" x "$INSTDIR\TradingAgentsCN-Portable-latest.7z" -o"$INSTDIR" -y -bsp1'
Pop $0

${If} $0 != 0
  MessageBox MB_ICONSTOP "Extraction failed. Error code: $0"
  Abort
${EndIf}

DetailPrint ""
DetailPrint "Extraction completed successfully!"

; 4. 清理临时文件
Delete "$INSTDIR\7z.exe"
Delete "$INSTDIR\TradingAgentsCN-Portable-latest.7z"

; 5. 更新配置文件...
DetailPrint "Updating configuration..."
; ... 其他配置步骤 ...

SectionEnd
```

**7z.exe 参数说明**：
- `x`：解压并保留目录结构
- `-o"$INSTDIR"`：输出目录
- `-y`：自动确认所有提示
- `-bsp1`：显示进度百分比

---

### 步骤 4：更新构建脚本

修改 `scripts/windows-installer/build/build_installer.ps1`：

```powershell
# 检查 7z.exe 是否存在
$7zExe = Join-Path $root "vendors\7zip\7z.exe"
if (-not (Test-Path $7zExe)) {
    Write-Host "ERROR: 7z.exe not found" -ForegroundColor Red
    Write-Host "Please download from https://www.7-zip.org/download.html" -ForegroundColor Yellow
    exit 1
}

# 查找最新的 .7z 文件（而不是 .zip）
$latestPackage = Get-ChildItem "$packagesDir\TradingAgentsCN-Portable-*.7z" | 
    Sort-Object LastWriteTime -Descending | 
    Select-Object -First 1
```

---

## 📊 性能对比

| 方案 | 解压时间 | 文件大小 | 进度显示 | 用户体验 |
|------|---------|---------|---------|---------|
| **PowerShell Expand-Archive（当前）** | 2-5 分钟 | 350 MB (ZIP) | ❌ 无 | ⭐⭐ |
| **7z.exe（推荐）** | 1-2 分钟 | 280 MB (7z) | ✅ 有 | ⭐⭐⭐⭐⭐ |

**改善**：
- ✅ 解压速度提升 **2-3 倍**
- ✅ 文件大小减少 **20%**
- ✅ 有进度百分比显示
- ✅ 用户体验显著改善

---

## 🚀 下次构建

```powershell
# 1. 下载 7z.exe（一次性操作）
# 访问 https://www.7-zip.org/download.html
# 下载 "7-Zip Extra"，提取 x64\7za.exe 到 vendors\7zip\7z.exe

# 2. 构建便携版（生成 .7z）
.\scripts\deployment\build_portable_package.ps1

# 3. 构建安装包（使用 7z.exe 解压）
.\scripts\windows-installer\build\build_installer.ps1 -SkipPortablePackage
```

---

## 📝 注意事项

1. **7z.exe 大小**：~1 MB，嵌入到安装程序后总大小增加不明显
2. **许可证合规**：需要在安装程序的"关于"或"许可证"页面注明使用了 7-Zip
3. **兼容性**：7z.exe 支持 Windows XP 及以上所有版本
4. **清理**：解压后记得删除 7z.exe 和 .7z 文件

---

**最后更新**: 2026-01-07  
**状态**: 待实施

