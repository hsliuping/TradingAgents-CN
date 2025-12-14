#!/usr/bin/env python3
"""
市场和类型检测器
自动识别股票代码的市场类型和分析类型（个股/指数）
"""

from typing import Tuple
import re


class MarketSymbolDetector:
    """市场和代码类型检测器"""
    
    # A股指数白名单（常见指数代码）
    A_STOCK_INDICES = {
        # 上证系列
        '000001',  # 上证指数
        '000003', '000008', '000009', '000010',
        '000016', '000300', '000688', '000852', '000905', '000906',
        '000985', '000991', '000992',
        
        # 深证系列
        '399001', '399002', '399003', '399004', '399005', '399006',
        '399100', '399101', '399102', '399106', '399107', '399108',
        '399330', '399678', '399550',
        
        # 中证指数（6位数字开头为93）
        # 会通过正则匹配覆盖
        
        # 特殊指数（以30开头但不是300xxx创业板）
        '300024',  # 机器人指数
    }
    
    # A股个股白名单（特殊情况：000开头但是个股）
    A_STOCK_STOCKS = {
        '000002',  # 万科A
        '000004',  # 国农科技
        '000005',  # 世纪星源
        '000006',  # 深振业Ａ
        '000007',  # 全新好
        # 可以继续添加...
    }
    
    @classmethod
    def detect(cls, symbol: str) -> Tuple[str, str]:
        """
        检测市场类型和分析类型
        
        Args:
            symbol: 股票/指数代码
            
        Returns:
            (market_type, analysis_type)
            - market_type: "A股", "港股", "美股", "未知"
            - analysis_type: "stock", "index", "unknown"
        """
        if not symbol:
            return ("未知", "unknown")
            
        symbol = symbol.strip().upper()
        
        # ==================== A股检测 ====================
        
        # 1. 带SH/SZ前缀
        if re.match(r'^(SH|SZ)', symbol):
            code = symbol[2:]
            return cls._detect_a_stock(code)
        
        # 2. 6位纯数字
        if re.match(r'^\d{6}$', symbol):
            return cls._detect_a_stock(symbol)
        
        # 3. 中证指数格式: 123456.CSI
        if re.match(r'^\d{6}\.CSI$', symbol):
            return ("A股", "index")
        
        # 4. 申万指数格式: 123456.SI
        if re.match(r'^\d{6}\.SI$', symbol):
            return ("A股", "index")
        
        # 5. H+5位数字（中证指数）
        if re.match(r'^H\d{5}$', symbol):
            return ("A股", "index")
        
        # ==================== 港股检测 ====================
        
        # 6. 港股格式: 12345.HK 或 01234.HK
        if re.match(r'^\d{4,5}\.HK$', symbol):
            return ("港股", "stock")
        
        # 7. 4-5位纯数字（可能是港股简写）
        if re.match(r'^\d{4,5}$', symbol):
            return ("港股", "stock")
        
        # 8. 恒生指数
        if symbol in ['HSI', 'HSCEI', 'HSTECH', '^HSI', '^HSCEI']:
            return ("港股", "index")
        
        # ==================== 美股检测 ====================
        
        # 9. 美股指数简写（在字母匹配之前检查）
        if symbol in ['SPX', 'DJI', 'IXIC', 'NDX', 'RUT', 'VIX']:
            return ("美股", "index")
        
        # 10. 美股指数: ^开头
        if re.match(r'^\^[A-Z]+$', symbol):
            return ("美股", "index")
        
        # 11. 美股格式: 1-5位字母（可能带点号）
        if re.match(r'^[A-Z]{1,5}(\.[A-Z])?$', symbol):
            return ("美股", "stock")
        
        # ==================== 未知 ====================
        return ("未知", "unknown")
    
    @classmethod
    def _detect_a_stock(cls, code: str) -> Tuple[str, str]:
        """
        检测A股代码是指数还是个股
        
        Args:
            code: 6位数字代码（不带前缀）
            
        Returns:
            (market_type, analysis_type)
        """
        # 0. 个股白名单检查（最高优先级）
        if code in cls.A_STOCK_STOCKS:
            return ("A股", "stock")
        
        # 1. 白名单检查（常见指数）
        if code in cls.A_STOCK_INDICES:
            return ("A股", "index")
        
        # 2. 指数代码段匹配
        
        # 000xxx: 上证指数（000001-000999大部分是指数）
        if re.match(r'^000\d{3}$', code):
            # 000001-000100: 上证指数
            # 000100-000999: 部分是指数，使用白名单
            num = int(code)
            if num <= 100 or code in cls.A_STOCK_INDICES:
                return ("A股", "index")
            # 000100之后如果不在白名单，可能是深市个股
            # 000001-009999 是深市主板，但000开头6位的基本都是指数
            # 这里采用保守策略：000xxx 优先判断为指数
            return ("A股", "index")
        
        # 399xxx: 深证指数（399001-399999大部分是指数）
        if re.match(r'^399\d{3}$', code):
            return ("A股", "index")
        
        # 93xxxx: 中证指数
        if re.match(r'^93\d{4}$', code):
            return ("A股", "index")
        
        # 30xxxx: 可能是指数（如中证科技类指数）
        # 但300xxx是创业板个股，需要区分
        if re.match(r'^30\d{4}$', code):
            # 300xxx: 创业板个股（300001-300999）
            if re.match(r'^300\d{3}$', code):
                return ("A股", "stock")
            # 30xxxx（超过4位）：可能是指数
            return ("A股", "index")
        
        # 3. 个股代码段
        
        # 6xxxxx: 沪市主板
        if re.match(r'^6\d{5}$', code):
            return ("A股", "stock")
        
        # 00xxxx: 深市主板（排除000开头的指数）
        # 000001-000999: 已在上面处理（指数）
        # 001xxx-009xxx: 深市主板个股
        if re.match(r'^00[1-9]\d{3}$', code):
            return ("A股", "stock")
        
        # 002xxx: 中小板
        if re.match(r'^002\d{3}$', code):
            return ("A股", "stock")
        
        # 300xxx: 创业板（3位后缀）
        if re.match(r'^300\d{3}$', code):
            return ("A股", "stock")
        
        # 688xxx: 科创板
        if re.match(r'^688\d{3}$', code):
            return ("A股", "stock")
        
        # 43xxxx/83xxxx/87xxxx: 北交所
        if re.match(r'^(43|83|87)\d{4}$', code):
            return ("A股", "stock")
        
        # 4. 默认策略
        # 如果都不匹配，根据代码长度判断
        # 6位数字：默认按个股处理（保守策略）
        return ("A股", "stock")


