"""
分层提示词组装服务

将基础模板 + 行业画像 + 个股画像 + 能力块 + 任务块组装为最终 Prompt。

核心职责:
- 合并行业画像与个股画像（继承/覆盖/追加）
- 生成 analysis_context_block
- 生成 capability_block
- 生成 task_block
- 完整组装最终 Prompt
"""

import logging
from typing import Optional, Dict, Any, List

from app.services.analysis_profile_service import AnalysisProfileService
from app.services.prompt_injection_policy_service import PromptInjectionPolicyService
from tradingagents.utils.template_client import get_template_client

logger = logging.getLogger(__name__)


class PromptAssemblyService:
    """
    分层提示词组装服务
    
    实现设计文档 §5 的运行时组装规则：
    - 行业分析：基础模板 → 场景策略 → 能力块 → 行业画像块 → 任务块
    - 个股分析：基础模板 → 场景策略 → 能力块 → 行业画像摘要 → 个股画像块 → 任务块
    """
    
    def __init__(self):
        self.profile_service = AnalysisProfileService()
        self.policy_service = PromptInjectionPolicyService()
        self.template_client = get_template_client()
    
    # ==================== 公开接口 ====================
    
    def _get_policy_sync(
        self,
        agent_type: Optional[str],
        agent_name: Optional[str],
        scope: str,
    ):
        """同步获取注入策略，无策略时返回 None"""
        if not agent_type or not agent_name:
            return None
        return self.policy_service.get_policy_by_agent_scope_sync(
            agent_type=agent_type,
            agent_name=agent_name,
            scope=scope,
        )

    def build_analysis_context_block(
        self,
        analysis_type: str,
        industry: Optional[str] = None,
        stock_symbol: Optional[str] = None,
        agent_type: Optional[str] = None,
        agent_name: Optional[str] = None,
        policy_override: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        构建 analysis_context_block（分析上下文块）
        
        Args:
            analysis_type: 分析类型 "general" / "industry" / "stock"
            industry: 行业名称
            stock_symbol: 股票代码
            agent_type: Agent 类型（可选，用于策略查询）
            agent_name: Agent 名称（可选，用于策略查询）
        
        Returns:
            格式化的分析上下文块文本
        """
        if analysis_type == "general":
            return ""

        # Phase 2: 策略控制 - injection_mode=none 时不注入
        policy = policy_override if policy_override is not None else self._get_policy_sync(agent_type, agent_name, analysis_type)
        if policy and policy.get("injection_mode") == "none":
            logger.info(f"📋 [策略] {agent_type}/{agent_name} scope={analysis_type} injection_mode=none，跳过上下文块")
            return ""
        
        blocks = []
        
        # 1. 获取行业画像
        industry_profile = None
        if industry:
            industry_profile = self._get_industry_profile_sync(industry)
        
        # 2. 获取个股画像
        stock_profile = None
        if stock_symbol and analysis_type == "stock":
            stock_profile = self._get_stock_profile_sync(stock_symbol)
        
        # 3. 合并画像（策略控制 inherit_industry_for_stock、include_comparable_companies）
        inherit_industry = policy.get("inherit_industry_for_stock", True) if policy else True
        include_comparable = policy.get("include_comparable_companies", True) if policy else True
        merged = self._merge_profiles(
            industry_profile,
            stock_profile,
            inherit_industry_for_stock=inherit_industry,
            include_comparable_companies=include_comparable,
        )
        
        # 3.5 策略：injection_mode=summary 时做摘要压缩（设计文档 §4.2）
        injection_mode = (policy.get("injection_mode") if policy else None) or "full"
        if injection_mode == "summary":
            merged = self._summarize_merged_profile(merged)
            logger.info("📋 [analysis_context_block] 使用 summary 模式，已压缩维度与文本")
        
        # 4. 格式化输出
        if merged.get("dimensions"):
            blocks.append("## 分析维度\n")
            for dim in merged["dimensions"]:
                importance = dim.get("importance", "high")
                name = dim.get("name", "")
                desc = dim.get("description", "")
                source = dim.get("source", "")
                source_hint = f"（来自{source}）" if source else ""
                blocks.append(f"- **{name}** [{importance}]{source_hint}: {desc}")
        
        if merged.get("key_metrics"):
            blocks.append("\n## 关键指标\n")
            blocks.append(", ".join(merged["key_metrics"]))
        
        if merged.get("analysis_focus"):
            blocks.append("\n## 分析重点\n")
            blocks.append(merged["analysis_focus"])
        
        if include_comparable and merged.get("comparable_companies"):
            blocks.append("\n## 可比公司\n")
            blocks.append(", ".join(merged["comparable_companies"]))
        
        if merged.get("special_notes"):
            blocks.append("\n## 特殊说明\n")
            blocks.append(merged["special_notes"])
        
        result = "\n".join(blocks)
        if result:
            logger.info(f"📋 [analysis_context_block] 生成长度: {len(result)}")
        return result
    
    def build_capability_block(
        self,
        analysis_type: str,
        industry: Optional[str] = None,
        stock_symbol: Optional[str] = None,
        agent_type: Optional[str] = None,
        agent_name: Optional[str] = None,
        policy_override: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        构建 capability_block（能力边界说明块）
        
        告知模型哪些数据可直接使用、哪些需要保守表达
        
        Args:
            analysis_type: 分析类型
            industry: 行业名称
            stock_symbol: 股票代码
            agent_type: Agent 类型（可选，用于策略查询）
            agent_name: Agent 名称（可选，用于策略查询）
        
        Returns:
            格式化的能力边界说明文本
        """
        # Phase 2: 策略控制 - include_capability_block=False 时不注入
        policy = policy_override if policy_override is not None else self._get_policy_sync(agent_type, agent_name, analysis_type)
        if policy and policy.get("include_capability_block") is False:
            logger.info(f"🔧 [策略] {agent_type}/{agent_name} scope={analysis_type} include_capability_block=False，跳过能力块")
            return ""

        # 收集能力快照
        capability = self._collect_capability_snapshot_sync()
        
        blocks = []
        blocks.append("## 数据能力边界\n")
        
        # 可直接使用
        builtin = capability.get("builtin_sources", [])
        if builtin:
            blocks.append("### 可直接使用的数据能力")
            for src in builtin[:4]:
                blocks.append(f"- {src.get('label')}: {src.get('description')[:80]}")
        
        # 可间接获取
        mcp_servers = capability.get("enabled_mcp_servers", [])
        skills = capability.get("active_skills", [])
        if mcp_servers or skills:
            blocks.append("\n### 可间接获取的数据能力")
            if mcp_servers:
                blocks.append("- MCP 服务:")
                for srv in mcp_servers[:3]:
                    desc = srv.get('description', '')[:60]
                    if not desc:
                        desc = f"{srv.get('tool_count', 0)} 个工具"
                    blocks.append(f"  - {srv.get('name')}: {desc}")
            if skills:
                blocks.append("- Skill 能力:")
                for sk in skills[:3]:
                    blocks.append(f"  - {sk.get('name')}: {sk.get('description', '')[:60]}")
        
        # 当前缺失提醒（策略可关闭 include_external_gap_notice）
        if policy is None or policy.get("include_external_gap_notice", True):
            blocks.append("\n### 数据缺口提醒")
            blocks.append("- 若需要运营指标、行业外部数据等非结构化信息，建议结合 MCP/Skill 或外部数据源")
            blocks.append("- 定性指标（如品牌力、管理层执行力等）需依赖专业判断或外部研报")
        
        result = "\n".join(blocks)
        logger.info(f"🔧 [capability_block] 生成长度: {len(result)}")
        return result
    
    def build_task_block(
        self,
        task_description: str,
        analysis_type: str,
    ) -> str:
        """
        构建 task_block（任务指令块）
        
        Args:
            task_description: 当前任务描述
            analysis_type: 分析类型
        
        Returns:
            格式化的任务块文本
        """
        if not task_description:
            return ""
        
        type_labels = {
            "general": "通用分析",
            "industry": "行业分析",
            "stock": "个股分析",
        }
        
        blocks = []
        blocks.append("## 当前分析任务\n")
        blocks.append(f"**分析类型**: {type_labels.get(analysis_type, analysis_type)}\n")
        blocks.append(f"**任务目标**:\n{task_description}")
        
        result = "\n".join(blocks)
        logger.info(f"🎯 [task_block] 生成长度: {len(result)}")
        return result
    
    def assemble_prompt(
        self,
        agent_type: str,
        agent_name: str,
        analysis_type: str = "general",
        industry: Optional[str] = None,
        stock_symbol: Optional[str] = None,
        task_description: str = "",
        include_capability: bool = True,
        variables: Optional[Dict[str, Any]] = None,
        workflow_id: Optional[str] = None,
        node_id: Optional[str] = None,
        template_override: Optional[Dict[str, Any]] = None,
        policy_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        完整组装入口：选模板 → 生成三块 → 变量替换 → 返回最终 Prompt
        
        Args:
            agent_type: Agent 类型
            agent_name: Agent 名称
            analysis_type: 分析类型 "general" / "industry" / "stock"
            industry: 行业名称
            stock_symbol: 股票代码
            task_description: 任务描述
            include_capability: 是否包含能力块
            variables: 额外变量字典
        
        Returns:
            {
                "final_prompt": str,          # 最终完整 Prompt
                "sections": Dict[str, str],   # 各段内容
                "sources": Dict[str, str],    # 各段来源
                "template_id": str,           # 使用的模板 ID
                "profile_used": Dict,         # 使用的画像信息
                "capability_gaps": List[str], # 能力缺口提醒
            }
        """
        # 1. 获取模板
        template = template_override or self.template_client.get_effective_template(
            agent_type,
            agent_name,
            workflow_id=workflow_id,
            node_id=node_id,
        )
        if not template:
            logger.warning(f"⚠️ 未找到模板: {agent_type}/{agent_name}")
            template = {}
        
        template_id = template.get("template_id", "")
        
        # 2. 获取策略（Phase 2）
        policy_override = (policy_overrides or {}).get(analysis_type)
        policy = policy_override if policy_override is not None else self._get_policy_sync(agent_type, agent_name, analysis_type)
        effective_include_capability = include_capability
        if policy and policy.get("include_capability_block") is False:
            effective_include_capability = False

        # 3. 生成三个块（传入 agent 信息供策略控制）
        context_block = self.build_analysis_context_block(
            analysis_type, industry, stock_symbol,
            agent_type=agent_type, agent_name=agent_name,
            policy_override=policy,
        )
        capability_block = self.build_capability_block(
            analysis_type, industry, stock_symbol,
            agent_type=agent_type, agent_name=agent_name,
            policy_override=policy,
        ) if effective_include_capability else ""
        task_block = self.build_task_block(task_description, analysis_type)
        
        # 4. 准备变量（包含三个新块）
        final_variables = variables or {}
        final_variables["analysis_context_block"] = context_block
        final_variables["capability_block"] = capability_block
        final_variables["task_block"] = task_block
        
        # 4. 格式化模板
        formatted = self.template_client.format_template(template, final_variables)
        
        # 4.5 策略 inject_position：若模板未包含占位符，将块追加到策略指定字段（设计文档 §7.2）
        inject_pos = (policy.get("inject_position") if policy else None) or "analysis_requirements"
        for key in ("system_prompt", "analysis_requirements", "constraints"):
            if key not in formatted or formatted[key] is None:
                formatted[key] = ""
        if context_block and inject_pos in formatted and context_block[:40] not in (formatted.get(inject_pos) or ""):
            formatted[inject_pos] = (formatted[inject_pos] or "").strip() + "\n\n" + context_block
        if task_block and "analysis_requirements" in formatted and task_block[:40] not in (formatted.get("analysis_requirements") or ""):
            formatted["analysis_requirements"] = (formatted["analysis_requirements"] or "").strip() + "\n\n" + task_block
        if capability_block and "constraints" in formatted and capability_block[:40] not in (formatted.get("constraints") or ""):
            formatted["constraints"] = (formatted["constraints"] or "").strip() + "\n\n" + capability_block
        
        # 5. 组装最终 Prompt
        parts = []
        sections = {}
        sources = {}
        
        if formatted.get("system_prompt"):
            parts.append(formatted["system_prompt"])
            sections["system_prompt"] = formatted["system_prompt"]
            sources["system_prompt"] = "基础角色模板"
        
        if formatted.get("tool_guidance"):
            parts.append("\n\n" + formatted["tool_guidance"])
            sections["tool_guidance"] = formatted["tool_guidance"]
            sources["tool_guidance"] = "基础角色模板"
        
        # analysis_requirements 承载 context_block + task_block
        if formatted.get("analysis_requirements"):
            parts.append("\n\n" + formatted["analysis_requirements"])
            sections["analysis_requirements"] = formatted["analysis_requirements"]
            sources["analysis_requirements"] = "基础模板 + 上下文注入"
        
        if formatted.get("output_format"):
            parts.append("\n\n" + formatted["output_format"])
            sections["output_format"] = formatted["output_format"]
            sources["output_format"] = "基础角色模板"
        
        # constraints 承载 capability_block
        if formatted.get("constraints"):
            parts.append("\n\n" + formatted["constraints"])
            sections["constraints"] = formatted["constraints"]
            sources["constraints"] = "基础模板 + 能力边界注入"
        
        # 记录三块来源
        if context_block:
            sections["analysis_context_block"] = context_block
            sources["analysis_context_block"] = f"画像服务（行业={industry or 'N/A'}, 个股={stock_symbol or 'N/A'}）"
        if capability_block:
            sections["capability_block"] = capability_block
            sources["capability_block"] = "能力评估服务"
        if task_block:
            sections["task_block"] = task_block
            sources["task_block"] = "任务描述"
        
        final_prompt = "\n".join(parts)
        
        # 6. 收集能力缺口
        capability_gaps = self._collect_capability_gaps(analysis_type, industry, stock_symbol)
        
        # 7. 收集使用的画像信息
        profile_used = {
            "industry": industry,
            "stock_symbol": stock_symbol,
            "industry_profile_found": bool(self._get_industry_profile_sync(industry)) if industry else False,
            "stock_profile_found": bool(self._get_stock_profile_sync(stock_symbol)) if stock_symbol else False,
        }
        
        logger.info(
            f"✅ [assemble_prompt] 组装完成: {agent_type}/{agent_name}, "
            f"类型={analysis_type}, 最终长度={len(final_prompt)}"
        )
        
        return {
            "final_prompt": final_prompt,
            "sections": sections,
            "sources": sources,
            "template_id": template_id,
            "profile_used": profile_used,
            "capability_gaps": capability_gaps,
        }
    
    # ==================== 内部工具 ====================
    
    def _get_industry_profile_sync(self, industry: str) -> Optional[Dict]:
        """同步获取行业画像"""
        if not industry:
            return None
        try:
            result = AnalysisProfileService.get_industry_dimensions_sync(industry)
            if result:
                # 重建 profile 结构
                from app.core.database import get_mongo_db_sync
                db = get_mongo_db_sync()
                doc = db["industry_analysis_profiles"].find_one(
                    {"industry": industry, "is_active": True}
                )
                if doc:
                    doc["id"] = str(doc.pop("_id"))
                    return doc
        except Exception as e:
            logger.warning(f"⚠️ 获取行业画像失败: {e}")
        return None
    
    def _get_stock_profile_sync(self, stock_symbol: str) -> Optional[Dict]:
        """同步获取个股画像"""
        if not stock_symbol:
            return None
        try:
            from app.core.database import get_mongo_db_sync
            db = get_mongo_db_sync()
            doc = db["stock_analysis_profiles"].find_one(
                {"stock_symbol": stock_symbol, "is_active": True}
            )
            if doc:
                doc["id"] = str(doc.pop("_id"))
                return doc
        except Exception as e:
            logger.warning(f"⚠️ 获取个股画像失败: {e}")
        return None
    
    def _merge_profiles(
        self,
        industry_profile: Optional[Dict],
        stock_profile: Optional[Dict],
        inherit_industry_for_stock: bool = True,
        include_comparable_companies: bool = True,
    ) -> Dict[str, Any]:
        """
        合并行业画像与个股画像
        
        规则（对应设计文档 §6）:
        1. inherit: 默认继承行业画像中的分析维度和关键指标
        2. append: 个股可追加专属维度
        3. override: 个股可重写某个行业维度的说明或重要性
        4. disable: 个股可显式关闭某些行业默认维度
        
        Args:
            industry_profile: 行业画像
            stock_profile: 个股画像
            inherit_industry_for_stock: 个股场景是否继承行业画像（策略控制）
            include_comparable_companies: 是否包含可比公司（策略控制）
        
        Returns:
            合并后的结构化内容
        """
        result = {
            "dimensions": [],
            "key_metrics": [],
            "analysis_focus": "",
            "comparable_companies": [],
            "special_notes": "",
        }
        
        # 1. 从行业画像继承（个股场景且 inherit_industry_for_stock=False 时跳过）
        if industry_profile and not (stock_profile and not inherit_industry_for_stock):
            dims = industry_profile.get("analysis_dimensions", [])
            for d in dims:
                result["dimensions"].append({
                    **d,
                    "source": "行业画像",
                })
            result["key_metrics"] = list(industry_profile.get("key_metrics", []))
            result["analysis_focus"] = industry_profile.get("analysis_focus", "")
            result["comparable_companies"] = list(industry_profile.get("comparable_companies", []))
        
        # 2. 应用个股画像覆盖
        if stock_profile:
            stock_dims = stock_profile.get("analysis_dimensions", [])
            stock_overrides = stock_profile.get("dimension_overrides", {})  # {维度名: {action: "override"/"disable", ...}}
            
            # 处理追加/覆盖
            for sd in stock_dims:
                name = sd.get("name", "")
                existing_idx = next(
                    (i for i, d in enumerate(result["dimensions"]) if d.get("name") == name),
                    None
                )
                
                if existing_idx is not None:
                    # override: 覆盖已有维度
                    result["dimensions"][existing_idx] = {
                        **result["dimensions"][existing_idx],
                        **sd,
                        "source": "个股画像覆盖",
                    }
                else:
                    # append: 追加新维度
                    result["dimensions"].append({
                        **sd,
                        "source": "个股画像追加",
                    })
            
            # 处理 disable
            for dim_name, override_info in stock_overrides.items():
                if override_info.get("action") == "disable":
                    result["dimensions"] = [
                        d for d in result["dimensions"]
                        if d.get("name") != dim_name
                    ]
            
            # 合并关键指标
            stock_metrics = stock_profile.get("key_metrics", [])
            for m in stock_metrics:
                if m not in result["key_metrics"]:
                    result["key_metrics"].append(m)
            
            # 特殊说明
            if stock_profile.get("special_notes"):
                result["special_notes"] = stock_profile["special_notes"]

        # 策略控制：不包含可比公司时清空
        if not include_comparable_companies:
            result["comparable_companies"] = []
        
        return result
    
    def _summarize_merged_profile(self, merged: Dict[str, Any]) -> Dict[str, Any]:
        """
        摘要模式：压缩合并后的画像，控制 token（设计文档 §4.2 injection_mode=summary）
        - 分析维度最多保留 5 条，描述截断至 50 字
        - 关键指标最多 5 个
        - 分析重点截断至 100 字
        - 可比公司最多 3 个
        - 特殊说明截断至 80 字
        """
        out = dict(merged)
        summary_desc_len = 50
        summary_focus_len = 100
        summary_notes_len = 80
        max_dimensions = 5
        max_key_metrics = 5
        max_comparable = 3

        if out.get("dimensions"):
            out["dimensions"] = [
                {
                    **d,
                    "description": (d.get("description") or "")[:summary_desc_len]
                    + ("..." if len((d.get("description") or "")) > summary_desc_len else ""),
                }
                for d in out["dimensions"][:max_dimensions]
            ]
        if out.get("key_metrics"):
            out["key_metrics"] = list(out["key_metrics"][:max_key_metrics])
        if out.get("analysis_focus"):
            s = out["analysis_focus"]
            out["analysis_focus"] = s[:summary_focus_len] + ("..." if len(s) > summary_focus_len else "")
        if out.get("comparable_companies"):
            out["comparable_companies"] = list(out["comparable_companies"][:max_comparable])
        if out.get("special_notes"):
            s = out["special_notes"]
            out["special_notes"] = s[:summary_notes_len] + ("..." if len(s) > summary_notes_len else "")
        return out
    
    def _collect_capability_snapshot_sync(self) -> Dict[str, Any]:
        """同步收集能力快照"""
        try:
            from app.core.database import get_mongo_db_sync
            db = get_mongo_db_sync()
            
            # 使用 AnalysisProfileService 的能力收集逻辑
            service = AnalysisProfileService()
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果已有事件循环，使用同步方式
                    return self._collect_capability_sync_impl(db)
                else:
                    return loop.run_until_complete(service._collect_capability_snapshot(db))
            except RuntimeError:
                return self._collect_capability_sync_impl(db)
        except Exception as e:
            logger.warning(f"⚠️ 收集能力快照失败: {e}")
            return {"builtin_sources": [], "enabled_mcp_servers": [], "active_skills": []}
    
    def _collect_capability_sync_impl(self, db) -> Dict[str, Any]:
        """同步收集能力快照的实现"""
        from app.services.analysis_profile_service import BUILTIN_SOURCE_DEFINITIONS
        
        builtin_sources = [
            {"key": item["key"], "label": item["label"], "description": item["description"]}
            for item in BUILTIN_SOURCE_DEFINITIONS
        ]
        
        enabled_mcp_servers = []
        try:
            for doc in db["mcp_server_configs"].find({"is_enabled": True}):
                tools = doc.get("discovered_tools", []) or []
                enabled_mcp_servers.append({
                    "server_id": doc.get("server_id", ""),
                    "name": doc.get("name", ""),
                    "description": doc.get("description", ""),
                    "tool_count": len(tools),
                })
        except Exception:
            pass
        
        active_skills = []
        try:
            for doc in db["external_skills"].find({"status": "active"}):
                active_skills.append({
                    "tool_id": doc.get("tool_id", ""),
                    "name": doc.get("display_name", ""),
                    "description": doc.get("description", ""),
                })
        except Exception:
            pass
        
        return {
            "builtin_sources": builtin_sources,
            "enabled_mcp_servers": enabled_mcp_servers,
            "active_skills": active_skills,
        }
    
    def _collect_capability_gaps(
        self,
        analysis_type: str,
        industry: Optional[str],
        stock_symbol: Optional[str],
    ) -> List[str]:
        """收集能力缺口提醒"""
        gaps = []
        
        # 检查行业画像是否存在
        if industry and analysis_type in ("industry", "stock"):
            profile = self._get_industry_profile_sync(industry)
            if not profile:
                gaps.append(f"行业「{industry}」暂无画像配置，建议先创建行业分析画像")
        
        # 检查个股画像是否存在
        if stock_symbol and analysis_type == "stock":
            profile = self._get_stock_profile_sync(stock_symbol)
            if not profile:
                gaps.append(f"个股「{stock_symbol}」暂无画像配置，将使用行业画像作为默认框架")
        
        # 检查 MCP/Skill 可用性
        capability = self._collect_capability_snapshot_sync()
        if not capability.get("enabled_mcp_servers"):
            gaps.append("当前未启用任何 MCP 服务器，部分数据能力可能受限")
        
        return gaps


# ==================== 全局单例 ====================

_assembly_service: Optional[PromptAssemblyService] = None


def get_prompt_assembly_service() -> PromptAssemblyService:
    """获取 PromptAssemblyService 全局单例"""
    global _assembly_service
    if _assembly_service is None:
        _assembly_service = PromptAssemblyService()
    return _assembly_service