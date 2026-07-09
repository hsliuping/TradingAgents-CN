"""
社媒消息API接入示例程序

本示例展示了如何通过API上传和查询社媒消息数据
支持批量上传、查询、搜索等功能
"""

import requests
import json
from datetime import datetime
from typing import List, Dict, Any

# API基础URL（根据实际部署地址修改）
BASE_URL = "http://localhost:8000/api/social-media"


class SocialMediaAPIClient:
    """社媒消息API客户端"""
    
    def __init__(self, base_url: str = BASE_URL, token: str = None):
        """
        初始化API客户端
        
        Args:
            base_url: API基础URL
            token: 认证token（如果需要）
        """
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.session = requests.Session()
        
        if token:
            self.session.headers.update({
                'Authorization': f'Bearer {token}'
            })
    
    def upload_file(
        self,
        file_path: str,
        symbol: str,
        platform: str = None,
        encoding: str = "utf-8",
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """
        上传社媒消息文件
        
        Args:
            file_path: 文件路径（支持JSON、CSV、Excel）
            symbol: 股票代码
            platform: 默认平台类型（可选）
            encoding: 文件编码（CSV/JSON使用）
            overwrite: 是否覆盖已存在的消息
            
        Returns:
            上传结果
        """
        url = f"{self.base_url}/upload"
        
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.split('/')[-1], f)}
            data = {
                'symbol': symbol,
                'encoding': encoding,
                'overwrite': str(overwrite).lower()
            }
            
            if platform:
                data['platform'] = platform
            
            response = self.session.post(url, files=files, data=data)
            response.raise_for_status()
            return response.json()
    
    def save_messages(
        self,
        symbol: str,
        messages: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        批量保存社媒消息（JSON格式）
        
        Args:
            symbol: 股票代码
            messages: 消息列表
            
        Returns:
            保存结果
        """
        url = f"{self.base_url}/save"
        
        payload = {
            'symbol': symbol,
            'messages': messages
        }
        
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    
    def query_messages(
        self,
        symbol: str = None,
        platform: str = None,
        sentiment: str = None,
        start_time: str = None,
        end_time: str = None,
        limit: int = 50,
        skip: int = 0
    ) -> Dict[str, Any]:
        """
        查询社媒消息
        
        Args:
            symbol: 股票代码
            platform: 平台类型
            sentiment: 情绪类型（positive/negative/neutral）
            start_time: 开始时间（格式：YYYY-MM-DD HH:MM:SS）
            end_time: 结束时间（格式：YYYY-MM-DD HH:MM:SS）
            limit: 返回数量限制
            skip: 跳过数量
            
        Returns:
            查询结果
        """
        url = f"{self.base_url}/query"
        
        payload = {
            'limit': limit,
            'skip': skip
        }
        
        if symbol:
            payload['symbol'] = symbol
        if platform:
            payload['platform'] = platform
        if sentiment:
            payload['sentiment'] = sentiment
        if start_time:
            payload['start_time'] = start_time
        if end_time:
            payload['end_time'] = end_time
        
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    
    def get_latest_messages(
        self,
        symbol: str,
        platform: str = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        获取最新社媒消息
        
        Args:
            symbol: 股票代码
            platform: 平台类型（可选）
            limit: 返回数量
            
        Returns:
            最新消息列表
        """
        url = f"{self.base_url}/latest/{symbol}"
        
        params = {'limit': limit}
        if platform:
            params['platform'] = platform
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    
    def search_messages(
        self,
        query: str,
        symbol: str = None,
        platform: str = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        全文搜索社媒消息
        
        Args:
            query: 搜索关键词
            symbol: 股票代码（可选）
            platform: 平台类型（可选）
            limit: 返回数量
            
        Returns:
            搜索结果
        """
        url = f"{self.base_url}/search"
        
        params = {
            'query': query,
            'limit': limit
        }
        
        if symbol:
            params['symbol'] = symbol
        if platform:
            params['platform'] = platform
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    
    def get_statistics(
        self,
        symbol: str = None,
        hours_back: int = 24
    ) -> Dict[str, Any]:
        """
        获取统计信息
        
        Args:
            symbol: 股票代码（可选）
            hours_back: 回溯小时数
            
        Returns:
            统计信息
        """
        url = f"{self.base_url}/statistics"
        
        params = {'hours_back': hours_back}
        if symbol:
            params['symbol'] = symbol
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    
    def get_sentiment_analysis(
        self,
        symbol: str,
        platform: str = None,
        hours_back: int = 24
    ) -> Dict[str, Any]:
        """
        获取情绪分析
        
        Args:
            symbol: 股票代码
            platform: 平台类型（可选）
            hours_back: 回溯小时数
            
        Returns:
            情绪分析结果
        """
        url = f"{self.base_url}/sentiment-analysis/{symbol}"
        
        params = {'hours_back': hours_back}
        if platform:
            params['platform'] = platform
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    
    def get_platforms(self) -> Dict[str, Any]:
        """
        获取支持的平台列表
        
        Returns:
            平台列表
        """
        url = f"{self.base_url}/platforms"
        
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()


def example_upload_file(client: SocialMediaAPIClient = None):
    """示例：上传文件"""
    if client is None:
        print("[警告] 未提供认证客户端，API调用将失败")
        return
    
    # 使用传入的客户端
    
    try:
        # 获取当前脚本所在目录
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        template_file = os.path.join(script_dir, "social_media_template.json")
        
        # 如果模板文件不存在，跳过上传示例
        if not os.path.exists(template_file):
            print("[跳过] 模板文件不存在，跳过文件上传示例")
            print(f"   模板文件路径: {template_file}")
            return
        
        # 上传JSON文件
        result = client.upload_file(
            file_path=template_file,
            symbol="000001",
            platform="weibo",
            encoding="utf-8",
            overwrite=False
        )
        
        print("[成功] 文件上传成功！")
        print(f"   保存了 {result['data']['saved']} 条消息")
        print(f"   失败 {result['data']['failed']} 条")
        
    except Exception as e:
        print(f"[失败] 上传失败: {e}")


def example_save_messages(client: SocialMediaAPIClient = None):
    """示例：批量保存消息（JSON格式）"""
    if client is None:
        print("[警告] 未提供认证客户端，API调用将失败")
        return
    
    # 准备消息数据
    messages = [
        {
            "message_id": "weibo_001",
            "platform": "weibo",
            "message_type": "post",
            "content": "平安银行今天表现不错！",
            "hashtags": ["平安银行"],
            "author": {
                "author_id": "user_001",
                "author_name": "测试用户",
                "verified": False,
                "influence_score": 50.0,
                "followers_count": 1000
            },
            "engagement": {
                "views": 1000,
                "likes": 50,
                "shares": 10,
                "comments": 5,
                "engagement_rate": 6.5
            },
            "publish_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sentiment": "positive",
            "sentiment_score": 0.7,
            "keywords": ["平安银行"],
            "importance": "low",
            "credibility": "medium",
            "language": "zh-CN",
            "data_source": "manual"
        }
    ]
    
    try:
        result = client.save_messages(
            symbol="000001",
            messages=messages
        )
        
        print("[成功] 消息保存成功！")
        print(f"   保存了 {result['data']['saved']} 条消息")
        
    except Exception as e:
        print(f"[失败] 保存失败: {e}")


def example_query_messages(client: SocialMediaAPIClient = None):
    """示例：查询消息"""
    if client is None:
        print("[警告] 未提供认证客户端，API调用将失败")
        return
    
    try:
        # 查询最近24小时的正向情绪消息
        result = client.query_messages(
            symbol="000001",
            platform="weibo",
            sentiment="positive",
            limit=20
        )
        
        print(f"[成功] 查询成功！找到 {result['data']['count']} 条消息")
        
        for msg in result['data']['messages'][:5]:
            print(f"   - [{msg['platform']}] {msg['content'][:50]}...")
        
    except Exception as e:
        print(f"[失败] 查询失败: {e}")


def example_get_statistics(client: SocialMediaAPIClient = None):
    """示例：获取统计信息"""
    if client is None:
        print("[警告] 未提供认证客户端，API调用将失败")
        return
    
    try:
        # 不传hours_back，统计所有符合条件的数据
        result = client.get_statistics(
            symbol="000001"
        )
        
        stats = result['data']['statistics']
        print("[成功] 统计信息：")
        print(f"   总消息数: {stats['total_count']}")
        print(f"   正向: {stats['positive_count']}")
        print(f"   负向: {stats['negative_count']}")
        print(f"   中性: {stats['neutral_count']}")
        
    except Exception as e:
        print(f"[失败] 获取统计失败: {e}")


def example_get_sentiment_analysis(client: SocialMediaAPIClient = None):
    """示例：获取情绪分析"""
    if client is None:
        print("[警告] 未提供认证客户端，API调用将失败")
        return
    
    try:
        result = client.get_sentiment_analysis(
            symbol="000001",
            hours_back=24
        )
        
        data = result['data']
        print("[成功] 情绪分析：")
        print(f"   总消息数: {data['total_messages']}")
        print(f"   情绪评分: {data['sentiment_score']:.2f}")
        print(f"   情绪分布: {data['sentiment_distribution']}")
        
    except Exception as e:
        print(f"[失败] 获取情绪分析失败: {e}")


def example_login(username: str = None, password: str = None):
    """示例：登录获取token"""
    client = SocialMediaAPIClient()
    
    try:
        # 登录获取token
        login_url = BASE_URL.replace("/api/social-media", "/api/auth/login")
        
        # 如果没有提供用户名密码，尝试使用环境变量或默认值
        if not username:
            import os
            username = os.getenv("API_USERNAME", "admin")
        if not password:
            import os
            password = os.getenv("API_PASSWORD", "admin123")  # 默认密码是admin123
        
        login_data = {
            "username": username,
            "password": password
        }
        
        print(f"   尝试登录用户: {username}")
        response = requests.post(login_url, json=login_data)
        
        if response.status_code == 401:
            print(f"[失败] 登录失败：用户名或密码错误（401 Unauthorized）")
            print("   提示：")
            print("   1. 请确保后端服务正在运行（http://localhost:8000）")
            print("   2. 请检查用户名和密码是否正确")
            print("   3. 可以通过环境变量设置：export API_USERNAME=your_username API_PASSWORD=your_password")
            print("   4. 或者修改示例代码中的用户名和密码")
            return None
        
        response.raise_for_status()
        result = response.json()
        
        if result.get("success") and result.get("data"):
            token = result["data"]["access_token"]
            print("[成功] 登录成功！")
            print(f"   Token: {token[:50]}...")
            print(f"   用户: {result['data'].get('user', {}).get('username', 'N/A')}")
            return token
        else:
            print("[失败] 登录失败：响应格式错误")
            print(f"   响应: {result}")
            return None
            
    except requests.exceptions.ConnectionError as e:
        print(f"[失败] 无法连接到后端服务: {e}")
        print("   提示：请确保后端服务正在运行（http://localhost:8000）")
        return None
    except Exception as e:
        print(f"[失败] 登录失败: {e}")
        print("   提示：请检查后端服务状态和网络连接")
        return None


if __name__ == "__main__":
    print("=" * 60)
    print("社媒消息API接入示例")
    print("=" * 60)
    
    # 步骤0：登录获取token
    print("\n0. 登录获取Token：")
    print("   提示：可以通过环境变量设置用户名密码：")
    print("   export API_USERNAME=your_username API_PASSWORD=your_password")
    print("   或者修改示例代码中的example_login函数")
    
    token = example_login()
    
    if not token:
        print("\n[警告] 无法获取token，后续API调用将失败")
        print("   请先登录获取token，然后更新示例代码中的用户名和密码")
        print("   或者设置环境变量：API_USERNAME 和 API_PASSWORD")
        exit(1)
    
    # 使用token创建客户端
    client = SocialMediaAPIClient(token=token)
    
    # 示例1：上传文件
    print("\n1. 上传文件示例：")
    example_upload_file(client)
    
    # 示例2：批量保存消息
    print("\n2. 批量保存消息示例：")
    example_save_messages(client)
    
    # 示例3：查询消息
    print("\n3. 查询消息示例：")
    example_query_messages(client)
    
    # 示例4：获取统计信息
    print("\n4. 获取统计信息示例：")
    example_get_statistics(client)
    
    # 示例5：获取情绪分析
    print("\n5. 获取情绪分析示例：")
    example_get_sentiment_analysis(client)
    
    print("\n" + "=" * 60)
    print("示例程序运行完成！")
    print("=" * 60)
    print("\n注意：所有API端点现在都需要用户认证")
    print("   请在请求头中添加: Authorization: Bearer <token>")
    print("   使用示例代码中的login函数获取token")

