# 检查 API Key 获取日志的脚本
# 用法: .\scripts\check_api_key_logs.ps1 [trace_id]

param(
    [string]$TraceId = "",
    [int]$Lines = 50
)

$logFile = "logs\tradingagents.log"

if (-not (Test-Path $logFile)) {
    Write-Host "❌ 日志文件不存在: $logFile" -ForegroundColor Red
    exit 1
}

Write-Host "`n🔍 搜索 API Key 相关日志..." -ForegroundColor Cyan
Write-Host "=" * 80

if ($TraceId) {
    Write-Host "📌 搜索 Trace ID: $TraceId" -ForegroundColor Yellow
    $pattern = "trace_id.*$TraceId"
} else {
    Write-Host "📌 搜索最近的 API Key 日志（最后 $Lines 条）" -ForegroundColor Yellow
    $pattern = "\[同步查询\]|\[依赖提供者\].*API Key|\[创建LLM\]|API Key.*来源"
}

# 搜索日志
if ($TraceId) {
    $results = Get-Content $logFile | Select-String -Pattern $pattern | Select-Object -Last $Lines
} else {
    $results = Get-Content $logFile | Select-String -Pattern $pattern | Select-Object -Last $Lines
}

if ($results) {
    Write-Host "`n✅ 找到 $($results.Count) 条相关日志:`n" -ForegroundColor Green
    
    foreach ($line in $results) {
        # 解析 JSON 日志
        try {
            $json = $line -replace '^.*?(\{.*\}).*$', '$1' | ConvertFrom-Json
            $time = $json.time
            $level = $json.level
            $name = $json.name
            $message = $json.message
            $traceId = $json.trace_id
            
            # 根据日志类型设置颜色
            $color = "White"
            if ($message -match "✅.*使用.*API Key") {
                $color = "Green"
            } elseif ($message -match "⚠️|❌") {
                $color = "Yellow"
            } elseif ($message -match "🔍") {
                $color = "Cyan"
            }
            
            Write-Host "[$time] [$level] [$name]" -ForegroundColor Gray -NoNewline
            Write-Host " $message" -ForegroundColor $color
            if ($traceId -and $traceId -ne "-") {
                Write-Host "   Trace ID: $traceId" -ForegroundColor DarkGray
            }
        } catch {
            # 如果不是 JSON 格式，直接输出
            Write-Host $line
        }
        Write-Host ""
    }
    
    Write-Host "`n" + "=" * 80
    Write-Host "📊 日志分析建议:" -ForegroundColor Cyan
    Write-Host "1. 查找 '[同步查询] ✅ 使用模型配置的 API Key（优先级1）' - 表示从数据库模型配置获取" -ForegroundColor White
    Write-Host "2. 查找 '[同步查询] ✅ 使用厂家配置的 API Key（优先级2）' - 表示从数据库厂家配置获取" -ForegroundColor White
    Write-Host "3. 查找 '[同步查询] ✅ 使用环境变量的 API Key（优先级3）' - 表示从环境变量获取" -ForegroundColor White
    Write-Host "4. 查找 '[依赖提供者] Quick API Key 来源' - 查看最终使用的 API Key 来源" -ForegroundColor White
    Write-Host "5. 查找 '[创建LLM] 🔑 [API Key] 传入值' - 查看传递给 LLM 的 API Key 状态" -ForegroundColor White
    
} else {
    Write-Host "`n⚠️ 未找到相关日志" -ForegroundColor Yellow
    Write-Host "提示: 请先运行一次分析任务，然后使用 trace_id 参数搜索特定任务的日志" -ForegroundColor Gray
}

Write-Host "`n💡 使用示例:" -ForegroundColor Cyan
Write-Host "  .\scripts\check_api_key_logs.ps1" -ForegroundColor White
Write-Host "  .\scripts\check_api_key_logs.ps1 -TraceId 'f4042050-f64a-4ea1-a039-df7e9cda182b'" -ForegroundColor White
