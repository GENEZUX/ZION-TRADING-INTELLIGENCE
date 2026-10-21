"""Motor de Backtesting determinista para ZION Trading Intelligence."""
import math

def run_sma_crossover(prices: list[float], initial_capital: float = 10000.0, short_window: int = 5, long_window: int = 20) -> dict:
    """Simula una estrategia de cruce de medias móviles (SMA Crossover)."""
    if len(prices) < long_window:
        return {
            "initial_capital": initial_capital,
            "final_capital": initial_capital,
            "return_pct": 0.0,
            "trades": 0,
            "win_rate": 0.0
        }

    cash = initial_capital
    position = 0.0
    entry_price = 0.0
    trades = 0
    wins = 0

    for i in range(long_window, len(prices)):
        window_short = prices[i - short_window : i]
        window_long = prices[i - long_window : i]
        
        sma_s = sum(window_short) / short_window
        sma_l = sum(window_long) / long_window
        current_price = prices[i]

        # Señal de compra (Golden Cross)
        if sma_s > sma_l and position == 0.0:
            position = cash / current_price
            cash = 0.0
            entry_price = current_price
            trades += 1

        # Señal de venta (Death Cross)
        elif sma_s < sma_l and position > 0.0:
            cash = position * current_price
            if current_price > entry_price:
                wins += 1
            position = 0.0

    # Liquidar posición final si queda abierta
    final_value = cash + (position * prices[-1] if position > 0.0 else 0.0)
    return_pct = (final_value - initial_capital) / initial_capital
    win_rate = (wins / trades) if trades > 0 else 0.0

    return {
        "initial_capital": initial_capital,
        "final_capital": final_value,
        "return_pct": return_pct,
        "trades": trades,
        "win_rate": win_rate
    }
