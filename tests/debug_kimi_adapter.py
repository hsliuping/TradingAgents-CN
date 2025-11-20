import asyncio
import os

from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

# 导入我们创建的 Kimi 适配器
from tradingagents.llm_adapters.openai_compatible_base import ChatKimiAI


async def main():
    """
    异步主函数，用于测试 ChatKimiAI。
    """
    print("--- 开始测试 ChatKimiAI (Moonshot AI) ---")

    # 1. 适配器内部会按 "传入参数 -> 环境变量" 的顺序自动加载 MOONSHOT_API_KEY。
    #    我们在这里仅检查环境变量是否存在，以提供更友好的用户提示。
    api_key = os.getenv("MOONSHOT_API_KEY")
    if not api_key:
        print("错误：请确保在 .env 文件中设置了 MOONSHOT_API_KEY")
        return
    print(f"✅ 成功检测到 MOONSHOT_API_KEY 环境变量: sk-...{api_key[-4:]}")

    # 2. 初始化 ChatKimiAI
    # Kimi 的主要模型包括: moonshot-v1-8k, moonshot-v1-32k, moonshot-v1-128k
    model_name = "moonshot-v1-8k"
    try:
        # 传入 api_key=None 会让它自动从环境变量查找
        kimi_llm = ChatKimiAI(
            model=model_name,
            api_key=None,
            temperature=0.3, # Kimi 推荐的 temperature
            timeout=180
        )
        print(f"✅ 成功初始化 ChatKimiAI，使用模型: {model_name}")
    except Exception as e:
        print(f"❌ 初始化 ChatKimiAI 失败: {e}")
        return

    # 3. 准备测试输入
    messages = [
        {"role": "system", "content": "你是 Kimi，由 Moonshot AI 提供的人工智能助手，你更擅长中文和英文的对话。你会为用户提供安全，有帮助，准确的回答。"},
        {"role": "user", "content": "请用一句话介绍一下什么是股票的阿尔法(Alpha)系数？"},
    ]
    print("\n▶️  发送请求到模型...")
    print(f"   输入内容: {messages}")

    # 4. 调用 ainvoke 方法并获取响应
    try:
        response = await kimi_llm.ainvoke(input=messages)

        print("\n✅ 成功收到模型响应！")
        print("--- 模型输出 ---")
        print(response.content)
        print("--------------------")

    except Exception as e:
        print(f"❌ 调用模型失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n--- ChatKimiAI 测试结束 ---")


if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main())
