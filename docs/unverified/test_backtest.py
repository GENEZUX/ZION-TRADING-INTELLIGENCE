import pytest
from src.backtest.engine import run_sma_crossover

def test_sma_crossover_insufficient_data():
    prices = [100.0] * 10
    res = run_sma_crossover(prices, initial_capital=10000.0, short_window=5, long_window=20)
    assert res["final_capital"] == 10000.0
    assert res["trades"] == 0

def test_sma_crossover_execution():
    # Tendencia alcista clara para gatillar compra
    prices = [10.0 + i * 0.5 for i in range(30)]
    res = run_sma_crossover(prices, initial_capital=10000.0, short_window=5, long_window=20)
    assert res["initial_capital"] == 10000.0
    assert "return_pct" in res
    assert "trades" in res
