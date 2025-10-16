
# -*- coding: utf-8 -*-

import requests
import json
from pathlib import Path
import tushare as ts
import os
from tradingagents.config.env_utils import parse_str_env

RED = '\033[91m'
GREEN = "\033[32m"
YELLOW = "\033[33m"
END = '\033[0m'


class TokenManager:
    """tushare Token管理器"""
    
    def __init__(self, cache_dir_name=".tushare"):
        """
        初始化Token管理器
        
        Args:
            cache_dir_name: 缓存目录名称，默认为.tushare
        """
        self.cache_dir_name = cache_dir_name
        self.default_token = ""
        # API地址和提取码
        # 注意：请确保你的提取码是正确的
        self.api_url = "https://extract.swiftiny.com/api/extract/getLatestKey"
        self.api_code = parse_str_env("EXTRACT_API_CODE")
    
    def get_cache_file_path(self):
        """获取缓存文件路径"""
        cache_dir = Path.home() / self.cache_dir_name
        cache_dir.mkdir(exist_ok=True)
        return cache_dir / "token_cache.json"
    
    def load_token_from_cache(self):
        """从本地缓存读取token"""
        cache_file = self.get_cache_file_path()
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    return cache_data.get('token')
            except (json.JSONDecodeError, IOError) as e:
                print(f"读取缓存文件失败: {e}")
        return None
    
    def save_token_to_cache(self, token, key_name=None, call_count=None, max_count=None):
        """将token保存到本地缓存"""
        cache_file = self.get_cache_file_path()
        cache_data = {
            'token': token,
            'key_name': key_name,
            'call_count': call_count,
            'max_count': max_count
        }
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            print(f"✓ Token已缓存到本地: {cache_file}")
        except IOError as e:
            print(f"保存缓存文件失败: {e}")
    
    def get_latest_token(self):
        """调用API获取最新token"""
        headers = {"Content-Type": "application/json"}
        data = {"code": self.api_code}
        
        try:
            print("正在获取最新token...")

            if self.api_code == "你的提取码":
                print(f" {RED}请在token_manager.py中配置你的提取码{END}")
                return None

            response = requests.post(self.api_url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('success') and result.get('status') == 200:
                token = result.get('apiKey')
                key_name = result.get('keyName')
                call_count = result.get('callCount')
                max_count = result.get('maxCount')
                announcement = result.get('announcement')

                # 获取通知内容
                content = None
                if announcement:
                    content = announcement.get('content')

                print(f" {GREEN}✓ 获取新token成功: {key_name}{END}")
                print(f" {GREEN}✓ 新token为: {token}{END}")

                print(f" {YELLOW}调用次数: {call_count}/{max_count}{END}")
                if content and content != "暂无": 
                    print()
                    print(f" {RED}===通知: {content}=== {END}")
                    print()
                
                # 保存到缓存
                self.save_token_to_cache(token, key_name, call_count, max_count)
                return token
            else:
                print(f" {RED}✗ 获取token失败: {result}{END}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"✗ 请求失败: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"✗ 解析响应失败: {e}")
            return None
    
    def validate_token(self, token):
        """
        验证token有效性，通过调用index_daily接口
        
        Args:
            token: 要验证的token
            
        Returns:
            bool: token是否有效
        """
        try:
            # 调用index_daily接口进行测试
            df = ts.pro_api(token).index_daily(
                ts_code="000001.SH", 
                start_date="20250101", 
                end_date="20250102"
            )
            
            # 如果能成功调用且返回数据，说明token有效
            print(f" {GREEN}✓ Token验证成功{END}")
            return True
            
        except Exception as e:
            error_msg = str(e)
            print(f" {RED}✗ Token验证失败: {error_msg}{END}")
            
            # 检查是否是token相关错误
            if self.is_token_invalid_error(error_msg):
                return False
            else:
                # 其他错误也认为token可能有问题
                return False
    
    def get_token(self, use_cache=True, fallback_to_default=True):
        """
        获取token，优先级：缓存 -> 默认值
        
        Args:
            use_cache: 是否使用缓存，默认True
            fallback_to_default: 如果缓存没有token，是否使用默认token，默认True
            
        Returns:
            str: token字符串，如果都获取失败则返回None
        """
        if use_cache:
            token = self.load_token_from_cache()
            if token:
                print("✓ 从缓存读取到Token")
                return token
        
        if fallback_to_default:
            print("✓ 使用默认Token")
            return self.default_token
        
        return None
    
    def get_valid_token(self, use_cache=True, fallback_to_default=False):
        """
        获取有效的token，会进行token有效性验证
        
        Args:   
            use_cache: 是否使用缓存，默认True
            fallback_to_default: 如果缓存没有token，是否使用默认token，默认True
            
        Returns:
            str: 有效的token字符串，如果都获取失败则返回None
        """
        # 先尝试从缓存获取token
        if use_cache:
            cached_token = self.load_token_from_cache()
            if cached_token:
                print("✓ 从缓存读取到Token，正在验证...")
                if self.validate_token(cached_token):
                    return cached_token
                else:
                    print("缓存的token无效，尝试获取新token...")
        
        # 缓存token无效或不存在，尝试获取新token
        new_token = self.get_latest_token()
        if new_token:
            print("正在验证新token...")
            if self.validate_token(new_token):
                return new_token
            else:
                print("新token验证失败")
        
        # 如果新token也无效，尝试使用默认token
        if fallback_to_default:
            print("尝试使用默认Token...")
            if self.validate_token(self.default_token):
                return self.default_token
            else:
                print("默认token也无效")
        
        return None

    def refresh_token(self):
        """刷新token，获取最新的token并保存到缓存"""
        return self.get_latest_token()
    
    @staticmethod
    def is_token_invalid_error(error_msg):
        """判断是否是token无效的错误"""
        error_indicators = [
            "您的token不对",
            "token不对", 
            "请确认",
            "token无效",
            "token过期"
        ]
        return any(indicator in str(error_msg) for indicator in error_indicators)


# 创建全局实例，方便直接导入使用
token_manager = TokenManager()

# 提供便捷的函数接口
def get_token(use_cache=True, fallback_to_default=True):
    """获取token的便捷函数"""
    return token_manager.get_token(use_cache, fallback_to_default)

def get_valid_token(use_cache=True, fallback_to_default=True):
    """获取有效token的便捷函数"""
    return token_manager.get_valid_token(use_cache, fallback_to_default)

def refresh_token():
    """刷新token的便捷函数"""
    return token_manager.refresh_token()

def is_token_invalid_error(error_msg):
    """判断token错误的便捷函数"""
    return TokenManager.is_token_invalid_error(error_msg) 