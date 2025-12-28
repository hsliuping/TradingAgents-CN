import akshare as ak
import pandas as pd
from typing import Dict, Optional, Tuple
from tradingagents.utils.logging_manager import get_logger

logger = get_logger("utils")

class IndexResolver:
    """
    指数代码解析器
    负责将输入的指数代码解析为可用的数据源参数
    解决 Code -> Data 的映射问题，特别是针对自定义/行业指数
    """
    
    # 静态映射表 (Code -> {name, source_type, ...})
    # source_type: 'index' (标准指数), 'concept' (概念板块), 'industry' (行业板块)
    STATIC_MAPPING = {
        # 常见行业/概念指数手动映射
        "980022": {"name": "半导体", "source_type": "concept", "symbol": "半导体"},
        "sh980022": {"name": "半导体", "source_type": "concept", "symbol": "半导体"},
        "BK0917": {"name": "半导体", "source_type": "concept", "symbol": "半导体"},
        "980032": {"name": "光伏设备", "source_type": "concept", "symbol": "光伏设备"},
        "sh980032": {"name": "光伏设备", "source_type": "concept", "symbol": "光伏设备"},
        "980030": {"name": "新能源车", "source_type": "concept", "symbol": "新能源车"},
    }
    
    # 内存缓存 (code -> result dict)
    _cache: Dict[str, Dict[str, str]] = {}

    @classmethod
    async def resolve(cls, code: str, market_type: str = "A股", use_cache: bool = True) -> Dict[str, str]:
        """
        解析指数代码
        """
        # 0. 检查缓存
        if use_cache and code in cls._cache:
            logger.info(f"✅ [IndexResolver] Hit memory cache for {code}: {cls._cache[code].get('symbol')}")
            return cls._cache[code].copy()
            
        # 1. 检查静态映射
        simple_code = code.strip().replace("sh", "").replace("sz", "").replace(".SH", "").replace(".SZ", "")
        # STATIC_MAPPING 已清空，跳过检查
        # if simple_code in cls.STATIC_MAPPING:
        #     logger.info(f"✅ [IndexResolver] Hit static mapping for {code}: {cls.STATIC_MAPPING[simple_code]['name']}")
        #     result = cls.STATIC_MAPPING[simple_code].copy()
        #     result["original_code"] = code
        #     if "description" not in result:
        #         result["description"] = f"{result.get('name')} ({result.get('source_type')})"
        #     
        #     if use_cache:
        #         cls._cache[code] = result
        #     return result
            
        result = await cls._resolve_logic(code, market_type)
        
        # 默认描述
        if result and "description" not in result:
             result["description"] = f"{result.get('name')} ({result.get('symbol')})"
        
        # 更新缓存
        if use_cache and result:
             cls._cache[code] = result
             
        return result

    @classmethod
    async def _resolve_logic(cls, code: str, market_type: str = "A股") -> Dict[str, str]:
        """
        内部解析逻辑
        """
        # 1. 清理代码
        clean_code = code.strip()
        # 移除常见前缀/后缀以便匹配
        simple_code = clean_code.replace("sh", "").replace("sz", "").replace(".SH", "").replace(".SZ", "")
        
        logger.info(f"🔍 [IndexResolver] Resolving code: {code} (simple: {simple_code}) with market: {market_type}")
            
        # 2. 动态查询 (AKShare)
        # 尝试从 AKShare 的板块列表中查找名称
        try:
            logger.info(f"🔄 [IndexResolver] Trying dynamic lookup for {simple_code}...")
            import asyncio
            loop = asyncio.get_running_loop()
            
            # 2.1 尝试概念板块 (Concept Board)
            def fetch_concepts():
                try:
                    return ak.stock_board_concept_name_em()
                except:
                    return pd.DataFrame()

            df_concepts = await loop.run_in_executor(None, fetch_concepts)
            if not df_concepts.empty:
                # 尝试直接匹配 '板块代码'
                match = df_concepts[df_concepts['板块代码'] == simple_code]
                
                # 尝试匹配 BK + 后四位 (常见模式)
                # 980022 -> BK0xxx? 不一定。
                # 东方财富的98xxxx通常对应BKxxxx? 
                # 例如 980022 可能是 BK0xxx。如果不确定，我们尝试模糊搜索名称? 
                # 但这里只有代码。
                # 策略: 尝试将 98xxxx 映射到 BKxxxx。
                # 980022 -> BK0022? (如果是纯数字匹配)
                
                if match.empty:
                    # 尝试 BK + 后四位
                    bk_code = "BK" + simple_code[-4:]
                    match = df_concepts[df_concepts['板块代码'] == bk_code]
                    
                # 尝试 BK + 后三位 (有些是3位)
                if match.empty:
                    bk_code_3 = "BK0" + simple_code[-3:]
                    match = df_concepts[df_concepts['板块代码'] == bk_code_3]

                if not match.empty:
                    name = match.iloc[0]['板块名称']
                    real_code = match.iloc[0]['板块代码']
                    logger.info(f"✅ [IndexResolver] Dynamic lookup success (concept): {simple_code} -> {name} ({real_code})")
                    return {
                        "name": name,
                        "source_type": "concept",
                        "symbol": name, # AKShare concept hist uses name
                        "original_code": code,
                        "description": f"{name}概念板块"
                    }

            # 2.2 尝试行业板块 (Industry Board)
            def fetch_industries():
                try:
                    return ak.stock_board_industry_name_em()
                except:
                    return pd.DataFrame()
            
            df_industries = await loop.run_in_executor(None, fetch_industries)
            if not df_industries.empty:
                match = df_industries[df_industries['板块代码'] == simple_code]
                
                # 尝试匹配 '板块名称'
                if match.empty:
                    match = df_industries[df_industries['板块名称'] == simple_code]
                    
                if match.empty:
                    bk_code = "BK" + simple_code[-4:]
                    match = df_industries[df_industries['板块代码'] == bk_code]
                    
                if not match.empty:
                    name = match.iloc[0]['板块名称']
                    logger.info(f"✅ [IndexResolver] Dynamic lookup success (industry): {simple_code} -> {name}")
                    return {
                        "name": name,
                        "source_type": "industry",
                        "symbol": name,
                        "original_code": code,
                        "description": f"{name}行业板块"
                    }
                    
            # 2.3 特殊映射策略 (980xxx)
            # 很多用户使用 980xxx 作为概念指数代码 (通达信/同花顺习惯)
            # 如果前面没找到，但代码是 980 开头，我们尝试去搜索
            if simple_code.startswith("980") or simple_code.startswith("880"): # 880是通达信板块
                 logger.info(f"⚠️ [IndexResolver] Detected potential concept code {simple_code}, trying brute force name search if possible or default to concept type")
                 # 由于无法从代码反推名称（除非有全量表），这里我们只能尽量猜测
                 # 或者，我们可以尝试调用 stock_board_concept_cons_em(symbol="名称")? 不行，我们需要名称。
                 # 如果前面没匹配到，说明该代码可能不在东财的概念列表中，或者映射规则不对。
                 # 此时我们最好将其标记为 "index" 并尝试通用指数接口，或者返回特定错误。
                 # 但为了流程不中断，我们返回一个带有 source_type='unknown_concept' 的结果?
                 # 不，Technical Analyst 会根据 source_type 决定调用哪个接口。
                 pass

        except Exception as e:
            logger.warning(f"⚠️ [IndexResolver] Dynamic lookup failed: {e}")

        # 3. 尝试作为标准指数验证 (Probe)
        # 如果动态查询失败，尝试验证是否为有效指数代码
        
        probe_candidates = [code, simple_code]
        
        if market_type == "A股":
            # 针对 980xxx，尝试加上 sz 前缀验证
            if simple_code.startswith("980"):
                 probe_candidates = [f"sz{simple_code}", f"sh{simple_code}"] + probe_candidates
            elif simple_code.startswith("000"):
                 probe_candidates = [f"sh{simple_code}"] + probe_candidates
            elif simple_code.startswith("399"):
                 probe_candidates = [f"sz{simple_code}"] + probe_candidates
            
            # 通用策略：如果原代码不带前缀，尝试加上 sz/sh
            if not code.lower().startswith(("sz", "sh")):
                 # 将可能的带前缀组合加到列表前面，优先尝试
                 probe_candidates = [f"sz{simple_code}", f"sh{simple_code}"] + probe_candidates
        
        elif market_type == "港股":
            # 港股处理逻辑...
            pass
        elif market_type == "美股":
            # 美股处理逻辑...
            pass

        for symbol in probe_candidates:
             try:
                 # 尝试获取最近一天的数据来验证代码有效性
                 # 使用 run_in_executor 避免阻塞
                 def probe_index():
                     try:
                         # 只获取最近几天的
                         return ak.stock_zh_index_daily(symbol=symbol)
                     except:
                         return None
                 
                 import asyncio
                 loop = asyncio.get_running_loop()
                 df_probe = await loop.run_in_executor(None, probe_index)
                 
                 if df_probe is not None and not df_probe.empty:
                     logger.info(f"✅ [IndexResolver] Validated as index: {symbol}")
                     return {
                         "name": f"指数{simple_code}", # 无法获取名称，使用通用名
                         "source_type": "index",
                         "symbol": symbol,
                         "original_code": code
                     }
             except Exception:
                 continue

        # 4. 默认回退逻辑
        logger.warning(f"⚠️ [IndexResolver] Unknown code {simple_code}, defaulting to index type.")
        return {
            "name": f"未知指数{simple_code}",
            "source_type": "index",
            "symbol": code,
            "original_code": code
        }

    @staticmethod
    def normalize_concept_data(df: pd.DataFrame) -> pd.DataFrame:
        """
        将板块接口返回的数据标准化为标准 OHLC 格式
        AKShare concept_hist 返回: 日期, 开盘, 收盘, 最高, 最低, ...
        需要转为: trade_date, open, close, high, low, volume
        """
        if df.empty:
            return df
            
        # 东方财富板块历史数据列名通常是中文
        rename_map = {
            "日期": "trade_date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
            "涨跌幅": "pct_chg",
            "换手率": "turnover_rate"
        }
        
        df = df.rename(columns=rename_map)
        
        # 确保类型正确
        numeric_cols = ["open", "close", "high", "low", "volume", "amount", "pct_chg"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        return df

