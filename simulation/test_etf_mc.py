"""Run from the repo root: python3 -m simulation.test_etf_mc"""
import numpy as np

from simulation.etf_mc import build_events, draw_returns, load_inputs, run_all, run_one
from simulation.etf_tax import apply_tax, vorabpauschale

NO_EVENTS = {"switches": [], "withdrawals": []}
FLAT = {"id": "x", "contributions": "flat_nominal", "returns": "historical"}


def small(**changes):
    inp = load_inputs(n_paths=200)
    inp["years"] = 10
    inp.update(changes)
    return inp


def risk_free(**changes):
    """No randomness, no fees, no tax: results can be worked out by hand."""
    k = len(small()["funds"])
    return small(sigma=np.zeros(k), ter=np.zeros(k), tax_rate=0.0, order_fee=0.0, **changes)


def test_tax_allowance_and_losses():
    one = lambda x: np.array([float(x)])
    tax, allowance, loss = apply_tax(one(1000), one(760), one(0), 0.26375)
    assert abs(tax[0] - 0.26375 * 240) < 1e-9 and allowance[0] == 0
    tax, allowance, loss = apply_tax(one(-500), one(760), one(0), 0.26375)
    assert tax[0] == 0 and loss[0] == 500 and allowance[0] == 760     # a loss is kept for later
    tax, allowance, loss = apply_tax(one(300), one(760), one(500), 0.26375)
    assert tax[0] == 0 and loss[0] == 200 and allowance[0] == 760     # the loss is used first


def test_vorabpauschale_is_capped_by_the_actual_gain():
    v = np.array([10_000.0])
    assert abs(vorabpauschale(v, 1.10, 0.025, 0.7)[0] - 175) < 1e-9   # 70% of 2.5% of 10000
    assert abs(vorabpauschale(v, 1.01, 0.025, 0.7)[0] - 100) < 1e-9   # the gain is smaller
    assert vorabpauschale(v, 0.90, 0.025, 0.7)[0] == 0                # a loss year: nothing


def test_no_risk_matches_compound_growth_by_hand():
    inp = risk_free()
    for name, p in inp["portfolios"].items():
        got = run_one(inp, NO_EVENTS, draw_returns(inp), FLAT, name)["final"][0]
        expected = 0.0
        for w, mu in zip(p["weights"], inp["mu"][p["idx"]]):
            v = inp["start_etf"] * w
            for _ in range(inp["years"] * 12):
                v = (v + inp["monthly_etf"] * w) * (1 + mu) ** (1 / 12)
            expected += v
        assert abs(got - expected) < 0.01, (name, got, expected)


def test_switches_conserve_value_when_there_is_no_tax_or_fees():
    k = len(small()["funds"])
    inp = risk_free(mu=np.full(k, 0.05))
    inp["years"] = 12
    events = build_events(inp)
    assert len(events["switches"]) >= 8
    shocks = draw_returns(inp)
    plain = run_one(inp, NO_EVENTS, shocks, FLAT, "four_etf_thematic")["final"][0]
    moved = run_one(inp, {"switches": events["switches"], "withdrawals": []},
                    shocks, FLAT, "four_etf_thematic")["final"][0]
    assert abs(plain - moved) < 0.01


def test_withdrawal_delivers_the_target_after_tax():
    k = len(small()["funds"])
    inp = small(sigma=np.zeros(k), mu=np.full(k, 0.06))
    events = {"switches": [], "withdrawals": [{"month": 60, "amount": 20_000}]}
    r = run_one(inp, events, draw_returns(inp), FLAT, "two_etf")
    assert np.allclose(r["withdrawn"], 20_000, atol=0.01) and (r["tax"] > 0).all()
    assert (r["shortfall"] == 0).all()


def test_no_gain_means_no_tax():
    k = len(small()["funds"])
    inp = small(sigma=np.zeros(k), mu=np.zeros(k), ter=np.zeros(k), order_fee=0.0)
    r = run_one(inp, NO_EVENTS, draw_returns(inp), FLAT, "four_etf_thematic")
    assert np.allclose(r["tax"], 0) and np.allclose(r["final"], r["paid_in"])


def test_returns_have_the_assumed_correlations():
    inp = small(n_paths=4000)
    shocks = draw_returns(inp).reshape(-1, len(inp["funds"]))
    assert np.abs(np.corrcoef(shocks.T) - inp["corr"]).max() < 0.03


def test_growing_scenario_pays_in_more_and_results_repeat():
    inp = small()
    grow = {"id": "g", "contributions": "grow_with_salary", "returns": "historical"}
    shocks = draw_returns(inp)
    a = run_one(inp, NO_EVENTS, shocks, FLAT, "two_etf")
    b = run_one(inp, NO_EVENTS, shocks, grow, "two_etf")
    assert b["paid_in"] > a["paid_in"] and (b["final"] > a["final"]).mean() > 0.9
    events, runs = run_all(inp)
    again = run_all(inp)[1]
    assert all(np.array_equal(runs[k]["final"], again[k]["final"]) for k in runs)
    for r in runs.values():
        assert np.allclose(r["weights"].sum(axis=1), 1) and (r["weights"] >= 0).all()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
