"""
许可证在线验证器

此文件将使用 Cython 编译，防止用户绕过验证逻辑
"""

import hashlib
import hmac
import time
import requests
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timedelta

from .models import License, LicenseTier, TIER_FEATURES


class LicenseValidator:
    """
    许可证验证器
    
    安全特性:
    1. 在线验证（防止伪造）
    2. 签名验证（防止篡改）
    3. 时间戳验证（防止重放攻击）
    4. 硬件绑定（防止共享）
    
    此类将被 Cython 编译，用户无法查看或修改验证逻辑
    """
    
    # 🔐 验证服务器地址（编译后无法修改）
    # ⚠️ 安全警告：此地址不能从环境变量读取，否则用户可以搭建假服务器绕过验证
    VALIDATION_SERVER = "https://www.tradingagentscn.com/api/v1/license"

    # 🔐 密钥（编译后无法查看）
    # 注意：实际部署时应该使用环境变量或更安全的方式
    SECRET_KEY = b"your-secret-key-change-this-in-production"
    
    # 缓存时间（秒）
    CACHE_DURATION = 3600  # 1小时
    
    def __init__(self, offline_mode: bool = False):
        """
        初始化验证器
        
        Args:
            offline_mode: 离线模式（用于测试）
        """
        self._offline_mode = offline_mode
        self._cache: Dict[str, Tuple[bool, Optional[License], float]] = {}
    
    def _get_machine_id(self) -> str:
        """
        获取机器唯一标识
        
        用于硬件绑定，防止许可证在多台机器上使用
        """
        import platform
        import uuid
        
        # 组合多个硬件信息
        machine_info = f"{platform.node()}-{uuid.getnode()}"
        
        # 生成哈希
        return hashlib.sha256(machine_info.encode()).hexdigest()[:16]
    
    def _sign_request(self, data: Dict[str, Any]) -> str:
        """
        签名请求数据
        
        防止请求被篡改
        """
        # 按键排序
        sorted_data = sorted(data.items())
        message = "&".join(f"{k}={v}" for k, v in sorted_data)
        
        # HMAC签名
        signature = hmac.new(
            self.SECRET_KEY,
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _verify_signature(self, data: Dict[str, Any], signature: str) -> bool:
        """验证签名"""
        expected = self._sign_request(data)
        return hmac.compare_digest(expected, signature)
    
    def validate_online(
        self,
        license_key: str,
        timeout: int = 10
    ) -> Tuple[bool, Optional[License], Optional[str]]:
        """
        在线验证许可证
        
        Args:
            license_key: 许可证密钥
            timeout: 超时时间（秒）
            
        Returns:
            (是否有效, 许可证对象, 错误信息)
        """
        # 检查缓存
        cache_key = f"{license_key}:{self._get_machine_id()}"
        if cache_key in self._cache:
            is_valid, license_obj, cached_at = self._cache[cache_key]
            if time.time() - cached_at < self.CACHE_DURATION:
                return is_valid, license_obj, None
        
        # 准备请求数据
        request_data = {
            "license_key": license_key,
            "machine_id": self._get_machine_id(),
            "timestamp": int(time.time()),
        }
        
        # 签名
        signature = self._sign_request(request_data)
        request_data["signature"] = signature
        
        try:
            # 发送验证请求
            response = requests.post(
                f"{self.VALIDATION_SERVER}/validate",
                json=request_data,
                timeout=timeout,
                headers={"User-Agent": "TradingAgentsCN/2.0"}
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # 验证响应签名
                response_signature = result.pop("signature", None)
                if not response_signature or not self._verify_signature(result, response_signature):
                    return False, None, "响应签名验证失败"
                
                # 解析许可证
                if result.get("valid"):
                    license_data = result.get("license")
                    license_obj = License.model_validate(license_data)
                    
                    # 缓存结果
                    self._cache[cache_key] = (True, license_obj, time.time())
                    
                    return True, license_obj, None
                else:
                    error_msg = result.get("error", "许可证无效")
                    return False, None, error_msg
            else:
                return False, None, f"验证服务器返回错误: {response.status_code}"
                
        except requests.Timeout:
            return False, None, "验证服务器超时"
        except requests.RequestException as e:
            return False, None, f"网络错误: {str(e)}"
        except Exception as e:
            return False, None, f"验证失败: {str(e)}"

    def validate_offline(self, license_key: str) -> Tuple[bool, Optional[License], Optional[str]]:
        """
        离线验证（用于测试或网络不可用时）

        仅验证格式和基本签名，不保证许可证真实性
        """
        try:
            # 解析许可证密钥
            # 格式: TIER-SIGNATURE-TIMESTAMP-CHECKSUM
            parts = license_key.split('-')
            if len(parts) < 4:
                return False, None, "许可证格式错误"

            tier_str, signature, timestamp_str, checksum = parts[:4]

            # 验证级别
            try:
                tier = LicenseTier(tier_str.lower())
            except ValueError:
                return False, None, "无效的许可证级别"

            # 验证时间戳（防止过期）
            try:
                timestamp = int(timestamp_str, 16)  # 16进制时间戳
                issue_time = datetime.fromtimestamp(timestamp)

                # 检查是否在合理时间范围内（不能是未来时间）
                if issue_time > datetime.now():
                    return False, None, "许可证时间戳无效"

            except (ValueError, OSError):
                return False, None, "许可证时间戳格式错误"

            # 验证校验和
            expected_checksum = self._calculate_checksum(tier_str, timestamp_str)
            if checksum != expected_checksum:
                return False, None, "许可证校验失败"

            # 创建许可证对象
            license_obj = License.create_for_tier(tier)

            return True, license_obj, None

        except Exception as e:
            return False, None, f"离线验证失败: {str(e)}"

    def _calculate_checksum(self, tier: str, timestamp: str) -> str:
        """
        计算校验和

        用于离线验证的基本防伪
        """
        data = f"{tier}-{timestamp}-{self._get_machine_id()}"
        return hashlib.sha256(
            hmac.new(self.SECRET_KEY, data.encode(), hashlib.sha256).digest()
        ).hexdigest()[:8]

    def validate(
        self,
        license_key: str,
        prefer_online: bool = True
    ) -> Tuple[bool, Optional[License], Optional[str]]:
        """
        验证许可证（自动选择在线或离线）

        Args:
            license_key: 许可证密钥
            prefer_online: 优先使用在线验证

        Returns:
            (是否有效, 许可证对象, 错误信息)
        """
        if self._offline_mode or not prefer_online:
            return self.validate_offline(license_key)

        # 尝试在线验证
        is_valid, license_obj, error = self.validate_online(license_key)

        # 如果在线验证失败（网络问题），回退到离线验证
        if not is_valid and error and ("网络" in error or "超时" in error):
            return self.validate_offline(license_key)

        return is_valid, license_obj, error

    def generate_trial_license(self, days: int = 30) -> str:
        """
        生成试用许可证

        Args:
            days: 试用天数

        Returns:
            许可证密钥
        """
        tier = "pro"
        timestamp = hex(int(time.time()))[2:]
        checksum = self._calculate_checksum(tier, timestamp)

        # 格式: TIER-TRIAL-TIMESTAMP-CHECKSUM
        return f"{tier}-trial-{timestamp}-{checksum}"

