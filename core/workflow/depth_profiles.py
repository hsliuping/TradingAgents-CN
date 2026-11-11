"""
三档分析画像注册表（DEPTH_PROFILES）

单一注册表管理三档分析的全部档位差异（流程环节/执行形态/轮数/产出规范/
工具预算/模型层级/数据面/记忆/缓存 TTL），替代散落各处的 depth_mapping，
终结「选哪档报告都一样」与口径漂移。

设计文档：docs/05-design/v4.0/analysis-depth-profiles-refactor.md
实施文档：docs/05-design/v4.0/analysis-depth-profiles-implementation.md
架构文档：docs/05-design/v4.0/profit-loss-dual-track-architecture.md §6/§7

三档简化（2026-11-04 定稿，原五档 → 三档）：
- 快速(1)  = 初筛摸底（原 1 档不动）
- 标准(3)  = 建立判断（原 3 档不动；原 2 基础档并入标准，旧值 2 显式报错）
- 深度(5)  = 选股研究（原 4 深度 + 5 全面 合并取并集；成本/模型/数据面
             取原 5 档上限，旧值 4 与「全面」显式报错）
- 退役档位（2/4、「基础」「全面」）运行时抛 ValueError，禁止静默降档；
  存量配置经 scripts/migration/migrate_depth_three_levels.py 显式迁移
  （2→3、4→5），历史报告的档位字段为历史事实不迁移。

值域约定：
- 档位名（中文）是对外唯一标识：快速/标准/深度
- 执行形态与轮数分离：debate_mode/risk_mode 决定走多 agent 接龙还是单节点
  自我辩论；debate_rounds/risk_rounds 仅 multi_agent 回退路径生效
- memory_mode: off | snapshot | snapshot_diff（语义见设计文档 §3.3）
- cache_ttl_min: 短周期分析缓存 TTL（分钟，见设计文档 §3.4）
"""

from dataclasses import dataclass
from typing import Any, Optional, Union

# 档位名（中文），level 1/3/5
DEPTH_NAMES: tuple[str, ...] = ("快速", "标准", "深度")

_DEFAULT_DEPTH = "标准"

# 退役档位（五档时代）→ 迁移目标；运行时命中即抛错，禁止静默降档
_RETIRED_LEVEL_TARGETS: dict[int, int] = {2: 3, 4: 5}
_RETIRED_NAME_TARGETS: dict[str, int] = {"基础": 3, "全面": 5}
_MIGRATION_SCRIPT = "scripts/migration/migrate_depth_three_levels.py"

# 流程环节名（nodes 集合成员）
NODE_ANALYST = "analyst"          # 分析师并行
NODE_DEBATE = "debate"            # 多空辩论
NODE_RISK_REVIEW = "risk_review"  # 风险会审
NODE_SCENARIO_SIM = "scenario_sim"  # 情景试算
NODE_INTEGRATION = "integration"  # 研究整合（research_manager + trader）

_FULL_NODES = frozenset(
    {NODE_ANALYST, NODE_DEBATE, NODE_RISK_REVIEW, NODE_SCENARIO_SIM, NODE_INTEGRATION}
)

# 执行形态
MODE_MULTI_AGENT = "multi_agent"
MODE_SELF_DEBATE = "self_debate"

# 记忆模式（设计文档 §3.3）
MEMORY_OFF = "off"
MEMORY_SNAPSHOT = "snapshot"
MEMORY_SNAPSHOT_DIFF = "snapshot_diff"

# 产出规范文案（三档逐档累加，M2.1 契约块正文；单点维护在此）
OUTPUT_SPEC_QUICK = (
    "输出 ≤600 字快报。结构：①3 条核心结论（每条一句话）②关键读数"
    "（价格/估值/预期）③最主要的 1 个风险。不展开论证、无数据表、无附录。"
)
OUTPUT_SPEC_STANDARD = (
    "完整论证。结构：论点→证据（带读数与口径）→反面证据→结论；含数据表；"
    "关键结论与证据一一对应。"
)
# 深度档 = 原深度(4) + 全面(5) 产出要求并集
# 🆕 v4.0 方法论进产品：选股六问落点 + 能力圈纪律（2026-11-05）
OUTPUT_SPEC_DEEP = (
    "标准档要求全部 + 证据链（关键结论标注证据来源与强度）+ 反例检验"
    "（主动找 ≥2 个反面证据并逐条回应）+ 明确失效条件"
    "+ 选股六问落点（逐项作答：是什么生意/生意好不好/贵不贵/动力在哪/"
    "会怎么死/触发条件是什么；缺数据的项如实标注缺什么，不得跳过不答）"
    "+ 信息缺口清单（缺什么数据/为什么缺/对判断的影响；设不出失效条件的问题"
    "＝能力圈外，显式列为「不参与判断」）"
    "+ 后续观察建议（可执行观察项，含阈值与建议回查时点）+ 附录（完整读数表）。"
)


