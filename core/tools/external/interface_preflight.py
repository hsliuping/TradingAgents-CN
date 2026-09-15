# -*- coding: utf-8 -*-
"""外部接口预检 — 规格确认阶段的连通性验证 + 查询参数差分测试。

背景：外部接口集成（目录外数据源）在代码生成前无法验证接口规格是否可用，
接口地址/请求头错误要等到沙箱执行阶段（每轮代码生成 2-4 分钟）才暴露，
浪费大量迭代时间。预检在规格确认时用沙箱真实调用一次接口，把
「接口不可达/404/参数错误」提前到确认页。

差分测试：接口对未知查询参数通常直接忽略（仍返回 200 + 全量数据），
「HTTP 200」并不证明该参数有过滤语义。预检对 spec 中不在用户 URL
查询串里的参数（如 brand_name）做差分调用：
- 两次响应签名相同 → 该参数被接口忽略 → 代码必须拉全量后本地过滤
- 签名变化 → 该参数疑似服务端过滤生效 → 可作为 URL 查询参数

用法（服务层）：
    probe = build_interface_probe(spec)          # 从 spec.constraints 提取 URL 构造探测代码
    sandbox = SandboxRunner().run(probe.code, spec, test_input=probe.params)
    verdict = interpret_probe_result(sandbox)    # verified / warning / failed + 消息
"""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl

# ASCII URL 字符集（与 static_validator 的接口 URL 校验保持一致：
# 中文紧贴 URL 时截断，避免把「rank_data发起」这类文本当 URL）
_URL_RE = re.compile(r"https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+")

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _find_interface_urls(spec: Any) -> List[str]:
    """提取 constraints 中所有 URL 匹配原文（含查询串，按出现顺序）"""
    constraint_text = "\n".join(str(c) for c in (getattr(spec, "constraints", None) or []))
    return [m.group(0) for m in _URL_RE.finditer(constraint_text)]


def _is_api_url(url: str) -> bool:
    """域名后至少 1 级路径，排除纯域名引用（如 Referer 根域名）"""
    return len([s for s in url.split("//", 1)[-1].split("/") if s]) >= 2


def _extract_interface_url(spec: Any) -> Optional[str]:
    """从 spec.constraints 提取接口 URL（含 URL 的约束行，取第一个；排除纯域名）"""
    for raw in _find_interface_urls(spec):
        url = raw.split("?")[0].rstrip(".,;:")
        if _is_api_url(url):
            return url
    return None


def _extract_documented_params(spec: Any) -> Dict[str, str]:
    """提取「文档化」查询参数——区分接口真实参数与业务过滤参数的依据。

    两个来源（按优先级）：
    1. 【接口规格】接口查询参数（用户 URL 原文查询串）约束——需求分析阶段
       从用户对话提取写入（URL 契约约束只保留基础地址，查询串单列）
    2. constraints 中带查询串的完整 URL（LLM 直接写入的原文 URL）
    """
    constraint_text = "\n".join(str(c) for c in (getattr(spec, "constraints", None) or []))
    # 来源 1：专门的文档化查询参数约束
    m = re.search(
        r"接口查询参数（用户 URL 原文查询串）[:：]\s*([A-Za-z0-9\-._~%&=]+)", constraint_text
    )
    if m:
        try:
            pairs = parse_qsl(m.group(1), keep_blank_values=True)
        except Exception:
            pairs = []
        if pairs:
            return dict(pairs)
    # 来源 2：constraints 中带查询串的完整 URL
    for raw in _find_interface_urls(spec):
        if "?" not in raw:
            continue
        url = raw.split("?")[0].rstrip(".,;:")
        if not _is_api_url(url):
            continue
        query = raw.split("?", 1)[1].rstrip(".,;:")
        try:
            pairs = parse_qsl(query, keep_blank_values=True)
        except Exception:
            continue
        if pairs:
            return dict(pairs)
    return {}


