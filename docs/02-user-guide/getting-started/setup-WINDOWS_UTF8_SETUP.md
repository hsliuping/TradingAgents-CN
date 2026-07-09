# 🔧 Windows UTF-8 系统编码设置指南

## 📋 概述

本指南介绍如何将Windows系统的默认编码从GBK（代码页936）永久修改为UTF-8（代码页65001），从根本上解决中文乱码问题。

---

## ✅ 推荐方法：使用Windows设置（GUI）

### 系统要求

- **Windows 10**: 版本 1903 (Build 18362) 或更高
- **Windows 11**: 所有版本
- **权限**: 不需要管理员权限

### 操作步骤

#### 方法1: 使用辅助脚本（推荐）

```powershell
# 运行辅助脚本，会自动打开设置页面
.\scripts\setup\enable_utf8_gui.ps1
```

脚本会：
1. ✅ 检查Windows版本
2. ✅ 显示详细步骤说明
3. ✅ 自动打开Windows设置页面

#### 方法2: 手动操作

1. **打开设置**
   - 按 `Windows + I` 键
   - 或点击"开始"菜单 → "设置"（齿轮图标）

2. **进入语言设置**
   - 点击 **"时间和语言"** (Time & Language)
   - 点击左侧的 **"语言"** (Language)

3. **打开管理语言设置**
   - 向下滚动到 **"相关设置"** (Related settings)
   - 点击 **"管理语言设置"** (Administrative language settings)

4. **更改系统区域设置**
   - 在弹出的窗口中，点击 **"更改系统区域设置..."** (Change system locale...)

5. **启用UTF-8**
   - ✅ 勾选 **"Beta: 使用 Unicode UTF-8 提供全球语言支持"**
   - (Beta: Use Unicode UTF-8 for worldwide language support)

6. **应用更改**
   - 点击 **"确定"** (OK)
   - 点击 **"立即重新启动"** (Restart now)

### 截图参考

```
┌─────────────────────────────────────────┐
│  区域设置                                │
├─────────────────────────────────────────┤
│  当前系统区域设置: 中文(简体，中国)      │
│                                         │
│  ☑ Beta: 使用 Unicode UTF-8 提供        │
│    全球语言支持                          │
│                                         │
│  [确定]  [取消]                         │
└─────────────────────────────────────────┘
```

---

## 🔐 高级方法：使用注册表（需要管理员权限）

### 系统要求

- **权限**: 需要管理员权限
- **适用**: 所有Windows 10/11版本

### 使用脚本自动设置

```powershell
# 以管理员身份运行PowerShell
# 右键点击PowerShell → "以管理员身份运行"

# 运行设置脚本
.\scripts\setup\set_windows_utf8.ps1
```

脚本会：
1. ✅ 检查Windows版本
2. ✅ 备份当前设置
3. ✅ 修改注册表
4. ✅ 验证设置
5. ✅ 提示重启

### 手动修改注册表

⚠️ **警告**: 修改注册表有风险，请先备份！

1. **打开注册表编辑器**
   ```powershell
   regedit
   ```

2. **导航到路径**
   ```
   HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\Nls\CodePage
   ```

3. **修改值**
   - 双击 `ACP`，将值改为 `65001`
   - 双击 `OEMCP`，将值改为 `65001`

4. **重启计算机**

---

## 🧪 验证UTF-8设置

### 重启后验证

```powershell
# 1. 检查控制台编码
[Console]::OutputEncoding
# 应该显示: Unicode (UTF-8)

# 2. 检查代码页
chcp
# 应该显示: Active code page: 65001

# 3. 测试中文显示
Write-Host "你好，世界！"
# 应该正常显示中文

# 4. 运行完整测试
.\scripts\deployment\test_utf8_encoding.ps1
```

### 预期输出

```
PS C:\> [Console]::OutputEncoding

BodyName          : utf-8
EncodingName      : Unicode (UTF-8)
HeaderName        : utf-8
WebName           : utf-8
WindowsCodePage   : 1200
IsBrowserDisplay  : True
IsBrowserSave     : True
IsMailNewsDisplay : True
IsMailNewsSave    : True
IsSingleByte      : False
EncoderFallback   : System.Text.EncoderReplacementFallback
DecoderFallback   : System.Text.DecoderReplacementFallback
IsReadOnly        : True
CodePage          : 65001
```

