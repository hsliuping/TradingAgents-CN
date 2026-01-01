"""
社媒消息文件解析工具
支持CSV、JSON、Excel格式的文件解析
"""
import json
import csv
import io
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    logging.warning("pandas未安装，Excel文件解析功能不可用")

from app.models.social_media import SocialMediaMessageModel, AuthorInfo, EngagementInfo

logger = logging.getLogger(__name__)


class SocialMediaFileParser:
    """社媒消息文件解析器"""
    
    @staticmethod
    def parse_json(content: bytes, encoding: str = 'utf-8') -> List[Dict[str, Any]]:
        """
        解析JSON文件
        
        Args:
            content: 文件内容（字节）
            encoding: 文件编码
            
        Returns:
            消息列表
        """
        try:
            text = content.decode(encoding)
            data = json.loads(text)
            
            # 支持两种格式：
            # 1. 直接是数组: [{...}, {...}]
            # 2. 包含messages字段的对象: {"messages": [{...}, {...}]}
            if isinstance(data, list):
                messages = data
            elif isinstance(data, dict) and 'messages' in data:
                messages = data['messages']
            else:
                raise ValueError("JSON格式错误：必须是数组或包含'messages'字段的对象")
            
            logger.info(f"✅ JSON解析成功: {len(messages)} 条消息")
            return messages
            
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON解析失败: {str(e)}")
        except UnicodeDecodeError as e:
            raise ValueError(f"文件编码错误: {str(e)}，请尝试使用UTF-8编码")
    
    @staticmethod
    def parse_csv(content: bytes, encoding: str = 'utf-8') -> List[Dict[str, Any]]:
        """
        解析CSV文件
        
        Args:
            content: 文件内容（字节）
            encoding: 文件编码
            
        Returns:
            消息列表
        """
        try:
            text = content.decode(encoding)
            reader = csv.DictReader(io.StringIO(text))
            messages = list(reader)
            
            # 转换数据类型
            for msg in messages:
                # 转换时间字段
                if 'publish_time' in msg and msg['publish_time']:
                    try:
                        # 尝试多种时间格式
                        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d %H:%M:%S', '%Y/%m/%d']:
                            try:
                                msg['publish_time'] = datetime.strptime(msg['publish_time'], fmt)
                                break
                            except ValueError:
                                continue
                        else:
                            raise ValueError(f"无法解析时间格式: {msg['publish_time']}")
                    except Exception as e:
                        logger.warning(f"⚠️ 时间解析失败: {e}，使用当前时间")
                        msg['publish_time'] = datetime.utcnow()
                
                # 转换数字字段
                for field in ['sentiment_score', 'influence_score', 'engagement_rate']:
                    if field in msg and msg[field]:
                        try:
                            msg[field] = float(msg[field])
                        except (ValueError, TypeError):
                            msg[field] = 0.0
                
                for field in ['views', 'likes', 'shares', 'comments', 'followers_count']:
                    if field in msg and msg[field]:
                        try:
                            msg[field] = int(msg[field])
                        except (ValueError, TypeError):
                            msg[field] = 0
                
                # 转换布尔字段
                for field in ['verified']:
                    if field in msg and msg[field]:
                        msg[field] = str(msg[field]).lower() in ['true', '1', 'yes', '是']
                
                # 转换列表字段（CSV中可能是逗号分隔的字符串）
                for field in ['hashtags', 'keywords', 'topics', 'media_urls']:
                    if field in msg and msg[field]:
                        if isinstance(msg[field], str):
                            msg[field] = [item.strip() for item in msg[field].split(',') if item.strip()]
                        elif not isinstance(msg[field], list):
                            msg[field] = []
                
                # 构建author对象
                if 'author_id' in msg or 'author_name' in msg:
                    msg['author'] = {
                        'author_id': msg.pop('author_id', ''),
                        'author_name': msg.pop('author_name', ''),
                        'verified': msg.pop('verified', False),
                        'influence_score': msg.pop('influence_score', 0.0),
                        'followers_count': msg.pop('followers_count', 0),
                        'avatar_url': msg.pop('avatar_url', None)
                    }
                
                # 构建engagement对象
                if any(field in msg for field in ['views', 'likes', 'shares', 'comments']):
                    msg['engagement'] = {
                        'views': msg.pop('views', 0),
                        'likes': msg.pop('likes', 0),
                        'shares': msg.pop('shares', 0),
                        'comments': msg.pop('comments', 0),
                        'engagement_rate': msg.pop('engagement_rate', 0.0)
                    }
            
            logger.info(f"✅ CSV解析成功: {len(messages)} 条消息")
            return messages
            
        except Exception as e:
            raise ValueError(f"CSV解析失败: {str(e)}")
    
    @staticmethod
    def parse_excel(content: bytes) -> List[Dict[str, Any]]:
        """
        解析Excel文件（支持.xlsx和.xls）
        
        Args:
            content: 文件内容（字节）
            
        Returns:
            消息列表
        """
        if not PANDAS_AVAILABLE:
            raise ValueError("pandas未安装，无法解析Excel文件。请安装: pip install pandas openpyxl")
        
        try:
            # 读取Excel文件
            df = pd.read_excel(io.BytesIO(content), engine='openpyxl')
            
            # 转换为字典列表
            messages = df.to_dict('records')
            
            # 清理NaN值
            for msg in messages:
                for key, value in list(msg.items()):
                    if pd.isna(value):
                        msg[key] = None
                    elif isinstance(value, (int, float)) and pd.isna(value):
                        msg[key] = 0
            
            # 转换数据类型（与CSV类似）
            for msg in messages:
                # 转换时间字段
                if 'publish_time' in msg and msg['publish_time']:
                    if isinstance(msg['publish_time'], datetime):
                        pass  # 已经是datetime类型
                    elif isinstance(msg['publish_time'], str):
                        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d %H:%M:%S', '%Y/%m/%d']:
                            try:
                                msg['publish_time'] = datetime.strptime(msg['publish_time'], fmt)
                                break
                            except ValueError:
                                continue
                        else:
                            msg['publish_time'] = datetime.utcnow()
                    elif pd.isna(msg['publish_time']):
                        msg['publish_time'] = datetime.utcnow()
                
                # 转换数字字段
                for field in ['sentiment_score', 'influence_score', 'engagement_rate']:
                    if field in msg and msg[field] is not None:
                        try:
                            msg[field] = float(msg[field])
                        except (ValueError, TypeError):
                            msg[field] = 0.0
                
                for field in ['views', 'likes', 'shares', 'comments', 'followers_count']:
                    if field in msg and msg[field] is not None:
                        try:
                            msg[field] = int(msg[field])
                        except (ValueError, TypeError):
                            msg[field] = 0
                
                # 转换布尔字段
                for field in ['verified']:
                    if field in msg and msg[field] is not None:
                        if isinstance(msg[field], bool):
                            pass
                        else:
                            msg[field] = str(msg[field]).lower() in ['true', '1', 'yes', '是']
                
                # 转换列表字段
                for field in ['hashtags', 'keywords', 'topics', 'media_urls']:
                    if field in msg and msg[field] is not None:
                        if isinstance(msg[field], str):
                            msg[field] = [item.strip() for item in str(msg[field]).split(',') if item.strip()]
                        elif not isinstance(msg[field], list):
                            msg[field] = []
                
                # 构建author对象
                if 'author_id' in msg or 'author_name' in msg:
                    msg['author'] = {
                        'author_id': msg.pop('author_id', ''),
                        'author_name': msg.pop('author_name', ''),
                        'verified': msg.pop('verified', False),
                        'influence_score': msg.pop('influence_score', 0.0),
                        'followers_count': msg.pop('followers_count', 0),
                        'avatar_url': msg.pop('avatar_url', None)
                    }
                
                # 构建engagement对象
                if any(field in msg for field in ['views', 'likes', 'shares', 'comments']):
                    msg['engagement'] = {
                        'views': msg.pop('views', 0),
                        'likes': msg.pop('likes', 0),
                        'shares': msg.pop('shares', 0),
                        'comments': msg.pop('comments', 0),
                        'engagement_rate': msg.pop('engagement_rate', 0.0)
                    }
            
            logger.info(f"✅ Excel解析成功: {len(messages)} 条消息")
            return messages
            
        except Exception as e:
            raise ValueError(f"Excel解析失败: {str(e)}")
    
    @staticmethod
    def parse_file(content: bytes, filename: str, encoding: str = 'utf-8') -> List[Dict[str, Any]]:
        """
        根据文件扩展名自动选择解析方法
        
        Args:
            content: 文件内容（字节）
            filename: 文件名
            encoding: 文件编码（仅用于CSV和JSON）
            
        Returns:
            消息列表
        """
        file_ext = Path(filename).suffix.lower()
        
        if file_ext == '.json':
            return SocialMediaFileParser.parse_json(content, encoding)
        elif file_ext == '.csv':
            return SocialMediaFileParser.parse_csv(content, encoding)
        elif file_ext in ['.xlsx', '.xls']:
            return SocialMediaFileParser.parse_excel(content)
        else:
            raise ValueError(f"不支持的文件格式: {file_ext}，支持格式: .json, .csv, .xlsx, .xls")
    
    @staticmethod
    def validate_and_normalize_messages(
        messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        验证和规范化消息数据
        
        Args:
            messages: 原始消息列表（必须包含symbol和platform字段）
            
        Returns:
            规范化后的消息列表
        """
        normalized = []
        errors = []
        
        for idx, msg in enumerate(messages):
            try:
                # 🔥 验证必需字段
                if 'symbol' not in msg or not msg['symbol']:
                    errors.append(f"第{idx+1}条消息缺少symbol字段（股票代码）")
                    continue
                
                if 'platform' not in msg or not msg['platform']:
                    errors.append(f"第{idx+1}条消息缺少platform字段（平台类型）")
                    continue
                
                symbol = msg['symbol']
                
                # 🔥 根据每条消息的股票代码自动识别市场类型
                market_type = None
                try:
                    from tradingagents.utils.stock_utils import StockUtils
                    market_info = StockUtils.get_market_info(symbol)
                    if market_info.get('is_china'):
                        market_type = 'A股'
                    elif market_info.get('is_hk'):
                        market_type = '港股'
                    elif market_info.get('is_us'):
                        market_type = '美股'
                    else:
                        market_type = 'A股'  # 默认A股
                except Exception as e:
                    logger.warning(f"⚠️ 无法识别市场类型（symbol={symbol}），使用默认值A股: {e}")
                    market_type = 'A股'
                
                # 🔥 自动识别或设置市场类型
                if 'market' not in msg or not msg['market']:
                    # 如果消息中没有market字段，使用自动识别的市场类型
                    msg['market'] = market_type
                else:
                    # 如果消息中有market字段，验证并标准化
                    market_value = msg['market']
                    if market_value.lower() in ['a股', 'china', 'china_a', 'cn']:
                        msg['market'] = 'A股'
                    elif market_value.lower() in ['港股', 'hong_kong', 'hk', 'hongkong']:
                        msg['market'] = '港股'
                    elif market_value.lower() in ['美股', 'us', 'usa', 'america']:
                        msg['market'] = '美股'
                    # 如果已经是标准格式（A股/港股/美股），保持不变
                
                # 确保有message_id（如果没有，生成一个）
                if 'message_id' not in msg or not msg['message_id']:
                    import uuid
                    msg['message_id'] = str(uuid.uuid4())
                
                # 确保有publish_time（如果没有，使用当前时间）
                if 'publish_time' not in msg or not msg['publish_time']:
                    msg['publish_time'] = datetime.utcnow()
                elif isinstance(msg['publish_time'], str):
                    # 尝试解析字符串时间
                    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d %H:%M:%S', '%Y/%m/%d']:
                        try:
                            msg['publish_time'] = datetime.strptime(msg['publish_time'], fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        msg['publish_time'] = datetime.utcnow()
                
                # 确保有data_source
                if 'data_source' not in msg or not msg['data_source']:
                    msg['data_source'] = 'manual'
                
                # 🔥 修复MongoDB语言代码问题：将zh-CN转换为none
                if msg.get('language') == 'zh-CN':
                    msg['language'] = 'none'
                elif not msg.get('language'):
                    msg['language'] = 'none'
                
                # 使用Pydantic模型验证
                try:
                    validated_msg = SocialMediaMessageModel.from_dict(msg)
                    normalized.append(validated_msg.to_dict())
                except Exception as e:
                    errors.append(f"第{idx+1}条消息验证失败: {str(e)}")
                    logger.warning(f"⚠️ 消息验证失败 (第{idx+1}条): {e}")
                    # 即使验证失败，也尝试保存（使用默认值）
                    normalized.append(msg)
                    
            except Exception as e:
                errors.append(f"第{idx+1}条消息处理失败: {str(e)}")
                logger.error(f"❌ 消息处理失败 (第{idx+1}条): {e}")
        
        if errors:
            error_msg = "验证失败，以下消息有问题：\n" + "\n".join(errors[:10])
            if len(errors) > 10:
                error_msg += f"\n...还有{len(errors)-10}条消息有问题"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        logger.info(f"✅ 验证完成: {len(normalized)}/{len(messages)} 条消息通过验证")
        return normalized