def _static_eval(node: Any, constants: Dict[str, Any]) -> Any:
    """对 AST 表达式做最小化静态求值，求不出返回 None。

    支持：字面量、模块/局部常量名（PAGE_SIZE = 100）、str(x) 单层包装。
    函数入参（month/offset 等运行期变量）一律返回 None——不猜默认值。
    """
    import ast

    if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float, bool)):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.Call):
        # 仅支持 str(x)/int(x) 这类单层字面量包装
        if isinstance(node.func, ast.Name) and node.func.id in ("str", "int", "float"):
            if len(node.args) == 1:
                inner = _static_eval(node.args[0], constants)
                if inner is None:
                    return None
                try:
                    return {"str": str, "int": int, "float": float}[node.func.id](inner)
                except (ValueError, TypeError):
                    return None
    return None


def _extract_query_params_from_parent_code(code: str) -> Dict[str, Any]:
    """从父版本代码中提取 requests 请求实际使用的查询参数及其静态值（AST）。

    升级场景：接口查询参数约束是从父代码提取的裸 URL（无查询串），
    文档化参数来源为空。父代码是多轮验证过的实现，其 requests 调用
    params 中的键就是接口真实查询参数——以此为基线，才能把新 spec
    臆造的业务参数正确划入差分测试。

    只收集真正流入 `params=` 的字典（内联字典 / 赋给变量后再传入
    params 的字典）。父代码里的请求头字典、别名映射表、输出结果
    字典等一律排除——曾因收集全部字典赋值，把 User-Agent/Referer/
    品牌别名/输出字段全混进预检基线。

    值来源全部是代码里的客观事实（字面量/常量赋值），不维护任何
    参数名→默认值的写死映射；运行期变量（函数入参）求值为 None，
    调用方据此跳过该参数（HTTP 查询参数通常可选，服务端有缺省行为）。

    Returns:
        有序 {参数名: 静态值或 None}
    """
    import ast

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {}

    ordered: Dict[str, Any] = {}

    def _collect(dict_node: ast.Dict) -> None:
        for k, v in zip(dict_node.keys, dict_node.values):
            if isinstance(k, ast.Constant) and isinstance(k.value, str) and k.value not in ordered:
                # 值的静态求值延后（常量表在全部节点收集后最完整）
                ordered[k.value] = v

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in getattr(node, "keywords", None) or []:
            if kw.arg != "params":
                continue
            # 内联 params={...}
            if isinstance(kw.value, ast.Dict):
                _collect(kw.value)
            # params=p（p 是变量）→ 收集 p = {...} 的赋值字典
            elif isinstance(kw.value, ast.Name):
                for sub in ast.walk(tree):
                    if (
                        isinstance(sub, ast.Assign)
                        and isinstance(sub.value, ast.Dict)
                        and any(
                            isinstance(t, ast.Name) and t.id == kw.value.id
                            for t in sub.targets
                        )
                    ):
                        _collect(sub.value)

    # 第 2 遍：常量表（PAGE_SIZE = 100 等），供静态求值
    constants: Dict[str, Any] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            val = _static_eval(node.value, constants)
            if val is not None:
                constants[node.targets[0].id] = val

    return {k: _static_eval(v, constants) for k, v in ordered.items()}


