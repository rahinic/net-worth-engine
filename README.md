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

### Costs

The ETF savings plan runs through Trade Republic, whose costs are in [`assumptions/costs.yaml`](assumptions/costs.yaml): €0 to execute a savings plan, €1 per manual order (rebalancing, selling), no custody fee. Each fund's own yearly fee (TER) is separate and sits inside the fund's price. Spreads are not modelled yet because no sourced figure was found.

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

**What happens next:** costs grow with inflation, but pay and contributions are flat in nominal terms until a raise. So between raises the gap widens and is covered from savings. In the generated statements the savings account is about €760 lower by September 2026, before the first raise in January 2027.

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

Inflation is 2.6% a year, the average of German CPI over 2016 to 2025 ([`assumptions/inflation.yaml`](assumptions/inflation.yaml)). Savings interest is 2.75% a year, set by the user, and is assumed to sit inside the tax-free allowance. The persona's €12,000 cash starts as €3,000 in the current account and €9,000 in savings, and after each payday the current account is topped up to or swept down to €3,000. Weekdays only, no public holidays.

## Cleaning with dbt

dbt-core on DuckDB turns the two messy exports into one clean ledger and a monthly timeline. Run everything from the repository root:

```
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
python3 -m generator.run
dbt build --project-dir dbt --profiles-dir dbt
```

| Model | What it does |
|---|---|
| `stg_salary_account`, `stg_savings_account` | Read each export and handle the three differences: date format, amount columns, preamble. |
| `int_ledger_clean` | One ledger for both accounts: duplicates dropped, spacing tidied, categories added from the `merchant_categories` seed. |
| `mart_monthly_cash` | Inflow, outflow and closing balance per account per month. |
| `mart_net_worth_at_cost` | Month-end net worth at cost: cash plus ETF and gold contributions as paid, with no market movement yet. |

Beyond the usual not-null and accepted-value checks, three tests compare the result with the answer key in `data/truth/`: every cleaned row must match the ledger, the closing balances must match, and the number of dropped rows must equal the duplicates in the mess log. I checked that they fail when the deduplication is broken.

At September 2026 the persona has about €50,000 at cost: €11,200 cash, €32,750 in ETFs and €5,970 in gold.

GitHub Actions (`.github/workflows/ci.yml`) runs the tests, checks the generated data is up to date, and runs `dbt build`.

## Status

Done: persona version 3, the net-pay function, the bank-statement generator and the dbt cleaning models. Planned: ETF Monte Carlo and gold comparison. Results will be published at https://rahinic.github.io/net-worth/.
