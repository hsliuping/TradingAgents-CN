#!/usr/bin/env python3
"""
快速数据服务器测试
使用多线程并行测试服务器连接
"""

import socket
import threading
import time
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

def test_socket_connection(server_info, timeout=3):
    """测试socket连接"""
    ip = server_info['ip']
    port = server_info['port']
    name = server_info.get('name', f'{ip}:{port}')
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        
        if result == 0:
            return {'server': server_info, 'status': 'success', 'message': 'Socket连接成功'}
        else:
            return {'server': server_info, 'status': 'failed', 'message': f'Socket连接失败: {result}'}
            
    except Exception as e:
        return {'server': server_info, 'status': 'error', 'message': f'连接异常: {str(e)}'}

def test_tdx_api_connection(server_info, timeout=5):
    """测试Tushare数据接口连接"""
    try:
        from pytdx.hq import TdxHq_API
        
        ip = server_info['ip']
        port = server_info['port']
        
        api = TdxHq_API()
        
        if api.connect(ip, port):
            # 尝试获取简单数据验证连接
            try:
                quotes = api.get_security_quotes([(0, '000001')])
                api.disconnect()
                
                if quotes and len(quotes) > 0:
                    return {'server': server_info, 'status': 'success', 'message': 'Tushare数据接口连接成功，数据获取正常'}
                else:
                    return {'server': server_info, 'status': 'partial', 'message': 'Tushare数据接口连接成功，但数据为空'}
            except Exception as e:
                api.disconnect()
                return {'server': server_info, 'status': 'partial', 'message': f'Tushare数据接口连接成功，但数据获取失败: {str(e)}'}
        else:
            return {'server': server_info, 'status': 'failed', 'message': 'Tushare数据接口连接失败'}
            
    except Exception as e:
        return {'server': server_info, 'status': 'error', 'message': f'Tushare数据接口测试异常: {str(e)}'}

