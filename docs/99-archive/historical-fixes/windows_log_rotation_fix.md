# Windows 日志轮转问题修复

## 问题描述

在 Windows 环境下运行应用时，日志轮转（log rotation）会出现 `PermissionError: [WinError 32]` 错误：

```
--- Logging error ---
Traceback (most recent call last):
  File "C:\Users\hsliu\AppData\Local\Programs\Python\Python310\lib\logging\handlers.py", line 74, in emit
    self.doRollover()
  File "C:\Users\hsliu\AppData\Local\Programs\Python\Python310\lib\logging\handlers.py", line 179, in doRollover
    self.rotate(self.baseFilename, dfn)
  File "C:\Users\hsliu\AppData\Local\Programs\Python\Python310\lib\logging\handlers.py", line 115, in rotate
    os.rename(source, dest)
PermissionError: [WinError 32] 另一个程序正在使用此文件，进程无法访问。: 
'C:\\TradingAgentsCN\\logs\\tradingagents.log' -> 'C:\\TradingAgentsCN\\logs\\tradingagents.log.1'
```

## 问题原因

Windows 系统的文件锁定机制与 Unix/Linux 不同：
- 当一个进程打开文件进行读取或写入时，Windows 会锁定该文件
- 标准的 `logging.handlers.RotatingFileHandler` 在轮转日志时需要重命名文件
- 如果有其他进程（如日志查看器、文本编辑器）正在读取日志文件，重命名操作会失败

## 解决方案

使用 `concurrent-log-handler` 包提供的 `ConcurrentRotatingFileHandler`，它专门解决了 Windows 上的文件锁定问题。

### 1. 依赖包

`concurrent-log-handler` 已经在 `requirements.txt` 中（第58行）：

```txt
concurrent-log-handler>=0.9.24
```

### 2. 修复的文件

#### 2.1 `app/core/logging_config.py`

**修复位置 1：** 第10-20行 - 添加 Windows 检测和导入逻辑

```python
# 🔥 在 Windows 上使用 concurrent-log-handler 避免文件占用问题
_IS_WINDOWS = platform.system() == "Windows"
if _IS_WINDOWS:
    try:
        from concurrent_log_handler import ConcurrentRotatingFileHandler
        _USE_CONCURRENT_HANDLER = True
    except ImportError:
        _USE_CONCURRENT_HANDLER = False
        logging.warning("concurrent-log-handler 未安装，在 Windows 上可能遇到日志轮转问题")
else:
    _USE_CONCURRENT_HANDLER = False
```

**修复位置 2：** 第237行 - 修复 error_file handler

```python
# 修改前
handlers_config["error_file"] = {
    "class": "logging.handlers.RotatingFileHandler",  # ❌ 硬编码
    ...
}

# 修改后
handlers_config["error_file"] = {
    "class": handler_class,  # ✅ 使用 Windows 兼容的处理器类
    ...
}
```

#### 2.2 `tradingagents/utils/logging_manager.py`

**修复位置 1：** 第18-28行 - 添加 Windows 检测和导入逻辑

```python
# 🔥 在 Windows 上使用 concurrent-log-handler 避免文件占用问题
_IS_WINDOWS = platform.system() == "Windows"
if _IS_WINDOWS:
    try:
        from concurrent_log_handler import ConcurrentRotatingFileHandler
        _USE_CONCURRENT_HANDLER = True
    except ImportError:
        _USE_CONCURRENT_HANDLER = False
        logging.warning("concurrent-log-handler 未安装，在 Windows 上可能遇到日志轮转问题")
else:
    _USE_CONCURRENT_HANDLER = False
```

**修复位置 2：** 第255-269行 - 修复 `_add_file_handler` 方法

```python
# 🔥 在 Windows 上使用 ConcurrentRotatingFileHandler 避免文件占用问题
if _USE_CONCURRENT_HANDLER:
    file_handler = ConcurrentRotatingFileHandler(
        log_file,
        maxBytes=max_size,
        backupCount=backup_count,
        encoding='utf-8'
    )
else:
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_size,
        backupCount=backup_count,
        encoding='utf-8'
    )
```

**修复位置 3：** 第292-305行 - 修复 `_add_error_handler` 方法

```python
# 🔥 在 Windows 上使用 ConcurrentRotatingFileHandler 避免文件占用问题
if _USE_CONCURRENT_HANDLER:
    error_handler = ConcurrentRotatingFileHandler(
        error_log_file,
        maxBytes=max_size,
        backupCount=backup_count,
        encoding='utf-8'
    )
else:
    error_handler = logging.handlers.RotatingFileHandler(
        error_log_file,
        maxBytes=max_size,
        backupCount=backup_count,
        encoding='utf-8'
    )
```

## 修复效果

- ✅ Windows 环境下日志轮转不再出现 `PermissionError`
- ✅ 支持多进程同时写入日志文件
- ✅ 兼容 Unix/Linux 系统（自动回退到标准 `RotatingFileHandler`）
- ✅ 不影响现有日志功能和配置

## 技术细节

### ConcurrentRotatingFileHandler 的优势

1. **跨平台兼容**：在 Windows 和 Unix/Linux 上都能正常工作
2. **并发安全**：支持多进程同时写入同一个日志文件
3. **文件锁定处理**：使用 `portalocker` 库处理文件锁定
4. **无缝替换**：API 与标准 `RotatingFileHandler` 完全兼容

### 自动检测逻辑

```python
_IS_WINDOWS = platform.system() == "Windows"
if _IS_WINDOWS:
    try:
        from concurrent_log_handler import ConcurrentRotatingFileHandler
        _USE_CONCURRENT_HANDLER = True
    except ImportError:
        _USE_CONCURRENT_HANDLER = False
else:
    _USE_CONCURRENT_HANDLER = False
```

- 自动检测操作系统
- 尝试导入 `ConcurrentRotatingFileHandler`
- 如果导入失败，回退到标准处理器并发出警告

## 相关资源

- [concurrent-log-handler GitHub](https://github.com/Preston-Landers/concurrent-log-handler)
- [Python logging.handlers 文档](https://docs.python.org/3/library/logging.handlers.html)
- [Windows 文件锁定机制](https://docs.microsoft.com/en-us/windows/win32/fileio/file-access-rights-constants)

