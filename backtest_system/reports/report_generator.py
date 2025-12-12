"""
报告生成器
Report Generator

负责生成详细的回测报告
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
import os
from pathlib import Path

logger = logging.getLogger(__name__)

class ReportGenerator:
    """报告生成器"""

    def __init__(self, output_dir: str = "reports"):
        """
        初始化报告生成器

        Args:
            output_dir: 输出目录
        """
        self.output_dir = output_dir
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # 创建输出目录
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

    def generate_comprehensive_report(
        self,
        backtest_result,
        stock_codes: List[str],
        performance_analysis: Dict,
        save_to_file: bool = True
    ) -> Dict:
        """
        生成综合报告

        Args:
            backtest_result: 回测结果
            stock_codes: 股票代码列表
            performance_analysis: 性能分析结果
            save_to_file: 是否保存到文件

        Returns:
            Dict: 报告数据
        """

        try:
            # 基础信息
            report_data = {
                "meta": {
                    "generated_at": datetime.now().isoformat(),
                    "stock_codes": stock_codes,
                    "backtest_period": {
                        "start": backtest_result.config.start_date,
                        "end": backtest_result.config.end_date,
                        "initial_capital": backtest_result.config.initial_capital,
                        "final_value": backtest_result.performance_metrics.get("final_value", 0)
                    }
                },
                "summary": self._generate_summary(backtest_result, performance_analysis),
                "daily_records": self._generate_daily_records(backtest_result.daily_analysis),
                "trade_records": self._generate_trade_records(backtest_result.trade_history),
                "performance_metrics": performance_analysis,
                "portfolio_history": backtest_result.portfolio_history,
                "recommendations": self._generate_recommendations(performance_analysis)
            }

            # 保存报告
            if save_to_file:
                self._save_report(report_data, stock_codes)

            self.logger.info("综合报告生成完成")
            return report_data

        except Exception as e:
            self.logger.error(f"生成综合报告失败: {e}")
            return {"error": str(e)}

    def _generate_summary(self, backtest_result, performance_analysis: Dict) -> Dict:
        """生成摘要信息"""

        metrics = backtest_result.performance_metrics

        summary = {
            "returns": {
                "total_return": metrics.get("total_return", 0),
                "annualized_return": metrics.get("annualized_return", 0),
                "benchmark_return": metrics.get("benchmark_return", 0),
                "excess_return": metrics.get("excess_return", 0)
            },
            "risk": {
                "max_drawdown": metrics.get("max_drawdown", 0),
                "volatility": metrics.get("volatility", 0),
                "sharpe_ratio": metrics.get("sharpe_ratio", 0),
                "win_rate": metrics.get("win_rate", 0)
            },
            "trading": {
                "total_trades": metrics.get("total_trades", 0),
                "trading_days": metrics.get("trading_days", 0)
            },
            "overall_grade": performance_analysis.get("overall_score", {}).get("grade", "N/A")
        }

        return summary

    def _generate_daily_records(self, daily_analysis: List[Dict]) -> List[Dict]:
        """生成每日记录"""

        daily_records = []

        for record in daily_analysis:
            daily_record = {
                "date": record.get("date"),
                "portfolio_value": record.get("portfolio_value", 0),
                "cash": record.get("cash", 0),
                "position_ratio": (record.get("portfolio_value", 0) - record.get("cash", 0)) / record.get("portfolio_value", 1) if record.get("portfolio_value", 0) > 0 else 0,
                "daily_return": 0,  # 需要计算
                "decision": {
                    "target_position": record.get("position_decision", {}).get("target_position", 0),
                    "confidence": record.get("position_decision", {}).get("confidence", 0),
                    "reason": record.get("position_decision", {}).get("reason", ""),
                    "risk_level": record.get("position_decision", {}).get("risk_level", "medium")
                },
                "market_state": record.get("market_analysis", {}),
                "trades_count": len(record.get("trades", []))
            }

            daily_records.append(daily_record)

        # 计算日收益率
        for i in range(1, len(daily_records)):
            prev_value = daily_records[i-1]["portfolio_value"]
            curr_value = daily_records[i]["portfolio_value"]
            if prev_value > 0:
                daily_records[i]["daily_return"] = (curr_value - prev_value) / prev_value

        return daily_records

    def _generate_trade_records(self, trade_history: List[Dict]) -> List[Dict]:
        """生成交易记录"""

        trade_records = []

        for trade in trade_history:
            trade_record = {
                "date": trade.get("date"),
                "stock_code": trade.get("stock_code"),
                "action": trade.get("action"),
                "shares": trade.get("shares", 0),
                "price": trade.get("price", 0),
                "value": trade.get("value", 0),
                "commission": trade.get("commission", 0),
                "slippage": trade.get("slippage", 0),
                "total_cost": trade.get("total_cost", 0),
                "total_proceeds": trade.get("total_proceeds", 0),
                "reason": trade.get("reason", "")
            }

            trade_records.append(trade_record)

        return trade_records

    def _generate_recommendations(self, performance_analysis: Dict) -> List[str]:
        """生成建议"""

        recommendations = []

        try:
            # 基于综合评分提供建议
            overall_score = performance_analysis.get("overall_score", {})
            if overall_score is None:
                total_score = 0
            else:
                total_score = overall_score.get("total_score", 0)

            if total_score >= 85:
                recommendations.append("🎉 策略表现优秀，建议继续使用并考虑扩大资金规模")
            elif total_score >= 70:
                recommendations.append("✅ 策略表现良好，可以实盘小资金测试")
            elif total_score >= 55:
                recommendations.append("⚠️ 策略表现一般，建议优化参数后再考虑")
            else:
                recommendations.append("❌ 策略表现不佳，建议重新设计或寻找其他策略")

            # 基于风险指标提供建议
            risk_analysis = performance_analysis.get("risk", {})
            if risk_analysis is None:
                max_drawdown = 0
            else:
                max_drawdown = risk_analysis.get("max_drawdown", 0)

            if max_drawdown > 0.2:  # 最大回撤超过20%
                recommendations.append("⚠️ 最大回撤较大，建议加强风险控制措施")

            volatility = risk_analysis.get("volatility", 0) if risk_analysis else 0
            if volatility > 0.3:  # 年化波动率超过30%
                recommendations.append("📊 波动率较高，考虑降低仓位或增加对冲")

            # 基于收益指标提供建议
            returns_analysis = performance_analysis.get("returns", {})
            if returns_analysis is None:
                sharpe_ratio = 0
            else:
                sharpe_ratio = returns_analysis.get("sharpe_ratio", 0)

            if sharpe_ratio < 1.0:
                recommendations.append("📈 夏普比率偏低，建议提高风险调整后收益")

            win_rate = returns_analysis.get("win_rate", 0) if returns_analysis else 0
            if win_rate < 0.4:
                recommendations.append("🎯 胜率偏低，建议优化入场时机或止损策略")

            # 基于交易频率提供建议
            trading_analysis = performance_analysis.get("trading", {})
            if trading_analysis is None:
                trades_per_day = 0
            else:
                trades_per_day = trading_analysis.get("trades_per_day", 0)

            if trades_per_day > 2:
                recommendations.append("⏰ 交易频率较高，注意控制交易成本")
            elif trades_per_day < 0.1:
                recommendations.append("🐌 交易频率较低，可能错过机会，考虑调整策略灵敏度")

            # 基于持仓分析提供建议
            position_analysis = performance_analysis.get("positions", {})
            if position_analysis is None:
                avg_position_ratio = 0
            else:
                avg_position_ratio = position_analysis.get("avg_position_ratio", 0)

            if avg_position_ratio > 0.8:
                recommendations.append("💰 平均仓位较高，建议预留更多现金应对风险")
            elif avg_position_ratio < 0.3:
                recommendations.append("📉 平均仓位较低，资金利用率偏低，可以适当提高仓位")

            # 综合建议
            if not recommendations:
                recommendations.append("策略表现均衡，继续保持并持续监控")

        except Exception as e:
            self.logger.error(f"生成建议失败: {e}")
            recommendations.append("无法生成建议，请检查分析结果")

        return recommendations

    def _save_report(self, report_data: Dict, stock_codes: List[str]):
        """保存报告到文件 - 仅生成增强分析所需的基础文件"""

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            stock_str = "_".join(stock_codes[:3])  # 最多显示3个股票代码

            # 仅生成增强分析所需的基础JSON和CSV文件
            json_file = os.path.join(self.output_dir, f"backtest_report_{stock_str}_{timestamp}.json")
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2, default=str)

            # CSV格式 - 每日记录（增强分析需要）
            daily_df = pd.DataFrame(report_data["daily_records"])
            if not daily_df.empty:
                csv_file = os.path.join(self.output_dir, f"daily_records_{stock_str}_{timestamp}.csv")
                daily_df.to_csv(csv_file, index=False, encoding='utf-8-sig')

            # CSV格式 - 交易记录（增强分析需要）
            trade_df = pd.DataFrame(report_data["trade_records"])
            if not trade_df.empty:
                csv_file = os.path.join(self.output_dir, f"trade_records_{stock_str}_{timestamp}.csv")
                trade_df.to_csv(csv_file, index=False, encoding='utf-8-sig')

            self.logger.info(f"增强分析所需基础文件已保存到: {self.output_dir}")
            self.logger.info(f"基础JSON: {json_file}")

        except Exception as e:
            self.logger.error(f"保存基础报告文件失败: {e}")

    def _generate_html_report(self, report_data: Dict) -> str:
        """生成HTML格式报告"""

        html_template = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>回测报告</title>
    <style>
        body {
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #e0e0e0;
        }
        .section {
            margin-bottom: 30px;
        }
        .section h2 {
            color: #333;
            border-left: 4px solid #007bff;
            padding-left: 15px;
            margin-bottom: 20px;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .metric-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #007bff;
        }
        .metric-label {
            font-weight: bold;
            color: #666;
            margin-bottom: 5px;
        }
        .metric-value {
            font-size: 24px;
            font-weight: bold;
            color: #333;
        }
        .metric-value.positive { color: #28a745; }
        .metric-value.negative { color: #dc3545; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #f8f9fa;
            font-weight: bold;
        }
        .recommendations {
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 8px;
            padding: 20px;
        }
        .recommendations h3 {
            color: #856404;
            margin-top: 0;
        }
        .recommendations ul {
            margin: 0;
            padding-left: 20px;
        }
        .recommendations li {
            margin-bottom: 10px;
        }
        .grade {
            font-size: 36px;
            font-weight: bold;
            text-align: center;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .grade.A, .grade.A-plus, .grade.A-minus { background: #d4edda; color: #155724; }
        .grade.B, .grade.B-plus, .grade.B-minus { background: #d1ecf1; color: #0c5460; }
        .grade.C, .grade.C-plus, .grade.C-minus { background: #fff3cd; color: #856404; }
        .grade.D { background: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>智能回测分析报告</h1>
            <p>生成时间: {generated_time}</p>
            <p>股票代码: {stock_codes}</p>
            <p>回测期间: {start_date} 至 {end_date}</p>
        </div>

        {overall_grade_section}

        <div class="section">
            <h2>📊 核心指标概览</h2>
            <div class="metrics-grid">
                {metrics_cards}
            </div>
        </div>

        <div class="section">
            <h2>📈 收益表现</h2>
            <div class="metrics-grid">
                {returns_cards}
            </div>
        </div>

        <div class="section">
            <h2>⚠️ 风险分析</h2>
            <div class="metrics-grid">
                {risk_cards}
            </div>
        </div>

        <div class="section">
            <h2>🔄 交易统计</h2>
            <div class="metrics-grid">
                {trading_cards}
            </div>
        </div>

        <div class="section">
            <h2>💡 优化建议</h2>
            <div class="recommendations">
                <h3>策略改进建议</h3>
                <ul>
                    {recommendations_list}
                </ul>
            </div>
        </div>

        <div class="section">
            <h2>📋 最近交易记录</h2>
            <table>
                <thead>
                    <tr>
                        <th>日期</th>
                        <th>股票代码</th>
                        <th>操作</th>
                        <th>数量</th>
                        <th>价格</th>
                        <th>金额</th>
                        <th>原因</th>
                    </tr>
                </thead>
                <tbody>
                    {recent_trades}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
        """

        # 准备数据
        meta = report_data["meta"]
        summary = report_data["summary"]
        trade_records = report_data["trade_records"]
        recommendations = report_data["recommendations"]

        # 生成指标卡片
        def format_card(label, value, is_positive=True):
            value_str = f"{value:.2%}" if isinstance(value, (int, float)) and abs(value) < 1 else f"{value:.2f}" if isinstance(value, (int, float)) else str(value)
            css_class = "positive" if is_positive and value > 0 else "negative" if not is_positive and value > 0 else ""
            return f"""
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value {css_class}">{value_str}</div>
            </div>
            """

        # 核心指标
        metrics_cards = [
            format_card("总收益率", summary["returns"]["total_return"]),
            format_card("年化收益率", summary["returns"]["annualized_return"]),
            format_card("最大回撤", summary["risk"]["max_drawdown"], False),
            format_card("夏普比率", summary["risk"]["sharpe_ratio"]),
            format_card("胜率", summary["risk"]["win_rate"]),
            format_card("交易次数", summary["trading"]["total_trades"])
        ]

        # 收益指标
        returns_cards = [
            format_card("总收益", summary["returns"]["total_return"]),
            format_card("年化收益", summary["returns"]["annualized_return"]),
            format_card("基准收益", summary["returns"]["benchmark_return"]),
            format_card("超额收益", summary["returns"]["excess_return"])
        ]

        # 风险指标
        risk_cards = [
            format_card("最大回撤", summary["risk"]["max_drawdown"], False),
            format_card("波动率", summary["risk"]["volatility"], False),
            format_card("夏普比率", summary["risk"]["sharpe_ratio"]),
            format_card("胜率", summary["risk"]["win_rate"])
        ]

        # 交易指标
        trading_cards = [
            format_card("总交易次数", summary["trading"]["total_trades"]),
            format_card("交易天数", summary["trading"]["trading_days"]),
            format_card("日均交易", summary["trading"]["total_trades"] / max(1, summary["trading"]["trading_days"]))
        ]

        # 建议列表
        recommendations_list = "\n".join(f"<li>{rec}</li>" for rec in recommendations)

        # 最近交易
        recent_trades_html = ""
        for trade in trade_records[-10:]:  # 最近10笔交易
            recent_trades_html += f"""
            <tr>
                <td>{trade.get('date', '')}</td>
                <td>{trade.get('stock_code', '')}</td>
                <td>{trade.get('action', '')}</td>
                <td>{trade.get('shares', 0)}</td>
                <td>{trade.get('price', 0):.2f}</td>
                <td>{trade.get('value', 0):.2f}</td>
                <td>{trade.get('reason', '')[:20]}...</td>
            </tr>
            """

        # 综合评级
        overall_grade = summary.get("overall_grade", "N/A")
        grade_display = overall_grade.replace("+", "-plus").replace("-", "-minus")
        overall_grade_section = f'<div class="grade {grade_display}">综合评级: {overall_grade}</div>' if overall_grade != "N/A" else ""

        # 填充模板
        return html_template.format(
            generated_time=meta["generated_at"][:19],
            stock_codes=", ".join(meta["stock_codes"]),
            start_date=meta["backtest_period"]["start"],
            end_date=meta["backtest_period"]["end"],
            overall_grade_section=overall_grade_section,
            metrics_cards="".join(metrics_cards),
            returns_cards="".join(returns_cards),
            risk_cards="".join(risk_cards),
            trading_cards="".join(trading_cards),
            recommendations_list=recommendations_list,
            recent_trades=recent_trades_html
        )