#!/usr/bin/env python3
"""
缓存现有分析结果的脚本
将已有的股票分析数据缓存到新的缓存系统中
"""

import os
import sys
import json
from datetime import date, datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tradingagents.utils.analysis_cache import get_global_cache, cache_analysis_result
from tradingagents.utils.logging_manager import get_logger

logger = get_logger('cache_script')

def cache_existing_progress_files():
    """缓存data目录中的现有分析进度文件"""
    data_dir = project_root / "data"
    cache = get_global_cache()
    
    logger.info("🔍 开始扫描现有分析文件...")
    
    # 处理progress_analysis文件
    progress_files = list(data_dir.glob("progress_analysis_*.json"))
    
    for progress_file in progress_files:
        try:
            logger.info(f"📄 处理文件: {progress_file.name}")
            
            with open(progress_file, 'r', encoding='utf-8') as f:
                progress_data = json.load(f)
            
            # 从文件名提取日期
            filename_parts = progress_file.stem.split('_')
            if len(filename_parts) >= 3:
                date_str = filename_parts[2]  # 20250730格式
                # 转换为标准日期格式
                try:
                    analysis_date = datetime.strptime(date_str, '%Y%m%d').strftime('%Y-%m-%d')
                except ValueError:
                    analysis_date = date.today().strftime('%Y-%m-%d')
            else:
                analysis_date = date.today().strftime('%Y-%m-%d')
            
            # 尝试从分析数据中提取股票代码
            stock_symbol = None
            
            # 方法1: 检查analysis_id中是否包含股票代码
            analysis_id = progress_data.get('analysis_id', '')
            
            # 方法2: 检查steps中的结果数据
            if 'results' in progress_data:
                for step_key, step_result in progress_data['results'].items():
                    if isinstance(step_result, dict) and 'stock_symbol' in step_result:
                        stock_symbol = step_result['stock_symbol']
                        break
            
            # 如果找不到股票代码，使用文件分析ID作为标识
            if not stock_symbol:
                stock_symbol = f"UNKNOWN_{filename_parts[1]}"  # 使用ID部分
            
            logger.info(f"📊 股票代码: {stock_symbol}, 分析日期: {analysis_date}")
            
            # 保存到缓存
            success = cache.save_analysis(stock_symbol, progress_data, analysis_date)
            if success:
                logger.info(f"✅ 已缓存: {stock_symbol} ({analysis_date})")
            else:
                logger.error(f"❌ 缓存失败: {stock_symbol}")
                
        except Exception as e:
            logger.error(f"❌ 处理文件失败 {progress_file.name}: {e}")
    
    # 处理reports目录中的分析报告
    reports_dir = data_dir / "reports"
    if reports_dir.exists():
        report_files = list(reports_dir.glob("*.md"))
        
        for report_file in report_files:
            try:
                # 从文件名解析股票代码和日期
                filename = report_file.stem
                parts = filename.split('_')
                
                if len(parts) >= 3:
                    stock_symbol = parts[0]
                    date_part = parts[-2]  # 倒数第二个部分通常是日期
                    
                    try:
                        analysis_date = datetime.strptime(date_part, '%Y%m%d').strftime('%Y-%m-%d')
                    except ValueError:
                        analysis_date = date.today().strftime('%Y-%m-%d')
                    
                    # 读取报告内容
                    with open(report_file, 'r', encoding='utf-8') as f:
                        report_content = f.read()
                    
                    # 构造分析数据
                    analysis_data = {
                        'type': 'markdown_report',
                        'source_file': str(report_file),
                        'content': report_content,
                        'generated_time': datetime.fromtimestamp(report_file.stat().st_mtime).isoformat()
                    }
                    
                    # 保存到缓存
                    success = cache.save_analysis(stock_symbol, analysis_data, analysis_date)
                    if success:
                        logger.info(f"✅ 已缓存报告: {stock_symbol} ({analysis_date})")
                        
            except Exception as e:
                logger.error(f"❌ 处理报告失败 {report_file.name}: {e}")