@dataclass(frozen=True)
class DepthProfile:
    name: str                 # "标准"
    level: int                # 3（取值 1/3/5）
    # —— 流程结构 ——
    nodes: frozenset          # 启用环节: {"analyst","debate","risk_review","scenario_sim","integration"}
    debate_mode: str          # "multi_agent" | "self_debate"
    risk_mode: str            # "multi_agent" | "self_debate"
    parallel_opening: bool    # A3 辩论第一轮并行开局
    debate_rounds: int        # multi_agent 回退路径生效
    risk_rounds: int          # multi_agent 回退路径生效
    # —— 产出与调用 ——
    output_spec: str          # 提示词产出规范（字数/结构）
    tool_budget: int          # max_tool_rounds
    model_tier: str           # quick | mixed | deep
    data_scope: str           # basic | standard | full | comprehensive
    memory_mode: str          # off | snapshot | snapshot_diff
    cache_ttl_min: int        # 短周期分析缓存 TTL（分钟）

    @property
    def memory_enabled(self) -> bool:
        """兼容既有 memory_enabled: bool 透传（builder / MemoryProvider 不改）。"""
        return self.memory_mode != MEMORY_OFF


# 三档画像矩阵（2026-11-04 三档简化定稿）——唯一事实来源
# 深度档 = 原深度(4) + 全面(5) 并集：环节/形态/记忆相同取并集，
# 工具预算/模型分层/数据面/缓存 TTL 取原 5 档（全面）上限。
DEPTH_PROFILES: dict[str, DepthProfile] = {
    "快速": DepthProfile(
        name="快速",
        level=1,
        nodes=frozenset({NODE_ANALYST, NODE_DEBATE, NODE_INTEGRATION}),
        debate_mode=MODE_MULTI_AGENT,
        risk_mode=MODE_MULTI_AGENT,
        parallel_opening=True,
        debate_rounds=1,
        risk_rounds=1,
        output_spec=OUTPUT_SPEC_QUICK,
        tool_budget=2,
        model_tier="quick",
        data_scope="basic",
        memory_mode=MEMORY_OFF,
        cache_ttl_min=30,
    ),
    "标准": DepthProfile(
        name="标准",
        level=3,
        nodes=_FULL_NODES,
        debate_mode=MODE_SELF_DEBATE,
        risk_mode=MODE_SELF_DEBATE,
        parallel_opening=True,
        debate_rounds=2,
        risk_rounds=1,
        output_spec=OUTPUT_SPEC_STANDARD,
        tool_budget=6,
        model_tier="mixed",
        data_scope="standard",
        memory_mode=MEMORY_SNAPSHOT,
        cache_ttl_min=120,
    ),
    "深度": DepthProfile(
        name="深度",
        level=5,
        nodes=_FULL_NODES,
        debate_mode=MODE_SELF_DEBATE,
        risk_mode=MODE_SELF_DEBATE,
        parallel_opening=True,
        debate_rounds=3,
        risk_rounds=1,
        output_spec=OUTPUT_SPEC_DEEP,
        tool_budget=15,
        model_tier="deep",
        data_scope="comprehensive",
        memory_mode=MEMORY_SNAPSHOT_DIFF,
        cache_ttl_min=1440,
    ),
}

_NUMERIC_TO_NAME = {profile.level: name for name, profile in DEPTH_PROFILES.items()}


def _raise_retired_depth(value: Union[str, int, float], target_level: int) -> None:
    """退役档位显式报错（禁静默降档）：五档时代的 2/4、基础/全面 已停用。"""
    target_name = _NUMERIC_TO_NAME[target_level]
    raise ValueError(
        f"研究深度 {value!r} 是已停用的档位（五档已简化为三档：快速1/标准3/深度5），"
        f"请改用「{target_name}」档（{target_level} 级），"
        f"或先运行迁移脚本 {_MIGRATION_SCRIPT} 处理存量配置。"
    )


