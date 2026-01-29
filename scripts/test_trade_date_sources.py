"""
测试各数据源的交易日历API功能
验证 Tushare、AKShare、BaoStock 是否能正常获取最后有效交易日期
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
from app.services.data_sources.manager import DataSourceManager
from app.services.data_sources.tushare_adapter import TushareAdapter
from app.services.data_sources.akshare_adapter import AKShareAdapter
from app.services.data_sources.baostock_adapter import BaoStockAdapter

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_tushare_trade_date():
    """测试 Tushare 交易日历API"""
    logger.info("=" * 80)
    logger.info("测试 Tushare 交易日历API")
    logger.info("=" * 80)
    
    try:
        adapter = TushareAdapter()
        
        # 检查可用性
        if not adapter.is_available():
            logger.error("❌ Tushare 数据源不可用")
            return None
        
        logger.info("✅ Tushare 数据源可用")
        
        # 获取最后有效交易日期
        logger.info("📅 正在通过交易日历API获取最后有效交易日期...")
        latest_date = adapter.find_latest_trade_date()
        
        if latest_date:
            logger.info(f"✅ Tushare 获取成功: {latest_date}")
            # 格式化显示
            try:
                date_obj = datetime.strptime(latest_date, "%Y%m%d")
                formatted_date = date_obj.strftime("%Y-%m-%d")
                logger.info(f"   格式化日期: {formatted_date}")
                
                # 计算距离今天的天数
                today = datetime.now()
                days_diff = (today - date_obj).days
                logger.info(f"   距离今天: {days_diff} 天")
            except Exception as e:
                logger.warning(f"   日期格式化失败: {e}")
            
            return latest_date
        else:
            logger.error("❌ Tushare 获取失败: 返回 None")
            return None
            
    except Exception as e:
        logger.error(f"❌ Tushare 测试失败: {e}", exc_info=True)
        return None


def test_akshare_trade_date():
    """测试 AKShare 交易日历API"""
    logger.info("=" * 80)
    logger.info("测试 AKShare 交易日历API")
    logger.info("=" * 80)
    
    try:
        adapter = AKShareAdapter()
        
        # 检查可用性（仅用于信息提示）
        is_avail = adapter.is_available()
        if is_avail:
            logger.info("✅ AKShare 数据源可用")
        else:
            logger.warning("⚠️  AKShare 数据源初始化可能有问题，但仍尝试调用API")
        
        # 直接尝试调用API，即使is_available返回False
        logger.info("📅 正在通过交易日历API获取最后有效交易日期...")
        latest_date = adapter.find_latest_trade_date()
        
        if latest_date:
            logger.info(f"✅ AKShare 获取成功: {latest_date}")
            # 格式化显示
            try:
                date_obj = datetime.strptime(latest_date, "%Y%m%d")
                formatted_date = date_obj.strftime("%Y-%m-%d")
                logger.info(f"   格式化日期: {formatted_date}")
                
                # 计算距离今天的天数
                today = datetime.now()
                days_diff = (today - date_obj).days
                logger.info(f"   距离今天: {days_diff} 天")
            except Exception as e:
                logger.warning(f"   日期格式化失败: {e}")
            
            return latest_date
        else:
            logger.error("❌ AKShare 获取失败: 返回 None")
            return None
            
    except Exception as e:
        logger.error(f"❌ AKShare 测试失败: {e}", exc_info=True)
        return None


def test_baostock_trade_date():
    """测试 BaoStock 交易日历API"""
    logger.info("=" * 80)
    logger.info("测试 BaoStock 交易日历API")
    logger.info("=" * 80)
    
    try:
        adapter = BaoStockAdapter()
        
        # 检查可用性（仅用于信息提示）
        is_avail = adapter.is_available()
        if is_avail:
            logger.info("✅ BaoStock 数据源可用")
        else:
            logger.warning("⚠️  BaoStock 数据源初始化可能有问题，但仍尝试调用API")
        
        # 直接尝试调用API，即使is_available返回False
        logger.info("📅 正在通过交易日历API获取最后有效交易日期...")
        latest_date = adapter.find_latest_trade_date()
        
        if latest_date:
            logger.info(f"✅ BaoStock 获取成功: {latest_date}")
            # 格式化显示
            try:
                date_obj = datetime.strptime(latest_date, "%Y%m%d")
                formatted_date = date_obj.strftime("%Y-%m-%d")
                logger.info(f"   格式化日期: {formatted_date}")
                
                # 计算距离今天的天数
                today = datetime.now()
                days_diff = (today - date_obj).days
                logger.info(f"   距离今天: {days_diff} 天")
            except Exception as e:
                logger.warning(f"   日期格式化失败: {e}")
            
            return latest_date
        else:
            logger.error("❌ BaoStock 获取失败: 返回 None")
            return None
            
    except Exception as e:
        logger.error(f"❌ BaoStock 测试失败: {e}", exc_info=True)
        return None


def test_cache_functionality():
    """测试缓存功能"""
    logger.info("=" * 80)
    logger.info("测试缓存功能")
    logger.info("=" * 80)
    
    try:
        from app.services.trade_date_cache_service import get_trade_date_cache_service
        from app.core.redis_client import init_redis
        
        # 初始化Redis连接
        try:
            asyncio.run(init_redis())
        except Exception as e:
            logger.warning(f"⚠️  Redis初始化失败: {e}，缓存功能可能不可用")
            return
        
        cache_service = get_trade_date_cache_service()
        
        # 测试写入缓存
        test_date = "20250129"
        logger.info(f"📝 测试写入缓存: tushare -> {test_date}")
        success = cache_service.set_cached_trade_date_sync("tushare", test_date)
        if success:
            logger.info("✅ 缓存写入成功")
        else:
            logger.warning("⚠️  缓存写入失败")
        
        # 测试读取缓存
        logger.info("📖 测试读取缓存: tushare")
        cached_date = cache_service.get_cached_trade_date_sync("tushare")
        if cached_date:
            logger.info(f"✅ 缓存读取成功: {cached_date}")
            if cached_date == test_date:
                logger.info("✅ 缓存数据一致")
            else:
                logger.warning(f"⚠️  缓存数据不一致: 期望 {test_date}, 实际 {cached_date}")
        else:
            logger.warning("⚠️  缓存读取失败")
        
        # 清除测试缓存
        cache_service.clear_cache_sync("tushare")
        logger.info("✅ 测试缓存已清除")
        
    except Exception as e:
        logger.error(f"❌ 缓存功能测试失败: {e}", exc_info=True)


def test_cache_retrieval():
    """测试从缓存获取"""
    logger.info("=" * 80)
    logger.info("测试缓存获取（第二次调用应该从缓存读取）")
    logger.info("=" * 80)
    
    try:
        from app.services.trade_date_cache_service import get_trade_date_cache_service
        from app.core.redis_client import init_redis
        
        # 初始化Redis连接
        try:
            asyncio.run(init_redis())
        except Exception as e:
            logger.warning(f"⚠️  Redis初始化失败: {e}，缓存功能可能不可用")
            return
        
        cache_service = get_trade_date_cache_service()
        
        # 测试各数据源的缓存读取
        for source in ["tushare", "akshare", "baostock"]:
            logger.info(f"\n📖 检查 {source} 的缓存:")
            cached_date = cache_service.get_cached_trade_date_sync(source)
            if cached_date:
                logger.info(f"   ✅ 缓存存在: {cached_date}")
            else:
                logger.info(f"   ⚠️  缓存不存在或已过期")
        
    except Exception as e:
        logger.error(f"❌ 缓存获取测试失败: {e}", exc_info=True)


def compare_results(results: dict):
    """比较各数据源的结果"""
    logger.info("=" * 80)
    logger.info("结果对比")
    logger.info("=" * 80)
    
    # 统计成功的数据源
    success_count = sum(1 for v in results.values() if v is not None)
    total_count = len(results)
    
    logger.info(f"成功获取: {success_count}/{total_count} 个数据源")
    
    # 显示各数据源的结果
    for source, date_str in results.items():
        status = "✅" if date_str else "❌"
        logger.info(f"{status} {source:15s}: {date_str or '获取失败'}")
    
    # 如果多个数据源都成功，比较日期是否一致
    successful_dates = {k: v for k, v in results.items() if v is not None}
    
    if len(successful_dates) > 1:
        logger.info("\n📊 日期一致性检查:")
        dates_set = set(successful_dates.values())
        if len(dates_set) == 1:
            logger.info(f"✅ 所有数据源返回的日期一致: {list(dates_set)[0]}")
        else:
            logger.warning(f"⚠️  数据源返回的日期不一致:")
            for source, date_str in successful_dates.items():
                try:
                    date_obj = datetime.strptime(date_str, "%Y%m%d")
                    formatted_date = date_obj.strftime("%Y-%m-%d")
                    logger.warning(f"   {source:15s}: {formatted_date} ({date_str})")
                except:
                    logger.warning(f"   {source:15s}: {date_str}")
    
    # 显示今天的信息
    today = datetime.now()
    logger.info(f"\n📅 今天是: {today.strftime('%Y-%m-%d %A')}")
    
    # 显示最近一周的日期信息
    logger.info("\n📅 最近一周的日期:")
    for i in range(7):
        date = today - timedelta(days=i)
        weekday = date.strftime('%A')
        logger.info(f"   {date.strftime('%Y-%m-%d')} ({weekday})")


def main():
    """主函数"""
    logger.info("=" * 80)
    logger.info("交易日历API测试程序（带缓存功能）")
    logger.info("=" * 80)
    logger.info(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("")
    
    # 测试缓存功能
    test_cache_functionality()
    logger.info("")
    
    results = {}
    
    # 测试 Tushare（第一次调用，会调用API并缓存）
    logger.info("🔄 第一次调用（会调用API并缓存）:")
    results['Tushare'] = test_tushare_trade_date()
    logger.info("")
    
    # 测试 AKShare（第一次调用，会调用API并缓存）
    results['AKShare'] = test_akshare_trade_date()
    logger.info("")
    
    # 测试 BaoStock（第一次调用，会调用API并缓存）
    results['BaoStock'] = test_baostock_trade_date()
    logger.info("")
    
    # 对比结果
    compare_results(results)
    
    # 测试缓存获取（第二次调用应该从缓存读取）
    logger.info("")
    test_cache_retrieval()
    
    # 再次测试（应该从缓存读取）
    logger.info("")
    logger.info("=" * 80)
    logger.info("🔄 第二次调用（应该从缓存读取）:")
    logger.info("=" * 80)
    
    results2 = {}
    results2['Tushare'] = test_tushare_trade_date()
    logger.info("")
    results2['AKShare'] = test_akshare_trade_date()
    logger.info("")
    results2['BaoStock'] = test_baostock_trade_date()
    logger.info("")
    
    # 对比两次结果
    logger.info("=" * 80)
    logger.info("两次调用结果对比:")
    logger.info("=" * 80)
    for source in results.keys():
        first = results.get(source)
        second = results2.get(source)
        if first == second:
            logger.info(f"✅ {source:15s}: 两次结果一致 ({first})")
        else:
            logger.warning(f"⚠️  {source:15s}: 第一次={first}, 第二次={second}")
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("测试完成")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