def build_interface_probe(spec: Any, parent_code: str = "") -> Optional[Dict[str, Any]]:
    """构造接口预检探测代码。

    Returns:
        {"code": 探测函数代码（函数名 = spec.tool_id，**kwargs 签名）,
         "params": 传给沙箱的请求参数（优先 spec.test_input，其次参数默认值）,
         "url": 探测的接口地址,
         "baseline_params": 基线请求参数（文档化查询参数 + test_input 对其的覆盖）,
         "suspected_filters": 疑似业务过滤参数名（不在文档化查询参数中，做差分测试）}
        无接口 URL（非外部接口需求/约束缺失）时返回 None。
    """
    url = _extract_interface_url(spec)
    if not url:
        return None

    # Referer：约束文本明确要求时带上，默认用接口同源根路径
    constraint_text = "\n".join(str(c) for c in (getattr(spec, "constraints", None) or []))
    origin = url.split("//", 1)[0] + "//" + url.split("//", 1)[-1].split("/", 1)[0] + "/"
    headers = {"User-Agent": _DEFAULT_UA}
    if "Referer" in constraint_text or "referer" in constraint_text:
        headers["Referer"] = origin

    # 请求参数：优先 test_input，其次参数默认值
    params: Dict[str, Any] = dict(getattr(spec, "test_input", None) or {})
    if not params:
        for p in getattr(spec, "parameters", None) or []:
            default = getattr(p, "default", None)
            if default is not None:
                params[getattr(p, "name", "")] = default

    # 差分测试分组：文档化查询参数为基线；spec 中不在文档化查询里的参数
    # （通常是需求分析为业务过滤造的参数，如 brand_name）做差分验证
    documented = _extract_documented_params(spec)
    # 升级场景：约束里只有从父代码提取的裸 URL（无查询串）时，
    # 从父版本代码 AST 提取其 requests 实际使用的查询参数作为文档化参数
    if not documented and parent_code:
        documented = _extract_query_params_from_parent_code(parent_code)

    if documented:
        baseline = {}
        for k, doc_v in documented.items():
            if k in params and params[k] not in (None, ""):
                # spec 同名参数值优先（test_input/默认值/父代码静态值）
                baseline[k] = params[k]
            elif doc_v not in (None, ""):
                # 静态可求值来源：URL 查询串示例值 / 父代码字面量或常量
                baseline[k] = doc_v
            # 求不出静态值（运行期变量）且 spec 无同名参数 → 不发该参数，
            # 不写死默认值：HTTP 查询参数通常可选，服务端有缺省行为；
            # 若该参数必填，预检会如实返回失败，而不是靠猜蒙混过关
        suspected = {k: v for k, v in params.items() if k not in documented}
    else:
        # 用户 URL 未带查询串：无从区分文档参数与业务参数，全部作为基线（不做差分）
        baseline = dict(params)
        suspected = {}

    func_name = getattr(spec, "tool_id", "interface_probe")
    code = f'''def {func_name}(**kwargs):
    """接口预检（自动生成的探测代码）：真实调用外部接口验证连通性与参数语义"""
    import requests

    url = {url!r}
    headers = {headers!r}
    baseline = {baseline!r}
    filter_values = {suspected!r}

    def _call(p):
        try:
            resp = requests.get(url, params=p, headers=headers, timeout=10)
            out = {{"http_status": resp.status_code,
                    "content_type": resp.headers.get("content-type", "")}}
            body = resp.text or ""
            out["body_head"] = body[:300]
            try:
                data = resp.json()
                out["json_ok"] = True
                if isinstance(data, dict):
                    out["json_keys"] = [str(k) for k in list(data.keys())[:12]]
                    inner = data.get("data")
                    if isinstance(inner, dict):
                        for key in ("list", "items", "rows", "data"):
                            v = inner.get(key)
                            if isinstance(v, list):
                                out["data_items"] = len(v)
                                if v and isinstance(v[0], dict):
                                    out["first_item_keys"] = [str(k) for k in list(v[0].keys())[:15]]
                                break
                    elif isinstance(inner, list):
                        out["data_items"] = len(inner)
                elif isinstance(data, list):
                    out["data_items"] = len(data)
            except Exception:
                out["json_ok"] = False
            return out
        except Exception as exc:
            return {{"error": type(exc).__name__ + ": " + str(exc)}}

    overrides = dict(kwargs or {{}})
    base_params = dict(baseline)
    for k, v in overrides.items():
        if k not in filter_values:
            base_params[k] = v
    base_out = _call(base_params)

    result = {{"probe": True,
               "http_status": base_out.get("http_status"),
               "content_type": base_out.get("content_type"),
               "body_head": base_out.get("body_head"),
               "json_ok": base_out.get("json_ok", False),
               "json_keys": base_out.get("json_keys"),
               "data_items": base_out.get("data_items"),
               "first_item_keys": base_out.get("first_item_keys")}}
    if base_out.get("error"):
        result["error"] = base_out["error"]
        return result

    # 差分测试：基线 vs 基线+疑似过滤参数，比较响应签名。
    # 签名只用结构稳定项（状态码/条数/字段名），不比较数据值——
    # 排行榜等实时数据的值在两次调用间自然波动，比较值会把「被忽略」误判成「过滤生效」
    if filter_values and base_out.get("http_status") == 200 and base_out.get("data_items"):
        full_params = dict(base_params)
        for k, v in filter_values.items():
            full_params[k] = overrides.get(k, v)
        full_out = _call(full_params)
        sig_b = (base_out.get("http_status"), base_out.get("data_items"),
                 tuple(base_out.get("first_item_keys") or []))
        sig_f = (full_out.get("http_status"), full_out.get("data_items"),
                 tuple(full_out.get("first_item_keys") or []))
        tested = sorted(filter_values.keys())
        if sig_b == sig_f:
            result["ignored_params"] = tested
        else:
            result["filter_effective_params"] = tested
        result["filter_test"] = {{
            "tested": tested,
            "baseline_items": base_out.get("data_items"),
            "with_filter_items": full_out.get("data_items"),
            "with_filter_status": full_out.get("http_status"),
        }}
    return result
'''
    return {
        "code": code,
        "params": params,
        "url": url,
        "baseline_params": baseline,
        "suspected_filters": sorted(suspected.keys()),
    }