def normalize_depth(research_depth: Union[str, int, float, None]) -> str:
    """把各种档位输入归一化为中文档位名。

    接受：1/3/5（int/float）、"1"/"3"/"5"、中文档位名（快速/标准/深度）。
    退役档位（2/4、「基础」「全面」，五档时代遗留）抛 ValueError——
    禁止静默降档，存量配置经迁移脚本显式处理。
    未知/非法输入（越界数字、乱串）回退「标准」。
    """
    if isinstance(research_depth, bool):
        return _DEFAULT_DEPTH
    if isinstance(research_depth, (int, float)):
        level = int(research_depth)
        if float(research_depth) != level:
            return _DEFAULT_DEPTH
        if level in _RETIRED_LEVEL_TARGETS:
            _raise_retired_depth(level, _RETIRED_LEVEL_TARGETS[level])
        return _NUMERIC_TO_NAME.get(level, _DEFAULT_DEPTH)
    if isinstance(research_depth, str):
        text = research_depth.strip()
        if text in _RETIRED_NAME_TARGETS:
            _raise_retired_depth(text, _RETIRED_NAME_TARGETS[text])
        if text in DEPTH_PROFILES:
            return text
        if text.isdigit():
            level = int(text)
            if level in _RETIRED_LEVEL_TARGETS:
                _raise_retired_depth(level, _RETIRED_LEVEL_TARGETS[level])
            return _NUMERIC_TO_NAME.get(level, _DEFAULT_DEPTH)
    return _DEFAULT_DEPTH


def get_profile(research_depth: Union[str, int, float, None]) -> DepthProfile:
    """按档位取画像；未知档位回退「标准」。"""
    return DEPTH_PROFILES[normalize_depth(research_depth)]


# ============================================================================
# M2.1 档位契约块（文案单点维护；core/agents/base.py 提示词组装处统一注入）
# ============================================================================
# 分层原则（实施文档 M2.1）：角色模板不动，五档差异全部收敛到运行时注入的
# 「档位契约块」——全体契约（篇幅/口径/环节声明）+ 按角色取用的角色段。

CONTRACT_DISCIPLINE_LINE = (
    "- 口径纪律：所有读数注明口径（官方/手工收集/推算）与数据日期；"
    "查不到的数据写「暂无读数：<原因>」，禁止编造、插值、外推。"
)

# 环节展示名（「本档不含环节」清单按此顺序取用）
_NODE_LABELS: dict[str, str] = {
    NODE_ANALYST: "分析师环节",
    NODE_DEBATE: "多空辩论",
    NODE_RISK_REVIEW: "风险会审",
    NODE_SCENARIO_SIM: "情景试算",
    NODE_INTEGRATION: "研究整合",
}

# 角色分组（角色段取用规则，实施文档 M2.1 表）
_REVIEW_ROLE_AGENTS = frozenset(
    {"risky_analyst_v2", "safe_analyst_v2", "neutral_analyst_v2", "risk_self_debate_v2"}
)
_DEBATE_ROLE_AGENTS = frozenset(
    {"bull_researcher_v2", "bear_researcher_v2", "research_self_debate_v2"}
)
_INTEGRATION_ROLE_AGENTS = frozenset({"research_manager_v2"})
_REPORT_ROLE_AGENTS = frozenset({"trader_v2"})

# ============================================================================
# 节点级思考预算（reasoning_effort）分层
# ============================================================================
# 档位默认 effort 对全部节点一视同仁，工具型分析师与论证型节点同预算，
# 全面档单节点（风险自我辩论）实测 24 分钟。按角色分层：工具型分析师关闭思考，
# 论证/裁决型节点保留中等思考，避免长提示词下思考耗尽超时。
# 覆盖优先级：节点/Agent 配置显式 reasoning_effort > 本表默认 > DB 模型配置 > 档位默认。
EFFORT_NONE = "none"
EFFORT_MEDIUM = "medium"

# 论证型角色（辩论/会审/整合/报告/情景），保留思考
_THINKING_ROLE_AGENTS = (
    _REVIEW_ROLE_AGENTS
    | _DEBATE_ROLE_AGENTS
    | _INTEGRATION_ROLE_AGENTS
    | _REPORT_ROLE_AGENTS
    | frozenset(
        {
            "bull_researcher",
            "bear_researcher",
            "research_manager",
            "risk_manager",
            "risk_manager_v2",
            "scenario_simulator",
            "scenario_simulator_v2",
            "trader",
        }
    )
)


