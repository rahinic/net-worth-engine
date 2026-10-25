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
| 2 ETFs | MSCI World 50%, S&P 500 50% |
| 4 ETFs (thematic) | MSCI World 50%, Emerging Markets 15%, AI & Big Data 17.5%, Gold Miners ETF 17.5% |

The monthly ETF savings plan is split by these weights. The starting €15,000 is assumed to be held in the same weights. The AI & Big Data fund has a short history, and the gold-miners fund depends on the gold price, so their return figures will be mostly estimates.

### Scenarios

| Scenario | Contributions | Returns |
|---|---|---|
| `flat_historical` | Flat in nominal terms | Historical |
| `flat_conservative` | Flat in nominal terms | Historical minus 2 points |
| `growing_historical` | Grow with salary (+10% at each raise) | Historical |

Return and volatility figures are in [`assumptions/returns.yaml`](assumptions/returns.yaml), each marked as sourced, adjusted or an estimate.

### Net pay

Net pay is computed from gross by [`persona/tax.py`](persona/tax.py), a simplified German tax and social-contribution function. Its docstring lists every simplification. Run the tests with `python3 persona/test_tax.py` from inside `persona/`.

**Budget scaled to match:** at €50,000 gross, tax class IV, the function gives about **€2,690 net a month**, not the roughly €3,000 in the brief. The brief's outgoings (€600 ETF, €100 gold, €1,350 fixed, €950 variable, €3,000 in total) would have run a shortfall of about €310 a month. All four amounts were scaled by the same factor (about 0.897) so that outgoings equal net pay at the start.

**What happens next:** costs grow with inflation, but pay and contributions are flat in nominal terms until a raise. So between raises the gap widens and is covered from savings. In the generated statements the savings account is about €950 lower by September 2026, before the first raise in January 2027.

## Bank statements

`python3 -m generator.run` writes two messy bank exports and the answer key to `data/` (already generated and committed). Settings are in [`generator/config.yaml`](generator/config.yaml). Run the tests with `python3 -m generator.test_generator`.

- `data/raw/`: the two exports, salary account and savings account, January 2024 to September 2026.
- `data/truth/ledger.csv`: the clean ledger with running balances.
- `data/truth/mess_log.csv`: every injected problem and the row it is on.

Both exports share one German-bank style: semicolons, ISO-8859-1, every field quoted, amounts like `1.234,56`, newest first. They differ in exactly three ways:

1. Dates: `31.01.2024` in the salary file, `2024-01-31` in the savings file.
2. Amounts: one signed `Betrag` column in the salary file, separate `Soll` and `Haben` columns in the savings file.
3. Preamble: the savings file has three metadata lines and a blank line above the header.

The mess, the same in both files: duplicated rows, changed case, spacing or umlauts in the text, a missing purpose on some card payments, and a few rows out of order.

The three differences are written up in [`docs/data-cleaning-notes.md`](docs/data-cleaning-notes.md).

Inflation is 2.6% a year, the average of German CPI over 2016 to 2025 ([`assumptions/inflation.yaml`](assumptions/inflation.yaml)). Savings interest of 2% a year is a placeholder, not yet approved. The persona's €12,000 cash starts as €3,000 in the current account and €9,000 in savings, and after each payday the current account is topped up to or swept down to €3,000. Weekdays only, no public holidays.

## Status

Done: persona version 3, the net-pay function and the bank-statement generator. Planned: dbt models, ETF Monte Carlo and gold comparison. Results will be published at https://rahinic.github.io/net-worth/.
