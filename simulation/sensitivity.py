"""How much the 2-ETF versus 4-ETF result depends on the assumptions.

Run: python3 -m simulation.sensitivity
Flat contributions, historical returns, nominal. Same random draws in every case.
"""
import csv

import numpy as np

from simulation.etf_mc import ROOT, build_events, draw_returns, load_inputs, run_one


def main():
    inp = load_inputs()
    shocks, events = draw_returns(inp), build_events(inp)
    scenario = next(s for s in inp["scenarios"] if s["id"] == "flat_historical")
    miners = inp["funds"].index("gold_miners_etf")

    cases = [("base assumptions", inp)]
    for rate in (0.08, 0.10, 0.158):
        changed = dict(inp, mu=inp["mu"].copy())
        changed["mu"][miners] = rate
        cases.append((f"gold miners return {rate * 100:g}% (base 5%)", changed))
    cases.append(("all fund fees (TER) equal at 0.20%", dict(inp, ter=np.full_like(inp["ter"], 0.002))))

    rows = []
    for label, case in cases:
        diff = (run_one(case, events, shocks, scenario, "four_etf_thematic")["final"]
                - run_one(case, events, shocks, scenario, "two_etf")["final"])
        rows.append([label, round(float((diff > 0).mean()), 2), round(float(np.median(diff)))])

    with open(ROOT / "data" / "results" / "etf_sensitivity.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case", "prob_four_beats_two", "median_diff_nominal_eur"])
        w.writerows(rows)
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
