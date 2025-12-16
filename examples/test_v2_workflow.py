"""
测试v2.0工作流执行

演示如何使用WorkflowEngine执行v2.0 Agent工作流
"""

import logging
import sys
import os
from pathlib import Path

# 设置控制台编码为UTF-8
if sys.platform == 'win32':
    os.system('chcp 65001 > nul')

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.workflow.engine import WorkflowEngine
from core.workflow.templates.v2_stock_analysis_workflow import V2_STOCK_ANALYSIS_WORKFLOW

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def progress_callback(progress: float, message: str, step_name: str = None, **kwargs):
    """进度回调函数"""
    print(f"[{progress:5.1f}%] {message}")
    if step_name:
        print(f"         步骤: {step_name}")


def get_llm_config_from_db():
    """从数据库获取LLM配置"""
    try:
        from pymongo import MongoClient
        from app.core.config import settings

        client = MongoClient(settings.MONGO_URI)
        db = client[settings.MONGO_DB]

        # 获取系统配置中的默认模型
        doc = db.system_configs.find_one({"is_active": True}, sort=[("version", -1)])

        if not doc or "llm_configs" not in doc:
            logger.warning("数据库中没有LLM配置，使用默认配置")
            client.close()
            return {
                "llm_provider": "dashscope",
                "quick_think_llm": "qwen-turbo",
                "deep_think_llm": "qwen-plus",
            }

        llm_configs = doc["llm_configs"]

        # 找到第一个启用的模型作为默认模型
        default_config = None
        for cfg in llm_configs:
            if cfg.get("enabled", True):
                provider = cfg.get("provider", "").lower()
                # 优先选择阿里百炼或 DeepSeek
                if provider in ["dashscope", "deepseek"]:
                    default_config = cfg
                    break

        if not default_config:
            for cfg in llm_configs:
                if cfg.get("enabled", True):
                    default_config = cfg
                    break

        client.close()

        if default_config:
            provider_name = default_config.get("provider", "dashscope")
            model_name = default_config.get("model_name", "qwen-turbo")
            backend_url = default_config.get("api_base") or default_config.get("base_url")
            api_key = default_config.get("api_key", "")

            # 如果数据库没有API Key，尝试从环境变量获取
            if not api_key or api_key.startswith("sk-xxx"):
                env_key_map = {
                    "dashscope": "DASHSCOPE_API_KEY",
                    "openai": "OPENAI_API_KEY",
                    "deepseek": "DEEPSEEK_API_KEY",
                }
                env_key = env_key_map.get(provider_name.lower())
                if env_key:
                    api_key = os.getenv(env_key, "")

            result = {
                "llm_provider": provider_name,
                "quick_think_llm": model_name,
                "deep_think_llm": model_name,
                "backend_url": backend_url,
                "api_key": api_key,
                "quick_temperature": default_config.get("temperature", 0.1),
                "quick_max_tokens": default_config.get("max_tokens", 2000),
                "quick_timeout": default_config.get("timeout", 30),
            }

            logger.info(f"从数据库获取配置: provider={provider_name}, model={model_name}")
            return result

        return {
            "llm_provider": "dashscope",
            "quick_think_llm": "qwen-turbo",
            "deep_think_llm": "qwen-plus",
        }

    except Exception as e:
        logger.warning(f"从数据库获取配置失败: {e}")
        return {
            "llm_provider": "dashscope",
            "quick_think_llm": "qwen-turbo",
            "deep_think_llm": "qwen-plus",
        }


def main():
    """主函数"""
    print("=" * 80)
    print("v2.0 工作流执行测试")
    print("=" * 80)

    # 1. 创建工作流引擎（从数据库获取LLM配置）
    print("\n1. 创建工作流引擎...")

    # 从数据库获取LLM配置
    legacy_config = get_llm_config_from_db()
    print(f"   LLM提供商: {legacy_config.get('llm_provider')}")
    print(f"   快速模型: {legacy_config.get('quick_think_llm')}")
    print(f"   深度模型: {legacy_config.get('deep_think_llm')}")

    engine = WorkflowEngine(legacy_config=legacy_config)
    
    # 2. 加载工作流定义
    print("\n2. 加载工作流定义...")
    engine.load(V2_STOCK_ANALYSIS_WORKFLOW)
    print(f"   工作流ID: {V2_STOCK_ANALYSIS_WORKFLOW.id}")
    print(f"   工作流名称: {V2_STOCK_ANALYSIS_WORKFLOW.name}")
    print(f"   节点数量: {len(V2_STOCK_ANALYSIS_WORKFLOW.nodes)}")
    print(f"   边数量: {len(V2_STOCK_ANALYSIS_WORKFLOW.edges)}")
    
    # 3. 验证工作流
    print("\n3. 验证工作流...")
    validation_result = engine.validate()
    if validation_result.is_valid:
        print("   [OK] 工作流验证通过")
    else:
        print("   [ERROR] 工作流验证失败:")
        for error in validation_result.errors:
            print(f"      - {error}")
        return

    # 4. 编译工作流
    print("\n4. 编译工作流...")
    try:
        engine.compile()
        print("   [OK] 工作流编译成功")
    except Exception as e:
        print(f"   [ERROR] 工作流编译失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 5. 准备输入数据
    print("\n5. 准备输入数据...")
    inputs = {
        # 提供多种参数名以兼容不同的Agent
        "ticker": "000001",  # 平安银行
        "company_of_interest": "000001",  # 兼容旧版Agent
        "analysis_date": "2025-12-15",
        "trade_date": "2025-12-15",  # 兼容旧版Agent
        "end_date": "2025-12-15",  # 兼容旧版Agent
        "market_type": "A股",
    }
    print(f"   股票代码: {inputs['ticker']}")
    print(f"   分析日期: {inputs['analysis_date']}")
    print(f"   市场类型: {inputs['market_type']}")
    
    # 6. 执行工作流
    print("\n6. 执行工作流...")
    print("-" * 80)
    
    try:
        result = engine.execute(
            inputs=inputs,
            progress_callback=progress_callback
        )

        print("-" * 80)
        print("\n[SUCCESS] 工作流执行成功！")

        # 7. 显示结果
        print("\n7. 执行结果:")
        print(f"   结果字段数量: {len(result)}")

        # 显示关键字段
        key_fields = [
            "market_report",
            "fundamentals_report",
            "news_report",
            "social_report",
            "sentiment_report",
            "bull_research",
            "bear_research",
            "investment_plan",
            "risk_assessment",
            "trading_instructions",
        ]

        for field in key_fields:
            if field in result:
                content = result[field]
                if isinstance(content, str):
                    print(f"\n   [REPORT] {field}:")
                    print(f"      长度: {len(content)} 字符")
                    # 显示前200个字符
                    preview = content[:200].replace('\n', ' ')
                    print(f"      预览: {preview}...")

        # 显示所有字段名
        print(f"\n   所有字段: {list(result.keys())}")

    except Exception as e:
        print(f"\n[ERROR] 工作流执行失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    main()

