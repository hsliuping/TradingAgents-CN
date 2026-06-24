#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票估值分析工具
支持 A股、港股的 PE/PB/PS/股息率分析及历史分位计算

作者: 弗兰克小斯基（Frankski）
Copyright (c) 2026 弗兰克小斯基（Frankski）. All rights reserved.

使用许可:
- 允许个人学习、研究、非商业用途使用
- 允许修改后个人使用
- 禁止直接复制核心算法用于商业产品或竞争性服务
- 禁止移除或修改作者署名后重新分发

免责声明: 本脚本提供的分析结果仅供参考，不构成投资建议。
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import sys
import argparse

# 指数代码映射（用于获取历史数据算分位）
INDEX_MAPPING = {
    "000300": "sh000300",  # 沪深300
    "000016": "sh000016",  # 上证50
    "000905": "sh000905",  # 中证500
    "399006": "sz399006",  # 创业板
    "000688": "sh000688",  # 科创50
    "HSI": "hkHSI",        # 恒生指数
    "HSTECH": "hkHSTECH",  # 恒生科技
}


def get_stock_valuation(stock_code, market="A"):
    """
    获取股票实时估值数据
    
    Args:
        stock_code: 股票代码 (如 "000858")
        market: "A" 或 "HK"
    
    Returns:
        dict: 包含 PE_TTM, PB, PS_TTM, 股息率等
    """
    try:
        if market == "A":
            # A股使用个股信息接口
            df = ak.stock_zh_a_spot_em()
            stock_row = df[df['代码'] == stock_code]
            if len(stock_row) == 0:
                return None
            
            row = stock_row.iloc[0]
            return {
                "code": stock_code,
                "name": row['名称'],
                "price": float(row['最新价']) if pd.notna(row['最新价']) else None,
                "pe_ttm": float(row['市盈率-动态']) if pd.notna(row['市盈率-动态']) else None,
                "pb": float(row['市净率']) if pd.notna(row['市净率']) else None,
                "ps_ttm": None,  # AKShare 实时接口不提供 PS
                "dividend_yield": float(row['股息率']) if pd.notna(row['股息率']) else None,
                "market_cap": float(row['总市值']) / 1e8 if pd.notna(row['总市值']) else None,  # 亿元
                "market": "A股"
            }
        else:
            # 港股
            df = ak.stock_hk_ggt_components_em()
            stock_row = df[df['代码'].str.contains(stock_code)]
            if len(stock_row) == 0:
                return None
            
            row = stock_row.iloc[0]
            return {
                "code": stock_code,
                "name": row['名称'],
                "price": float(row['最新价']) if pd.notna(row['最新价']) else None,
                "pe_ttm": float(row['市盈率']) if pd.notna(row['市盈率']) else None,
                "pb": None,  # 港股接口可能不提供 PB
                "ps_ttm": None,
                "dividend_yield": None,
                "market_cap": None,
                "market": "港股"
            }
    except Exception as e:
        print(f"获取估值数据失败: {e}", file=sys.stderr)
        return None


def get_historical_valuation(stock_code, years=10):
    """
    获取历史估值数据用于计算分位
    
    Returns:
        DataFrame with historical PE/PB data
    """
    try:
        # 使用理杏仁或 akshare 的估值数据接口
        # 这里使用指数估值作为参考（个股历史估值数据较难获取免费接口）
        # 实际使用时可能需要付费数据源如理杏仁、乌龟量化等
        
        # 获取历史价格数据
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=365*years)).strftime("%Y%m%d")
        
        df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", 
                                start_date=start_date, end_date=end_date)
        
        if df is None or len(df) == 0:
            return None
        
        # 计算历史价格分位（作为估值分位的近似）
        df['收盘'] = pd.to_numeric(df['收盘'], errors='coerce')
        return df
    except Exception as e:
        print(f"获取历史数据失败: {e}", file=sys.stderr)
        return None


