# TradingAgents-CN Pro - 数据库初始化脚本
# 用于便携版首次启动时初始化 MongoDB 数据库

param(
    [string]$MongoHost = "localhost",
    [int]$MongoPort = 27017,
    [string]$ConfigFile = "install\database_export_config_2025-11-13.json"
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  TradingAgents-CN Pro - 数据库初始化                      ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# 检查 MongoDB 是否运行
Write-Host "🔍 检查 MongoDB 服务..." -ForegroundColor Yellow
try {
    $mongoTest = & python -c "from pymongo import MongoClient; client = MongoClient('mongodb://${MongoHost}:${MongoPort}/', serverSelectionTimeoutMS=2000); client.admin.command('ping'); print('OK')" 2>&1
    if ($mongoTest -notmatch "OK") {
        throw "MongoDB 连接失败"
    }
    Write-Host "✅ MongoDB 服务正常运行" -ForegroundColor Green
} catch {
    Write-Host "❌ MongoDB 服务未运行或无法连接" -ForegroundColor Red
    Write-Host "   请先启动 MongoDB 服务" -ForegroundColor Yellow
    exit 1
}

# 检查配置文件
Write-Host ""
Write-Host "📂 检查配置文件..." -ForegroundColor Yellow
if (-not (Test-Path $ConfigFile)) {
    Write-Host "❌ 配置文件不存在: $ConfigFile" -ForegroundColor Red
    Write-Host "   请确保配置文件存在" -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ 配置文件存在: $ConfigFile" -ForegroundColor Green

# 获取文件大小
$fileSize = (Get-Item $ConfigFile).Length / 1MB
Write-Host "   文件大小: $([math]::Round($fileSize, 2)) MB" -ForegroundColor Cyan

# 导入配置数据
Write-Host ""
Write-Host "🚀 开始导入配置数据..." -ForegroundColor Yellow
Write-Host ""

try {
    # 运行导入脚本
    $importScript = "scripts\import_config_and_create_user.py"
    
    if (-not (Test-Path $importScript)) {
        throw "导入脚本不存在: $importScript"
    }
    
    # 执行导入（覆盖模式）
    Write-Host "   执行导入脚本..." -ForegroundColor Cyan
    & python $importScript $ConfigFile --host --overwrite
    
    if ($LASTEXITCODE -ne 0) {
        throw "导入脚本执行失败"
    }
    
    Write-Host ""
    Write-Host "✅ 配置数据导入成功！" -ForegroundColor Green
    
} catch {
    Write-Host ""
    Write-Host "❌ 配置数据导入失败: $_" -ForegroundColor Red
    exit 1
}

# 验证导入结果
Write-Host ""
Write-Host "🔍 验证导入结果..." -ForegroundColor Yellow

$verifyScript = @"
from pymongo import MongoClient
client = MongoClient('mongodb://${MongoHost}:${MongoPort}/')
db = client['tradingagents']

collections = {
    'system_configs': '系统配置',
    'users': '用户',
    'llm_providers': 'LLM提供商',
    'model_catalog': '模型目录',
    'datasource_groupings': '数据源分组',
    'platform_configs': '平台配置',
    'market_categories': '市场分类'
}

print('\n📊 数据库集合统计:')
for col_name, col_desc in collections.items():
    count = db[col_name].count_documents({})
    print(f'   {col_desc} ({col_name}): {count} 条记录')

# 检查默认用户
admin_user = db.users.find_one({'username': 'admin'})
if admin_user:
    print('\n✅ 默认管理员账号已创建')
    print(f'   用户名: admin')
    print(f'   角色: {admin_user.get(\"role\", \"admin\")}')
else:
    print('\n⚠️  默认管理员账号未找到')

client.close()
"@

try {
    & python -c $verifyScript
    Write-Host ""
    Write-Host "✅ 数据库验证通过！" -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "⚠️  数据库验证失败: $_" -ForegroundColor Yellow
}

# 完成
Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  数据库初始化完成！                                        ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "🔐 默认登录信息:" -ForegroundColor Cyan
Write-Host "   用户名: admin" -ForegroundColor White
Write-Host "   密码: admin123" -ForegroundColor White
Write-Host ""
Write-Host "📝 下一步:" -ForegroundColor Cyan
Write-Host "   1. 启动后端服务" -ForegroundColor White
Write-Host "   2. 启动前端服务" -ForegroundColor White
Write-Host "   3. 访问 http://localhost 并登录" -ForegroundColor White
Write-Host "   4. 在系统管理中配置 API 密钥" -ForegroundColor White
Write-Host ""

