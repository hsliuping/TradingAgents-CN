# -*- coding: utf-8 -*-
"""升级补丁模式 — Skill 迭代升级的「父契约 + delta」规格生成。

背景：升级会话曾从对话文本**重新生成全量 spec**，规格 LLM 没读过父版本
代码与契约，凭升级需求一句话重新发明一切——曾把父版本多轮验证的
`rank_data_type: int = 11`（全国月度销量榜）重写成字符串
「月度销量榜」直接发给接口，接口静默回退到热度榜，业务校验判
「月销 102 万辆不合理」，修复循环按错误 spec 打回正确代码，死循环。

对齐主流编程 agent 的 edit-apply 模型（原代码是基座，LLM 只输出增量，
系统确定性套用）：
1. LLM 先读懂父版本（完整契约 + 已验证代码）——读后写
2. 再理解升级需求，定位变更点
3. **只输出补丁（delta）**——未提及的字段没有输出通道，结构上杜绝重写
4. apply_upgrade_patch 确定性套用：父契约 + 补丁 → 新 spec
5. 变更点清单（change_points）随 spec.metadata 返回，确认页 diff 式展示

用法（requirement_analyzer）：
    prompt = build_upgrade_patch_prompt(parent_contract, conversation)
    raw = llm.chat(prompt)                # LLM 输出补丁 JSON
    spec = apply_upgrade_patch(parent_contract, json.loads(raw))

parent_contract 结构（服务层从 external_skills 加载并计算版本号）：
    {
        "tool_id": 父版本 tool_id,
        "root_tool_id": 系列根 tool_id（parent_skill_id or tool_id）,
        "new_tool_id": "{root}_v{N}"（按 DB 版本序计算，与 _save_skill 一致）,
        "new_version": N,
        "display_name"/"description"/"category"/"data_source": ...,
        "parameters": [SkillParameter dict, ...],
        "expected_output": {"type", "fields", "description"},
        "constraints": [str, ...],
        "test_input": {...},
        "code": 父版本完整已验证代码（仅供 LLM 阅读，不进 spec）,
    }
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from core.tools.external.skill_spec import (
    ExpectedOutput,
    SkillParameter,
    SkillSpec,
    ValidationCheck,
)

# 补丁 JSON 里允许出现的参数字段（防止 LLM 塞进无关键）
_PARAM_FIELDS = {"name", "type", "description", "required", "default", "enum"}


def _strip_version_suffix(display_name: str) -> str:
    """去掉显示名尾部的版本后缀（“ v2”/“ v3”），再加新后缀。"""
    return re.sub(r"\s*v\d+$", "", (display_name or "").strip())


def build_upgrade_patch_prompt(parent_contract: Dict[str, Any], conversation: str) -> str:
    """构造升级补丁生成 prompt：父契约 + 父代码 + 升级对话 → 只输出 delta。"""
    # 契约部分给 LLM 看（code 单列，避免契约 JSON 过大）
    contract_view = {
        k: parent_contract.get(k)
        for k in (
            "tool_id", "display_name", "description", "category", "data_source",
            "parameters", "expected_output", "constraints", "test_input",
        )
    }
    code = str(parent_contract.get("code") or "").strip()

    return (
        "你是 Skill 升级补丁生成器。与从零写规格不同，你的任务是："
        "先读懂父版本（契约 + 已验证代码），再理解用户的升级需求，"
        "最后**只输出需要变更的部分（补丁）**。\n\n"
        "## 第一步：读懂父版本（内化理解，无需输出）\n\n"
        "### 父版本契约（多轮实测验证的事实，不是参考建议）\n"
        f"```json\n{json.dumps(contract_view, ensure_ascii=False, indent=1)}\n```\n\n"
        "### 父版本已验证代码\n"
        f"```python\n{code}\n```\n\n"
        "## 第二步：理解升级需求\n\n"
        f"对话内容:\n{conversation}\n\n"
        "## 第三步：输出补丁（只包含变更，未提及的内容一律原样继承）\n\n"
        "【补丁规则 — 极其重要】\n"
        "1. **你没有权限重写父版本契约**：参数定义（名称/类型/默认值/取值语义）、"
        "接口约束（URL/请求头/取值要求，如「rank_data_type 需为 11」）是多轮验证的事实，"
        "除非升级需求明确要求修改，否则必须原样继承，一个字都不许改\n"
        "2. 输出字段同理：只增删本次升级涉及的字段，其余字段名保持原样\n"
        "3. remove 类操作必须极其谨慎：仅当用户明确要求删除时使用\n"
        "4. change_points 是给用户看的变更清单，逐条对应实际改动，"
        "让用户一眼看懂「这次升级改了什么、其余全部继承」\n"
        "5. 若升级需求与父版本已验证行为冲突（如要求改变参数取值语义），"
        "照做但在 constraint_additions 中说明，并列入 change_points\n\n"
        "请只输出 JSON（不要其他内容）：\n"
        "{\n"
        '  "upgrade_summary": "一句话总结本次升级",\n'
        '  "change_points": ["输出字段新增 price_range（厂商指导价区间）", "..."],\n'
        '  "description": "可选——仅当功能定位变化时提供新 description，否则省略该键",\n'
        '  "parameter_changes": {\n'
        '    "add": [{"name": "new_param", "type": "string", "description": "...", "required": false}],\n'
        '    "modify": [{"name": "已有参数名", "仅列出需要修改的字段": "..."}],\n'
        '    "remove": []\n'
        "  },\n"
        '  "output_field_changes": {"add": ["price_range"], "remove": []},\n'
        '  "output_description": "可选——仅当输出含义变化时提供",\n'
        '  "constraint_additions": ["本次升级新增的行为约束"],\n'
        '  "test_input_updates": {}\n'
        "}"
    )


def _apply_parameter_changes(
    parent_params: List[Dict[str, Any]],
    changes: Optional[Dict[str, Any]],
) -> Tuple[List[SkillParameter], List[str]]:
    """套用参数补丁：add 追加 / modify 只合并列出的字段 / remove 删除。

    modify 是关键防线：补丁只提供要改的字段（如 description），
    其余字段（type/default/required）从父版本原样保留——
    LLM 没有输出通道整体重写一个参数。
    """
    merged: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for p in parent_params or []:
        name = str(p.get("name") or "").strip()
        if name and name not in merged:
            merged[name] = dict(p)
            order.append(name)

    notes: List[str] = []
    changes = changes or {}

    for entry in changes.get("remove") or []:
        name = str(entry).strip()
        if name in merged:
            del merged[name]
            order.remove(name)
            notes.append(f"参数删除 {name}")

    for entry in changes.get("modify") or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if not name or name not in merged:
            continue
        # 只合并合法字段且值非 None，其余（含 name 本身）不动
        touched = [
            k for k in entry
            if k != "name" and k in _PARAM_FIELDS and entry[k] is not None
        ]
        for k in touched:
            merged[name][k] = entry[k]
        if touched:
            notes.append(f"参数修改 {name}（{', '.join(sorted(touched))}）")

    for entry in changes.get("add") or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        clean = {k: entry[k] for k in entry if k in _PARAM_FIELDS}
        if name in merged:
            # 同名参数已存在：按 modify 合并（LLM 应该用 modify，这里兜底）
            for k, v in clean.items():
                if k != "name" and v is not None:
                    merged[name][k] = v
            notes.append(f"参数合并 {name}")
        else:
            merged[name] = clean
            order.append(name)
            notes.append(f"参数新增 {name}")

    params = []
    for name in order:
        try:
            params.append(SkillParameter(**merged[name]))
        except Exception:
            continue
    return params, notes


def _apply_output_changes(
    parent_fields: List[str],
    changes: Optional[Dict[str, Any]],
) -> Tuple[List[str], List[str]]:
    """套用输出字段补丁：+add -remove，保序去重。"""
    fields = [str(f) for f in (parent_fields or []) if str(f).strip()]
    changes = changes or {}
    remove = {str(f) for f in (changes.get("remove") or [])}
    notes: List[str] = []
    if remove:
        fields = [f for f in fields if f not in remove]
        notes.append(f"输出字段删除 {', '.join(sorted(remove))}")
    added = []
    for f in (changes.get("add") or []):
        f = str(f).strip()
        if f and f not in fields:
            fields.append(f)
            added.append(f)
    if added:
        notes.append(f"输出字段新增 {', '.join(added)}")
    return fields, notes


def apply_upgrade_patch(
    parent_contract: Dict[str, Any], patch: Dict[str, Any]
) -> SkillSpec:
    """确定性套用补丁：父契约 + delta → 新 SkillSpec。

    补丁没提到的字段全部从父版本继承（参数/约束/输出/测试输入），
    tool_id/display_name 按服务层计算的版本号确定。
    变更点清单写入 spec.metadata.upgrade_change_points（确认页展示）。
    """
    root_tool_id = str(parent_contract.get("root_tool_id") or parent_contract.get("tool_id") or "")
    new_tool_id = str(parent_contract.get("new_tool_id") or f"{root_tool_id}_v2")
    new_version = int(parent_contract.get("new_version") or 2)

    parent_params = list(parent_contract.get("parameters") or [])
    parameters, param_notes = _apply_parameter_changes(
        parent_params, patch.get("parameter_changes")
    )

    parent_output = dict(parent_contract.get("expected_output") or {})
    parent_fields = list(parent_output.get("fields") or [])
    fields, field_notes = _apply_output_changes(
        parent_fields, patch.get("output_field_changes")
    )
    output_desc = str(patch.get("output_description") or parent_output.get("description") or "")

    # 约束：父版本约束原样继承（含接口 URL/取值要求），再追加补丁新增
    constraints: List[str] = [str(c) for c in (parent_contract.get("constraints") or []) if str(c).strip()]
    if root_tool_id:
        iter_note = f"本 Skill 是 {root_tool_id} 的迭代优化版本"
        if iter_note not in constraints:
            constraints.append(iter_note)
    for c in patch.get("constraint_additions") or []:
        c = str(c).strip()
        if c and c not in constraints:
            constraints.append(c)

    # 测试输入：父版本 + 补丁覆盖
    test_input = dict(parent_contract.get("test_input") or {})
    updates = patch.get("test_input_updates")
    if isinstance(updates, dict):
        test_input.update(updates)

    # 变更点清单：优先用 LLM 给的 change_points，缺失时用套用过程的实际记录兜底
    change_points = [str(c) for c in (patch.get("change_points") or []) if str(c).strip()]
    if not change_points:
        change_points = param_notes + field_notes
    upgrade_summary = str(patch.get("upgrade_summary") or "").strip()

    # 验收检查从最终输出字段推导（存在性检查：升级字段可能合法为空串，如 price_range）
    validation_checks: List[ValidationCheck] = [
        ValidationCheck(
            name="status_success", description="输出状态必须成功",
            required=True, check_type="status_success", rule_level="output",
            blocking=True, value_path="output", forbid_null=False,
        )
    ]
    for f in fields:
        validation_checks.append(
            ValidationCheck(
                name=f"required_field:{f}", description=f"成功输出时 {f} 字段存在",
                required=True, check_type="required_field", rule_level="data",
                blocking=True, field=f, value_path="data", forbid_null=False,
            )
        )

    parent_display = str(parent_contract.get("display_name") or "")
    display_name = f"{_strip_version_suffix(parent_display)} v{new_version}"

    description = str(patch.get("description") or parent_contract.get("description") or "")

    return SkillSpec(
        tool_id=new_tool_id,
        display_name=display_name,
        description=description,
        category=str(parent_contract.get("category") or "utility"),
        data_source=str(parent_contract.get("data_source") or ""),
        parameters=parameters,
        expected_output=ExpectedOutput(
            type=str(parent_output.get("type") or "list[dict]"),
            fields=fields,
            description=output_desc,
        ),
        validation_checks=validation_checks,
        constraints=constraints,
        test_input=test_input,
        metadata={
            "upgrade_mode": "patch",
            "upgrade_parent_tool_id": root_tool_id,
            "upgrade_change_points": change_points,
            "upgrade_summary": upgrade_summary,
        },
        parent_skill_id=root_tool_id,
        version=new_version,
    )


def parent_contract_to_json(contract: Dict[str, Any], max_code_chars: int = 12000) -> str:
    """父契约摘要（降级路径注入旧版全量规格生成 prompt 用）。"""
    view = {
        k: contract.get(k)
        for k in ("tool_id", "display_name", "description", "parameters",
                  "expected_output", "constraints", "test_input")
    }
    code = str(contract.get("code") or "")
    if len(code) > max_code_chars:
        code = code[:max_code_chars] + "\n... (截断)"
    view["code"] = code
    return json.dumps(view, ensure_ascii=False, indent=1)
