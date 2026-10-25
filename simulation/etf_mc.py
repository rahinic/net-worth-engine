"""Monte Carlo of the 2-ETF and 4-ETF portfolios with German tax.

Illustrative simulation, not financial advice. Every input comes from persona/ and
assumptions/; nothing is hard-coded here.

How it works, one month at a time, for every path at once:
  1. January: pay the Vorabpauschale tax for the year just ended, out of the portfolio.
  2. If a switch is due (first decade): sell part of one fund, pay tax and fees, buy another.
  3. If a withdrawal is due: sell pro rata across the funds so that the amount, after tax
     and fees, reaches her. It is spent and leaves the portfolio.
  4. Invest the monthly savings plan, split by the current weights.
  5. Apply the month's random returns, minus the funds' yearly fee (TER).
At the end the whole portfolio is sold, with tax, to give the after-tax final value.

Simplifications, on purpose:
  - Returns are lognormal and correlated; there are no extra-fat tails, so extreme crashes
    are understated. Gold miners are one of the five correlated funds, not yet tied to the
    gold model.
  - Cost basis is an average per fund, not first-in-first-out.
  - Vorabpauschale uses the opening value of the year; purchases during the year are not
    pro-rated. Tax on it is paid by selling pro rata, without tax on that small sale.
  - The Vorabpauschale for year Y is paid in January of Y+1.
  - Switch dates and withdrawal dates and amounts are drawn once and are the same for every
    path. Which funds she switches between, and how much, is drawn per path, so the results
    average over the ways she might have switched. The draws are the same in every scenario
    and for both portfolios.
"""
import csv
from pathlib import Path

import numpy as np
import yaml

from simulation.etf_tax import apply_tax, vorabpauschale

ROOT = Path(__file__).resolve().parent.parent
PERCENTILES = (5, 25, 50, 75, 95)


def _yaml(path):
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def load_inputs(n_paths=None):
    persona, returns = _yaml("persona/persona.yaml"), _yaml("assumptions/returns.yaml")
    corr, costs = _yaml("assumptions/correlations.yaml"), _yaml("assumptions/costs.yaml")
    trading, tax = _yaml("assumptions/trading.yaml"), _yaml("assumptions/german_tax.yaml")
    inflation, cfg = _yaml("assumptions/inflation.yaml"), _yaml("simulation/config.yaml")

    funds = corr["funds"]
    column = {name: i for i, name in enumerate(funds)}
    portfolios = {}
    for name, p in persona["portfolios"].items():
        idx = np.array([column[f] for f in p["weights"]])
        portfolios[name] = {"idx": idx, "weights": np.array(list(p["weights"].values()), dtype=float)}

    basiszins = tax["basiszins_pct_by_year"]
    return {
        "n_paths": n_paths or cfg["n_paths"],
        "seed": cfg["seed"],
        "years": persona["simulation"]["horizon_years"],
        "start_year": persona["simulation"]["start_date"].year,
        "funds": funds,
        "corr": np.array(corr["matrix"], dtype=float),
        "mu": np.array([returns["funds"][f]["return_historical"] for f in funds]),
        "sigma": np.array([returns["funds"][f]["volatility"] for f in funds]),
        "conservative_shift": returns["conservative_shift_pct_points"] / 100,
        "ter": np.array([costs["ter_pct_per_year"][f] for f in funds]) / 100,
        "order_fee": costs["manual_order_fee_eur"],
        "plan_fee": costs["savings_plan_execution_fee_eur"],
        "tax_rate": tax["abgeltungsteuer_pct"] / 100 * (1 + tax["soli_pct_of_tax"] / 100),
        "teilfreistellung": tax["teilfreistellung_pct"] / 100,
        "allowance": tax["sparer_pauschbetrag_eur"] - tax["savings_interest_eur_per_year"],
        "vp_fraction": tax["vorabpauschale_fraction_of_basis"],
        "basiszins": lambda year: basiszins.get(year, tax["basiszins_pct_after_2026"]) / 100,
        "inflation": inflation["average_pct_per_year"] / 100,
        "start_etf": persona["start_net_worth_eur"]["etf"],
        "monthly_etf": persona["monthly_eur"]["etf_savings_plan"],
        "raise_pct": persona["income"]["raise"]["pct"],
        "raise_every_months": persona["income"]["raise"]["every_years"] * 12,
        "portfolios": portfolios,
        "scenarios": persona["scenarios"],
        "trading": trading,
    }


