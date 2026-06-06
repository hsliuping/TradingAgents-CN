"""纯函数技术指标:输入 close 序列(及 high/low),输出与输入等长、前缀不足处为 None。"""
from typing import List, Optional, Dict


def ma(closes: List[float], window: int) -> List[Optional[float]]:
    out: List[Optional[float]] = []
    for i in range(len(closes)):
        if i + 1 < window:
            out.append(None)
        else:
            out.append(sum(closes[i + 1 - window:i + 1]) / window)
    return out


def _ema(values: List[float], span: int) -> List[float]:
    k = 2 / (span + 1)
    out: List[float] = []
    prev = values[0]
    for i, v in enumerate(values):
        prev = v if i == 0 else v * k + prev * (1 - k)
        out.append(prev)
    return out


def rsi(closes: List[float], window: int) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(closes)
    if len(closes) <= window:
        return out
    gains, losses = [], []
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))
    avg_g = sum(gains[:window]) / window
    avg_l = sum(losses[:window]) / window
    for i in range(window, len(closes)):
        if i > window:
            avg_g = (avg_g * (window - 1) + gains[i - 1]) / window
            avg_l = (avg_l * (window - 1) + losses[i - 1]) / window
        rs = float("inf") if avg_l == 0 else avg_g / avg_l
        out[i] = 100.0 if avg_l == 0 else 100 - 100 / (1 + rs)
    return out


def macd(closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, List[float]]:
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    dif = [f - s for f, s in zip(ema_fast, ema_slow)]
    dea = _ema(dif, signal)
    hist = [(d - e) * 2 for d, e in zip(dif, dea)]
    return {"dif": dif, "dea": dea, "hist": hist}


def boll(closes: List[float], window: int = 20, k: float = 2.0) -> Dict[str, List[Optional[float]]]:
    mid = ma(closes, window)
    upper: List[Optional[float]] = []
    lower: List[Optional[float]] = []
    for i in range(len(closes)):
        if i + 1 < window:
            upper.append(None)
            lower.append(None)
        else:
            seg = closes[i + 1 - window:i + 1]
            m = mid[i]
            var = sum((x - m) ** 2 for x in seg) / window
            sd = var ** 0.5
            upper.append(m + k * sd)
            lower.append(m - k * sd)
    return {"mid": mid, "upper": upper, "lower": lower}
