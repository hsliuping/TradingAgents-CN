import asyncio
import json
from types import SimpleNamespace


def test_determine_phase_resets_to_confirmation_for_new_request_after_result():
    from app.services.intelligent_screening_service import IntelligentScreeningService

    service = IntelligentScreeningService(db=object())
    history = [
        {"role": "assistant", "phase": "result", "content": "上一轮已给出筛选结果"},
    ]

    phase = service._determine_phase(history, "帮我选几只高分红的股票")

    assert phase == "confirmation"


def test_select_phase_history_drops_stale_history_for_fresh_confirmation():
    from app.services.intelligent_screening_service import IntelligentScreeningService

    service = IntelligentScreeningService(db=object())
    history = [
        {"role": "user", "content": "执行筛选方案"},
        {"role": "assistant", "phase": "result", "content": "上一轮结果 JSON"},
        {"role": "user", "content": "为什么财报期还是 20250930"},
        {"role": "assistant", "phase": "result", "content": "这是数据口径解释"},
    ]

    selected = service._select_phase_history(history, "confirmation", "帮我选几只高分红的股票")

    assert selected == []


def test_select_phase_history_keeps_latest_planning_only_for_result_execution():
    from app.services.intelligent_screening_service import IntelligentScreeningService

    service = IntelligentScreeningService(db=object())
    history = [
        {"role": "user", "content": "帮我选几只高分红的股票"},
        {"role": "assistant", "phase": "confirmation", "content": "需求分析"},
        {"role": "user", "content": "采纳建议后筛选"},
        {"role": "assistant", "phase": "planning", "content": "严格执行 dividend_yield>=5, pe_ttm<=15"},
        {"role": "user", "content": "执行筛选方案"},
        {"role": "assistant", "phase": "result", "content": "旧结果和超时说明"},
        {"role": "user", "content": "为什么财报期还是 20250930"},
        {"role": "assistant", "phase": "result", "content": "旧的财报期解释"},
    ]

    selected = service._select_phase_history(history, "result", "执行筛选方案")

    assert selected == [history[3]]


def test_select_phase_history_keeps_latest_result_when_user_references_current_stocks():
    from app.services.intelligent_screening_service import IntelligentScreeningService

    service = IntelligentScreeningService(db=object())
    history = [
        {"role": "assistant", "phase": "planning", "content": "筛选计划"},
        {"role": "assistant", "phase": "result", "content": "当前推荐的 5 只股票"},
    ]

    selected = service._select_phase_history(history, "result", "把这5只加入股票关注列表")

    assert selected == history


def test_extract_locked_execution_plan_keeps_planning_parameters():
    from app.services.intelligent_screening_service import IntelligentScreeningService

    service = IntelligentScreeningService(db=object())
    history = [
        {
            "role": "assistant",
            "phase": "planning",
            "content": (
                "### 工具调用\n"
                "**步骤 1**：调用 `screen_stocks_by_criteria`\n"
                "- `conditions`: `[{\"field\": \"dividend_yield\", \"operator\": \">=\", \"value\": 5}, {\"field\": \"pe_ttm\", \"operator\": \"<=\", \"value\": 15}]`\n"
                "- `limit`: 50\n"
                '- `order_by_field`: "dividend_yield"\n'
                '- `order_direction`: "desc"\n\n'
                "**步骤 2**：调用 `batch_check_profit_consistency`\n"
                "- `years`: 3\n"
                "- `threshold_cv`: 0.3\n"
            ),
        }
    ]

    plan = service._extract_locked_execution_plan(history)

    assert plan is not None
    assert json.loads(plan["screen"]["conditions_json"])[1]["field"] == "pe_ttm"
    assert plan["screen"]["limit"] == 50
    assert plan["screen"]["order_by_field"] == "dividend_yield"
    assert plan["batch"]["years"] == 3
    assert plan["batch"]["threshold_cv"] == 0.3


