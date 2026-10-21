import pytest
from src.analytics.metrics import calculate_returns, max_drawdown, volatility

def test_calculate_returns():
    prices = [100.0, 110.0, 104.5]
    rets = calculate_returns(prices)
    assert len(rets) == 2
    assert pytest.approx(rets[0], 0.0001) == 0.10
    assert pytest.approx(rets[1], 0.0001) == -0.05

def test_max_drawdown():
    prices = [100.0, 120.0, 90.0, 110.0]
    mdd = max_drawdown(prices)
    # Pico es 120, caída a 90 es -25% (-0.25)
    assert pytest.approx(mdd, 0.0001) == -0.25

def test_volatility():
    prices = [100.0, 102.0, 101.0, 103.0]
    rets = calculate_returns(prices)
    vol = volatility(rets)
    assert vol > 0.0
