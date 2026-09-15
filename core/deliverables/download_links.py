# -*- coding: utf-8 -*-
"""交付物文件下载签名链接。

背景：交付物下载路由（/api/assistant/deliverables/{filename}）原本依赖
JWT 请求头 / Session Cookie 鉴权。但 LLM 回复中的下载链接是 <a> 标签，
浏览器直接导航**不会携带 Authorization 头**（前端 JWT 存 localStorage，
只有 XHR/fetch 会带上），用户点击后必然 401"未登录或登录已过期"。

修复采用 presigned URL 模式（与 S3 预签名下载同思路）：
- 工具生成文件时用服务端 JWT_SECRET 派生密钥对「文件名+过期时间」做
  HMAC-SHA256 签名，把 ?exp=&sig= 附加到下载链接；
- 下载路由验证签名：有效且未过期 → 放行（浏览器直接点击场景）；
  无效/缺失 → 回退到原有登录鉴权（API 直接调用场景行为不变）。

签名密钥从 settings.JWT_SECRET 派生（加域分隔符，避免与 JWT 用途混淆），
不新增任何配置项；泄露面与 JWT 一致，不引入额外风险。
"""

import hashlib
import hmac
import time

# 签名有效期：Excel 导出是即时消费场景，24h 足够回看历史会话重新下载
_SIGNATURE_TTL_HOURS = 24

# 域分隔：确保同一密钥派生出的签名密钥与 JWT 签名密钥不同
_DOMAIN_SEP = b":deliverable-download-v1"


def _signing_key() -> bytes:
    from app.core.config import settings

    return f"{settings.JWT_SECRET}".encode("utf-8") + _DOMAIN_SEP


def _compute_sig(filename: str, exp: int) -> str:
    msg = f"{filename}:{exp}".encode("utf-8")
    return hmac.new(_signing_key(), msg, hashlib.sha256).hexdigest()[:32]


def sign_deliverable_query(filename: str, ttl_hours: int = _SIGNATURE_TTL_HOURS) -> str:
    """为交付物文件名生成签名查询串（exp + sig），附加在下载链接后。"""
    exp = int(time.time()) + int(ttl_hours) * 3600
    sig = _compute_sig(filename, exp)
    return f"exp={exp}&sig={sig}"


def verify_deliverable_signature(filename: str, exp, sig) -> bool:
    """校验签名查询参数：缺失/过期/不匹配一律 False。"""
    if exp is None or not sig:
        return False
    try:
        exp_int = int(exp)
    except (TypeError, ValueError):
        return False
    if exp_int < int(time.time()):
        return False
    expected = _compute_sig(filename, exp_int)
    return hmac.compare_digest(expected, str(sig))
