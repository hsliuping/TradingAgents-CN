# 运行辩论功能测试

Write-Host "激活虚拟环境..." -ForegroundColor Cyan
.\venv\Scripts\Activate.ps1

Write-Host "`n运行单元测试..." -ForegroundColor Cyan
python -m pytest tests/core/agents/test_researcher_debate.py -v

Write-Host "`n运行集成测试..." -ForegroundColor Cyan
python -m pytest tests/integration/test_debate_workflow.py -v -s

Write-Host "`n测试完成！" -ForegroundColor Green

