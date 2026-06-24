#!/usr/bin/env python3
"""
金融数据自然语言取数脚本
通过自然语言查询金融数据

用法:
    python fetch_data.py "同花顺收盘价"
"""

import sys
import json
from pathlib import Path
import urllib.parse
import urllib.request
import urllib.error

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

DEFAULT_BASE_URL = "https://repilot.51ifind.com/"
SKILL_CODE = "nlp_finance_query"
CONFIG_DIR = Path.home() / ".config" / "ifind-repilot"
CONFIG_FILE = CONFIG_DIR / "config.json"


def get_config():
    """读取配置文件"""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"错误: 配置文件 {CONFIG_FILE} 格式无效，请检查 JSON 格式是否正确", file=sys.stderr)
        return {}


def get_base_url():
    """获取 base URL"""
    config = get_config()
    return config.get("base_url", DEFAULT_BASE_URL).rstrip("/")


def get_token():
    """获取认证 token"""
    config = get_config()
    token = config.get("auth_token")
    if not token:
        raise ValueError(f"请先配置 auth_token，参考 {CONFIG_FILE}")
    return token


def fetch_data(query: str) -> dict:
    """
    查询金融数据

    Args:
        query: 查询问句

    Returns:
        API 返回的 JSON 数据

    Raises:
        ValueError: 参数无效或认证失败
        RuntimeError: API 调用失败
    """
    if not query or not query.strip():
        raise ValueError("query 参数不能为空")

    token = get_token()
    base_url = get_base_url()

    params = {"query": query, "skillCode": SKILL_CODE}
    query_string = urllib.parse.urlencode(params)
    url = f"{base_url}/research_pilot_service/openapi/skills/v1/finance/query?{query_string}"

    request = urllib.request.Request(url)
    request.add_header("Authorization", token)
    request.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API HTTP 错误: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"网络错误: {e.reason}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"响应 JSON 解析失败: {e}")

    if result.get("code") != 1:
        error_msg = result.get("msg", "未知错误")
        sub_msg = result.get("subMsg") or result.get("sub_msg", "")
        raise RuntimeError(f"API 返回失败: {error_msg} {sub_msg}".strip())

    return result


def check_token():
    """检查 token 配置状态"""
    config = get_config()

    print("Token 检查:")
    print("-" * 40)

    if config.get("auth_token"):
        print("√ auth_token 已配置")
        return True
    else:
        print("× auth_token 未配置")
        print(f"\n请运行: python fetch_data.py --set-token <your_token>")
        print(f"或手动创建 {CONFIG_FILE}:")
        print(f'  mkdir -p {CONFIG_DIR}')
        print(f'  echo \'{{"auth_token": "your_token_here"}}\' > {CONFIG_FILE}')
        return False


def set_config(key: str, value: str):
    """设置配置项"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    config = get_config()
    config[key] = value

    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

    print(f"已保存到 {CONFIG_FILE}")
    return True


def main():
    if len(sys.argv) < 2:
        print("用法: python fetch_data.py <查询问句>", file=sys.stderr)
        print("      python fetch_data.py --check-token", file=sys.stderr)
        print("      python fetch_data.py --set-token <token>", file=sys.stderr)
        print("      python fetch_data.py --set-url <url>", file=sys.stderr)
        sys.exit(1)

    if sys.argv[1] == "--check-token":
        check_token()
        sys.exit(0)

    if sys.argv[1] == "--set-token":
        if len(sys.argv) < 3:
            print("错误: 请提供 token 值", file=sys.stderr)
            print("用法: python fetch_data.py --set-token <token>", file=sys.stderr)
            sys.exit(1)
        set_config("auth_token", sys.argv[2])
        sys.exit(0)

    if sys.argv[1] == "--set-url":
        if len(sys.argv) < 3:
            print("错误: 请提供 url 值", file=sys.stderr)
            print("用法: python fetch_data.py --set-url <url>", file=sys.stderr)
            sys.exit(1)
        set_config("base_url", sys.argv[2])
        sys.exit(0)

    query = " ".join(sys.argv[1:])

    try:
        result = fetch_data(query)
        data = result.get("data", "")
        if isinstance(data, str):
            print(data)
        else:
            print(json.dumps(data, ensure_ascii=False, indent=2))
    except (ValueError, RuntimeError) as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()