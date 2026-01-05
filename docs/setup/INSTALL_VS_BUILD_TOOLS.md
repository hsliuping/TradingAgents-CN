# Visual Studio Build Tools 安装指南

## 📋 概述

Visual Studio Build Tools 是 Microsoft 提供的 C/C++ 编译工具集，用于编译 Python 扩展模块（如 Cython 生成的 `.pyd` 文件）。

## 🎯 为什么需要它？

在 TradingAgents-CN Pro 版本中，我们使用 Cython 将关键的许可证验证模块编译为二进制 `.pyd` 文件，以提供更好的代码保护。这需要 C/C++ 编译器。

## 📥 下载和安装

### 方法 1：在线安装（推荐）

1. **下载安装程序**
   - 访问官方下载页面：https://visualstudio.microsoft.com/zh-hans/downloads/
   - 滚动到页面底部，找到 **"Visual Studio 2022 生成工具"** 或 **"Build Tools for Visual Studio 2022"**
   - 点击 **"免费下载"** 按钮

2. **运行安装程序**
   - 下载完成后，运行 `vs_BuildTools.exe`
   - 等待安装程序初始化

3. **选择工作负载**
   - 在 **"工作负载"** 选项卡中，勾选：
     - ✅ **"使用 C++ 的桌面开发"** (Desktop development with C++)
   
4. **选择单个组件（可选但推荐）**
   - 切换到 **"单个组件"** 选项卡
   - 确保以下组件已选中：
     - ✅ MSVC v143 - VS 2022 C++ x64/x86 生成工具（最新版本）
     - ✅ Windows 10 SDK 或 Windows 11 SDK（最新版本）
     - ✅ C++ CMake tools for Windows

5. **开始安装**
   - 点击右下角的 **"安装"** 按钮
   - 安装大小约 **6-8 GB**，需要一些时间
   - 等待安装完成

### 方法 2：离线安装

如果网络不稳定，可以使用离线安装包：

1. **下载离线安装包**
   ```powershell
   # 下载完整的离线安装包
   vs_BuildTools.exe --layout C:\VSBuildToolsOffline --add Microsoft.VisualStudio.Workload.VCTools --lang zh-CN
   ```

2. **从离线包安装**
   ```powershell
   C:\VSBuildToolsOffline\vs_BuildTools.exe --noweb
   ```

### 方法 3：命令行静默安装（高级用户）

```powershell
# 以管理员身份运行 PowerShell
vs_BuildTools.exe --quiet --wait --norestart --nocache `
  --add Microsoft.VisualStudio.Workload.VCTools `
  --add Microsoft.VisualStudio.Component.VC.Tools.x86.x64 `
  --add Microsoft.VisualStudio.Component.Windows10SDK.19041
```

## ✅ 验证安装

安装完成后，验证编译器是否可用：

```powershell
# 打开新的 PowerShell 窗口（重要！）
# 检查 cl.exe（C++ 编译器）是否在 PATH 中
where.exe cl

# 或者手动查找
Get-ChildItem "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC" -Recurse -Filter "cl.exe"
```

如果找到了 `cl.exe`，说明安装成功！

## 🔧 配置环境变量（如果需要）

通常安装程序会自动配置，但如果编译时仍然找不到编译器，可以手动设置：

1. **找到 vcvarsall.bat 路径**
   ```
   C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat
   ```

2. **在编译前运行**
   ```powershell
   # 设置 x64 环境
   & "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64
   ```

## 🐍 测试 Python 扩展编译

安装完成后，测试是否可以编译 Python 扩展：

```powershell
# 激活虚拟环境
.\venv\Scripts\Activate.ps1

# 安装 Cython
pip install Cython

# 测试编译
python -c "import setuptools; print('OK')"
```

## 📦 编译 TradingAgents-CN 许可证模块

现在可以编译许可证模块了：

```powershell
# 进入项目根目录
cd C:\TradingAgentsCN

# 运行编译脚本
.\scripts\deployment\compile_licensing.ps1
```

## 🔍 常见问题

### Q1: 安装后仍然提示找不到编译器？

**解决方案：**
1. 重启计算机（让环境变量生效）
2. 打开新的 PowerShell 窗口
3. 手动运行 vcvarsall.bat 设置环境

### Q2: 安装空间不足？

**解决方案：**
- 最小安装需要约 6 GB
- 可以只选择 "MSVC" 和 "Windows SDK" 组件
- 清理其他磁盘空间

### Q3: 下载速度慢？

**解决方案：**
- 使用离线安装包
- 或者使用国内镜像源（如果有）

### Q4: 我已经安装了 Visual Studio，还需要 Build Tools 吗？

**不需要！** 如果你已经安装了完整的 Visual Studio（Community/Professional/Enterprise），它已经包含了 Build Tools，可以直接编译。

## 📚 相关资源

- [Visual Studio Build Tools 官方文档](https://docs.microsoft.com/zh-cn/visualstudio/install/build-tools-container)
- [Python 扩展编译指南](https://wiki.python.org/moin/WindowsCompilers)
- [Cython 文档](https://cython.readthedocs.io/)

## 🎉 下一步

安装完成后，你可以：
1. ✅ 编译许可证模块为 `.pyd` 文件
2. ✅ 构建更安全的便携版包
3. ✅ 生成 Windows 安装程序

返回 [部署文档](../deployment/README.md) 继续下一步操作。