def build_preflight_facts_text(preflight: Any) -> str:
    """把预检结论渲染为面向 LLM 的【接口实测事实】区块文本。

    同时供两处注入：
    - CodeGenerator user prompt（pipeline_tool 内部每轮代码生成）
    - Agent Loop 协调者任务 prompt（协调者据此写反馈，不会给出
      「把业务过滤参数拼进 URL」这类错误指导）
    无预检结果时返回空串。
    """
    if not isinstance(preflight, dict) or not preflight.get("url"):
        return ""

    lines = [
        "【🔍 接口实测事实（预检阶段已真实调用过该接口验证）】",
        f"- 实测 URL: {preflight.get('url')}",
    ]
    http_status = preflight.get("http_status")
    if http_status is not None:
        lines.append(f"- HTTP 状态: {http_status}")

    sample_fields = preflight.get("sample_fields") or []
    data_items = preflight.get("data_items")
    if preflight.get("status") == "verified":
        if data_items is not None:
            lines.append(f"- 实测返回数据条数: {data_items}")
        if sample_fields:
            lines.append(
                "- 返回条目的真实字段（以此为准，严禁臆造）: "
                + ", ".join(str(f) for f in sample_fields)
            )
        probed_params = preflight.get("probed_params") or {}
        if probed_params:
            params_desc = ", ".join(
                f"{k}={v!r}" for k, v in list(probed_params.items())[:10]
            )
            lines.append(f"- 实测验证可用的查询参数（已拼进 URL 请求成功）: {params_desc}")
        ignored_params = [str(p) for p in (preflight.get("ignored_params") or []) if p]
        if ignored_params:
            lines.append(
                "- ⚠️ 以下参数已实测被接口忽略（传入与否返回完全相同的数据）: "
                + "、".join(ignored_params)
            )
        # 数据边界判定（数据驱动，无写死关键词）：对每个被忽略的业务过滤参数，
        # 检查返回字段中是否存在语义对应的字段（token 互相包含）。
        # 匹配不上 → 该过滤概念在接口数据中无承载字段，必须声明数据边界——
        # 历史教训：LLM 为补齐映射臆造新端点全部 404，浪费整轮迭代。
        # 参数名与字段名全部来自实测，换一个数据源/换一种业务照样成立。
        unmatched_filters: List[str] = []
        for p in ignored_params:
            token = str(p).lower()
            if not any(token in str(f).lower() or str(f).lower() in token
                       for f in sample_fields):
                unmatched_filters.append(str(p))
        if unmatched_filters:
            lines.append(
                f"- ⚠️ 实测返回字段中不存在与 {'、'.join(unmatched_filters)} 对应的字段"
                "（字段清单里没有名称相关的字段）：基于该条件的过滤只能靠返回数据中的"
                "名称类字段做近似匹配，且可能覆盖不全；无法完全覆盖时必须在输出中"
                "明确说明「接口数据不含相关字段，结果可能不完整」，严禁臆造新接口端点"
            )
        server_filters = [str(p) for p in (preflight.get("server_filter_params") or []) if p]
        if server_filters:
            lines.append(
                "- 以下业务参数实测会改变接口返回（服务端过滤疑似生效，可作 URL 查询参数）: "
                + "、".join(server_filters)
            )
        lines += [
            "",
            "实测约束（必须遵守）：",
            "- 代码中引用的接口返回字段必须来自上方实测真实字段清单，严禁臆造字段名",
            "- 查询参数只允许使用实测验证可用的查询参数及规格明确要求的参数",
        ]
        if ignored_params:
            lines.append(
                f"- {'、'.join(ignored_params)} 已实测被接口忽略，"
                "严禁拼进 URL；对应的业务过滤必须先拉取接口数据"
                "（必要时用实测验证可用的查询参数拉全量），再按返回字段在本地实现"
            )
        else:
            lines.append(
                "- 严禁把业务过滤条件臆造为接口查询参数拼进 URL；"
                "业务上需要的过滤/排序/聚合若不在实测查询参数中，必须先拉取接口数据"
                "（必要时用实测验证可用的查询参数拉全量），再用返回字段在本地实现"
            )
    else:
        # warning：接口可达但未识别到数据条目或非 JSON，结构未探明
        lines += [
            f"- 预检结论: {preflight.get('message') or '接口可达但数据结构未探明'}",
            "",
            "实测约束（必须遵守）：",
            "- 接口可达但数据结构未探明：解析响应时先取 JSON 顶层键定位数据列表，"
            "严禁按训练记忆臆造字段名或数据结构",
            "- 严禁把业务过滤条件臆造为接口查询参数拼进 URL；"
            "此类过滤必须拉取数据后在本地用返回字段实现",
        ]
    return "\n".join(lines) + "\n"


