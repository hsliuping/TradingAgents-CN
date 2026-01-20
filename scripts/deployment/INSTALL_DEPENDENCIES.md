# 安装依赖包说明

## ⚠️ 重要提示

**嵌入式 Python 必须使用 `python.exe -m pip`，不能直接使用 `pip.exe`！**

### ❌ 错误的方式
```powershell
.\vendors\python\Scripts\pip.exe install -r requirements.txt
```

### ✅ 正确的方式
```powershell
.\vendors\python\python.exe -m pip install -r requirements.txt
```

## 快速安装命令

在 `C:\TradingAgentsCN\release\TradingAgentsCN-portable` 目录下运行：

```powershell
# 使用阿里云镜像（推荐，速度快）
.\vendors\python\python.exe -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com --upgrade

# 或使用清华镜像
.\vendors\python\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn --upgrade

# 或使用默认源
.\vendors\python\python.exe -m pip install -r requirements.txt --upgrade
```

## 使用安装脚本

运行快速安装脚本（自动尝试多个镜像源）：

```powershell
cd C:\TradingAgentsCN
.\scripts\deployment\install_dependencies_fast.ps1
```

## 常见问题

### 1. socket.py 导入错误
**原因**：直接使用了 `pip.exe` 而不是 `python.exe -m pip`  
**解决**：使用 `python.exe -m pip` 命令

### 2. pip 未安装
**解决**：运行 `setup_embedded_python.ps1` 来安装 pip

### 3. 网络超时
**解决**：使用国内镜像源（阿里云、清华等）
