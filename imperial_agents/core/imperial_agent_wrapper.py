"""
帝国AI角色适配层 - 核心包装器
Imperial Agent Wrapper - Core Module

这个模块实现了帝国角色与TradingAgents能力的融合，提供统一的分析接口。
"""

import asyncio
import json
import traceback
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# TradingAgents核心导入
from tradingagents.agents.utils.agent_utils import Toolkit
from tradingagents.utils.logging_init import get_logger
from tradingagents.utils.stock_utils import StockUtils

# 导入LLM支持
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

logger = get_logger("imperial_agents")


class AnalysisType(Enum):
    """分析类型枚举"""
    MARKET_ANALYSIS = "market_analysis"      # 市场分析
    FUNDAMENTAL_ANALYSIS = "fundamental"     # 基本面分析
    TECHNICAL_ANALYSIS = "technical"         # 技术分析
    SENTIMENT_ANALYSIS = "sentiment"         # 情绪分析
    RISK_ANALYSIS = "risk"                   # 风险分析
    NEWS_ANALYSIS = "news"                   # 新闻分析


class DecisionLevel(Enum):
    """决策级别枚举"""
    STRONG_BUY = "强烈买入"
    BUY = "买入"
    HOLD = "持有"
    SELL = "卖出"
    STRONG_SELL = "强烈卖出"
    NEUTRAL = "中性"


@dataclass
class AnalysisResult:
    """分析结果数据结构"""
    role_name: str                          # 角色名称
    analysis_type: AnalysisType            # 分析类型
    symbol: str                            # 股票代码
    decision: DecisionLevel                # 决策建议
    confidence: float                      # 置信度 (0-1)
    reasoning: str                         # 分析理由
    key_factors: List[str]                 # 关键因素
    risk_warnings: List[str]               # 风险提示
    timestamp: datetime                    # 分析时间
    raw_data: Optional[Dict[str, Any]] = None  # 原始数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = asdict(self)
        result['analysis_type'] = self.analysis_type.value
        result['decision'] = self.decision.value
        result['timestamp'] = self.timestamp.isoformat()
        return result


@dataclass
class RoleConfig:
    """角色配置数据结构"""
    name: str                              # 角色名称
    title: str                             # 角色称号
    expertise: List[str]                   # 专业领域
    personality_traits: Dict[str, str]     # 个性特征
    decision_style: str                    # 决策风格
    risk_tolerance: str                    # 风险承受度
    preferred_timeframe: str               # 偏好时间框架
    analysis_focus: List[AnalysisType]     # 分析重点
    system_prompt_template: str           # 系统提示模板
    constraints: List[str]                 # 行为约束
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RoleConfig':
        """从字典创建角色配置"""
        # 处理analysis_focus的枚举转换
        if 'analysis_focus' in data:
            data['analysis_focus'] = [
                AnalysisType(item) if isinstance(item, str) else item 
                for item in data['analysis_focus']
            ]
        return cls(**data)


