# Windows安装程序制作指南

## 📋 概述

本指南介绍如何为TradingAgents-CN Pro版创建专业的Windows安装程序（.exe）。

---

## 🎯 安装程序特性

### 用户体验

- ✅ **专业安装向导** - 现代化的安装界面
- ✅ **许可协议显示** - 显示软件许可协议
- ✅ **自定义安装路径** - 用户可选择安装位置
- ✅ **开始菜单快捷方式** - 自动创建程序组
- ✅ **桌面快捷方式** - 可选的桌面图标
- ✅ **完整卸载功能** - 干净卸载所有文件

### 技术特性

- ✅ **NSIS 3.x** - 使用业界标准的安装程序制作工具
- ✅ **LZMA压缩** - 高压缩比，减小安装包体积
- ✅ **注册表集成** - 正确注册到Windows系统
- ✅ **管理员权限** - 确保正确安装到Program Files

---

## 🛠️ 准备工作

### 1. 安装NSIS

**下载地址**: https://nsis.sourceforge.io/Download

**安装步骤**:

1. 下载NSIS 3.x最新版本
2. 运行安装程序
3. 安装到默认位置：`C:\Program Files\NSIS`
4. 完成安装

**验证安装**:

```powershell
# 检查NSIS是否安装
Test-Path "C:\Program Files\NSIS\makensis.exe"
# 应该返回: True
```

### 2. 准备Pro版文件

确保已经构建了Pro版：

```powershell
# 构建Pro版
.\scripts\deployment\build_pro_package.ps1
```

这将创建：
- `release/TradingAgentsCN-portable/` - 完整的Pro版文件
- `release/packages/*.zip` - ZIP打包文件

---

## 🚀 构建安装程序

### 方法1: 一键构建（推荐）

```powershell
# 完整构建（包括Pro版）
.\scripts\deployment\build_installer.ps1

# 只构建安装程序（使用现有Pro版）
.\scripts\deployment\build_installer.ps1 -SkipBuild

# 指定版本号
.\scripts\deployment\build_installer.ps1 -Version "v2.0.0"
```

### 方法2: 手动构建

```powershell
# 1. 构建Pro版
.\scripts\deployment\build_pro_package.ps1

# 2. 创建BAT文件
.\installer\create_bat_files.ps1

# 3. 编译NSIS脚本
& "C:\Program Files\NSIS\makensis.exe" /V4 .\installer\installer.nsi
```

---

## 📦 输出文件

### 安装程序位置

```
release/packages/TradingAgentsCN-Setup-v1.0.0-preview.exe
```

### 文件信息

- **文件名**: `TradingAgentsCN-Setup-v1.0.0-preview.exe`
- **大小**: 约 350 MB（压缩后）
- **类型**: Windows可执行文件（.exe）

---

## 🎨 安装程序界面

### 安装流程

1. **欢迎页面**
   - 显示产品名称和版本
   - 简要介绍

2. **许可协议**
   - 显示LICENSE文件内容
   - 用户必须接受才能继续

3. **选择安装目录**
   - 默认：`C:\Program Files\TradingAgentsCN`
   - 用户可自定义

4. **安装进度**
   - 显示文件复制进度
   - 创建快捷方式

5. **完成页面**
   - 可选：立即启动程序
   - 可选：查看README

### 创建的快捷方式

**开始菜单** (`开始 > TradingAgents-CN Pro`):
- 启动 TradingAgents-CN
- 停止 TradingAgents-CN
- 访问 Web 界面
- 卸载

**桌面**:
- TradingAgents-CN（启动快捷方式）

---

## 🔧 自定义安装程序

### 修改NSIS脚本

编辑 `installer/installer.nsi`：

```nsis
; 修改产品信息
!define PRODUCT_NAME "TradingAgents-CN Pro"
!define PRODUCT_VERSION "1.0.0-preview"
!define PRODUCT_PUBLISHER "Your Company"
!define PRODUCT_WEB_SITE "https://your-website.com"

; 修改默认安装路径
InstallDir "$PROGRAMFILES64\YourFolder"

; 修改欢迎页面文本
!define MUI_WELCOMEPAGE_TEXT "您的自定义文本..."
```

### 添加自定义图标

1. 准备图标文件（.ico格式）
2. 放置到 `installer/` 目录
3. 修改NSIS脚本：

