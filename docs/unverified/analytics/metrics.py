"""Módulo de métricas financieras y cuantitativas para ZION."""
import math

def calculate_returns(prices: list[float]) -> list[float]:
    """Calcula retornos logarítmicos o simples a partir de una serie de precios de cierre."""
    if len(prices) < 2:
        return []
    returns = []
    for i in range(1, len(prices)):
        prev = prices[i - 1]
        curr = prices[i]
        if prev > 0:
            returns.append((curr - prev) / prev)
        else:
            returns.append(0.0)
    return returns

def max_drawdown(prices: list[float]) -> float:
    """Calcula el Maximum Drawdown (MDD) de una serie de precios."""
    if not prices:
        return 0.0
    peak = prices[0]
    max_dd = 0.0
    for price in prices:
        if price > peak:
            peak = price
        if peak > 0:
            dd = (price - peak) / peak
            if dd < max_dd:
                max_dd = dd
    return float(max_dd)

def volatility(returns: list[float]) -> float:
    """Calcula la volatilidad (desviación estándar) de los retornos."""
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return float(math.sqrt(variance))
