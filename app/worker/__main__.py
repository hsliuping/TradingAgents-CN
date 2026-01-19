"""
Worker 模块启动入口
支持使用 python -m app.worker 启动 Worker
"""

import asyncio
import sys
import logging
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.worker.analysis_worker import AnalysisWorker


def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('logs/worker.log', encoding='utf-8')
        ]
    )


async def main():
    """主函数"""
    print("🚀 启动TradingAgents分析Worker...")
    
    # 设置日志
    setup_logging()
    
    # 创建Worker实例
    worker = AnalysisWorker()
    
    try:
        # 启动Worker
        await worker.start()
    except KeyboardInterrupt:
        print("\n⏹️  收到中断信号，正在关闭Worker...")
    except Exception as e:
        print(f"❌ Worker启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("✅ Worker已安全退出")


if __name__ == "__main__":
    # 确保日志目录存在
    Path("logs").mkdir(exist_ok=True)
    
    # 运行Worker
    asyncio.run(main())