class ImperialAgentWrapper(ABC):
    """
    帝国AI角色包装器基类
    
    这个类融合了TradingAgents的技术能力与帝国角色的个性特征，
    为每个角色提供统一的分析接口和决策框架。
    """
    
    def __init__(
        self, 
        role_config: RoleConfig,
        llm: Any,
        toolkit: Optional[Toolkit] = None,
        imperial_config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化帝国角色包装器
        
        Args:
            role_config: 角色配置
            llm: 语言模型实例
            toolkit: TradingAgents工具集
            imperial_config: 帝国特色配置
        """
        self.role_config = role_config
        self.llm = llm
        self.toolkit = toolkit or Toolkit()
        self.imperial_config = imperial_config or {}
        
        # 角色状态
        self.analysis_history: List[AnalysisResult] = []
        self.current_context: Dict[str, Any] = {}
        
        logger.info(f"🎭 [帝国角色] {self.role_config.name} 初始化完成")
        logger.info(f"🎯 [角色特征] 专业: {', '.join(self.role_config.expertise)}")
        logger.info(f"⚖️ [决策风格] {self.role_config.decision_style}")
    
    @property
    def name(self) -> str:
        """获取角色名称"""
        return self.role_config.name
    
    @property
    def title(self) -> str:
        """获取角色称号"""
        return self.role_config.title
    
    def get_personality_context(self) -> str:
        """获取个性化上下文"""
        traits = self.role_config.personality_traits
        context_parts = []
        
        for trait, description in traits.items():
            context_parts.append(f"- {trait}: {description}")
        
        return f"""**{self.name}的个性特征**:
{chr(10).join(context_parts)}

**决策风格**: {self.role_config.decision_style}
**风险偏好**: {self.role_config.risk_tolerance}
**分析时框**: {self.role_config.preferred_timeframe}
"""
    
    def create_analysis_prompt(
        self, 
        symbol: str,
        analysis_type: AnalysisType,
        market_data: Optional[str] = None,
        additional_context: Optional[str] = None
    ) -> str:
        """
        创建个性化分析提示
        
        Args:
            symbol: 股票代码
            analysis_type: 分析类型
            market_data: 市场数据
            additional_context: 额外上下文
            
        Returns:
            str: 个性化的分析提示
        """
        # 获取股票市场信息
        market_info = StockUtils.get_market_info(symbol)
        
        # 构建基础上下文
        base_context = f"""# {self.role_config.title} - {analysis_type.value}分析

## 股票信息
- **代码**: {symbol}
- **市场**: {market_info['market_name']}
- **货币**: {market_info['currency_name']} ({market_info['currency_symbol']})

## 角色设定
{self.get_personality_context()}

## 分析要求
- **分析类型**: {analysis_type.value}
- **重点关注**: {', '.join([t.value for t in self.role_config.analysis_focus])}
- **必须提供**: 明确的投资建议和置信度
- **输出语言**: 中文
"""
        
        # 添加市场数据
        if market_data:
            base_context += f"\n## 市场数据\n{market_data}\n"
        
        # 添加额外上下文
        if additional_context:
            base_context += f"\n## 补充信息\n{additional_context}\n"
        
        # 添加角色特定的系统提示
        role_prompt = self.role_config.system_prompt_template.format(
            symbol=symbol,
            market_name=market_info['market_name'],
            currency=market_info['currency_name'],
            analysis_type=analysis_type.value
        )
        
        base_context += f"\n## 角色指令\n{role_prompt}\n"
        
        # 添加输出格式要求
        base_context += f"""
## 输出格式要求
请按以下格式输出分析结果：

**决策建议**: [强烈买入/买入/持有/卖出/强烈卖出/中性]
**置信度**: [0-100]%
**关键因素**: 
- 因素1
- 因素2
- 因素3

**风险提示**:
- 风险1
- 风险2

**详细分析**:
[详细的分析过程和推理]

作为{self.name}，请基于您的专业知识和个性特征进行分析。
"""
        
        return base_context
    
    def parse_analysis_result(
        self, 
        response: str, 
        symbol: str,
        analysis_type: AnalysisType
    ) -> AnalysisResult:
        """
        解析LLM响应为结构化分析结果
        
        Args:
            response: LLM响应
            symbol: 股票代码
            analysis_type: 分析类型
            
        Returns:
            AnalysisResult: 结构化分析结果
        """
        # 默认值
        decision = DecisionLevel.NEUTRAL
        confidence = 0.5
        key_factors = []
        risk_warnings = []
        reasoning = response
        
        try:
            # 解析决策建议
            if "强烈买入" in response:
                decision = DecisionLevel.STRONG_BUY
            elif "买入" in response:
                decision = DecisionLevel.BUY
            elif "强烈卖出" in response:
                decision = DecisionLevel.STRONG_SELL
            elif "卖出" in response:
                decision = DecisionLevel.SELL
            elif "持有" in response:
                decision = DecisionLevel.HOLD
            else:
                decision = DecisionLevel.NEUTRAL
            
            # 解析置信度
            import re
            confidence_match = re.search(r'置信度[：:]\s*(\d+(?:\.\d+)?)%?', response)
            if confidence_match:
                confidence = float(confidence_match.group(1)) / 100
                confidence = max(0, min(1, confidence))  # 限制在0-1范围
            
            # 解析关键因素
            factors_match = re.search(r'关键因素[：:].*?(?=\*\*|$)', response, re.DOTALL)
            if factors_match:
                factors_text = factors_match.group(0)
                key_factors = [
                    line.strip('- ').strip() 
                    for line in factors_text.split('\n')[1:] 
                    if line.strip().startswith('-')
                ]
            
            # 解析风险提示
            risks_match = re.search(r'风险提示[：:].*?(?=\*\*|$)', response, re.DOTALL)
            if risks_match:
                risks_text = risks_match.group(0)
                risk_warnings = [
                    line.strip('- ').strip() 
                    for line in risks_text.split('\n')[1:] 
                    if line.strip().startswith('-')
                ]
            
        except Exception as e:
            logger.warning(f"⚠️ [解析警告] {self.name} 结果解析部分失败: {e}")
        
        return AnalysisResult(
            role_name=self.name,
            analysis_type=analysis_type,
            symbol=symbol,
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            key_factors=key_factors,
            risk_warnings=risk_warnings,
            timestamp=datetime.now()
        )
    
    async def analyze_stock_async(
        self,
        symbol: str,
        analysis_type: AnalysisType,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        additional_context: Optional[str] = None
    ) -> AnalysisResult:
        """
        异步股票分析方法
        
        Args:
            symbol: 股票代码
            analysis_type: 分析类型
            start_date: 开始日期
            end_date: 结束日期
            additional_context: 额外上下文
            
        Returns:
            AnalysisResult: 分析结果
        """
        try:
            logger.info(f"🔍 [{self.name}] 开始分析 {symbol} ({analysis_type.value})")
            
            # 获取市场数据
            market_data = None
            if analysis_type in [AnalysisType.MARKET_ANALYSIS, AnalysisType.TECHNICAL_ANALYSIS]:
                try:
                    # 设置默认日期
                    if not end_date:
                        end_date = datetime.now().strftime('%Y-%m-%d')
                    if not start_date:
                        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
                    
                    # 调用统一市场数据工具
                    market_data = self.toolkit.get_stock_market_data_unified.invoke({
                        'ticker': symbol,
                        'start_date': start_date,
                        'end_date': end_date
                    })
                    logger.info(f"📊 [{self.name}] 市场数据获取成功，长度: {len(market_data)}")
                except Exception as e:
                    logger.warning(f"⚠️ [{self.name}] 市场数据获取失败: {e}")
                    market_data = f"市场数据获取失败: {e}"
            
            # 创建分析提示
            prompt = self.create_analysis_prompt(
                symbol=symbol,
                analysis_type=analysis_type,
                market_data=market_data,
                additional_context=additional_context
            )
            
            # 调用LLM进行分析
            messages = [HumanMessage(content=prompt)]
            response = await self.llm.ainvoke(messages)
            
            # 解析结果
            analysis_result = self.parse_analysis_result(
                response.content, 
                symbol, 
                analysis_type
            )
            
            # 保存分析历史
            self.analysis_history.append(analysis_result)
            
            logger.info(f"✅ [{self.name}] 分析完成: {analysis_result.decision.value} (置信度: {analysis_result.confidence:.2%})")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"❌ [{self.name}] 分析失败: {e}")
            traceback.print_exc()
            
            # 返回错误分析结果
            return AnalysisResult(
                role_name=self.name,
                analysis_type=analysis_type,
                symbol=symbol,
                decision=DecisionLevel.NEUTRAL,
                confidence=0.0,
                reasoning=f"分析过程中出现错误: {str(e)}",
                key_factors=[],
                risk_warnings=[f"分析失败: {str(e)}"],
                timestamp=datetime.now()
            )
    
    def analyze_stock(
        self,
        symbol: str,
        analysis_type: AnalysisType,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        additional_context: Optional[str] = None
    ) -> AnalysisResult:
        """
        同步股票分析方法
        
        Args:
            symbol: 股票代码
            analysis_type: 分析类型
            start_date: 开始日期
            end_date: 结束日期 
            additional_context: 额外上下文
            
        Returns:
            AnalysisResult: 分析结果
        """
        # 使用asyncio运行异步方法
        try:
            # 获取或创建事件循环
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果已经在运行中的循环，创建新任务
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.analyze_stock_async(symbol, analysis_type, start_date, end_date, additional_context)
                    )
                    return future.result()
            else:
                # 直接运行
                return loop.run_until_complete(
                    self.analyze_stock_async(symbol, analysis_type, start_date, end_date, additional_context)
                )
        except Exception as e:
            logger.error(f"❌ [{self.name}] 同步分析调用失败: {e}")
            # 直接尝试异步调用的同步版本
            return asyncio.run(
                self.analyze_stock_async(symbol, analysis_type, start_date, end_date, additional_context)
            )
    
    @abstractmethod
    def get_specialized_analysis(self, symbol: str, **kwargs) -> AnalysisResult:
        """
        获取角色专业化分析
        
        这个方法需要在子类中实现，提供角色特定的分析逻辑
        
        Args:
            symbol: 股票代码
            **kwargs: 其他参数
            
        Returns:
            AnalysisResult: 专业化分析结果
        """
        pass
    
    def get_analysis_summary(self, limit: int = 10) -> Dict[str, Any]:
        """
        获取分析历史摘要
        
        Args:
            limit: 返回记录数量限制
            
        Returns:
            Dict[str, Any]: 分析摘要
        """
        recent_analyses = self.analysis_history[-limit:] if self.analysis_history else []
        
        if not recent_analyses:
            return {
                'role_name': self.name,
                'total_analyses': 0,
                'recent_analyses': [],
                'avg_confidence': 0.0,
                'decision_distribution': {}
            }
        
        # 计算统计信息
        total_confidence = sum(a.confidence for a in recent_analyses)
        avg_confidence = total_confidence / len(recent_analyses)
        
        # 决策分布
        decision_dist = {}
        for analysis in recent_analyses:
            decision_name = analysis.decision.value
            decision_dist[decision_name] = decision_dist.get(decision_name, 0) + 1
        
        return {
            'role_name': self.name,
            'total_analyses': len(self.analysis_history),
            'recent_analyses': [a.to_dict() for a in recent_analyses],
            'avg_confidence': avg_confidence,
            'decision_distribution': decision_dist
        }


class ImperialAgentFactory:
    """帝国角色工厂类"""
    
    @staticmethod
    def create_agent(
        role_name: str,
        llm: Any,
        toolkit: Optional[Toolkit] = None,
        config_override: Optional[Dict[str, Any]] = None
    ) -> ImperialAgentWrapper:
        """
        创建帝国角色实例
        
        Args:
            role_name: 角色名称
            llm: 语言模型实例
            toolkit: 工具集
            config_override: 配置覆盖
            
        Returns:
            ImperialAgentWrapper: 角色实例
        """
        # 根据role_name返回对应的具体角色实现
        if role_name == "威科夫AI":
            from imperial_agents.roles.wyckoff_ai import WyckoffAI
            return WyckoffAI(llm, toolkit)
        elif role_name == "马仁辉AI":
            from imperial_agents.roles.marenhui_ai import MarenhuiAI
            return MarenhuiAI(llm, toolkit)
        elif role_name == "鳄鱼导师AI":
            from imperial_agents.roles.crocodile_mentor_ai import CrocodileMentorAI
            return CrocodileMentorAI(llm, toolkit)
        else:
            # 未知角色，返回基础实现
            from imperial_agents.roles.base_role import BaseImperialRole
            
            # 加载角色配置
            role_config = ImperialAgentFactory.load_role_config(role_name, config_override)
            
            return BaseImperialRole(role_config, llm, toolkit)
    
    @staticmethod
    def load_role_config(
        role_name: str, 
        config_override: Optional[Dict[str, Any]] = None
    ) -> RoleConfig:
        """
        加载角色配置
        
        Args:
            role_name: 角色名称
            config_override: 配置覆盖
            
        Returns:
            RoleConfig: 角色配置
        """
        # 默认配置（后续会从配置文件加载）
        default_configs = {
            "威科夫AI": {
                "name": "威科夫AI",
                "title": "威科夫分析专家",
                "expertise": ["威科夫分析", "技术分析", "市场心理学"],
                "personality_traits": {
                    "分析风格": "深入细致，关注市场结构",
                    "决策特点": "基于价格和成交量关系判断",
                    "沟通方式": "专业术语丰富，逻辑清晰"
                },
                "decision_style": "技术面驱动，重视市场结构",
                "risk_tolerance": "中等风险",
                "preferred_timeframe": "中短期",
                "analysis_focus": [AnalysisType.TECHNICAL_ANALYSIS, AnalysisType.MARKET_ANALYSIS],
                "system_prompt_template": """你是威科夫分析专家，擅长通过价格和成交量的关系分析市场。
请基于威科夫分析方法对{symbol}进行{analysis_type}，重点关注：
1. 价格和成交量的背离关系
2. 市场阶段判断（累积、标记、派发、下跌）
3. 关键支撑和阻力位
4. 市场参与者行为分析
请用专业的威科夫理论术语进行分析。""",
                "constraints": ["必须基于威科夫理论", "重视成交量分析", "关注市场结构"]
            }
        }
        
        # 获取基础配置
        config_data = default_configs.get(role_name, default_configs["威科夫AI"])
        
        # 应用覆盖配置
        if config_override:
            config_data.update(config_override)
        
        return RoleConfig.from_dict(config_data)


# 导出主要类和函数
__all__ = [
    'ImperialAgentWrapper',
    'AnalysisResult', 
    'RoleConfig',
    'AnalysisType',
    'DecisionLevel',
    'ImperialAgentFactory'
]
