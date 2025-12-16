"""
持仓分析智能体适配器

包含以下智能体:
- pa_technical: 技术面分析师 (v1 & v2)
- pa_fundamental: 基本面分析师 (v1 & v2)
- pa_risk: 风险评估师 (v1 & v2)
- pa_advisor: 操作建议师 (v1 & v2)
"""

# v1.0 Agents (基于BaseAgent)
from .technical_analyst import TechnicalAnalystAgent
from .fundamental_analyst import FundamentalAnalystAgent
from .risk_assessor import RiskAssessorAgent
from .action_advisor import ActionAdvisorAgent

# v2.0 Agents (基于ResearcherAgent/ManagerAgent)
from .technical_analyst_v2 import TechnicalAnalystV2
from .fundamental_analyst_v2 import FundamentalAnalystV2
from .risk_assessor_v2 import RiskAssessorV2
from .action_advisor_v2 import ActionAdvisorV2

__all__ = [
    # v1.0
    "TechnicalAnalystAgent",
    "FundamentalAnalystAgent",
    "RiskAssessorAgent",
    "ActionAdvisorAgent",
    # v2.0
    "TechnicalAnalystV2",
    "FundamentalAnalystV2",
    "RiskAssessorV2",
    "ActionAdvisorV2",
]

