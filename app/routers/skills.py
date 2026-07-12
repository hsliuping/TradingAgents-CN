"""
Skill 管理 API

基于 Agent Skills 标准 + 扩展字段的 Skill CRUD 接口。
支持：导入 SKILL.md、从 URL 导入、列表查询、更新、删除、启用/禁用、注册到 ToolRegistry
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query, UploadFile, File
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.database import get_mongo_db
from app.services.capability_index_service import CapabilityIndexService
from app.services.clawhub_skill_service import ClawHubSkillService, SKILLS_DIR
from app.services.skillhub_service import SkillHubService
from app.services.skill_credential_service import (
    SkillCredentialService,
    CredentialDeclaration,
    CREDENTIALS_COLLECTION,
)
from core.skills.models import SkillMetadata, SkillParameter, SkillReturns, ImplementationType
from core.skills.parser import SkillParser
from core.skills.converter import SkillConverter
from core.skills.executor import SkillExecutor
from core.skills.script_executor import ScriptSkillExecutor
from core.tools.registry import get_tool_registry

logger = logging.getLogger("webapi")

router = APIRouter(prefix="/api/skills", tags=["skills"])

COLLECTION = "skills"


# =============================================================================
# 请求/响应模型
# =============================================================================

class SkillResponse(BaseModel):
    """Skill 响应模型"""
    id: str = ""
    name: str
    description: str
    version: str = "1.0.0"
    author: str = ""
    category: str = "general"
    tags: List[str] = []
    icon: str = "🔧"
    color: str = "#95a5a6"
    when_to_use: str = ""
    parameters: List[Dict[str, Any]] = []
    returns: Optional[Dict[str, Any]] = None
    implementation: Optional[Dict[str, Any]] = None
    instructions: str = ""
    enabled: bool = True
    fc_enabled: bool = True
    is_builtin: bool = False
    skill_type: str = "knowledge"
    is_executable: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SkillCreateRequest(BaseModel):
    """创建 Skill 请求"""
    name: str
    description: str
    version: str = "1.0.0"
    author: str = ""
    category: str = "general"
    tags: List[str] = []
    icon: str = "🔧"
    color: str = "#95a5a6"
    when_to_use: str = ""
    parameters: List[Dict[str, Any]] = []
    returns: Optional[Dict[str, Any]] = None
    implementation: Optional[Dict[str, Any]] = None
    instructions: str = ""
    enabled: bool = True
    fc_enabled: bool = True


class SkillImportRequest(BaseModel):
    """导入 SKILL.md 请求"""
    content: str = Field(..., description="SKILL.md 文件内容")


class SkillImportUrlRequest(BaseModel):
    """从 URL 导入请求"""
    url: str = Field(..., description="SKILL.md 的直链 URL，如 GitHub raw 地址")


class SkillToggleRequest(BaseModel):
    """启用/禁用请求"""
    enabled: bool


# =============================================================================
# 辅助函数
# =============================================================================

def _doc_to_response(doc: Dict[str, Any]) -> SkillResponse:
    """将 MongoDB 文档转换为 SkillResponse"""
    doc.pop("_id", None)
    impl = doc.get("implementation")
    has_impl = impl is not None
    params = doc.get("parameters", [])
    skill_type = "knowledge"
    if has_impl:
        skill_type = impl.get("type", "unknown") if isinstance(impl, dict) else "unknown"
    return SkillResponse(
        id=doc.get("name", ""),
        name=doc.get("name", ""),
        description=doc.get("description", ""),
        version=doc.get("version", "1.0.0"),
        author=doc.get("author", ""),
        category=doc.get("category", "general"),
        tags=doc.get("tags", []),
        icon=doc.get("icon", "🔧"),
        color=doc.get("color", "#95a5a6"),
        when_to_use=doc.get("when_to_use", ""),
        parameters=params,
        returns=doc.get("returns"),
        implementation=impl,
        instructions=doc.get("instructions", ""),
        enabled=doc.get("enabled", True),
        fc_enabled=doc.get("fc_enabled", True),
        is_builtin=doc.get("is_builtin", False),
        skill_type=skill_type,
        is_executable=has_impl,
        created_at=doc.get("created_at", ""),
        updated_at=doc.get("updated_at", ""),
    )


def _skill_to_doc(skill: SkillMetadata) -> Dict[str, Any]:
    """将 SkillMetadata 转换为 MongoDB 文档"""
    doc = skill.model_dump(exclude_none=True)
    # 确保时间戳为字符串
    now = datetime.utcnow().isoformat()
    if "created_at" not in doc or not doc["created_at"]:
        doc["created_at"] = now
    doc["updated_at"] = now
    return doc


def _request_to_doc(req: SkillCreateRequest) -> Dict[str, Any]:
    """将创建请求转换为 MongoDB 文档"""
    doc = req.model_dump(exclude_none=True)
    now = datetime.utcnow().isoformat()
    doc["created_at"] = now
    doc["updated_at"] = now
    doc["is_builtin"] = False
    return doc


def _kwargs_to_cli_args(kwargs: Dict[str, Any]) -> List[str]:
    """将关键字参数转换为命令行参数列表

    约定：
    - 优先使用 `cli_args` 数组直接作为 argv（LLM 可完整控制参数）
    - 名为 `query`、`question`、`q`、`input` 的参数视为位置参数（脚本第一个 argv）
    - 其他参数转为 `--name value` 形式（下划线转连字符）
    - 布尔 True 仅加 flag（无 value）
    - None 跳过
    """
    # 优先使用 cli_args 数组（LLM 完全控制命令行参数）
    if "cli_args" in kwargs and kwargs["cli_args"] is not None:
        raw = kwargs["cli_args"]
        if isinstance(raw, list):
            return [str(x) for x in raw]
        if isinstance(raw, str):
            # 简单按空格分割（支持 LLM 用单个字符串拼接）
            import shlex
            try:
                return shlex.split(raw)
            except ValueError:
                return raw.split()

    cli_args: List[str] = []
    positional_keys = ("query", "question", "q", "input", "keyword", "text")
    positional_value = None
    extras: List[tuple] = []

    for key, value in kwargs.items():
        if value is None or key == "cli_args":
            continue
        if key in positional_keys and positional_value is None:
            positional_value = str(value)
        else:
            extras.append((key, value))

    if positional_value is not None:
        cli_args.append(positional_value)

    for key, value in extras:
        flag = f"--{key.replace('_', '-')}"
        if isinstance(value, bool):
            if value:
                cli_args.append(flag)
        else:
            cli_args.extend([flag, str(value)])

    return cli_args


def _create_script_skill_wrapper(doc: Dict[str, Any]):
    """为本地脚本型 Skill 创建同步包装函数

    该包装器会在调用时：
    1. 读取 Skill 文档中的 skill_dir 和 script_path
    2. 从 MongoDB 解密加载凭证
    3. 将 kwargs 转换为命令行参数（位置参数 + --flag value）
    4. 调用 ScriptSkillExecutor.execute_cli 执行脚本
    """
    import inspect

    impl = doc.get("implementation") or {}
    skill_name = doc.get("name", "")
    skill_dir = impl.get("skill_dir") or doc.get("skill_dir")
    script_path = impl.get("script_path")
    timeout = impl.get("timeout", 60)

    def wrapper(**kwargs):
        credentials = {}
        try:
            from app.core.database import get_mongo_db_sync
            from app.services.skill_credential_service import _decrypt_value
            db = get_mongo_db_sync()
            if db is not None:
                cred_doc = db[CREDENTIALS_COLLECTION].find_one({"skill_name": skill_name})
                if cred_doc:
                    credentials = {
                        key: _decrypt_value(value)
                        for key, value in (cred_doc.get("credentials") or {}).items()
                    }
        except Exception as e:
            logger.warning(f"⚠️ 加载 Skill '{skill_name}' 凭证失败: {e}")

        # 允许 LLM 通过 script 参数指定要调用哪个脚本（多脚本 Skill 场景）
        actual_script_path = script_path
        if kwargs.get("script"):
            requested = str(kwargs.pop("script"))
            # 在 skill_dir 中查找匹配的脚本
            sk_path = Path(skill_dir) if skill_dir else None
            if sk_path and sk_path.exists():
                # 支持相对路径、纯文件名、含/不含 .py 后缀
                candidates = []
                if not requested.endswith(".py"):
                    requested_py = requested + ".py"
                else:
                    requested_py = requested
                # 在 scripts/ 和根目录寻找
                for base in [sk_path / "scripts", sk_path]:
                    if base.is_dir():
                        for p in base.iterdir():
                            if p.is_file() and p.name == requested_py:
                                candidates.append(p)
                if candidates:
                    chosen = candidates[0]
                    # 相对路径
                    actual_script_path = str(chosen.relative_to(sk_path)).replace("\\", "/")
                    logger.info(f"🎯 Skill '{skill_name}' 选择脚本: {actual_script_path}")
                else:
                    logger.warning(f"⚠️ Skill '{skill_name}' 找不到指定脚本 '{requested}'，使用默认: {script_path}")

        cli_args = _kwargs_to_cli_args(kwargs)
        logger.info(f"🔧 调用脚本型 Skill: {skill_name} script={actual_script_path} args={cli_args}")

        result = ScriptSkillExecutor.execute_cli(
            skill_dir=skill_dir,
            script_path=actual_script_path,
            args=cli_args,
            credentials=credentials,
            timeout=timeout,
        )
        if not result.get("success"):
            raise RuntimeError(result.get("error") or "脚本执行失败")
        return result.get("result")

    wrapper.__name__ = skill_name.replace("-", "_")
    wrapper.__doc__ = doc.get("description", "")

    # 构建函数签名 - 如果 SKILL.md 没声明参数，给一个默认 `query` 参数让 LLM 知道
    params = []
    declared_params = doc.get("parameters") or []
    if declared_params:
        for p in declared_params:
            default = inspect.Parameter.empty if p.get("required", True) else p.get("default")
            params.append(inspect.Parameter(
                name=p.get("name"),
                kind=inspect.Parameter.KEYWORD_ONLY,
                default=default,
            ))
    else:
        # SKILL.md 没有声明 parameters
        # 默认提供三个参数：
        # - query: 简单场景的位置参数（字符串）
        # - cli_args: 完整命令行参数数组，用于复杂脚本（如 dcf_calculator.py --fcf 100 --shares 50）
        # - script: 多脚本 Skill 场景下指定要调用哪个脚本（如 'dcf_calculator' 或 'valuation_snapshot.py'）
        params.append(inspect.Parameter(
            name="query",
            kind=inspect.Parameter.KEYWORD_ONLY,
            default=None,
            annotation=Optional[str],
        ))
        params.append(inspect.Parameter(
            name="cli_args",
            kind=inspect.Parameter.KEYWORD_ONLY,
            default=None,
            annotation=Optional[List[str]],
        ))
        params.append(inspect.Parameter(
            name="script",
            kind=inspect.Parameter.KEYWORD_ONLY,
            default=None,
            annotation=Optional[str],
        ))

    if params:
        wrapper.__signature__ = inspect.Signature(parameters=params)
        # 同时设置 __annotations__，让 LangChain/Pydantic 推断 schema
        wrapper.__annotations__ = {p.name: (p.annotation if p.annotation != inspect.Parameter.empty else str) for p in params}

    return wrapper


async def _register_skill_to_registry(doc: Dict[str, Any]):
    """将 Skill 注册到 ToolRegistry（如果是可执行 Skill）

    规则：
    - knowledge 类型（无 implementation）：不注册为可调用工具，作为提示词上下文注入
    - python/http/mcp 类型：注册为可调用工具
    - 无参数的可执行 Skill：注册为无参函数
    - 本地脚本型 Skill（有 skill_dir + script_path）：注册为可调用工具，执行时通过 {baseDir} 替换
    """
    impl = doc.get("implementation")
    logger.info(
        f"🔧 _register_skill_to_registry: name={doc.get('name')}, "
        f"impl_type={impl.get('type') if isinstance(impl, dict) else None}, "
        f"has_code={bool(impl.get('code')) if isinstance(impl, dict) else False}, "
        f"has_script_path={bool(impl.get('script_path')) if isinstance(impl, dict) else False}, "
        f"has_skill_dir_in_impl={bool(impl.get('skill_dir')) if isinstance(impl, dict) else False}, "
        f"has_skill_dir_in_doc={bool(doc.get('skill_dir'))}"
    )

    # knowledge 类型：不注册为工具，由 Agent 基类注入提示词
    if not impl:
        logger.info(f"📚 Skill '{doc.get('name')}' 是知识型，不注册为可调用工具（将通过提示词注入）")
        return

    try:
        # 过滤掉 SkillMetadata 不识别的扩展字段（如 skill_dir, has_scripts, source_type）
        _META_KNOWN_FIELDS = {
            "name", "description", "allowed_tools", "version", "author", "category",
            "tags", "icon", "color", "when_to_use", "parameters", "returns", "examples",
            "implementation", "instructions", "enabled", "fc_enabled", "is_builtin",
            "source_file", "created_at", "updated_at",
        }
        skill_kwargs = {k: v for k, v in doc.items() if k != "_id" and k in _META_KNOWN_FIELDS}
        skill = SkillMetadata(**skill_kwargs)

        # 如果提供了 code，使用沙箱包装器
        if impl.get("code"):
            from core.tools.external_skill_loader import register_single_external_skill
            from core.tools.fc_converter import sanitize_function_name
            tool_id = sanitize_function_name(skill.name.replace("-", "_"))
            register_single_external_skill(
                None,
                get_tool_registry(),
                {
                    **doc,
                    "tool_id": tool_id,
                    "code": impl.get("code"),
                    "display_name": skill.description[:50] if skill.description else skill.name,
                    "parameters": doc.get("parameters", []),
                },
            )
        else:
            registry = get_tool_registry()
            from core.tools.fc_converter import sanitize_function_name
            tool_id = sanitize_function_name(skill.name.replace("-", "_"))

            # ⚠️ 命名冲突检查：Skill name → tool_id 不能与 impl.function 同名
            #    否则 ToolRegistry 中的 wrapper 会与原始函数 key 冲突，
            #    导致 SkillExecutor 调用时形成死循环。
            impl_type_str = impl.get("type") if isinstance(impl, dict) else getattr(impl, "type", None)
            impl_func = impl.get("function") if isinstance(impl, dict) else getattr(impl, "function", None)
            if impl_type_str == "python" and impl_func and impl_func == tool_id:
                suggested_name = f"{doc.get('name', 'unnamed')}-tool"
                logger.warning(
                    f"⚠️ Skill 命名冲突: tool_id '{tool_id}' 与 impl.function '{impl_func}' 同名！"
                    f" 这会导致执行时的无限递归。建议将 Skill name 改为 '{suggested_name}' 以避免冲突。"
                )
                logger.warning(
                    f"   冲突 Skill: name={doc.get('name')}, function={impl_func}, module={impl.get('module')}"
                )

            # 兼容：如果 impl 里没有 skill_dir，从 doc 顶层补
            if isinstance(impl, dict) and impl.get("script_path") and not impl.get("skill_dir"):
                if doc.get("skill_dir"):
                    impl["skill_dir"] = doc["skill_dir"]
                    logger.info(f"   → 自动从 doc.skill_dir 补全 impl.skill_dir: {doc['skill_dir']}")

            if isinstance(impl, dict) and impl.get("script_path") and (impl.get("skill_dir") or doc.get("skill_dir")):
                wrapper = _create_script_skill_wrapper(doc)
                logger.info(f"   → 使用脚本型 Skill 包装器（execute_cli 模式）")
            else:
                wrapper = SkillExecutor.create_sync_wrapper(skill)
                logger.info(f"   → 使用通用 SkillExecutor 同步包装器")

            # 🔥 category 必须是 ToolCategory 枚举值，否则映射到 external
            from core.tools.config import ToolCategory
            valid_categories = {c.value for c in ToolCategory}
            raw_category = doc.get("category", "external")
            if raw_category not in valid_categories:
                logger.info(f"   → category '{raw_category}' 不在枚举范围，映射到 'external'")
                raw_category = "external"

            registry.register_function(
                tool_id=tool_id,
                func=wrapper,
                name=skill.description[:50] if skill.description else skill.name,
                category=raw_category,
                description=skill.description,
                is_online=True,
                override=True,
            )
        logger.info(f"✅ Skill '{skill.name}' 已注册到 ToolRegistry (tool_id={tool_id}, type={impl.get('type', 'unknown')})")
    except Exception as e:
        logger.warning(f"⚠️ Skill 注册到 ToolRegistry 失败: {e}", exc_info=True)


async def _sync_capability_index(db: AsyncIOMotorDatabase):
    try:
        await CapabilityIndexService(db).ensure_index()
    except Exception as e:
        logger.warning(f"⚠️ CapabilityIndex 同步失败: {e}")


# =============================================================================
# API 端点
# =============================================================================

@router.get("", response_model=List[SkillResponse])
async def list_skills(
    category: Optional[str] = Query(None, description="按分类筛选"),
    enabled: Optional[bool] = Query(None, description="按启用状态筛选"),
    skill_type: Optional[str] = Query(None, description="按类型筛选: knowledge, python, http, mcp"),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取所有 Skill 列表"""
    query = {}
    if category:
        query["category"] = category
    if enabled is not None:
        query["enabled"] = enabled

    skills = []
    async for doc in db[COLLECTION].find(query).sort("created_at", -1):
        resp = _doc_to_response(doc)
        if skill_type:
            if resp.skill_type != skill_type:
                continue
        skills.append(resp)
    return skills


