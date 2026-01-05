# TradingAgents-CN Pro 版本打包说明

## 📦 打包策略

### 免费版 vs Pro版 打包差异

| 内容类型 | 免费版 | Pro版 |
|---------|--------|------|
| **核心功能代码** | ✅ 完整 | ✅ 完整 |
| **基础文档** | ✅ 完整 | ✅ 完整 |
| **24节课程源码** | ✅ 包含 | ❌ 不包含 |
| **课程PPT源文件** | ✅ 包含 | ❌ 不包含 |
| **设计文档** | ✅ 包含 | ❌ 不包含 |
| **前端Pro功能** | ✅ 包含（需许可证） | ✅ 包含（需许可证） |

---

## 🔐 Pro版保护策略

### 1. 课程内容保护

**排除的目录**：
```
docs/courses/advanced/expanded/     # 24节课程扩写内容（约3万行）
docs/courses/advanced/ppt/          # PPT源文件
docs/courses/advanced/images/       # 课程截图（约110张）
docs/design/                        # 设计文档
```

**保留的内容**：
```
docs/courses/advanced/README.md     # 课程目录（可见）
docs/courses/advanced/*.md          # 课程大纲（可见）
```

**用户体验**：
- 用户可以看到课程目录和大纲
- 点击课程时，前端检测许可证
- 无许可证：显示升级提示
- 有许可证：从服务器加载课程内容

### 2. 前端代码保护

**前端构建后的代码**：
- ✅ 已经过 Vite 打包混淆
- ✅ 源码不可读
- ✅ Pro功能有许可证门控

**许可证验证**：
```typescript
// frontend/src/components/LicenseGate.vue
// 在组件级别验证许可证
if (!hasProLicense) {
  showUpgradePrompt()
}
```

### 3. 后端代码保护

**后端代码**：
- ⚠️ Python代码是明文的
- ✅ 但有许可证验证逻辑
- ✅ 关键功能需要许可证才能调用

**建议**：
- 考虑使用 PyInstaller 打包后端（可选）
- 或者保持现状，依赖许可证验证

---

## 🛠️ 打包脚本使用

### 方案一：使用Pro版同步脚本（推荐）

```powershell
# 1. 使用Pro版同步脚本
.\scripts\deployment\sync_to_portable_pro.ps1

# 2. 构建打包
.\scripts\deployment\build_portable_package.ps1 -SkipSync
```

### 方案二：修改原有脚本

修改 `build_portable_package.ps1`，将同步脚本改为Pro版：

```powershell
# 第33行附近，修改为：
$syncScript = Join-Path $root "scripts\deployment\sync_to_portable_pro.ps1"
```

---

## 📋 打包检查清单

### 打包前检查

- [ ] 确认当前分支是 `feature/professional-edition`
- [ ] 确认前端已构建（`yarn build`）
- [ ] 确认许可证验证逻辑已测试
- [ ] 确认课程内容不在打包目录中

### 打包后验证

```powershell
# 1. 解压打包文件到测试目录
Expand-Archive -Path "release\packages\TradingAgentsCN-Portable-*.zip" -DestinationPath "test-package"

# 2. 检查课程目录
Get-ChildItem "test-package\docs\courses\advanced" -Recurse

# 应该看到：
# ✅ README.md
# ✅ *.md (课程大纲)
# ❌ expanded/ (不应该存在)
# ❌ ppt/ (不应该存在)
# ❌ images/ (不应该存在)

# 3. 启动测试
cd test-package
.\start_all.ps1

# 4. 访问课程页面，验证：
# - 课程目录可见
# - 点击课程显示升级提示（无许可证）
# - 输入许可证后可以访问（有许可证）
```

---

## 🔄 课程内容分发策略

### 选项A：在线加载（推荐）

**优点**：
- ✅ 课程内容完全保护
- ✅ 可以随时更新课程
- ✅ 可以追踪用户学习进度

**实现**：
```typescript
// 前端从API加载课程内容
async function loadLesson(lessonId: string) {
  const response = await api.get(`/api/courses/advanced/${lessonId}`, {
    headers: { 'X-License-Key': licenseKey }
  })
  return response.data
}
```

**后端**：
```python
# app/routers/courses.py
@router.get("/courses/advanced/{lesson_id}")
async def get_lesson(lesson_id: str, license_key: str = Header(None)):
    # 验证许可证
    if not verify_license(license_key):
        raise HTTPException(403, "需要Pro许可证")
    
    # 从数据库或文件加载课程内容
    return load_lesson_content(lesson_id)
```

### 选项B：加密打包

**优点**：
- ✅ 离线可用
- ✅ 内容加密保护

**缺点**：
- ❌ 无法更新课程
- ❌ 需要额外的加密/解密逻辑

**实现**：
```python
# 打包时加密课程内容
import cryptography

def encrypt_course_content(content: str, key: bytes) -> bytes:
    # 使用Fernet加密
    f = Fernet(key)
    return f.encrypt(content.encode())

# 运行时解密
def decrypt_course_content(encrypted: bytes, license_key: str) -> str:
    key = derive_key_from_license(license_key)
    f = Fernet(key)
    return f.decrypt(encrypted).decode()
```

---

## 📝 建议

### 短期方案（立即可用）

1. ✅ 使用 `sync_to_portable_pro.ps1` 排除课程源码
2. ✅ 前端保持许可证门控
3. ✅ 课程内容通过在线API提供

### 长期方案（更安全）

1. 考虑使用 PyInstaller 打包后端为可执行文件
2. 课程内容加密存储
3. 实现更完善的许可证管理系统（在线验证、过期检查等）

---

## ⚠️ 重要提醒

1. **不要将Pro版打包文件上传到公开仓库**
2. **定期更新许可证验证逻辑**
3. **监控许可证使用情况**
4. **保留课程源码的备份**

---

## 📞 问题排查

### 问题1：打包后课程内容仍然存在

**检查**：
```powershell
# 查看打包文件中的docs目录
7z l "release\packages\TradingAgentsCN-Portable-*.zip" | Select-String "docs/courses"
```

**解决**：
- 确认使用了 `sync_to_portable_pro.ps1`
- 检查 `$excludeDirs` 配置是否正确

### 问题2：用户无法访问课程

**检查**：
- 许可证是否正确配置
- API端点是否正常
- 前端许可证验证逻辑是否正确

---

**最后更新**：2026-01-04

