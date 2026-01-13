# Cython 编译指南

本文档说明如何使用 Cython 将 `core/licensing` 目录编译为 `.so` 共享库文件，以提供最强的代码保护。

## 📋 为什么需要 Cython 编译？

| 保护方式 | 保护级别 | 可逆性 | 适用范围 |
|---------|---------|--------|---------|
| `.py` 源码 | ⭐ | 完全可读 | 开源部分 |
| `.pyc` 字节码 | ⭐⭐⭐ | 可反编译 | 一般业务代码 |
| `.so` Cython | ⭐⭐⭐⭐⭐ | 几乎不可逆 | 核心许可证模块 |

**结论**: `core/licensing` 包含许可证验证逻辑，必须使用 Cython 编译为 `.so` 文件。

## 🛠️ 环境准备

### Ubuntu 22.04 服务器

```bash
# 1. 安装 Python 开发工具
sudo apt-get update
sudo apt-get install -y python3-dev build-essential

# 2. 安装 Cython
pip3 install cython

# 3. 验证安装
python3 -c "import Cython; print(Cython.__version__)"
gcc --version
```

### 其他 Linux 发行版

```bash
# CentOS/RHEL
sudo yum install -y python3-devel gcc gcc-c++
pip3 install cython

# Arch Linux
sudo pacman -S python gcc
pip3 install cython
```

## 🚀 编译流程

### 方式 1: 使用自动化脚本（推荐）

```bash
# 1. 进入项目目录
cd TradingAgents-CN-Pro

# 2. 运行完整编译脚本（包含 Cython 编译）
./docker/scripts/compile-code.sh

# 脚本会自动:
# - 编译 app/ 和 core/ 为 .pyc
# - 检测 Cython 是否安装
# - 如果安装了 Cython，自动编译 core/licensing 为 .so
# - 删除源码 .py 文件
```

### 方式 2: 单独编译 core/licensing

```bash
# 1. 先运行基础编译
./docker/scripts/compile-code.sh

# 2. 单独运行 Cython 编译
./docker/scripts/compile-licensing.sh
```

## 📁 编译产物

编译完成后，`docker/build/compiled/core/licensing/` 目录结构：

```
core/licensing/
├── __init__.py              # 保留（模块初始化）
├── validator.cpython-310-x86_64-linux-gnu.so   # 编译后的共享库
├── license_manager.cpython-310-x86_64-linux-gnu.so
└── ...其他 .so 文件
```

**注意**:
- `.so` 文件名包含 Python 版本和架构信息
- 不同平台的 `.so` 文件不兼容（需要分别编译）
- 源码 `.py` 文件已被删除（除了 `__init__.py`）

## 🔍 验证编译结果

```bash
# 1. 检查 .so 文件
find docker/build/compiled/core/licensing -name "*.so"

# 2. 检查是否还有源码文件（应该只有 __init__.py）
find docker/build/compiled/core/licensing -name "*.py"

# 3. 测试导入
cd docker/build/compiled
python3 -c "from core.licensing import validator; print('导入成功')"
```

## 🐛 常见问题

### 问题 1: 找不到 Python.h

**错误信息**:
```
fatal error: Python.h: No such file or directory
```

**解决方案**:
```bash
# Ubuntu/Debian
sudo apt-get install python3-dev

# CentOS/RHEL
sudo yum install python3-devel
```

### 问题 2: 找不到 gcc

**错误信息**:
```
error: command 'gcc' failed: No such file or directory
```

**解决方案**:
```bash
# Ubuntu/Debian
sudo apt-get install build-essential

# CentOS/RHEL
sudo yum groupinstall "Development Tools"
```

### 问题 3: Cython 版本不兼容

**错误信息**:
```
ImportError: cannot import name 'Cython' from 'Cython'
```

**解决方案**:
```bash
# 卸载旧版本
pip3 uninstall cython

# 安装最新版本
pip3 install cython --upgrade
```

### 问题 4: .so 文件无法导入

**错误信息**:
```
ImportError: cannot import name 'validator' from 'core.licensing'
```

**可能原因**:
1. Python 版本不匹配（编译时用的 3.10，运行时用的 3.9）
2. 架构不匹配（在 x86_64 编译，在 ARM64 运行）
3. `__init__.py` 被删除

**解决方案**:
```bash
# 检查 Python 版本
python3 --version

# 检查架构
uname -m

# 确保 __init__.py 存在
ls -la docker/build/compiled/core/licensing/__init__.py
```

## 📝 多架构编译

如果需要支持多个架构（如 AMD64 和 ARM64），需要在对应架构的机器上分别编译。

### AMD64 (x86_64)

```bash
# 在 AMD64 服务器上
./docker/scripts/compile-code.sh

# 产物: validator.cpython-310-x86_64-linux-gnu.so
```

### ARM64 (aarch64)

```bash
# 在 ARM64 服务器上（如树莓派、AWS Graviton）
./docker/scripts/compile-code.sh

# 产物: validator.cpython-310-aarch64-linux-gnu.so
```

## 🔐 安全建议

1. **不要提交编译产物到 Git**:
   - `.so` 文件已在 `.gitignore` 中
   - 只提交源码，在部署时编译

2. **保护编译环境**:
   - 在安全的服务器上编译
   - 编译后立即删除源码

3. **验证编译结果**:
   - 确保所有 `.py` 文件已删除
   - 测试 `.so` 文件可以正常导入

4. **备份源码**:
   - 在编译前备份 `core/licensing` 源码
   - 保存在安全的位置

## 📚 参考资料

- [Cython 官方文档](https://cython.readthedocs.io/)
- [Python Extension Modules](https://docs.python.org/3/extending/extending.html)
- [setuptools 文档](https://setuptools.pypa.io/)

---

**最后更新**: 2026-01-13  
**版本**: v1.0.0