def resolve_agent_reasoning_effort(agent_id: str) -> Optional[str]:
    """按角色取节点级思考预算默认值；未登记角色返回 None（沿用既有链路）。"""
    name = str(agent_id or "").strip()
    if not name:
        return None
    if name in _THINKING_ROLE_AGENTS:
        return EFFORT_MEDIUM
    if name.endswith(("_analyst", "_analyst_v1", "_analyst_v2")):
        return EFFORT_NONE
    return None



def _analyst_role_section(level: int) -> str:
    """分析师段：读数密度随档位（快速=仅核心读数，标准=数据表，深度=来源与强度）。"""
    if level <= 1:
        density = "仅列核心读数（价格/估值/预期），不铺开全量数据。"
    elif level == 3:
        density = "关键读数配完整数据表，结论与读数一一对应。"
    else:
        density = "关键读数配完整数据表，并标注证据来源与强度。"
    return f"- 读数密度：{density}"


def _debate_role_section(level: int) -> str:
    """辩论段：交锋要求随档位（标准+=回应闭环，深度+=失效条件与情景区间）。"""
    if level <= 1:
        requirement = "单轮发言：直接给出本方论点与证据，无需回应对方。"
    elif level <= 3:
        requirement = "须回应对方上一轮的 1-2 个新增点（回应闭环），不重复扩写已有内容。"
    else:
        requirement = (
            "须回应对方上一轮的 1-2 个新增点（回应闭环），不重复扩写已有内容；"
            "结论附失效条件（出现何种证据/读数时判断作废）；"
            "必须给出本方判断对应的股价情景区间（形如「40.5—45.0 元」，写明口径与时点），"
            "供情景试算直接引用——缺区间视为本方论证不完整。"
        )
    return f"- 交锋要求：{requirement}"


_REVIEW_ROLE_SECTION = (
    "- 审阅要求：单轮质证：只输出本视角的评审结论与依据，不重复他方观点。"
)


def _integration_role_section(level: int) -> str:
    """整合段：分歧与信息缺口随档位（标准档 1 项，深度+ 完整清单）。"""
    if level <= 1:
        requirement = "如实列出分歧（如有）；缺数据的方面注明信息缺口，不得省略或编造。"
    elif level == 3:
        requirement = "显式列出分歧与信息缺口（各至少 1 项）。"
    else:
        requirement = "完整列出分歧清单与信息缺口清单（缺什么数据/为什么缺/对判断的影响）。"
    return f"- 整合要求：{requirement}"


_REPORT_ROLE_SECTION = (
    "- 报告章节要求：「篇幅与结构」所列章节即最终报告的章节清单，"
    "逐章成文、缺一不可；「本档不含环节」须在报告中显式声明。"
)


def resolve_role_section(agent_name: str, level: int) -> str:
    """按 agent 角色取契约块角色段；未登记角色只给全体契约（返回空串）。"""
    name = str(agent_name or "")
    if name in _REPORT_ROLE_AGENTS:
        return _REPORT_ROLE_SECTION
    if name in _INTEGRATION_ROLE_AGENTS:
        return _integration_role_section(level)
    if name in _REVIEW_ROLE_AGENTS:
        return _REVIEW_ROLE_SECTION
    if name in _DEBATE_ROLE_AGENTS:
        return _debate_role_section(level)
    if name.endswith("_analyst_v2"):
        return _analyst_role_section(level)
    return ""


def build_contract_block(profile: DepthProfile, agent_name: str = "") -> str:
    """构建「本档分析契约」提示词块（全体契约 + 角色段）。

    由 core/agents/base.py 提示词组装处注入，与行业维度块、知识 Skill 块并列。
    """
    skipped = [label for node, label in _NODE_LABELS.items() if node not in profile.nodes]
    skipped_text = "、".join(skipped) if skipped else "无"
    lines = [
        "",
        "",
        f"【本档分析契约：{profile.name}档】",
        f"- 篇幅与结构：{profile.output_spec}",
        CONTRACT_DISCIPLINE_LINE,
        f"- 本档不含环节：{skipped_text}（报告中按此声明说明，不得虚构不含环节的结论）",
    ]
    role_section = resolve_role_section(agent_name, profile.level)
    if role_section:
        lines.append(role_section)
    snapshot_section = build_snapshot_requirements(profile, agent_name)
    if snapshot_section:
        lines.append(snapshot_section)
    return "\n".join(lines) + "\n"


