# TradingAgents-CN Pro 版本打包指南

## 📋 概述

本指南说明如何打包 TradingAgents-CN Pro 版本，确保课程源码和敏感内容不被包含在分发包中。

---

## 🎯 打包目标

### 需要排除的内容

| 内容 | 路径 | 原因 |
|-----|------|------|
| **24节课程源码** | `docs/courses/advanced/expanded/` | 付费内容，约3万行Markdown |
| **课程PPT源文件** | `docs/courses/advanced/ppt/` | 付费内容 |
| **课程截图** | `docs/courses/advanced/expanded/images/` | 付费内容，约110张 |
| **设计文档** | `docs/design/` | 内部文档 |
| **致谢邮件** | `docs/email-to-tradingagents-team.txt` | 内部文档 |

### 需要保留的内容

| 内容 | 路径 | 说明 |
|-----|------|------|
| **课程目录** | `docs/courses/advanced/README.md` | 让用户看到课程列表 |
| **课程大纲** | `docs/courses/advanced/*.md` | 让用户了解课程内容 |
| **核心代码** | `app/`, `tradingagents/`, `web/` | 完整功能代码 |
| **前端构建** | `frontend/dist/` | 已混淆的前端代码 |

---

## 🚀 快速开始

### 一键打包（推荐）

```powershell
# 在项目根目录执行
.\scripts\deployment\build_pro_package.ps1
```

这个脚本会：
1. ✅ 使用Pro版同步脚本（自动排除课程源码）
2. ✅ 构建前端
3. ✅ 打包为ZIP文件

### 验证打包结果

```powershell
# 验证最新的打包文件
.\scripts\deployment\verify_pro_package.ps1

# 或指定文件
.\scripts\deployment\verify_pro_package.ps1 -PackagePath "release\packages\TradingAgentsCN-Portable-v1.0.0.zip"
```

---

## 📝 详细步骤

### 步骤1：准备代码

```powershell
# 1. 切换到正确的分支
git checkout feature/professional-edition

# 2. 确保代码是最新的
git pull origin feature/professional-edition

# 3. 检查许可证验证逻辑
# 确保前后端的许可证验证都正常工作
```

### 步骤2：构建前端

```powershell
cd frontend

# 安装依赖
yarn install --frozen-lockfile

# 构建（会自动混淆代码）
yarn vite build

cd ..
```

### 步骤3：同步代码（Pro版）

```powershell
# 使用Pro版同步脚本
.\scripts\deployment\sync_to_portable_pro.ps1

# 检查同步结果
Get-ChildItem "release\TradingAgentsCN-portable\docs\courses\advanced" -Recurse

# 应该看到：
# ✅ README.md
# ✅ *.md (课程大纲)
# ❌ expanded/ (不应该存在)
# ❌ ppt/ (不应该存在)
```

### 步骤4：打包

```powershell
# 打包（跳过同步，因为已经手动同步过了）
.\scripts\deployment\build_portable_package.ps1 -SkipSync -Version "v1.0.0"
```

### 步骤5：验证

```powershell
# 运行验证脚本
.\scripts\deployment\verify_pro_package.ps1

# 应该看到：
# ✅ PASS: Course expanded content excluded
# ✅ PASS: PPT source files excluded
# ✅ PASS: Design documents excluded
# ✅ PASS: Course README exists
# ✅ PASS: Core files present
# ✅ PASS: Frontend dist exists
```

---

## 🔍 验证检查清单

### 自动验证（使用脚本）

```powershell
.\scripts\deployment\verify_pro_package.ps1
```

### 手动验证

```powershell
# 1. 解压打包文件
$testDir = "C:\temp\test-package"
Expand-Archive -Path "release\packages\TradingAgentsCN-Portable-*.zip" -DestinationPath $testDir

# 2. 检查课程目录
Get-ChildItem "$testDir\docs\courses\advanced" -Recurse | Select-Object FullName

# 3. 确认以下目录不存在
Test-Path "$testDir\docs\courses\advanced\expanded"  # 应该返回 False
Test-Path "$testDir\docs\courses\advanced\ppt"       # 应该返回 False
Test-Path "$testDir\docs\design"                     # 应该返回 False

# 4. 确认核心文件存在
Test-Path "$testDir\app\main.py"                     # 应该返回 True
Test-Path "$testDir\frontend\dist\index.html"        # 应该返回 True
```

---

## 🛡️ 安全检查

### 打包前

- [ ] 确认当前分支是 `feature/professional-edition`
- [ ] 确认许可证验证逻辑已测试通过
- [ ] 确认前端已构建（`frontend/dist` 存在）
- [ ] 确认没有敏感信息在代码中（API密钥、密码等）

### 打包后

- [ ] 运行 `verify_pro_package.ps1` 验证通过
- [ ] 手动检查解压后的文件
- [ ] 测试启动和基本功能
- [ ] 测试许可证验证（无许可证应该无法访问课程）

---

## 📦 打包文件说明

### 文件命名

```
TradingAgentsCN-Portable-{版本号}-{时间戳}.zip
```

示例：
```
TradingAgentsCN-Portable-v1.0.0-20260104-143000.zip
```

### 文件大小

| 版本 | 预期大小 | 说明 |
|-----|---------|------|
| **免费版** | ~800MB | 包含课程源码 |
| **Pro版** | ~750MB | 排除课程源码（节省约50MB） |

---

## 🔄 课程内容分发

### 方案：在线API加载（推荐）

**前端实现**：
```typescript
// frontend/src/api/courses.ts
export async function loadLesson(lessonId: string) {
  const licenseKey = localStorage.getItem('pro_license_key')
  
  const response = await api.get(`/api/courses/advanced/${lessonId}`, {
    headers: { 'X-License-Key': licenseKey }
  })
  
  return response.data
}
```

**后端实现**：
```python
# app/routers/courses.py
from fastapi import APIRouter, Header, HTTPException

router = APIRouter()

@router.get("/courses/advanced/{lesson_id}")
async def get_lesson(
    lesson_id: str,
    x_license_key: str = Header(None, alias="X-License-Key")
):
    # 验证许可证
    if not verify_license(x_license_key):
        raise HTTPException(status_code=403, detail="需要Pro许可证")
    
    # 从数据库或文件加载课程内容
    lesson_content = load_lesson_from_db(lesson_id)
    
    return {
        "lesson_id": lesson_id,
        "content": lesson_content,
        "title": get_lesson_title(lesson_id)
    }
```

---

## ⚠️ 常见问题

### Q1: 打包后课程内容仍然存在？

**A**: 确认使用了 `sync_to_portable_pro.ps1` 而不是 `sync_to_portable.ps1`

### Q2: 用户如何访问课程？

**A**: 用户需要：
1. 购买Pro许可证
2. 在系统设置中输入许可证密钥
3. 系统验证许可证后，从API加载课程内容

### Q3: 如何更新课程内容？

**A**: 
- 课程内容存储在服务器端
- 更新课程只需更新服务器端的内容
- 用户无需重新下载客户端

---

## 📞 技术支持

如有问题，请查看：
- `scripts/deployment/README_PRO_PACKAGING.md` - 详细技术文档
- `scripts/deployment/verify_pro_package.ps1` - 验证脚本源码

---

**最后更新**：2026-01-04

