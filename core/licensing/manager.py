"""
许可证管理器
"""

import os
import json
import threading
from typing import Optional
from pathlib import Path

from .models import License, LicenseTier, TIER_FEATURES


class LicenseManager:
    """
    许可证管理器 (单例模式)
    
    用法:
        manager = LicenseManager()
        
        # 检查许可证
        if manager.is_valid:
            # 执行操作
            pass
        
        # 检查功能
        if manager.can_use_feature("sector_analyst"):
            # 使用功能
            pass
    """
    
    _instance = None
    _lock = threading.Lock()
    
    # 许可证存储路径
    LICENSE_FILE = "config/license.json"
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(LicenseManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._license: Optional[License] = None
            self._load_license()
            self._initialized = True
    
    def _load_license(self) -> None:
        """加载许可证"""
        license_path = Path(self.LICENSE_FILE)
        
        if license_path.exists():
            try:
                with open(license_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._license = License.model_validate(data)
            except Exception as e:
                print(f"加载许可证失败: {e}")
                self._license = License.create_free()
        else:
            # 使用免费许可证
            self._license = License.create_free()
    
    def _save_license(self) -> None:
        """保存许可证"""
        if self._license is None:
            return
        
        license_path = Path(self.LICENSE_FILE)
        license_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(license_path, 'w', encoding='utf-8') as f:
            json.dump(self._license.model_dump(), f, indent=2, default=str)
    
    def activate(self, license_key: str) -> bool:
        """
        激活许可证
        
        Args:
            license_key: 许可证密钥
            
        Returns:
            是否激活成功
        """
        # TODO: 实现许可证验证逻辑
        # 这里是简化实现，实际应该调用验证服务
        
        # 解析许可证密钥
        # 格式: TIER-XXXX-XXXX-XXXX
        parts = license_key.split('-')
        if len(parts) < 4:
            return False
        
        tier_str = parts[0].lower()
        try:
            tier = LicenseTier(tier_str)
        except ValueError:
            return False
        
        # 创建许可证
        self._license = License.create_for_tier(tier)
        self._save_license()
        
        return True
    
    def deactivate(self) -> None:
        """停用许可证，恢复免费版"""
        self._license = License.create_free()
        self._save_license()
    
    @property
    def license(self) -> License:
        """当前许可证"""
        if self._license is None:
            self._license = License.create_free()
        return self._license
    
    @property
    def tier(self) -> LicenseTier:
        """当前级别"""
        return self.license.tier
    
    @property
    def is_valid(self) -> bool:
        """许可证是否有效"""
        return self.license.is_valid
    
    @property
    def features(self):
        """当前功能配置"""
        return self.license.features
    
    def can_use_feature(self, feature_name: str) -> bool:
        """检查是否可以使用某功能"""
        features = self.features
        
        # 检查布尔型功能
        if hasattr(features, f"allow_{feature_name}"):
            return getattr(features, f"allow_{feature_name}")
        
        return True
    
    def check_limit(self, limit_name: str, current_value: int) -> bool:
        """
        检查是否超过限制
        
        Args:
            limit_name: 限制名称 (如 max_workflows)
            current_value: 当前值
            
        Returns:
            是否在限制内
        """
        features = self.features
        
        if hasattr(features, limit_name):
            max_value = getattr(features, limit_name)
            return current_value < max_value
        
        return True
    
    def get_remaining(self, limit_name: str, current_value: int) -> int:
        """获取剩余配额"""
        features = self.features
        
        if hasattr(features, limit_name):
            max_value = getattr(features, limit_name)
            return max(0, max_value - current_value)
        
        return 999999

