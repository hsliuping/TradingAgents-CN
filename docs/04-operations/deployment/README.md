# 📦 TradingAgents-CN 部署文档

## 🚀 快速开始

### Pro版打包（推荐）

```powershell
# 一键打包（包含混合编译）
.\scripts\deployment\build_pro_package.ps1
```

这个命令会：
1. ✅ 同步代码（排除课程源码）
2. ✅ **混合编译core目录**（Cython + 字节码）
3. ✅ 构建前端
4. ✅ 打包为ZIP

---

## 📚 文档索引

### 核心文档

| 文档 | 说明 | 适用人群 |
|------|------|---------|
| [安全改进总结](./SECURITY_IMPROVEMENTS_SUMMARY.md) | 本次安全改进的完整说明 | 所有人 |
| [混合编译策略](./HYBRID_COMPILATION_STRATEGY.md) | 详细的编译策略和技术细节 | 开发者 |
| [Pro版快速参考](./PRO_PACKAGE_QUICK_REF.md) | 常用命令和快速参考 | 运维人员 |

### 其他文档

| 文档 | 说明 |
|------|------|
| [许可证系统设计](./LICENSE_SYSTEM_DESIGN.md) | 许可证系统架构 |
| [部署指南](./DEPLOYMENT_GUIDE.md) | 完整部署流程 |
| [快速参考](./QUICK_REFERENCE.md) | 绿色版部署参考 |
| [UTF-8编码指南](./UTF8_ENCODING_GUIDE.md) | 解决中文乱码问题 |

---

## 🔐 安全特性

### 混合编译策略

```
core/
├── licensing/          # 🔐 Cython编译 → C扩展 (.pyd/.so)
│   ├── validator.py    # 在线验证器（最关键）
│   ├── manager.py      # 许可证管理器
│   └── features.py     # 功能门控
├── agents/             # 📦 字节码编译 → .pyc
├── workflow/           # 📦 字节码编译 → .pyc
└── llm/                # 📦 字节码编译 → .pyc
```

### 保护级别

| 编译方式 | 保护级别 | 反编译难度 | 性能提升 |
|---------|---------|-----------|---------|
| Cython | ⭐⭐⭐⭐⭐ | 极高（需要逆向C代码） | 10-30% |
| 字节码 | ⭐⭐⭐ | 中等（需要工具） | 5-10% |

---

## 🛡️ 许可证验证

### 安全特性

- ✅ **在线验证**: 防止伪造许可证
- ✅ **签名验证**: 防止请求/响应被篡改
- ✅ **硬件绑定**: 防止许可证共享
- ✅ **时间戳验证**: 防止重放攻击
- ✅ **Cython编译**: 验证逻辑无法被查看或修改

### 无法绕过的保护

用户**无法**：
- ❌ 查看验证服务器地址
- ❌ 查看签名密钥
- ❌ 修改 `activate()` 方法
- ❌ 绕过在线验证
- ❌ 伪造许可证

---

## 📊 编译对比

### 编译前（不安全）

```python
# core/licensing/manager.py (源码可见)
def activate(self, license_key: str) -> bool:
    # 用户可以修改这里返回True
    parts = license_key.split('-')
    tier = LicenseTier(parts[0])
    self._license = License.create_for_tier(tier)
    return True  # 直接激活！
```

**问题**:
- ❌ 用户输入 `pro-1234-5678-9012` 就能激活
- ❌ 用户可以修改代码绕过验证

### 编译后（安全）

```
core/licensing/
├── manager.pyd         # C扩展，无法查看
├── validator.pyd       # C扩展，无法查看
└── features.pyd        # C扩展，无法查看
```

**保护**:
- ✅ 用户无法查看验证逻辑
- ✅ 用户无法修改激活方法
- ✅ 必须通过在线验证

---

## 🧪 测试

### 测试编译结果

```powershell
# 1. 测试core模块
python -c "import core; print(core.__version__)"

# 2. 测试许可证管理器
python -c "from core.licensing import LicenseManager; m = LicenseManager(); print(m.tier)"

# 3. 测试验证器
python -c "from core.licensing.validator import LicenseValidator; v = LicenseValidator()"
```

### 测试许可证激活

```python
from core.licensing import LicenseManager

manager = LicenseManager()
success, error = manager.activate("pro-xxxx-xxxx-xxxx")

if success:
    print(f"✅ 激活成功！级别: {manager.tier}")
else:
    print(f"❌ 激活失败: {error}")
```

---

## 🔧 故障排查

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

---

## 📞 获取帮助

### 文档

- [安全改进总结](./SECURITY_IMPROVEMENTS_SUMMARY.md) - 完整的改进说明
- [混合编译策略](./HYBRID_COMPILATION_STRATEGY.md) - 技术细节
- [Pro版快速参考](./PRO_PACKAGE_QUICK_REF.md) - 常用命令

### 常见问题

1. **Q: Cython编译失败怎么办？**
   - A: 安装Visual Studio Build Tools，或使用 `-SkipCython` 参数

2. **Q: 如何测试编译结果？**
   - A: 运行 `python -c "import core; print(core.__version__)"`

3. **Q: 许可证验证失败怎么办？**
   - A: 检查网络连接，或使用离线模式测试

---

**最后更新**: 2026-01-04
**版本**: 2.0.0

