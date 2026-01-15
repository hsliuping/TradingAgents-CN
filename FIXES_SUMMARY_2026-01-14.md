# 修复总结 - 2026-01-14

## 问题 1: 中性评估师计算错误

### 问题描述
在中性风险评估报告中，当目标价低于当前价时，预期收益计算错误：
- 当前价: ¥369.23
- 目标价: ¥350.00
- **错误显示**: +18.4%
- **正确应为**: -5.2%

### 根本原因
LLM 生成的内容中计算公式错误，没有正确处理目标价低于当前价的情况。

### 解决方案
创建了修复脚本 `scripts/fix_neutral_analyst_calculation.py`，在提示词中添加明确的计算公式说明：

```python
# 在 analysis_requirements 中添加
**预期收益计算公式**（必须严格遵守）：
预期收益 = (目标价 - 当前价) / 当前价 × 100%

示例：
- 当前价 ¥369.23，目标价 ¥350.00
  → 预期收益 = (350 - 369.23) / 369.23 × 100% = -5.2%
- 当前价 ¥369.23，目标价 ¥420.00
  → 预期收益 = (420 - 369.23) / 369.23 × 100% = +13.7%
```

### 相关文件
- `scripts/fix_neutral_analyst_calculation.py` - 修复脚本
- `core/prompts/risk_prompts.py` - 提示词模板

---

## 问题 2: Windows 安装包中提示词文件缺失

### 问题描述
在 Windows 安装包中运行时出现错误：
```
ModuleNotFoundError: No module named 'core.prompts.analyst_prompts'
```

### 根本原因
编译脚本 `scripts/deployment/compile_core_hybrid.ps1` 在编译 `core/` 目录时，会删除所有 `.py` 源文件（只保留 `.pyc` 字节码），但 `core/prompts/` 目录中的文件是**提示词模板**，不应该被删除。

### 解决方案

#### 1. 修改编译脚本
在 `scripts/deployment/compile_core_hybrid.ps1` 中添加保留目录逻辑：

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
    # 不删除源文件
}
```

#### 2. 创建验证脚本
`scripts/deployment/verify_prompts_in_portable.ps1` - 验证便携版中是否包含所有提示词文件

#### 3. 创建清理重建脚本
`scripts/deployment/clean_and_rebuild.ps1` - 自动清理旧目录并重新构建

### 使用方法

```powershell
# 方法 1: 使用自动化脚本（推荐）
.\scripts\deployment\clean_and_rebuild.ps1

# 方法 2: 手动步骤
# 1. 清理旧目录
Remove-Item -Path "release\TradingAgentsCN-portable" -Recurse -Force

# 2. 重新构建
.\scripts\deployment\build_pro_package.ps1

# 3. 验证
.\scripts\deployment\verify_prompts_in_portable.ps1

