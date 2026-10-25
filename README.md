# net-worth-engine

A synthetic-persona net worth simulation: German-bank CSVs, an ETF Monte Carlo with German tax, and Indian versus German gold. Python, DuckDB and dbt-core, all free.

Illustrative simulation using synthetic data. Not financial advice.

## Persona, version 3

[`persona/persona.yaml`](persona/persona.yaml) is the source of truth.

- Pooja, 35, Indian origin, lives in Berlin. Married, spouse on a similar income, tax class IV.
- €50,000 gross, with +10% (nominal) every 3 years.
- Starts with €30,000: ETFs €15,000, savings €12,000, gold €3,000.
- Each month: €538 ETF savings plan, €90 Indian gold scheme, about €1,210 fixed costs and about €852 variable costs, €2,690 in total.
- Contributions stay flat in nominal terms.

### ETF portfolios

| Portfolio | Funds |
|---|---|
| 2 ETFs | MSCI World and S&P 500, weights not set yet |
| 4 ETFs (thematic) | MSCI World 50%, Emerging Markets 15%, AI & Big Data 17.5%, Renewable Energy 17.5% |

The monthly ETF savings plan is split by these weights. The starting €15,000 is assumed to be held in the same weights. The AI & Big Data and Renewable Energy funds have short histories, so their return figures will be mostly estimates.

### Scenarios

| Scenario | Contributions | Returns |
|---|---|---|
| `flat_historical` | Flat in nominal terms | Historical |
| `flat_conservative` | Flat in nominal terms | Historical minus 2 points |
| `growing_historical` | Grow with salary (+10% at each raise) | Historical |

The return figures are not set yet.

### Net pay

Net pay is computed from gross by [`persona/tax.py`](persona/tax.py), a simplified German tax and social-contribution function. Its docstring lists every simplification. Run the tests with `python3 persona/test_tax.py` from inside `persona/`.

**Budget scaled to match:** at €50,000 gross, tax class IV, the function gives about **€2,690 net a month**, not the roughly €3,000 in the brief. The brief's outgoings (€600 ETF, €100 gold, €1,350 fixed, €950 variable, €3,000 in total) would have run a shortfall of about €310 a month. All four amounts were scaled by the same factor (about 0.897) so that outgoings equal net pay at the start. Savings neither grow nor shrink at first. Raises lift net pay while contributions stay flat, so a surplus appears later and goes to the savings account.

## Status

Done: persona version 3 and the net-pay function. Planned: the bank-statement generator, dbt models, ETF Monte Carlo and gold comparison. Results will be published at https://rahinic.github.io/net-worth/.
