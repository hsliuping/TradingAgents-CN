# 🚀 TradingAgents-CN Pro版打包快速参考

## 一键打包

```powershell
# 完整打包（推荐）- 包含混合编译
.\scripts\deployment\build_pro_package.ps1

# 跳过同步（使用现有文件）
.\scripts\deployment\build_pro_package.ps1 -SkipSync

# 跳过前端构建
.\scripts\deployment\build_pro_package.ps1 -SkipFrontend
```

---

## 编译策略

| 目录 | 编译方式 | 保护级别 | 文件格式 |
|------|---------|---------|---------|
| `core/licensing/` | Cython | ⭐⭐⭐⭐⭐ | `.pyd`/`.so` |
| `core/agents/` | 字节码 | ⭐⭐⭐ | `.pyc` |
| `core/workflow/` | 字节码 | ⭐⭐⭐ | `.pyc` |
| `core/llm/` | 字节码 | ⭐⭐⭐ | `.pyc` |

---

## 许可证验证

### 激活许可证

```python
from core.licensing import LicenseManager

manager = LicenseManager()
success, error = manager.activate("pro-xxxx-xxxx-xxxx")

if success:
    print(f"✅ 激活成功！级别: {manager.tier}")
else:
    print(f"❌ 激活失败: {error}")
```

### 检查功能权限

```python
from core.licensing import require_feature

@require_feature("sector_analyst")
def analyze_sector(ticker: str):
    # 只有Pro用户可以调用
    pass
```

### 获取许可证信息

```python
manager = LicenseManager()

print(f"级别: {manager.tier}")
print(f"功能: {manager.features}")
print(f"过期时间: {manager.license.expires_at}")
```

---

## 安全特性

### ✅ 已实现

- [x] Cython编译许可证验证逻辑
- [x] 在线验证（防止伪造）
- [x] 签名验证（防止篡改）
- [x] 硬件绑定（防止共享）
- [x] 时间戳验证（防止重放攻击）
- [x] 字节码编译核心业务逻辑
- [x] 移除文档字符串（-OO优化）

### 🔐 保护内容

**无法查看**：
- 验证服务器地址
- 签名密钥
- 硬件绑定算法
- 验证逻辑

**无法修改**：
- `activate()` 方法
- `validate()` 方法
- 功能门控逻辑

---

## 测试命令

```powershell
# 1. 测试core模块
python -c "import core; print(core.__version__)"

# 2. 测试许可证管理器
python -c "from core.licensing import LicenseManager; m = LicenseManager(); print(m.tier)"

# 3. 测试验证器
python -c "from core.licensing.validator import LicenseValidator; v = LicenseValidator(offline_mode=True)"

# 4. 测试功能门控
python -c "from core.licensing import require_feature; print(require_feature)"
```

---

## 故障排查

### Cython编译失败

```powershell
# 安装Visual Studio Build Tools
# https://visualstudio.microsoft.com/downloads/

# 或跳过Cython编译
.\scripts\deployment\compile_core_hybrid.ps1 -SkipCython
```

### 导入错误

```powershell
# 检查编译产物
Get-ChildItem "release\TradingAgentsCN-portable\core\licensing" -Recurse

# 应该看到 .pyd 或 .pyc 文件
```

### 许可证验证失败

```python
# 使用离线模式测试
from core.licensing.validator import LicenseValidator

validator = LicenseValidator(offline_mode=True)
is_valid, license_obj, error = validator.validate_offline("pro-test-12345678-abcd1234")
print(f"Valid: {is_valid}, Error: {error}")
```

---

## 文件结构

### 编译前

```
core/
├── licensing/
│   ├── manager.py      (源码, 176行)
│   ├── validator.py    (源码, 260行)
│   └── features.py     (源码, 140行)
└── ...
```

### 编译后

```
core/
├── licensing/
│   ├── manager.pyd     (C扩展, 无法查看)
│   ├── validator.pyd   (C扩展, 无法查看)
│   └── features.pyd    (C扩展, 无法查看)
└── ...
```

---

## 环境变量

```bash
# .env
LICENSE_SERVICE_URL=https://license.tradingagents.cn/api/v1
LICENSE_SERVICE_TIMEOUT=10
LICENSE_CACHE_TTL=3600
```

---

## 相关文档

- [混合编译策略详解](./HYBRID_COMPILATION_STRATEGY.md)
- [许可证系统设计](./LICENSE_SYSTEM_DESIGN.md)
- [部署指南](./DEPLOYMENT_GUIDE.md)

---

**最后更新**: 2026-01-04