def build_events(inp):
    """Switch and withdrawal events. Dates are shared by every path; the switch details are
    drawn per path (arrays with one entry per path). Same draws for every scenario and portfolio."""
    rng = np.random.default_rng(inp["seed"] + 1)
    n = inp["n_paths"]
    sw, wd = inp["trading"]["phase_1_switching"], inp["trading"]["withdrawals"]
    last_month = (sw["to"].year - inp["start_year"] + 1) * 12

    switches, month = [], 0
    while True:
        month += 3 * int(rng.integers(sw["every_quarters"][0], sw["every_quarters"][1] + 1))
        if month >= last_month:
            break
        switches.append({
            "month": month,
            "moved_pct": rng.uniform(*sw["amount_moved_pct_of_portfolio"], size=n),
            "shift": rng.uniform(*sw["weight_shift_points"], size=n) / 100,
            "pick_a": rng.integers(0, 1000, size=n),
            "pick_b": rng.integers(0, 1000, size=n),
        })

    step = wd["rounded_to_eur"]
    withdrawals = [{"month": (year - inp["start_year"]) * 12,
                    "amount": step * round(float(rng.uniform(*wd["amount_eur_range"])) / step)}
                   for year in wd["years"]]
    return {"switches": switches, "withdrawals": withdrawals}


def draw_returns(inp):
    """Correlated standard normal shocks, shape (months, paths, funds). Shared by all runs."""
    rng = np.random.default_rng(inp["seed"])
    months, n, k = inp["years"] * 12, inp["n_paths"], len(inp["funds"])
    shocks = rng.standard_normal((months, n, k), dtype=np.float32)
    chol = np.linalg.cholesky(inp["corr"]).astype(np.float32)
    return (shocks.reshape(-1, k) @ chol.T).reshape(months, n, k)


