#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股股票基础信息同步到MongoDB
从通达信获取股票基础信息并同步到MongoDB数据库
"""

import os
import sys

# 先将仓库根目录加入 sys.path，确保可导入 tradingagents 包
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
import pandas as pd

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('scripts')

# 使用项目内的数据源管理器，替代缺失的 enhanced_stock_list_fetcher
from app.services.data_sources.manager import DataSourceManager

try:
    import pymongo
    from pymongo import MongoClient
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False
    logger.error(f"❌ pymongo未安装，请运行: pip install pymongo")

class StockInfoSyncer:
    """A股股票信息同步器"""
    
    def __init__(self, mongodb_config: Dict[str, Any] = None):
        """
        初始化同步器
        
        Args:
            mongodb_config: MongoDB配置字典
        """
        self.mongodb_client = None
        self.mongodb_db = None
        self.collection_name = "stock_basic_info"
        
        # 使用提供的配置或从环境变量读取
        if mongodb_config:
            self.mongodb_config = mongodb_config
        else:
            self.mongodb_config = self._load_mongodb_config_from_env()
        
        # 初始化MongoDB连接
        self._init_mongodb()
    
    def _load_mongodb_config_from_env(self) -> Dict[str, Any]:
        """从环境变量加载MongoDB配置"""
        from dotenv import load_dotenv
        load_dotenv()
        
        # 优先使用连接字符串
        connection_string = os.getenv('MONGODB_CONNECTION_STRING')
        if connection_string:
            return {
                'connection_string': connection_string,
                'database': os.getenv('MONGODB_DATABASE', 'tradingagents')
            }
        
        # 使用分离的配置参数
        return {
            'host': os.getenv('MONGODB_HOST', 'localhost'),
            'port': int(os.getenv('MONGODB_PORT', 27017)),
            'username': os.getenv('MONGODB_USERNAME'),
            'password': os.getenv('MONGODB_PASSWORD'),
            'database': os.getenv('MONGODB_DATABASE', 'tradingagents'),
            'auth_source': os.getenv('MONGODB_AUTH_SOURCE', 'admin')
        }
    
    def _init_mongodb(self):
        """初始化MongoDB连接"""
        if not MONGODB_AVAILABLE:
            logger.error(f"❌ MongoDB不可用，请安装pymongo")
            return
        
        try:
            # 构建连接字符串
            if 'connection_string' in self.mongodb_config:
                connection_string = self.mongodb_config['connection_string']
            else:
                config = self.mongodb_config
                if config.get('username') and config.get('password'):
                    connection_string = f"mongodb://{config['username']}:{config['password']}@{config['host']}:{config['port']}/{config['auth_source']}"
                else:
                    connection_string = f"mongodb://{config['host']}:{config['port']}/"
            
            # 创建客户端
            self.mongodb_client = MongoClient(
                connection_string,
                serverSelectionTimeoutMS=5000  # 5秒超时
            )
            
            # 测试连接
            self.mongodb_client.admin.command('ping')
            
            # 选择数据库
            self.mongodb_db = self.mongodb_client[self.mongodb_config['database']]
            
            logger.info(f"✅ MongoDB连接成功: {self.mongodb_config.get('host', 'unknown')}")
            
            # 创建索引
            self._create_indexes()
            
        except Exception as e:
            logger.error(f"❌ MongoDB连接失败: {e}")
            self.mongodb_client = None
            self.mongodb_db = None
    
    def _create_indexes(self):
        """创建数据库索引"""
        if self.mongodb_db is None:
            return
        
        try:
            collection = self.mongodb_db[self.collection_name]
            
            # 创建索引
            indexes = [
                ('code', 1),  # 股票代码索引
                ('sse', 1),   # 市场索引
                ([('code', 1), ('sse', 1)], {'unique': True}),  # 复合唯一索引
                ('sec', 1),   # 股票分类索引
                ('updated_at', -1),  # 更新时间索引
                ('name', 'text')  # 股票名称文本索引
            ]
            
            for index in indexes:
                if isinstance(index, tuple) and len(index) == 2 and isinstance(index[1], dict):
                    # 带选项的索引
                    collection.create_index(index[0], **index[1])
                else:
                    # 普通索引
                    collection.create_index(index)
            
            logger.info(f"✅ 数据库索引创建完成: {self.collection_name}")
            
        except Exception as e:
            logger.warning(f"⚠️ 创建索引时出现警告: {e}")
    
    def fetch_stock_data(self, stock_type: str = 'stock') -> Optional[pd.DataFrame]:
        """获取列表数据（优先 Tushare，回退 AKShare / BaoStock）"""
        logger.info(f"📊 正在获取 {stock_type} 列表数据（内置数据源管理器）...")

        # 目前仅对股票列表提供适配；index/etf 若未实现则跳过
        if stock_type not in ("stock", "stocks"):
            logger.warning(f"⚠️ 暂不支持类型 {stock_type} 的列表获取，跳过。")
            return None

        try:
            dsm = DataSourceManager()
            df, source = dsm.get_stock_list_with_fallback()
            if df is None or df.empty:
                logger.error("❌ 未能从任何数据源获取到股票列表")
                return None

            logger.info(f"✅ 成功从 {source} 获取 {len(df)} 条股票数据")

            # 规范化字段到本脚本需要的形态
            norm_df = self._normalize_stock_list_df(df)
            if norm_df is None or norm_df.empty:
                logger.error("❌ 股票列表规范化失败")
                return None
            return norm_df

        except Exception as e:
            logger.error(f"❌ 获取 {stock_type} 数据时发生错误: {e}")
            return None

    def _normalize_stock_list_df(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """将不同数据源返回的 DataFrame 规范化为:
        columns: code, name, sse, sec, market, volunit, decimal_point, pre_close
        """
        try:
            out = pd.DataFrame()

            # 统一取 6 位代码
            if 'symbol' in df.columns:
                out['code'] = df['symbol'].astype(str).str.zfill(6)
            elif 'ts_code' in df.columns:
                out['code'] = df['ts_code'].astype(str).str.split('.').str[0].str.zfill(6)
            elif 'code' in df.columns:
                out['code'] = df['code'].astype(str).str.zfill(6)
            else:
                # 无可用列
                return None

            # 名称
            name_col = None
            for c in ['name', '名称', 'sec_name', 'fullname']:
                if c in df.columns:
                    name_col = c
                    break
            out['name'] = df[name_col] if name_col else out['code']

            # 交易所简称 sse: sh/sz/bj —— 优先 ts_code 后缀，否则按代码前缀判断
            def infer_sse(row):
                # 如果有 ts_code 列，优先用后缀
                ts_code = str(row['ts_code']) if 'ts_code' in df.columns else ''
                if ts_code.endswith('.SH'):
                    return 'sh'
                if ts_code.endswith('.SZ'):
                    return 'sz'
                if ts_code.endswith('.BJ'):
                    return 'bj'
                code = str(row['code']).zfill(6)
                if code.startswith(('60', '68', '90')):
                    return 'sh'
                if code.startswith(('00', '30', '20')):
                    return 'sz'
                if code.startswith(('8', '4')):
                    return 'bj'
                return 'sz'

            tmp = df.copy()
            # 确保存在辅助列供推断使用
            if 'ts_code' not in tmp.columns:
                tmp['ts_code'] = ''
            tmp['code'] = out['code']
            out['sse'] = tmp.apply(infer_sse, axis=1)

            # 分类/板块: 优先 industry/行业，否则用 market 字段，否则 unknown
            if 'industry' in df.columns and df['industry'].notna().any():
                out['sec'] = df['industry'].fillna('unknown')
            elif 'market' in df.columns and df['market'].notna().any():
                out['sec'] = df['market'].fillna('unknown')
            else:
                out['sec'] = 'unknown'

            # 市场名称（中文便于可视化）
            out['market'] = out['sse'].map({'sh': '上海', 'sz': '深圳', 'bj': '北京'}).fillna('未知')

            # 其余字段设置默认值
            out['category'] = '股票'
            out['volunit'] = 0
            out['decimal_point'] = 0
            out['pre_close'] = 0.0

            # 去重 & 只保留必要列
            out = out.drop_duplicates(subset=['code', 'sse'])
            out = out[['code', 'name', 'sse', 'sec', 'market', 'category', 'volunit', 'decimal_point', 'pre_close']]
            return out
        except Exception as e:
            logger.error(f"规范化股票列表失败: {e}")
            return None
    
    def sync_to_mongodb(self, stock_data: pd.DataFrame) -> bool:
        """将股票数据同步到MongoDB"""
        if self.mongodb_db is None:
            logger.error(f"❌ MongoDB未连接，无法同步数据")
            return False
        
        if stock_data is None or stock_data.empty:
            logger.error(f"❌ 没有数据需要同步")
            return False
        
        try:
            collection = self.mongodb_db[self.collection_name]
            current_time = datetime.utcnow()
            
            # 准备批量操作
            bulk_operations = []
            
            for idx, row in stock_data.iterrows():
                # 构建文档
                document = {
                    'code': row['code'],
                    'name': row['name'],
                    'sse': row['sse'],
                    'market': row.get('market', '深圳' if row['sse'] == 'sz' else '上海'),
                    'sec': row.get('sec', 'unknown'),
                    'category': row.get('category', '未知'),
                    'volunit': row.get('volunit', 0),
                    'decimal_point': row.get('decimal_point', 0),
                    'pre_close': row.get('pre_close', 0.0),
                    'updated_at': current_time,
                    'sync_source': 'tdx',  # 数据来源标识
                    'data_version': '1.0'
                }
                
                # 添加创建时间（仅在插入时）
                update_doc = {
                    '$set': document,
                    '$setOnInsert': {'created_at': current_time}
                }
                
                # 使用upsert操作
                bulk_operations.append(
                    pymongo.UpdateOne(
                        {'code': row['code'], 'sse': row['sse']},
                        update_doc,
                        upsert=True
                    )
                )
            
            # 执行批量操作
            if bulk_operations:
                result = collection.bulk_write(bulk_operations)
                
                logger.info(f"📊 数据同步完成:")
                logger.info(f"  - 插入新记录: {result.upserted_count}")
                logger.info(f"  - 更新记录: {result.modified_count}")
                logger.info(f"  - 匹配记录: {result.matched_count}")
                
                return True
            else:
                logger.error(f"❌ 没有数据需要同步")
                return False
                
        except Exception as e:
            logger.error(f"❌ 同步数据到MongoDB时发生错误: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_sync_statistics(self) -> Dict[str, Any]:
        """获取同步统计信息"""
        if self.mongodb_db is None:
            return {}
        
        try:
            collection = self.mongodb_db[self.collection_name]
            
            # 总记录数
            total_count = collection.count_documents({})
            
            # 按市场统计
            market_stats = list(collection.aggregate([
                {'$group': {
                    '_id': '$sse',
                    'count': {'$sum': 1}
                }}
            ]))
            
            # 按分类统计
            category_stats = list(collection.aggregate([
                {'$group': {
                    '_id': '$sec',
                    'count': {'$sum': 1}
                }}
            ]))
            
            # 最近更新时间
            latest_update = collection.find_one(
                {},
                sort=[('updated_at', -1)]
            )
            
            return {
                'total_count': total_count,
                'market_distribution': {item['_id']: item['count'] for item in market_stats},
                'category_distribution': {item['_id']: item['count'] for item in category_stats},
                'latest_update': latest_update['updated_at'] if latest_update else None
            }
            
        except Exception as e:
            logger.error(f"❌ 获取统计信息时发生错误: {e}")
            return {}
    
    def query_stocks(self, 
                    code: str = None, 
                    name: str = None, 
                    market: str = None, 
                    category: str = None,
                    limit: int = 10) -> List[Dict[str, Any]]:
        """查询股票信息"""
        if self.mongodb_db is None:
            return []
        
        try:
            collection = self.mongodb_db[self.collection_name]
            
            # 构建查询条件
            query = {}
            if code:
                query['code'] = {'$regex': code, '$options': 'i'}
            if name:
                query['name'] = {'$regex': name, '$options': 'i'}
            if market:
                query['sse'] = market
            if category:
                query['sec'] = category
            
            # 执行查询
            cursor = collection.find(query).limit(limit)
            results = list(cursor)
            
            # 移除MongoDB的_id字段
            for result in results:
                if '_id' in result:
                    del result['_id']
            
            return results
            
        except Exception as e:
            logger.error(f"❌ 查询股票信息时发生错误: {e}")
            return []
    
    def close(self):
        """关闭数据库连接"""
        if self.mongodb_client:
            self.mongodb_client.close()
            logger.info(f"🔒 MongoDB连接已关闭")


def main():
    """主函数"""
    logger.info(f"=")
    logger.info(f"📊 A股股票基础信息同步到MongoDB")
    logger.info(f"=")
    
    # 创建同步器
    syncer = StockInfoSyncer()
    
    if syncer.mongodb_db is None:
        logger.error(f"❌ MongoDB连接失败，请检查配置")
        return
    
    try:
        # 同步股票数据
        logger.info(f"\n🏢 同步股票数据...")
        stock_data = syncer.fetch_stock_data('stock')
        if stock_data is not None:
            syncer.sync_to_mongodb(stock_data)
        
        # 指数与ETF目前未实现列表拉取，保留占位日志
        logger.info(f"\n📊 同步指数数据（暂未实现，跳过）...")
        logger.info(f"\n📈 同步ETF数据（暂未实现，跳过）...")
        
        # 显示统计信息
        logger.info(f"\n📊 同步统计信息:")
        stats = syncer.get_sync_statistics()
        if stats:
            logger.info(f"  总记录数: {stats.get('total_count', 0)}")
            
            market_dist = stats.get('market_distribution', {})
            if market_dist:
                logger.info(f"  市场分布:")
                for market, count in market_dist.items():
                    market_name = "深圳" if market == 'sz' else "上海"
                    logger.info(f"    {market_name}市场: {count} 条")
            
            category_dist = stats.get('category_distribution', {})
            if category_dist:
                logger.info(f"  分类分布:")
                for category, count in category_dist.items():
                    logger.info(f"    {category}: {count} 条")
            
            latest_update = stats.get('latest_update')
            if latest_update:
                logger.info(f"  最近更新: {latest_update}")
        
        # 示例查询
        logger.debug(f"\n🔍 示例查询 - 查找平安银行:")
        results = syncer.query_stocks(name="平安", limit=5)
        for result in results:
            logger.info(f"  {result['code']} - {result['name']} ({result['market']})")
        
    except KeyboardInterrupt:
        logger.info(f"\n⏹️ 用户中断操作")
    except Exception as e:
        logger.error(f"\n❌ 同步过程中发生错误: {e}")
        import traceback

        traceback.print_exc()
    finally:
        syncer.close()
    
    logger.info(f"\n✅ 同步完成")


if __name__ == "__main__":
    main()