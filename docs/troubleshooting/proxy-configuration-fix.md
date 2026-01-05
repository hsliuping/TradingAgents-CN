# 代理配置问题修复说明

**版本**: v1.0.1  
**日期**: 2026-01-05  
**问题**: 用户未配置代理时，Tushare API 调用失败

---

## 📋 问题描述

### 错误日志

```json
{
  "time": "2026-01-05 23:17:40",
  "name": "app.services.config_service",
  "level": "ERROR",
  "trace_id": "57476bc3-6c1a-43e8-a339-115135c2b624",
  "message": "❌ [TEST] Tushare API call failed: HTTPConnectionPool(host='127.0.0.1', port=10809): Max retries exceeded with url: http://api.waditu.com/dataapi/trade_cal (Caused by ProxyError('Unable to connect to proxy', NewConnectionError('<urllib3.connection.HTTPConnection object at 0x000001597F754F10>: Failed to establish a new connection: [WinError 10061] 由于目标计算机积极拒绝，无法连接。')))"
}
```

### 问题根源

1. **系统环境变量中存在代理配置**（`HTTP_PROXY=http://127.0.0.1:10809`）
2. **用户未运行代理服务器**（端口 10809 无响应）
3. **Tushare 库自动读取系统代理**，导致连接失败
4. **Web 界面代理配置显示为灰色**，无法修改（因为来源是 `environment`）

---

## ✅ 修复方案

### 1. 添加代理启用开关

**后端** (`app/core/config.py`):
```python
PROXY_ENABLED: bool = Field(default=False)  # 代理总开关，默认关闭
```

**前端** (`frontend/src/views/Settings/ConfigManagement.vue`):
```vue
<el-form-item label="启用代理">
  <el-switch
    v-model="systemSettings.proxy_enabled"
    active-text="开启"
    inactive-text="关闭"
  />
</el-form-item>
```

### 2. 修复环境变量优先级问题

**允许 Web 界面编辑代理配置**（即使来自环境变量）:

`app/services/config_provider.py`:
```python
# 🔧 代理配置允许在 Web 界面编辑（即使来自环境变量）
proxy_keys = ("http_proxy", "https_proxy", "no_proxy", "proxy_enabled")

if k in proxy_keys:
    editable = True  # 代理配置始终可编辑
else:
    editable = not sensitive and source != "environment"
```

### 3. 国内数据源自动禁用代理

**Tushare API 测试时临时禁用代理**:

`app/services/config_service.py`:
```python
# 🔧 临时禁用代理（Tushare 是国内数据源，不需要代理）
original_http_proxy = os.environ.get('HTTP_PROXY')
original_https_proxy = os.environ.get('HTTPS_PROXY')

try:
    # 临时清除代理
    if 'HTTP_PROXY' in os.environ:
        del os.environ['HTTP_PROXY']
    if 'HTTPS_PROXY' in os.environ:
        del os.environ['HTTPS_PROXY']
    
    # 调用 Tushare API
    ts.set_token(api_key)
    pro = ts.pro_api()
    df = pro.trade_cal(exchange='SSE', start_date='20240101', end_date='20240101')
finally:
    # 恢复原始代理设置
    if original_http_proxy is not None:
        os.environ['HTTP_PROXY'] = original_http_proxy
    if original_https_proxy is not None:
        os.environ['HTTPS_PROXY'] = original_https_proxy
```

### 4. 代理启用逻辑优化

**只有在 `PROXY_ENABLED=True` 时才设置代理环境变量**:

`app/core/config.py`:
```python
if settings.PROXY_ENABLED:
    if settings.HTTP_PROXY:
        os.environ['HTTP_PROXY'] = settings.HTTP_PROXY
        os.environ['http_proxy'] = settings.HTTP_PROXY
    if settings.HTTPS_PROXY:
        os.environ['HTTPS_PROXY'] = settings.HTTPS_PROXY
        os.environ['https_proxy'] = settings.HTTPS_PROXY
else:
    # 代理未启用，清除环境变量中的代理设置
    for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
        if key in os.environ:
            del os.environ[key]

# NO_PROXY 始终设置（国内数据源不使用代理）
if settings.NO_PROXY:
    os.environ['NO_PROXY'] = settings.NO_PROXY
    os.environ['no_proxy'] = settings.NO_PROXY
```

---

## 🎯 使用说明

### 场景 1: 不需要代理（国内用户）

1. 访问 **设置 → 配置管理 → 系统设置 → 网络代理**
2. 确保 **启用代理** 开关为 **关闭**
3. 点击 **保存设置**
4. 重启后端服务

### 场景 2: 需要代理（访问 Yahoo Finance、Google News）

1. 访问 **设置 → 配置管理 → 系统设置 → 网络代理**
2. 开启 **启用代理** 开关
3. 填写 **HTTP 代理** 和 **HTTPS 代理**（例如：`127.0.0.1:7890`）
4. 点击 **测试代理连接** 验证
5. 点击 **保存设置**
6. 重启后端服务

---

## 📝 注意事项

1. **国内数据源自动绕过代理**：
   - Tushare (`api.tushare.pro`)
   - AKShare (东方财富、新浪、腾讯等)
   - BaoStock (`baostock.com`)

2. **代理配置修改后需要重启后端服务**才能生效

3. **默认代理状态为关闭**，避免用户未配置代理时出现连接错误

---

**相关文件**:
- `app/core/config.py` - 代理配置定义
- `app/services/config_provider.py` - 配置元数据管理
- `app/services/config_service.py` - Tushare API 测试
- `app/core/config_bridge.py` - 配置桥接逻辑
- `app/main.py` - 启动日志
- `frontend/src/views/Settings/ConfigManagement.vue` - 前端界面

**测试和验证**:
- `scripts/verify_proxy_fix.py` - 验证脚本
- `tests/test_proxy_configuration.py` - 单元测试

