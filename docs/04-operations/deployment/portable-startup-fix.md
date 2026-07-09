# 便携版启动问题修复说明

## 📋 问题总结

### 问题 1: `python -m app` 无法工作

**现象**:
```powershell
python -m app
# 错误: No module named app
```

**原因**:
- 便携版使用虚拟环境（`venv`）
- 虚拟环境的 `sys.path` 不包含项目根目录
- `python -m app` 需要 Python 能够先找到 `app` 包

**解决方案**:
1. 在 `app/__main__.py` 中添加代码，将项目根目录加入 `sys.path`
2. 启动脚本改为直接运行 `python app\__main__.py`，而不是 `python -m app`

---

### 问题 2: `start_services_clean.ps1` 卡住

**现象**:
- 启动脚本在 MongoDB/Redis 启动步骤卡住
- 脚本无法继续执行

**原因**:
- `Start-Proc` 函数使用 `ReadToEnd()` 读取进程输出
- MongoDB 和 Redis 是长期运行的服务，不会关闭输出流
- `ReadToEnd()` 会一直阻塞等待

**解决方案**:
- 使用 `Peek()` 和 `ReadLine()` 只读取已经可用的输出
- 避免使用 `ReadToEnd()` 阻塞调用

---

## 🔧 修改的文件

### 1. `app/__main__.py`

**修改内容**:
```python
import os
import sys

# 🔧 确保项目根目录在 sys.path 中，以便能够导入 app 模块
# 这对于便携版特别重要，因为虚拟环境可能不包含项目根目录
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import uvicorn

def main():
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)

if __name__ == "__main__":
    main()
```

---

### 2. `scripts/installer/start_services_clean.ps1`

**修改位置**: `Start-Proc` 函数（第 98-122 行）

**修改前**:
```powershell
if ($process.HasExited) {
    Write-Host "Failed to start $Name (process exited)"
    $stdout = $process.StandardOutput.ReadToEnd()  # ❌ 会阻塞
    $stderr = $process.StandardError.ReadToEnd()   # ❌ 会阻塞
    if ($stdout) { Write-Host "  STDOUT: $stdout" }
    if ($stderr) { Write-Host "  STDERR: $stderr" }
    return $null
}
```

**修改后**:
```powershell
if ($process.HasExited) {
    Write-Host "Failed to start $Name (process exited)"
    # 🔧 不使用 ReadToEnd()，因为它会阻塞
    # 只读取已经可用的输出
    $stdout = ""
    $stderr = ""
    try {
        while ($process.StandardOutput.Peek() -gt -1) {
            $stdout += $process.StandardOutput.ReadLine() + "`n"
        }
        while ($process.StandardError.Peek() -gt -1) {
            $stderr += $process.StandardError.ReadLine() + "`n"
        }
    } catch {
        # Ignore errors when reading output
    }
    if ($stdout) { Write-Host "  STDOUT: $stdout" }
    if ($stderr) { Write-Host "  STDERR: $stderr" }
    return $null
}
```

---

### 3. `scripts/installer/start_all.ps1`

**修改 1**: 后端启动方式（第 223-328 行）

**关键改动**:
```powershell
# 修改前
$psi.Arguments = "-m app"

# 修改后
$appMain = Join-Path $root "app\__main__.py"
$psi.Arguments = "`"$appMain`""
```

**修改 2**: 简化进程输出处理

- ❌ 删除了复杂的异步读取代码（`BeginOutputReadLine()` 等）
- ✅ 让后端进程自己通过 uvicorn 的日志配置输出到文件

---

## ✅ 验证步骤

### 1. 测试后端启动

```powershell
cd C:\TradingAgentsCN\release\TradingAgentsCN-portable

# 激活虚拟环境
.\venv\Scripts\activate

# 直接运行 app\__main__.py
python app\__main__.py
```

**预期结果**:
- ✅ 后端成功启动
- ✅ 日志显示 MongoDB 和 Redis 连接成功
- ✅ Uvicorn 服务器启动

### 2. 测试 API

```powershell
# 测试健康检查
Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing

# 测试 API 文档
Invoke-WebRequest -Uri "http://localhost:8000/docs" -UseBasicParsing
```

**预期结果**:
- ✅ 状态码 200
- ✅ API 正常响应

### 3. 测试完整启动流程

```powershell
.\start_all.ps1
```

**预期结果**:
- ✅ MongoDB 启动成功
- ✅ Redis 启动成功
- ✅ Backend 启动成功
- ✅ Nginx 启动成功
- ✅ 所有服务正常运行

---

## 📝 注意事项

1. **虚拟环境激活问题**:
   - 在便携版目录运行 `.\venv\scripts\activate` 可能会激活系统的 Python 环境
   - 建议直接使用 `.\venv\Scripts\python.exe` 运行脚本

2. **启动方式**:
   - ✅ 推荐: `.\venv\Scripts\python.exe app\__main__.py`
   - ❌ 不推荐: `python -m app`（需要项目根目录在 `sys.path` 中）

3. **日志位置**:
   - 后端日志: `logs/app.log`
   - 启动日志: `logs/backend_startup.log`
   - 错误日志: `logs/backend_error.log`

---

**最后更新**: 2026-01-05  
**修复版本**: v1.0.0

