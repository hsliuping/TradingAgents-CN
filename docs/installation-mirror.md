# 国内镜像加速安装指南

## 问题

安装依赖时速度很慢或经常卡死，特别是安装 torch、transformers 等大型包。

## 解决方案

使用国内 PyPI 镜像源加速安装。

---

## 🚀 快速使用（推荐）

### 方式 1: 使用锁定版本（最快，强烈推荐）

```bash
# 步骤 1: 安装所有依赖包（使用锁定版本，速度最快）
pip install -r requirements-lock.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 步骤 2: 安装本项目（可编辑模式，--no-deps 避免重新解析依赖）
pip install -e . --no-deps
```

**优势**：
- ✅ **安装速度极快**（无需依赖解析，直接下载指定版本）
- ✅ **环境完全可重现**（所有包版本锁定）
- ✅ **避免版本冲突**和 PyYAML 编译错误
- ✅ **节省时间**（从几分钟缩短到几十秒）

**说明**: `--no-deps` 参数告诉 pip 不要检查和安装依赖，因为我们已经通过 requirements-lock.txt 安装了所有依赖。

### 方式 2: 使用可编辑模式（开发时推荐）

```bash
# 使用清华镜像
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

# 或使用阿里云镜像
pip install -e . -i https://mirrors.aliyun.com/pypi/simple/

# 或使用中科大镜像
pip install -e . -i https://mirrors.ustc.edu.cn/pypi/web/simple
```

**注意**: 此方式需要 pip 解析依赖，速度较慢（可能需要几分钟），但适合开发时修改代码。

---

## 🔧 永久配置镜像（推荐）

### Windows

```powershell
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

### Linux / macOS

```bash
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

配置后，以后所有 `pip install` 命令都会自动使用镜像源。

---

## 📋 推荐镜像源

| 镜像源 | URL | 说明 |
|--------|-----|------|
| 清华大学 | `https://pypi.tuna.tsinghua.edu.cn/simple` | ⭐ 推荐，速度快，稳定 |
| 阿里云 | `https://mirrors.aliyun.com/pypi/simple/` | 稳定，速度快 |
| 中科大 | `https://mirrors.ustc.edu.cn/pypi/web/simple` | 教育网友好 |
| 豆瓣 | `https://pypi.douban.com/simple/` | 备选 |

---

## ✅ 完整安装示例

```bash
# 1. 配置镜像（一次性）
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 2. 升级 pip
pip install --upgrade pip

# 3. 安装项目
pip install -e .

# 完成！
```

---

## 🔄 取消镜像配置

如果需要恢复默认 PyPI 源：

```bash
pip config unset global.index-url
```

---

## 💡 其他加速方法

### 使用 uv（更快的包管理器）

```bash
# 安装 uv
pip install uv

# 使用 uv 安装（自动使用最快的源）
uv pip install -e .
```

---

## 🐛 常见问题

### 问题 1: PyYAML 编译错误（Windows）

**错误信息**:
```
AttributeError: cython_sources
Getting requirements to build wheel did not run successfully
```

**原因**: PyYAML 在 Windows 上需要编译，但缺少 C 编译器或 Cython 依赖。

**解决方案**:

**方法 1: 使用预编译的二进制包（推荐）**
```bash
# 先单独安装 PyYAML 的预编译版本
pip install --only-binary :all: pyyaml -i https://pypi.tuna.tsinghua.edu.cn/simple

# 然后安装项目
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**方法 2: 升级 pip 和 setuptools**
```bash
python -m pip install --upgrade pip setuptools wheel -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**方法 3: 安装 Microsoft C++ Build Tools**
- 下载: https://visualstudio.microsoft.com/visual-cpp-build-tools/
- 安装 "Desktop development with C++" 工作负载
- 重启后再安装

---

### 问题 2: 安装仍然很慢

如果使用镜像后仍然很慢：

1. 尝试更换其他镜像源
2. 检查网络连接
3. 使用 `uv` 包管理器
4. 在 GitHub Issues 中反馈

---

**推荐配置**: 清华镜像 + pip 永久配置，一劳永逸！🎉

