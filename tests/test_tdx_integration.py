#!/usr/bin/env python3
"""
测试Tushare数据接口集成
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_pytdx_installation():
    """测试pytdx库安装"""
    print("🧪 测试pytdx库安装")
    print("=" * 50)
    
    try:
        import pytdx
        print(f"✅ pytdx库已安装，版本: {pytdx.__version__}")
        return True
    except ImportError:
        print("❌ pytdx库未安装")
        print("💡 安装命令: pip install pytdx")
        return False

def test_tdx_connection():
    """测试通达信连接"""
    print("\n🔗 测试Tushare数据接口连接")
    print("=" * 50)

    try:
        from tradingagents.dataflows.tdx_utils import TongDaXinDataProvider

        provider = TongDaXinDataProvider()
        success = provider.connect()

        if success:
            print("✅ Tushare数据接口连接成功")

            # 测试断开连接
            provider.disconnect()
            print("✅ 连接断开成功")
            return True
        else:
            print("❌ Tushare数据接口连接失败")
            return False

    except Exception as e:
        print(f"❌ 连接测试失败: {e}")
        return False

def test_server_list():
    """测试服务器列表并保存可用服务器"""
    print("\n🌐 测试数据服务器列表")
    print("=" * 50)

    # 完整的数据服务器列表
    servers = [
        # 原始列表
        {'ip': '101.227.73.20', 'port': 7709},
        {'ip': '101.227.77.254', 'port': 7709},
        {'ip': '114.80.63.12', 'port': 7709},
        {'ip': '114.80.63.35', 'port': 7709},
        {'ip': '115.238.56.198', 'port': 7709},
        {'ip': '115.238.90.165', 'port': 7709},
        {'ip': '124.160.88.183', 'port': 7709},
        {'ip': '14.215.128.18', 'port': 7709},
        {'ip': '180.153.18.170', 'port': 7709},
        {'ip': '180.153.18.171', 'port': 7709},
        {'ip': '180.153.39.51', 'port': 7709},
        {'ip': '202.108.253.130', 'port': 7709},
        {'ip': '202.108.253.131', 'port': 7709},
        {'ip': '218.108.47.69', 'port': 7709},
        {'ip': '218.108.98.244', 'port': 7709},
        {'ip': '218.75.126.9', 'port': 7709},
        {'ip': '221.231.141.60', 'port': 7709},
        {'ip': '59.173.18.140', 'port': 7709},
        {'ip': '60.12.136.250', 'port': 7709},
        {'ip': '60.28.23.80', 'port': 7709},

        # 2019年新增
        {'ip': '106.14.95.149', 'port': 7711, 'name': '上海双线资讯主站'},
        {'ip': '112.74.214.43', 'port': 7711, 'name': '深圳双线资讯主站1'},
        {'ip': '113.105.142.162', 'port': 7711, 'name': '东莞电信资讯主站'},
        {'ip': '119.97.185.10', 'port': 7711, 'name': '武汉电信资讯主站2'},
        {'ip': '119.97.185.6', 'port': 7711, 'name': '武汉电信资讯主站1'},
        {'ip': '120.24.0.77', 'port': 7711, 'name': '深圳双线资讯主站2'},
        {'ip': '120.79.212.229', 'port': 7711, 'name': '深圳双线资讯主站3'},
        {'ip': '47.107.75.159', 'port': 7711, 'name': '深圳双线资讯主站4'},
        {'ip': '47.92.127.181', 'port': 7711, 'name': '北京双线资讯主站'},

        # 2022年新增
        {'ip': '124.71.187.122', 'port': 7709, 'name': '上海双线主站14'},
        {'ip': '119.97.185.59', 'port': 7709, 'name': '武汉电信主站1'},
        {'ip': '47.107.64.168', 'port': 7709, 'name': '深圳双线主站7'},
        {'ip': '124.70.75.113', 'port': 7709, 'name': '北京双线主站4'},
        {'ip': '124.71.9.153', 'port': 7709, 'name': '广州双线主站4'},
        {'ip': '123.60.84.66', 'port': 7709, 'name': '上海双线主站15'},
        {'ip': '47.107.228.47', 'port': 7719, 'name': '深圳双线主站8'},
        {'ip': '120.46.186.223', 'port': 7709, 'name': '北京双线主站5'},
        {'ip': '124.70.22.210', 'port': 7709, 'name': '北京双线主站6'},
        {'ip': '139.9.133.247', 'port': 7709, 'name': '北京双线主站7'},
        {'ip': '116.205.163.254', 'port': 7709, 'name': '广州双线主站5'},
        {'ip': '116.205.171.132', 'port': 7709, 'name': '广州双线主站6'},
        {'ip': '116.205.183.150', 'port': 7709, 'name': '广州双线主站7'},

        # 行情主站
        {'ip': '106.120.74.86', 'port': 7711, 'name': '北京行情主站1'},
        {'ip': '113.105.73.88', 'port': 7709, 'name': '深圳行情主站'},
        {'ip': '113.105.73.88', 'port': 7711, 'name': '深圳行情主站'},
        {'ip': '114.80.80.222', 'port': 7711, 'name': '上海行情主站'},
        {'ip': '117.184.140.156', 'port': 7711, 'name': '移动行情主站'},
        {'ip': '119.147.171.206', 'port': 443, 'name': '广州行情主站'},
        {'ip': '119.147.171.206', 'port': 80, 'name': '广州行情主站'},
        {'ip': '218.108.50.178', 'port': 7711, 'name': '杭州行情主站'},
        {'ip': '221.194.181.176', 'port': 7711, 'name': '北京行情主站2'},

        # 原始服务器
        {'ip': '106.120.74.86', 'port': 7709, 'name': '北京'},
        {'ip': '112.95.140.74', 'port': 7709},
        {'ip': '112.95.140.92', 'port': 7709},
        {'ip': '112.95.140.93', 'port': 7709},
        {'ip': '113.05.73.88', 'port': 7709, 'name': '深圳'},
        {'ip': '114.67.61.70', 'port': 7709},
        {'ip': '114.80.149.19', 'port': 7709},
        {'ip': '114.80.149.22', 'port': 7709},
        {'ip': '114.80.149.84', 'port': 7709},
        {'ip': '114.80.80.222', 'port': 7709, 'name': '上海'},
        {'ip': '117.184.140.156', 'port': 7709, 'name': '移动'},
        {'ip': '119.147.164.60', 'port': 7709, 'name': '广州'},
        {'ip': '119.147.171.206', 'port': 7709, 'name': '广州'},
        {'ip': '119.29.51.30', 'port': 7709},
        {'ip': '121.14.104.70', 'port': 7709},
        {'ip': '121.14.104.72', 'port': 7709},
        {'ip': '121.14.110.194', 'port': 7709, 'name': '深圳'},
        {'ip': '121.14.2.7', 'port': 7709},
        {'ip': '123.125.108.23', 'port': 7709},
        {'ip': '123.125.108.24', 'port': 7709},
        {'ip': '180.153.18.17', 'port': 7709},
        {'ip': '218.108.50.178', 'port': 7709, 'name': '杭州'},
        {'ip': '218.9.148.108', 'port': 7709},
        {'ip': '221.194.181.176', 'port': 7709, 'name': '北京'},
        {'ip': '59.173.18.69', 'port': 7709},
        {'ip': '60.191.117.167', 'port': 7709},
        {'ip': '60.28.29.69', 'port': 7709},
        {'ip': '61.135.142.73', 'port': 7709},
        {'ip': '61.135.142.88', 'port': 7709, 'name': '北京'},
        {'ip': '61.152.107.168', 'port': 7721},
        {'ip': '61.152.249.56', 'port': 7709, 'name': '上海'},
        {'ip': '61.153.144.179', 'port': 7709},
        {'ip': '61.153.209.138', 'port': 7709},
        {'ip': '61.153.209.139', 'port': 7709},

        # 域名服务器
        {'ip': 'hq.cjis.cn', 'port': 7709, 'name': '财经信息'},
        {'ip': 'hq1.daton.com.cn', 'port': 7709, 'name': '大通证券'},
        {'ip': 'jstdx.gtjas.com', 'port': 7709, 'name': '国泰君安江苏'},
        {'ip': 'shtdx.gtjas.com', 'port': 7709, 'name': '国泰君安上海'},
        {'ip': 'sztdx.gtjas.com', 'port': 7709, 'name': '国泰君安深圳'},

        # 扩展端口
        {'ip': '113.105.142.162', 'port': 7721},
        {'ip': '23.129.245.199', 'port': 7721},
    ]

    try:
        import socket
        import json
        from pytdx.hq import TdxHq_API

        def test_socket_connection(ip, port, timeout=2):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                result = sock.connect_ex((ip, port))
                sock.close()
                return result == 0
            except:
                return False

        def test_tdx_api(ip, port, timeout=3):
            try:
                api = TdxHq_API()
                result = api.connect(ip, port)
                if result:
                    # 简单测试获取数据
                    quotes = api.get_security_quotes([(0, '000001')])
                    api.disconnect()
                    return quotes is not None and len(quotes) > 0
                return False
            except:
                return False

        working_servers = []
        print(f"开始测试 {len(servers)} 个服务器...")

        # 分批测试，优先测试有名称的服务器
        priority_servers = [s for s in servers if s.get('name')]
        regular_servers = [s for s in servers if not s.get('name')]

        # 测试前20个优先服务器 + 前10个常规服务器
        test_servers = priority_servers[:20] + regular_servers[:10]
        print(f"优先测试 {len(test_servers)} 个服务器（优先级服务器 + 常规服务器）")

        for i, server in enumerate(test_servers, 1):
            ip = server['ip']
            port = server['port']
            name = server.get('name', f'{ip}:{port}')

            print(f"[{i}/{len(test_servers)}] 测试 {name}...")

            if test_socket_connection(ip, port):
                print(f"  ✅ Socket连接成功")
                if test_tdx_api(ip, port):
                    print(f"  ✅ Tushare数据接口测试成功")
                    working_servers.append(server)
                else:
                    print(f"  ⚠️ Tushare数据接口测试失败")
            else:
                print(f"  ❌ Socket连接失败")

        print(f"\n📊 测试结果:")
        print(f"  测试服务器: {len(test_servers)}")
        print(f"  可用服务器: {len(working_servers)}")

        if working_servers:
            # 保存可用服务器到配置文件
            config_data = {
                'working_servers': working_servers,
                'test_time': datetime.now().isoformat(),
                'total_tested': len(test_servers),
                'working_count': len(working_servers)
            }

            with open('tdx_servers_config.json', 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)

            print(f"✅ 可用服务器已保存到 tdx_servers_config.json")

            # 显示可用服务器
            print(f"\n✅ 可用服务器列表:")
            for server in working_servers:
                name = server.get('name', f"{server['ip']}:{server['port']}")
                print(f"  • {name}")

            return True
        else:
            print("❌ 没有找到可用的服务器")
            return False

    except Exception as e:
        print(f"❌ 服务器测试失败: {e}")
        return False

def test_realtime_data():
    """测试实时数据获取"""
    print("\n📊 测试实时数据获取")
    print("=" * 50)
    
    try:
        from tradingagents.dataflows.tdx_utils import TongDaXinDataProvider
        
        provider = TongDaXinDataProvider()
        
        # 测试几个知名股票
        test_stocks = [
            ('000001', '平安银行'),
            ('600519', '贵州茅台'),
            ('000858', '五粮液')
        ]
        
        for code, name in test_stocks:
            print(f"\n📈 测试 {code} ({name}):")
            
            try:
                data = provider.get_real_time_data(code)
                
                if data:
                    print(f"✅ 获取成功")
                    print(f"   股票名称: {data.get('name', 'N/A')}")
                    print(f"   当前价格: ¥{data.get('price', 0):.2f}")
                    print(f"   涨跌幅: {data.get('change_percent', 0):.2f}%")
                    print(f"   成交量: {data.get('volume', 0):,}手")
                else:
                    print(f"⚠️ 未获取到数据")
                    
            except Exception as e:
                print(f"❌ 获取失败: {e}")
        
        provider.disconnect()
        return True
        
    except Exception as e:
        print(f"❌ 实时数据测试失败: {e}")
        return False

def test_historical_data():
    """测试历史数据获取"""
    print("\n📈 测试历史数据获取")
    print("=" * 50)
    
    try:
        from tradingagents.dataflows.tdx_utils import TongDaXinDataProvider
        
        provider = TongDaXinDataProvider()
        
        # 测试获取平安银行最近30天数据
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        print(f"📅 获取000001(平安银行) {start_date} 至 {end_date} 的数据")
        
        df = provider.get_stock_history_data('000001', start_date, end_date)
        
        if not df.empty:
            print(f"✅ 历史数据获取成功")
            print(f"   数据条数: {len(df)}条")
            print(f"   数据列: {list(df.columns)}")
            print(f"   日期范围: {df.index[0]} 至 {df.index[-1]}")
            print(f"   期间涨幅: {((df['Close'].iloc[-1] - df['Close'].iloc[0]) / df['Close'].iloc[0] * 100):.2f}%")
            
            # 显示最近5天数据
            print(f"\n📋 最近5天数据:")
            print(df.tail().to_string())
        else:
            print("⚠️ 未获取到历史数据")
        
        provider.disconnect()
        return not df.empty
        
    except Exception as e:
        print(f"❌ 历史数据测试失败: {e}")
        return False

def test_technical_indicators():
    """测试技术指标计算"""
    print("\n🔍 测试技术指标计算")
    print("=" * 50)
    
    try:
        from tradingagents.dataflows.tdx_utils import TongDaXinDataProvider
        
        provider = TongDaXinDataProvider()
        
        print("📊 计算000001(平安银行)的技术指标")
        
        indicators = provider.get_stock_technical_indicators('000001')
        
        if indicators:
            print("✅ 技术指标计算成功")
            
            for name, value in indicators.items():
                if value is not None:
                    if isinstance(value, float):
                        print(f"   {name}: {value:.4f}")
                    else:
                        print(f"   {name}: {value}")
                else:
                    print(f"   {name}: N/A")
        else:
            print("⚠️ 未计算出技术指标")
        
        provider.disconnect()
        return bool(indicators)
        
    except Exception as e:
        print(f"❌ 技术指标测试失败: {e}")
        return False

def test_market_overview():
    """测试市场概览"""
    print("\n🏛️ 测试市场概览")
    print("=" * 50)
    
    try:
        from tradingagents.dataflows.tdx_utils import TongDaXinDataProvider
        
        provider = TongDaXinDataProvider()
        
        market_data = provider.get_market_overview()
        
        if market_data:
            print("✅ 市场概览获取成功")
            
            for name, data in market_data.items():
                change_symbol = "📈" if data['change'] >= 0 else "📉"
                print(f"   {change_symbol} {name}:")
                print(f"      点位: {data['price']:.2f}")
                print(f"      涨跌: {data['change']:+.2f} ({data['change_percent']:+.2f}%)")
        else:
            print("⚠️ 未获取到市场概览")
        
        provider.disconnect()
        return bool(market_data)
        
    except Exception as e:
        print(f"❌ 市场概览测试失败: {e}")
        return False

def test_integration_functions():
    """测试集成函数"""
    print("\n🔧 测试集成函数")
    print("=" * 50)
    
    try:
        from tradingagents.dataflows.tdx_utils import get_china_stock_data, get_china_market_overview
        
        # 测试股票数据获取函数
        print("📊 测试get_china_stock_data函数")
        
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        result = get_china_stock_data('000001', start_date, end_date)
        
        if "股票数据分析" in result:
            print("✅ 股票数据函数测试成功")
            print(f"   返回内容长度: {len(result)} 字符")
        else:
            print("⚠️ 股票数据函数返回异常")
            print(f"   返回内容: {result[:200]}...")
        
        # 测试市场概览函数
        print("\n🏛️ 测试get_china_market_overview函数")
        
        market_result = get_china_market_overview()
        
        if "中国股市概览" in market_result:
            print("✅ 市场概览函数测试成功")
            print(f"   返回内容长度: {len(market_result)} 字符")
        else:
            print("⚠️ 市场概览函数返回异常")
            print(f"   返回内容: {market_result[:200]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ 集成函数测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🧪 Tushare数据接口集成测试")
    print("=" * 70)
    
    # 运行所有测试
    tests = [
        ("pytdx库安装", test_pytdx_installation),
        ("服务器连接测试", test_server_list),
        ("通达信连接", test_tdx_connection),
        ("实时数据获取", test_realtime_data),
        ("历史数据获取", test_historical_data),
        ("技术指标计算", test_technical_indicators),
        ("市场概览", test_market_overview),
        ("集成函数", test_integration_functions),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name}测试异常: {e}")
            results[test_name] = False
    
    # 显示测试结果总结
    print(f"\n📊 测试结果总结:")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results.items():
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {test_name}: {status}")
        if success:
            passed += 1
    
    print(f"\n🎯 总体结果: {passed}/{total} 测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！Tushare数据接口集成成功")
        print("\n💡 现在可以使用以下功能:")
        print("  • 获取A股实时行情数据")
        print("  • 获取历史K线数据")
        print("  • 计算技术指标")
        print("  • 查看市场概览")
        print("  • 在TradingAgents中使用中国股票分析")
    elif passed >= total * 0.7:
        print("⚠️ 大部分测试通过，基本功能可用")
        print("💡 建议检查失败的测试项目")
    else:
        print("🔴 多项测试失败，需要检查配置")
        print("💡 建议:")
        print("  1. 确认pytdx库已正确安装")
        print("  2. 检查网络连接")
        print("  3. 尝试重新运行测试")
    
    print(f"\n📋 使用说明:")
    print("=" * 50)
    print("1. 在Web界面中可以分析中国股票代码 (如: 000001, 600519)")
    print("2. Tushare数据接口提供实时数据，无需额外API密钥")
    print("3. 支持A股、深股、创业板、科创板等所有板块")
    print("4. 数据包括实时行情、历史K线、技术指标等")

if __name__ == "__main__":
    main()