def interpret_probe_result(sandbox_result: Any) -> Dict[str, Any]:
    """把沙箱执行结果解读为预检结论。

    Returns:
        {"status": "verified" | "warning" | "failed", "message": 展示消息, ...细节}
        差分测试产出：ignored_params（被接口忽略，须本地过滤）/
        server_filter_params（疑似服务端过滤生效，可拼 URL）
    """
    if not getattr(sandbox_result, "success", False):
        return {
            "status": "failed",
            "message": f"预检脚本执行失败: {getattr(sandbox_result, 'error', None) or '未知错误'}",
        }
    output = getattr(sandbox_result, "output", None)
    if not isinstance(output, dict):
        return {"status": "failed", "message": "预检未返回结构化结果"}

    if output.get("error"):
        return {"status": "failed", "message": f"接口不可达: {output['error']}"}

    status_code = output.get("http_status")
    if status_code != 200:
        hints = {
            404: "接口路径不存在（404）——请核对 URL 路径拼写",
            403: "接口拒绝访问（403）——可能需要额外请求头或鉴权",
            401: "接口需要认证（401）——请补充鉴权方式",
            429: "接口限流（429）——稍后重试或降低调用频率",
        }
        hint = hints.get(status_code, f"接口返回异常状态码 {status_code}")
        return {"status": "failed", "http_status": status_code, "message": hint}

    data_items = output.get("data_items")
    if data_items:
        verdict = {
            "status": "verified",
            "http_status": 200,
            "data_items": data_items,
            "sample_fields": (output.get("first_item_keys") or [])[:8],
            "message": f"接口连通性已验证：HTTP 200，返回 {data_items} 条数据",
        }
    elif output.get("json_ok"):
        verdict = {
            "status": "warning",
            "http_status": 200,
            "message": "接口可达（HTTP 200，JSON 响应），但未识别到数据条目——可能是查询参数语义问题，建议核对参数",
        }
    else:
        verdict = {
            "status": "warning",
            "http_status": 200,
            "message": "接口可达（HTTP 200），但返回非 JSON 内容——可能是网页或被反爬拦截，请核对请求头要求",
        }

    # 差分测试结论（基线有数据时才会产出）
    ignored = [str(p) for p in (output.get("ignored_params") or []) if p]
    if ignored:
        verdict["ignored_params"] = ignored
        verdict["message"] += (
            f"；实测 {('、'.join(ignored))} 参数被接口忽略（不影响返回），"
            "对应过滤需在代码中本地实现"
        )
    effective = [str(p) for p in (output.get("filter_effective_params") or []) if p]
    if effective:
        verdict["server_filter_params"] = effective
        verdict["message"] += f"；实测 {('、'.join(effective))} 参数会改变接口返回（服务端过滤疑似生效）"
    return verdict
