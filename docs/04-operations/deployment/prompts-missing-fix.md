# 修复 Windows 安装包中提示词文件缺失问题

## 问题描述

在 Windows 安装包中，`core/prompts/` 目录下的 Python 源文件（`.py`）被编译脚本删除了，导致运行时找不到提示词模板，出现以下错误：

```
ModuleNotFoundError: No module named 'core.prompts.analyst_prompts'
```

## 根本原因

在 `scripts/deployment/compile_core_hybrid.ps1` 编译脚本中，为了保护代码，会将所有 `.py` 文件编译为 `.pyc` 字节码，然后删除源文件。但是 `core/prompts/` 目录中的文件是**提示词模板**，不应该被删除。

## 解决方案

### 1. 修改编译脚本

已修改 `scripts/deployment/compile_core_hybrid.ps1`，在删除源文件时跳过 `prompts/` 目录：

```powershell
# 🔥 保留的目录（不删除源码）
$keepDirs = @(
    "prompts"  # 提示词模板目录，必须保留源码
)

# 检查是否在保留目录中
$inKeepDir = $false
foreach ($keepDir in $keepDirs) {
    if ($relativePath -like "*\$keepDir\*" -or $relativePath -like "$keepDir\*") {
        $inKeepDir = $true
        break
    }
}

if ($inKeepDir) {
    Write-Host "  Kept (in prompts/): $relativePath" -ForegroundColor Cyan
} elseif (...) {
    # 其他逻辑
}
```

### 2. 清理旧的便携版目录

由于之前构建的便携版目录中已经删除了提示词文件，需要清理并重新构建：

```powershell
# 方法 1: 使用自动化脚本（推荐）
.\scripts\deployment\clean_and_rebuild.ps1

# 方法 2: 手动清理
Remove-Item -Path "release\TradingAgentsCN-portable" -Recurse -Force
.\scripts\deployment\build_pro_package.ps1
```

### 3. 验证修复

运行验证脚本检查提示词文件是否存在：

```powershell
.\scripts\deployment\verify_prompts_in_portable.ps1
```

预期输出：

```
✅ core/prompts/ directory exists

Checking Python files in core/prompts/...

Python source files (.py): 3
  ✅ core\prompts\analyst_prompts.py
  ✅ core\prompts\debate_prompts.py
  ✅ core\prompts\risk_prompts.py

Checking critical files...

  ✅ core\prompts\analyst_prompts.py
  ✅ core\prompts\debate_prompts.py
  ✅ core\prompts\risk_prompts.py

✅ All prompts files are present!
```

### 4. 重新构建 Windows 安装包

```powershell
# 使用已清理的便携版目录构建安装包
.\scripts\windows-installer\build\build_installer.ps1 -SkipPortablePackage
```

## 完整构建流程

```powershell
# 1. 清理并重新构建便携版（包含验证）
.\scripts\deployment\clean_and_rebuild.ps1

# 2. 构建 Windows 安装包（跳过便携版构建，使用已有的）
.\scripts\windows-installer\build\build_installer.ps1 -SkipPortablePackage

# 3. 测试安装包
# 运行生成的 .exe 文件并验证功能
```

## 相关文件

- **编译脚本**: `scripts/deployment/compile_core_hybrid.ps1`
- **构建脚本**: `scripts/deployment/build_pro_package.ps1`
- **安装包脚本**: `scripts/windows-installer/build/build_installer.ps1`
- **验证脚本**: `scripts/deployment/verify_prompts_in_portable.ps1`
- **清理重建脚本**: `scripts/deployment/clean_and_rebuild.ps1`

## 注意事项

1. **不要跳过清理步骤**：旧的便携版目录中可能包含已删除的提示词文件，必须清理后重新构建
2. **验证是必须的**：每次构建后都应该运行验证脚本确保文件完整
3. **其他需要保留的目录**：如果将来有其他目录也需要保留源码，在 `$keepDirs` 数组中添加即可

## 测试清单

- [ ] 清理旧的便携版目录
- [ ] 重新构建便携版
- [ ] 验证 `core/prompts/` 目录存在
- [ ] 验证所有 `.py` 文件存在
- [ ] 构建 Windows 安装包
- [ ] 安装并运行测试
- [ ] 验证分析功能正常（不再出现 ModuleNotFoundError）

## 更新日期

2026-01-14

