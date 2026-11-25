# 运行提示词对比脚本

Write-Host "激活虚拟环境..." -ForegroundColor Cyan
.\env\Scripts\Activate.ps1

Write-Host "`n运行提示词对比脚本..." -ForegroundColor Cyan
python scripts/compare_prompts.py

Write-Host "`n完成！" -ForegroundColor Green