def test_run_locked_result_execution_uses_locked_plan_arguments(monkeypatch):
    from app.services import intelligent_screening_service as service_module

    service = service_module.IntelligentScreeningService(db=object())
    calls = []

    async def fake_execute_screening_query(raw_conditions, limit, order_by_field, order_direction):
        calls.append(("screen_query", {
            "raw_conditions": raw_conditions,
            "limit": limit,
            "order_by_field": order_by_field,
            "order_direction": order_direction,
        }))
        return [
            {
                "code": "600566",
                "name": "济川药业",
                "industry": "医药",
                "dividend_yield": 5.41,
                "pe": 16.28,
                "pe_ttm": 11.88,
                "pb": 2.10,
                "roe": 18.2,
                "debt_to_assets": 24.1,
                "n_cashflow_act": 2.8e9,
                "close": 31.2,
                "report_period": "20250930",
            },
            {
                "code": "601921",
                "name": "浙版传媒",
                "industry": "传媒",
                "dividend_yield": 5.92,
                "pe": 13.40,
                "pe_ttm": 9.56,
                "pb": 1.55,
                "roe": 12.4,
                "debt_to_assets": 21.3,
                "n_cashflow_act": 1.9e9,
                "close": 8.6,
                "report_period": "20250930",
            },
        ], 2

    monkeypatch.setattr(service_module, "_execute_screening_query", fake_execute_screening_query)

    async def fake_batch(**kwargs):
        calls.append(("batch", kwargs))
        return (
            "📊 汇总：稳定 1 只 | 不稳定 0 只 | 无数据 1 只\n"
            "✅ 稳定股票代码：601921\n"
            "⚪ 无数据股票代码：600566"
        )

    service._tool_functions = {
        "batch_check_profit_consistency": fake_batch,
    }

    locked_plan = {
        "planning_content": "已批准计划",
        "screen": {
            "conditions_json": json.dumps([
                {"field": "dividend_yield", "operator": ">=", "value": 5},
                {"field": "pe_ttm", "operator": "<=", "value": 15},
            ], ensure_ascii=False),
            "limit": 50,
            "order_by_field": "dividend_yield",
            "order_direction": "desc",
        },
        "batch": {"years": 3, "threshold_cv": 0.3},
    }

    content, tools_used, stocks = asyncio.run(
        service._run_locked_result_execution("执行筛选方案", locked_plan)
    )

    assert "601921" in content
    assert "PE(TTM)" in content
    assert tools_used == ["screen_stocks_by_criteria", "batch_check_profit_consistency"]
    assert calls[0][0] == "screen_query"
    assert calls[0][1]["raw_conditions"][1]["field"] == "pe_ttm"
    assert calls[1][0] == "batch"
    assert json.loads(calls[1][1]["stock_codes_json"]) == ["600566", "601921"]
    assert len(stocks) == 1
    assert stocks[0]["code"] == "601921"
    assert stocks[0]["pe"] == 9.56
    assert stocks[0]["pe_display_label"] == "PE(TTM)"
    assert stocks[0]["pb_display_label"] == "PB"


def test_locked_result_summary_is_compacted_for_llm():
    from app.services.intelligent_screening_service import IntelligentScreeningService

    service = IntelligentScreeningService(db=object())
    locked_plan = {
        "screen": {
            "conditions_json": json.dumps([
                {"field": "dividend_yield", "operator": ">=", "value": 4},
                {"field": "pe_ttm", "operator": "<=", "value": 15},
            ], ensure_ascii=False),
            "limit": 50,
            "order_by_field": "dividend_yield",
            "order_direction": "desc",
        },
        "batch": {"years": 3, "threshold_cv": 0.3},
    }
    screening_output = (
        "共找到 37 只符合条件的股票\n"
        "1. 601919 中远海控\n"
        "2. 603565 中谷物流\n"
        "3. 000915 华特达因\n"
        "4. 002818 富森美\n"
        "5. 300770 新媒股份\n"
        "6. 002867 周大生\n"
        "候选代码列表（按当前排序，共 37 只）: 601919, 603565, 000915, 002818, 300770, 002867"
    )
    batch_output = (
        "共验证 37 只股票近 3 年盈利稳定性\n"
        "📊 汇总：稳定 9 只 | 不稳定 0 只 | 无数据 28 只\n"
        "✅ 稳定股票代码：601919, 600803, 600096, 600211, 601857, 600066, 603558, 603444, 600377\n"
        "⚪ 无数据股票代码：603565, 000915, 002818, 300770, 002867, 600729, 601928"
    )

    compact_plan = service._build_locked_plan_summary(locked_plan)
    compact_screen = service._compact_screening_output_for_llm(screening_output)
    compact_batch = service._compact_batch_output_for_llm(batch_output)

    assert "planning_content" not in compact_plan
    assert "候选代码列表" not in compact_screen
    assert "其余 1 只候选已省略" in compact_screen
    assert "⚪ 无数据股票代码" not in compact_batch
    assert "无数据股票数量: 28" in compact_batch