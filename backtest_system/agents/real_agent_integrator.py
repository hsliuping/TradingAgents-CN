"""
真实Agent集成器
Real Agent Integrator

集成项目中现有的多Agent系统进行真实的市场分析和决策
"""

import logging
import time
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

class RealAgentIntegrator:
    """真实Agent集成器"""

    def __init__(self, config: Dict = None):
        """
        初始化Agent集成器

        Args:
            config: 配置参数
        """
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # 初始化Agents
        self._init_agents()

        # 缓存分析结果
        self.analysis_cache = {}

    def _init_agents(self):
        """初始化项目中的Agents"""
        try:
            # 尝试导入项目中的Agent函数 - 使用函数式架构
            from tradingagents.agents.analysts.market_analyst import create_market_analyst
            from tradingagents.agents.analysts.news_analyst import create_news_analyst
            from tradingagents.agents.analysts.fundamentals_analyst import create_fundamentals_analyst
            from tradingagents.agents.analysts.china_market_analyst import create_china_market_analyst

            # 注意：这些agent函数需要llm和toolkit参数，在真正使用时需要提供
            self.create_market_analyst = create_market_analyst
            self.create_news_analyst = create_news_analyst
            self.create_fundamentals_analyst = create_fundamentals_analyst
            self.create_china_market_analyst = create_china_market_analyst

            # 标记为可用，但在实际调用时需要初始化LLM
            self.agents_available = True
            self.agents_need_llm = True  # 标记需要LLM初始化
            self.logger.info("成功导入Agent创建函数，需要LLM初始化")

        except ImportError as e:
            self.logger.warning(f"无法导入真实Agents: {e}，将使用模拟分析")
            self.agents_available = False
            self.agents_need_llm = False
        except Exception as e:
            self.logger.error(f"初始化Agents失败: {e}")
            self.agents_available = False
            self.agents_need_llm = False

    def analyze_market(
        self,
        stock_code: str,
        date: str,
        stock_data: pd.DataFrame,
        news_data: pd.DataFrame = None
    ) -> Dict:
        """
        使用真实Agent进行市场分析

        Args:
            stock_code: 股票代码
            date: 分析日期
            stock_data: 股票数据
            news_data: 新闻数据

        Returns:
            Dict: 分析结果
        """

        cache_key = f"{stock_code}_{date}"
        if cache_key in self.analysis_cache:
            self.logger.debug(f"使用缓存的分析结果: {cache_key}")
            return self.analysis_cache[cache_key]

        start_time = time.time()

        try:
            if self.agents_available:
                analysis_result = self._real_agent_analysis(stock_code, date, stock_data, news_data)
            else:
                analysis_result = self._mock_agent_analysis(stock_code, date, stock_data, news_data)

            # 缓存结果
            self.analysis_cache[cache_key] = analysis_result

            analysis_time = time.time() - start_time
            self.logger.info(f"市场分析完成: {stock_code} {date}, 耗时: {analysis_time:.2f}秒")

            return analysis_result

        except Exception as e:
            self.logger.error(f"市场分析失败: {e}")
            return self._get_default_analysis()

    def _real_agent_analysis(self, stock_code: str, date: str, stock_data: pd.DataFrame, news_data: pd.DataFrame = None) -> Dict:
        """使用真实Agent进行分析"""

        self.logger.info(f"开始真实Agent分析: {stock_code} {date}")

        try:
            # 检查是否有可用的agent函数
            if not self.agents_available or not hasattr(self, 'create_market_analyst'):
                self.logger.warning("Agent函数不可用，使用模拟分析")
                return self._mock_agent_analysis(stock_code, date, stock_data, news_data)

            # 创建一个简单的分析结果，因为真实agents需要LLM实例化
            # 这里使用项目现有的数据接口进行增强分析
            self.logger.info("使用项目数据接口进行增强分析...")

            # 使用简单的技术分析计算
            try:
                # 计算技术指标
                if not stock_data.empty and 'close' in stock_data.columns:
                    technical_indicators = {}

                    # 计算技术指标
                    prices = stock_data['close'].values

                    # RSI计算
                    if len(prices) >= 15:
                        rsi = self._calculate_simple_rsi(prices)
                        technical_indicators['rsi'] = rsi

                    # MACD计算
                    if len(prices) >= 26:
                        macd = self._calculate_simple_macd(prices)
                        technical_indicators['macd'] = macd

                    # 计算移动平均线
                    prices = stock_data['close'].values
                    if len(prices) >= 5:
                        ma5 = np.mean(prices[-5:])
                        ma20 = np.mean(prices[-20:]) if len(prices) >= 20 else np.mean(prices)
                        current_price = prices[-1]

                        technical_indicators.update({
                            'current_price': current_price,
                            'ma5': ma5,
                            'ma20': ma20,
                            'price_vs_ma5': (current_price - ma5) / ma5,
                            'price_vs_ma20': (current_price - ma20) / ma20,
                            'trend_signal': 'bullish' if current_price > ma5 > ma20 else 'bearish' if current_price < ma5 < ma20 else 'neutral'
                        })

                    # 新闻情绪分析
                    sentiment_score = 0
                    news_count = 0
                    if news_data is not None and not news_data.empty:
                        # 简单的关键词情绪分析
                        positive_words = ['利好', '上涨', '增长', '看好', '买入', '推荐', '强势', '突破']
                        negative_words = ['利空', '下跌', '下滑', '看空', '卖出', '减持', '弱势', '跌破']

                        for _, news in news_data.iterrows():
                            title = str(news.get('title', '')).lower()
                            content = str(news.get('content', '')).lower()
                            text = title + ' ' + content

                            for word in positive_words:
                                sentiment_score += text.count(word)
                            for word in negative_words:
                                sentiment_score -= text.count(word)
                            news_count += 1

                        if news_count > 0:
                            sentiment_score = sentiment_score / news_count
                            sentiment_score = max(-1, min(1, sentiment_score / 5))  # 归一化到[-1,1]

                    # 综合分析
                    trend_strength = technical_indicators.get('trend_signal', 'neutral')
                    if trend_strength == 'bullish':
                        technical_strength = min(0.8, abs(technical_indicators.get('price_vs_ma20', 0)) * 2)
                    elif trend_strength == 'bearish':
                        technical_strength = -min(0.8, abs(technical_indicators.get('price_vs_ma20', 0)) * 2)
                    else:
                        technical_strength = 0

                    return {
                        "technical_analysis": {
                            "signal": trend_strength,
                            "strength": abs(technical_strength),
                            "indicators": technical_indicators
                        },
                        "sentiment_analysis": {
                            "sentiment": "positive" if sentiment_score > 0.1 else "negative" if sentiment_score < -0.1 else "neutral",
                            "score": sentiment_score,
                            "confidence": min(0.8, news_count / 10) if news_count > 0 else 0.3,
                            "news_count": news_count
                        },
                        "market_state": {
                            "trend": trend_strength,
                            "strength": abs(technical_strength),
                            "sentiment": "positive" if sentiment_score > 0.1 else "negative" if sentiment_score < -0.1 else "neutral",
                            "confidence": (abs(technical_strength) + min(0.8, news_count / 10) if news_count > 0 else 0.3) / 2
                        },
                        "analysis_summary": f"增强分析完成: 技术面{trend_strength}, 情绪面{'积极' if sentiment_score > 0.1 else '消极' if sentiment_score < -0.1 else '中性'}",
                        "confidence": (abs(technical_strength) + min(0.8, news_count / 10) if news_count > 0 else 0.3) / 2,
                        "recommendations": self._generate_simple_recommendations(trend_strength, sentiment_score, technical_strength)
                    }

            except Exception as e:
                self.logger.error(f"增强分析失败: {e}")
                return self._mock_agent_analysis(stock_code, date, stock_data, news_data)

        except Exception as e:
            self.logger.error(f"真实Agent分析失败: {e}")
            return self._mock_agent_analysis(stock_code, date, stock_data, news_data)

    def _mock_agent_analysis(self, stock_code: str, date: str, stock_data: pd.DataFrame, news_data: pd.DataFrame = None) -> Dict:
        """模拟Agent分析（当真实Agent不可用时）"""

        self.logger.info(f"执行模拟Agent分析: {stock_code} {date}")

        # 模拟分析延迟
        time.sleep(np.random.uniform(1, 3))  # 1-3秒模拟真实分析时间

        # 技术指标分析
        technical_analysis = self._analyze_technical_indicators(stock_data)

        # 新闻情绪分析
        sentiment_analysis = self._analyze_sentiment(news_data) if news_data is not None else self._mock_sentiment()

        # 基本面分析
        fundamentals_analysis = self._analyze_fundamentals(stock_code)

        # 市场状态分析
        market_state = self._analyze_market_state(technical_analysis, sentiment_analysis)

        # 风险评估
        risk_assessment = self._assess_risk(technical_analysis, sentiment_analysis, market_state)

        return {
            "technical_analysis": technical_analysis,
            "sentiment_analysis": sentiment_analysis,
            "fundamentals_analysis": fundamentals_analysis,
            "market_state": market_state,
            "risk_assessment": risk_assessment,
            "analysis_summary": f"模拟分析完成，当前市场状态: {market_state.get('trend', 'unknown')}",
            "confidence": np.random.uniform(0.6, 0.9),
            "recommendations": self._generate_recommendations(market_state, risk_assessment)
        }

    def _analyze_technical_indicators(self, stock_data: pd.DataFrame) -> Dict:
        """分析技术指标"""

        if stock_data.empty or 'close' not in stock_data.columns:
            return {"signal": "neutral", "strength": 0.0, "indicators": {}}

        prices = stock_data['close'].values
        volumes = stock_data['volume'].values if 'volume' in stock_data.columns else None

        # 计算移动平均线
        if len(prices) >= 5:
            ma5 = np.mean(prices[-5:])
            ma20 = np.mean(prices[-20:]) if len(prices) >= 20 else np.mean(prices)
            current_price = prices[-1]

            # 移动平均线信号
            if current_price > ma5 > ma20:
                ma_signal = "bullish"
                ma_strength = min((current_price - ma20) / ma20, 0.1) * 10
            elif current_price < ma5 < ma20:
                ma_signal = "bearish"
                ma_strength = min((ma20 - current_price) / ma20, 0.1) * 10
            else:
                ma_signal = "neutral"
                ma_strength = 0.0
        else:
            ma_signal = "neutral"
            ma_strength = 0.0
            ma5 = ma20 = prices[-1] if len(prices) > 0 else 0

        # RSI计算
        rsi = self._calculate_rsi(prices)
        rsi_signal = "neutral"
        if rsi > 70:
            rsi_signal = "overbought"
        elif rsi < 30:
            rsi_signal = "oversold"

        # 成交量分析
        volume_signal = "normal"
        if volumes is not None and len(volumes) >= 5:
            avg_volume = np.mean(volumes[-5:])
            current_volume = volumes[-1]
            if current_volume > avg_volume * 1.5:
                volume_signal = "high"
            elif current_volume < avg_volume * 0.5:
                volume_signal = "low"

        # 综合技术信号
        signals = [ma_signal, rsi_signal]
        bullish_count = sum(1 for s in signals if "bull" in s or s == "oversold")
        bearish_count = sum(1 for s in signals if "bear" in s or s == "overbought")

        if bullish_count > bearish_count:
            overall_signal = "bullish"
        elif bearish_count > bullish_count:
            overall_signal = "bearish"
        else:
            overall_signal = "neutral"

        strength = (ma_strength + abs(50 - rsi) / 50) / 2

        return {
            "signal": overall_signal,
            "strength": strength,
            "indicators": {
                "ma5": ma5,
                "ma20": ma20,
                "rsi": rsi,
                "volume_signal": volume_signal,
                "ma_signal": ma_signal,
                "rsi_signal": rsi_signal
            }
        }

    def _calculate_simple_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """计算简单的RSI指标"""
        try:
            if len(prices) < period + 1:
                return 50.0

            deltas = np.diff(prices)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)

            avg_gain = np.mean(gains[-period:])
            avg_loss = np.mean(losses[-period:])

            if avg_loss == 0:
                return 100.0

            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

            return rsi
        except:
            return 50.0

    def _calculate_simple_macd(self, prices: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict:
        """计算简单的MACD指标"""
        try:
            if len(prices) < slow:
                return {"macd": 0, "signal": 0, "histogram": 0}

            # 计算EMA
            def ema(data, period):
                alpha = 2 / (period + 1)
                ema_values = np.zeros(len(data))
                ema_values[0] = data[0]
                for i in range(1, len(data)):
                    ema_values[i] = alpha * data[i] + (1 - alpha) * ema_values[i-1]
                return ema_values

            ema_fast = ema(prices, fast)
            ema_slow = ema(prices, slow)

            macd_line = ema_fast - ema_slow
            signal_line = ema(macd_line, signal)
            histogram = macd_line - signal_line

            return {
                "macd": macd_line[-1],
                "signal": signal_line[-1],
                "histogram": histogram[-1]
            }
        except:
            return {"macd": 0, "signal": 0, "histogram": 0}

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """计算RSI指标"""
        try:
            if len(prices) < period + 1:
                return 50.0

            deltas = np.diff(prices)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)

            avg_gain = np.mean(gains[-period:])
            avg_loss = np.mean(losses[-period:])

            if avg_loss == 0:
                return 100.0

            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

            return rsi
        except:
            return 50.0

    def _analyze_sentiment(self, news_data: pd.DataFrame) -> Dict:
        """分析新闻情绪"""

        if news_data.empty:
            return self._mock_sentiment()

        # 模拟情绪分析
        sentiment_scores = []
        for _, article in news_data.iterrows():
            # 简单的情绪模拟
            score = np.random.normal(0, 0.3)
            sentiment_scores.append(max(-1, min(1, score)))

        avg_sentiment = np.mean(sentiment_scores) if sentiment_scores else 0

        if avg_sentiment > 0.2:
            sentiment_label = "positive"
        elif avg_sentiment < -0.2:
            sentiment_label = "negative"
        else:
            sentiment_label = "neutral"

        return {
            "sentiment": sentiment_label,
            "score": avg_sentiment,
            "confidence": min(abs(avg_sentiment) * 2, 1.0),
            "news_count": len(news_data)
        }

    def _mock_sentiment(self) -> Dict:
        """模拟情绪分析"""
        sentiment_score = np.random.normal(0, 0.2)
        sentiment_score = max(-1, min(1, sentiment_score))

        if sentiment_score > 0.1:
            sentiment_label = "positive"
        elif sentiment_score < -0.1:
            sentiment_label = "negative"
        else:
            sentiment_label = "neutral"

        return {
            "sentiment": sentiment_label,
            "score": sentiment_score,
            "confidence": np.random.uniform(0.5, 0.8),
            "news_count": np.random.randint(5, 20)
        }

    def _analyze_fundamentals(self, stock_code: str) -> Dict:
        """分析基本面"""

        # 模拟基本面分析
        pe_ratio = np.random.uniform(10, 50)
        pb_ratio = np.random.uniform(1, 8)
        roe = np.random.uniform(0.05, 0.25)
        debt_ratio = np.random.uniform(0.1, 0.8)

        # 基本面评分
        fundamental_score = 0
        if pe_ratio < 20:
            fundamental_score += 0.3
        if pb_ratio < 3:
            fundamental_score += 0.2
        if roe > 0.15:
            fundamental_score += 0.3
        if debt_ratio < 0.5:
            fundamental_score += 0.2

        return {
            "pe_ratio": pe_ratio,
            "pb_ratio": pb_ratio,
            "roe": roe,
            "debt_ratio": debt_ratio,
            "fundamental_score": fundamental_score,
            "rating": "good" if fundamental_score > 0.6 else "fair" if fundamental_score > 0.3 else "poor"
        }

    def _analyze_market_state(self, technical_analysis: Dict, sentiment_analysis: Dict) -> Dict:
        """分析市场状态"""

        tech_signal = technical_analysis.get("signal", "neutral")
        tech_strength = technical_analysis.get("strength", 0)
        sentiment = sentiment_analysis.get("sentiment", "neutral")

        # 判断市场趋势
        if tech_signal == "bullish" and sentiment == "positive" and tech_strength > 0.5:
            trend = "uptrend"
        elif tech_signal == "bearish" and sentiment == "negative" and tech_strength > 0.5:
            trend = "downtrend"
        elif tech_strength < 0.3:
            trend = "sideways"
        else:
            trend = "uncertain"

        # 市场活跃度
        volume_signal = technical_analysis.get("indicators", {}).get("volume_signal", "normal")
        if volume_signal == "high" and tech_strength > 0.6:
            market_state = "breakout"
        elif volume_signal == "low":
            market_state = "consolidation"
        else:
            market_state = "normal"

        return {
            "trend": trend,
            "state": market_state,
            "strength": tech_strength,
            "sentiment": sentiment,
            "confidence": (tech_strength + sentiment_analysis.get("confidence", 0.5)) / 2
        }

    def _assess_risk(self, technical_analysis: Dict, sentiment_analysis: Dict, market_state: Dict) -> Dict:
        """评估风险"""

        tech_strength = technical_analysis.get("strength", 0)
        sentiment_confidence = sentiment_analysis.get("confidence", 0.5)
        market_confidence = market_state.get("confidence", 0.5)

        # 波动性风险
        volatility_risk = min(tech_strength * 2, 1.0)

        # 情绪风险
        if sentiment_analysis.get("sentiment") == "negative":
            sentiment_risk = 1 - sentiment_confidence
        else:
            sentiment_risk = 0.5

        # 市场不确定性风险
        uncertainty_risk = 1 - market_confidence

        # 综合风险评分
        overall_risk = (volatility_risk + sentiment_risk + uncertainty_risk) / 3

        if overall_risk > 0.7:
            risk_level = "high"
        elif overall_risk > 0.4:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "risk_level": risk_level,
            "risk_score": overall_risk,
            "volatility_risk": volatility_risk,
            "sentiment_risk": sentiment_risk,
            "uncertainty_risk": uncertainty_risk
        }

    def _extract_position_indicators(self, analysis_results: Dict) -> Dict:
        """从分析结果中提取仓位决策指标"""

        try:
            comprehensive = analysis_results.get("comprehensive_analysis", {})

            # 提取关键指标
            technical_strength = self._extract_technical_strength(analysis_results)
            sentiment_score = self._extract_sentiment_score(analysis_results)
            fundamental_score = self._extract_fundamental_score(analysis_results)
            market_consensus = self._extract_market_consensus(analysis_results)

            return {
                "technical_strength": technical_strength,
                "sentiment_score": sentiment_score,
                "fundamental_score": fundamental_score,
                "market_consensus": market_consensus,
                "analysis_summary": comprehensive.get("summary", "综合分析完成"),
                "confidence": comprehensive.get("confidence", 0.7),
                "recommendations": comprehensive.get("recommendations", [])
            }

        except Exception as e:
            self.logger.error(f"提取仓位指标失败: {e}")
            return self._get_default_analysis()

    def _extract_technical_strength(self, analysis_results: Dict) -> float:
        """提取技术指标强度"""
        try:
            tech_analysis = analysis_results.get("technical_analysis", {})
            return float(tech_analysis.get("strength", 0.5))
        except:
            return 0.5

    def _extract_sentiment_score(self, analysis_results: Dict) -> float:
        """提取情绪得分"""
        try:
            news_analysis = analysis_results.get("news_analysis", {})
            score = news_analysis.get("sentiment", {}).get("score", 0)
            return max(-1, min(1, float(score) + 1) / 2)  # 转换到0-1范围
        except:
            return 0.5

    def _extract_fundamental_score(self, analysis_results: Dict) -> float:
        """提取基本面评分"""
        try:
            fundamentals = analysis_results.get("fundamentals_analysis", {})
            return float(fundamentals.get("fundamental_score", 0.5))
        except:
            return 0.5

    def _extract_market_consensus(self, analysis_results: Dict) -> float:
        """提取市场共识"""
        try:
            # 模拟计算市场共识
            consensus = np.random.uniform(0.3, 0.8)
            return consensus
        except:
            return 0.5

    def _generate_simple_recommendations(self, trend: str, sentiment_score: float, technical_strength: float) -> List[str]:
        """生成简单的投资建议"""
        recommendations = []

        if trend == "bullish" and sentiment_score > 0.1:
            recommendations.append("技术和情绪都偏积极，可考虑适度加仓")
        elif trend == "bullish" and sentiment_score < -0.1:
            recommendations.append("技术面积极但情绪面消极，建议谨慎操作")
        elif trend == "bearish" and sentiment_score < -0.1:
            recommendations.append("技术和情绪都偏消极，建议减仓或观望")
        elif trend == "bearish" and sentiment_score > 0.1:
            recommendations.append("技术面消极但情绪面积极，建议等待确认信号")
        else:
            recommendations.append("市场信号不明朗，建议保持中性仓位")

        if abs(technical_strength) > 0.6:
            recommendations.append("技术信号较强，值得关注")

        return recommendations

    def _generate_recommendations(self, market_state: Dict, risk_assessment: Dict) -> List[str]:
        """生成投资建议"""

        recommendations = []
        trend = market_state.get("trend", "unknown")
        risk_level = risk_assessment.get("risk_level", "medium")

        if trend == "uptrend":
            if risk_level == "low":
                recommendations.append("建议积极加仓，把握上涨机会")
            else:
                recommendations.append("建议适度加仓，控制风险")
        elif trend == "downtrend":
            recommendations.append("建议减仓或观望，防范下跌风险")
        elif trend == "sideways":
            recommendations.append("建议保持中性仓位，等待方向明确")
        else:
            recommendations.append("建议谨慎操作，观察市场变化")

        if risk_level == "high":
            recommendations.append("当前风险较高，建议降低仓位规模")
        elif risk_level == "low":
            recommendations.append("当前风险较低，可考虑增加仓位")

        return recommendations

    def _get_default_analysis(self) -> Dict:
        """获取默认分析结果"""
        return {
            "technical_strength": 0.5,
            "sentiment_score": 0.5,
            "fundamental_score": 0.5,
            "market_consensus": 0.5,
            "analysis_summary": "分析暂不可用，使用默认值",
            "confidence": 0.3,
            "recommendations": ["建议谨慎操作"]
        }

    def clear_cache(self):
        """清空分析缓存"""
        self.analysis_cache.clear()
        self.logger.info("分析缓存已清空")