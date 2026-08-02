"""
京东云合作版配置

通过 JDYUN_MODE=true 环境变量启用京东云合作版模式。
所有 LLM 和数据源配置从京东云平台注入的环境变量读取：
- OPENAI_API_BASE: 京东云模型服务地址
- OPENAI_API_KEY: 京东云 API Key
- OPENAI_MODEL: 默认对话模型
- EMBEDDING_MODEL: Embedding 模型
- TUSHARE_TOKEN: Tushare 数据源 Token
"""

import os
import logging
from typing import Dict

logger = logging.getLogger(__name__)

# 京东云预置的对话模型列表（均可用作 quick_model 或 deep_model）
# 🔥 支持通过 OPENAI_MODEL 环境变量覆盖（逗号分隔多个模型，第一个为默认模型）
JDYUN_DEFAULT_CHAT_MODELS = [
    "GLM-5",
    "GLM-5.1",
    "GLM-5.2",
    "DeepSeek-V4-Flash",
]

# 默认 Embedding 模型
JDYUN_DEFAULT_EMBEDDING_MODEL = "Qwen3-Embedding-8B"

# Qwen3-Embedding-8B 输出维度
# 🔥 京东云本地模型只支持 [64, 128, 256, 512, 768, 1024, 1536, 2048] 维度
# 为确保兼容性，统一使用 1024 维
JDYUN_EMBEDDING_DIMS = 1024

# 京东云 Provider 名称
JDYUN_PROVIDER_NAME = "jdyun"


def is_jdyun_mode() -> bool:
    """检测是否启用京东云合作版模式"""
    return os.getenv("JDYUN_MODE", "").strip().lower() in ("true", "1", "yes")


def get_jdyun_api_base() -> str:
    """获取京东云模型服务地址"""
    return os.getenv("OPENAI_API_BASE", "").strip()


def get_jdyun_api_key() -> str:
    """获取京东云 API Key"""
    return os.getenv("OPENAI_API_KEY", "").strip()


def get_jdyun_chat_models() -> list:
    """获取京东云对话模型列表

    从 OPENAI_MODEL 环境变量解析（逗号分隔多个模型，第一个为默认模型），
    未设置时回退到默认列表。
    """
    raw = os.getenv("OPENAI_MODEL", "").strip()
    if raw:
        models = [m.strip() for m in raw.split(",") if m.strip()]
        if models:
            return models
    return list(JDYUN_DEFAULT_CHAT_MODELS)


def get_jdyun_default_model() -> str:
    """获取默认对话模型（OPENAI_MODEL 列表中的第一个）"""
    models = get_jdyun_chat_models()
    return models[0] if models else JDYUN_DEFAULT_CHAT_MODELS[0]


def get_jdyun_embedding_model() -> str:
    """获取 Embedding 模型"""
    model = os.getenv("EMBEDDING_MODEL", "").strip()
    return model if model else JDYUN_DEFAULT_EMBEDDING_MODEL


def get_jdyun_embedding_api_base() -> str:
    """获取 Embedding 服务地址（留空则使用对话模型服务地址）"""
    base = os.getenv("EMBEDDING_API_BASE", "").strip()
    return base if base else get_jdyun_api_base()


def get_jdyun_embedding_api_key() -> str:
    """获取 Embedding API Key（留空则使用对话模型 API Key）"""
    key = os.getenv("EMBEDDING_API_KEY", "").strip()
    return key if key else get_jdyun_api_key()


def get_jdyun_tushare_token() -> str:
    """获取 Tushare Token"""
    return os.getenv("TUSHARE_TOKEN", "").strip()


def is_jdyun_model(model_name: str) -> bool:
    """判断模型是否属于京东云预置模型"""
    return (model_name or "").strip() in get_jdyun_chat_models()


def get_jdyun_status() -> dict:
    """获取京东云配置状态（不含敏感信息）"""
    basic_auth_users = get_jdyun_basic_auth_users()
    return {
        "jdyun_mode": is_jdyun_mode(),
        "api_base": get_jdyun_api_base(),
        "api_key_configured": bool(get_jdyun_api_key()),
        "current_model": get_jdyun_default_model(),
        "available_models": get_jdyun_chat_models(),
        "embedding_model": get_jdyun_embedding_model(),
        "embedding_dims": JDYUN_EMBEDDING_DIMS,
        "tushare_token_configured": bool(get_jdyun_tushare_token()),
        "akshare_available": True,  # AKShare 是开源免费数据源，始终可用
        # Basic Auth 白名单状态（仅返回计数，不含密码）
        "basic_auth_enabled": bool(basic_auth_users),
        "basic_auth_users_count": len(basic_auth_users),
    }