---

## 📊 对比：修改前后

### 修改前（GBK编码）

```powershell
PS C:\> [Console]::OutputEncoding
# CodePage: 936 (GBK)

PS C:\> Write-Host "你好，世界！"
# 输出: 浣犲ソ锛屼笘鐣岋紒 (乱码)
```

### 修改后（UTF-8编码）

```powershell
PS C:\> [Console]::OutputEncoding
# CodePage: 65001 (UTF-8)

PS C:\> Write-Host "你好，世界！"
# 输出: 你好，世界！ (正常)
```

---

## 🔄 恢复原始设置

### 如果需要恢复GBK编码

#### 使用备份文件

```powershell
# 1. 找到备份文件
# 位置: 桌面\UTF8_Backup_YYYYMMDD_HHMMSS\registry_backup.reg

# 2. 双击备份文件导入注册表

# 3. 重启计算机
```

#### 手动恢复

1. 打开 **设置** → **时间和语言** → **语言**
2. 点击 **"管理语言设置"**
3. 点击 **"更改系统区域设置..."**
4. ❌ 取消勾选 **"Beta: 使用 Unicode UTF-8..."**
5. 点击 **"确定"** 并重启

---

## ⚠️ 注意事项

### 兼容性问题

1. **旧版软件**: 某些老旧软件可能不兼容UTF-8
   - 解决: 使用兼容模式运行
   - 或临时切换回GBK

2. **批处理文件**: 某些.bat文件可能需要重新保存为UTF-8
   - 解决: 使用记事本打开，另存为UTF-8编码

3. **第三方工具**: 某些工具可能假设使用GBK编码
   - 解决: 检查工具的编码设置

### 最佳实践

1. ✅ **修改前备份**: 使用脚本自动备份，或手动导出注册表
2. ✅ **测试验证**: 修改后运行测试脚本验证
3. ✅ **逐步迁移**: 先在测试环境验证，再应用到生产环境
4. ✅ **文档记录**: 记录修改时间和原因

---

## 🎯 常见问题

### Q1: 修改后某些软件显示乱码怎么办？

**A**: 这是因为该软件不兼容UTF-8。解决方法：
1. 检查软件是否有编码设置选项
2. 使用兼容模式运行软件
3. 临时切换回GBK编码使用该软件

### Q2: 是否会影响系统性能？

**A**: 不会。UTF-8编码对系统性能的影响可以忽略不计。

### Q3: 是否需要重新安装软件？

**A**: 不需要。大多数现代软件都支持UTF-8编码。

### Q4: 修改后能否恢复？

**A**: 可以。使用备份文件或手动取消勾选即可恢复。

### Q5: Windows Server是否支持？

**A**: Windows Server 2019及更高版本支持此功能。

---

## 📚 相关资源

- [Microsoft官方文档](https://docs.microsoft.com/en-us/windows/apps/design/globalizing/use-utf8-code-page)
- [UTF-8编码指南](../deployment/UTF8_ENCODING_GUIDE.md)
- [PowerShell脚本UTF-8设置](../../scripts/deployment/utf8_encoding_template.ps1)

---

## 🚀 推荐工作流

### 新系统设置

```powershell
# 1. 设置系统UTF-8编码
.\scripts\setup\enable_utf8_gui.ps1

# 2. 重启计算机

# 3. 验证设置
.\scripts\deployment\test_utf8_encoding.ps1

# 4. 开始使用
.\scripts\deployment\build_pro_package.ps1
```

### 现有系统迁移

```powershell
# 1. 备份当前设置
.\scripts\setup\set_windows_utf8.ps1
# (会自动备份)

# 2. 重启计算机

# 3. 测试现有脚本
# 运行你的常用脚本，检查是否有问题

# 4. 如有问题，使用备份恢复
```

---

**更新日期**: 2026-01-05  
**版本**: 1.0.0  
**适用系统**: Windows 10 (1903+) / Windows 11