@router.get("/categories")
async def list_skill_categories(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取所有 Skill 分类"""
    pipeline = [
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    categories = []
    async for doc in db[COLLECTION].aggregate(pipeline):
        categories.append({"id": doc["_id"], "name": doc["_id"], "count": doc["count"]})
    return categories


@router.post("", response_model=SkillResponse)
async def create_skill(
    req: SkillCreateRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """创建新 Skill"""
    # 检查是否已存在
    existing = await db[COLLECTION].find_one({"name": req.name})
    if existing:
        raise HTTPException(status_code=400, detail=f"Skill '{req.name}' 已存在")

    doc = _request_to_doc(req)
    await db[COLLECTION].insert_one(doc)

    # 注册到 ToolRegistry
    await _register_skill_to_registry(doc)
    await _sync_capability_index(db)

    doc.pop("_id", None)
    return _doc_to_response(doc)


@router.post("/import", response_model=SkillResponse)
async def import_skill(
    req: SkillImportRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """从 SKILL.md 内容导入 Skill"""
    try:
        skill = SkillParser.parse_content(req.content)
    except (ValueError, Exception) as e:
        raise HTTPException(status_code=400, detail=f"SKILL.md 解析失败: {e}")

    # 检查是否已存在
    existing = await db[COLLECTION].find_one({"name": skill.name})
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Skill '{skill.name}' 已存在，请使用更新接口",
        )

    doc = _skill_to_doc(skill)
    await db[COLLECTION].insert_one(doc)

    # 注册到 ToolRegistry
    await _register_skill_to_registry(doc)
    await _sync_capability_index(db)

    doc.pop("_id", None)
    return _doc_to_response(doc)


@router.post("/import-file", response_model=SkillResponse)
async def import_skill_file(
    file: UploadFile = File(..., description="SKILL.md 文件"),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """上传并导入 SKILL.md 文件"""
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件编码必须为 UTF-8")

    try:
        skill = SkillParser.parse_content(text)
    except (ValueError, Exception) as e:
        raise HTTPException(status_code=400, detail=f"SKILL.md 解析失败: {e}")

    existing = await db[COLLECTION].find_one({"name": skill.name})
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Skill '{skill.name}' 已存在，请使用更新接口",
        )

    doc = _skill_to_doc(skill)
    doc["source_file"] = file.filename
    await db[COLLECTION].insert_one(doc)

    await _register_skill_to_registry(doc)
    await _sync_capability_index(db)

    doc.pop("_id", None)
    return _doc_to_response(doc)


# =============================================================================
# 测试响应模型（被多个导入端点共用，需提前定义）
# =============================================================================

class SkillTestResponse(BaseModel):
    """测试 Skill 响应"""
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time_ms: int = 0


class ImportWithTestResponse(BaseModel):
    """导入并测试响应"""
    skill: SkillResponse
    test_result: Optional[SkillTestResponse] = None
    message: str


# =============================================================================
# 腾讯 SkillHub 对接（skillhub.cloud.tencent.com）
# =============================================================================

class SkillHubSkillResponse(BaseModel):
    """SkillHub 技能响应"""
    skill_id: str = Field(..., description="技能 ID，如 tencent-docs")
    display_name: str = Field("", description="显示名称")
    description: str = Field("", description="描述")
    category: str = Field("", description="分类")
    author: str = Field("", description="作者/来源")
    downloads: str = Field("", description="下载量，如 1569.1 万")
    version: str = Field("", description="版本号")
    needs_api_key: bool = Field(False, description="是否需要 API Key")
    ai_score: str = Field("", description="AI 评分")
    url: str = Field("", description="SkillHub 详情页 URL")
    install_command: str = Field("", description="安装命令")


class SkillHubListResponse(BaseModel):
    """SkillHub 列表响应"""
    total: str = Field("7.1 万", description="总数量描述")
    skills: List[SkillHubSkillResponse] = []
    featured: List[SkillHubSkillResponse] = Field(default_factory=list, description="精选推荐")


# SkillHub 精选技能（从网站爬取的热门技能，定期更新）
SKILLHUB_FEATURED = [
    SkillHubSkillResponse(
        skill_id="web-tools-guide",
        display_name="Web Tools Guide",
        description="搜索/上网/查资料必备前置技能，包含 web_search、web_fetch、browser 等工具的错误处理流程",
        category="知识管理",
        author="SkillHub",
        downloads="6215.8 万",
        version="latest",
        needs_api_key=False,
        ai_score="4.7",
        url="https://skillhub.cloud.tencent.com/skills/web-tools-guide",
        install_command="skillhub install web-tools-guide",
    ),
    SkillHubSkillResponse(
        skill_id="tencent-docs",
        display_name="腾讯文档 TENCENT DOCS",
        description="在线云文档平台，创建/编辑/管理文档的首选 Skill，支持文档/Excel/PPT/思维导图等",
        category="办公效率",
        author="腾讯文档团队",
        downloads="1569.1 万",
        version="v1.0.37",
        needs_api_key=True,
        ai_score="4.7",
        url="https://skillhub.cloud.tencent.com/skills/tencent-docs",
        install_command="skillhub install tencent-docs",
    ),
    SkillHubSkillResponse(
        skill_id="self-improving-agent",
        display_name="Self-Improving Agent",
        description="捕获经验教训、错误及修正内容，实现持续改进。适用于操作失败、用户纠正、发现更优方法等场景",
        category="Agent 增强",
        author="SkillHub",
        downloads="81.3 万",
        version="latest",
        needs_api_key=False,
        ai_score="4.1",
        url="https://skillhub.cloud.tencent.com/skills/self-improving-agent",
        install_command="skillhub install self-improving-agent",
    ),
    SkillHubSkillResponse(
        skill_id="skill-vetter",
        display_name="Skill Vetter",
        description="AI 智能体技能安全预审工具，安装 ClawdHub、GitHub 等来源技能前检查风险信号、权限范围及可疑模式",
        category="安全",
        author="SkillHub",
        downloads="26.8 万",
        version="latest",
        needs_api_key=False,
        ai_score="4.5",
        url="https://skillhub.cloud.tencent.com/skills/skill-vetter",
        install_command="skillhub install skill-vetter",
    ),
    SkillHubSkillResponse(
        skill_id="customer-hunter",
        display_name="Customer Hunter",
        description="腾讯云销售获客 Skill，从企查查/百度百科/BOSS 直聘挖掘目标客户，三维评分生成 HTML 报告",
        category="销售获客",
        author="SkillHub",
        downloads="470",
        version="v1.0.15",
        needs_api_key=True,
        ai_score="4.7",
        url="https://skillhub.cloud.tencent.com/skills/customer-hunter",
        install_command="skillhub install customer-hunter",
    ),
    SkillHubSkillResponse(
        skill_id="wxa-skills-generate",
        display_name="微信小程序 AI 开发模式生成",
        description="基于原有业务代码生成原子接口与原子组件，支持 CodeBuddy、Claude Code 等 Coding Agent",
        category="微信小程序",
        author="微信小程序团队",
        downloads="",
        version="latest",
        needs_api_key=False,
        ai_score="",
        url="https://skillhub.cloud.tencent.com/skills/wxa-skills-generate",
        install_command="skillhub install wxa-skills-generate",
    ),
    SkillHubSkillResponse(
        skill_id="agently-mail",
        display_name="Agently Mail",
        description="QQ 邮箱团队为 Agent 打造的专属邮箱服务，支持微信登录授权、收发邮件、搜索、附件管理等",
        category="办公效率",
        author="QQ 邮箱团队",
        downloads="",
        version="latest",
        needs_api_key=True,
        ai_score="",
        url="https://skillhub.cloud.tencent.com/skills/agently-mail",
        install_command="skillhub install agently-mail",
    ),
    SkillHubSkillResponse(
        skill_id="tcop-api",
        display_name="腾讯云可观测平台",
        description="用自然语言驱动腾讯云可观测平台全部 API 能力，无需翻文档、无需手拼参数",
        category="运维监控",
        author="腾讯云可观测团队",
        downloads="",
        version="latest",
        needs_api_key=True,
        ai_score="",
        url="https://skillhub.cloud.tencent.com/skills/tcop-api",
        install_command="skillhub install tcop-api",
    ),
]


@router.get("/skillhub/skills", response_model=SkillHubListResponse)
async def list_skillhub_skills(
    keyword: str = Query("", description="搜索关键词"),
):
    """浏览腾讯 SkillHub (skillhub.cloud.tencent.com) 上的技能"""
    if keyword:
        # 关键词搜索：在精选列表中过滤
        kw = keyword.lower()
        filtered = [
            s for s in SKILLHUB_FEATURED
            if kw in s.display_name.lower() or kw in s.description.lower() or kw in s.category.lower()
        ]
        return SkillHubListResponse(
            total=f"{len(filtered)} 个匹配",
            skills=filtered,
            featured=SKILLHUB_FEATURED[:4],
        )

    return SkillHubListResponse(
        total="7.1 万",
        skills=SKILLHUB_FEATURED,
        featured=SKILLHUB_FEATURED[:4],
    )


class ImportFromSkillHubRequest(BaseModel):
    """从 SkillHub 导入请求"""
    skill_id: str = Field(..., description="SkillHub 技能 ID，如 tencent-docs")
    test_args: Optional[Dict[str, Any]] = Field(default=None, description="测试参数")


@router.post("/import-skillhub", response_model=ImportWithTestResponse)
async def import_from_skillhub(
    req: ImportFromSkillHubRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """从腾讯 SkillHub 导入 Skill（获取 SKILL.md 并解析注册）"""
    try:
        skill_content = ""

        # 尝试从 SkillHub 网站获取 SKILL.md
        skillhub_url = f"https://skillhub.cloud.tencent.com/skills/{req.skill_id}"
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(skillhub_url)
                if resp.status_code == 200:
                    # 从 HTML 中提取 SKILL.md 内容
                    text = resp.text
                    # 尝试查找页面中的 SKILL.md 内容块
                    import re
                    # 查找 <pre> 或 code 块中的内容
                    skill_md_match = re.search(r'<pre[^>]*class="[^"]*skill[^"]*"[^>]*>(.*?)</pre>', text, re.DOTALL)
                    if skill_md_match:
                        from html import unescape
                        skill_content = unescape(skill_md_match.group(1).strip())
        except Exception as e:
            logger.warning(f"从 SkillHub 网站获取内容失败: {e}")

        # 如果无法从网站获取，生成基础 SKILL.md
        if not skill_content:
            # 从精选列表中查找技能信息
            skill_info = next((s for s in SKILLHUB_FEATURED if s.skill_id == req.skill_id), None)
            if not skill_info:
                skill_info = SkillHubSkillResponse(
                    skill_id=req.skill_id,
                    display_name=req.skill_id,
                    description=f"从 SkillHub 导入的技能: {req.skill_id}",
                )

            skill_content = f"""---
name: {req.skill_id}
version: "1.0.0"
description: {skill_info.description}
author: {skill_info.author or "SkillHub"}
category: {skill_info.category or "imported"}
tags: [skillhub, {skill_info.category.lower() if skill_info.category else "imported"}]
parameters: []
implementation:
  type: python
  code: |
    import json, sys
    args = json.loads(sys.stdin.read()) if sys.stdin else {{}}
    print("__SANDBOX_OUTPUT_START__")
    print(json.dumps({{"info": "Skill imported from SkillHub", "skill_id": "{req.skill_id}", "name": "{skill_info.display_name}"}}, ensure_ascii=False))
    print("__SANDBOX_OUTPUT_END__")
when_to_use: |
  当用户提到 {skill_info.display_name} 或 {req.skill_id} 相关功能时触发此 Skill。
---

{skill_info.description}

安装命令: {skill_info.install_command}
详情: {skill_info.url}
"""

        # 解析并导入
        skill = SkillParser.parse_content(skill_content)
        doc = _skill_to_doc(skill)
        doc["source_type"] = "skillhub"
        doc["source_url"] = f"https://skillhub.cloud.tencent.com/skills/{req.skill_id}"

        existing = await db[COLLECTION].find_one({"name": doc["name"]})
        if existing:
            await db[COLLECTION].update_one({"name": doc["name"]}, {"$set": doc})
            doc["_id"] = existing["_id"]
        else:
            await db[COLLECTION].insert_one(doc)

        await _register_skill_to_registry(doc)
        await _sync_capability_index(db)

        # 测试
        test_result = None
        if req.test_args:
            impl = doc.get("implementation", {})
            if impl.get("type") == "python" and impl.get("code"):
                sandbox_result = _execute_python_sandbox(impl["code"], req.test_args, 30)
                test_result = SkillTestResponse(
                    success=sandbox_result["success"],
                    result=sandbox_result.get("result"),
                    error=sandbox_result.get("error"),
                    execution_time_ms=sandbox_result.get("execution_time_ms", 0),
                )

        skill_resp = _doc_to_response(doc)
        return ImportWithTestResponse(
            skill=skill_resp,
            test_result=test_result,
            message=f"已从 SkillHub 导入 Skill: {skill_resp.name}",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"从 SkillHub 导入失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


# =============================================================================
# 测试和平台对接接口
# =============================================================================

class SkillTestRequest(BaseModel):
    """测试 Skill 请求"""
    skill_name: str
    args: Dict[str, Any] = Field(default_factory=dict, description="测试参数（直接传给脚本）")
    question: str = Field(default="", description="自然语言测试问题，由 LLM 自动转换为脚本参数")
    timeout: int = Field(default=30, description="超时时间（秒）")


def _execute_python_sandbox(code: str, args: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    """在沙箱中执行 Python 代码"""
    import subprocess
    import tempfile
    import json
    from pathlib import Path

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        temp_path = f.name

    try:
        # 准备输入参数
        input_data = json.dumps(args, ensure_ascii=False)

        # 执行代码
        proc = subprocess.run(
            ["python", temp_path],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(Path(__file__).parent.parent.parent),
        )

        if proc.returncode != 0:
            return {"success": False, "error": proc.stderr or "执行失败", "execution_time_ms": 0}

        # 解析输出
        stdout = proc.stdout.strip()
        if "__SANDBOX_OUTPUT_START__" in stdout:
            start = stdout.index("__SANDBOX_OUTPUT_START__") + len("__SANDBOX_OUTPUT_START__")
            end = stdout.index("__SANDBOX_OUTPUT_END__")
            result_str = stdout[start:end].strip()
            try:
                result = json.loads(result_str)
            except:
                result = result_str
            return {"success": True, "result": result, "execution_time_ms": 0}
        else:
            return {"success": True, "result": {"stdout": stdout}, "execution_time_ms": 0}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"执行超时（{timeout}s）", "execution_time_ms": timeout * 1000}
    except Exception as e:
        return {"success": False, "error": str(e), "execution_time_ms": 0}
    finally:
        Path(temp_path).unlink(missing_ok=True)


@router.post("/test", response_model=SkillTestResponse)
async def test_skill(
    req: SkillTestRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """测试 Skill（区分 knowledge 和 executable 类型）"""
    try:
        # 尝试从 skills 集合获取
        doc = await db[COLLECTION].find_one({"name": req.skill_name})
        if doc:
            return await _test_skill_doc(doc, req, db)

        # 尝试从 external_skills 获取
        ext_doc = await db["external_skills"].find_one({"tool_id": req.skill_name})
        if ext_doc:
            code = ext_doc.get("code", "")
            if code:
                # 检测是否是占位代码（只有 info 字段）
                is_placeholder = _is_placeholder_code(code)
                if is_placeholder:
                    return SkillTestResponse(
                        success=False,
                        error="此 Skill 为知识型（knowledge），仅有文档描述，无可执行代码。"
                              "它通过 ToolRegistry 为 Agent 提供上下文信息，不需要独立执行测试。",
                        result={
                            "skill_type": "knowledge",
                            "name": ext_doc.get("display_name") or ext_doc.get("tool_id"),
                            "description": ext_doc.get("description", ""),
                            "registered_in_registry": _check_tool_registry(ext_doc.get("tool_id", "")),
                        },
                        execution_time_ms=0
                    )

                # 确定测试参数：优先级 question(LLM转参) > args > test_input > 空
                test_args = dict(req.args) if req.args else {}
                llm_conversion_note = None

                if req.question:
                    # 有自然语言问题：先走 LLM 转参
                    conversion = await _convert_question_to_args_for_external_skill(ext_doc, req.question)
                    if conversion.get("success"):
                        test_args = conversion.get("args", {})
                        llm_conversion_note = conversion.get("note", "")
                        logger.info(
                            f"💬 external_skill 测试: question='{req.question[:50]}...' → args={test_args}"
                        )
                    else:
                        # LLM 转换失败，用 test_input 兜底
                        fallback_input = ext_doc.get("test_input") or {}
                        if fallback_input:
                            test_args = fallback_input
                            llm_conversion_note = f"LLM 转换失败，使用 test_input 兜底: {conversion.get('error', '')}"
                            logger.warning(
                                f"⚠️ external_skill 测试 LLM 转参失败，使用 test_input 兜底: {conversion.get('error')}"
                            )
                elif not test_args:
                    # 既没有问题也没有 args，自动用 test_input 测试
                    fallback_input = ext_doc.get("test_input") or {}
                    if fallback_input:
                        test_args = fallback_input
                        llm_conversion_note = "自动使用 test_input 作为测试参数"
                        logger.info(f"🔄 external_skill 测试: 无问题/参数，自动使用 test_input={test_args}")

                # 使用 SandboxRunner 执行（正确处理纯函数代码）
                result = _run_external_skill_sandbox(code, ext_doc, test_args, req.timeout)
                resp_result = result.get("result")
                if isinstance(resp_result, dict) and llm_conversion_note:
                    resp_result = dict(resp_result)
                    resp_result["_llm_conversion_note"] = llm_conversion_note
                    resp_result["_test_args"] = test_args
                return SkillTestResponse(
                    success=result["success"],
                    result=resp_result,
                    error=result.get("error"),
                    execution_time_ms=result.get("execution_time_ms", 0)
                )
            else:
                return SkillTestResponse(
                    success=False,
                    error="该 Skill 没有可执行代码",
                    result={"skill_type": "unknown"}
                )

        raise HTTPException(status_code=404, detail=f"Skill '{req.skill_name}' 不存在")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"测试 Skill 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"测试失败: {str(e)}")


def _is_placeholder_code(code: str) -> bool:
    """检测是否是占位代码（只返回 info 元数据）"""
    import re
    # 匹配模式: print(json.dumps({"info": "Skill imported from...
    placeholder_patterns = [
        r'"info".*?"Skill imported',
        r'"info".*?"Skill imported from SkillHub"',
        r'__SANDBOX_OUTPUT',
    ]
    for pattern in placeholder_patterns:
        if re.search(pattern, code):
            return True
    return False


def _run_external_skill_sandbox(
    code: str,
    ext_doc: Dict[str, Any],
    test_args: Dict[str, Any],
    timeout: int,
) -> Dict[str, Any]:
    """用 SandboxRunner 执行 external_skill 的纯函数代码。

    _execute_python_sandbox 是通过 stdin 传参的，不适用于纯函数代码。
    SandboxRunner 会自动包装一层 main 入口来调用函数。

    Args:
        code: Skill 的 Python 函数代码
        ext_doc: external_skills 文档（用于取 tool_id）
        test_args: 测试参数字典
        timeout: 超时秒数

    Returns:
        {"success": bool, "result": Any, "error": str, "execution_time_ms": int}
    """
    try:
        from core.tools.external.sandbox_runner import SandboxRunner
        from core.tools.external.skill_spec import SkillSpec

        # 构造最小化的 SkillSpec（只需要 tool_id 和 test_input）
        tool_id = ext_doc.get("tool_id", "")
        spec = SkillSpec(
            tool_id=tool_id,
            display_name=ext_doc.get("display_name", tool_id),
            description=ext_doc.get("description", ""),
            category=ext_doc.get("category", "utility"),
            test_input=test_args,
        )

        runner = SandboxRunner(timeout=timeout)
        sandbox_result = runner.run(code, spec, test_input=test_args)

        # 把子进程的 stdout/stderr 打到 webapi 日志，方便排查数据源选择等问题
        if sandbox_result.stdout:
            for line in sandbox_result.stdout.split("\n"):
                line = line.strip()
                if line:
                    logger.info(f"📦 [沙箱stdout] {line}")
        if sandbox_result.stderr:
            for line in sandbox_result.stderr.split("\n"):
                line = line.strip()
                if line:
                    logger.warning(f"📦 [沙箱stderr] {line}")

        return {
            "success": sandbox_result.success,
            "result": sandbox_result.output,
            "error": sandbox_result.error,
            "execution_time_ms": int((sandbox_result.execution_time or 0) * 1000),
        }
    except Exception as e:
        logger.error(f"external_skill 沙箱执行异常: {e}", exc_info=True)
        return {"success": False, "result": None, "error": str(e), "execution_time_ms": 0}


async def _convert_question_to_args_for_external_skill(
    ext_doc: Dict[str, Any],
    question: str,
) -> Dict[str, Any]:
    """用 LLM 把自然语言问题转换为 external_skill 的函数参数。

    Args:
        ext_doc: external_skills 集合中的文档，含 parameters、description、display_name 等
        question: 用户的自然语言测试问题

    Returns:
        {"success": True, "args": {...}, "note": "..."} 或 {"success": False, "error": "..."}
    """
    import os
    import json as _json

    parameters = ext_doc.get("parameters") or []
    display_name = ext_doc.get("display_name") or ext_doc.get("tool_id", "")
    description = ext_doc.get("description") or ""
    test_input = ext_doc.get("test_input") or {}

    if not parameters:
        # 没有参数定义，直接返回空参数
        return {"success": True, "args": {}, "note": "无参数定义"}

    try:
        from core.llm.unified_client import UnifiedLLMClient
        from core.llm.models import Message
    except Exception as e:
        return {"success": False, "error": f"无法导入 LLM 客户端: {e}"}

    llm_client = None
    last_err = None
    for provider, env_key in [
        ("dashscope", "DASHSCOPE_API_KEY"),
        ("deepseek", "DEEPSEEK_API_KEY"),
    ]:
        if not os.getenv(env_key):
            continue
        try:
            llm_client = UnifiedLLMClient.from_provider(provider)
            break
        except Exception as e:
            last_err = e
            continue

    if llm_client is None:
        return {"success": False, "error": f"找不到可用的 LLM 配置: {last_err}"}

    # 构造参数定义的 JSON 描述
    param_schema = []
    for p in parameters:
        param_schema.append({
            "name": p.get("name", ""),
            "type": p.get("param_type") or p.get("type", "string"),
            "required": p.get("required", False),
            "default": p.get("default"),
            "description": p.get("description", ""),
        })

    system_prompt = f"""你是一个参数提取助手。你的任务是从用户的自然语言问题中，提取出调用 Skill 函数所需的参数。

## Skill 信息
- 名称: {display_name}
- 描述: {description[:500]}

## 函数参数定义
```json
{_json.dumps(param_schema, ensure_ascii=False, indent=2)}
```

## 参考测试输入（参数格式参考）
```json
{_json.dumps(test_input, ensure_ascii=False, indent=2)}
```

## 任务
从用户问题中提取参数值，输出严格的 JSON 格式：
```json
{{
  "args": {{
    "param1": "value1",
    "param2": 123
  }}
}}
```

## 规则
1. 只输出 JSON，不要输出任何其他文字、解释、markdown 代码块
2. 用户问题中没提到的参数，如果有默认值可以不填；如果是必填参数但问题里没给，就用参考测试输入中的值或合理默认值
3. 股票代码为 6 位纯数字（如 000002、600519），不要带 .SH/.SZ 后缀
4. 数字类型的参数必须是数字，不要加引号"""

    try:
        response = llm_client.chat(
            [
                Message(role="system", content=system_prompt),
                Message(role="user", content=f"用户问题：{question}\n\n请提取参数。"),
            ],
            max_tokens=512,
        )
        # 记录 token 使用
        try:
            from app.services.usage_statistics_service import usage_statistics_service
            await usage_statistics_service.record_llm_usage(
                response=response,
                session_id="skill_test",
                analysis_type="skill_test",
            )
        except Exception as e:
            logger.warning(f"记录 token 使用失败: {e}")
        raw = (response.content or "").strip()

        # 尝试从可能的 markdown 代码块中提取 JSON
        if "```" in raw:
            import re as _re
            m = _re.search(r"```(?:json)?\s*\n(.*?)\n```", raw, _re.DOTALL)
            if m:
                raw = m.group(1).strip()

        # 去掉可能的前缀/后缀
        raw = raw.strip()
        if raw.startswith("```json"):
            raw = raw[7:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        parsed = _json.loads(raw)
        args = parsed.get("args", {}) if isinstance(parsed, dict) else {}

        # 类型校正：根据参数定义把值转成正确类型
        for p in parameters:
            name = p.get("name", "")
            ptype = (p.get("param_type") or p.get("type", "")).lower()
            if name in args:
                try:
                    if ptype in ("int", "integer", "number"):
                        args[name] = int(args[name])
                    elif ptype in ("float", "double"):
                        args[name] = float(args[name])
                    elif ptype == "boolean":
                        if isinstance(args[name], str):
                            args[name] = args[name].lower() in ("true", "1", "yes")
                except (ValueError, TypeError):
                    pass

        return {
            "success": True,
            "args": args,
            "note": f"LLM 提取自问题: {question[:60]}",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _check_tool_registry(tool_id: str) -> bool:
    """检查工具是否已注册到 ToolRegistry"""
    try:
        registry = get_tool_registry()
        tool = registry.get_tool(tool_id.replace("-", "_"))
        return tool is not None
    except Exception:
        return False


def _collect_script_help_info(doc: Dict[str, Any]) -> str:
    """扫描 Skill 包内所有 .py 脚本，运行 --help 拿到参数说明

    返回拼接好的字符串，供 LLM 在系统提示词里参考。
    """
    import subprocess as _sp

    impl = doc.get("implementation") or {}
    skill_dir = impl.get("skill_dir") or doc.get("skill_dir")
    if not skill_dir:
        return "（无脚本目录信息）"

    skill_path = Path(skill_dir)
    if not skill_path.exists():
        return f"（脚本目录不存在: {skill_dir}）"

    # 找所有 .py 脚本（scripts/ 优先，否则根目录）
    scripts_dir = skill_path / "scripts"
    candidates = []
    if scripts_dir.is_dir():
        candidates = sorted([p for p in scripts_dir.iterdir() if p.is_file() and p.suffix == ".py"])
    else:
        candidates = sorted([p for p in skill_path.iterdir()
                             if p.is_file() and p.suffix == ".py" and p.name != "__init__.py"])

    if not candidates:
        return "（未找到可执行脚本）"

    sections = []
    for script in candidates[:8]:  # 最多取 8 个，避免提示词过长
        rel_path = script.relative_to(skill_path)
        try:
            proc = _sp.run(
                ["python", str(script), "--help"],
                cwd=str(skill_path),
                capture_output=True,
                text=True,
                timeout=10,
                encoding="utf-8",
                errors="replace",
            )
            help_text = (proc.stdout or proc.stderr or "").strip()
            if help_text:
                # 截断单个脚本的 help 输出避免过长
                if len(help_text) > 800:
                    help_text = help_text[:800] + "\n... (已截断)"
                sections.append(f"### `{rel_path}`\n```\n{help_text}\n```")
            else:
                sections.append(f"### `{rel_path}`\n（无 --help 输出，可能是无参脚本，直接执行即可）")
        except Exception as e:
            sections.append(f"### `{rel_path}`\n（获取 --help 失败: {e}）")

    return "\n\n".join(sections) if sections else "（无脚本帮助信息）"


async def _test_skill_via_agent(
    doc: Dict[str, Any],
    question: str,
    timeout: int,
    db: AsyncIOMotorDatabase,
) -> Dict[str, Any]:
    """通过 LLM Function Calling 测试 Skill

    与项目实际 Agent 调用 Skill 使用相同的技术栈：
    1. 从 ToolRegistry 获取已注册的 Skill 工具（含凭证注入逻辑）
    2. 用 UnifiedLLMClient 创建 LLM 客户端
    3. 注册 Skill 为可调用工具
    4. 把 SKILL.md 的 description + instructions 作为系统提示词
    5. 让 LLM 自主调用工具
    6. 返回完整的执行轨迹（LLM 推理 + 工具调用 + 工具结果）

    Args:
        doc: MongoDB 中的 Skill 文档
        question: 用户测试问题（自然语言）
        timeout: 超时秒数
        db: MongoDB 数据库

    Returns:
        {success, result, error, execution_time_ms, tool_calls, final_answer}
    """
    import time as _time
    start = _time.time()

    skill_name = doc.get("name", "")
    tool_id = skill_name.replace("-", "_")

    # 1. 从 ToolRegistry 获取已注册工具，如果没有则即时注册（lazy 注册）
    try:
        registry = get_tool_registry()
        tool_func = registry.get_function(tool_id)
        if tool_func is None:
            logger.info(f"🔁 Skill '{skill_name}' 未在 ToolRegistry，尝试即时注册...")
            try:
                await _register_skill_to_registry(doc)
                tool_func = registry.get_function(tool_id)
            except Exception as reg_err:
                return {
                    "success": False,
                    "error": f"即时注册 Skill 失败: {reg_err}",
                    "execution_time_ms": int((_time.time() - start) * 1000),
                }
        tool_metadata = registry.get_tool(tool_id)
    except Exception as e:
        return {
            "success": False,
            "error": f"获取工具失败: {e}",
            "execution_time_ms": int((_time.time() - start) * 1000),
        }

    if tool_func is None:
        # 如果还是没注册成功，给出明确诊断
        impl = doc.get("implementation") or {}
        diag = {
            "has_implementation": bool(impl),
            "impl_type": impl.get("type") if isinstance(impl, dict) else None,
            "has_script_path": bool(impl.get("script_path") if isinstance(impl, dict) else None),
            "has_skill_dir": bool((impl.get("skill_dir") if isinstance(impl, dict) else None) or doc.get("skill_dir")),
        }
        return {
            "success": False,
            "error": (
                f"Skill '{skill_name}' (tool_id={tool_id}) 未注册到 ToolRegistry，"
                f"即时注册也失败。诊断信息: {diag}。"
                f"请确认该 Skill 的 implementation.script_path 和 skill_dir 已正确写入数据库。"
            ),
            "execution_time_ms": int((_time.time() - start) * 1000),
        }

    # 2. 创建 LLM 客户端（按系统配置）
    try:
        import os
        from core.llm.unified_client import UnifiedLLMClient
        from core.llm.models import Message

        llm_client = None
        last_err = None
        for provider, env_key in [
            ("dashscope", "DASHSCOPE_API_KEY"),
            ("deepseek", "DEEPSEEK_API_KEY"),
        ]:
            if not os.getenv(env_key):
                continue
            try:
                llm_client = UnifiedLLMClient.from_provider(provider)
                logger.info(f"💡 测试 Skill 使用 LLM provider={provider}")
                break
            except Exception as e:
                last_err = e
                continue

        if llm_client is None:
            return {
                "success": False,
                "error": f"找不到可用的 LLM 配置（已尝试 DASHSCOPE/DEEPSEEK）: {last_err}",
                "execution_time_ms": int((_time.time() - start) * 1000),
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"初始化 LLM 客户端失败: {e}",
            "execution_time_ms": int((_time.time() - start) * 1000),
        }

    # 3. 注册 Skill 为 LLM 工具
    try:
        tool_def = llm_client.register_tool(
            tool_func,
            name=tool_id,
            description=doc.get("description") or skill_name,
        )
    except Exception as e:
        return {
            "success": False,
            "error": f"注册 Skill 工具失败: {e}",
            "execution_time_ms": int((_time.time() - start) * 1000),
        }

    # 4. 构造提示词：把 SKILL.md instructions 作为系统提示词
    instructions = doc.get("instructions") or ""
    description = doc.get("description") or ""
    when_to_use = doc.get("when_to_use") or ""

    # 4.1 扫描脚本目录，获取所有 .py 脚本的 --help 输出，让 LLM 知道每个脚本支持的参数
    script_help_info = _collect_script_help_info(doc)

    system_prompt = f"""你是一个 Skill 测试助手。你的任务是根据用户的问题，调用名为 `{tool_id}` 的工具来获取真实结果。

## Skill 描述
{description}

## 何时使用
{when_to_use}

## Skill 详细说明（来自 SKILL.md）
{instructions[:6000]}

## 脚本命令行参数说明（来自脚本 --help 输出）
{script_help_info}

## 工具调用方式
工具接受三种参数：
- `query` (string): 简单场景，会作为脚本的第一个位置参数
- `cli_args` (string[]): 完整的命令行参数数组，**用于需要 --flag value 形式的复杂脚本**
- `script` (string): 当 Skill 包含**多个脚本**时，指定要调用哪个（如 `"dcf_calculator"` 或 `"valuation_snapshot.py"`）

例如要调用 `dcf_calculator.py --fcf 100 --shares 50 --growth 0.1`，应该传：
```json
{{"script": "dcf_calculator", "cli_args": ["--fcf", "100", "--shares", "50", "--growth", "0.1"]}}
```

## 关键规则
1. **必须调用 `{tool_id}` 工具来回答问题**，不要凭空作答
2. **仔细阅读上面的"脚本命令行参数说明"**，从所有可用脚本中**选择最合适的一个**（用 `script` 参数指定）
3. **优先选择参数最简单/有合理默认值的脚本**做测试（如 `valuation_snapshot`、`watchlist_manager` 等），避免选择需要大量必填参数的（如 `dcf_calculator` 需要 --fcf --shares）
4. **如果脚本需要数字/特定参数，但用户问题里没给出，你应该自己生成合理的测试值**（例如测试 DCF 估值器可以用 fcf=100, shares=50 等典型数字）
5. **不要因为缺少真实数据而拒绝调用**——这是测试，目的是验证工具能否正常执行
6. 拿到工具返回结果后，简明总结关键信息
7. 如果工具失败，明确告知失败原因"""

    user_question = question.strip() or "请用合理的测试参数调用该工具，验证它能正常工作。如果脚本需要 --fcf、--shares 等特定参数，请自己生成测试值。"

    messages = [
        Message(role="system", content=system_prompt),
        Message(role="user", content=user_question),
    ]

    # 5. 让 LLM 自主调用工具
    tool_calls_trace = []
    try:
        response = await llm_client.achat(
            messages=messages,
            tools=[tool_def],
            auto_execute_tools=True,
            max_tool_rounds=3,
            tools_used=tool_calls_trace,
        )
    except Exception as e:
        logger.error(f"❌ LLM 调用失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"LLM 调用失败: {e}",
            "execution_time_ms": int((_time.time() - start) * 1000),
        }

    # 记录 token 使用
    try:
        from app.services.usage_statistics_service import usage_statistics_service
        await usage_statistics_service.record_llm_usage(
            response=response,
            session_id="skill_test",
            analysis_type="skill_test",
        )
    except Exception as e:
        logger.warning(f"记录 token 使用失败: {e}")

    elapsed_ms = int((_time.time() - start) * 1000)

    # 6. 整理结果
    return {
        "success": True,
        "result": {
            "skill_name": skill_name,
            "question": user_question,
            "tool_calls": tool_calls_trace,
            "tool_calls_count": len(tool_calls_trace),
            "final_answer": response.content or "",
            "model": response.model,
            "provider": response.provider,
        },
        "execution_time_ms": elapsed_ms,
    }


async def _test_skill_doc(doc: Dict[str, Any], req: SkillTestRequest, db: AsyncIOMotorDatabase) -> SkillTestResponse:
    """测试 skills 集合中的 Skill 文档"""
    impl = doc.get("implementation", {}) if isinstance(doc.get("implementation"), dict) else {}

    # 判断 Skill 类型
    skill_type = impl.get("type") if impl else "knowledge"
    logger.info(f"🔬 _test_skill_doc: name={doc.get('name')}, skill_type={skill_type}, "
                f"has_script_path={bool(impl.get('script_path'))}, has_code={bool(impl.get('code'))}, "
                f"has_skill_dir={bool(impl.get('skill_dir') or doc.get('skill_dir'))}")

    if skill_type == "python" and impl.get("code"):
        # 内嵌 Python 代码
        code = impl["code"]
        # 检测占位代码
        if _is_placeholder_code(code):
            return SkillTestResponse(
                success=True,
                result={
                    "skill_type": "knowledge",
                    "name": doc.get("display_name") or doc.get("name"),
                    "description": doc.get("description", ""),
                    "registered_in_registry": _check_tool_registry(doc.get("name", "")),
                    "note": "此 Skill 为知识型，提供 Agent 上下文信息，无需独立执行。"
                },
                execution_time_ms=0
            )
        # 真正的可执行代码
        result = _execute_python_sandbox(code, req.args, req.timeout)
        return SkillTestResponse(
            success=result["success"],
            result=result.get("result"),
            error=result.get("error"),
            execution_time_ms=result.get("execution_time_ms", 0)
        )

    # 本地脚本型 Skill：通过 Agent + Function Calling 真实执行
    # 与项目分析流程使用相同的技术栈（LLM + ToolRegistry + UnifiedLLMClient）
    script_path = impl.get("script_path") if isinstance(impl, dict) else None
    skill_dir_val = (impl.get("skill_dir") if isinstance(impl, dict) else None) or doc.get("skill_dir")
    if script_path and skill_dir_val:
        agent_result = await _test_skill_via_agent(
            doc=doc,
            question=req.question or "",
            timeout=req.timeout or 60,
            db=db,
        )
        return SkillTestResponse(
            success=agent_result.get("success", False),
            result=agent_result.get("result"),
            error=agent_result.get("error"),
            execution_time_ms=agent_result.get("execution_time_ms", 0),
        )

    # knowledge 类型或其他类型
    return SkillTestResponse(
        success=True,
        result={
            "skill_type": skill_type,
            "name": doc.get("display_name") or doc.get("name"),
            "description": doc.get("description", ""),
            "category": doc.get("category", ""),
            "parameters_count": len(doc.get("parameters", [])),
            "registered_in_registry": _check_tool_registry(doc.get("name", "")),
            "has_implementation": bool(impl),
            "note": f"此 Skill 为 {skill_type} 类型，{'可执行但当前未配置执行入口' if skill_type == 'python' else '作为知识库/提示词为 Agent 提供支持'}"
        },
        execution_time_ms=0
    )


class GitHubRepoSkill(BaseModel):
    """GitHub 仓库中的 Skill"""
    path: str
    name: str
    url: str
    raw_url: str
    size: int


class GitHubRepoResponse(BaseModel):
    """GitHub 仓库响应"""
    owner: str
    repo: str
    skills: List[GitHubRepoSkill]
    readme: Optional[str] = None


@router.get("/github/repo/{owner}/{repo}", response_model=GitHubRepoResponse)
async def list_github_repo_skills(owner: str, repo: str):
    """列出 GitHub 仓库中的 Skill 文件"""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 获取仓库内容列表
            api_url = f"https://api.github.com/repos/{owner}/{repo}/contents"
            resp = await client.get(api_url)
            resp.raise_for_status()
            contents = resp.json()

            skills = []
            readme = None

            for item in contents:
                if item["type"] == "file":
                    name = item["name"]
                    # 查找 SKILL.md 或 *.skill.md 文件
                    if name == "SKILL.md" or name.endswith(".skill.md"):
                        skills.append(GitHubRepoSkill(
                            path=item["path"],
                            name=name.replace(".md", ""),
                            url=item["html_url"],
                            raw_url=item["download_url"],
                            size=item["size"]
                        ))
                    elif name.lower() == "readme.md":
                        # 获取 README
                        readme_resp = await client.get(item["download_url"])
                        if readme_resp.status_code == 200:
                            readme = readme_resp.text

        return GitHubRepoResponse(
            owner=owner,
            repo=repo,
            skills=skills,
            readme=readme
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"仓库 {owner}/{repo} 不存在")
        raise HTTPException(status_code=400, detail=f"GitHub API 错误: {e.response.status_code}")
    except Exception as e:
        logger.error(f"获取 GitHub 仓库失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取仓库失败: {str(e)}")


class ImportFromGitHubRequest(BaseModel):
    """从 GitHub 导入请求"""
    owner: str
    repo: str
    path: str
    test_args: Dict[str, Any] = Field(default_factory=dict, description="测试参数")


@router.post("/import-github", response_model=ImportWithTestResponse)
async def import_skill_from_github(
    req: ImportFromGitHubRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """从 GitHub 仓库导入 Skill 并测试"""
    try:
        # 获取 raw 内容
        raw_url = f"https://raw.githubusercontent.com/{req.owner}/{req.repo}/main/{req.path}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(raw_url)
            if resp.status_code == 404:
                # 尝试 master 分支
                raw_url = f"https://raw.githubusercontent.com/{req.owner}/{req.repo}/master/{req.path}"
                resp = await client.get(raw_url)
            resp.raise_for_status()
            content = resp.text

        # 解析并导入
        skill = SkillParser.parse_content(content)
        existing = await db[COLLECTION].find_one({"name": skill.name})
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Skill '{skill.name}' 已存在，请使用更新接口或先删除再导入",
            )

        doc = _skill_to_doc(skill)
        doc["source_url"] = raw_url
        doc["source_type"] = "github"
        await db[COLLECTION].insert_one(doc)
        await _register_skill_to_registry(doc)
        await _sync_capability_index(db)

        doc.pop("_id", None)
        skill_resp = _doc_to_response(doc)

        # 如果是可执行类型，自动测试
        test_result = None
        if skill_resp.is_executable and skill_resp.implementation:
            test_req = SkillTestRequest(
                skill_name=skill_resp.name,
                args=req.test_args,
                timeout=30
            )
            try:
                test_result = await test_skill(test_req, db)
            except Exception as e:
                test_result = SkillTestResponse(success=False, error=f"测试失败: {str(e)}")

        message = "导入成功" + ("，测试通过" if test_result and test_result.success else "")
        return ImportWithTestResponse(
            skill=skill_resp,
            test_result=test_result,
            message=message
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"从 GitHub 导入失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


class SmitheryServerResponse(BaseModel):
    """Smithery MCP Server 响应"""
    id: str
    name: str
    description: str
    tools: List[Dict[str, Any]]
    install_command: str


@router.get("/smithery/servers", response_model=List[SmitheryServerResponse])
async def list_smithery_servers():
    """列出 Smithery 上的 MCP Server"""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get("https://smithery.ai/api/servers")
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            data = resp.json()

        servers = []
        for server in data.get("servers", [])[:50]:
            servers.append(SmitheryServerResponse(
                id=server.get("id", ""),
                name=server.get("name", ""),
                description=server.get("description", ""),
                tools=server.get("tools", []),
                install_command=f"npx -y @smithery/cli install {server.get('id', '')}"
            ))

        return servers
    except Exception as e:
        logger.error(f"获取 Smithery 服务器列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取列表失败: {str(e)}")


# =============================================================================
# MCP Hub 中国 (mcp-cn.com)
# =============================================================================


class MCPHubServerResponse(BaseModel):
    """MCP Hub 中国服务器响应"""
    server_id: int
    qualified_name: str
    display_name: str
    description: str
    creator: str
    use_count: int
    tag: str
    is_domestic: bool
    connections: str
    package_url: str

class MCPHubListResponse(BaseModel):
    """MCP Hub 列表响应"""
    total: int
    page: int
    page_size: int
    servers: List[MCPHubServerResponse]


@router.get("/mcphub/servers", response_model=MCPHubListResponse)
async def list_mcphub_servers(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=50, description="每页数量"),
    keyword: str = Query("", description="搜索关键词"),
):
    """浏览 MCP Hub 中国 (mcp-cn.com) 上的 MCP Server"""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            params = {"page": page, "pageSize": page_size}
            if keyword:
                params["keyword"] = keyword
            resp = await client.get("https://www.mcp-cn.com/api/servers", params=params)
            resp.raise_for_status()
            data = resp.json()

        servers = []
        for item in data.get("data", []):
            servers.append(MCPHubServerResponse(
                server_id=item.get("server_id", 0),
                qualified_name=item.get("qualified_name", ""),
                display_name=item.get("display_name", ""),
                description=item.get("description", ""),
                creator=item.get("creator", ""),
                use_count=item.get("use_count", 0),
                tag=item.get("tag", ""),
                is_domestic=item.get("is_domestic", False),
                connections=item.get("connections", ""),
                package_url=item.get("package_url", ""),
            ))

        pagination = data.get("pagination", {})
        return MCPHubListResponse(
            total=pagination.get("total", 0),
            page=page,
            page_size=page_size,
            servers=servers,
        )
    except Exception as e:
        logger.error(f"获取 MCP Hub 服务器列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取列表失败: {str(e)}")


# =============================================================================
# AgentHub / ClawHub (agent.xjtool.top)
# =============================================================================


class AgentHubItemResponse(BaseModel):
    """AgentHub 资源响应"""
    id: int
    pkg_id: str
    type: str
    display_name: str
    description: str
    version: str
    origin: str
    source_url: str
    stars: int
    downloads: int
    installs: int
    icon_url: str = ""

class AgentHubSearchResponse(BaseModel):
    """AgentHub 搜索响应"""
    total: int
    items: List[AgentHubItemResponse]


@router.get("/agenthub/search", response_model=AgentHubSearchResponse)
async def search_agenthub(
    q: str = Query("", description="搜索关键词"),
    type_filter: str = Query("", description="类型过滤: skill | mcp-server"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    """搜索 AgentHub (agent.xjtool.top) 上的 Skill 和 MCP Server"""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            params: Dict[str, Any] = {"q": q or "stock", "page": page, "size": page_size}
            if type_filter:
                params["type"] = type_filter
            resp = await client.get("https://agent.xjtool.top/api/search", params=params)
            resp.raise_for_status()
            data = resp.json()

        items = []
        for item in data.get("items", []):
            items.append(AgentHubItemResponse(
                id=item.get("id", 0),
                pkg_id=item.get("pkgId", ""),
                type=item.get("type", ""),
                display_name=item.get("displayName", ""),
                description=item.get("description", ""),
                version=item.get("version", ""),
                origin=item.get("origin", ""),
                source_url=item.get("sourceUrl", ""),
                stars=item.get("stars", 0),
                downloads=item.get("downloads", 0),
                installs=item.get("installs", 0),
                icon_url=item.get("iconUrl", ""),
            ))

        return AgentHubSearchResponse(
            total=data.get("total", 0),
            items=items,
        )
    except Exception as e:
        logger.error(f"搜索 AgentHub 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


# =============================================================================
# 从 AgentHub 导入
# =============================================================================


class ImportFromAgentHubRequest(BaseModel):
    """从 AgentHub 导入请求"""
    pkg_id: str = Field(..., description="AgentHub 包 ID，如 io.clawhub.mbpz/akshare-stock")
    test_args: Optional[Dict[str, Any]] = Field(default=None, description="测试参数")


@router.post("/import-agenthub", response_model=ImportWithTestResponse)
async def import_from_agenthub(
    req: ImportFromAgentHubRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """从 AgentHub 导入 Skill（获取源码并解析为 SKILL.md 格式）"""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            # 获取 Skill 详情和源码
            resp = await client.get(f"https://agent.xjtool.top/api/items/{req.pkg_id}")
            if resp.status_code == 404:
                raise HTTPException(status_code=404, detail=f"未找到 Skill: {req.pkg_id}")
            resp.raise_for_status()
            item_data = resp.json()

        # 尝试获取源码内容
        source_url = item_data.get("sourceUrl", "")
        skill_content = ""

        if source_url:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    src_resp = await client.get(source_url)
                    if src_resp.status_code == 200:
                        skill_content = src_resp.text
            except Exception:
                pass

        if not skill_content:
            # 如果无法获取源码，生成一个基础 SKILL.md
            skill_content = f"""---
name: {item_data.get("displayName", req.pkg_id.split("/")[-1]).lower().replace(" ", "-")}
version: "{item_data.get("version", "1.0.0")}"
description: {item_data.get("description", "")}
author: {item_data.get("origin", "agenthub")}
category: imported
tags: [agenthub, {item_data.get("type", "skill")}]
parameters: []
implementation:
  type: python
  code: |
    import json, sys
    args = json.loads(sys.stdin.read()) if sys.stdin else {{}}
    print("__SANDBOX_OUTPUT_START__")
    print(json.dumps({{"info": "Skill imported from AgentHub", "name": "{item_data.get("displayName", "")}", "pkg_id": "{req.pkg_id}"}}, ensure_ascii=False))
    print("__SANDBOX_OUTPUT_END__")
---

{item_data.get("description", "从 AgentHub 导入的 Skill")}
"""

        # 解析并导入
        skill = SkillParser.parse_content(skill_content)
        doc = _skill_to_doc(skill)
        doc["source_type"] = "agenthub"
        doc["source_url"] = source_url or f"https://agent.xjtool.top/api/items/{req.pkg_id}"

        existing = await db[COLLECTION].find_one({"name": doc["name"]})
        if existing:
            # 更新
            await db[COLLECTION].update_one({"name": doc["name"]}, {"$set": doc})
            doc["_id"] = existing["_id"]
        else:
            await db[COLLECTION].insert_one(doc)

        await _register_skill_to_registry(doc)
        await _sync_capability_index(db)

        # 测试
        test_result = None
        if req.test_args:
            impl = doc.get("implementation", {})
            if impl.get("type") == "python" and impl.get("code"):
                sandbox_result = _execute_python_sandbox(impl["code"], req.test_args, 30)
                test_result = SkillTestResponse(
                    success=sandbox_result["success"],
                    result=sandbox_result.get("result"),
                    error=sandbox_result.get("error"),
                    execution_time_ms=sandbox_result.get("execution_time_ms", 0),
                )

        skill_resp = _doc_to_response(doc)
        return ImportWithTestResponse(
            skill=skill_resp,
            test_result=test_result,
            message=f"已从 AgentHub 导入 Skill: {skill_resp.name}",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"从 AgentHub 导入失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


# =============================================================================
# ClawHub (clawhub.ai) - 本地 Skill 包管理
# 支持 openclaw skills install 类似的安装方式，下载完整 Skill 包到本地
# =============================================================================


class ClawHubSearchResult(BaseModel):
    """ClawHub 搜索结果项"""
    slug: str
    display_name: str
    summary: str = ""
    version: Optional[str] = Field(default="", description="版本号，可能为 None")
    owner_handle: str = ""
    owner_display_name: str = ""
    canonical_url: str = ""
    score: float = 0.0
    updated_at: Optional[int] = None


class ClawHubSearchResponse(BaseModel):
    """ClawHub 搜索响应"""
    query: str
    total: int
    results: List[ClawHubSearchResult]


@router.get("/clawhub/search", response_model=ClawHubSearchResponse)
async def search_clawhub(
    q: str = Query(..., description="搜索关键词"),
    limit: int = Query(20, ge=1, le=50, description="返回数量上限"),
):
    """搜索 ClawHub (clawhub.ai) 上的 Skill

    调用 ClawHub 公开 API: GET /api/v1/search?q=...
    无需认证，速率限制 3000/min per IP
    """
    try:
        results = await ClawHubSkillService.search_skills(q, limit=limit)
        logger.info(f"🔍 ClawHub 搜索 q='{q}': 返回 {len(results) if results else 0} 条结果")
        parsed = [ClawHubSearchResult(**r) for r in (results or [])]
        return ClawHubSearchResponse(query=q, total=len(parsed), results=parsed)
    except Exception as e:
        logger.error(f"❌ ClawHub 搜索异常: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"ClawHub 搜索失败: {str(e)}")


class ClawHubInstallRequest(BaseModel):
    """ClawHub Skill 安装请求"""
    slug: str = Field(..., description="Skill 标识，如 'ifind-repilot-finance-data-search' 或 '@wenzisay/ifind-repilot-finance-data-search'")
    version: Optional[str] = Field(default=None, description="指定版本（可选）")
    tag: Optional[str] = Field(default=None, description="版本标签，如 'latest'（可选）")


class ClawHubInstallResponse(BaseModel):
    """ClawHub Skill 安装响应"""
    success: bool
    skill_name: str = ""
    skill_dir: str = ""
    version: str = ""
    has_scripts: bool = False
    scripts_count: int = 0
    extracted_files_count: int = 0
    skill_type: str = ""
    message: str


@router.post("/install-clawhub", response_model=ClawHubInstallResponse)
async def install_from_clawhub(
    req: ClawHubInstallRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """从 ClawHub 安装 Skill 包到本地目录

    流程：
    1. 调用 ClawHub API 下载完整 Skill 包（含 scripts/）
    2. 解压到 skills/<slug>/ 目录
    3. 校验是否为脚本型 Skill（含 scripts/ 目录），拒绝知识型
    4. 解析 SKILL.md 并注册到 MongoDB
    5. 注册到 ToolRegistry

    类似 `openclaw skills install <slug>` 命令的效果
    """
    try:
        # 1. 下载并解压 Skill 包
        install_result = await ClawHubSkillService.install_skill(
            slug=req.slug, version=req.version, tag=req.tag
        )

        if not install_result.get("success"):
            return ClawHubInstallResponse(
                success=False,
                skill_name=req.slug,
                message=install_result.get("message", "安装失败"),
                skill_type=install_result.get("skill_type", ""),
            )

        # 2. 解析 SKILL.md 并注册到 MongoDB
        skill_name = install_result["skill_name"]
        skill_dir = install_result["skill_dir"]

        try:
            doc = await _import_local_skill_to_db(skill_dir, db, source_type="clawhub")
        except Exception as e:
            logger.warning(f"Skill 包已下载但注册到 MongoDB 失败: {e}", exc_info=True)
            return ClawHubInstallResponse(
                success=True,
                skill_name=skill_name,
                skill_dir=skill_dir,
                version=install_result.get("version", ""),
                has_scripts=True,
                scripts_count=install_result.get("scripts_count", 0),
                extracted_files_count=install_result.get("extracted_files_count", 0),
                message=f"Skill 包已下载到 {skill_dir}，但注册到数据库失败: {e}。可使用 import-local 接口重试。",
            )

        return ClawHubInstallResponse(
            success=True,
            skill_name=skill_name,
            skill_dir=skill_dir,
            version=install_result.get("version", ""),
            has_scripts=True,
            scripts_count=install_result.get("scripts_count", 0),
            extracted_files_count=install_result.get("extracted_files_count", 0),
            message=f"Skill '{skill_name}' 安装并注册成功",
        )
    except Exception as e:
        logger.error(f"从 ClawHub 安装 Skill 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"安装失败: {str(e)}")


class LocalSkillImportRequest(BaseModel):
    """本地 Skill 导入请求"""
    skill_dir: str = Field(..., description="本地 Skill 包目录路径，如 'skills/ifind-finance-search' 或绝对路径")


class LocalSkillImportResponse(BaseModel):
    """本地 Skill 导入响应"""
    success: bool
    skill_name: str = ""
    skill_dir: str = ""
    has_scripts: bool = False
    scripts_count: int = 0
    message: str


@router.post("/import-local", response_model=LocalSkillImportResponse)
async def import_local_skill(
    req: LocalSkillImportRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """从本地目录导入 Skill 包到 MongoDB

    适用于：
    - 已通过 `openclaw skills install` 或 `clawhub install` 安装到 skills/ 目录的 Skill
    - 手动下载的 Skill 包

    要求：
    - 目录中必须包含 SKILL.md 文件
    - 目录中必须包含 scripts/ 子目录（拒绝知识型 Skill）
    """
    try:
        # 解析目录路径
        skill_dir_path = Path(req.skill_dir)
        if not skill_dir_path.is_absolute():
            skill_dir_path = (SKILLS_DIR / req.skill_dir).resolve()

        if not skill_dir_path.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Skill 目录不存在: {skill_dir_path}。请先使用 install-clawhub 安装 Skill 包。",
            )

        # 校验 SKILL.md
        skill_md_path = skill_dir_path / "SKILL.md"
        if not skill_md_path.exists():
            raise HTTPException(
                status_code=400,
                detail=f"目录中未找到 SKILL.md: {skill_md_path}",
            )

        # 校验 scripts/ 目录（拒绝知识型 Skill）
        scripts_dir = skill_dir_path / "scripts"
        if not scripts_dir.is_dir():
            raise HTTPException(
                status_code=400,
                detail=(
                    f"知识型 Skill（无 scripts/ 目录）不支持导入。"
                    f"本项目只支持包含可执行脚本的 Python 脚本型 Skill。"
                ),
            )
        script_files = [f for f in scripts_dir.iterdir() if f.is_file() and f.suffix == ".py"]
        if not script_files:
            raise HTTPException(
                status_code=400,
                detail=f"scripts/ 目录中没有 Python 脚本文件，无法导入",
            )

        doc = await _import_local_skill_to_db(str(skill_dir_path), db, source_type="local")

        return LocalSkillImportResponse(
            success=True,
            skill_name=doc.get("name", ""),
            skill_dir=str(skill_dir_path),
            has_scripts=True,
            scripts_count=len(script_files),
            message=f"Skill '{doc.get('name', '')}' 导入成功",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"本地 Skill 导入失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


class LocalSkillItem(BaseModel):
    """本地 Skill 包项"""
    name: str
    skill_dir: str
    has_scripts: bool
    has_skill_md: bool
    source: str = "local"
    version: str = ""
    installed_at: str = ""
    canonical_url: str = ""
    imported_to_db: bool = False


@router.get("/local", response_model=List[LocalSkillItem])
async def list_local_skills(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """列出本地已安装的 Skill 包

    扫描 skills/ 目录，返回所有包含 SKILL.md 的子目录。
    同时检查是否已导入到 MongoDB。
    """
    local_skills = ClawHubSkillService.list_local_skills()

    # 查询 MongoDB 中已导入的 Skill
    imported_names = set()
    async for doc in db[COLLECTION].find({"source_type": {"$in": ["clawhub_local", "local", "clawhub"]}}, {"name": 1}):
        if doc.get("name"):
            imported_names.add(doc["name"])

    result = []
    for item in local_skills:
        item["imported_to_db"] = item["name"] in imported_names
        result.append(LocalSkillItem(**item))
    return result


class LocalSkillUninstallResponse(BaseModel):
    """本地 Skill 卸载响应"""
    success: bool
    message: str


@router.delete("/local/{slug}", response_model=LocalSkillUninstallResponse)
async def uninstall_local_skill(
    slug: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """卸载本地 Skill 包

    1. 删除 skills/<slug>/ 目录
    2. 从 MongoDB 中删除对应记录
    3. 从 ToolRegistry 中注销（由重启后自然失效）
    """
    try:
        # 1. 删除本地目录
        result = ClawHubSkillService.uninstall_local_skill(slug)
        if not result.get("success"):
            return LocalSkillUninstallResponse(
                success=False,
                message=result.get("message", "卸载失败"),
            )

        # 2. 从 MongoDB 删除记录
        delete_result = await db[COLLECTION].delete_many({
            "$or": [
                {"name": slug},
                {"name": slug.replace("-", "_")},
            ]
        })
        deleted_count = delete_result.deleted_count

        message = result.get("message", "卸载成功")
        if deleted_count > 0:
            message += f"，已删除 {deleted_count} 条数据库记录"

        return LocalSkillUninstallResponse(success=True, message=message)
    except Exception as e:
        logger.error(f"卸载本地 Skill 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"卸载失败: {str(e)}")


# =============================================================
# SkillHub (腾讯) Skill 搜索与安装
# 通过 skillhub CLI 子进程调用，skill 实际存储在 GitHub
# =============================================================


class SkillHubSearchResult(BaseModel):
    """SkillHub 搜索结果项"""
    slug: str = ""
    skill_id: str = ""
    display_name: str = ""
    summary: str = ""
    version: str = ""
    owner_handle: str = ""
    github_owner: str = ""
    github_repo: str = ""
    github_stars: int = 0
    download_count: int = 0
    security_score: int = 0
    security_status: str = ""
    ai_score: Optional[float] = None
    rating: float = 0
    is_verified: bool = False
    canonical_url: str = ""


class SkillHubSearchResponse(BaseModel):
    """SkillHub 搜索响应"""
    query: str
    total: int
    results: List[SkillHubSearchResult]


class SkillHubInstallRequest(BaseModel):
    """SkillHub 安装请求"""
    skill_id: str = Field(..., description="Skill slug，如 'stock-info-explorer'")


class SkillHubInstallResponse(BaseModel):
    """SkillHub 安装响应"""
    success: bool
    skill_name: str = ""
    skill_dir: str = ""
    version: str = ""
    has_scripts: bool = False
    scripts_count: int = 0
    message: str


# =============================================================
# ZIP 文件上传 / URL 导入（替代 SkillHub CLI）
# =============================================================

class ImportZipResponse(BaseModel):
    """ZIP 导入响应"""
    success: bool
    skill_name: str = ""
    skill_dir: str = ""
    has_scripts: bool = False
    scripts_count: int = 0
    dependencies_installed: bool = False
    dependencies_log: str = ""
    message: str


def _install_skill_dependencies(skill_dir: str) -> Dict[str, Any]:
    """如果 Skill 包内有 requirements.txt，自动安装依赖

    Returns:
        {success: bool, installed: bool, log: str}
        - installed=False 表示没有 requirements.txt（不算失败）
        - installed=True success=True 表示成功安装
    """
    import subprocess as _sp
    import sys

    req_file = Path(skill_dir) / "requirements.txt"
    if not req_file.exists():
        return {"success": True, "installed": False, "log": "无 requirements.txt，跳过依赖安装"}

    try:
        # 读取一下内容，过滤注释和空行
        lines = [
            l.strip() for l in req_file.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.strip().startswith("#")
        ]
        if not lines:
            return {"success": True, "installed": False, "log": "requirements.txt 为空"}

        logger.info(f"📦 检测到 requirements.txt，开始安装依赖: {lines}")

        proc = _sp.run(
            [sys.executable, "-m", "pip", "install", "-r", str(req_file), "--disable-pip-version-check"],
            capture_output=True,
            text=True,
            timeout=300,  # 5 分钟超时
            encoding="utf-8",
            errors="replace",
        )

        log_output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        # 截断日志避免过长
        if len(log_output) > 2000:
            log_output = log_output[:1000] + "\n... (中间省略) ...\n" + log_output[-1000:]

        if proc.returncode == 0:
            logger.info(f"✅ Skill 依赖安装成功: {skill_dir}")
            return {"success": True, "installed": True, "log": log_output}
        else:
            logger.error(f"❌ Skill 依赖安装失败 (returncode={proc.returncode})")
            return {"success": False, "installed": True, "log": log_output}
    except Exception as e:
        logger.error(f"❌ 依赖安装异常: {e}", exc_info=True)
        return {"success": False, "installed": True, "log": f"安装异常: {e}"}


@router.post("/{skill_name}/install-deps")
async def install_skill_deps(
    skill_name: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """为已安装的 Skill 手动触发 requirements.txt 依赖安装

    使用场景：导入时依赖安装失败、用户后来手动改了 requirements.txt 等。
    """
    existing = await db[COLLECTION].find_one({
        "$or": [
            {"name": skill_name},
            {"display_name": skill_name},
        ]
    })
    if not existing:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' 不存在")

    skill_dir = existing.get("skill_dir")
    if not skill_dir or not Path(skill_dir).exists():
        raise HTTPException(status_code=400, detail=f"Skill 目录不存在: {skill_dir}")

    result = _install_skill_dependencies(skill_dir)
    return {
        "success": result["success"],
        "installed": result["installed"],
        "log": result["log"],
        "message": (
            "依赖安装成功" if result["installed"] and result["success"]
            else ("无 requirements.txt 可安装" if not result["installed"] else "依赖安装失败")
        ),
    }


def _resolve_skill_name(skill_root: Path, fallback: str) -> str:
    """从 SKILL.md frontmatter 解析真实的 name 字段，并转换为合法目录名

    处理逻辑：
    1. 优先提取括号内的英文 slug（如 "股票价值投资分析 (valuation-analysis)" → "valuation-analysis"）
    2. 如果整个 name 已是合法 slug（英文/数字/连字符/下划线），直接使用
    3. 否则把空格替换为连字符，剥离非 ASCII 字符
    4. 解析失败或结果为空时返回 fallback
    """
    import re

    skill_md = skill_root / "SKILL.md"
    if not skill_md.exists():
        return fallback
    try:
        content = skill_md.read_text(encoding="utf-8")
        skill = SkillParser.parse_content(content)
        name = skill.metadata.name if skill and skill.metadata else None
        if not name or not name.strip():
            return fallback

        name = name.strip()

        # 1. 优先提取括号内的 slug：xxx (yyy) → yyy
        m = re.search(r'\(([a-zA-Z0-9][\w\-]*)\)', name)
        if m:
            slug = m.group(1).strip()
            if slug:
                logger.info(f"📝 从 name 括号提取 slug: '{name}' → '{slug}'")
                return slug

        # 2. 已是合法 slug
        if re.match(r'^[a-zA-Z0-9][\w\-]*$', name):
            return name

        # 3. slugify：空格→连字符，剥离非 ASCII
        slug = re.sub(r'[^\w\-]', '-', name).strip('-')
        slug = re.sub(r'-+', '-', slug)
        # 移除非 ASCII（中文等）
        slug = ''.join(c for c in slug if c.isascii())
        slug = slug.strip('-')

        if slug:
            logger.info(f"📝 name slugify: '{name}' → '{slug}'")
            return slug
    except Exception as e:
        logger.warning(f"从 SKILL.md 解析 name 失败，使用 fallback={fallback}: {e}")

    return fallback


@router.post("/import-zip", response_model=ImportZipResponse)
async def import_skill_from_zip(
    file: UploadFile = File(..., description="Skill 包 ZIP 文件"),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """上传 ZIP 文件导入 Skill 包

    流程：
    1. 接收 ZIP 文件，校验格式和大小（50MB 限制）
    2. 解压到临时目录，定位 SKILL.md 根目录
    3. 移动到 skills/<name>/
    4. 解析 SKILL.md 并注册到 MongoDB + ToolRegistry
    """
    import tempfile

    # 1. 校验文件类型
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="请上传 .zip 格式的文件")

    try:
        zip_bytes = await file.read()
        if len(zip_bytes) > 50 * 1024 * 1024:  # 50MB 限制
            raise HTTPException(status_code=400, detail="ZIP 文件大小不能超过 50MB")

        # 2. 解压到临时目录
        with tempfile.TemporaryDirectory(prefix="skill_import_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            ClawHubSkillService._extract_zip(zip_bytes, tmp_path)

            # 3. 定位 SKILL.md 根目录
            skill_root = ClawHubSkillService._locate_skill_root(tmp_path)
            if not skill_root:
                raise HTTPException(
                    status_code=400,
                    detail="ZIP 包中未找到 SKILL.md 文件，请确认是有效的 Skill 包",
                )

            # 优先从 SKILL.md 解析真实的 name 字段（避免使用临时目录名）
            skill_name = _resolve_skill_name(skill_root, fallback=skill_root.name)
            target_dir = SKILLS_DIR / skill_name

            # 4. 如果目标已存在，先删除旧目录
            if target_dir.exists():
                import shutil
                shutil.rmtree(target_dir)
                logger.info(f"🔄 已替换已存在的 Skill 包: {skill_name}")

            # 5. 移动到 skills/ 目录
            import shutil
            shutil.move(str(skill_root), str(target_dir))
            logger.info(f"📦 ZIP 导入成功: {skill_name} → {target_dir}")

            # 6. 解析 SKILL.md 并注册到 MongoDB + ToolRegistry
            doc = await _import_local_skill_to_db(str(target_dir), db, source_type="zip_upload")
            await _register_skill_to_registry(doc)

            script_count = len(doc.get("script_files", []))

            # 7. 自动安装 requirements.txt 依赖
            dep_result = _install_skill_dependencies(str(target_dir))

            msg = f"Skill '{skill_name}' 导入成功"
            if dep_result["installed"]:
                if dep_result["success"]:
                    msg += "，依赖已安装"
                else:
                    msg += "，但依赖安装失败（请手动 pip install -r requirements.txt）"

            return ImportZipResponse(
                success=True,
                skill_name=skill_name,
                skill_dir=str(target_dir),
                has_scripts=doc.get("has_scripts", False),
                scripts_count=script_count,
                dependencies_installed=dep_result["installed"] and dep_result["success"],
                dependencies_log=dep_result["log"],
                message=msg,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ ZIP 导入失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


class ImportUrlRequest(BaseModel):
    """URL 导入请求"""
    url: str = Field(..., description="Skill 包 ZIP 下载链接")
    name: Optional[str] = Field(None, description="自定义 Skill 名称（可选）")


@router.post("/import-url", response_model=ImportZipResponse)
async def import_skill_from_url(
    req: ImportUrlRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """通过下载链接导入 Skill 包

    流程：
    1. 从 URL 下载 ZIP 文件
    2. 解压到临时目录，定位 SKILL.md
    3. 移动到 skills/<name>/
    4. 解析 SKILL.md 并注册到 MongoDB + ToolRegistry
    """
    import tempfile

    try:
        url = req.url.strip()

        # 1. 下载 ZIP
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            zip_bytes = resp.content

        if len(zip_bytes) > 50 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="文件大小超过 50MB")

        # 2. 解压到临时目录
        with tempfile.TemporaryDirectory(prefix="skill_url_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            ClawHubSkillService._extract_zip(zip_bytes, tmp_path)

            # 3. 定位 SKILL.md 根目录
            skill_root = ClawHubSkillService._locate_skill_root(tmp_path)
            if not skill_root:
                raise HTTPException(
                    status_code=400,
                    detail="ZIP 包中未找到 SKILL.md 文件，请确认是有效的 Skill 包",
                )

            # 4. 确定名称（优先从 SKILL.md 解析真实 name）
            skill_name = req.name or _resolve_skill_name(skill_root, fallback=skill_root.name)
            target_dir = SKILLS_DIR / skill_name

            if target_dir.exists():
                import shutil
                shutil.rmtree(target_dir)

            # 5. 移动到 skills/ 目录
            import shutil
            shutil.move(str(skill_root), str(target_dir))
            logger.info(f"📦 URL 导入成功: {skill_name} ← {url[:80]}...")

            # 6. 解析并注册
            doc = await _import_local_skill_to_db(str(target_dir), db, source_type="url_import")
            await _register_skill_to_registry(doc)

            script_count = len(doc.get("script_files", []))

            # 7. 自动安装 requirements.txt 依赖
            dep_result = _install_skill_dependencies(str(target_dir))

            msg = f"Skill '{skill_name}' 从 URL 导入成功"
            if dep_result["installed"]:
                if dep_result["success"]:
                    msg += "，依赖已安装"
                else:
                    msg += "，但依赖安装失败（请手动 pip install -r requirements.txt）"

            return ImportZipResponse(
                success=True,
                skill_name=skill_name,
                skill_dir=str(target_dir),
                has_scripts=doc.get("has_scripts", False),
                scripts_count=script_count,
                dependencies_installed=dep_result["installed"] and dep_result["success"],
                dependencies_log=dep_result["log"],
                message=msg,
            )

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"下载失败 (HTTP {e.response.status_code})")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ URL 导入失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


# =============================================================
# 内部辅助函数：将本地 Skill 包导入 MongoDB
# =============================================================

async def _import_local_skill_to_db(
    skill_dir: str,
    db: AsyncIOMotorDatabase,
    source_type: str = "local",
) -> Dict[str, Any]:
    """将本地 Skill 包导入 MongoDB

    Args:
        skill_dir: Skill 包目录绝对路径
        db: MongoDB 数据库
        source_type: 来源类型（clawhub / local）

    Returns:
        导入的 Skill doc

    Raises:
        HTTPException: 如果 SKILL.md 解析失败
    """
    skill_dir_path = Path(skill_dir)
    skill_md_path = skill_dir_path / "SKILL.md"

    # 解析 SKILL.md
    content = skill_md_path.read_text(encoding="utf-8")
    skill = SkillParser.parse_content(content)

    # 构建 doc
    doc = _skill_to_doc(skill)
    doc["skill_dir"] = str(skill_dir_path.resolve())
    doc["source_type"] = source_type
    doc["has_scripts"] = True

    # 列出 Python 脚本（兼容两种包结构）
    #   A) scripts/*.py（ClawHub 标准）
    #   B) 根目录 *.py（SkillHub 部分包结构，如 stock-monitor/monitor.py）
    scripts_dir = skill_dir_path / "scripts"
    script_files = []
    if scripts_dir.is_dir():
        script_files = [f.name for f in scripts_dir.iterdir() if f.is_file() and f.suffix == ".py"]
    else:
        # 检查根目录 .py 文件
        script_files = [f.name for f in skill_dir_path.iterdir()
                        if f.is_file() and f.suffix == ".py" and f.name != "__init__.py"]
        if script_files:
            logger.info(f"📦 Skill '{doc.get('name', '?')}' 使用根目录脚本: {script_files}")
    doc["script_files"] = script_files

    # 如果 SKILL.md 中没有声明 implementation，自动构建一个
    # 优先使用 scripts/ 目录中的入口脚本，否则用根目录第一个 .py 文件
    if not doc.get("implementation"):
        if script_files:
            if (skill_dir_path / "scripts").is_dir():
                script_path = f"scripts/{script_files[0]}"
            else:
                script_path = script_files[0]
            doc["implementation"] = {
                "type": "python",
                "script_path": script_path,
                "skill_dir": str(skill_dir_path.resolve()),
                "note": "Auto-detected",
            }
    else:
        # 如果已有 implementation，补充 skill_dir 字段
        impl = doc["implementation"]
        if isinstance(impl, dict):
            impl.setdefault("skill_dir", str(skill_dir_path.resolve()))
            # 如果没有 code/module/function，但有脚本文件，添加 script_path
            if not impl.get("code") and not impl.get("module") and not impl.get("script_path"):
                if script_files:
                    if (skill_dir_path / "scripts").is_dir():
                        impl["script_path"] = f"scripts/{script_files[0]}"
                    else:
                        impl["script_path"] = script_files[0]

    # 解析凭证声明并保存到 doc
    credential_decls = SkillCredentialService.parse_credentials_from_skill_md(str(skill_dir_path))
    if credential_decls:
        doc["required_credentials"] = [d.to_dict() for d in credential_decls]

    # 写入 MongoDB（upsert）
    existing = await db[COLLECTION].find_one({"name": doc["name"]})
    if existing:
        await db[COLLECTION].update_one({"name": doc["name"]}, {"$set": doc})
        doc["_id"] = existing["_id"]
    else:
        await db[COLLECTION].insert_one(doc)

    # 注册到 ToolRegistry
    await _register_skill_to_registry(doc)
    await _sync_capability_index(db)

    logger.info(f"✅ 本地 Skill '{doc['name']}' 已导入 MongoDB (skill_dir={skill_dir_path})")
    return doc


# =============================================================================
# Skill 凭证管理
# 支持两种凭证配置方式：
# 1. frontmatter env 声明（环境变量注入）
# 2. 命令行参数式配置（如 --set-token）
# =============================================================================


class CredentialRequirementResponse(BaseModel):
    """凭证声明响应"""
    name: str
    description: str = ""
    required: bool = False
    config_type: str = "env"  # env | script_arg
    config_command: str = ""
    configured: bool = False
    masked_value: str = ""


class CredentialStatusResponse(BaseModel):
    """凭证状态响应"""
    skill_name: str
    required: List[CredentialRequirementResponse] = []
    extra: List[Dict[str, str]] = []
    all_configured: bool = False
    missing_required: List[str] = []


class SaveCredentialsRequest(BaseModel):
    """保存凭证请求"""
    credentials: Dict[str, str] = Field(..., description="凭证键值对（明文，将加密存储）")


class ConfigureViaScriptRequest(BaseModel):
    """通过脚本命令配置凭证请求"""
    config_command: str = Field(..., description="配置命令，如 '--set-token'")
    credential_value: str = Field(..., description="凭证值")
    script_path: Optional[str] = Field(default=None, description="脚本路径（默认从 implementation.script_path 获取）")
    timeout: int = Field(default=30, description="超时秒数")


@router.get("/{skill_name}/credentials/required", response_model=CredentialStatusResponse)
async def get_skill_credentials_status(
    skill_name: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取 Skill 凭证配置状态

    返回需要的凭证列表及其配置状态（不返回明文）。
    凭证声明从 SKILL.md 解析，支持两种方式：
    1. frontmatter metadata.openclaw.env 声明
    2. instructions 中的 --set-token 等配置命令
    """
    # 获取 Skill 文档
    doc = await db[COLLECTION].find_one({"name": skill_name})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' 不存在")

    # 获取凭证声明
    declarations: List[CredentialDeclaration] = []
    skill_dir = doc.get("skill_dir")
    if skill_dir:
        declarations = SkillCredentialService.parse_credentials_from_skill_md(skill_dir)
    else:
        # 从 doc 中读取已保存的声明
        for decl_dict in doc.get("required_credentials", []):
            declarations.append(CredentialDeclaration(
                name=decl_dict.get("name", ""),
                description=decl_dict.get("description", ""),
                required=decl_dict.get("required", False),
                config_type=decl_dict.get("config_type", "env"),
                config_command=decl_dict.get("config_command", ""),
            ))

    # 获取凭证状态
    status = await SkillCredentialService.get_credentials_status(db, skill_name, declarations)

    return CredentialStatusResponse(
        skill_name=status["skill_name"],
        required=[CredentialRequirementResponse(**r) for r in status["required"]],
        extra=status["extra"],
        all_configured=status["all_configured"],
        missing_required=status["missing_required"],
    )


@router.post("/{skill_name}/credentials")
async def save_skill_credentials(
    skill_name: str,
    req: SaveCredentialsRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """保存 Skill 凭证（加密存储）

    将凭证值加密后存储到 MongoDB skill_credentials 集合。
    执行脚本时会自动注入为环境变量。

    对于使用 --set-token 等命令配置的 Skill，
    请使用 /credentials/configure-script 端点。
    """
    # 校验 Skill 存在
    doc = await db[COLLECTION].find_one({"name": skill_name})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' 不存在")

    result = await SkillCredentialService.save_credentials(db, skill_name, req.credentials)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "保存失败"))

    return {
        "success": True,
        "skill_name": skill_name,
        "saved_count": result["saved_count"],
        "message": f"凭证已保存（{result['saved_count']} 项）",
    }


