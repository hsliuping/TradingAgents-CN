# 付费用户认证模块设计

## 1. 系统架构概述

```
┌─────────────────────────────────────────────────────────────────┐
│                     用户本地电脑                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │           TradingAgents-CN 桌面应用                        │  │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │  │
│  │  │  免费功能    │    │  专业版功能  │    │  认证模块    │  │  │
│  │  │  (无限制)   │    │  (需认证)   │    │  (Key验证)  │  │  │
│  │  └─────────────┘    └─────────────┘    └──────┬──────┘  │  │
│  └───────────────────────────────────────────────┼──────────┘  │
└──────────────────────────────────────────────────┼──────────────┘
                                                   │
                                                   │ HTTPS 验证
                                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                     云端认证服务                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              License 认证网站                              │  │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │  │
│  │  │  用户注册    │    │  Key管理    │    │  管理后台    │  │  │
│  │  │  登录系统    │    │  生成/验证  │    │  权限管理    │  │  │
│  │  └─────────────┘    └─────────────┘    └─────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## 2. 用户认证流程

### 2.1 新用户流程

```
用户首次使用专业版功能
        ↓
弹出提示：需要认证Key
        ↓
引导用户访问认证网站
        ↓
用户注册账号（邮箱/手机）
        ↓
系统自动生成License Key
        ↓
7天免费体验期开始
        ↓
用户复制Key到本地应用
        ↓
本地应用验证Key有效性
        ↓
解锁专业版功能
```

### 2.2 付费开通流程

```
用户7天体验期到期
        ↓
专业版功能受限
        ↓
引导用户付费（微信公众号赞助）
        ↓
用户完成赞助并留言（邮箱/手机）
        ↓
管理员在后台确认
        ↓
更新用户会员状态
        ↓
用户本地应用自动同步状态
        ↓
恢复专业版功能
```

## 3. 数据模型设计

### 3.1 License Key 结构

```
Key格式: TACN-XXXX-XXXX-XXXX-XXXX
        │    │    │    │    │
        │    └────┴────┴────┴── 随机字符(16位)
        └── 产品前缀 (TradingAgents-CN)
```

### 3.2 云端数据库 - 用户表 `users`

```python
{
    "_id": ObjectId,
    "email": str,                  # 注册邮箱（唯一）
    "phone": str,                  # 手机号（可选）
    "password_hash": str,          # 密码哈希
    "nickname": str,               # 昵称
    
    # License 信息
    "license_key": str,            # 唯一License Key
    "license_status": str,         # trial / active / expired / revoked
    
    # 会员信息
    "membership": {
        "type": str,               # free / trial / monthly / yearly / lifetime
        "start_date": datetime,
        "expire_date": datetime,
        "trial_used": bool,        # 是否已使用试用
    },
    
    # 付费记录
    "payments": [
        {
            "payment_id": str,
            "amount": float,
            "channel": str,        # wechat_reward
            "payment_date": datetime,
            "months_added": int,
            "operator": str,       # 操作员
            "note": str
        }
    ],
    
    # 设备绑定（可选，防止Key滥用）
    "devices": [
        {
            "device_id": str,
            "device_name": str,
            "last_active": datetime
        }
    ],
    "max_devices": int,            # 最大设备数，默认3
    
    # 元数据
    "created_at": datetime,
    "updated_at": datetime,
    "last_login": datetime
}
```

### 3.3 本地应用配置 - `license.json`

```json
{
    "license_key": "TACN-XXXX-XXXX-XXXX-XXXX",
    "user_email": "user@example.com",
    "device_id": "auto-generated-uuid",
    "last_verified": "2025-12-04T10:00:00Z",
    "cached_status": {
        "is_valid": true,
        "membership_type": "yearly",
        "expire_date": "2026-12-04",
        "features": ["portfolio_analysis", "trade_review", "unlimited_analysis"]
    }
}
```

## 4. API 设计

### 4.1 认证网站 API

```
/api/auth
├── POST /register             # 用户注册
├── POST /login                # 用户登录
├── POST /logout               # 退出登录
├── POST /forgot-password      # 忘记密码
└── POST /reset-password       # 重置密码

/api/license
├── GET  /info                 # 获取License信息
├── POST /verify               # 验证License有效性（供本地应用调用）
├── POST /activate             # 激活License（绑定设备）
└── POST /regenerate           # 重新生成License Key

