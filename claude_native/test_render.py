import os
import tempfile
import tradingagents_render as r

MOCK = {
    "meta": {"code": "600845", "name": "宝信软件", "as_of_date": "20260605"},
    "analyses": [
        {"dimension": "技术面", "stance": "看多", "score": 70,
         "key_points": ["均线多头"], "risks": ["超买"]},
        {"dimension": "基本面", "stance": "中性", "score": 55,
         "key_points": ["PE 中位"], "risks": ["增速放缓"]},
    ],
    "debate": [{"round": 1, "bull": {"side": "bull", "argument": "订单饱满"},
                "bear": {"side": "bear", "argument": "估值不低"}}],
    "trader": "BUY 仓位30% 进场逻辑... 止损逻辑...",
    "final": {"signal_lights": {"综合": "🟢", "估值": "🟡", "资金": "🟢"},
               "action": "BUY", "position_pct": 30, "target_price_range": [40, 48],
               "key_catalysts": ["工业软件放量"], "key_risks": ["大盘系统性回调"],
               "one_liner": "工业软件龙头,资金面支撑,逢回调可配。"},
}


def test_card_contains_core_fields():
    md = r.render_card(MOCK)
    assert "宝信软件" in md and "600845" in md
    assert "🟢" in md and "BUY" in md and "30" in md
    assert "技术面" in md and "基本面" in md
    assert "不构成投资建议" in md


def test_summary_sorts_and_lists():
    md = r.render_summary([MOCK])
    assert "600845" in md and "宝信软件" in md and "BUY" in md


def test_write_card_creates_file():
    with tempfile.TemporaryDirectory() as d:
        p = r.write_card(MOCK, d)
        assert os.path.exists(p) and p.endswith(".md")
