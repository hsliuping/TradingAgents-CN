"""
MCP Server 独立进程启动入口

用法:
    python -m core.mcp                  # 默认 SSE 传输，端口 8001
    python -m core.mcp --transport http  # HTTP 传输
    python -m core.mcp --port 9001       # 自定义端口

Claude Desktop 配置示例 (claude_desktop_config.json):
{
  "mcpServers": {
    "tradingagents-cn": {
      "url": "http://localhost:8001/sse"
    }
  }
}
"""

import argparse
import logging
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
project_root = str(Path(__file__).resolve().parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-24s | %(levelname)-5s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("core.mcp")


def main():
    parser = argparse.ArgumentParser(description="TradingAgents-CN MCP Server")
    parser.add_argument(
        "--transport",
        choices=["sse", "http", "stdio"],
        default="sse",
        help="传输协议 (默认: sse)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="监听端口 (默认: 8001)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="监听地址 (默认: 0.0.0.0)",
    )
    args = parser.parse_args()

    # 加载 .env 环境变量
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    logger.info("=" * 60)
    logger.info("🚀 TradingAgents-CN MCP Server 启动中...")
    logger.info(f"   传输协议: {args.transport}")
    if args.transport != "stdio":
        logger.info(f"   监听地址: {args.host}:{args.port}")
    logger.info("=" * 60)

    from core.mcp.server import mcp

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

