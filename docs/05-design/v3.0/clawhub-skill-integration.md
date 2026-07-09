# ClawHub Skill 接入方案设计文档

> 本文档记录 TradingAgentsCN 项目如何正确接入 ClawHub/OpenClaw 生态的 Skill，重点解决 Python 脚本型 Skill 的安装、执行和凭证管理问题。

## 0. 一句话总结

当前项目只支持 SKILL.md 内嵌代码的 Skill，无法接入 ClawHub 上依赖外部脚本文件的 Python 脚本型 Skill。本方案通过支持本地 Skill 包管理、脚本执行和凭证配置，让项目能正确接入 ClawHub 生态的金融数据类 Skill。

---

## 1. 背景与问题

### 1.1 ClawHub Skill 生态

ClawHub（clawhub.ai）是 OpenClaw 官方的 Skill 注册中心，目前有 13000+ Skills。Skill 包结构：

```
my-skill/
├── SKILL.md           # 必需：YAML frontmatter + Markdown 指令
├── scripts/           # 可选：可执行脚本（Python/Bash/Node.js）
│   └── fetch_data.py
├── references/        # 可选：参考文档（按需加载）
│   └── api-docs.md
└── assets/            # 可选：静态资源（模板、图标等）
```

### 1.2 Skill 类型

