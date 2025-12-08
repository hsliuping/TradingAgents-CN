"""
功能门控

控制功能访问权限
"""

from functools import wraps
from typing import Callable, Optional, Union

from .manager import LicenseManager
from .models import LicenseTier


class FeatureGate:
    """
    功能门控
    
    用法:
        gate = FeatureGate()
        
        # 检查功能
        if gate.is_allowed("sector_analyst"):
            # 使用功能
            pass
        
        # 装饰器方式
        @gate.require("sector_analyst")
        def my_function():
            pass
    """
    
    def __init__(self, manager: Optional[LicenseManager] = None):
        self._manager = manager or LicenseManager()
    
    def is_allowed(self, feature: str) -> bool:
        """检查功能是否允许"""
        return self._manager.can_use_feature(feature)
    
    def check_tier(self, required_tier: Union[str, LicenseTier]) -> bool:
        """检查是否达到所需级别"""
        if isinstance(required_tier, str):
            required_tier = LicenseTier(required_tier)
        
        tier_order = [
            LicenseTier.FREE,
            LicenseTier.BASIC,
            LicenseTier.PRO,
            LicenseTier.ENTERPRISE
        ]
        
        current_index = tier_order.index(self._manager.tier)
        required_index = tier_order.index(required_tier)
        
        return current_index >= required_index
    
    def require(
        self,
        feature: Optional[str] = None,
        tier: Optional[Union[str, LicenseTier]] = None,
        error_message: Optional[str] = None
    ) -> Callable:
        """
        装饰器: 要求特定功能或级别
        
        用法:
            @gate.require(feature="sector_analyst")
            def analyze_sector():
                pass
            
            @gate.require(tier="pro")
            def pro_feature():
                pass
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # 检查功能
                if feature and not self.is_allowed(feature):
                    msg = error_message or f"功能 '{feature}' 需要升级许可证"
                    raise PermissionError(msg)
                
                # 检查级别
                if tier and not self.check_tier(tier):
                    msg = error_message or f"此功能需要 {tier} 或更高级别许可证"
                    raise PermissionError(msg)
                
                return func(*args, **kwargs)
            
            return wrapper
        return decorator
    
    def require_tier(self, tier: Union[str, LicenseTier]) -> Callable:
        """装饰器: 要求特定级别"""
        return self.require(tier=tier)
    
    def require_feature(self, feature: str) -> Callable:
        """装饰器: 要求特定功能"""
        return self.require(feature=feature)


# 全局功能门控实例
_global_gate: Optional[FeatureGate] = None


def get_feature_gate() -> FeatureGate:
    """获取全局功能门控实例"""
    global _global_gate
    if _global_gate is None:
        _global_gate = FeatureGate()
    return _global_gate


def require_feature(feature: str) -> Callable:
    """
    便捷装饰器: 要求特定功能
    
    用法:
        from core.licensing import require_feature
        
        @require_feature("sector_analyst")
        def analyze_sector():
            pass
    """
    return get_feature_gate().require_feature(feature)


def require_tier(tier: Union[str, LicenseTier]) -> Callable:
    """
    便捷装饰器: 要求特定级别
    
    用法:
        from core.licensing import require_tier
        
        @require_tier("pro")
        def pro_feature():
            pass
    """
    return get_feature_gate().require_tier(tier)

