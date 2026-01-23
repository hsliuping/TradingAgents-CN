# 清理 Qdrant 数据目录
# 用途：删除旧的 Qdrant 集合，让系统重新创建（使用正确的向量维度）

param(
    [switch]$Force  # 强制删除，不提示确认
)

$ErrorActionPreference = "Stop"

# Qdrant 数据目录
$QdrantDataDir = "data\qdrant"

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "清理 Qdrant 数据目录" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# 检查目录是否存在
if (-not (Test-Path $QdrantDataDir)) {
    Write-Host "✅ Qdrant 数据目录不存在，无需清理" -ForegroundColor Green
    Write-Host "   目录: $QdrantDataDir" -ForegroundColor Gray
    exit 0
}

# 显示目录信息
$collections = Get-ChildItem -Path "$QdrantDataDir\collection" -Directory -ErrorAction SilentlyContinue
$collectionCount = if ($collections) { $collections.Count } else { 0 }

Write-Host "📁 Qdrant 数据目录: $QdrantDataDir" -ForegroundColor Yellow
Write-Host "📊 集合数量: $collectionCount" -ForegroundColor Yellow

if ($collections) {
    Write-Host ""
    Write-Host "集合列表:" -ForegroundColor Gray
    foreach ($col in $collections) {
        Write-Host "  - $($col.Name)" -ForegroundColor Gray
    }
}

Write-Host ""

# 确认删除
if (-not $Force) {
    Write-Host "⚠️  警告：此操作将删除所有 Qdrant 数据！" -ForegroundColor Red
    Write-Host "   删除后，系统将使用正确的向量维度重新创建集合。" -ForegroundColor Yellow
    Write-Host ""
    $confirm = Read-Host "是否继续？(y/N)"
    
    if ($confirm -ne "y" -and $confirm -ne "Y") {
        Write-Host ""
        Write-Host "❌ 操作已取消" -ForegroundColor Yellow
        exit 0
    }
}

Write-Host ""
Write-Host "🗑️  正在删除 Qdrant 数据目录..." -ForegroundColor Yellow

try {
    Remove-Item -Path $QdrantDataDir -Recurse -Force
    Write-Host "✅ Qdrant 数据目录已删除" -ForegroundColor Green
    Write-Host ""
    Write-Host "📝 下一步操作:" -ForegroundColor Cyan
    Write-Host "   1. 重启后端服务" -ForegroundColor Gray
    Write-Host "   2. 系统将自动创建新的 Qdrant 集合（使用正确的向量维度）" -ForegroundColor Gray
    Write-Host "   3. 检查日志确认集合创建成功" -ForegroundColor Gray
    Write-Host ""
} catch {
    Write-Host "❌ 删除失败: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 可能的原因:" -ForegroundColor Yellow
    Write-Host "   - 后端服务正在运行（请先停止服务）" -ForegroundColor Gray
    Write-Host "   - 文件被其他程序占用" -ForegroundColor Gray
    Write-Host ""
    Write-Host "🔧 解决方法:" -ForegroundColor Yellow
    Write-Host "   1. 停止后端服务" -ForegroundColor Gray
    Write-Host "   2. 重新运行此脚本" -ForegroundColor Gray
    Write-Host ""
    exit 1
}

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "✅ 清理完成" -ForegroundColor Green
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