# ============================================================================
# M3 流程门控（v2 模板 CONDITION 分流 + skipped 运行清单 + 报告标注）
# ============================================================================
# 机制（设计文档 §4.1）：v2 模板在 merge→debate、research_manager→
# scenario_simulator→risk_debate 段插 CONDITION 门；门控只做整段跳过，
# A9-P1/P2 自我辩论内部路由不动。条件表达式只写 state.get('<旗标>') 简式，
# 复杂判断（环节归属）收敛在 profile.nodes（本模块）。

# 运行清单节点状态
STATUS_INCLUDED = "included"
STATUS_SKIPPED = "skipped"

# 环节 → v2 模板节点 ID（门控跳过整段时这些节点置 skipped 写入运行清单；
# 与 _REVIEW_ROLE_AGENTS 等同为 v2 链路约定，集中单点维护）
_STAGE_GRAPH_NODES: dict[str, tuple[str, ...]] = {
    NODE_ANALYST: (
        "index_analyst_v2",
        "sector_analyst_v2",
        "market_analyst_v2",
        "fundamentals_analyst_v2",
        "news_analyst_v2",
        "social_analyst_v2",
    ),
    NODE_DEBATE: ("debate", "bull_researcher_v2", "bear_researcher_v2"),
    NODE_SCENARIO_SIM: ("scenario_simulator_v2",),
    NODE_RISK_REVIEW: (
        "risk_debate",
        "risky_analyst_v2",
        "safe_analyst_v2",
        "neutral_analyst_v2",
        "risk_manager_v2",
    ),
    NODE_INTEGRATION: ("research_manager_v2", "trader_v2"),
}

# v2 模板门控旗标（CONDITION 节点表达式形如 `not state.get('_skip_debate')`）
# 语义：True=跳过该段；缺旗标（None）视为 False——旧链路/自定义流照常执行，行为不变
GATE_FLAG_DEBATE = "_skip_debate"
GATE_FLAG_SCENARIO_SIM = "_skip_scenario_sim"
GATE_FLAG_RISK_REVIEW = "_skip_risk_review"


def build_gate_flags(profile: DepthProfile) -> dict[str, bool]:
    """M3：按 profile.nodes 计算 v2 模板门控旗标（True=跳过该段）。"""
    return {
        GATE_FLAG_DEBATE: NODE_DEBATE not in profile.nodes,
        GATE_FLAG_SCENARIO_SIM: NODE_SCENARIO_SIM not in profile.nodes,
        GATE_FLAG_RISK_REVIEW: NODE_RISK_REVIEW not in profile.nodes,
    }


def build_run_manifest(profile: DepthProfile) -> list:
    """M3：按档位生成环节运行清单（节点级 included/skipped）。

    由 workflow_api._prepare_inputs 写入 state["depth_run_manifest"]，
    report_saver 与前端时间线可读；被跳过节点以 skipped 态留痕，不静默消失。
    """
    manifest: list = []
    for stage, stage_label in _NODE_LABELS.items():
        status = STATUS_INCLUDED if stage in profile.nodes else STATUS_SKIPPED
        for node_id in _STAGE_GRAPH_NODES.get(stage, ()):
            manifest.append({
                "node_id": node_id,
                "stage": stage,
                "stage_label": stage_label,
                "status": status,
            })
    return manifest


