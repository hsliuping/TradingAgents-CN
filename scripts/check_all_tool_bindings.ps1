# 检查所有工具绑定的一致性

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "检查所有工具绑定的一致性" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 激活虚拟环境
if (Test-Path "venv\Scripts\Activate.ps1") {
    & "venv\Scripts\Activate.ps1"
} elseif (Test-Path "env\Scripts\Activate.ps1") {
    & "env\Scripts\Activate.ps1"
} else {
    Write-Host "错误: 找不到虚拟环境" -ForegroundColor Red
    Read-Host "按任意键退出"
    exit 1
}

# 运行检查脚本
python scripts\check_all_tool_bindings.py

Read-Host "按任意键退出"