# ============================================================================
# LLM 限速配置（应对京东云 API 限速）
# ============================================================================

def get_jdyun_llm_max_retries() -> int:
    """获取 LLM 调用最大重试次数（京东云模式默认 8，应对 429 限速）"""
    return int(os.getenv("JDYUN_LLM_MAX_RETRIES", "8"))


def get_jdyun_llm_max_rpm() -> int:
    """获取 LLM 每分钟最大请求数（用于限速器配置，默认 30）"""
    return int(os.getenv("JDYUN_LLM_MAX_RPM", "30"))


def get_jdyun_batch_max_concurrent() -> int:
    """获取批量分析最大并发数（京东云模式默认 1，避免 LLM 限速）"""
    return int(os.getenv("JDYUN_BATCH_MAX_CONCURRENT", "1"))


def get_jdyun_worker_max_concurrent() -> int:
    """获取 Worker 最大并发任务数（京东云模式默认 1，避免 LLM 限速）"""
    return int(os.getenv("JDYUN_WORKER_MAX_CONCURRENT", "1"))


def get_jdyun_stock_interval_seconds() -> int:
    """获取定时分析股票间的间隔秒数（京东云模式默认 10 秒）"""
    return int(os.getenv("JDYUN_STOCK_INTERVAL_SECONDS", "10"))


def get_llm_max_retries(default: int = 2) -> int:
    """
    获取 LLM 最大重试次数（兼容京东云和非京东云模式）

    Args:
        default: 非京东云模式下的默认重试次数（默认 2）

    Returns:
        京东云模式返回 get_jdyun_llm_max_retries()，否则返回 default
    """
    if is_jdyun_mode():
        return get_jdyun_llm_max_retries()
    return default


# ============================================================================
# Basic Auth 白名单配置（京东云网关代理场景）
# ============================================================================
# 语义说明：
#   - Basic Auth 的 username 是京东云用户的唯一标识（如 jcloud-ugidvcp）
#   - Basic Auth 的 password 字段是京东云平台生成的「访问令牌」
#   - 访问令牌与用户登录密码完全解耦
#
# 两种配置模式：
#   1. 严格模式（token 固定不变）: JDYUN_BASIC_AUTH_USERS="jcloud-ugidvcp:8437F13D..."
#      → username + token 都必须匹配
#   2. 通配符模式（token 可变）:   JDYUN_BASIC_AUTH_USERS="jcloud-ugidvcp:*"
#      → 只校验 username，token 可任意变化（适用于京东云动态签发 token 的场景）
#
# 通配符模式安全性：
#   - 在"一用户一容器"架构下，容器端口仅对京东云网关暴露，不直接对外
#   - 京东云网关侧已对用户做过认证，到达容器的请求都是可信的
#   - 容器只需识别"是哪个用户"即可，不需要二次校验 token
# ============================================================================

# 通配符，表示不校验 token（只校验 username）
JDYUN_TOKEN_WILDCARD = "*"


def get_jdyun_basic_auth_users() -> Dict[str, str]:
    """
    解析京东云 Basic Auth 白名单（用户名 → 访问令牌）

    环境变量格式: JDYUN_BASIC_AUTH_USERS=user1:token1,user2:token2
    - 多个账户用英文逗号分隔（一用户一容器场景下通常只有一条）
    - 用户名和访问令牌用英文冒号分隔
    - 令牌中的冒号用第一个冒号切分（避免歧义）
    - 令牌为 * 时表示通配符模式（只校验 username，不校验 token）

    Returns:
        {"user1": "token1", "user2": "*"} 形式的用户-令牌字典

    安全性:
    - 这里的值是京东云平台生成的访问令牌，不是用户登录密码
    - 令牌以明文存储在 env 中，等同 OPENAI_API_KEY 的处理方式
    - 建议仅在京东云注入的环境使用，不要写入 .env.jdyun 提交到 Git
    - 京东云网关负责 https 加密传输，明文只在容器内可见
    """
    raw = os.getenv("JDYUN_BASIC_AUTH_USERS", "").strip()
    if not raw:
        return {}
    result: Dict[str, str] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry or ":" not in entry:
            logger.warning("⚠️ [京东云 Basic Auth] 跳过格式错误的账户配置项: %s", entry)
            continue
        user, token = entry.split(":", 1)
        user = user.strip()
        token = token.strip()
        if user and token:
            result[user] = token
        else:
            logger.warning("⚠️ [京东云 Basic Auth] 跳过空用户名或令牌的账户: %s", entry)
    if result:
        # 统计通配符模式数量
        wildcard_count = sum(1 for v in result.values() if v == JDYUN_TOKEN_WILDCARD)
        if wildcard_count:
            logger.info(
                "🔐 [京东云 Basic Auth] 已加载 %d 个白名单账户（其中 %d 个为通配符模式，只校验用户名）",
                len(result), wildcard_count,
            )
        else:
            logger.info("🔐 [京东云 Basic Auth] 已加载 %d 个白名单账户（严格模式）", len(result))
    return result