/api/user
├── GET  /profile              # 获取用户信息
├── PUT  /profile              # 更新用户信息
└── GET  /devices              # 获取绑定设备列表
```

### 4.2 管理后台 API

```
/api/admin
├── GET  /users                # 用户列表
├── GET  /users/:id            # 用户详情
├── PUT  /users/:id/membership # 更新会员状态
├── POST /users/:id/extend     # 延长会员期限
├── POST /users/:id/revoke     # 撤销License
└── GET  /statistics           # 统计数据
```

### 4.3 本地应用调用的验证接口

**POST /api/license/verify**

请求：
```json
{
    "license_key": "TACN-XXXX-XXXX-XXXX-XXXX",
    "device_id": "uuid",
    "device_name": "Windows PC",
    "app_version": "1.0.1"
}
```

响应（成功）：
```json
{
    "valid": true,
    "user": {
        "email": "user@example.com",
        "nickname": "用户昵称"
    },
    "membership": {
        "type": "yearly",
        "expire_date": "2026-12-04",
        "days_remaining": 365
    },
    "features": [
        "portfolio_analysis",
        "trade_review",
        "unlimited_analysis",
        "unlimited_depth",
        "unlimited_watchlist"
    ]
}
```

响应（失败）：
```json
{
    "valid": false,
    "error_code": "LICENSE_EXPIRED",
    "message": "您的会员已过期，请续费继续使用",
    "renew_url": "https://xxx.com/renew"
}
```

---

## 5. 本地应用认证模块设计

### 5.1 新增文件

```
app/
├── services/
│   └── license_service.py     # License验证服务
├── models/
│   └── license.py             # License数据模型
└── routers/
    └── license.py             # License API路由

config/
└── license.json               # 本地License配置（用户填入Key后生成）
```

### 5.2 License服务实现

```python
# app/services/license_service.py

class LicenseService:
    """License认证服务"""

    LICENSE_SERVER = "https://license.tradingagents-cn.com"
    VERIFY_INTERVAL = 24 * 3600  # 24小时验证一次

    async def get_license_status(self) -> LicenseStatus:
        """获取当前License状态"""

    async def verify_license(self, force: bool = False) -> VerifyResult:
        """验证License（支持离线缓存）"""

    async def activate_license(self, key: str) -> ActivateResult:
        """激活License Key"""

    async def check_feature(self, feature: str) -> bool:
        """检查是否有某功能权限"""

    def get_cached_status(self) -> Optional[LicenseStatus]:
        """获取缓存的License状态（离线使用）"""
```

### 5.3 功能权限映射

```python
# 功能权限定义
FEATURE_PERMISSIONS = {
    # 免费版功能
    "single_analysis": ["free", "trial", "monthly", "yearly", "lifetime"],
    "basic_learning": ["free", "trial", "monthly", "yearly", "lifetime"],
    "paper_trading": ["free", "trial", "monthly", "yearly", "lifetime"],

    # 专业版功能
    "batch_analysis": ["trial", "monthly", "yearly", "lifetime"],
    "scheduled_analysis": ["trial", "monthly", "yearly", "lifetime"],
    "portfolio_analysis": ["trial", "monthly", "yearly", "lifetime"],
    "trade_review": ["trial", "monthly", "yearly", "lifetime"],
    "pro_learning": ["trial", "monthly", "yearly", "lifetime"],
    "unlimited_depth": ["trial", "monthly", "yearly", "lifetime"],
    "report_export": ["trial", "monthly", "yearly", "lifetime"],
}

# 配额限制
QUOTA_LIMITS = {
    "free": {
        "daily_analysis": 3,
        "max_depth": 2,
        "watchlist_limit": 10,
        "report_retention_days": 7
    },
    "trial": {
        "daily_analysis": 999,
        "max_depth": 5,
        "watchlist_limit": 100,
        "report_retention_days": 30
    },
    "monthly": { ... },
    "yearly": { ... },
    "lifetime": { ... }
}
```

### 5.4 认证检查装饰器

```python
# app/utils/auth_decorators.py

