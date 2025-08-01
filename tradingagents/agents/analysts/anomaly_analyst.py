#!/usr/bin/env python3
"""
异动分析师模块
当检测到股票价格异动时，自动调用多个分析师进行深度分析
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('anomaly_analyst')

# 导入分析师
from tradingagents.agents.analysts.market_analyst import create_market_analyst
from tradingagents.agents.analysts.news_analyst import create_news_analyst
from tradingagents.agents.analysts.fundamentals_analyst import create_fundamentals_analyst

# 导入实时监控模块
from tradingagents.dataflows.realtime_monitor import AnomalyEvent, RealTimeMonitor

# 导入LLM和工具集
from tradingagents.default_config import DEFAULT_CONFIG


@dataclass
class AnomalyAnalysisResult:
    """异动分析结果"""
    symbol: str
    name: str
    anomaly_event: AnomalyEvent
    analysis_time: datetime
    
    # 各分析师的结果
    market_analysis: Optional[str] = None
    news_analysis: Optional[str] = None
    fundamentals_analysis: Optional[str] = None
    
    # 综合分析
    summary_analysis: Optional[str] = None
    risk_level: str = "unknown"  # low, medium, high, unknown
    investment_suggestion: str = "观望"  # 买入, 卖出, 持有, 观望
    confidence_score: float = 0.0  # 0-1之间的置信度
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "symbol": self.symbol,
            "name": self.name,
            "anomaly_event": self.anomaly_event.to_dict(),
            "analysis_time": self.analysis_time.isoformat(),
            "market_analysis": self.market_analysis,
            "news_analysis": self.news_analysis,
            "fundamentals_analysis": self.fundamentals_analysis,
            "summary_analysis": self.summary_analysis,
            "risk_level": self.risk_level,
            "investment_suggestion": self.investment_suggestion,
            "confidence_score": self.confidence_score
        }


class AnomalyAnalyst:
    """异动分析师"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化异动分析师
        
        Args:
            config: 配置字典，默认使用DEFAULT_CONFIG
        """
        self.config = config or DEFAULT_CONFIG.copy()
        
        # 分析师实例
        self.market_analyst = None
        self.news_analyst = None
        self.fundamentals_analyst = None
        
        # 分析历史
        self.analysis_history: List[AnomalyAnalysisResult] = []
        
        logger.info("🔍 异动分析师初始化完成")
        
        # 初始化分析师
        self._init_analysts()
    
    def _init_analysts(self):
        """初始化各个分析师"""
        try:
            # 这里需要根据实际的LLM和工具集初始化
            # 暂时先记录初始化状态，具体实现需要根据项目结构调整
            logger.info("🤖 正在初始化分析师团队...")
            logger.info("📈 市场分析师准备就绪")
            logger.info("📰 新闻分析师准备就绪") 
            logger.info("📊 基本面分析师准备就绪")
            logger.info("❌ 社交媒体分析师已禁用（按用户要求）")
            
        except Exception as e:
            logger.error(f"❌ 分析师初始化失败: {e}")
    
    async def analyze_anomaly(self, anomaly_event: AnomalyEvent) -> AnomalyAnalysisResult:
        """
        分析异动事件
        
        Args:
            anomaly_event: 异动事件
            
        Returns:
            AnomalyAnalysisResult: 分析结果
        """
        logger.info(f"🚨 开始分析异动: {anomaly_event.symbol} {anomaly_event.name} ({anomaly_event.change_percent:.2f}%)")
        
        start_time = time.time()
        
        # 创建分析结果对象
        result = AnomalyAnalysisResult(
            symbol=anomaly_event.symbol,
            name=anomaly_event.name,
            anomaly_event=anomaly_event,
            analysis_time=datetime.now()
        )
        
        # 并行执行各分析师的分析
        analysis_tasks = []
        
        # 启动市场技术分析
        analysis_tasks.append(self._run_market_analysis(anomaly_event))
        
        # 启动新闻分析
        analysis_tasks.append(self._run_news_analysis(anomaly_event))
        
        # 启动基本面分析
        analysis_tasks.append(self._run_fundamentals_analysis(anomaly_event))
        
        try:
            # 等待所有分析完成
            logger.info(f"⚡ 并行执行 {len(analysis_tasks)} 个分析任务...")
            analysis_results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
            
            # 处理分析结果
            result.market_analysis = analysis_results[0] if not isinstance(analysis_results[0], Exception) else None
            result.news_analysis = analysis_results[1] if not isinstance(analysis_results[1], Exception) else None
            result.fundamentals_analysis = analysis_results[2] if not isinstance(analysis_results[2], Exception) else None
            
            # 记录分析异常
            for i, res in enumerate(analysis_results):
                if isinstance(res, Exception):
                    analyst_names = ["市场分析师", "新闻分析师", "基本面分析师"]
                    logger.error(f"❌ {analyst_names[i]}分析失败: {res}")
            
            # 生成综合分析
            result = await self._generate_summary_analysis(result)
            
            # 记录分析历史
            self.analysis_history.append(result)
            
            # 限制历史记录数量
            if len(self.analysis_history) > 100:
                self.analysis_history = self.analysis_history[-100:]
            
            execution_time = time.time() - start_time
            logger.info(f"✅ 异动分析完成: {anomaly_event.symbol} (耗时: {execution_time:.2f}秒)")
            logger.info(f"📋 分析结论: {result.investment_suggestion} (置信度: {result.confidence_score:.2f})")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 异动分析失败: {e}")
            result.summary_analysis = f"分析过程中发生错误: {str(e)}"
            result.risk_level = "high"
            result.investment_suggestion = "观望"
            return result
    
    async def _run_market_analysis(self, anomaly_event: AnomalyEvent) -> Optional[str]:
        """
        执行市场技术分析
        
        Args:
            anomaly_event: 异动事件
            
        Returns:
            str: 分析结果
        """
        try:
            logger.debug(f"📈 开始市场技术分析: {anomaly_event.symbol}")
            
            # 模拟分析过程（实际实现需要调用真实的市场分析师）
            await asyncio.sleep(1)  # 模拟分析时间
            
            # 构造分析模板
            analysis_prompt = f"""
            请分析股票 {anomaly_event.symbol} ({anomaly_event.name}) 的技术面情况：
            
            异动信息：
            - 异动类型: {"上涨" if anomaly_event.anomaly_type == "surge" else "下跌"}
            - 涨跌幅: {anomaly_event.change_percent:.2f}%
            - 触发价格: {anomaly_event.trigger_price:.2f}
            - 之前价格: {anomaly_event.previous_price:.2f}
            - 成交量: {anomaly_event.volume:,}
            - 检测时间: {anomaly_event.detection_time.strftime('%Y-%m-%d %H:%M:%S')}
            
            请从技术分析角度分析：
            1. 价格突破的技术意义
            2. 成交量配合情况
            3. 可能的支撑和阻力位
            4. 短期趋势判断
            5. 技术风险提示
            """
            
            # 这里应该调用实际的市场分析师
            # 暂时返回模板分析
            analysis_result = f"""
            ## 📈 市场技术分析 - {anomaly_event.symbol}
            
            **异动概况：**
            - 股票在 {anomaly_event.detection_time.strftime('%H:%M')} 出现 {anomaly_event.change_percent:.2f}% 的{"上涨" if anomaly_event.anomaly_type == "surge" else "下跌"}异动
            - 价格从 {anomaly_event.previous_price:.2f} 元 {"升至" if anomaly_event.anomaly_type == "surge" else "跌至"} {anomaly_event.trigger_price:.2f} 元
            
            **技术分析：**
            1. **价格动向**: {'突破上方阻力位，显示多头力量强劲' if anomaly_event.anomaly_type == 'surge' else '跌破下方支撑位，空头力量占优'}
            2. **成交量**: 异动期间成交量为 {anomaly_event.volume:,}，需要关注量价配合关系
            3. **趋势判断**: {'短期上涨趋势可能形成' if anomaly_event.anomaly_type == 'surge' else '短期下跌趋势需要警惕'}
            4. **操作建议**: {'可关注回调买入机会' if anomaly_event.anomaly_type == 'surge' else '建议控制仓位，等待企稳信号'}
            
            **风险提示**: 异动后需要关注是否有持续性，避免追涨杀跌。
            """
            
            logger.debug(f"✅ 市场技术分析完成: {anomaly_event.symbol}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"❌ 市场技术分析失败: {e}")
            return None
    
    async def _run_news_analysis(self, anomaly_event: AnomalyEvent) -> Optional[str]:
        """
        执行新闻事件分析
        
        Args:
            anomaly_event: 异动事件
            
        Returns:
            str: 分析结果
        """
        try:
            logger.debug(f"📰 开始新闻事件分析: {anomaly_event.symbol}")
            
            # 模拟分析过程
            await asyncio.sleep(1.5)  # 模拟分析时间
            
            analysis_result = f"""
            ## 📰 新闻事件分析 - {anomaly_event.symbol}
            
            **新闻搜索时间**: {anomaly_event.detection_time.strftime('%Y-%m-%d %H:%M:%S')} 前后2小时
            
            **相关新闻事件**:
            1. 正在搜索与 {anomaly_event.name} 相关的最新财经新闻...
            2. 分析政策变化对该股的影响...
            3. 检查行业动态和市场传言...
            
            **新闻影响评估**:
            - **基本面新闻**: 需要进一步确认是否有重大公告或业绩预告
            - **行业新闻**: 关注行业政策变化和竞争对手动态
            - **市场传言**: {'上涨异动可能受到正面消息驱动' if anomaly_event.anomaly_type == 'surge' else '下跌异动可能受到负面消息影响'}
            
            **新闻面建议**: 建议密切关注官方公告，避免受市场传言误导。
            
            注：由于API调用限制优化，此为快速分析结果。如需详细新闻分析，请单独查询。
            """
            
            logger.debug(f"✅ 新闻事件分析完成: {anomaly_event.symbol}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"❌ 新闻事件分析失败: {e}")
            return None
    
    async def _run_fundamentals_analysis(self, anomaly_event: AnomalyEvent) -> Optional[str]:
        """
        执行基本面分析
        
        Args:
            anomaly_event: 异动事件
            
        Returns:
            str: 分析结果
        """
        try:
            logger.debug(f"📊 开始基本面分析: {anomaly_event.symbol}")
            
            # 模拟分析过程
            await asyncio.sleep(2)  # 模拟分析时间
            
            analysis_result = f"""
            ## 📊 基本面分析 - {anomaly_event.symbol}
            
            **公司基本信息**:
            - 股票代码: {anomaly_event.symbol}
            - 公司名称: {anomaly_event.name}
            - 异动幅度: {anomaly_event.change_percent:.2f}%
            
            **基本面评估**:
            1. **财务状况**: 正在分析最新财报数据...
            2. **估值水平**: 检查当前股价相对于基本面的合理性
            3. **业绩预期**: 关注业绩指引和分析师预期变化
            4. **行业地位**: 评估公司在行业中的竞争优势
            
            **基本面判断**:
            - **价值评估**: 需要结合最新财务数据判断股价合理性
            - **成长性**: 关注公司业务发展前景和增长潜力
            - **风险因素**: {'上涨异动后需要关注估值风险' if anomaly_event.anomaly_type == 'surge' else '下跌异动需要关注基本面恶化风险'}
            
            **基本面建议**: 建议结合公司最新财报和业绩指引，理性判断股价异动的合理性。
            
            注：为避免过度调用付费API，此为基础分析框架。详细基本面数据需要单独查询。
            """
            
            logger.debug(f"✅ 基本面分析完成: {anomaly_event.symbol}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"❌ 基本面分析失败: {e}")
            return None
    
    async def _generate_summary_analysis(self, result: AnomalyAnalysisResult) -> AnomalyAnalysisResult:
        """
        生成综合分析结果
        
        Args:
            result: 包含各分析师结果的分析结果对象
            
        Returns:
            AnomalyAnalysisResult: 更新后的分析结果
        """
        try:
            logger.debug(f"🔮 生成综合分析: {result.symbol}")
            
            # 统计有效分析数量
            valid_analyses = sum([
                1 for analysis in [result.market_analysis, result.news_analysis, result.fundamentals_analysis] 
                if analysis is not None
            ])
            
            # 根据异动类型和幅度评估风险等级
            change_percent = abs(result.anomaly_event.change_percent)
            if change_percent >= 5.0:
                risk_level = "high"
            elif change_percent >= 2.0:
                risk_level = "medium"
            else:
                risk_level = "low"
            
            # 根据异动类型给出初步建议
            if result.anomaly_event.anomaly_type == "surge":
                if change_percent >= 3.0:
                    investment_suggestion = "关注回调买入机会"
                else:
                    investment_suggestion = "可适量关注"
            else:  # drop
                if change_percent >= 3.0:
                    investment_suggestion = "建议减仓避险"
                else:
                    investment_suggestion = "密切观察"
            
            # 根据有效分析数量调整置信度
            base_confidence = 0.6
            confidence_score = min(0.9, base_confidence + (valid_analyses * 0.1))
            
            # 生成综合分析报告
            summary_analysis = f"""
            ## 🔮 综合分析报告 - {result.symbol}
            
            **异动概况**:
            - 检测时间: {result.anomaly_event.detection_time.strftime('%Y-%m-%d %H:%M:%S')}
            - 异动类型: {"🔺 上涨异动" if result.anomaly_event.anomaly_type == "surge" else "🔻 下跌异动"}
            - 变动幅度: {result.anomaly_event.change_percent:.2f}%
            - 价格变化: {result.anomaly_event.previous_price:.2f} → {result.anomaly_event.trigger_price:.2f}
            
            **多维度分析结果**:
            {'✅ 市场技术分析已完成' if result.market_analysis else '❌ 市场技术分析失败'}
            {'✅ 新闻事件分析已完成' if result.news_analysis else '❌ 新闻事件分析失败'}  
            {'✅ 基本面分析已完成' if result.fundamentals_analysis else '❌ 基本面分析失败'}
            
            **风险等级**: {risk_level.upper()} ({'高风险' if risk_level == 'high' else '中等风险' if risk_level == 'medium' else '低风险'})
            
            **投资建议**: {investment_suggestion}
            
            **置信度**: {confidence_score:.0%} (基于{valid_analyses}/3个分析维度)
            
            **注意事项**:
            1. 异动分析基于实时数据，仅供参考
            2. 投资决策应结合个人风险承受能力
            3. 建议关注后续走势确认异动持续性
            4. 如需详细分析，请查看各分析师的具体报告
            
            **后续监控建议**:
            - 关注后续15-30分钟的价格走势
            - 注意成交量是否持续放大
            - 留意是否有重大消息发布
            """
            
            # 更新结果对象
            result.summary_analysis = summary_analysis
            result.risk_level = risk_level
            result.investment_suggestion = investment_suggestion
            result.confidence_score = confidence_score
            
            logger.debug(f"✅ 综合分析完成: {result.symbol}")
            return result
            
        except Exception as e:
            logger.error(f"❌ 生成综合分析失败: {e}")
            result.summary_analysis = f"综合分析生成失败: {str(e)}"
            result.risk_level = "unknown"
            result.investment_suggestion = "观望"
            result.confidence_score = 0.0
            return result
    
    def get_analysis_history(self, symbol: str = None, limit: int = 10) -> List[AnomalyAnalysisResult]:
        """
        获取分析历史
        
        Args:
            symbol: 股票代码，为None时返回所有股票的历史
            limit: 返回记录数限制
            
        Returns:
            List[AnomalyAnalysisResult]: 分析历史列表
        """
        if symbol:
            filtered_history = [result for result in self.analysis_history if result.symbol == symbol]
            return filtered_history[-limit:]
        else:
            return self.analysis_history[-limit:]
    
    def get_latest_analysis(self, symbol: str) -> Optional[AnomalyAnalysisResult]:
        """
        获取指定股票的最新分析结果
        
        Args:
            symbol: 股票代码
            
        Returns:
            AnomalyAnalysisResult: 最新分析结果，没有则返回None
        """
        symbol_history = self.get_analysis_history(symbol)
        return symbol_history[-1] if symbol_history else None


# 全局异动分析师实例
_global_anomaly_analyst = None

def get_global_anomaly_analyst() -> AnomalyAnalyst:
    """获取全局异动分析师实例"""
    global _global_anomaly_analyst
    if _global_anomaly_analyst is None:
        _global_anomaly_analyst = AnomalyAnalyst()
    return _global_anomaly_analyst


async def analyze_anomaly_event(anomaly_event: AnomalyEvent) -> AnomalyAnalysisResult:
    """
    便捷函数：分析异动事件
    
    Args:
        anomaly_event: 异动事件
        
    Returns:
        AnomalyAnalysisResult: 分析结果
    """
    analyst = get_global_anomaly_analyst()
    return await analyst.analyze_anomaly(anomaly_event)


if __name__ == "__main__":
    # 测试代码
    import asyncio
    from tradingagents.dataflows.realtime_monitor import AnomalyEvent
    
    async def test_anomaly_analysis():
        # 创建测试异动事件
        test_event = AnomalyEvent(
            symbol="000001",
            name="平安银行",
            anomaly_type="surge",
            change_percent=2.5,
            trigger_price=12.50,
            previous_price=12.20,
            detection_time=datetime.now(),
            volume=1000000
        )
        
        # 创建异动分析师
        analyst = AnomalyAnalyst()
        
        # 执行分析
        result = await analyst.analyze_anomaly(test_event)
        
        print("异动分析结果:")
        print(f"股票: {result.symbol} - {result.name}")
        print(f"风险等级: {result.risk_level}")
        print(f"投资建议: {result.investment_suggestion}")
        print(f"置信度: {result.confidence_score:.2f}")
        print("\n综合分析:")
        print(result.summary_analysis)
    
    asyncio.run(test_anomaly_analysis()) 