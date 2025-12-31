"""
简单的交易复盘任务中心集成测试

测试目标：
1. 验证代码结构正确性
2. 验证方法签名正确性
3. 验证导入正确性
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_imports():
    """测试导入是否正确"""
    print("🧪 测试 1: 验证导入...")
    
    try:
        # 测试模型导入
        from app.models.analysis import AnalysisTaskType, AnalysisStatus
        print("   ✅ AnalysisTaskType 导入成功")
        print(f"   ✅ TRADE_REVIEW 任务类型存在: {hasattr(AnalysisTaskType, 'TRADE_REVIEW')}")
        
        # 测试请求模型导入
        from app.models.review import CreateTradeReviewRequest, ReviewType
        print("   ✅ CreateTradeReviewRequest 导入成功")
        
        return True
    except Exception as e:
        print(f"   ❌ 导入失败: {e}")
        return False


def test_service_methods():
    """测试服务方法是否存在"""
    print("\n🧪 测试 2: 验证服务方法...")
    
    try:
        # 检查 UnifiedAnalysisService 是否有新方法
        import inspect
        from app.services import unified_analysis_service
        
        # 获取 UnifiedAnalysisService 类
        service_class = unified_analysis_service.UnifiedAnalysisService
        
        # 检查方法是否存在
        methods = [
            'create_trade_review_task',
            'execute_trade_review',
            '_update_trade_review_task_status'
        ]
        
        for method_name in methods:
            if hasattr(service_class, method_name):
                method = getattr(service_class, method_name)
                sig = inspect.signature(method)
                print(f"   ✅ {method_name} 方法存在")
                print(f"      参数: {list(sig.parameters.keys())}")
            else:
                print(f"   ❌ {method_name} 方法不存在")
                return False
        
        return True
    except Exception as e:
        print(f"   ❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_router_modification():
    """测试路由是否正确修改"""
    print("\n🧪 测试 3: 验证路由修改...")
    
    try:
        # 读取路由文件内容
        router_file = os.path.join(os.path.dirname(__file__), '..', 'app', 'routers', 'review.py')
        
        with open(router_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查关键代码是否存在
        checks = [
            ('use_task_center', '判断是否使用任务中心'),
            ('UnifiedAnalysisService', '导入 UnifiedAnalysisService'),
            ('create_trade_review_task', '调用 create_trade_review_task'),
            ('execute_trade_review', '调用 execute_trade_review'),
            ('asyncio.create_task', '后台任务执行'),
        ]
        
        all_passed = True
        for keyword, description in checks:
            if keyword in content:
                print(f"   ✅ {description}: 找到 '{keyword}'")
            else:
                print(f"   ❌ {description}: 未找到 '{keyword}'")
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"   ❌ 检查失败: {e}")
        return False


def test_documentation():
    """测试文档是否存在"""
    print("\n🧪 测试 4: 验证文档...")
    
    try:
        doc_file = os.path.join(
            os.path.dirname(__file__), 
            '..', 
            'docs', 
            'design', 
            'v2.0', 
            'trade-review-task-center-integration.md'
        )
        
        if os.path.exists(doc_file):
            print(f"   ✅ 设计文档存在: {doc_file}")
            
            # 检查文档内容
            with open(doc_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'UnifiedAnalysisService' in content:
                print("   ✅ 文档包含 UnifiedAnalysisService 说明")
            if 'create_trade_review_task' in content:
                print("   ✅ 文档包含 create_trade_review_task 说明")
            if 'execute_trade_review' in content:
                print("   ✅ 文档包含 execute_trade_review 说明")
            
            return True
        else:
            print(f"   ❌ 设计文档不存在: {doc_file}")
            return False
    except Exception as e:
        print(f"   ❌ 检查失败: {e}")
        return False


def main():
    """运行所有测试"""
    print("=" * 60)
    print("🚀 交易复盘任务中心集成 - 简单测试")
    print("=" * 60)
    
    results = []
    
    results.append(("导入测试", test_imports()))
    results.append(("服务方法测试", test_service_methods()))
    results.append(("路由修改测试", test_router_modification()))
    results.append(("文档测试", test_documentation()))
    
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{status} - {name}")
    
    all_passed = all(passed for _, passed in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过！")
    else:
        print("⚠️  部分测试失败，请检查上述输出")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

