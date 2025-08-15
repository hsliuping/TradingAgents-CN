"""
帝国AI基础角色实现
Imperial Base Role Implementation

提供基础角色实现和通用分析逻辑
"""

from typing import Dict, Any, Optional
from datetime import datetime

from imperial_agents.core.imperial_agent_wrapper import (
    ImperialAgentWrapper, 
    AnalysisResult, 
    AnalysisType, 
    DecisionLevel,
    RoleConfig
)
from tradingagents.utils.logging_init import get_logger

logger = get_logger("imperial_roles")


class BaseImperialRole(ImperialAgentWrapper):
    """
    基础帝国角色实现
    
    提供通用的分析逻辑和默认行为，
    可以作为所有具体角色的基础类。
    """
    
    def __init__(self, role_config: RoleConfig, llm: Any, toolkit: Any = None):
        """
        初始化基础帝国角色
        
        Args:
            role_config: 角色配置
            llm: 语言模型实例
            toolkit: TradingAgents工具集
        """
        super().__init__(role_config, llm, toolkit)
        
        # 基础角色特定初始化
        self.analysis_count = 0
        self.success_rate = 0.0
        
        logger.info(f"🏛️ [基础角色] {self.name} 基础实现已加载")
    
    def get_specialized_analysis(self, symbol: str, **kwargs) -> AnalysisResult:
        """
        获取基础专业化分析
        
        Args:
            symbol: 股票代码
            **kwargs: 其他参数
            
        Returns:
            AnalysisResult: 基础分析结果
        """
        try:
            # 默认进行市场分析
            analysis_type = kwargs.get('analysis_type', AnalysisType.MARKET_ANALYSIS)
            
            # 获取基础市场数据分析
            result = self.analyze_stock(
                symbol=symbol,
                analysis_type=analysis_type,
                start_date=kwargs.get('start_date'),
                end_date=kwargs.get('end_date'),
                additional_context=kwargs.get('additional_context')
            )
            
            # 更新统计信息
            self.analysis_count += 1
            
            logger.info(f"🏛️ [基础角色] {self.name} 完成专业化分析")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ [基础角色] {self.name} 专业化分析失败: {e}")
            
            return AnalysisResult(
                role_name=self.name,
                analysis_type=AnalysisType.MARKET_ANALYSIS,
                symbol=symbol,
                decision=DecisionLevel.NEUTRAL,
                confidence=0.0,
                reasoning=f"基础分析过程中出现错误: {str(e)}",
                key_factors=[],
                risk_warnings=[f"分析失败: {str(e)}"],
                timestamp=datetime.now()
            )
    
    def get_role_status(self) -> Dict[str, Any]:
        """
        获取角色状态信息
        
        Returns:
            Dict[str, Any]: 角色状态
        """
        summary = self.get_analysis_summary()
        
        return {
            'role_name': self.name,
            'role_title': self.title,
            'analysis_count': self.analysis_count,
            'success_rate': self.success_rate,
            'recent_performance': summary,
            'capabilities': self.role_config.expertise,
            'status': 'active'
        }


# 导出基础角色类
__all__ = ['BaseImperialRole']