def run_one(inp, events, shocks, scenario, portfolio):
    """One scenario on one portfolio, all paths at once."""
    n, months = inp["n_paths"], inp["years"] * 12
    p = inp["portfolios"][portfolio]
    idx, k = p["idx"], len(p["idx"])
    sigma, ter, tf = inp["sigma"][idx], inp["ter"][idx], inp["teilfreistellung"]
    mu = inp["mu"][idx] + (inp["conservative_shift"] if scenario["returns"] == "conservative" else 0.0)
    mean_log = (np.log1p(mu) - sigma ** 2 / 2) / 12
    rate, fee = inp["tax_rate"], inp["order_fee"]

    weights = np.tile(p["weights"], (n, 1))     # target weights, one row per path
    rows = np.arange(n)
    value = inp["start_etf"] * weights
    basis, vp_paid = value.copy(), np.zeros((n, k))
    allowance_left, loss_pot = np.full(n, inp["allowance"]), np.zeros(n)
    year_start, year_growth = value.copy(), np.ones((n, k))
    tax_total, fees_total, ter_total = np.zeros(n), np.zeros(n), np.zeros(n)
    withdrawn, shortfall, paid_in = np.zeros(n), np.zeros(n), float(inp["start_etf"])
    switch_at = {e["month"]: e for e in events["switches"]}
    withdraw_at = {e["month"]: e for e in events["withdrawals"]}
    yearly = []

    def scale_holdings(fraction):
        keep = (1 - fraction)[:, None]
        value[:] *= keep
        basis[:] *= keep
        vp_paid[:] *= keep

    for t in range(months):
        year, month = inp["start_year"] + t // 12, t % 12

        if month == 0:
            allowance_left[:] = inp["allowance"]
            if t > 0:
                vp = vorabpauschale(year_start, year_growth, inp["basiszins"](year - 1), inp["vp_fraction"])
                tax, allowance_left, loss_pot = apply_tax(
                    (vp * (1 - tf)).sum(axis=1), allowance_left, loss_pot, rate)
                vp_paid += vp
                scale_holdings(np.minimum(1.0, tax / np.maximum(value.sum(axis=1), 1e-9)))
                tax_total += tax
            year_start, year_growth = value.copy(), np.ones((n, k))

        if t in switch_at:
            e = switch_at[t]
            a = e["pick_a"] % k                          # fund sold, per path
            b = (a + 1 + e["pick_b"] % (k - 1)) % k      # fund bought, never the same fund
            held = value[rows, a]
            sold = np.minimum(held, e["moved_pct"] / 100 * value.sum(axis=1))
            f = np.divide(sold, held, out=np.zeros(n), where=held > 0)
            tax, allowance_left, loss_pot = apply_tax(
                f * (held - basis[rows, a] - vp_paid[rows, a]) * (1 - tf),
                allowance_left, loss_pot, rate)
            order = np.where(sold > 0, fee, 0.0)
            bought = np.maximum(sold - order - tax - order, 0.0)
            value[rows, a] -= sold
            basis[rows, a] *= 1 - f
            vp_paid[rows, a] *= 1 - f
            value[rows, b] += bought
            basis[rows, b] += bought
            tax_total += tax
            fees_total += 2 * order
            moved = np.minimum(e["shift"], weights[rows, a])
            weights[rows, a] -= moved
            weights[rows, b] += moved

        if t in withdraw_at:
            target = withdraw_at[t]["amount"]
            total = value.sum(axis=1)
            orders = (value > 1e-9).sum(axis=1) * fee
            unrealised = ((value - basis - vp_paid) * (1 - tf)).sum(axis=1)
            sold = np.full(n, float(target))
            for _ in range(10):  # sell enough that the amount after tax and fees is the target
                share = np.minimum(1.0, sold / np.maximum(total, 1e-9))
                tax, _, _ = apply_tax(share * unrealised, allowance_left, loss_pot, rate)
                sold = np.minimum(total, target + orders + tax)
            share = np.minimum(1.0, sold / np.maximum(total, 1e-9))
            tax, allowance_left, loss_pot = apply_tax(share * unrealised, allowance_left, loss_pot, rate)
            received = np.maximum(sold - orders - tax, 0.0)
            scale_holdings(share)
            tax_total += tax
            fees_total += orders
            withdrawn += received
            shortfall += np.maximum(target - received, 0.0)

        scale = (1 + inp["raise_pct"] / 100) ** (t // inp["raise_every_months"]) \
            if scenario["contributions"] == "grow_with_salary" else 1.0
        contribution = inp["monthly_etf"] * scale
        value += contribution * weights
        basis += contribution * weights
        paid_in += contribution

        growth = np.exp(mean_log + shocks[t][:, idx].astype(np.float64) * (sigma / np.sqrt(12)))
        grown = value * growth
        ter_total += (grown * ter / 12).sum(axis=1)
        value = grown * (1 - ter / 12)
        year_growth = year_growth * growth * (1 - ter / 12)
        if month == 11:
            yearly.append(value.sum(axis=1))

    total = value.sum(axis=1)
    tax, _, _ = apply_tax(((value - basis - vp_paid) * (1 - tf)).sum(axis=1),
                          np.full(n, inp["allowance"]), loss_pot, rate)
    orders = (value > 1e-9).sum(axis=1) * fee
    deflator = (1 + inp["inflation"]) ** inp["years"]
    final = total - tax - orders
    return {
        "final": final, "final_real": final / deflator, "paid_in": paid_in,
        "tax": tax_total + tax, "fees": fees_total + orders, "ter": ter_total,
        "withdrawn": withdrawn, "shortfall": shortfall,
        "yearly": np.array(yearly), "weights": weights,
    }


BASELINE = "flat_historical_no_switches"


def run_all(inp):
    """The three scenarios, plus a baseline of flat contributions and historical returns with
    no switching, to show how much the switching matters."""
    events, shocks = build_events(inp), draw_returns(inp)
    runs = {(s["id"], name): run_one(inp, events, shocks, s, name)
            for s in inp["scenarios"] for name in inp["portfolios"]}
    flat = next(s for s in inp["scenarios"] if s["contributions"] == "flat_nominal" and s["returns"] == "historical")
    still = {"switches": [], "withdrawals": events["withdrawals"]}
    for name in inp["portfolios"]:
        runs[(BASELINE, name)] = run_one(inp, still, shocks, flat, name)
    return events, runs


def _pct(a):
    return [float(x) for x in np.percentile(a, PERCENTILES)]


def write_results(inp, events, runs, out):
    out.mkdir(parents=True, exist_ok=True)

    def write(name, header, rows):
        with open(out / name, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows([[round(x, 2) if isinstance(x, float) else x for x in r] for r in rows])

    pcols = [f"p{p}" for p in PERCENTILES]
    rows = []
    for (scenario, portfolio), r in runs.items():
        for basis, key in (("nominal", "final"), ("real", "final_real")):
            rows.append([scenario, portfolio, basis, *_pct(r[key]), float(r[key].mean())])
    write("etf_summary.csv", ["scenario", "portfolio", "basis", *pcols, "mean"], rows)

    rows = []
    for (scenario, portfolio), r in runs.items():
        lost = (r["final"] + r["withdrawn"]) < r["paid_in"]
        rows.append([scenario, portfolio, float(r["paid_in"]), float(r["withdrawn"].mean()),
                     float(r["tax"].mean()), float(r["fees"].mean()), float(r["ter"].mean()),
                     float(lost.mean()), float((r["shortfall"] > 0.5).mean())])
    write("etf_costs.csv", ["scenario", "portfolio", "paid_in", "mean_withdrawn", "mean_tax",
                            "mean_order_fees", "mean_ter", "prob_lost_money", "prob_withdrawal_shortfall"], rows)

    rows = []
    for scenario in dict.fromkeys(k[0] for k in runs):
        two, four = runs[(scenario, "two_etf")], runs[(scenario, "four_etf_thematic")]
        for basis, key in (("nominal", "final"), ("real", "final_real")):
            diff = four[key] - two[key]
            rows.append([scenario, basis, float((diff > 0).mean()), *_pct(diff)])
    write("etf_comparison.csv", ["scenario", "basis", "prob_four_beats_two",
                                 *[f"diff_{c}" for c in pcols]], rows)

    rows = []
    deflator = [(1 + inp["inflation"]) ** (y + 1) for y in range(inp["years"])]
    for (scenario, portfolio), r in runs.items():
        for y in range(inp["years"]):
            for basis, d in (("nominal", 1.0), ("real", deflator[y])):
                rows.append([scenario, portfolio, inp["start_year"] + y, basis, *_pct(r["yearly"][y] / d)])
    write("etf_yearly_bands.csv", ["scenario", "portfolio", "year", "basis", *pcols], rows)

    rows = [["switch", e["month"], round(float(e["moved_pct"].mean()), 1),
             round(float(e["shift"].mean()) * 100, 1)] for e in events["switches"]]
    rows += [["withdrawal", e["month"], e["amount"], ""] for e in events["withdrawals"]]
    write("etf_events.csv", ["event", "month_index", "moved_pct_or_amount_eur", "weight_shift_points"], rows)

    rows = []
    for (scenario, portfolio), r in runs.items():
        names = [inp["funds"][i] for i in inp["portfolios"][portfolio]["idx"]]
        for j, fund in enumerate(names):
            rows.append([scenario, portfolio, fund, float(inp["portfolios"][portfolio]["weights"][j]),
                         float(r["weights"][:, j].mean()), *[float(x) for x in np.percentile(r["weights"][:, j], (5, 95))]])
    write("etf_final_weights.csv", ["scenario", "portfolio", "fund", "start_weight",
                                    "mean_final_weight", "p5_final_weight", "p95_final_weight"], rows)


if __name__ == "__main__":
    inputs = load_inputs()
    events, runs = run_all(inputs)
    write_results(inputs, events, runs, ROOT / "data" / "results")
    print(f"{len(runs)} runs of {inputs['n_paths']:,} paths; "
          f"{len(events['switches'])} switches, {len(events['withdrawals'])} withdrawals")
