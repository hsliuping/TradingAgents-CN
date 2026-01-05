# ============================================================================
# UTF-8 Encoding Template for PowerShell Scripts
# ============================================================================
# 此模板提供了在PowerShell脚本中设置UTF-8编码的标准方法
# 
# 使用方法：
# 1. 将下面的代码块复制到你的PowerShell脚本开头（param块之后）
# 2. 确保在任何文件操作之前设置编码
# ============================================================================

<#
.SYNOPSIS
    UTF-8编码设置模板

.DESCRIPTION
    此脚本展示了如何在PowerShell中正确设置UTF-8编码，
    解决Windows系统默认使用GBK编码导致的中文乱码问题。

.NOTES
    适用于：
    - Windows PowerShell 5.1
    - PowerShell Core 6.0+
    - PowerShell 7.0+
#>

# ============================================================================
# 标准UTF-8编码设置（复制此块到你的脚本中）
# ============================================================================

# 设置控制台和文件编码为UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
$OutputEncoding = [System.Text.Encoding]::UTF8

# ============================================================================
# 说明
# ============================================================================

<#
各设置的作用：

1. [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
   - 设置控制台输出编码为UTF-8
   - 影响 Write-Host, Write-Output 等命令的输出

2. [Console]::InputEncoding = [System.Text.Encoding]::UTF8
   - 设置控制台输入编码为UTF-8
   - 影响从控制台读取的输入

3. $PSDefaultParameterValues['*:Encoding'] = 'utf8'
   - 设置所有cmdlet的默认Encoding参数为utf8
   - 影响 Set-Content, Out-File, Export-Csv 等命令

4. $OutputEncoding = [System.Text.Encoding]::UTF8
   - 设置PowerShell输出流的编码
   - 影响管道和重定向操作
#>

# ============================================================================
# 常见问题和解决方案
# ============================================================================

<#
问题1: 中文文件名显示乱码
解决: 确保设置了 [Console]::OutputEncoding

问题2: 写入文件时中文乱码
解决: 使用 -Encoding UTF8 参数，或设置 $PSDefaultParameterValues

问题3: 读取文件时中文乱码
解决: 使用 Get-Content -Encoding UTF8

问题4: 日志文件中文乱码
解决: 确保所有文件操作都使用UTF-8编码
#>

# ============================================================================
# 示例：正确的文件操作
# ============================================================================

<#
# 写入文件（推荐方式）
$content = "这是中文内容"
Set-Content -Path "test.txt" -Value $content -Encoding UTF8

# 读取文件（推荐方式）
$content = Get-Content -Path "test.txt" -Encoding UTF8

# 追加文件（推荐方式）
Add-Content -Path "test.txt" -Value "追加内容" -Encoding UTF8

# 输出到文件（推荐方式）
"输出内容" | Out-File -FilePath "test.txt" -Encoding UTF8

# 导出CSV（推荐方式）
$data | Export-Csv -Path "data.csv" -Encoding UTF8 -NoTypeInformation
#>

# ============================================================================
# 示例：完整的脚本模板
# ============================================================================

<#
# ============================================================================
# 你的脚本标题
# ============================================================================

param(
    [string]$InputFile = "",
    [string]$OutputFile = ""
)

# 设置控制台和文件编码为UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
$OutputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = "Stop"

# 你的脚本逻辑
Write-Host "开始处理..." -ForegroundColor Green

# 读取文件
if ($InputFile -and (Test-Path $InputFile)) {
    $content = Get-Content -Path $InputFile -Encoding UTF8
    Write-Host "读取文件: $InputFile" -ForegroundColor Cyan
}

# 写入文件
if ($OutputFile) {
    $result = "处理结果：成功"
    Set-Content -Path $OutputFile -Value $result -Encoding UTF8
    Write-Host "写入文件: $OutputFile" -ForegroundColor Cyan
}

Write-Host "处理完成！" -ForegroundColor Green
#>

# ============================================================================
# 验证编码设置
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  UTF-8 Encoding Verification" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "当前编码设置:" -ForegroundColor Yellow
Write-Host "  Console Output Encoding: $([Console]::OutputEncoding.EncodingName)" -ForegroundColor Gray
Write-Host "  Console Input Encoding:  $([Console]::InputEncoding.EncodingName)" -ForegroundColor Gray
Write-Host "  Output Encoding:         $($OutputEncoding.EncodingName)" -ForegroundColor Gray
Write-Host ""

Write-Host "测试中文显示:" -ForegroundColor Yellow
Write-Host "  你好，世界！" -ForegroundColor Green
Write-Host "  Hello, 世界！" -ForegroundColor Green
Write-Host "  こんにちは、世界！" -ForegroundColor Green
Write-Host ""

Write-Host "✅ 如果上面的中文显示正常，说明UTF-8编码设置成功！" -ForegroundColor Green
Write-Host ""