def require_pro(feature: str = None):
    """专业版功能检查装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            license_service = get_license_service()

            if feature:
                has_permission = await license_service.check_feature(feature)
            else:
                has_permission = await license_service.is_pro_user()

            if not has_permission:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "code": "PRO_REQUIRED",
                        "message": "此功能需要专业版会员",
                        "upgrade_url": "https://xxx.com/upgrade"
                    }
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# 使用示例
@router.post("/portfolio/analysis")
@require_pro(feature="portfolio_analysis")
async def create_portfolio_analysis(...):
    ...
```

---

## 6. 前端认证界面设计

### 6.1 页面结构

```
frontend/src/views/License/
├── index.vue              # License管理页面
├── ActivateDialog.vue     # 激活Key对话框
└── UpgradePrompt.vue      # 升级提示组件
```

### 6.2 License状态显示

**位置**: 侧边栏底部或设置页面

```
┌─────────────────────────────┐
│  👤 当前账户                │
│  user@example.com          │
│                            │
│  📋 会员状态: 年度会员      │
│  📅 到期时间: 2026-12-04   │
│  ✅ 剩余 365 天            │
│                            │
│  [管理License] [续费]      │
└─────────────────────────────┘
```

### 6.3 激活弹窗

```
┌─────────────────────────────────────────┐
│           激活专业版                     │
├─────────────────────────────────────────┤
│                                         │
│  请输入您的License Key:                  │
│  ┌─────────────────────────────────┐   │
│  │ TACN-____-____-____-____        │   │
│  └─────────────────────────────────┘   │
│                                         │
│  还没有Key？                            │
│  👉 点击前往注册获取7天免费体验          │
│                                         │
│         [取消]  [激活]                  │
└─────────────────────────────────────────┘
```

### 6.4 功能受限提示

当用户访问专业版功能时：

```
┌─────────────────────────────────────────┐
│           🔒 专业版功能                  │
├─────────────────────────────────────────┤
│                                         │
│  "持仓分析" 是专业版独享功能             │
│                                         │
│  专业版包含：                           │
│  ✓ 持仓分析与建议                       │
│  ✓ 交易操作复盘                         │
│  ✓ 不限次数分析                         │
│  ✓ 完整课程体系                         │
│  ✓ 更多高级功能...                      │
│                                         │
│  [了解更多]  [立即开通]                 │
└─────────────────────────────────────────┘
```

---

## 7. 设备识别方案

### 7.1 设备指纹生成

**采集的硬件信息**：

```python
# app/utils/device_fingerprint.py

import platform
import uuid
import hashlib
import subprocess

def get_device_fingerprint() -> dict:
    """生成设备指纹"""

    # 1. MAC地址 (网卡物理地址)
    mac = ':'.join(['{:02x}'.format((uuid.getnode() >> i) & 0xff)
                   for i in range(0, 48, 8)][::-1])

    # 2. 计算机名
    hostname = platform.node()

    # 3. 操作系统信息
    os_info = f"{platform.system()}-{platform.release()}"

    # 4. CPU信息 (Windows)
    cpu_id = ""
    if platform.system() == "Windows":
        try:
            output = subprocess.check_output(
                'wmic cpu get ProcessorId',
                shell=True
            ).decode()
            cpu_id = output.split('\n')[1].strip()
        except:
            pass

    # 5. 硬盘序列号 (Windows)
    disk_id = ""
    if platform.system() == "Windows":
        try:
            output = subprocess.check_output(
                'wmic diskdrive get SerialNumber',
                shell=True
            ).decode()
            disk_id = output.split('\n')[1].strip()
        except:
            pass

    # 6. 主板序列号 (Windows)
    board_id = ""
    if platform.system() == "Windows":
        try:
            output = subprocess.check_output(
                'wmic baseboard get SerialNumber',
                shell=True
            ).decode()
            board_id = output.split('\n')[1].strip()
        except:
            pass

    return {
        "mac": mac,
        "hostname": hostname,
        "os": os_info,
        "cpu_id": cpu_id,
        "disk_id": disk_id,
        "board_id": board_id
    }


def generate_device_id(fingerprint: dict) -> str:
    """
    根据指纹生成设备唯一ID
    使用多个因素组合，单个因素变化不影响ID
    """
    # 主要因素 (权重高)
    primary = f"{fingerprint['cpu_id']}|{fingerprint['disk_id']}"

    # 次要因素 (权重低，用于辅助)
    secondary = f"{fingerprint['mac']}|{fingerprint['board_id']}"

    # 组合生成ID
    combined = f"{primary}:{secondary}"
    device_id = hashlib.sha256(combined.encode()).hexdigest()[:32]

    return device_id


def get_device_display_name(fingerprint: dict) -> str:
    """生成用户友好的设备名称"""
    return f"{fingerprint['hostname']} ({fingerprint['os']})"
```

### 7.2 设备指纹组成

| 因素 | 获取方式 | 稳定性 | 说明 |
|------|---------|--------|------|
| CPU ID | wmic cpu get ProcessorId | ⭐⭐⭐⭐⭐ | 几乎不变 |
| 硬盘序列号 | wmic diskdrive get SerialNumber | ⭐⭐⭐⭐ | 换硬盘才变 |
| 主板序列号 | wmic baseboard get SerialNumber | ⭐⭐⭐⭐⭐ | 几乎不变 |
| MAC地址 | uuid.getnode() | ⭐⭐⭐ | 换网卡/虚拟机会变 |
| 计算机名 | platform.node() | ⭐⭐ | 用户可能修改 |

**策略**: 主要依赖 CPU ID + 硬盘序列号，MAC地址作为辅助验证。

### 7.3 设备管理界面

**认证网站 - 我的设备页面**：

```
┌─────────────────────────────────────────────────────────────┐
│                    我的设备 (2/3)                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 💻 DESKTOP-ABC123 (Windows-10)                      │   │
│  │    设备ID: a1b2c3d4...                              │   │
│  │    激活时间: 2025-12-01 10:30                       │   │
│  │    最后活跃: 2025-12-04 15:22 ✅ 在线               │   │
│  │                                    [解绑此设备]     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 💻 LAPTOP-XYZ789 (Windows-11)                       │   │
│  │    设备ID: e5f6g7h8...                              │   │
│  │    激活时间: 2025-11-20 09:15                       │   │
│  │    最后活跃: 2025-11-25 18:40 ⚪ 5天前              │   │
│  │                                    [解绑此设备]     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  💡 您还可以绑定 1 台设备                                   │
│                                                             │
│  ────────────────────────────────────────────────────────  │
│  常见问题：                                                 │
│  • 重装系统后设备ID可能变化，届时会占用新的设备名额          │
│  • 如遇问题，请联系客服处理                                 │
└─────────────────────────────────────────────────────────────┘
```

### 7.4 设备绑定流程

```
用户首次激活License Key
        ↓
本地应用生成设备指纹
        ↓
发送到服务器: {license_key, device_id, device_name}
        ↓
服务器检查该Key已绑定设备数
        ↓
    ┌───────────────────────┬────────────────────────┐
    │  < 3台                │  = 3台                 │
    │                       │                        │
    ▼                       ▼                        │
绑定成功               检查是否是已绑定设备          │
返回激活成功                  │                      │
                    ┌────────┴────────┐              │
                    │ 是              │ 否           │
                    ▼                 ▼              │
               正常验证          返回错误:           │
                              "已达设备上限，        │
                               请先解绑其他设备"    │
```

### 7.5 特殊情况处理

| 情况 | 处理方式 |
|------|---------|
| 重装系统 | 设备ID可能变化，占用新名额；用户可解绑旧设备 |
| 更换硬盘 | 设备ID会变化，占用新名额 |
| 虚拟机 | 每个虚拟机视为独立设备 |
| 设备丢失 | 用户登录网站解绑该设备 |
| 超出限制 | 提示用户解绑或联系客服 |

---

## 8. 离线与安全设计

### 8.1 离线使用策略

```python
验证策略：
1. 首次激活：必须联网验证
2. 日常使用：每24小时联网验证一次
3. 离线宽限：最多允许7天离线使用
4. 超期处理：提示用户联网验证，但不立即禁用

缓存机制：
- 验证成功后缓存状态到本地 license.json
- 缓存有效期：7天
- 超过7天未联网：提示需要联网验证
```

### 8.2 防滥用措施

```
1. 设备绑定
   - 每个Key最多绑定3台设备
   - 超出时需解绑旧设备

2. 请求签名
   - 验证请求带时间戳和签名
   - 防止请求伪造

3. Key格式校验
   - 本地先校验Key格式
   - 减少无效请求

4. 异常监控
   - 同一Key短时间内多设备激活告警
   - 频繁验证失败告警
```

---

## 9. 管理后台功能

### 9.1 用户管理

- 用户列表（搜索、筛选、分页）
- 用户详情查看
- 会员状态修改
- 延长/缩短会员期限
- 撤销License

### 9.2 付费处理流程

```
管理员收到微信赞助通知
        ↓
登录管理后台
        ↓
搜索用户（通过赞助留言中的邮箱/手机）
        ↓
点击"开通会员"
        ↓
选择会员类型和时长
        ↓
填写付款信息（金额、备注）
        ↓
确认开通
        ↓
系统自动更新用户状态
        ↓
用户下次打开应用自动同步
```

### 9.3 统计报表

- 用户增长趋势
- 付费转化率
- 会员类型分布
- 到期提醒列表

---

## 10. 实现计划

### Phase 1: 认证网站搭建 (Week 1-2)
- [ ] 用户注册/登录系统
- [ ] License Key生成与管理
- [ ] 验证API实现
- [ ] 基础前端页面

### Phase 2: 管理后台 (Week 3)
- [ ] 管理员登录
- [ ] 用户管理功能
- [ ] 会员开通功能
- [ ] 基础统计

### Phase 3: 本地应用集成 (Week 4)
- [ ] License服务实现
- [ ] 认证检查装饰器
- [ ] 前端License管理页面
- [ ] 功能受限提示

### Phase 4: 测试与优化 (Week 5)
- [ ] 端到端测试
- [ ] 离线场景测试
- [ ] 安全测试
- [ ] 文档完善

---

## 11. 定价方案

| 会员类型 | 价格 | 时长 | 说明 |
|---------|------|------|------|
| 免费体验 | ¥0 | 7天 | 新用户自动获得 |
| 月度会员 | ¥29 | 30天 | 按月付费 |
| 年度会员 | ¥199 | 365天 | 推荐，省¥149 |
| 永久会员 | ¥399 | 永久 | 一次付费，永久使用 |

**早鸟优惠**: 首月5折

