# 🚀 编译和打包使用指南

## 📋 快速开始

### 方式1：一键打包（推荐）

```powershell
# 完整打包流程（同步 + 编译 + 构建 + 打包）
.\scripts\deployment\build_pro_package.ps1
```

这个命令会自动执行：
1. ✅ 同步代码到 `release/TradingAgentsCN-portable`
2. ✅ **混合编译core目录**
   - Cython编译 `core/licensing/` → `.pyd`
   - 字节码编译其他目录 → `.pyc`
3. ✅ 构建前端（如果有）
4. ✅ 打包为ZIP文件

---

### 方式2：分步执行

#### 步骤1：同步代码

```powershell
# 同步Pro版代码（排除课程源码）
.\scripts\deployment\sync_to_portable_pro.ps1
```

#### 步骤2：混合编译

```powershell
# 编译core目录
.\scripts\deployment\compile_core_hybrid.ps1
```

**可选参数**：
```powershell
# 跳过Cython编译（如果没有编译器）
.\scripts\deployment\compile_core_hybrid.ps1 -SkipCython

# 保留源码（用于调试）
.\scripts\deployment\compile_core_hybrid.ps1 -KeepSource

# 指定输出目录
.\scripts\deployment\compile_core_hybrid.ps1 -OutputDir "D:\MyRelease\core"
```

#### 步骤3：测试编译结果

```powershell
# 测试编译产物
.\scripts\deployment\test_compilation.ps1
```

这个脚本会：
- ✅ 检查编译文件（.pyd/.pyc）
- ✅ 测试Python导入
- ✅ 测试许可证验证
- ✅ 显示测试结果

#### 步骤4：打包

```powershell
# 打包（跳过同步和编译）
.\scripts\deployment\build_pro_package.ps1 -SkipSync
```

---

## 🔧 环境准备

### Windows环境

#### 1. 安装Python

```powershell
# 检查Python版本
python --version
# 应该是 Python 3.10.x 或更高
```

#### 2. 安装Cython（用于编译）

```powershell
pip install Cython
```

#### 3. 安装Visual Studio Build Tools

**下载地址**: https://visualstudio.microsoft.com/downloads/

**安装组件**:
- ✅ C++ 生成工具
- ✅ Windows 10 SDK

**验证安装**:
```powershell
# 检查是否有cl.exe
where cl
```

#### 4. 安装前端构建工具（可选）

```powershell
# 安装Node.js和Yarn
# 下载: https://nodejs.org/
# 安装Yarn: npm install -g yarn
```

---

### Linux环境

```bash
# 安装依赖
sudo apt-get update
sudo apt-get install -y python3-dev build-essential

# 安装Cython
pip install Cython

# 安装Node.js和Yarn（可选）
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
npm install -g yarn
```

---

## 📊 编译结果

### 编译前

```
core/licensing/
├── __init__.py         (源码, 可查看)
├── manager.py          (源码, 176行)
├── validator.py        (源码, 260行)
├── features.py         (源码, 140行)
└── models.py           (源码, 156行)
```

### 编译后（Cython成功）

```
core/licensing/
├── __init__.py         (清空)
├── manager.pyd         (C扩展, 无法查看)
├── validator.pyd       (C扩展, 无法查看)
├── features.pyd        (C扩展, 无法查看)
└── models.py           (保留, 被其他模块导入)
```

### 编译后（仅字节码）

```
core/licensing/
├── __init__.py         (清空)
├── manager.pyc         (字节码)
├── validator.pyc       (字节码)
├── features.pyc        (字节码)
└── models.py           (保留)
```

---

## 🧪 测试

### 测试1：检查编译文件

```powershell
# 查看编译产物
Get-ChildItem "release\TradingAgentsCN-portable\core\licensing" -Recurse

# 应该看到 .pyd 或 .pyc 文件
```

### 测试2：测试导入

```powershell
cd release\TradingAgentsCN-portable

# 测试core模块
python -c "import core; print(core.__version__)"

# 测试许可证管理器
python -c "from core.licensing import LicenseManager; m = LicenseManager(); print(m.tier)"

# 测试验证器
python -c "from core.licensing.validator import LicenseValidator; v = LicenseValidator(offline_mode=True)"
```

### 测试3：运行完整测试

```powershell
# 运行测试脚本
.\scripts\deployment\test_compilation.ps1
```

---

## 🔐 安全验证

### 验证1：无法查看源码

尝试打开 `.pyd` 文件：
- ✅ 应该看到二进制内容，无法阅读
- ✅ 反编译工具无法还原源码

### 验证2：无法修改逻辑

尝试修改 `activate()` 方法：
- ✅ 无法找到源码
- ✅ 无法修改返回值

### 验证3：在线验证生效

```python
from core.licensing import LicenseManager

manager = LicenseManager()

# 尝试激活无效许可证
success, error = manager.activate("fake-1234-5678-9012")
print(f"Success: {success}, Error: {error}")
# 应该失败，因为需要在线验证
```

---

## ⚠️ 常见问题

### 问题1: Cython编译失败

**症状**:
```
error: Microsoft Visual C++ 14.0 or greater is required
```

**解决方案**:
1. 安装Visual Studio Build Tools
2. 或者跳过Cython编译：
   ```powershell
   .\scripts\deployment\compile_core_hybrid.ps1 -SkipCython
   ```

---

### 问题2: 导入错误

**症状**:
```
ImportError: cannot import name 'LicenseValidator'
```

**解决方案**:
1. 检查编译产物：
   ```powershell
   Get-ChildItem "release\TradingAgentsCN-portable\core\licensing" -Recurse
   ```
2. 确保有 `.pyd` 或 `.pyc` 文件
3. 重新运行编译：
   ```powershell
   .\scripts\deployment\compile_core_hybrid.ps1
   ```

---

### 问题3: 前端构建失败

**症状**:
```
yarn: command not found
```

**解决方案**:
1. 安装Node.js和Yarn
2. 或者跳过前端构建：
   ```powershell
   .\scripts\deployment\build_pro_package.ps1 -SkipFrontend
   ```

---

## 📞 获取帮助

### 文档

- [混合编译策略详解](./HYBRID_COMPILATION_STRATEGY.md)
- [安全改进总结](./SECURITY_IMPROVEMENTS_SUMMARY.md)
- [Pro版快速参考](./PRO_PACKAGE_QUICK_REF.md)

### 调试

```powershell
# 启用详细输出
$VerbosePreference = "Continue"
.\scripts\deployment\compile_core_hybrid.ps1

# 保留源码用于调试
.\scripts\deployment\compile_core_hybrid.ps1 -KeepSource
```

---

**最后更新**: 2026-01-04
**版本**: 2.0.0

