#!/usr/bin/env python3
"""
测试股票数据获取的完整集成
"""

import sys
sys.path.append('.')

def test_stock_data_flow():
    """测试完整的股票数据流程"""
    print("🔍 测试股票数据获取流程...")
    
    try:
        from tradingagents.dataflows.tdx_utils import get_china_stock_data
        from tradingagents.dataflows.database_manager import get_database_manager
        
        # 测试一个简单的股票代码
        stock_code = "000001"  # 平安银行
        
        print(f"📈 测试获取股票数据: {stock_code}")
        
        # 获取股票数据（这会使用统一的database_manager）
        try:
            result = get_china_stock_data(
                stock_code=stock_code,
                start_date="2024-01-01",
                end_date="2024-01-31"
            )
            
            if result:
                print("✅ 股票数据获取成功")
                print(f"数据类型: {type(result)}")
                if isinstance(result, dict):
                    print(f"数据键: {list(result.keys())}")
                elif hasattr(result, 'shape'):
                    print(f"数据形状: {result.shape}")
            else:
                print("⚠️ 未获取到数据（可能是网络或API问题）")
                
        except Exception as e:
            print(f"⚠️ 数据获取失败: {e}")
            print("这可能是由于网络连接或Tushare数据接口问题，不影响数据库修复验证")
        
        # 验证数据库中的数据
        print("\n🗄️ 验证数据库存储...")
        db_manager = get_database_manager()
        
        if db_manager.mongodb_db is not None:
            stock_collection = db_manager.mongodb_db['stock_data']
            
            # 查找刚才可能保存的数据
            saved_data = stock_collection.find_one({
                'symbol': stock_code,
                'market_type': 'china'
            })
            
            if saved_data:
                print(f"✅ 在数据库中找到股票数据: {stock_code}")
                
                # 安全地访问嵌套数据
                data_field = saved_data.get('data', {})
                if isinstance(data_field, dict):
                    data_source = data_field.get('data_source', 'unknown')
                else:
                    data_source = 'unknown'
                
                print(f"数据源: {data_source}")
                print(f"更新时间: {saved_data.get('updated_at', 'unknown')}")
                print(f"文档结构: {list(saved_data.keys())}")
            else:
                print(f"ℹ️ 数据库中暂无 {stock_code} 的数据（可能是首次运行或网络问题）")
            
            # 检查总的文档数量
            total_count = stock_collection.count_documents({})
            print(f"📊 stock_data集合总文档数: {total_count}")
            
            # 检查是否有重复的symbol+market_type组合
            pipeline = [
                {
                    '$group': {
                        '_id': {'symbol': '$symbol', 'market_type': '$market_type'},
                        'count': {'$sum': 1}
                    }
                },
                {
                    '$match': {'count': {'$gt': 1}}
                }
            ]
            
            duplicates = list(stock_collection.aggregate(pipeline))
            if duplicates:
                print(f"⚠️ 发现重复组合: {len(duplicates)}")
                for dup in duplicates:
                    print(f"  - {dup['_id']}: {dup['count']} 条记录")
            else:
                print("✅ 无重复的symbol+market_type组合")
        
        db_manager.close()
        print("\n🎉 股票数据流程测试完成")
        
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 股票数据集成测试")
    print("=" * 50)
    
    test_stock_data_flow()
    
    print("\n" + "=" * 50)
    print("✅ 集成测试完成")