def verify_jdyun_basic_auth(username: str, token: str) -> bool:
    """
    验证京东云 Basic Auth 凭据（用户名 + 访问令牌）

    Args:
        username: 京东云用户唯一标识（如 jcloud-ugidvcp）
        token: 京东云平台为该用户生成的访问令牌（不是登录密码）

    Returns:
        凭据有效返回 True，否则 False

    两种模式:
        - 严格模式: 白名单中令牌为具体值时，username + token 都必须匹配
        - 通配符模式: 白名单中令牌为 * 时，只校验 username（token 可任意变化）

    安全性:
        - 严格模式使用 hmac.compare_digest 做恒定时间比较（避免时序攻击）
        - 用户名不在白名单时直接返回 False，不进行令牌比较
        - 通配符模式适用于京东云网关已认证的场景，容器不直接对外暴露
    """
    import hmac

    white_list = get_jdyun_basic_auth_users()
    expected_token = white_list.get(username, "")
    if not expected_token:
        # username 不在白名单
        return False
    if expected_token == JDYUN_TOKEN_WILDCARD:
        # 通配符模式：只校验 username，不校验 token
        # 适用于京东云动态签发 token、token 定期轮换等场景
        return True
    # 严格模式：username + token 都校验
    return hmac.compare_digest(
        token.encode("utf-8"),
        expected_token.encode("utf-8"),
    )


# ============================================================================
# 京东云网关 IP 白名单（第二道防线）
# ============================================================================
# 分级校验策略下，老用户免令牌校验，存在 username 泄露后被伪造的风险
# IP 白名单确保请求必须来自京东云网关，即使 username 泄露，外部攻击者也无法伪造
#
# 配置方式:
#   JDYUN_GATEWAY_IPS=10.0.0.1,10.0.0.2,172.16.0.0/12
#   - 支持单个 IP 和 CIDR 格式，逗号分隔
#   - 留空则不启用 IP 校验（仅依赖网络隔离）
# ============================================================================

def get_jdyun_gateway_ips() -> list:
    """
    解析京东云网关 IP 白名单。

    环境变量: JDYUN_GATEWAY_IPS=10.0.0.1,172.16.0.0/12
    - 支持单个 IP（10.0.0.1）和 CIDR（172.16.0.0/12）
    - 逗号分隔多个

    Returns:
        IP/CIDR 字符串列表，未配置返回空列表
    """
    raw = os.getenv("JDYUN_GATEWAY_IPS", "").strip()
    if not raw:
        return []
    return [ip.strip() for ip in raw.split(",") if ip.strip()]


def is_from_jdyun_gateway(client_ip: str) -> bool:
    """
    检查请求是否来自京东云网关（IP 白名单校验）。

    Args:
        client_ip: 客户端 IP 地址（从 request.client.host 获取）

    Returns:
        在白名单内返回 True，不在或未配置白名单返回 True（未配置时不拦截）

    安全性:
        - 未配置 JDYUN_GATEWAY_IPS 时不校验（向后兼容）
        - 配置后，非白名单 IP 的请求直接拒绝
        - 支持 CIDR 格式（如 172.16.0.0/12）
    """
    import ipaddress

    gateway_ips = get_jdyun_gateway_ips()
    if not gateway_ips:
        # 未配置 IP 白名单 → 不拦截（向后兼容）
        return True

    if not client_ip:
        return False

    try:
        client_addr = ipaddress.ip_address(client_ip)
        for rule in gateway_ips:
            try:
                if "/" in rule:
                    # CIDR 格式
                    network = ipaddress.ip_network(rule, strict=False)
                    if client_addr in network:
                        return True
                else:
                    # 单个 IP
                    if client_addr == ipaddress.ip_address(rule):
                        return True
            except ValueError:
                logger.warning(f"⚠️ [京东云 IP 白名单] 无效的 IP/CIDR 规则: {rule}")
                continue
        return False
    except ValueError:
        logger.warning(f"⚠️ [京东云 IP 白名单] 无效的客户端 IP: {client_ip}")
        return False
