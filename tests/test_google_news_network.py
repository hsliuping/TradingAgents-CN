#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试网络环境是否可以访问Google News

功能：
1. 测试基础网络连接
2. 测试Google搜索可达性
3. 测试Google News RSS可达性
4. 模拟实际新闻抓取
"""

import sys
import requests
from datetime import datetime, timedelta
from pathlib import Path
import json

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_basic_network():
    """测试1: 基础网络连接"""
    print("\n" + "="*80)
    print("测试1: 基础网络连接")
    print("="*80)
    
    test_urls = [
        ("百度", "https://www.baidu.com"),
        ("Google", "https://www.google.com"),
    ]
    
    results = []
    for name, url in test_urls:
        try:
            response = requests.get(url, timeout=10)
            status = "✅ 可访问" if response.status_code == 200 else f"⚠️ 状态码: {response.status_code}"
            print(f"{name:15} {url:40} {status}")
            results.append({
                "name": name,
                "url": url,
                "accessible": response.status_code == 200,
                "status_code": response.status_code
            })
        except requests.exceptions.Timeout:
            print(f"{name:15} {url:40} ❌ 超时")
            results.append({"name": name, "url": url, "accessible": False, "error": "timeout"})
        except requests.exceptions.ConnectionError as e:
            print(f"{name:15} {url:40} ❌ 连接失败: {str(e)[:50]}")
            results.append({"name": name, "url": url, "accessible": False, "error": "connection_error"})
        except Exception as e:
            print(f"{name:15} {url:40} ❌ 错误: {str(e)[:50]}")
            results.append({"name": name, "url": url, "accessible": False, "error": str(e)[:50]})
    
    return results

def test_google_news_rss():
    """测试2: Google News RSS订阅"""
    print("\n" + "="*80)
    print("测试2: Google News RSS访问")
    print("="*80)
    
    # Google News RSS格式
    keywords = "China policy"
    base_url = "https://news.google.com/rss/search"
    params = {
        'q': keywords,
        'hl': 'en-US',
        'gl': 'US',
        'ceid': 'US:en'
    }
    
    print(f"关键词: {keywords}")
    print(f"RSS URL: {base_url}")
    print(f"参数: {params}")
    print()
    
    try:
        response = requests.get(base_url, params=params, timeout=15)
        print(f"状态码: {response.status_code}")
        print(f"响应长度: {len(response.content)} bytes")
        
        if response.status_code == 200:
            content = response.text
            print(f"✅ RSS获取成功")
            print(f"内容类型: {response.headers.get('Content-Type', 'unknown')}")
            print(f"前500字符:\n{content[:500]}")
            
            # 尝试解析RSS
            if '<?xml' in content:
                print("\n✅ RSS格式正确（包含XML声明）")
                
                # 统计条目数量
                item_count = content.count('<item>')
                print(f"📰 新闻条目数量: {item_count}")
                
                return {
                    "accessible": True,
                    "status_code": 200,
                    "item_count": item_count,
                    "content_length": len(content)
                }
            else:
                print("\n⚠️ 响应不是有效的XML格式")
                return {"accessible": False, "error": "invalid_xml"}
        else:
            print(f"❌ RSS获取失败，状态码: {response.status_code}")
            return {"accessible": False, "status_code": response.status_code}
            
    except requests.exceptions.Timeout:
        print("❌ 请求超时")
        return {"accessible": False, "error": "timeout"}
    except requests.exceptions.ConnectionError as e:
        print(f"❌ 连接失败: {str(e)[:100]}")
        return {"accessible": False, "error": "connection_error"}
    except Exception as e:
        print(f"❌ 错误: {str(e)[:100]}")
        return {"accessible": False, "error": str(e)[:100]}

def test_news_parsing():
    """测试3: 新闻解析"""
    print("\n" + "="*80)
    print("测试3: 模拟新闻解析")
    print("="*80)
    
    try:
        from gnews import GNews
        
        print("使用 GNews 库...")
        gnews = GNews(
            language='en',
            country='US',
            period='7d',
            max_results=5
        )
        
        keywords = "China economy"
        print(f"搜索关键词: {keywords}")
        
        news_list = gnews.get_news(keywords)
        
        print(f"\n✅ 获取到 {len(news_list)} 条新闻")
        
        for i, news in enumerate(news_list[:3], 1):
            print(f"\n{i}. {news.get('title', 'N/A')}")
            print(f"   来源: {news.get('publisher', {}).get('title', 'N/A')}")
            print(f"   时间: {news.get('published date', 'N/A')}")
            print(f"   链接: {news.get('url', 'N/A')[:80]}...")
        
        return {
            "accessible": True,
            "library": "GNews",
            "news_count": len(news_list)
        }
        
    except ImportError:
        print("⚠️ GNews库未安装，尝试直接解析RSS...")
        
        try:
            import feedparser
            
            url = "https://news.google.com/rss/search?q=China+economy&hl=en-US&gl=US&ceid=US:en"
            print(f"RSS URL: {url}")
            
            feed = feedparser.parse(url)
            
            if feed.entries:
                print(f"\n✅ 解析成功，获取到 {len(feed.entries)} 条新闻")
                
                for i, entry in enumerate(feed.entries[:3], 1):
                    print(f"\n{i}. {entry.get('title', 'N/A')}")
                    print(f"   时间: {entry.get('published', 'N/A')}")
                    print(f"   链接: {entry.get('link', 'N/A')[:80]}...")
                
                return {
                    "accessible": True,
                    "library": "feedparser",
                    "news_count": len(feed.entries)
                }
            else:
                print("❌ 未能解析到新闻条目")
                return {"accessible": False, "error": "no_entries"}
                
        except ImportError:
            print("❌ feedparser库也未安装")
            return {"accessible": False, "error": "no_parser_library"}
        except Exception as e:
            print(f"❌ 解析失败: {str(e)}")
            return {"accessible": False, "error": str(e)[:100]}
    
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        return {"accessible": False, "error": str(e)[:100]}

def save_test_results(results):
    """保存测试结果"""
    output_dir = Path("./test_results")
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # JSON格式
    json_file = output_dir / f"google_news_network_test_{timestamp}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump({
            "test_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "results": results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 测试结果已保存: {json_file}")
    
    # TXT格式
    txt_file = output_dir / f"google_news_network_test_{timestamp}.txt"
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("Google News 网络环境测试报告\n")
        f.write("="*80 + "\n\n")
        f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        for key, value in results.items():
            f.write(f"\n{key}:\n")
            f.write(json.dumps(value, ensure_ascii=False, indent=2))
            f.write("\n")
    
    print(f"✅ 文本报告已保存: {txt_file}")
    
    return json_file, txt_file

def main():
    """主测试流程"""
    print("\n" + "="*80)
    print("🌐 Google News 网络环境测试")
    print("="*80)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {}
    
    # 测试1: 基础网络
    results['basic_network'] = test_basic_network()
    
    # 测试2: Google News RSS
    results['google_news_rss'] = test_google_news_rss()
    
    # 测试3: 新闻解析
    results['news_parsing'] = test_news_parsing()
    
    # 保存结果
    json_file, txt_file = save_test_results(results)
    
    # 总结
    print("\n" + "="*80)
    print("📊 测试总结")
    print("="*80)
    
    google_accessible = any(
        r.get('accessible', False) and r.get('name') == 'Google' 
        for r in results.get('basic_network', [])
    )
    rss_accessible = results.get('google_news_rss', {}).get('accessible', False)
    parsing_works = results.get('news_parsing', {}).get('accessible', False)
    
    print(f"Google访问: {'✅ 可达' if google_accessible else '❌ 不可达'}")
    print(f"Google News RSS: {'✅ 可达' if rss_accessible else '❌ 不可达'}")
    print(f"新闻解析: {'✅ 正常' if parsing_works else '❌ 失败'}")
    
    print(f"\n📁 详细结果:")
    print(f"   - JSON: {json_file}")
    print(f"   - TXT:  {txt_file}")
    
    if google_accessible and rss_accessible and parsing_works:
        print("\n✅ 网络环境正常，可以使用Google News")
        return 0
    elif not google_accessible:
        print("\n❌ 无法访问Google，可能需要配置代理或使用其他新闻源")
        return 1
    elif not rss_accessible:
        print("\n❌ 无法访问Google News RSS，请检查网络配置")
        return 1
    else:
        print("\n⚠️ 网络可达但新闻解析失败，可能需要安装依赖库")
        print("   建议: pip install gnews feedparser")
        return 1

if __name__ == "__main__":
    exit(main())