def calculate_percentile(current_value, historical_values):
    """
    计算当前值在历史数据中的分位数
    
    Args:
        current_value: 当前值
        historical_values: 历史值列表/数组
    
    Returns:
        float: 百分位数 (0-100)
    """
    if historical_values is None or len(historical_values) == 0:
        return None
    
    historical_values = np.array(historical_values)
    historical_values = historical_values[~np.isnan(historical_values)]
    
    if len(historical_values) == 0:
        return None
    
    percentile = (historical_values <= current_value).mean() * 100
    return percentile


def get_industry_valuation(stock_code):
    """
    获取同行业公司估值对比
    
    Returns:
        dict: 行业中位数 PE, PB 等
    """
    try:
        # 获取所有 A股数据
        df = ak.stock_zh_a_spot_em()
        
        # 这里简化处理，实际应该根据行业分类筛选
        # 计算全市场估值中位数作为参考
        pe_median = df['市盈率-动态'].median()
        pb_median = df['市净率'].median()
        
        return {
            "market_pe_median": float(pe_median) if pd.notna(pe_median) else None,
            "market_pb_median": float(pb_median) if pd.notna(pb_median) else None,
            "note": "全市场中位数（行业数据需要更细分的分类接口）"
        }
    except Exception as e:
        print(f"获取行业估值失败: {e}", file=sys.stderr)
        return None


def format_valuation_report(valuation_data, percentiles=None, industry_data=None):
    """
    格式化估值分析报告
    """
    if valuation_data is None:
        return "无法获取估值数据"
    
    report = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 估值分析报告 - {valuation_data['name']} ({valuation_data['code']})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 基础数据
  当前价格: {valuation_data['price']:.2f} 元
  总市值: {valuation_data['market_cap']:.2f} 亿元
  市场: {valuation_data['market']}

📈 估值指标
"""
    
    if valuation_data['pe_ttm']:
        report += f"  PE-TTM: {valuation_data['pe_ttm']:.2f}x"
        if percentiles and 'pe' in percentiles:
            report += f" (历史{percentiles['pe']:.0f}%分位)"
        report += "\n"
    
    if valuation_data['pb']:
        report += f"  PB: {valuation_data['pb']:.2f}x"
        if percentiles and 'pb' in percentiles:
            report += f" (历史{percentiles['pb']:.0f}%分位)"
        report += "\n"
    
    if valuation_data['dividend_yield']:
        report += f"  股息率: {valuation_data['dividend_yield']:.2f}%\n"
    
    if industry_data:
        report += f"""
🏭 行业对比
  全市场 PE 中位数: {industry_data['market_pe_median']:.2f}x
  全市场 PB 中位数: {industry_data['market_pb_median']:.2f}x
  {industry_data['note']}
"""
    
    report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    return report


def main():
    parser = argparse.ArgumentParser(description='股票估值分析工具')
    parser.add_argument('stock_code', help='股票代码 (如 000858)')
    parser.add_argument('--market', choices=['A', 'HK'], default='A', help='市场 (A 或 HK)')
    parser.add_argument('--history-years', type=int, default=10, help='历史数据年限')
    
    args = parser.parse_args()
    
    # 获取估值数据
    valuation = get_stock_valuation(args.stock_code, args.market)
    
    if valuation is None:
        print(f"无法获取股票 {args.stock_code} 的数据", file=sys.stderr)
        sys.exit(1)
    
    # 获取历史数据计算分位
    hist_data = get_historical_valuation(args.stock_code, args.history_years)
    percentiles = {}
    
    if hist_data is not None:
        # 使用价格分位作为估值分位的近似
        if valuation['price']:
            percentiles['price'] = calculate_percentile(
                valuation['price'], 
                hist_data['收盘'].values
            )
    
    # 获取行业对比
    industry = get_industry_valuation(args.stock_code)
    
    # 生成报告
    report = format_valuation_report(valuation, percentiles, industry)
    print(report)
    
    # 输出 JSON 供程序调用
    result = {
        "valuation": valuation,
        "percentiles": percentiles,
        "industry": industry,
        "timestamp": datetime.now().isoformat()
    }
    
    # 同时输出 JSON 到 stderr 方便调用方解析
    print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)


if __name__ == "__main__":
    main()