def create_920005_sample_data():
    """为920005创建示例分析数据"""
    from datetime import timedelta
    
    cache = get_global_cache()
    
    logger.info("🚢 创建920005江龙船艇的示例分析数据...")
    
    # 创建今天的分析数据
    today = date.today().strftime('%Y-%m-%d')
    
    sample_analysis = {
        'stock_symbol': '920005',
        'stock_name': '江龙船艇',
        'market_type': 'A股',
        'analysis_type': 'comprehensive',
        'analysis_date': today,
        'created_time': datetime.now().isoformat(),
        'market_analysis': {
            'current_price': 64.63,
            'price_change': '+2.35%',
            'volume': 1256789,
            'market_cap': '约20亿元',
            'trend': '上升趋势',
            'technical_indicators': {
                'ma5': 62.45,
                'ma10': 60.12,
                'rsi': 68.5,
                'macd': 'DIFF金叉DEA'
            }
        },
        'fundamentals_analysis': {
            'industry': '船舶制造',
            'main_business': '特种船舶制造与海洋工程装备',
            'financial_highlights': {
                'revenue_growth': '+15.2%',
                'profit_margin': '12.3%',
                'roe': '15.8%',
                'debt_ratio': '35.2%'
            },
            'competitive_advantages': [
                '在特种船舶制造领域具有技术优势',
                '军民融合战略布局',
                '海洋工程装备市场需求增长'
            ]
        },
        'news_analysis': {
            'recent_news': [
                {
                    'title': '江龙船艇获得军用特种船舶订单',
                    'impact': 'positive',
                    'summary': '公司近期获得大额军用特种船舶制造订单，预计对业绩产生积极影响'
                },
                {
                    'title': '海洋经济政策利好船舶制造行业',
                    'impact': 'positive',
                    'summary': '国家海洋经济发展政策为船舶制造企业带来新机遇'
                }
            ],
            'sentiment_score': 0.75,
            'market_sentiment': '积极'
        },
        'risk_analysis': {
            'risk_level': '中等',
            'main_risks': [
                '船舶制造周期较长，资金占用风险',
                '军工订单依赖度较高',
                '原材料价格波动影响'
            ],
            'risk_score': 3.2
        },
        'investment_advice': {
            'recommendation': '谨慎买入',
            'target_price': 68.00,
            'confidence_level': 0.72,
            'investment_reasoning': [
                '公司在特种船舶制造领域具有竞争优势',
                '受益于海洋经济和军民融合政策',
                '近期获得重要订单，业绩预期向好',
                '但需关注行业周期性和资金风险'
            ],
            'position_suggestion': '建议分批建仓，控制仓位在5-8%'
        },
        'technical_analysis': {
            'chart_pattern': '上升三角形',
            'support_levels': [60.0, 62.5],
            'resistance_levels': [66.0, 68.5],
            'trend_direction': '短期看涨',
            'volume_analysis': '放量上涨，资金流入积极'
        },
        'summary': {
            'overall_score': 7.2,
            'strengths': [
                '技术优势明显',
                '政策环境利好',
                '订单增长稳定'
            ],
            'weaknesses': [
                '行业周期性强',
                '资金需求大',
                '市场竞争加剧'
            ],
            'conclusion': '江龙船艇作为特种船舶制造企业，在当前政策环境下具备良好发展前景。建议投资者关注其订单执行情况和现金流状况，适度参与。'
        }
    }
    
    # 保存分析数据
    success = cache.save_analysis('920005', sample_analysis, today)
    
    if success:
        logger.info("✅ 920005江龙船艇分析数据已缓存")
        
        # 也创建一个昨天的数据作为历史记录
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        historical_analysis = sample_analysis.copy()
        historical_analysis['analysis_date'] = yesterday
        historical_analysis['market_analysis']['current_price'] = 63.15
        historical_analysis['market_analysis']['price_change'] = '+1.85%'
        
        cache.save_analysis('920005', historical_analysis, yesterday)
        logger.info("✅ 920005历史分析数据已缓存")
    else:
        logger.error("❌ 920005分析数据缓存失败")

def main():
    """主函数"""
    logger.info("🚀 开始缓存现有分析结果...")
    
    # 缓存现有文件
    cache_existing_progress_files()
    
    # 创建920005示例数据
    create_920005_sample_data()
    
    # 显示缓存统计
    cache = get_global_cache()
    stats = cache.get_cache_stats()
    
    logger.info("📊 缓存统计:")
    logger.info(f"   总文件数: {stats.get('total_files', 0)}")
    logger.info(f"   总大小: {stats.get('total_size_mb', 0)} MB")
    logger.info(f"   股票数量: {stats.get('symbol_count', 0)}")
    logger.info(f"   缓存目录: {stats.get('cache_directory', 'unknown')}")
    
    # 列出所有缓存
    cached_list = cache.list_cached_analyses()
    logger.info(f"📋 缓存列表 ({len(cached_list)}个):")
    for item in cached_list[:10]:  # 只显示前10个
        logger.info(f"   {item['symbol']} - {item['date']}")
    
    logger.info("✅ 缓存任务完成！")

if __name__ == "__main__":
    main()