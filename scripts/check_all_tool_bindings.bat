@echo off
REM 检查所有工具绑定的一致性

echo ========================================
echo 检查所有工具绑定的一致性
echo ========================================

REM 激活虚拟环境
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else if exist env\Scripts\activate.bat (
    call env\Scripts\activate.bat
) else (
    echo 错误: 找不到虚拟环境
    pause
    exit /b 1
)

REM 运行检查脚本
python scripts\check_all_tool_bindings.py

pause

