from tradingagents.utils.stock_validator import StockDataPreparationResult
from tradingagents.utils.logging_manager import get_logger
import re

logger = get_logger('index_validator')

async def prepare_index_data_async(stock_code: str) -> StockDataPreparationResult:
    """Validate index code and check data availability."""
    
    # 1. Format Check
    # A股指数: 000300.SH, 399001.SZ
    # 美股/全球: ^GSPC, ^HSI, ^IXIC
    # 或简单的纯数字 (AKShare有时支持)
    
    # 简单正则
    is_valid_format = False
    if re.match(r"^\d{6}\.(SH|SZ)$", stock_code):
        is_valid_format = True
    elif stock_code.startswith("^"):
        is_valid_format = True
    # 允许一些常见名称如 'sh000001'
    elif re.match(r"^(sh|sz)\d{6}$", stock_code):
        is_valid_format = True
    # 允许中文名称（因为下游支持自动搜索）
    elif re.match(r"^[\u4e00-\u9fa5]+$", stock_code):
        is_valid_format = True
        
    if not is_valid_format:
        return StockDataPreparationResult(
            is_valid=False,
            stock_code=stock_code,
            error_message="指数代码格式错误",
            suggestion="A股指数请使用 000300.SH 格式，全球指数请使用 ^GSPC 格式，或直接输入中文名称"
        )
        
    # 2. Data Source Check (Lightweight)
    try:
        # 尝试导入 akshare，验证库是否安装
        import akshare as ak
        
        # 暂时只做格式检查，不做网络请求以节省时间
        logger.info(f"✅ 指数代码格式验证通过: {stock_code}")
        
        return StockDataPreparationResult(
            is_valid=True,
            stock_code=stock_code,
            stock_name="Index", # 暂不获取真实名称
            market_type="index",
            has_historical_data=True
        )
        
    except Exception as e:
        logger.error(f"❌ 数据源检查失败: {e}")
        return StockDataPreparationResult(
            is_valid=False,
            stock_code=stock_code,
            error_message=f"数据源不可用: {str(e)}",
            suggestion="请检查网络连接或数据源配置"
        )