def main():
    """主函数"""
    print("🚀 快速数据服务器测试")
    print("=" * 70)
    
    # 完整服务器列表
    servers = [
        # 2022年新增的优先服务器
        {'ip': '124.71.187.122', 'port': 7709, 'name': '上海双线主站14'},
        {'ip': '119.97.185.59', 'port': 7709, 'name': '武汉电信主站1'},
        {'ip': '47.107.64.168', 'port': 7709, 'name': '深圳双线主站7'},
        {'ip': '124.70.75.113', 'port': 7709, 'name': '北京双线主站4'},
        {'ip': '124.71.9.153', 'port': 7709, 'name': '广州双线主站4'},
        {'ip': '123.60.84.66', 'port': 7709, 'name': '上海双线主站15'},
        {'ip': '120.46.186.223', 'port': 7709, 'name': '北京双线主站5'},
        {'ip': '124.70.22.210', 'port': 7709, 'name': '北京双线主站6'},
        {'ip': '139.9.133.247', 'port': 7709, 'name': '北京双线主站7'},
        {'ip': '116.205.163.254', 'port': 7709, 'name': '广州双线主站5'},
        {'ip': '116.205.171.132', 'port': 7709, 'name': '广州双线主站6'},
        {'ip': '116.205.183.150', 'port': 7709, 'name': '广州双线主站7'},
        
        # 行情主站
        {'ip': '106.120.74.86', 'port': 7711, 'name': '北京行情主站1'},
        {'ip': '113.105.73.88', 'port': 7709, 'name': '深圳行情主站'},
        {'ip': '114.80.80.222', 'port': 7711, 'name': '上海行情主站'},
        {'ip': '117.184.140.156', 'port': 7711, 'name': '移动行情主站'},
        {'ip': '218.108.50.178', 'port': 7711, 'name': '杭州行情主站'},
        {'ip': '221.194.181.176', 'port': 7711, 'name': '北京行情主站2'},
        
        # 之前测试成功的服务器
        {'ip': '115.238.56.198', 'port': 7709, 'name': '已知可用1'},
        {'ip': '115.238.90.165', 'port': 7709, 'name': '已知可用2'},
        {'ip': '180.153.18.170', 'port': 7709, 'name': '已知可用3'},
        
        # 其他重要服务器
        {'ip': '106.120.74.86', 'port': 7709, 'name': '北京'},
        {'ip': '114.80.80.222', 'port': 7709, 'name': '上海'},
        {'ip': '117.184.140.156', 'port': 7709, 'name': '移动'},
        {'ip': '119.147.164.60', 'port': 7709, 'name': '广州'},
        {'ip': '121.14.110.194', 'port': 7709, 'name': '深圳'},
        {'ip': '218.108.50.178', 'port': 7709, 'name': '杭州'},
        {'ip': '221.194.181.176', 'port': 7709, 'name': '北京'},
        {'ip': '61.135.142.88', 'port': 7709, 'name': '北京'},
        {'ip': '61.152.249.56', 'port': 7709, 'name': '上海'},
        
        # 域名服务器
        {'ip': 'hq.cjis.cn', 'port': 7709, 'name': '财经信息'},
        {'ip': 'hq1.daton.com.cn', 'port': 7709, 'name': '大通证券'},
        
        # 一些常用服务器
        {'ip': '101.227.73.20', 'port': 7709},
        {'ip': '101.227.77.254', 'port': 7709},
        {'ip': '114.80.63.12', 'port': 7709},
        {'ip': '114.80.63.35', 'port': 7709},
        {'ip': '124.160.88.183', 'port': 7709},
        {'ip': '180.153.18.171', 'port': 7709},
        {'ip': '180.153.39.51', 'port': 7709},
        {'ip': '218.108.47.69', 'port': 7709},
        {'ip': '218.108.98.244', 'port': 7709},
        {'ip': '218.75.126.9', 'port': 7709},
    ]
    
    print(f"📊 开始测试 {len(servers)} 个服务器...")
    print("第一阶段: Socket连接测试 (并行)")
    
    # 第一阶段：并行Socket连接测试
    socket_working = []
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_server = {executor.submit(test_socket_connection, server): server for server in servers}
        
        completed = 0
        for future in as_completed(future_to_server):
            completed += 1
            result = future.result()
            
            if result['status'] == 'success':
                socket_working.append(result['server'])
                name = result['server'].get('name', f"{result['server']['ip']}:{result['server']['port']}")
                print(f"[{completed}/{len(servers)}] ✅ {name}")
            else:
                name = result['server'].get('name', f"{result['server']['ip']}:{result['server']['port']}")
                print(f"[{completed}/{len(servers)}] ❌ {name}")
    
    print(f"\n📊 Socket测试结果: {len(socket_working)}/{len(servers)} 服务器可连接")
    
    if socket_working:
        print(f"\n第二阶段: Tushare数据接口测试 (前{min(10, len(socket_working))}个)")
        
        # 第二阶段：测试前10个Socket连接成功的服务器的Tushare数据接口
        api_working = []
        test_servers = socket_working[:10]  # 只测试前10个以节省时间
        
        for i, server in enumerate(test_servers, 1):
            name = server.get('name', f"{server['ip']}:{server['port']}")
            print(f"[{i}/{len(test_servers)}] 测试Tushare数据接口: {name}...")
            
            result = test_tdx_api_connection(server)
            
            if result['status'] == 'success':
                api_working.append(server)
                print(f"  ✅ {result['message']}")
            elif result['status'] == 'partial':
                api_working.append(server)  # 连接成功但数据有问题也算可用
                print(f"  ⚠️ {result['message']}")
            else:
                print(f"  ❌ {result['message']}")
        
        print(f"\n📊 最终结果:")
        print(f"  Socket可连接: {len(socket_working)} 个")
        print(f"  Tushare数据接口可用: {len(api_working)} 个")
        
        if api_working:
            # 保存可用服务器配置
            config_data = {
                'working_servers': api_working,
                'socket_working_servers': socket_working,
                'test_time': datetime.now().isoformat(),
                'total_tested': len(servers),
                'socket_working_count': len(socket_working),
                'api_working_count': len(api_working)
            }
            
            with open('tdx_servers_config.json', 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            
            print(f"\n✅ 配置已保存到 tdx_servers_config.json")
            
            print(f"\n🎯 推荐使用的服务器:")
            for i, server in enumerate(api_working[:5], 1):  # 显示前5个
                name = server.get('name', f"{server['ip']}:{server['port']}")
                print(f"  {i}. {name}")
            
            print(f"\n💡 使用建议:")
            print(f"  1. 优先使用前3个服务器")
            print(f"  2. 如果连接失败，自动切换到备用服务器")
            print(f"  3. 定期重新测试服务器可用性")
            
            return True
        else:
            print(f"\n❌ 没有找到可用的Tushare数据接口服务器")
            return False
    else:
        print(f"\n❌ 没有找到可连接的服务器")
        print(f"💡 可能的原因:")
        print(f"  1. 网络防火墙阻止了连接")
        print(f"  2. 服务器地址已过期")
        print(f"  3. 当前网络环境不支持")
        return False

if __name__ == "__main__":
    main()
