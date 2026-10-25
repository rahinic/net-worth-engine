# net-worth-engine

A synthetic-persona net worth simulation: German-bank CSVs, an ETF Monte Carlo with German tax, and Indian versus German gold. Python, DuckDB and dbt-core, all free.

Illustrative simulation using synthetic data. Not financial advice.

## Persona, version 3

[`persona/persona.yaml`](persona/persona.yaml) is the source of truth.

- Pooja, 35, Indian origin, lives in Berlin.
- €50,000 gross, with +10% (nominal) every 3 years.
- Starts with €30,000: ETFs €15,000, savings €12,000, gold €3,000.
- Each month: €600 ETF savings plan, €100 Indian gold scheme, about €1,350 fixed costs and about €950 variable costs.
- Contributions stay flat in nominal terms.

### Scenarios

| Scenario | Contributions | Returns |
|---|---|---|
| `flat_historical` | Flat in nominal terms | Historical |
| `flat_conservative` | Flat in nominal terms | Historical minus 2 points |
| `growing_historical` | Grow with salary (+10% at each raise) | Historical |

The return figures are not set yet.

### Net pay

Net pay is computed from gross by [`persona/tax.py`](persona/tax.py), a simplified German tax and social-contribution function. Its docstring lists every simplification. Run the tests with `python3 persona/test_tax.py` from inside `persona/`.

**Known gap:** at €50,000 gross, tax class I, the function gives about **€2,690 net a month**, not the roughly €3,000 in the brief. Costs and contributions add up to €3,000, so with class I the persona runs a shortfall of about €310 a month, paid from savings. The brief did not give a marital status; tax class III would give about €3,020 net.

## Status

Done: persona version 3 and the net-pay function. Planned: the bank-statement generator, dbt models, ETF Monte Carlo and gold comparison. Results will be published at https://rahinic.github.io/net-worth/.
