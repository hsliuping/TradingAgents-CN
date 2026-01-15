# 快速修复指南 - TradingAgents-CN Pro

## 🚨 常见问题快速解决

### 问题 1: 编译卡住 "copying *.pyd"

**症状**: 构建时卡在复制 `.pyd` 文件

**快速解决**:
```powershell
# 方法 1: 终止所有 Python 进程（推荐）
.\scripts\deployment\check_python_processes.ps1 -KillAll

# 方法 2: 手动停止
# 在运行 FastAPI 的终端按 Ctrl+C

# 然后重新构建
.\scripts\deployment\clean_and_rebuild.ps1
```

**详细文档**: `docs/deployment/FIX_CYTHON_BUILD_HANG.md`

---

### 问题 2: 安装包运行时找不到提示词模块

**症状**: `ModuleNotFoundError: No module named 'core.prompts.analyst_prompts'`

**快速解决**:
```powershell
# 清理并重新构建
.\scripts\deployment\clean_and_rebuild.ps1

# 验证文件存在
.\scripts\deployment\verify_prompts_in_portable.ps1

# 重新构建安装包
.\scripts\windows-installer\build\build_installer.ps1 -SkipPortablePackage
```

**详细文档**: `docs/deployment/FIX_PROMPTS_MISSING_ISSUE.md`

---

### 问题 3: 中性评估报告计算错误

**症状**: 目标价低于当前价，但显示正收益

**快速解决**:
```powershell
# 激活虚拟环境
.\venv\Scripts\Activate.ps1

# 运行修复脚本
python scripts/fix_neutral_analyst_calculation.py
```

**详细文档**: `scripts/fix_neutral_analyst_calculation.py`

---

## 📦 完整构建流程（推荐）

```powershell
# 1. 检查并终止 Python 进程
.\scripts\deployment\check_python_processes.ps1 -KillAll

# 2. 清理并重新构建便携版
.\scripts\deployment\clean_and_rebuild.ps1

# 3. 验证提示词文件
.\scripts\deployment\verify_prompts_in_portable.ps1

# 4. 构建 Windows 安装包
.\scripts\windows-installer\build\build_installer.ps1 -SkipPortablePackage

# 5. 测试安装包
# 运行生成的 .exe 文件
```

---

## 🛠️ 常用命令

### 进程管理
```powershell
# 查看所有 Python 进程
Get-Process -Name "python*"

# 终止所有 Python 进程
Get-Process -Name "python*" | Stop-Process -Force

# 使用脚本检查
.\scripts\deployment\check_python_processes.ps1
```

### 清理操作
```powershell
# 清理便携版目录
Remove-Item -Path "release\TradingAgentsCN-portable" -Recurse -Force

# 清理编译产物
Remove-Item -Path "build" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "release\TradingAgentsCN-portable\core\licensing\*.pyd" -Force
```

### 验证操作
```powershell
# 验证提示词文件
.\scripts\deployment\verify_prompts_in_portable.ps1

# 验证便携版目录结构
Get-ChildItem -Path "release\TradingAgentsCN-portable" -Recurse -Directory
```

---

## 📚 详细文档索引

| 问题 | 文档位置 |
|------|---------|
| Cython 编译卡住 | `docs/deployment/FIX_CYTHON_BUILD_HANG.md` |
| 提示词文件缺失 | `docs/deployment/FIX_PROMPTS_MISSING_ISSUE.md` |
| 中性评估计算错误 | `scripts/fix_neutral_analyst_calculation.py` |
| 完整修复总结 | `FIXES_SUMMARY_2026-01-14.md` |

---

## ⚠️ 注意事项

1. **构建前务必停止所有 Python 进程**，否则可能卡住
2. **必须清理旧的便携版目录**，否则会使用缓存的旧文件
3. **验证步骤不可跳过**，确保文件完整性
4. **保存所有未保存的工作**，再终止 Python 进程

---

## 🆘 仍然有问题？

1. 查看详细文档（见上方索引）
2. 检查终端输出的错误信息
3. 确认所有 Python 进程已关闭
4. 尝试重启 PowerShell 终端
5. 最后手段：重启计算机

---

**更新日期**: 2026-01-14