| 类型 | 特征 | 项目是否适用 |
|---|---|---|
| **知识型** | 只有 SKILL.md，无 scripts | ❌ 不适用（依赖 OpenClaw 工具链） |
| **Python 脚本型** | 有 scripts/*.py | ✅ 适用（项目支持 Python 沙箱） |
| **需要凭证型** | frontmatter 声明 env | ✅ 适用（需要凭证管理） |

### 1.3 当前问题

| # | 问题 | 影响 |
|---|---|---|
| 1 | 只支持 SKILL.md 内嵌代码，不支持外部脚本 | 无法接入 ClawHub 上 90% 的 Skill |
| 2 | 无法下载完整 Skill 包（含 scripts/） | 只能获取 SKILL.md 文本 |
| 3 | 无凭证管理机制 | 金融类 Skill 无法配置 API Key |
| 4 | 无 `{baseDir}` 变量替换 | 脚本无法引用同包内的其他文件 |
| 5 | 导入知识型 Skill 无意义 | 误导用户，浪费资源 |

### 1.4 用户需求

1. **不要知识型 Skill** — 项目用不了
2. **支持 Python 脚本型 Skill** — 需要安装到本地目录，包含 scripts/ 文件
3. **支持凭证配置** — 金融类 Skill 需要 key

---

## 2. 解决方案

### 2.1 方案概览

```
ClawHub Skill
  ↓ 下载完整包（含 scripts/）
本地 Skill 存储目录
  ↓ 解析 SKILL.md frontmatter
注册到 MongoDB + ToolRegistry
  ↓ 配置凭证（env vars）
执行时注入环境变量 + {baseDir} 替换
  ↓ 调用 scripts/*.py
返回结果给 Agent
```

### 2.2 本地 Skill 存储目录

```
c:\TradingAgentsCN\
├── skills/                    # Skill 包存储目录
│   ├── ifind-finance-search/  # 每个 Skill 一个子目录
│   │   ├── SKILL.md
│   │   ├── scripts/
│   │   │   └── fetch_data.py
│   │   ├── references/
│   │   └── assets/
│   └── weather-query/
│       ├── SKILL.md
│       └── scripts/
│           └── weather.py
```

### 2.3 Skill 执行机制

```python
# 执行 Skill 脚本时：
# 1. 设置 baseDir 环境变量为 Skill 目录路径
# 2. 注入凭证环境变量
# 3. 执行 scripts/*.py
# 4. 捕获输出

import subprocess
import os

env = os.environ.copy()
env["baseDir"] = skill_dir  # {baseDir} 替换
env["IFIND_AUTH_TOKEN"] = "user_configured_token"  # 凭证注入

result = subprocess.run(
    ["python", f"{skill_dir}/scripts/fetch_data.py", query],
    capture_output=True,
    text=True,
    env=env,
    timeout=30
)
```

### 2.4 凭证管理

**frontmatter 声明**：
```yaml
metadata:
  openclaw:
    env:
      - name: IFIND_AUTH_TOKEN
        description: "飞研平台认证 token"
        required: true
      - name: IFIND_BASE_URL
        description: "API 基础 URL"
        required: false
```

**MongoDB 存储**：
```javascript
// skill_credentials 集合
{
  skill_name: "ifind-finance-search",
  credentials: {
    "IFIND_AUTH_TOKEN": "encrypted_token_value",
    "IFIND_BASE_URL": "https://repilot.51ifind.com"
  },
  created_at: ISODate("..."),
  updated_at: ISODate("...")
}
```

**UI 配置**：
- Skill 详情页显示需要配置的凭证列表
- 用户输入凭证值，加密存储
- 执行时自动注入环境变量

---

## 3. 实施计划

### 3.1 阶段 1：本地 Skill 包管理（P0）

| 任务 | 说明 |
|---|---|
| 创建 `skills/` 目录 | Skill 包存储根目录 |
| 实现 ClawHub Skill 下载 | 通过 API 下载完整 Skill 包（含 scripts/） |
| 实现本地 Skill 导入 | 扫描 `skills/` 目录，解析 SKILL.md |
| 实现 `{baseDir}` 替换 | 脚本执行时替换为实际路径 |

### 3.2 阶段 2：凭证管理（P0）

| 任务 | 说明 |
|---|---|
| 解析 frontmatter env 声明 | 从 SKILL.md 提取需要的凭证列表 |
| 凭证存储 API | CRUD 接口，加密存储 |
| 凭证配置 UI | Skill 详情页配置凭证 |
| 执行时凭证注入 | 脚本执行时注入环境变量 |

### 3.3 阶段 3：Skill 执行集成（P0）

| 任务 | 说明 |
|---|---|
| 修改 SkillExecutor | 支持执行本地脚本型 Skill |
| 修改 ToolRegistry 注册 | 脚本型 Skill 注册为可调用工具 |
| 修改测试逻辑 | 支持测试脚本型 Skill |

### 3.4 阶段 4：UI 优化（P1）

| 任务 | 说明 |
|---|---|
| Skill 中心增加"安装"入口 | 从 ClawHub 安装 Skill |
| Skill 详情页显示包结构 | 展示 scripts/、references/ 等 |
| 凭证配置状态展示 | 显示已配置/未配置 |
| 移除知识型 Skill 支持 | 不再导入知识型 Skill |

---

## 4. 技术实现细节

### 4.1 ClawHub Skill 下载

```python
# app/services/clawhub_skill_service.py

import httpx
import os
import zipfile
import io
from pathlib import Path

class ClawHubSkillService:
    """ClawHub Skill 下载和管理服务"""
    
    SKILLS_DIR = Path("skills")  # Skill 存储根目录
    
    @classmethod
    async def install_skill(cls, skill_slug: str) -> dict:
        """从 ClawHub 安装 Skill
        
        Args:
            skill_slug: Skill 标识，如 "@wenzisay/ifind-repilot-finance-data-search"
        
        Returns:
            安装结果
        """
        # 1. 获取 Skill 包 ZIP
        zip_url = f"https://clawhub.ai/api/v1/skills/{skill_slug}/download"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(zip_url)
            resp.raise_for_status()
        
        # 2. 解压到 skills/ 目录
        skill_name = skill_slug.split("/")[-1]
        skill_dir = cls.SKILLS_DIR / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            zf.extractall(skill_dir)
        
        # 3. 解析 SKILL.md
        skill_md_path = skill_dir / "SKILL.md"
        if not skill_md_path.exists():
            raise FileNotFoundError("SKILL.md not found in package")
        
        # 4. 注册到 MongoDB 和 ToolRegistry
        await cls._register_skill(skill_dir, skill_md_path)
        
        return {
            "success": True,
            "skill_name": skill_name,
            "skill_dir": str(skill_dir),
            "message": "Skill 安装成功"
        }
```

### 4.2 脚本型 Skill 执行

```python
# core/skills/script_executor.py

import subprocess
import os
from pathlib import Path
from typing import Dict, Any

class ScriptSkillExecutor:
    """脚本型 Skill 执行器"""
    
    @staticmethod
    def execute(
        skill_dir: str,
        script_path: str,
        args: list = None,
        credentials: Dict[str, str] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """执行 Skill 脚本
        
        Args:
            skill_dir: Skill 包目录路径
            script_path: 脚本相对路径（如 "scripts/fetch_data.py"）
            args: 命令行参数
            credentials: 凭证环境变量
            timeout: 超时秒数
        
        Returns:
            {success, result, error, execution_time_ms}
        """
        import time
        start = time.time()
        
        # 构建环境变量
        env = os.environ.copy()
        env["baseDir"] = skill_dir  # {baseDir} 替换
        if credentials:
            for key, value in credentials.items():
                env[key] = value
        
        # 构建命令
        full_script_path = Path(skill_dir) / script_path
        cmd = ["python", str(full_script_path)]
        if args:
            cmd.extend(args)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=timeout,
                cwd=skill_dir
            )
            
            execution_time_ms = int((time.time() - start) * 1000)
            
            if result.returncode == 0:
                return {
                    "success": True,
                    "result": result.stdout,
                    "error": None if not result.stderr else result.stderr,
                    "execution_time_ms": execution_time_ms
                }
            else:
                return {
                    "success": False,
                    "result": None,
                    "error": result.stderr or f"Exit code: {result.returncode}",
                    "execution_time_ms": execution_time_ms
                }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "result": None,
                "error": f"执行超时（{timeout}秒）",
                "execution_time_ms": timeout * 1000
            }
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "error": str(e),
                "execution_time_ms": int((time.time() - start) * 1000)
            }
```

### 4.3 凭证管理

```python
# app/services/skill_credential_service.py

from cryptography.fernet import Fernet
from app.core.config import settings

class SkillCredentialService:
    """Skill 凭证管理服务"""
    
    @staticmethod
    def _get_fernet() -> Fernet:
        """获取 Fernet 加密器"""
        key = settings.JWT_SECRET.encode()[:32].ljust(32)
        import base64
        return Fernet(base64.urlsafe_b64encode(key))
    
    @classmethod
    async def save_credentials(
        cls, db, skill_name: str, credentials: Dict[str, str]
    ):
        """保存 Skill 凭证（加密存储）"""
        fernet = cls._get_fernet()
        encrypted = {
            key: fernet.encrypt(value.encode()).decode()
            for key, value in credentials.items()
        }
        await db.skill_credentials.update_one(
            {"skill_name": skill_name},
            {"$set": {"credentials": encrypted, "skill_name": skill_name}},
            upsert=True
        )
    
    @classmethod
    async def get_credentials(
        cls, db, skill_name: str
    ) -> Dict[str, str]:
        """获取 Skill 凭证（解密）"""
        doc = await db.skill_credentials.find_one({"skill_name": skill_name})
        if not doc:
            return {}
        
        fernet = cls._get_fernet()
        decrypted = {}
        for key, encrypted_value in doc.get("credentials", {}).items():
            try:
                decrypted[key] = fernet.decrypt(encrypted_value.encode()).decode()
            except Exception:
                decrypted[key] = ""
        return decrypted
    
    @classmethod
    async def get_required_credentials(cls, skill_dir: str) -> list:
        """从 SKILL.md 解析需要的凭证列表"""
        from core.skills.parser import SkillParser
        skill_md_path = Path(skill_dir) / "SKILL.md"
        skill = SkillParser.parse_file(str(skill_md_path))
        
        # 从 frontmatter 提取 env 声明
        env_vars = []
        metadata = skill.metadata or {}
        openclaw_meta = metadata.get("openclaw", {}) if isinstance(metadata, dict) else {}
        env_decls = openclaw_meta.get("env", [])
        
        for env_decl in env_decls:
            if isinstance(env_decl, dict):
                env_vars.append({
                    "name": env_decl.get("name", ""),
                    "description": env_decl.get("description", ""),
                    "required": env_decl.get("required", False)
                })
            elif isinstance(env_decl, str):
                env_vars.append({
                    "name": env_decl,
                    "description": "",
                    "required": True
                })
        
        return env_vars
```

### 4.4 修改 SkillExecutor

```python
# core/skills/executor.py - 新增 _execute_script 方法

class SkillExecutor:
    
    @staticmethod
    async def _execute_script(
        skill_dir: str,
        script_path: str,
        credentials: Dict[str, str] = None,
        **kwargs
    ) -> Any:
        """执行脚本型 Skill
        
        Args:
            skill_dir: Skill 包目录
            script_path: 脚本路径
            credentials: 凭证
            **kwargs: 传递给脚本的参数
        """
        from core.skills.script_executor import ScriptSkillExecutor
        
        # 将 kwargs 转换为命令行参数
        args = []
        for key, value in kwargs.items():
            args.extend([f"--{key}", str(value)])
        
        result = ScriptSkillExecutor.execute(
            skill_dir=skill_dir,
            script_path=script_path,
            args=args,
            credentials=credentials,
            timeout=60
        )
        
        if not result["success"]:
            raise RuntimeError(result["error"])
        
        # 尝试解析 JSON
        output = result["result"]
        try:
            import json
            return json.loads(output)
        except (json.JSONDecodeError, ValueError):
            return output
```

---

## 5. API 设计

### 5.1 ClawHub Skill 安装

```
POST /api/skills/install-clawhub
Body: { "skill_slug": "@wenzisay/ifind-repilot-finance-data-search" }
Response: { "success": true, "skill_name": "...", "skill_dir": "..." }
```

### 5.2 本地 Skill 导入

```
POST /api/skills/import-local
Body: { "skill_dir": "skills/ifind-finance-search" }
Response: { "success": true, "skill_name": "..." }
```

### 5.3 凭证管理

```
GET  /api/skills/{skill_name}/credentials/required
     → 返回需要的凭证列表

POST /api/skills/{skill_name}/credentials
Body: { "credentials": { "IFIND_AUTH_TOKEN": "xxx" } }
     → 保存凭证（加密）

GET  /api/skills/{skill_name}/credentials
     → 返回凭证状态（已配置/未配置，不返回明文）
```

### 5.4 脚本型 Skill 测试

```
POST /api/skills/{skill_name}/test
Body: { "args": { "query": "贵州茅台当前股价" } }
Response: { "success": true, "result": "..." }
```

---

## 6. 前端 UI 设计

### 6.1 Skill 中心新增"安装"入口

```
Skill 中心
├── 我的 Skill
├── 发现/导入
│   ├── SkillHub（腾讯）
│   ├── ClawHub（OpenClaw）  ← 新增
│   └── GitHub
├── AI 生成
├── 能力缺口
└── 执行日志
```

### 6.2 ClawHub Tab

- 搜索框：搜索 ClawHub 上的 Skill
- Skill 列表：显示名称、描述、作者、下载量
- 安装按钮：一键安装到本地
- 过滤器：只显示 Python 脚本型（过滤掉知识型）

### 6.3 Skill 详情页

```
┌─────────────────────────────────────┐
│ ifind-finance-data-search           │
│                                     │
│ 类型: Python 脚本型                  │
│ 来源: ClawHub                       │
│ 目录: skills/ifind-finance-search/  │
│                                     │
│ 📁 包结构                            │
│ ├── SKILL.md                        │
│ ├── scripts/fetch_data.py           │
│ └── references/                     │
│                                     │
│ 🔑 凭证配置                          │
│ ├── IFIND_AUTH_TOKEN: ✅ 已配置      │
│ └── IFIND_BASE_URL:  ❌ 未配置       │
│ [配置凭证]                           │
│                                     │
│ [测试] [绑定 Agent] [删除]           │
└─────────────────────────────────────┘
```

---

## 7. 注意事项

1. **安全性**：
   - 脚本在子进程中执行，有超时限制
   - 凭证加密存储（Fernet）
   - 不执行知识型 Skill（无脚本）

2. **兼容性**：
   - 保留现有 SKILL.md 内嵌代码的支持
   - 新增脚本型 Skill 的支持
   - 两种方式共存

3. **性能**：
   - 脚本执行有 30-60 秒超时
   - 凭证解密缓存
   - Skill 包下载有大小限制

4. **错误处理**：
   - 下载失败：提示用户重试
   - 脚本执行失败：返回 stderr
   - 凭证缺失：提示用户配置

---

## 8. 实施记录

### 阶段 1：本地 Skill 包管理

**状态**: ✅ 已完成

**实施内容**:
- [x] 创建 `skills/` 目录（[skills/.gitkeep](file:///c:/TradingAgentsCN/skills/.gitkeep)）
- [x] 实现 ClawHub Skill 下载服务（[app/services/clawhub_skill_service.py](file:///c:/TradingAgentsCN/app/services/clawhub_skill_service.py)）
- [x] 实现本地 Skill 导入（拒绝知识型）
- [x] 实现 `{baseDir}` / `<skill_dir>` 变量替换（[core/skills/script_executor.py](file:///c:/TradingAgentsCN/core/skills/script_executor.py)）
- [x] 新增 API 端点（[app/routers/skills.py](file:///c:/TradingAgentsCN/app/routers/skills.py)）

**新增文件**:
1. `app/services/clawhub_skill_service.py` - ClawHub Skill 下载与管理服务
   - `ClawHubSkillService.search_skills(query, limit)` - 搜索 ClawHub Skill
   - `ClawHubSkillService.get_skill_info(slug)` - 获取 Skill 元数据
   - `ClawHubSkillService.install_skill(slug, version, tag)` - 安装 Skill 包到本地
   - `ClawHubSkillService.list_local_skills()` - 列出本地已安装的 Skill
   - `ClawHubSkillService.uninstall_local_skill(slug)` - 卸载本地 Skill

2. `core/skills/script_executor.py` - 脚本型 Skill 执行器
   - `ScriptSkillExecutor.execute(skill_dir, script_path, args, credentials)` - 执行脚本
   - `ScriptSkillExecutor.replace_base_dir(text, skill_dir)` - 替换 `{baseDir}` / `<skill_dir>` 变量
   - `ScriptSkillExecutor.prepare_script_args(skill_doc, call_args)` - 准备调用参数

**修改文件**:
1. `app/routers/skills.py` - 新增 ClawHub 相关 API 端点
   - `GET /api/skills/clawhub/search?q=...` - 搜索 ClawHub Skill
   - `POST /api/skills/install-clawhub` - 从 ClawHub 安装 Skill 包
   - `POST /api/skills/import-local` - 从本地目录导入 Skill
   - `GET /api/skills/local` - 列出本地已安装的 Skill 包
   - `DELETE /api/skills/local/{slug}` - 卸载本地 Skill 包
   - 修改 `_register_skill_to_registry` - 过滤扩展字段，支持本地脚本型 Skill

**ClawHub API 调研结果**:
- 官方 API 文档: https://docs.openclaw.ai/clawhub/api
- 下载端点: `GET /api/v1/download?slug=&version=&tag=` (无需认证)
- 搜索端点: `GET /api/v1/search?q=...` (无需认证)
- 元数据端点: `GET /api/v1/skills/{slug}` (无需认证)
- 速率限制: 匿名下载 1200/min per IP，搜索 3000/min per IP
- slug 格式: Skill 唯一标识，如 `ifind-repilot-finance-data-search`

**验证结果**:
- ✅ 搜索 API 正常工作，成功搜索到 `ifind-repilot-finance-data-search`
- ✅ 安装流程正常，成功下载并解压 Skill 包
- ✅ 知识型 Skill 拒绝导入（无 scripts/ 目录时返回错误）
- ✅ `{baseDir}` 和 `<skill_dir>` 变量替换正常工作
- ✅ 已安装的 Skill: `ifind-repilot-finance-data-search` (含 scripts/fetch_data.py)

**已安装的测试 Skill**:
```
skills/ifind-repilot-finance-data-search/
├── .clawhub/
│   └── origin.json          # 来源信息
├── scripts/
│   └── fetch_data.py        # 5061 bytes，Python 脚本
├── SKILL.md                 # 4376 bytes，Skill 定义
├── skill-card.md            # 2598 bytes，Skill 卡片
└── _meta.json               # 152 bytes，元数据
```

**注意事项**:
1. 这个 Skill 使用 `<skill_dir>` 变量（而非 `{baseDir}`），ScriptSkillExecutor 已支持两种格式
2. Skill 凭证通过命令行参数 `--set-token` 配置，存储在 `~/.config/ifind-repilot/config.json`
3. 阶段 2 需要支持这种凭证配置方式（不仅是 frontmatter env 声明）

### 阶段 2：凭证管理

**状态**: ✅ 已完成

**实施内容**:
- [x] 解析 frontmatter env 声明
- [x] 凭证加密存储（Fernet，复用 JWT_SECRET）
- [x] 凭证存储 API
- [x] 执行时凭证注入（ScriptSkillExecutor 已支持）
- [x] 支持命令行参数式凭证配置（如 `--set-token`）
- [ ] 凭证配置 UI（前端，待阶段 4 实施）

**新增文件**:
1. `app/services/skill_credential_service.py` - Skill 凭证管理服务
   - `SkillCredentialService.parse_credentials_from_skill_md(skill_dir)` - 从 SKILL.md 解析凭证声明
   - `SkillCredentialService.save_credentials(db, skill_name, credentials)` - 加密保存凭证
   - `SkillCredentialService.get_credentials_decrypted(db, skill_name)` - 获取解密后的凭证（用于执行注入）
   - `SkillCredentialService.get_credentials_status(db, skill_name, declarations)` - 获取凭证状态（遮蔽显示）
   - `SkillCredentialService.delete_credentials(db, skill_name, keys)` - 删除凭证
   - `SkillCredentialService.configure_via_script(...)` - 通过脚本命令配置凭证（如 `--set-token`）

**修改文件**:
1. `app/routers/skills.py` - 新增凭证管理 API 端点
   - `GET /api/skills/{skill_name}/credentials/required` - 获取凭证配置状态
   - `POST /api/skills/{skill_name}/credentials` - 保存凭证（加密）
   - `GET /api/skills/{skill_name}/credentials` - 获取凭证状态（别名）
   - `DELETE /api/skills/{skill_name}/credentials` - 删除凭证
   - `POST /api/skills/{skill_name}/credentials/configure-script` - 通过脚本命令配置凭证
   - 修改 `_import_local_skill_to_db` - 导入时解析凭证声明并保存到 doc

**凭证配置方式**:

1. **frontmatter env 声明**（标准方式）:
   ```yaml
   metadata:
     openclaw:
       env:
         - name: API_KEY
           description: "API 密钥"
           required: true
   ```
   执行脚本时，凭证值会注入为环境变量 `API_KEY`。

2. **命令行参数式配置**（如 ifind-repilot）:
   ```bash
   python3 <skill_dir>/scripts/fetch_data.py --set-token <your_auth_token>
   ```
   通过 `/credentials/configure-script` 端点执行配置命令，凭证值同时加密保存到 MongoDB。

**加密机制**:
- 算法：Fernet（AES-128-CBC + HMAC-SHA256）
- 密钥来源：从 `JWT_SECRET` 派生（SHA-256 哈希）
- 存储格式：`v2:<fernet_token>`
- 集合：`skill_credentials`

**验证结果**:
- ✅ 从 `ifind-repilot-finance-data-search` 的 SKILL.md 成功解析出 `--set-token` 配置命令
- ✅ 凭证名推导：`--set-token` → `TOKEN`
- ✅ Fernet 加密解密正常工作
- ✅ 遮蔽显示：`sk-ifind-1234567890abcdef` → `sk-i****cdef`
- ✅ API 端点全部注册成功（30 个路由）

**注意事项**:
1. 凭证名推导（`_derive_var_name`）可能不够语义化，如 `--set-token` 推导为 `TOKEN` 而非 `AUTH_TOKEN`。用户可通过 API 自定义凭证名。
2. 命令行参数式配置会同时执行脚本命令和保存到数据库，确保两种注入方式都能工作。
3. 执行脚本时，凭证会通过环境变量注入（`ScriptSkillExecutor.execute` 的 `credentials` 参数）。

### 阶段 3：Skill 执行集成

**状态**: ✅ 已完成

**实施内容**:
- [x] 修改 SkillExecutor - 集成 ScriptSkillExecutor
- [x] 修改 PythonImplementation 模型 - 支持 `script_path` / `skill_dir` / `timeout`
- [x] 修改 ToolRegistry 注册 - 脚本型 Skill 注册为可调用工具
- [x] 修改测试逻辑 - 支持真实执行脚本型 Skill
- [x] 实现 Agent 调用脚本型 Skill 的完整链路
- [x] 执行时自动加载并注入加密凭证

**修改文件**:
1. `core/skills/models.py`
   - `PythonImplementation` 新增 `script_path`、`skill_dir`、`timeout` 字段
   - 支持 ClawHub/OpenClaw 本地脚本型 Skill 的结构化描述

2. `core/skills/executor.py`
   - `_execute_python` 增加本地脚本执行分支
   - 当 `implementation.script_path + implementation.skill_dir` 存在时调用 `ScriptSkillExecutor.execute`

3. `app/routers/skills.py`
   - 新增 `_create_script_skill_wrapper(doc)`
   - ToolRegistry 注册时，脚本型 Skill 使用专用 wrapper
   - wrapper 执行时从 `skill_credentials` 集合加载并解密凭证
   - `/api/skills/test` 支持真实执行本地脚本型 Skill

4. `app/routers/skill_center.py`
   - 修复本地脚本型 Skill 在 Skill 中心被显示为 knowledge 的问题
   - `source_type=clawhub` 时来源显示为 `clawhub`

**执行链路**:
```text
Agent / 智能助手
  -> ToolRegistry.get_tool(tool_id)
  -> _create_script_skill_wrapper
  -> 加载 skill_credentials 并解密
  -> ScriptSkillExecutor.execute(skill_dir, script_path, args, credentials)
  -> subprocess 执行 scripts/*.py
  -> stdout JSON 解析返回
```

**测试链路**:
```text
POST /api/skills/test
  -> _test_skill_doc
  -> 检测 implementation.script_path + skill_dir
  -> 加载凭证
  -> ScriptSkillExecutor.execute
  -> 返回真实执行结果
```

**验证结果**:
- ✅ 后端 Python 语法检查通过
- ✅ skills.py 路由加载成功（30 个路由）
- ✅ PythonImplementation 支持 `script_path` / `skill_dir`
- ✅ skill_center.py 语法检查通过

### 阶段 4：UI 优化

**状态**: ✅ 已完成（基础版）

**实施内容**:
- [x] Skill 中心增加"ClawHub 安装"入口
- [x] 支持 ClawHub 搜索
- [x] 支持输入 slug 安装并导入
- [x] 支持本地 Skill 包列表展示
- [x] 支持本地包手动导入
- [x] Skill 列表增加"凭证"按钮
- [x] 凭证配置弹窗
- [x] 支持 env 凭证保存
- [x] 支持 `--set-token` 脚本命令式凭证配置
- [x] ClawHub 来源展示
- [ ] 包结构详情展示（后续可增强）

**修改文件**:
1. `frontend/src/api/skills.ts`
   - 新增 ClawHub 类型：`ClawHubSearchResult`、`ClawHubInstallResponse`、`LocalSkillItem`
   - 新增凭证类型：`CredentialRequirement`、`CredentialStatusResponse`
   - 新增 API 方法：
     - `searchClawHub`
     - `installClawHub`
     - `importLocalSkill`
     - `listLocalSkills`
     - `getCredentialStatus`
     - `saveCredentials`
     - `configureCredentialViaScript`

2. `frontend/src/views/Workflow/SkillCenter.vue`
   - 新增 `ClawHub 安装` Tab
   - 新增搜索、安装、本地包列表功能
   - Skill 操作列新增 `凭证` 按钮
   - 新增凭证配置弹窗
   - 自动根据凭证类型选择保存方式：
     - `env` → 保存到 MongoDB 加密凭证
     - `script_arg` → 执行 `/credentials/configure-script`

**UI 使用流程**:
```text
Skill 中心
  -> ClawHub 安装 Tab
  -> 输入 slug 或搜索关键词
  -> 安装并导入
  -> 回到我的 Skill
  -> 点击“凭证”配置 token/key
  -> 点击“测试”真实执行脚本
  -> 绑定 Agent 后 Agent 可调用
```

**验证结果**:
- ✅ SkillCenter.vue 无 VS Code 诊断错误
- ✅ skills.ts 无 VS Code 诊断错误
