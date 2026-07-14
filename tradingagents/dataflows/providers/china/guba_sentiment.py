"""东方财富股吧情绪分析 Provider（5 个 AKShare 接口封装）"""
import akshare as ak
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_eastmoney_guba_sentiment(ticker: str) -> str:
    """
    全市场股吧综合评分（带代码过滤）。
    字段: 序号、代码、名称、最新价、综合得分、关注指数、机构参与度
    """
    try:
        df = ak.stock_comment_em()
        if df is None or df.empty:
            return "无数据"
        row = df[df["代码"] == ticker]
        if row.empty:
            return f"未找到 {ticker} 的股吧数据"
        r = row.iloc[0]
        return (
            f"股票: {r.get('名称', ticker)}\n"
            f"综合得分: {r.get('综合得分', 'N/A')}\n"
            f"关注指数: {r.get('关注指数', 'N/A')}\n"
            f"机构参与度: {r.get('机构参与度', 'N/A')}\n"
            f"上升排名: {r.get('上升', 'N/A')}\n"
            f"目前排名: {r.get('目前排名', 'N/A')}"
        )
    except Exception as e:
        raise RuntimeError(f"东财股吧综合失败: {e}")


def get_guba_desire_score(ticker: str) -> str:
    """股吧参与意愿（5/30日均值）"""
    try:
        df = ak.stock_comment_detail_scrd_desire_em(symbol=ticker)
        if df is None or df.empty:
            return "无数据"
        items = []
        for _, row in df.tail(5).iterrows():
            items.append(
                f"- {row.get('交易日期')}: "
                f"参与意愿={row.get('参与意愿', 'N/A')}, "
                f"5日均={row.get('5日平均参与意愿', 'N/A')}, "
                f"变化={row.get('参与意愿变化', 'N/A')}"
            )
        return "\n".join(items)
    except Exception as e:
        raise RuntimeError(f"股吧意愿失败: {e}")


def get_guba_focus_score(ticker: str) -> str:
    """用户关注指数（30日）"""
    try:
        df = ak.stock_comment_detail_scrd_focus_em(symbol=ticker)
        if df is None or df.empty:
            return "无数据"
        items = [
            f"- {row['交易日']}: 关注指数={row['用户关注指数']}"
            for _, row in df.tail(5).iterrows()
        ]
        return "\n".join(items)
    except Exception as e:
        raise RuntimeError(f"股吧关注度失败: {e}")


def get_guba_long_score(ticker: str) -> str:
    """综合评分历史（30日）"""
    try:
        df = ak.stock_comment_detail_zhpj_lspf_em(symbol=ticker)
        if df is None or df.empty:
            return "无数据"
        items = [
            f"- {row['交易日']}: 评分={row['评分']}"
            for _, row in df.tail(5).iterrows()
        ]
        return "\n".join(items)
    except Exception as e:
        raise RuntimeError(f"股吧评分历史失败: {e}")


def get_institutional_participation(ticker: str) -> str:
    """机构参与度（42日）"""
    try:
        df = ak.stock_comment_detail_zlkp_jgcyd_em(symbol=ticker)
        if df is None or df.empty:
            return "无数据"
        items = [
            f"- {row['交易日']}: 机构参与度={row['机构参与度']}"
            for _, row in df.tail(5).iterrows()
        ]
        return "\n".join(items)
    except Exception as e:
        raise RuntimeError(f"机构参与度失败: {e}")
