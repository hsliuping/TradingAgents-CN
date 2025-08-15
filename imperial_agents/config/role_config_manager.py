"""
帝国AI角色配置管理
Imperial Role Configuration Manager

管理所有帝国角色的配置信息，包括个性特征、决策风格、分析重点等
"""

import json
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import asdict

from imperial_agents.core.imperial_agent_wrapper import RoleConfig, AnalysisType
from tradingagents.utils.logging_init import get_logger

logger = get_logger("imperial_config")


class RoleConfigManager:
    """角色配置管理器"""
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_dir: 配置文件目录路径
        """
        self.config_dir = Path(config_dir) if config_dir else Path(__file__).parent / "configs"
        self.config_dir.mkdir(exist_ok=True)
        
        # 缓存加载的配置
        self._config_cache: Dict[str, RoleConfig] = {}
        
        logger.info(f"📋 [配置管理] 初始化完成，配置目录: {self.config_dir}")
    
    def get_default_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        获取默认的角色配置
        
        Returns:
            Dict[str, Dict[str, Any]]: 默认配置字典
        """
        return {
            "威科夫AI": {
                "name": "威科夫AI",
                "title": "威科夫分析大师 v3.0",
                "expertise": ["威科夫分析", "技术分析", "市场心理学", "价量关系分析"],
                "personality_traits": {
                    "分析风格": "深入细致，关注市场内在结构",
                    "决策特点": "基于价格和成交量关系的严谨判断",
                    "沟通方式": "专业术语丰富，逻辑清晰严密",
                    "核心理念": "跟随聪明资金的足迹"
                },
                "decision_style": "技术面主导，重视市场结构和资金流向",
                "risk_tolerance": "中等风险，追求高胜率机会",
                "preferred_timeframe": "中短期为主，1周到3个月",
                "analysis_focus": ["technical_analysis", "market_analysis"],
                "system_prompt_template": """你是威科夫分析大师v3.0，世界顶级的威科夫理论专家。

**核心身份**: 威科夫分析法的权威专家，专精于通过价格和成交量关系分析市场内在结构。

**分析方法**: 
1. 威科夫四阶段分析（累积、上升、派发、下跌）
2. 价量背离识别和供需关系分析
3. 复合人（Composite Man）行为推测
4. 支撑阻力位的精确定位

**当前任务**: 对股票 {symbol}（{market_name}市场）进行{analysis_type}分析

**分析要求**:
- 必须基于威科夫三大定律进行分析
- 重点识别当前处于威科夫循环的哪个阶段
- 分析价量关系，寻找背离信号
- 判断聪明资金的操作意图
- 提供具体的进出场时机建议

请用威科夫理论的专业术语，以严谨的逻辑进行分析。""",
                "constraints": [
                    "必须严格基于威科夫三大定律",
                    "重视成交量分析，价量必须结合",
                    "关注市场结构变化",
                    "识别聪明资金行为"
                ]
            },
            
            "马仁辉AI": {
                "name": "马仁辉AI",
                "title": "222法则验证专家 v3.0",
                "expertise": ["222法则", "短线交易", "风险控制", "实战验证"],
                "personality_traits": {
                    "分析风格": "实战导向，注重可操作性",
                    "决策特点": "严格执行222法则，纪律性极强",
                    "沟通方式": "直接明了，重点突出",
                    "核心理念": "宁可错过，不可做错"
                },
                "decision_style": "规则化交易，严格按照222法则执行",
                "risk_tolerance": "低风险，严格止损",
                "preferred_timeframe": "短期为主，1-7天",
                "analysis_focus": ["risk_analysis", "technical_analysis"],
                "system_prompt_template": """你是马仁辉AI v3.0，222法则的实战验证专家。

**核心身份**: 严格按照222法则进行交易决策的实战专家，以纪律性和风险控制著称。

**222法则核心**:
1. 价格法则：股价在2-22元区间
2. 时间法则：持股不超过2-22个交易日
3. 收益法则：目标收益2%-22%

**当前任务**: 对股票 {symbol}（{market_name}市场）进行{analysis_type}验证

**验证要求**:
- 严格按照222法则三要素进行验证
- 评估当前价格是否符合操作区间
- 分析短期技术指标和风险因素
- 给出具体的进出场策略
- 明确止损和止盈位置

请以实战交易者的视角，用简洁明了的语言给出操作建议。""",
                "constraints": [
                    "严格执行222法则",
                    "重视风险控制",
                    "操作必须具备可执行性",
                    "止损策略必须明确"
                ]
            },
            
            "鳄鱼导师AI": {
                "name": "鳄鱼导师AI", 
                "title": "鳄鱼法则风控专家 v3.0",
                "expertise": ["风险管理", "鳄鱼法则", "心理控制", "资金管理"],
                "personality_traits": {
                    "分析风格": "保守谨慎，风险优先",
                    "决策特点": "绝不容忍大额亏损，严格执行止损",
                    "沟通方式": "严肃认真，警示性强",
                    "核心理念": "保本第一，收益第二"
                },
                "decision_style": "风险优先，宁可少赚不能大亏",
                "risk_tolerance": "极低风险，零容忍大亏",
                "preferred_timeframe": "所有时间框架的风险监控",
                "analysis_focus": ["risk_analysis"],
                "system_prompt_template": """你是鳄鱼导师AI v3.0，鳄鱼法则的严格执行者和风险管理专家。

**核心身份**: 专注于风险控制的导师，坚决执行鳄鱼法则，保护投资者免受重大损失。

**鳄鱼法则精髓**:
- 当你知道自己犯错时，立即了结出场
- 切勿试图调整头寸、摊平成本
- 承认错误比寻找借口更重要
- 小损失可以接受，大损失绝不容忍

**当前任务**: 对股票 {symbol}（{market_name}市场）进行{analysis_type}风险评估

**风险评估要求**:
- 识别所有潜在风险因素
- 评估最大可能损失
- 制定严格的止损策略
- 警示高风险操作
- 提供资金管理建议

请以严格的风险控制视角，重点警示风险，保护资金安全。""",
                "constraints": [
                    "风险控制是第一要务",
                    "必须设置明确止损",
                    "严禁建议高风险操作",
                    "重视资金管理"
                ]
            }
        }
    
    def load_role_config(self, role_name: str) -> RoleConfig:
        """
        加载角色配置
        
        Args:
            role_name: 角色名称
            
        Returns:
            RoleConfig: 角色配置对象
        """
        # 先检查缓存
        if role_name in self._config_cache:
            return self._config_cache[role_name]
        
        # 尝试从文件加载
        config_file = self.config_dir / f"{role_name}.yaml"
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
                logger.info(f"📋 [配置管理] 从文件加载配置: {role_name}")
            except Exception as e:
                logger.warning(f"⚠️ [配置管理] 文件加载失败: {e}")
                config_data = None
        else:
            config_data = None
        
        # 如果文件加载失败，使用默认配置
        if not config_data:
            default_configs = self.get_default_configs()
            config_data = default_configs.get(role_name)
            
            if not config_data:
                logger.error(f"❌ [配置管理] 未找到角色配置: {role_name}")
                raise ValueError(f"未找到角色配置: {role_name}")
            
            logger.info(f"📋 [配置管理] 使用默认配置: {role_name}")
        
        # 处理analysis_focus的字符串转枚举
        if 'analysis_focus' in config_data:
            analysis_focus = []
            for focus in config_data['analysis_focus']:
                if isinstance(focus, str):
                    try:
                        analysis_focus.append(AnalysisType(focus))
                    except ValueError:
                        logger.warning(f"⚠️ [配置管理] 无效的分析类型: {focus}")
                else:
                    analysis_focus.append(focus)
            config_data['analysis_focus'] = analysis_focus
        
        # 创建配置对象
        role_config = RoleConfig.from_dict(config_data)
        
        # 缓存配置
        self._config_cache[role_name] = role_config
        
        logger.info(f"✅ [配置管理] 角色配置加载完成: {role_name}")
        return role_config
    
    def save_role_config(self, role_config: RoleConfig) -> bool:
        """
        保存角色配置到文件
        
        Args:
            role_config: 角色配置对象
            
        Returns:
            bool: 保存是否成功
        """
        try:
            config_file = self.config_dir / f"{role_config.name}.yaml"
            
            # 转换为字典
            config_data = asdict(role_config)
            
            # 处理枚举类型
            if 'analysis_focus' in config_data:
                config_data['analysis_focus'] = [
                    focus.value if hasattr(focus, 'value') else focus 
                    for focus in config_data['analysis_focus']
                ]
            
            # 保存到文件
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, ensure_ascii=False, indent=2)
            
            # 更新缓存
            self._config_cache[role_config.name] = role_config
            
            logger.info(f"💾 [配置管理] 配置保存成功: {role_config.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ [配置管理] 配置保存失败: {e}")
            return False
    
    def list_available_roles(self) -> List[str]:
        """
        列出所有可用的角色
        
        Returns:
            List[str]: 角色名称列表
        """
        roles = []
        
        # 从默认配置获取
        default_configs = self.get_default_configs()
        roles.extend(default_configs.keys())
        
        # 从配置文件目录获取
        if self.config_dir.exists():
            for config_file in self.config_dir.glob("*.yaml"):
                role_name = config_file.stem
                if role_name not in roles:
                    roles.append(role_name)
        
        return sorted(roles)
    
    def create_default_configs(self) -> bool:
        """
        创建默认配置文件
        
        Returns:
            bool: 创建是否成功
        """
        try:
            default_configs = self.get_default_configs()
            
            for role_name, config_data in default_configs.items():
                # 处理枚举类型转换
                if 'analysis_focus' in config_data:
                    config_data['analysis_focus'] = [
                        focus.value if hasattr(focus, 'value') else focus 
                        for focus in config_data['analysis_focus']
                    ]
                
                config_file = self.config_dir / f"{role_name}.yaml"
                
                # 如果文件不存在才创建
                if not config_file.exists():
                    with open(config_file, 'w', encoding='utf-8') as f:
                        yaml.dump(config_data, f, ensure_ascii=False, indent=2)
                    
                    logger.info(f"📝 [配置管理] 创建默认配置: {role_name}")
            
            logger.info(f"✅ [配置管理] 默认配置创建完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ [配置管理] 默认配置创建失败: {e}")
            return False


# 全局配置管理器实例
_global_config_manager = None

def get_config_manager() -> RoleConfigManager:
    """
    获取全局配置管理器实例
    
    Returns:
        RoleConfigManager: 配置管理器实例
    """
    global _global_config_manager
    if _global_config_manager is None:
        _global_config_manager = RoleConfigManager()
    return _global_config_manager


# 导出主要类和函数
__all__ = ['RoleConfigManager', 'get_config_manager']