```nsis
!define MUI_ICON "installer\your-icon.ico"
!define MUI_UNICON "installer\your-uninstall-icon.ico"
```

### 添加额外的安装选项

```nsis
Section "可选组件" SEC04
  ; 您的安装代码
SectionEnd
```

---

## ✅ 测试安装程序

### 测试清单

- [ ] 在干净的Windows系统上测试
- [ ] 验证安装到默认路径
- [ ] 验证安装到自定义路径
- [ ] 检查开始菜单快捷方式
- [ ] 检查桌面快捷方式
- [ ] 测试启动程序
- [ ] 测试卸载功能
- [ ] 验证完全卸载（无残留文件）

### 测试环境

**推荐测试环境**:
- Windows 10 64位
- Windows 11 64位
- Windows Server 2019/2022

**最低要求**:
- Windows 10 64位
- 4GB RAM
- 2GB 可用磁盘空间

---

## 📝 安装程序脚本说明

### installer.nsi 结构

```nsis
; 1. 头文件和定义
!include "MUI2.nsh"
!define PRODUCT_NAME "..."

; 2. 安装程序设置
Name "..."
OutFile "..."
InstallDir "..."

; 3. 界面设置
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE
...

; 4. 安装部分
Section "主程序" SEC01
  ; 复制文件
  File /r "..."
  
  ; 创建快捷方式
  CreateShortCut "..."
  
  ; 写入注册表
  WriteRegStr "..."
SectionEnd

; 5. 卸载部分
Section "Uninstall"
  ; 删除文件
  RMDir /r "$INSTDIR"
  
  ; 删除快捷方式
  Delete "..."
  
  ; 删除注册表
  DeleteRegKey "..."
SectionEnd
```

---

## 🔍 故障排除

### NSIS未找到

**错误**: `ERROR: NSIS not found!`

**解决方案**:
1. 确认NSIS已安装
2. 检查安装路径
3. 重新安装NSIS

### 编译失败

**错误**: `NSIS compilation failed`

**解决方案**:
1. 检查NSIS脚本语法
2. 确认所有引用的文件存在
3. 查看详细错误信息

### 安装程序无法运行

**错误**: 双击安装程序无反应

**解决方案**:
1. 右键 > 以管理员身份运行
2. 检查Windows Defender是否拦截
3. 检查文件是否损坏

---

## 📊 文件大小对比

| 格式 | 大小 | 说明 |
|------|------|------|
| 原始文件 | ~800 MB | 未压缩的Pro版文件 |
| ZIP压缩 | ~344 MB | 使用ZIP压缩 |
| NSIS安装程序 | ~350 MB | 使用LZMA压缩 |

---

## 🚀 发布安装程序

### 发布前检查

- [ ] 版本号正确
- [ ] 所有功能测试通过
- [ ] 许可证文件正确
- [ ] README文档完整
- [ ] 在多个系统上测试

### 发布渠道

1. **GitHub Releases**
   - 上传.exe文件
   - 编写Release Notes
   - 添加安装说明

2. **官方网站**
   - 提供下载链接
   - 显示系统要求
   - 提供安装教程

3. **其他渠道**
   - 云存储（百度网盘、阿里云盘等）
   - 企业内部分发

---

## 📚 相关文档

- [Pro版编译策略](PRO_COMPILATION_STRATEGY.md)
- [Pro版打包指南](PRO_PACKAGE_QUICK_REF.md)
- [安全改进总结](SECURITY_IMPROVEMENTS_SUMMARY.md)

---

## 💡 最佳实践

1. **版本管理**
   - 使用语义化版本号
   - 在VERSION文件中维护版本
   - 每次发布更新版本号

2. **测试**
   - 在虚拟机中测试
   - 测试升级安装
   - 测试卸载功能

3. **文档**
   - 提供详细的安装说明
   - 包含系统要求
   - 提供故障排除指南

4. **安全**
   - 对安装程序进行数字签名（可选）
   - 提供SHA256校验和
   - 通过官方渠道发布

---

## ✅ 完成清单

- [ ] NSIS已安装
- [ ] Pro版已构建
- [ ] BAT文件已创建
- [ ] NSIS脚本已编译
- [ ] 安装程序已测试
- [ ] 文档已准备
- [ ] 准备发布

