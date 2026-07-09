# 🔤 UTF-8 编码设置指南

## 📋 问题背景

Windows系统默认使用**GBK编码**（代码页936），这会导致PowerShell脚本在处理中文时出现乱码问题：

- ❌ 控制台输出中文乱码
- ❌ 文件读写中文乱码
- ❌ 日志文件中文乱码
- ❌ 错误信息显示异常

## ✅ 解决方案

在所有PowerShell脚本开头添加UTF-8编码设置：

```powershell
# 设置控制台和文件编码为UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
$OutputEncoding = [System.Text.Encoding]::UTF8
```

## 📁 已修改的脚本

以下脚本已经添加了UTF-8编码设置：

### 部署脚本（scripts/deployment/）

| 脚本 | 状态 | 说明 |
|------|------|------|
| `build_pro_package.ps1` | ✅ | Pro版一键打包 |
| `build_portable_package.ps1` | ✅ | 便携版一键打包 |
| `compile_core_hybrid.ps1` | ✅ | 混合编译脚本 |
| `test_compilation.ps1` | ✅ | 编译测试脚本 |
| `sync_to_portable.ps1` | ✅ | 代码同步脚本 |
| `sync_to_portable_pro.ps1` | ✅ | Pro版代码同步 |
| `deploy_stop_scripts.ps1` | ✅ | 部署停止脚本 |
| `update_scripts_for_embedded_python.ps1` | ✅ | 更新Python路径 |

## 🔧 编码设置详解

### 1. Console.OutputEncoding

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

**作用**: 设置控制台输出编码
**影响**: `Write-Host`, `Write-Output` 等命令的输出

### 2. Console.InputEncoding

```powershell
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
```

**作用**: 设置控制台输入编码
**影响**: 从控制台读取的输入

### 3. PSDefaultParameterValues

```powershell
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
```

**作用**: 设置所有cmdlet的默认Encoding参数
**影响**: `Set-Content`, `Out-File`, `Export-Csv` 等命令

### 4. OutputEncoding

```powershell
$OutputEncoding = [System.Text.Encoding]::UTF8
```

**作用**: 设置PowerShell输出流的编码
**影响**: 管道和重定向操作

## 📝 使用示例

### 完整脚本模板

```powershell
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

# 文件操作会自动使用UTF-8编码
Set-Content -Path "output.txt" -Value "中文内容"
```

### 文件操作最佳实践

```powershell
# ✅ 推荐：显式指定UTF-8编码
Set-Content -Path "file.txt" -Value "内容" -Encoding UTF8

# ✅ 推荐：使用默认参数（已设置为UTF-8）
Set-Content -Path "file.txt" -Value "内容"

# ❌ 不推荐：不设置编码（可能使用系统默认编码）
# 在没有设置 $PSDefaultParameterValues 的情况下
```

## 🧪 验证编码设置

运行测试脚本验证UTF-8编码是否正确设置：

```powershell
# 运行UTF-8编码验证脚本
.\scripts\deployment\utf8_encoding_template.ps1
```

**预期输出**:
```
============================================================================
  UTF-8 Encoding Verification
============================================================================

当前编码设置:
  Console Output Encoding: Unicode (UTF-8)
  Console Input Encoding:  Unicode (UTF-8)
  Output Encoding:         Unicode (UTF-8)

测试中文显示:
  你好，世界！
  Hello, 世界！
  こんにちは、世界！

✅ 如果上面的中文显示正常，说明UTF-8编码设置成功！
```

## 🔍 常见问题

### Q1: 为什么需要设置4个编码变量？

**A**: 每个变量控制不同的编码场景：
- `Console.OutputEncoding` → 控制台输出
- `Console.InputEncoding` → 控制台输入
- `PSDefaultParameterValues` → 文件操作默认编码
- `OutputEncoding` → 管道和重定向

### Q2: 设置后仍然乱码怎么办？

**A**: 检查以下几点：
1. 确保编码设置在所有文件操作**之前**
2. 确保源文件本身是UTF-8编码
3. 确保终端/控制台支持UTF-8显示
4. 尝试重启PowerShell会话

### Q3: 是否需要在每个脚本中都设置？

**A**: 是的，建议在每个脚本中都设置，因为：
- PowerShell会话的编码设置不会自动继承
- 不同脚本可能在不同环境中运行
- 显式设置可以避免环境差异导致的问题

### Q4: 对性能有影响吗？

**A**: 几乎没有影响：
- 编码设置只在脚本启动时执行一次
- 对脚本运行性能的影响可以忽略不计

## 📚 参考资源

- [PowerShell编码文档](https://docs.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_character_encoding)
- [UTF-8编码模板](../../scripts/deployment/utf8_encoding_template.ps1)

## 🎯 下一步

1. **验证现有脚本**: 运行脚本确认中文显示正常
2. **新建脚本**: 使用模板创建新的PowerShell脚本
3. **报告问题**: 如果发现编码问题，请及时反馈

---

**更新日期**: 2026-01-05  
**版本**: 1.0.0