def build_depth_report_notice(research_depth, manifest) -> str:
    """M3.2：报告末尾的档位/跳环节标注 + 跳过风险会审时的静态风险声明。

    合规底线：跳环节不跳免责——风险会审被跳过（快速档）时，静态风险声明
    与「不构成投资建议」必须常驻报告。skipped 环节显式标注，不静默消失。
    """
    entries = manifest or []
    skipped_labels: list = []
    risk_review_skipped = False
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("status") != STATUS_SKIPPED:
            continue
        label = entry.get("stage_label") or entry.get("stage") or ""
        if label and label not in skipped_labels:
            skipped_labels.append(label)
        if entry.get("stage") == NODE_RISK_REVIEW:
            risk_review_skipped = True
    if not skipped_labels and not risk_review_skipped:
        return ""
    depth_name = normalize_depth(research_depth)
    lines = ["", "", "---", "", f"## 🎚️ 分析档位说明（{depth_name}模式）"]
    if skipped_labels:
        lines += [
            "",
            f"本档不含：{'、'.join(skipped_labels)}（未执行，不产生对应结论）。",
        ]
    if risk_review_skipped:
        lines += [
            "",
            "## ⚠️ 静态风险声明",
            "",
            "本档未执行风险会审环节，以上内容不含风险会审结论，仅附静态风险提示：",
            "股市有风险，投资需谨慎。本报告由 AI 生成，不构成投资建议，据此操作风险自担。",
        ]
    return "\n".join(lines)


# ============================================================================
# M4 呈现与回归（前端档位说明 + 报告元数据，C7）
# ============================================================================


def build_depth_profile_meta(research_depth) -> dict:
    """M4.2：报告元数据——档位/环节清单/执行形态/实际轮数。

    由 app/utils/report_saver.py 落库到 analysis_reports.depth_profile，
    便于复盘与验收（设计文档 §5.3）。轮数为该档实际生效轮数（multi_agent
    路径；self_debate 形态为单节点单次调用，见执行形态字段）。
    """
    depth = normalize_depth(research_depth)
    profile = DEPTH_PROFILES[depth]
    return {
        "depth": depth,
        "level": profile.level,
        "manifest": build_run_manifest(profile),
        "debate_mode": profile.debate_mode,
        "risk_mode": profile.risk_mode,
        "debate_rounds": profile.debate_rounds,
        "risk_rounds": profile.risk_rounds,
    }


def build_profile_summaries() -> list:
    """M4.1：前端档位选择器差异说明数据源（环节清单/产出形态）。

    经后端 /api 透出（app/routers/analysis.py），前端不硬编码档位差异。
    """
    summaries: list = []
    for depth in DEPTH_NAMES:
        profile = DEPTH_PROFILES[depth]
        included = [label for node, label in _NODE_LABELS.items() if node in profile.nodes]
        skipped = [label for node, label in _NODE_LABELS.items() if node not in profile.nodes]
        summaries.append({
            "name": profile.name,
            "level": profile.level,
            "included_stages": included,
            "skipped_stages": skipped,
            "output_spec": profile.output_spec,
        })
    return summaries


# ============================================================================
# M5 记忆收编 + 结论快照 + 演化对照（C8，设计文档 §3.3）
# ============================================================================
# 产品判断：记忆是研究资产不是 agent 私产——按股票集中为「结论快照」
# （判断/依据/假设/失效条件，与研究日志四态、决策闭环备忘录同构），按股票+日期
# 版本化存档；上期快照作「对比基线」注入（对比与增量聚焦，不让 agent 照抄）；
# per-agent 向量记忆从分析提示词注入退位（写入/审核链路保留）。
# 五档记忆语义：快速 off 不读不写；基础/标准 snapshot 读写快照；深度/全面
# snapshot_diff 额外强制「结论演化对照」章节 + 优先检验上期待验证假设。

SNAPSHOT_SECTION_TITLE = "结论快照"
EVOLUTION_SECTION_TITLE = "结论演化对照"

# 「结论快照」章节行前缀（report_saver 解析快照用，与指令文案严格一致）
SNAPSHOT_FIELD_JUDGMENT = "判断"
SNAPSHOT_FIELD_EVIDENCE = "依据"
SNAPSHOT_FIELD_ASSUMPTIONS = "假设"
SNAPSHOT_FIELD_INVALIDATIONS = "失效条件"

# 快照/演化对照产出角色（整合层 + 报告层；快照以 trader/整合层输出为准）
_SNAPSHOT_OUTPUT_ROLE_AGENTS = _REPORT_ROLE_AGENTS | _INTEGRATION_ROLE_AGENTS

# 上期结论块注入白名单（M5.2）：research_manager / 辩论节点 / 整合节点
PREV_SNAPSHOT_AGENTS = frozenset(
    {
        "research_manager_v2",
        "bull_researcher_v2",
        "bear_researcher_v2",
        "research_self_debate_v2",
        "trader_v2",
    }
)

