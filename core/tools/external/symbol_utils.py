"""
A 股股票代码标准化工具

供代码生成器在 Prompt 中引用，使生成的 Skill 支持多种输入格式。
生成的代码运行在沙箱中，不能 import core，因此需将逻辑内联到生成代码中。
"""


def normalize_a_share_symbol(symbol: str) -> str:
    """
    将多种格式的 A 股代码统一为 6 位数字代码。

    支持的输入格式：
    - 600519（纯数字）
    - SH600519、SZ000001、BJ830001、BJ920985（交易所前缀）
    - 600519.SH、000001.SZ、830001.BJ、920985.BJ（交易所后缀，920 为北交所 2025-10 起统一号段）

    Args:
        symbol: 用户输入的股票代码

    Returns:
        6 位数字代码，如 "600519"、"000001"
    """
    if not symbol:
        return ""
    s = str(symbol).strip().upper()
    # 移除 SH/SZ/SS/BJ 前缀
    for prefix in ("SH", "SZ", "SS", "BJ"):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    # 移除 .SH/.SZ/.SS/.BJ 后缀
    for suffix in (".SH", ".SZ", ".SS", ".BJ"):
        if s.endswith(suffix):
            s = s[:-len(suffix)]
            break
    # 只保留数字
    digits = "".join(c for c in s if c.isdigit())
    if not digits:
        return ""
    # 保持 6 位（A 股标准），不足则补齐前导零，超过取后 6 位
    return digits.zfill(6)[-6:] if len(digits) <= 6 else digits[-6:]


# 内联代码片段（供 Prompt 注入，LLM 生成时使用）
# 生成的 Skill 不能 import core，因此需将逻辑复制到函数体内
SYMBOL_NORMALIZE_INLINE = '''
def _normalize_a_share_symbol(symbol: str) -> str:
    """将多种格式的 A 股代码统一为 6 位数字。支持: 600519, SH600519, 600519.SH, 830001.BJ, 920985.BJ 等"""
    if not symbol:
        return ""
    s = str(symbol).strip().upper()
    for prefix in ("SH", "SZ", "SS", "BJ"):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    for suffix in (".SH", ".SZ", ".SS", ".BJ"):
        if s.endswith(suffix):
            s = s[:-len(suffix)]
            break
    digits = "".join(c for c in s if c.isdigit())
    if not digits:
        return ""
    return digits[-6:].zfill(6) if len(digits) <= 6 else digits[-6:]
'''
