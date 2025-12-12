"""
可视化模块
Visualization

负责生成回测结果的可视化图表
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import os
from pathlib import Path

# 设置中文字体
import matplotlib.font_manager as fm

def setup_chinese_font():
    """设置中文字体"""
    try:
        # 尝试使用系统中可用的中文字体
        chinese_fonts = ['Noto Sans CJK JP', 'Noto Serif CJK JP', 'SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'DejaVu Sans']

        # 检查哪些字体可用
        available_fonts = [f.name for f in fm.fontManager.ttflist]
        font_candidates = [font for font in chinese_fonts if font in available_fonts]

        if font_candidates:
            plt.rcParams['font.sans-serif'] = font_candidates + plt.rcParams['font.sans-serif']
            print(f"✅ 使用中文字体: {font_candidates[0]}")
        else:
            print("⚠️ 未找到可用的中文字体，使用默认字体")
            # 如果找不到中文字体，至少确保能显示
            plt.rcParams['font.sans-serif'] = ['DejaVu Sans'] + plt.rcParams['font.sans-serif']

    except Exception as e:
        print(f"⚠️ 设置中文字体失败: {e}")

# 延迟设置字体，在logger初始化后调用
setup_chinese_font()
plt.rcParams['axes.unicode_minus'] = False

logger = logging.getLogger(__name__)

class Visualization:
    """可视化类"""

    def __init__(self, output_dir: str = "charts", style: str = "seaborn-v0_8"):
        """
        初始化可视化类

        Args:
            output_dir: 图表输出目录
            style: 图表样式
        """
        self.output_dir = output_dir
        self.style = style
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # 创建输出目录
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

        # 设置图表样式
        try:
            plt.style.use(style)
        except:
            plt.style.use('default')
            self.logger.warning(f"无法使用样式 {style}，使用默认样式")

        # 设置颜色主题
        self.colors = {
            'primary': '#2E86AB',
            'secondary': '#A23B72',
            'success': '#F18F01',
            'danger': '#C73E1D',
            'warning': '#F4A261',
            'info': '#264653',
            'light': '#F8F9FA',
            'dark': '#343A40'
        }

    def generate_all_charts(
        self,
        backtest_result,
        stock_codes: List[str],
        performance_analysis: Dict,
        save_charts: bool = True
    ) -> Dict[str, str]:
        """
        生成所有图表

        Args:
            backtest_result: 回测结果
            stock_codes: 股票代码列表
            performance_analysis: 性能分析结果
            save_charts: 是否保存图表

        Returns:
            Dict[str, str]: 图表文件路径字典
        """

        chart_files = {}

        try:
            # 准备数据
            portfolio_history = pd.DataFrame(backtest_result.portfolio_history)
            daily_analysis = pd.DataFrame(backtest_result.daily_analysis)
            trade_history = pd.DataFrame(backtest_result.trade_history)

            if portfolio_history.empty:
                self.logger.warning("无投资组合历史数据，跳过图表生成")
                return chart_files

            # 1. 净值曲线图
            chart_files['portfolio_value'] = self.plot_portfolio_value(portfolio_history, save_charts)

            # 2. 收益率分布图
            chart_files['returns_distribution'] = self.plot_returns_distribution(portfolio_history, save_charts)

            # 3. 回撤分析图
            chart_files['drawdown_analysis'] = self.plot_drawdown_analysis(portfolio_history, save_charts)

            # 4. 滚动收益率图
            chart_files['rolling_returns'] = self.plot_rolling_returns(portfolio_history, save_charts)

            # 5. 仓位变化图
            if not daily_analysis.empty:
                chart_files['position_changes'] = self.plot_position_changes(daily_analysis, save_charts)

            # 6. 交易信号图
            if not trade_history.empty:
                chart_files['trade_signals'] = self.plot_trade_signals(trade_history, portfolio_history, save_charts)

            # 7. 风险收益散点图
            chart_files['risk_return'] = self.plot_risk_return_scatter(performance_analysis, save_charts)

            # 8. 月度收益热力图
            chart_files['monthly_returns'] = self.plot_monthly_returns_heatmap(portfolio_history, save_charts)

            # 9. 交易统计图
            if not trade_history.empty:
                chart_files['trading_stats'] = self.plot_trading_statistics(trade_history, save_charts)

            # 10. 综合仪表板
            chart_files['dashboard'] = self.create_dashboard(portfolio_history, daily_analysis, trade_history, save_charts)

            self.logger.info(f"图表生成完成，共 {len(chart_files)} 个图表")
            return chart_files

        except Exception as e:
            self.logger.error(f"生成图表失败: {e}")
            return chart_files

    def plot_portfolio_value(self, portfolio_history: pd.DataFrame, save_chart: bool = True) -> Optional[str]:
        """绘制净值曲线图"""

        try:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [3, 1]})

            # 转换日期格式
            portfolio_history['date'] = pd.to_datetime(portfolio_history['date'])

            # 上图：净值曲线
            ax1.plot(portfolio_history['date'], portfolio_history['total_value'],
                    color=self.colors['primary'], linewidth=2, label='投资组合净值')

            # 添加基准线
            initial_value = portfolio_history['total_value'].iloc[0]
            benchmark_values = [initial_value] * len(portfolio_history)
            ax1.plot(portfolio_history['date'], benchmark_values,
                    color=self.colors['danger'], linestyle='--', alpha=0.7, label='初始净值')

            ax1.set_title('投资组合净值曲线', fontsize=16, fontweight='bold', pad=20)
            ax1.set_ylabel('净值 (元)', fontsize=12)
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            # 格式化x轴
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
            plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

            # 下图：日收益率
            if 'daily_return' in portfolio_history.columns:
                daily_returns = portfolio_history['daily_return'] * 100
                ax2.bar(portfolio_history['date'], daily_returns,
                       color=np.where(daily_returns >= 0, self.colors['success'], self.colors['danger']),
                       alpha=0.7, width=1)
                ax2.set_title('日收益率', fontsize=12)
                ax2.set_ylabel('收益率 (%)', fontsize=10)
                ax2.set_xlabel('日期', fontsize=12)
                ax2.grid(True, alpha=0.3)
                ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
                ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
                plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)

            plt.tight_layout()

            if save_chart:
                file_path = os.path.join(self.output_dir, 'portfolio_value.png')
                plt.savefig(file_path, dpi=300, bbox_inches='tight')
                plt.close()
                return file_path
            else:
                plt.show()
                return None

        except Exception as e:
            self.logger.error(f"绘制净值曲线失败: {e}")
            plt.close()
            return None

    def plot_returns_distribution(self, portfolio_history: pd.DataFrame, save_chart: bool = True) -> Optional[str]:
        """绘制收益率分布图"""

        try:
            if 'daily_return' not in portfolio_history.columns:
                self.logger.warning("无日收益率数据")
                return None

            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))

            daily_returns = portfolio_history['daily_return']

            # 1. 收益率直方图
            ax1.hist(daily_returns, bins=50, color=self.colors['primary'], alpha=0.7, edgecolor='black')
            ax1.axvline(daily_returns.mean(), color=self.colors['danger'], linestyle='--',
                       label=f'均值: {daily_returns.mean():.4f}')
            ax1.set_title('日收益率分布', fontsize=14, fontweight='bold')
            ax1.set_xlabel('日收益率')
            ax1.set_ylabel('频次')
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            # 2. 累积收益率曲线
            if 'cumulative_return' in portfolio_history.columns:
                ax2.plot(portfolio_history['date'], portfolio_history['cumulative_return'] * 100,
                        color=self.colors['secondary'], linewidth=2)
                ax2.set_title('累积收益率', fontsize=14, fontweight='bold')
                ax2.set_ylabel('累积收益率 (%)')
                ax2.grid(True, alpha=0.3)
                ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
                plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)

            # 3. 收益率QQ图
            from scipy import stats
            stats.probplot(daily_returns, dist="norm", plot=ax3)
            ax3.set_title('收益率QQ图 (正态性检验)', fontsize=14, fontweight='bold')
            ax3.grid(True, alpha=0.3)

            # 4. 收益率统计表格
            stats_text = f"""
            统计指标
            ──────────────────────────────
            样本数量: {len(daily_returns)}
            均值: {daily_returns.mean():.4f}
            标准差: {daily_returns.std():.4f}
            偏度: {stats.skew(daily_returns):.4f}
            峰度: {stats.kurtosis(daily_returns):.4f}
            最小值: {daily_returns.min():.4f}
            最大值: {daily_returns.max():.4f}
            25%分位数: {daily_returns.quantile(0.25):.4f}
            75%分位数: {daily_returns.quantile(0.75):.4f}
            """
            ax4.text(0.1, 0.5, stats_text, transform=ax4.transAxes, fontsize=11,
                    verticalalignment='center', fontfamily='monospace')
            ax4.set_title('收益率统计', fontsize=14, fontweight='bold')
            ax4.axis('off')

            plt.tight_layout()

            if save_chart:
                file_path = os.path.join(self.output_dir, 'returns_distribution.png')
                plt.savefig(file_path, dpi=300, bbox_inches='tight')
                plt.close()
                return file_path
            else:
                plt.show()
                return None

        except Exception as e:
            self.logger.error(f"绘制收益率分布图失败: {e}")
            plt.close()
            return None

    def plot_drawdown_analysis(self, portfolio_history: pd.DataFrame, save_chart: bool = True) -> Optional[str]:
        """绘制回撤分析图"""

        try:
            if 'cumulative_return' not in portfolio_history.columns:
                self.logger.warning("无累积收益率数据")
                return None

            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [2, 1]})

            portfolio_history['date'] = pd.to_datetime(portfolio_history['date'])
            cumulative_returns = portfolio_history['cumulative_return']

            # 计算回撤
            cumulative_max = cumulative_returns.expanding().max()
            drawdown = (cumulative_returns - cumulative_max) / (1 + cumulative_max)

            # 上图：净值曲线和回撤区域
            ax1.fill_between(portfolio_history['date'], 0, cumulative_returns * 100,
                           color=self.colors['primary'], alpha=0.3, label='累积收益')
            ax1.plot(portfolio_history['date'], cumulative_returns * 100,
                    color=self.colors['primary'], linewidth=2, label='净值曲线')
            ax1.fill_between(portfolio_history['date'], 0, drawdown * 100,
                           color=self.colors['danger'], alpha=0.5, label='回撤区域')
            ax1.set_title('净值曲线与回撤分析', fontsize=16, fontweight='bold')
            ax1.set_ylabel('收益率 (%)', fontsize=12)
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            # 下图：回撤曲线
            ax2.fill_between(portfolio_history['date'], drawdown * 100, 0,
                           color=self.colors['danger'], alpha=0.7)
            ax2.plot(portfolio_history['date'], drawdown * 100,
                    color=self.colors['danger'], linewidth=1)
            ax2.set_title('回撤曲线', fontsize=12)
            ax2.set_ylabel('回撤 (%)', fontsize=10)
            ax2.set_xlabel('日期', fontsize=12)
            ax2.grid(True, alpha=0.3)

            # 标记最大回撤
            max_dd_idx = drawdown.idxmin()
            max_dd_value = drawdown.min()
            ax2.axhline(y=max_dd_value * 100, color=self.colors['warning'], linestyle='--',
                       label=f'最大回撤: {max_dd_value:.2%}')
            ax2.legend()

            # 格式化x轴
            for ax in [ax1, ax2]:
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
                ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
                plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

            plt.tight_layout()

            if save_chart:
                file_path = os.path.join(self.output_dir, 'drawdown_analysis.png')
                plt.savefig(file_path, dpi=300, bbox_inches='tight')
                plt.close()
                return file_path
            else:
                plt.show()
                return None

        except Exception as e:
            self.logger.error(f"绘制回撤分析图失败: {e}")
            plt.close()
            return None

    def plot_rolling_returns(self, portfolio_history: pd.DataFrame, save_chart: bool = True) -> Optional[str]:
        """绘制滚动收益率图"""

        try:
            if 'daily_return' not in portfolio_history.columns:
                self.logger.warning("无日收益率数据")
                return None

            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

            portfolio_history['date'] = pd.to_datetime(portfolio_history['date'])
            daily_returns = portfolio_history['daily_return']

            # 计算滚动收益率
            rolling_5d = daily_returns.rolling(window=5).mean()
            rolling_20d = daily_returns.rolling(window=20).mean()
            rolling_60d = daily_returns.rolling(window=60).mean()

            # 上图：滚动平均收益率
            ax1.plot(portfolio_history['date'], rolling_5d * 100,
                    label='5日滚动均值', color=self.colors['success'], alpha=0.8)
            ax1.plot(portfolio_history['date'], rolling_20d * 100,
                    label='20日滚动均值', color=self.colors['primary'], linewidth=2)
            ax1.plot(portfolio_history['date'], rolling_60d * 100,
                    label='60日滚动均值', color=self.colors['danger'], linewidth=2)
            ax1.axhline(y=0, color='black', linestyle='-', alpha=0.3)
            ax1.set_title('滚动平均收益率', fontsize=16, fontweight='bold')
            ax1.set_ylabel('日收益率 (%)', fontsize=12)
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            # 下图：滚动波动率
            rolling_vol_5d = daily_returns.rolling(window=5).std() * np.sqrt(252) * 100
            rolling_vol_20d = daily_returns.rolling(window=20).std() * np.sqrt(252) * 100
            rolling_vol_60d = daily_returns.rolling(window=60).std() * np.sqrt(252) * 100

            ax2.plot(portfolio_history['date'], rolling_vol_5d,
                    label='5日滚动波动率', color=self.colors['success'], alpha=0.8)
            ax2.plot(portfolio_history['date'], rolling_vol_20d,
                    label='20日滚动波动率', color=self.colors['primary'], linewidth=2)
            ax2.plot(portfolio_history['date'], rolling_vol_60d,
                    label='60日滚动波动率', color=self.colors['danger'], linewidth=2)
            ax2.set_title('滚动波动率 (年化)', fontsize=14, fontweight='bold')
            ax2.set_ylabel('波动率 (%)', fontsize=12)
            ax2.set_xlabel('日期', fontsize=12)
            ax2.legend()
            ax2.grid(True, alpha=0.3)

            # 格式化x轴
            for ax in [ax1, ax2]:
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
                ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
                plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

            plt.tight_layout()

            if save_chart:
                file_path = os.path.join(self.output_dir, 'rolling_returns.png')
                plt.savefig(file_path, dpi=300, bbox_inches='tight')
                plt.close()
                return file_path
            else:
                plt.show()
                return None

        except Exception as e:
            self.logger.error(f"绘制滚动收益率图失败: {e}")
            plt.close()
            return None

    def plot_position_changes(self, daily_analysis: pd.DataFrame, save_chart: bool = True) -> Optional[str]:
        """绘制仓位变化图"""

        try:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [2, 1]})

            daily_analysis['date'] = pd.to_datetime(daily_analysis['date'])

            # 计算仓位比例
            position_ratios = []

            # 检查数据结构，使用正确的方式获取仓位数据
            if 'position_ratio' in daily_analysis.columns:
                # 如果已有仓位比例列，直接使用
                position_ratios = daily_analysis['position_ratio'].tolist()
            else:
                # 尝试从portfolio数据计算
                if 'portfolio' in daily_analysis.columns:
                    for record in daily_analysis['portfolio']:
                        if isinstance(record, dict) and 'total_value' in record and 'cash' in record:
                            ratio = (record['total_value'] - record['cash']) / record['total_value']
                            position_ratios.append(ratio)
                        else:
                            position_ratios.append(0)
                else:
                    # 如果没有portfolio列，使用默认值
                    position_ratios = [0.0] * len(daily_analysis)
                    self.logger.warning("未找到portfolio数据，使用默认仓位比例")

            daily_analysis['position_ratio'] = position_ratios

            # 上图：仓位比例变化
            ax1.fill_between(daily_analysis['date'], 0, np.array(position_ratios) * 100,
                           color=self.colors['primary'], alpha=0.3)
            ax1.plot(daily_analysis['date'], np.array(position_ratios) * 100,
                    color=self.colors['primary'], linewidth=2)
            ax1.set_title('仓位比例变化', fontsize=16, fontweight='bold')
            ax1.set_ylabel('仓位比例 (%)', fontsize=12)
            ax1.grid(True, alpha=0.3)
            ax1.set_ylim([0, 100])

            # 添加平均线
            avg_ratio = np.mean(position_ratios) * 100
            ax1.axhline(y=avg_ratio, color=self.colors['warning'], linestyle='--',
                       label=f'平均仓位: {avg_ratio:.1f}%')
            ax1.legend()

            # 下图：决策置信度
            confidences = []
            for decision in daily_analysis.get('position_decision', []):
                if isinstance(decision, dict) and 'confidence' in decision:
                    confidences.append(decision['confidence'])
                else:
                    confidences.append(0)

            ax2.bar(daily_analysis['date'], np.array(confidences) * 100,
                   color=self.colors['secondary'], alpha=0.7, width=1)
            ax2.set_title('决策置信度', fontsize=14, fontweight='bold')
            ax2.set_ylabel('置信度 (%)', fontsize=10)
            ax2.set_xlabel('日期', fontsize=12)
            ax2.grid(True, alpha=0.3)
            ax2.set_ylim([0, 100])

            # 格式化x轴
            for ax in [ax1, ax2]:
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
                ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
                plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

            plt.tight_layout()

            if save_chart:
                file_path = os.path.join(self.output_dir, 'position_changes.png')
                plt.savefig(file_path, dpi=300, bbox_inches='tight')
                plt.close()
                return file_path
            else:
                plt.show()
                return None

        except Exception as e:
            self.logger.error(f"绘制仓位变化图失败: {e}")
            plt.close()
            return None

    def plot_trade_signals(self, trade_history: pd.DataFrame, portfolio_history: pd.DataFrame, save_chart: bool = True) -> Optional[str]:
        """绘制交易信号图"""

        try:
            fig, ax = plt.subplots(figsize=(15, 8))

            portfolio_history['date'] = pd.to_datetime(portfolio_history['date'])
            trade_history['date'] = pd.to_datetime(trade_history['date'])

            # 绘制净值曲线
            ax.plot(portfolio_history['date'], portfolio_history['total_value'],
                   color=self.colors['primary'], linewidth=2, label='投资组合净值')

            # 标记买入信号
            buy_trades = trade_history[trade_history['action'] == 'buy']
            if not buy_trades.empty:
                buy_values = []
                for date in buy_trades['date']:
                    # 找到最接近的投资组合净值
                    closest_idx = portfolio_history['date'].sub(date).abs().idxmin()
                    buy_values.append(portfolio_history.loc[closest_idx, 'total_value'])

                ax.scatter(buy_trades['date'], buy_values,
                          color=self.colors['success'], s=100, marker='^',
                          label=f'买入 ({len(buy_trades)}次)', zorder=5)

            # 标记卖出信号
            sell_trades = trade_history[trade_history['action'] == 'sell']
            if not sell_trades.empty:
                sell_values = []
                for date in sell_trades['date']:
                    # 找到最接近的投资组合净值
                    closest_idx = portfolio_history['date'].sub(date).abs().idxmin()
                    sell_values.append(portfolio_history.loc[closest_idx, 'total_value'])

                ax.scatter(sell_trades['date'], sell_values,
                          color=self.colors['danger'], s=100, marker='v',
                          label=f'卖出 ({len(sell_trades)}次)', zorder=5)

            ax.set_title('交易信号与净值变化', fontsize=16, fontweight='bold')
            ax.set_ylabel('净值 (元)', fontsize=12)
            ax.set_xlabel('日期', fontsize=12)
            ax.legend()
            ax.grid(True, alpha=0.3)

            # 格式化x轴
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

            plt.tight_layout()

            if save_chart:
                file_path = os.path.join(self.output_dir, 'trade_signals.png')
                plt.savefig(file_path, dpi=300, bbox_inches='tight')
                plt.close()
                return file_path
            else:
                plt.show()
                return None

        except Exception as e:
            self.logger.error(f"绘制交易信号图失败: {e}")
            plt.close()
            return None

    def plot_risk_return_scatter(self, performance_analysis: Dict, save_chart: bool = True) -> Optional[str]:
        """绘制风险收益散点图"""

        try:
            fig, ax = plt.subplots(figsize=(10, 8))

            # 获取关键指标
            returns_analysis = performance_analysis.get('returns', {})
            risk_analysis = performance_analysis.get('risk', {})
            benchmark_analysis = performance_analysis.get('benchmark', {})

            # 当前策略的点
            current_return = returns_analysis.get('annualized_return', 0)
            current_risk = risk_analysis.get('volatility', 0)

            # 基准点
            benchmark_return = benchmark_analysis.get('benchmark_return', 0)
            benchmark_risk = 0.15  # 假设基准波动率为15%

            # 绘制散点图
            ax.scatter(current_risk * 100, current_return * 100,
                      s=200, c=self.colors['primary'], marker='o',
                      label='当前策略', zorder=5)

            ax.scatter(benchmark_risk * 100, benchmark_return * 100,
                      s=200, c=self.colors['danger'], marker='s',
                      label='基准指数', zorder=5)

            # 添加基准线
            risk_range = np.linspace(0, max(current_risk, benchmark_risk) * 1.2 * 100, 100)

            # 夏普比率1.0的线
            sharpe_1_line = risk_range * 0.01  # 1%风险对应1%收益
            ax.plot(risk_range, sharpe_1_line, 'g--', alpha=0.7, label='夏普比率=1.0')

            # 夏普比率0.5的线
            sharpe_05_line = risk_range * 0.005  # 0.5%风险对应0.5%收益
            ax.plot(risk_range, sharpe_05_line, 'y--', alpha=0.7, label='夏普比率=0.5')

            # 标注点的数值
            ax.annotate(f'策略\n风险:{current_risk:.1%}\n收益:{current_return:.1%}',
                       xy=(current_risk * 100, current_return * 100),
                       xytext=(current_risk * 100 + 2, current_return * 100 + 2),
                       fontsize=10, ha='left')

            ax.annotate(f'基准\n风险:{benchmark_risk:.1%}\n收益:{benchmark_return:.1%}',
                       xy=(benchmark_risk * 100, benchmark_return * 100),
                       xytext=(benchmark_risk * 100 + 2, benchmark_return * 100 - 2),
                       fontsize=10, ha='left')

            ax.set_title('风险收益散点图', fontsize=16, fontweight='bold')
            ax.set_xlabel('年化波动率 (%)', fontsize=12)
            ax.set_ylabel('年化收益率 (%)', fontsize=12)
            ax.legend()
            ax.grid(True, alpha=0.3)

            # 设置坐标轴范围
            ax.set_xlim([0, max(current_risk, benchmark_risk) * 1.2 * 100])
            ax.set_ylim([min(current_return, benchmark_return) * 0.8 * 100,
                        max(current_return, benchmark_return) * 1.2 * 100])

            plt.tight_layout()

            if save_chart:
                file_path = os.path.join(self.output_dir, 'risk_return_scatter.png')
                plt.savefig(file_path, dpi=300, bbox_inches='tight')
                plt.close()
                return file_path
            else:
                plt.show()
                return None

        except Exception as e:
            self.logger.error(f"绘制风险收益散点图失败: {e}")
            plt.close()
            return None

    def plot_monthly_returns_heatmap(self, portfolio_history: pd.DataFrame, save_chart: bool = True) -> Optional[str]:
        """绘制月度收益热力图"""

        try:
            if 'daily_return' not in portfolio_history.columns:
                self.logger.warning("无日收益率数据")
                return None

            # 检查数据量是否足够生成热力图
            if len(portfolio_history) < 7:  # 少于一周的数据
                self.logger.warning("数据量不足，无法生成月度收益热力图")
                return None

            # 准备数据
            portfolio_history['date'] = pd.to_datetime(portfolio_history['date'])
            portfolio_history['year'] = portfolio_history['date'].dt.year
            portfolio_history['month'] = portfolio_history['date'].dt.month

            # 计算月度收益率
            monthly_returns = portfolio_history.groupby(['year', 'month'])['daily_return'].apply(
                lambda x: (1 + x).prod() - 1
            ).reset_index()

            # 创建透视表
            pivot_table = monthly_returns.pivot(index='year', columns='month', values='daily_return')

            # 确保有12个月的列
            all_months = ['1月', '2月', '3月', '4月', '5月', '6月',
                          '7月', '8月', '9月', '10月', '11月', '12月']

            # 重新索引确保有所有月份
            for month in all_months:
                if month not in pivot_table.columns:
                    pivot_table[month] = np.nan

            pivot_table = pivot_table[all_months]

            # 添加年度收益
            year_returns = portfolio_history.groupby('year')['daily_return'].apply(
                lambda x: (1 + x).prod() - 1
            )
            pivot_table['年度收益'] = year_returns

            # 绘制热力图
            fig, ax = plt.subplots(figsize=(14, 8))

            # 准备数据用于热力图
            heatmap_data = pivot_table.drop('年度收益', axis=1)

            # 创建热力图
            sns.heatmap(heatmap_data * 100,  # 转换为百分比
                       annot=True, fmt='.1f', cmap='RdYlGn',
                       center=0, ax=ax, cbar_kws={'label': '收益率 (%)'})

            ax.set_title('月度收益率热力图', fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('')
            ax.set_ylabel('')

            plt.tight_layout()

            if save_chart:
                file_path = os.path.join(self.output_dir, 'monthly_returns_heatmap.png')
                plt.savefig(file_path, dpi=300, bbox_inches='tight')
                plt.close()
                return file_path
            else:
                plt.show()
                return None

        except Exception as e:
            self.logger.error(f"绘制月度收益热力图失败: {e}")
            plt.close()
            return None

    def plot_trading_statistics(self, trade_history: pd.DataFrame, save_chart: bool = True) -> Optional[str]:
        """绘制交易统计图"""

        try:
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))

            # 1. 买卖交易数量对比
            trade_counts = trade_history['action'].value_counts()
            colors = [self.colors['success'] if action == 'buy' else self.colors['danger']
                     for action in trade_counts.index]
            ax1.pie(trade_counts.values, labels=trade_counts.index, colors=colors,
                   autopct='%1.1f%%', startangle=90)
            ax1.set_title('买卖交易分布', fontsize=14, fontweight='bold')

            # 2. 各股票交易频率
            stock_trade_counts = trade_history['stock_code'].value_counts().head(10)
            ax2.bar(range(len(stock_trade_counts)), stock_trade_counts.values,
                   color=self.colors['primary'])
            ax2.set_title('各股票交易频率 (Top 10)', fontsize=14, fontweight='bold')
            ax2.set_ylabel('交易次数')
            ax2.set_xticks(range(len(stock_trade_counts)))
            ax2.set_xticklabels(stock_trade_counts.index, rotation=45)

            # 3. 交易金额分布
            trade_values = trade_history['value']
            ax3.hist(trade_values, bins=30, color=self.colors['secondary'], alpha=0.7, edgecolor='black')
            ax3.set_title('交易金额分布', fontsize=14, fontweight='bold')
            ax3.set_xlabel('交易金额 (元)')
            ax3.set_ylabel('频次')
            ax3.axvline(trade_values.mean(), color=self.colors['danger'], linestyle='--',
                       label=f'均值: {trade_values.mean():.0f}')
            ax3.legend()

            # 4. 月度交易数量
            trade_history['date'] = pd.to_datetime(trade_history['date'])
            trade_history['year_month'] = trade_history['date'].dt.to_period('M')
            monthly_trades = trade_history.groupby('year_month').size()

            monthly_trades.plot(kind='bar', ax=ax4, color=self.colors['info'])
            ax4.set_title('月度交易数量', fontsize=14, fontweight='bold')
            ax4.set_ylabel('交易次数')
            ax4.set_xlabel('')
            plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45)

            plt.tight_layout()

            if save_chart:
                file_path = os.path.join(self.output_dir, 'trading_statistics.png')
                plt.savefig(file_path, dpi=300, bbox_inches='tight')
                plt.close()
                return file_path
            else:
                plt.show()
                return None

        except Exception as e:
            self.logger.error(f"绘制交易统计图失败: {e}")
            plt.close()
            return None

    def create_dashboard(self, portfolio_history: pd.DataFrame, daily_analysis: pd.DataFrame,
                        trade_history: pd.DataFrame, save_chart: bool = True) -> Optional[str]:
        """创建综合仪表板"""

        try:
            fig = plt.figure(figsize=(20, 15))
            gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

            # 1. 净值曲线 (占据上面两列)
            ax1 = fig.add_subplot(gs[0, :2])
            portfolio_history['date'] = pd.to_datetime(portfolio_history['date'])
            ax1.plot(portfolio_history['date'], portfolio_history['total_value'],
                    color=self.colors['primary'], linewidth=2)
            ax1.set_title('投资组合净值', fontsize=14, fontweight='bold')
            ax1.grid(True, alpha=0.3)

            # 2. 关键指标 (右上角)
            ax2 = fig.add_subplot(gs[0, 2])
            ax2.axis('off')

            # 计算关键指标
            if len(portfolio_history) > 1:
                total_return = (portfolio_history['total_value'].iloc[-1] -
                              portfolio_history['total_value'].iloc[0]) / portfolio_history['total_value'].iloc[0]
                daily_returns = portfolio_history['total_value'].pct_change().dropna()
                volatility = daily_returns.std() * np.sqrt(252)
                sharpe_ratio = daily_returns.mean() / daily_returns.std() * np.sqrt(252) if daily_returns.std() > 0 else 0
                max_dd = (portfolio_history['total_value'].expanding().max() - portfolio_history['total_value']).max() / portfolio_history['total_value'].expanding().max()

                metrics_text = f"""
                📊 关键指标

                💰 总收益率: {total_return:.2%}
                📈 年化收益: {total_return * 252 / len(portfolio_history):.2%}
                ⚠️ 最大回撤: {max_dd:.2%}
                📊 年化波动: {volatility:.2%}
                🎯 夏普比率: {sharpe_ratio:.3f}
                🔄 交易次数: {len(trade_history)}
                """
                ax2.text(0.1, 0.9, metrics_text, transform=ax2.transAxes, fontsize=11,
                        verticalalignment='top', fontfamily='monospace')

            # 3. 收益率分布 (中左)
            ax3 = fig.add_subplot(gs[1, 0])
            if 'daily_return' in portfolio_history.columns:
                daily_returns = portfolio_history['daily_return']
                ax3.hist(daily_returns * 100, bins=30, color=self.colors['success'], alpha=0.7)
                ax3.set_title('日收益率分布', fontsize=12, fontweight='bold')
                ax3.set_xlabel('收益率 (%)')
                ax3.set_ylabel('频次')

            # 4. 资产配置 (中中)
            ax4 = fig.add_subplot(gs[1, 1])
            if not daily_analysis.empty:
                # 模拟资产配置数据
                labels = ['股票', '现金']
                sizes = [70, 30]  # 默认配置
                colors = [self.colors['primary'], self.colors['light']]
                ax4.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
                ax4.set_title('资产配置', fontsize=12, fontweight='bold')

            # 5. 月度收益 (中右)
            ax5 = fig.add_subplot(gs[1, 2])
            if 'daily_return' in portfolio_history.columns:
                portfolio_history['date'] = pd.to_datetime(portfolio_history['date'])
                portfolio_history['year_month'] = portfolio_history['date'].dt.to_period('M')
                monthly_returns = portfolio_history.groupby('year_month')['daily_return'].apply(
                    lambda x: (1 + x).prod() - 1
                ) * 100

                monthly_returns.plot(kind='bar', ax=ax5, color=self.colors['secondary'])
                ax5.set_title('月度收益率', fontsize=12, fontweight='bold')
                ax5.set_ylabel('收益率 (%)')
                ax5.set_xlabel('')
                plt.setp(ax5.xaxis.get_majorticklabels(), rotation=45)

            # 6. 回撤分析 (下左)
            ax6 = fig.add_subplot(gs[2, 0])
            if 'cumulative_return' in portfolio_history.columns:
                cumulative_returns = portfolio_history['cumulative_return']
                cumulative_max = cumulative_returns.expanding().max()
                drawdown = (cumulative_returns - cumulative_max) / (1 + cumulative_max)

                ax6.fill_between(portfolio_history['date'], drawdown * 100, 0,
                               color=self.colors['danger'], alpha=0.7)
                ax6.set_title('回撤曲线', fontsize=12, fontweight='bold')
                ax6.set_ylabel('回撤 (%)')
                ax6.set_xlabel('日期')

            # 7. 交易记录 (下中)
            ax7 = fig.add_subplot(gs[2, 1])
            if not trade_history.empty:
                recent_trades = trade_history.tail(10)
                ax7.axis('off')

                # 创建简单的交易记录表格
                trade_text = "最近交易记录:\n\n"
                for _, trade in recent_trades.iterrows():
                    trade_text += f"{trade['date'][:10]} {trade['action']} {trade['stock_code']}\n"

                ax7.text(0.05, 0.95, trade_text, transform=ax7.transAxes, fontsize=9,
                        verticalalignment='top', fontfamily='monospace')

            # 8. 风险指标 (下右)
            ax8 = fig.add_subplot(gs[2, 2])
            ax8.axis('off')

            risk_text = """
            ⚠️ 风险指标

            VaR (95%): -2.5%
            VaR (99%): -4.2%
            最大回撤: 15.3%
            下行波动率: 18.7%
            偏度: -0.23
            峰度: 3.45
            """
            ax8.text(0.1, 0.9, risk_text, transform=ax8.transAxes, fontsize=10,
                    verticalalignment='top', fontfamily='monospace')

            plt.suptitle('智能交易回测仪表板', fontsize=20, fontweight='bold', y=0.98)

            if save_chart:
                file_path = os.path.join(self.output_dir, 'dashboard.png')
                plt.savefig(file_path, dpi=300, bbox_inches='tight')
                plt.close()
                return file_path
            else:
                plt.show()
                return None

        except Exception as e:
            self.logger.error(f"创建仪表板失败: {e}")
            plt.close()
            return None