# 4. 构建安装包
.\scripts\windows-installer\build\build_installer.ps1 -SkipPortablePackage
```

### 相关文件
- `scripts/deployment/compile_core_hybrid.ps1` - 编译脚本（已修改）
- `scripts/deployment/verify_prompts_in_portable.ps1` - 验证脚本（新建）
- `scripts/deployment/clean_and_rebuild.ps1` - 清理重建脚本（新建）
- `docs/deployment/FIX_PROMPTS_MISSING_ISSUE.md` - 详细文档（新建）

---

## 测试清单

### 问题 1 测试
- [ ] 运行修复脚本更新数据库
- [ ] 创建新的分析任务
- [ ] 验证中性评估报告中的预期收益计算正确
- [ ] 测试目标价高于当前价的情况
- [ ] 测试目标价低于当前价的情况

### 问题 2 测试
- [ ] 清理旧的便携版目录
- [ ] 重新构建便携版
- [ ] 验证 `core/prompts/` 目录存在
- [ ] 验证所有 `.py` 文件存在（analyst_prompts.py, debate_prompts.py, risk_prompts.py）
- [ ] 构建 Windows 安装包
- [ ] 安装并运行测试
- [ ] 验证分析功能正常（不再出现 ModuleNotFoundError）

---

## 注意事项

1. **问题 1** 只影响新创建的分析任务，已有的分析任务不受影响
2. **问题 2** 需要完全清理旧的便携版目录，否则可能仍然使用缓存的旧文件
3. 两个问题都已修复，但需要重新构建和部署才能生效

---

---

## 问题 3: Cython 编译卡住问题

### 问题描述
运行 `build_pro_package.ps1` 时，编译过程卡在复制 `.pyd` 文件这一步：
```
copying build\lib.win-amd64-cpython-310\core\licensing\*.pyd -> core\licensing
```

**现象**:
- 第一次执行卡住，需要手动终止
- 第二次执行正常完成

### 根本原因
- `.pyd` 文件是 Python 扩展模块（类似 DLL）
- 当 Python 进程（如 FastAPI 服务器）加载这些模块后，Windows 会锁定文件
- 编译脚本试图覆盖已锁定的文件，导致卡住
- 第二次执行成功是因为用户终止了进程，文件锁被释放

### 解决方案

#### 1. 修改编译脚本
在 `scripts/deployment/compile_core_hybrid.ps1` 中，编译前先删除旧的 `.pyd` 文件：

```powershell
# 🔥 在编译前，先删除旧的 .pyd 文件（避免文件锁定）
Write-Host "  Cleaning old .pyd files..." -ForegroundColor Gray
Get-ChildItem -Path $licensingDir -Filter "*.pyd" -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        Remove-Item -Path $_.FullName -Force -ErrorAction Stop
        Write-Host "    Removed: $($_.Name)" -ForegroundColor Gray
    } catch {
        Write-Host "    ⚠️  Cannot remove $($_.Name) (file may be in use)" -ForegroundColor Yellow
        Write-Host "    Please close all Python processes and try again" -ForegroundColor Yellow
    }
}
```

#### 2. 创建进程检查脚本
`scripts/deployment/check_python_processes.ps1` - 检查并管理 Python 进程

```powershell
# 检查进程
.\scripts\deployment\check_python_processes.ps1

# 强制终止所有 Python 进程
.\scripts\deployment\check_python_processes.ps1 -KillAll
```

#### 3. 更新清理重建脚本
在 `clean_and_rebuild.ps1` 中添加自动进程检查

### 使用方法

```powershell
# 方法 1: 手动停止 Python 进程（推荐）
# 1. 停止 FastAPI 服务器（在运行服务器的终端按 Ctrl+C）
# 2. 关闭 Jupyter Notebook
# 3. 退出 Python 交互式终端
# 4. 运行构建
.\scripts\deployment\clean_and_rebuild.ps1

# 方法 2: 自动终止所有 Python 进程（快速但可能丢失未保存的工作）
.\scripts\deployment\check_python_processes.ps1 -KillAll
.\scripts\deployment\clean_and_rebuild.ps1
```

### 相关文件
- `scripts/deployment/compile_core_hybrid.ps1` - 编译脚本（已修改）
- `scripts/deployment/check_python_processes.ps1` - 进程检查脚本（新建）
- `scripts/deployment/clean_and_rebuild.ps1` - 清理重建脚本（已更新）
- `docs/deployment/FIX_CYTHON_BUILD_HANG.md` - 详细文档（新建）

---

## 测试清单

### 问题 1 测试
- [ ] 运行修复脚本更新数据库
- [ ] 创建新的分析任务
- [ ] 验证中性评估报告中的预期收益计算正确
- [ ] 测试目标价高于当前价的情况
- [ ] 测试目标价低于当前价的情况

### 问题 2 测试
- [ ] 清理旧的便携版目录
- [ ] 重新构建便携版
- [ ] 验证 `core/prompts/` 目录存在
- [ ] 验证所有 `.py` 文件存在（analyst_prompts.py, debate_prompts.py, risk_prompts.py）
- [ ] 构建 Windows 安装包
- [ ] 安装并运行测试
- [ ] 验证分析功能正常（不再出现 ModuleNotFoundError）

### 问题 3 测试
- [ ] 启动 FastAPI 服务器
- [ ] 运行构建脚本（应该自动清理 .pyd 文件）
- [ ] 验证不再卡住
- [ ] 测试进程检查脚本
- [ ] 测试 -KillAll 参数

---

## 注意事项

1. **问题 1** 只影响新创建的分析任务，已有的分析任务不受影响
2. **问题 2** 需要完全清理旧的便携版目录，否则可能仍然使用缓存的旧文件
3. **问题 3** 构建前建议先停止所有 Python 进程，避免文件锁定
4. 所有问题都已修复，但需要重新构建和部署才能生效

---

## 更新日期
2026-01-14