_SNAPSHOT_OUTPUT_REQUIREMENT = (
    f"- 结论快照要求：最终输出末尾附「{SNAPSHOT_SECTION_TITLE}」章节（系统据此沉淀"
    "下期对比基线），固定四行：\n"
    f"  - {SNAPSHOT_FIELD_JUDGMENT}：<方向>｜<评级>｜置信 <百分比或高/中/低>\n"
    f"  - {SNAPSHOT_FIELD_EVIDENCE}：<关键读数（口径，数据日期）>（逐条以「；」分隔）\n"
    f"  - {SNAPSHOT_FIELD_ASSUMPTIONS}：<本次判断依赖的假设>（逐条以「；」分隔）\n"
    f"  - {SNAPSHOT_FIELD_INVALIDATIONS}：<出现何种证据/读数时判断作废>（逐条以「；」分隔）"
)

_EVOLUTION_OUTPUT_REQUIREMENT = (
    f"- 结论演化对照要求：若上下文含【上期结论（对比基线）】块，在"
    f"「{SNAPSHOT_SECTION_TITLE}」章节前输出「{EVOLUTION_SECTION_TITLE}」章节："
    "与上期逐条对照判断/依据/假设/失效条件，变化必须归因（输入变化→列出变化的读数；"
    "输入未变→结论应保持，漂移须显式说明理由）；上期失效条件被触发的单独标注"
    "「失效条件命中」；与上期一致则写明「无变化」。无上期结论块时写明"
    "「首期分析，无对照」。上期待验证假设本次须优先检验并注明检验结果。"
)


def build_snapshot_requirements(profile: DepthProfile, agent_name: str = "") -> str:
    """M5：快照/演化对照产出要求（memory_mode != off 时给整合/报告角色）。

    快速档（off）不写快照无要求；基础/标准（snapshot）只要求「结论快照」章节；
    深度/全面（snapshot_diff）追加「结论演化对照」章节。
    """
    if profile.memory_mode == MEMORY_OFF:
        return ""
    if str(agent_name or "") not in _SNAPSHOT_OUTPUT_ROLE_AGENTS:
        return ""
    lines = [_SNAPSHOT_OUTPUT_REQUIREMENT]
    if profile.memory_mode == MEMORY_SNAPSHOT_DIFF:
        lines.append(_EVOLUTION_OUTPUT_REQUIREMENT)
    return "\n".join(lines)


def _format_snapshot_items(items: Any) -> str:
    """快照条目列表 → 「；」分隔文本；空列表如实写「暂无」。"""
    if isinstance(items, str):
        items = [items] if items.strip() else []
    values = [str(item).strip() for item in (items or []) if str(item).strip()]
    return "；".join(values) if values else "暂无"


def build_prev_snapshot_block(snapshot: dict) -> str:
    """M5.2：上期结论块（对比基线）——base.py 注入研究/辩论/整合环节提示词。

    用途是对比与增量聚焦（上期已查证事实不重复劳动、上期待验证假设优先检验），
    不是让 agent 照抄上期结论；结论以本次证据为准。
    """
    judgment = snapshot.get("judgment") or {}
    if isinstance(judgment, dict):
        judgment_text = str(judgment.get("text") or "").strip() or "暂无"
    else:
        judgment_text = str(judgment).strip() or "暂无"
    depth = snapshot.get("depth") or ""
    data_as_of = snapshot.get("data_as_of") or snapshot.get("snapshot_date") or "未知"
    snapshot_date = snapshot.get("snapshot_date") or "未知"
    lines = [
        f"【上期结论（对比基线）｜数据基准日 {data_as_of}｜{depth}档｜生成于 {snapshot_date}】",
        f"- {SNAPSHOT_FIELD_JUDGMENT}：{judgment_text}",
        f"- {SNAPSHOT_FIELD_EVIDENCE}：{_format_snapshot_items(snapshot.get('evidence'))}",
        f"- {SNAPSHOT_FIELD_ASSUMPTIONS}：{_format_snapshot_items(snapshot.get('assumptions'))}",
        f"- {SNAPSHOT_FIELD_INVALIDATIONS}：{_format_snapshot_items(snapshot.get('invalidations'))}",
        "（用途：对比与增量聚焦——上期已查证的事实不重复劳动，上期假设与失效条件"
        "优先检验；不要照抄上期结论，结论以本次证据为准。）",
    ]
    return "\n".join(lines)
