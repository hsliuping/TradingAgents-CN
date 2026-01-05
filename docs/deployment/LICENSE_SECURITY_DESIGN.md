# 许可证验证安全设计

## 🔐 安全问题

### 问题描述

如果许可证验证服务器地址可以通过环境变量配置，用户可以轻易绕过验证：

```bash
# 用户修改 .env 文件
LICENSE_SERVICE_URL=http://localhost:9999
```

```python
# 用户搭建假验证服务器
@app.post("/api/v1/validate")
def fake_validate():
    return {"valid": true, "license": {...}}  # 永远返回通过
```

**结果**: 用户成功绕过所有许可证验证！❌

---

## ✅ 解决方案

### 1. 硬编码验证服务器地址

**在 Cython 编译的代码中写死域名**，防止用户修改：

#### `core/licensing/validator.py` (会被编译为 `.pyd`)

```python
class LicenseValidator:
    # 🔐 验证服务器地址（编译后无法修改）
    # ⚠️ 安全警告：此地址不能从环境变量读取
    VALIDATION_SERVER = "https://www.tradingagentscn.com/api/v1/license"
    
    # 🔐 密钥（编译后无法查看）
    SECRET_KEY = b"your-secret-key-change-this-in-production"
```

**编译后**:
- 文件变成 `validator.pyd` (Windows) 或 `validator.so` (Linux)
- 用户无法查看或修改 `VALIDATION_SERVER` 的值
- 用户无法查看 `SECRET_KEY`

---

#### `app/services/license_service.py`

```python
class LicenseService:
    # 🔐 验证服务器地址（硬编码，防止用户修改）
    BASE_URL = "https://www.tradingagentscn.com/api/v1"
    
    def __init__(self):
        self.base_url = self.BASE_URL  # 不从环境变量读取
```

---

### 2. 移除环境变量配置

**从 `app/core/config.py` 中移除**:

```python
# ❌ 删除这个配置（不安全）
# LICENSE_SERVICE_URL: str = Field(default="http://localhost:8081")

# ✅ 只保留超时和缓存配置
LICENSE_SERVICE_TIMEOUT: int = Field(default=10)
LICENSE_CACHE_TTL: int = Field(default=300)
```

**从 `.env` 文件中移除**:

```bash
# ❌ 删除这个配置
# LICENSE_SERVICE_URL=https://www.tradingagentscn.com/api/v1

# ✅ 只保留超时和缓存配置
LICENSE_SERVICE_TIMEOUT=10
LICENSE_CACHE_TTL=300
```

---

## 🛡️ 多层安全防护

### 1. 硬编码域名（第一层）

- ✅ 域名写死在 Cython 编译的代码中
- ✅ 用户无法修改
- ✅ 用户无法查看源码

### 2. 请求签名验证（第二层）

```python
def _sign_request(self, data: dict) -> str:
    """使用 HMAC-SHA256 签名请求"""
    message = json.dumps(data, sort_keys=True)
    signature = hmac.new(
        self.SECRET_KEY,
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return signature
```

- ✅ 每个请求都包含签名
- ✅ 签名密钥在编译后的代码中，用户无法查看
- ✅ 即使用户搭建假服务器，也无法生成正确的签名

### 3. 响应签名验证（第三层）

```python
def _verify_signature(self, data: dict, signature: str) -> bool:
    """验证服务器响应的签名"""
    expected = self._sign_request(data)
    return hmac.compare_digest(expected, signature)
```

- ✅ 验证服务器返回的签名
- ✅ 防止中间人攻击
- ✅ 防止伪造响应

### 4. 硬件绑定（第四层）

```python
def _get_machine_id(self) -> str:
    """获取机器唯一标识"""
    # 基于 CPU ID、主板序列号等硬件信息
    # 防止许可证在多台机器上使用
```

- ✅ 许可证绑定到特定机器
- ✅ 防止许可证共享
- ✅ 防止批量激活

### 5. 时间戳验证（第五层）

```python
request_data = {
    "license_key": license_key,
    "machine_id": machine_id,
    "timestamp": int(time.time()),  # 当前时间戳
}
```

- ✅ 防止重放攻击
- ✅ 服务器验证时间戳是否在合理范围内

---

## 🎯 验证流程

```
用户应用
    ↓
    1. 生成请求（包含许可证密钥、机器ID、时间戳）
    ↓
    2. 使用 SECRET_KEY 签名请求
    ↓
    3. 发送到 https://www.tradingagentscn.com/api/v1/license/validate
    ↓
验证服务器
    ↓
    4. 验证请求签名（使用相同的 SECRET_KEY）
    ↓
    5. 验证许可证密钥是否有效
    ↓
    6. 验证机器ID是否匹配
    ↓
    7. 验证时间戳是否在合理范围内
    ↓
    8. 生成响应并签名
    ↓
用户应用
    ↓
    9. 验证响应签名
    ↓
    10. 缓存验证结果（1小时）
```

---

## 📝 API 端点

### 许可证验证 API

**端点**: `POST https://www.tradingagentscn.com/api/v1/license/validate`

**请求**:
```json
{
  "license_key": "pro-xxxx-xxxx-xxxx",
  "machine_id": "abc123...",
  "timestamp": 1704355200,
  "signature": "sha256_hmac_signature"
}
```

**响应**:
```json
{
  "valid": true,
  "license": {
    "id": "uuid",
    "tier": "pro",
    "user_email": "user@example.com",
    "expires_at": "2025-12-31T23:59:59",
    "features": {...}
  },
  "signature": "response_signature"
}
```

### App Token 验证 API

**端点**: `POST https://www.tradingagentscn.com/api/v1/app/verify-token`

**请求**:
```json
{
  "token": "app-token-xxxx",
  "device_id": "device-123",
  "app_version": "1.0.0"
}
```

**响应**:
```json
{
  "email": "user@example.com",
  "plan": "pro",
  "features": ["advanced_analysis", "unlimited_tasks"],
  "trial_end_at": null,
  "pro_expire_at": "2025-12-31T23:59:59"
}
```

---

## ⚠️ 重要提醒

### 开发环境

开发时可以使用离线模式：

```python
validator = LicenseValidator(offline_mode=True)
```

### 生产环境

1. **确保 `core/licensing/` 已编译为 `.pyd` 文件**
2. **不要在源码中暴露 `SECRET_KEY`**
3. **定期更新 `SECRET_KEY`**
4. **监控异常的验证请求**

---

**最后更新**: 2026-01-05  
**安全级别**: 高  
**相关文件**:
- `core/licensing/validator.py`
- `app/services/license_service.py`
- `app/core/config.py`