@router.get("/{skill_name}/credentials", response_model=CredentialStatusResponse)
async def get_skill_credentials(
    skill_name: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取 Skill 凭证状态（别名，同 /credentials/required）"""
    return await get_skill_credentials_status(skill_name, db)


@router.delete("/{skill_name}/credentials")
async def delete_skill_credentials(
    skill_name: str,
    keys: Optional[str] = Query(None, description="要删除的凭证键名（逗号分隔），不传则删除全部"),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """删除 Skill 凭证"""
    key_list = keys.split(",") if keys else None
    result = await SkillCredentialService.delete_credentials(db, skill_name, key_list)
    return {
        "success": result["success"],
        "deleted_count": result["deleted_count"],
        "message": f"已删除 {result['deleted_count']} 项凭证",
    }


@router.post("/{skill_name}/credentials/configure-script")
async def configure_credential_via_script(
    skill_name: str,
    req: ConfigureViaScriptRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """通过脚本的配置命令配置凭证

    适用于使用 --set-token 等命令配置凭证的 Skill。
    例如：python scripts/fetch_data.py --set-token <token>

    执行后，凭证会被脚本自身存储（如写入 ~/.config/xxx/config.json）。
    同时也会将凭证值加密保存到 MongoDB，便于后续执行时注入环境变量。
    """
    # 校验 Skill 存在
    doc = await db[COLLECTION].find_one({"name": skill_name})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' 不存在")

    skill_dir = doc.get("skill_dir")
    if not skill_dir:
        raise HTTPException(
            status_code=400,
            detail=f"Skill '{skill_name}' 没有本地包目录（skill_dir），无法执行配置命令",
        )

    # 获取脚本路径
    script_path = req.script_path
    if not script_path:
        impl = doc.get("implementation") or {}
        script_path = impl.get("script_path")
    if not script_path:
        raise HTTPException(
            status_code=400,
            detail="未指定 script_path，且 Skill implementation 中没有 script_path 字段",
        )

    # 执行配置命令
    result = await SkillCredentialService.configure_via_script(
        skill_dir=skill_dir,
        script_path=script_path,
        config_command=req.config_command,
        credential_value=req.credential_value,
        timeout=req.timeout,
    )

    if not result.get("success"):
        return {
            "success": False,
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "message": result.get("message", "配置失败"),
        }

    # 同时将凭证值加密保存到 MongoDB
    # 推导凭证名：--set-token -> AUTH_TOKEN
    var_name = SkillCredentialService._derive_var_name(
        req.config_command.lstrip("-").replace("set-", "").replace("config-", "")
    )
    await SkillCredentialService.save_credentials(
        db, skill_name, {var_name: req.credential_value}
    )

    return {
        "success": True,
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "message": f"凭证配置成功，已执行 {req.config_command} 命令并保存到数据库",
        "saved_credential_name": var_name,
    }


# =============================================================================
# 动态路径路由（必须放在固定路径路由之后，避免路径参数匹配冲突）
# =============================================================================

@router.get("/{skill_name}", response_model=SkillResponse)
async def get_skill(
    skill_name: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取 Skill 详情"""
    doc = await db[COLLECTION].find_one({"name": skill_name})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' 不存在")
    return _doc_to_response(doc)


@router.put("/{skill_name}", response_model=SkillResponse)
async def update_skill(
    skill_name: str,
    req: SkillCreateRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """更新 Skill"""
    existing = await db[COLLECTION].find_one({"name": skill_name})
    if not existing:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' 不存在")

    if existing.get("is_builtin", False):
        raise HTTPException(status_code=400, detail="内置 Skill 不可修改")

    update_doc = req.model_dump(exclude_none=True)
    update_doc["updated_at"] = datetime.utcnow().isoformat()
    update_doc["name"] = req.name

    await db[COLLECTION].update_one({"name": skill_name}, {"$set": update_doc})

    updated = await db[COLLECTION].find_one({"name": req.name})
    if updated:
        await _register_skill_to_registry(updated)
        await _sync_capability_index(db)

    return _doc_to_response(updated or update_doc)


@router.delete("/{skill_name}")
async def delete_skill(
    skill_name: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """删除 Skill（卸载）

    1. 删除 MongoDB 中的 Skill 记录
    2. 从 ToolRegistry 中注销
    3. 删除 Agent 绑定关系
    4. 删除本地 skills/<skill_name>/ 目录（如果存在）
    5. 删除该 Skill 的凭证

    支持 name 或 display_name 匹配。
    """
    # 兼容：支持 name / display_name / skill_id(下划线) 多种格式匹配
    existing = await db[COLLECTION].find_one({
        "$or": [
            {"name": skill_name},
            {"display_name": skill_name},
            {"name": skill_name.replace("_", "-")},
            {"skill_id": skill_name},
            {"skill_id": skill_name.replace("-", "_")},
        ]
    })

    if not existing:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' 不存在")

    real_name = existing["name"]

    if existing.get("is_builtin", False):
        raise HTTPException(status_code=400, detail="内置 Skill 不可删除")

    # 1. 删除 MongoDB 记录
    await db[COLLECTION].delete_one({"name": real_name})

    # 2. 从 ToolRegistry 注销
    tool_id = real_name.replace("-", "_")
    registry = get_tool_registry()
    registry.unregister(tool_id)

    # 3. 删除 Agent 绑定关系
    await db.tool_agent_bindings.delete_many({"tool_id": tool_id})

    # 4. 删除本地 skills/ 目录（同时尝试多种名称匹配）
    deleted_dir = False
    # 尝试直接匹配 name / display_name / skill_id
    candidates = [
        real_name,
        skill_name,
        existing.get("display_name", ""),
        existing.get("skill_id", ""),
    ]
    # 去重
    seen = set()
    unique_candidates = []
    for c in candidates:
        c = str(c or "").strip()
        if c and c not in seen:
            seen.add(c)
            unique_candidates.append(c)

    for name_to_try in unique_candidates:
        try:
            result = ClawHubSkillService.uninstall_local_skill(name_to_try)
            if result.get("success"):
                deleted_dir = True
                break
        except Exception:
            pass

    # 如果直接匹配都失败，扫描 skill_import_* 目录，通过 SKILL.md 中的 skill_id 匹配
    if not deleted_dir:
        try:
            import re
            skills_dir = Path(__file__).resolve().parents[2] / "skills"
            for child in skills_dir.iterdir():
                if not child.is_dir():
                    continue
                if not child.name.startswith("skill_import_"):
                    continue
                skill_md = child / "SKILL.md"
                if not skill_md.exists():
                    continue
                content = skill_md.read_text(encoding="utf-8", errors="ignore")
                # 检查是否包含该 skill 的 skill_id 或 name
                doc_skill_id = str(existing.get("skill_id", "")).strip()
                doc_name = str(existing.get("name", "")).strip()
                if doc_skill_id and doc_skill_id in content:
                    import shutil
                    shutil.rmtree(child)
                    deleted_dir = True
                    logger.info(f"✅ 通过 SKILL.md 匹配删除了 import 目录: {child.name} (skill_id={doc_skill_id})")
                    break
                if doc_name and doc_name in content:
                    import shutil
                    shutil.rmtree(child)
                    deleted_dir = True
                    logger.info(f"✅ 通过 SKILL.md 匹配删除了 import 目录: {child.name} (name={doc_name})")
                    break
        except Exception:
            pass

    # 5. 删除凭证
    try:
        await SkillCredentialService.delete_credentials(db, real_name, keys=None)
    except Exception as e:
        logger.warning(f"删除 Skill 凭证失败: {e}")

    await _sync_capability_index(db)

    msg = f"Skill '{real_name}' 已卸载"
    if deleted_dir:
        msg += "（含本地目录和凭证）"
    return {"success": True, "message": msg, "deleted_dir": deleted_dir}


@router.post("/{skill_name}/toggle")
async def toggle_skill(
    skill_name: str,
    req: SkillToggleRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """启用/禁用 Skill"""
    existing = await db[COLLECTION].find_one({"name": skill_name})
    if not existing:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' 不存在")

    await db[COLLECTION].update_one(
        {"name": skill_name},
        {"$set": {"enabled": req.enabled, "updated_at": datetime.utcnow().isoformat()}},
    )

    tool_id = skill_name.replace("-", "_")
    registry = get_tool_registry()
    if req.enabled:
        updated = await db[COLLECTION].find_one({"name": skill_name})
        if updated:
            await _register_skill_to_registry(updated)
    else:
        registry.unregister(tool_id)
    await _sync_capability_index(db)

    status = "启用" if req.enabled else "禁用"
    return {"success": True, "message": f"Skill '{skill_name}' 已{status}"}


@router.get("/{skill_name}/export")
async def export_skill(
    skill_name: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """导出 Skill 为 SKILL.md 格式"""
    doc = await db[COLLECTION].find_one({"name": skill_name})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' 不存在")

    doc.pop("_id", None)

    import yaml
    frontmatter_fields = {}
    for key in ("name", "description", "version", "author", "category", "tags",
                "when_to_use", "parameters", "returns", "implementation",
                "enabled", "fc_enabled"):
        val = doc.get(key)
        if val is not None and val != "" and val != []:
            frontmatter_fields[key] = val

    yaml_str = yaml.dump(frontmatter_fields, allow_unicode=True, default_flow_style=False, sort_keys=False)
    instructions = doc.get("instructions", "")

    skill_md = f"---\n{yaml_str}---\n\n{instructions}\n"

    return {"content": skill_md, "filename": f"{skill_name}.SKILL.md"}