def detect_market_and_type(symbol: str) -> Tuple[str, str]:
    """
    便捷函数：检测市场类型和分析类型
    
    Args:
        symbol: 股票/指数代码
        
    Returns:
        (market_type, analysis_type)
    """
    return MarketSymbolDetector.detect(symbol)


# ==================== 测试代码 ====================
if __name__ == "__main__":
    """测试各种代码格式"""
    test_cases = [
        # A股个股
        ("600519", ("A股", "stock"), "贵州茅台"),
        ("000002", ("A股", "stock"), "万科A"),
        ("300750", ("A股", "stock"), "宁德时代"),
        ("688981", ("A股", "stock"), "中芯国际"),
        ("sh600519", ("A股", "stock"), "带前缀-贵州茅台"),
        
        # A股指数
        ("000001", ("A股", "index"), "上证指数"),
        ("000300", ("A股", "index"), "沪深300"),
        ("000016", ("A股", "index"), "上证50"),
        ("000852", ("A股", "index"), "中证1000"),
        ("399006", ("A股", "index"), "创业板指"),
        ("300024", ("A股", "index"), "机器人指数"),
        ("931865", ("A股", "index"), "中证半导体"),
        ("931643", ("A股", "index"), "中证机器人"),
        ("931865.CSI", ("A股", "index"), "中证半导体CSI"),
        ("H30184", ("A股", "index"), "中证半导体H格式"),
        ("801010.SI", ("A股", "index"), "申万农林牧渔"),
        
        # 港股
        ("00700.HK", ("港股", "stock"), "腾讯"),
        ("0700", ("港股", "stock"), "腾讯简写"),
        ("HSI", ("港股", "index"), "恒生指数"),
        
        # 美股
        ("AAPL", ("美股", "stock"), "苹果"),
        ("BRK.B", ("美股", "stock"), "伯克希尔B股"),
        ("^GSPC", ("美股", "index"), "标普500"),
        ("SPX", ("美股", "index"), "标普500简写"),
    ]
    
    detector = MarketSymbolDetector()
    print("\n" + "="*80)
    print("市场和类型检测测试")
    print("="*80 + "\n")
    
    passed = 0
    failed = 0
    
    for symbol, expected, desc in test_cases:
        result = detector.detect(symbol)
        status = "✅" if result == expected else "❌"
        
        if result == expected:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} {symbol:15s} → 市场:{result[0]:4s} 类型:{result[1]:7s} | {desc}")
        if result != expected:
            print(f"   预期: 市场:{expected[0]:4s} 类型:{expected[1]:7s}")
    
    print(f"\n{'='*80}")
    print(f"测试结果: {passed}/{len(test_cases)} 通过")
    print(f"{'='*80}\n")
