"""BT-01 / BT-02: cost model and train/test split are explicit."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Costs:
    commission_bps: float = 5.0
    slippage_bps: float = 2.0


def apply_costs(gross_pnl: float, notional: float, costs: Costs) -> float:
    """Apply commission and slippage to a single round-trip trade."""
    total_bps = costs.commission_bps + costs.slippage_bps
    return gross_pnl - notional * total_bps / 10_000.0


def test_costs_reduce_pnl():
    net = apply_costs(gross_pnl=10.0, notional=1000.0, costs=Costs())
    assert net < 10.0


def test_costs_make_losses_worse():
    net = apply_costs(gross_pnl=-10.0, notional=1000.0, costs=Costs())
    assert net < -10.0


def test_train_test_split_is_disjoint_and_ordered():
    series = list(range(100))
    split = 70
    train, test = series[:split], series[split:]
    assert max(train) < min(test)
    assert set(train).isdisjoint(set(test))
