-- Mart: month-end net worth at cost.
--
-- Net worth = cash in both bank accounts + ETFs + gold. ETFs and gold are valued at
-- what was paid, not at market value, so there is no market movement here yet; the
-- simulations add that. One row per month, dated at the month end.

-- Cash: both bank accounts added up, with each account kept as its own column.
with cash as (
    select
        month,
        sum(closing_balance_eur) as cash_eur,
        sum(case when account = 'salary' then closing_balance_eur end) as current_account_eur,
        sum(case when account = 'savings' then closing_balance_eur end) as savings_account_eur
    from {{ ref('mart_monthly_cash') }}
    group by month
),

-- What left the current account for ETFs and gold each month, taken from the
-- categorised ledger. Those standing orders are the contributions.
invested as (
    select
        date_trunc('month', booking_date)::date as month,
        sum(case when category = 'contribution_etf' then -amount_eur else 0 end) as etf_paid_eur,
        sum(case when category = 'contribution_gold' then -amount_eur else 0 end) as gold_paid_eur
    from {{ ref('int_ledger_clean') }}
    group by 1
),

-- What the persona already held in ETFs and gold on day one (seed).
start_value as (
    select
        max(case when account = 'etf' then opening_eur end) as etf_eur,
        max(case when account = 'gold' then opening_eur end) as gold_eur
    from {{ ref('opening_balances') }}
)

select
    -- First day of the month plus one month, minus a day = the last day of the month.
    (c.month + interval 1 month - interval 1 day)::date as month_end,
    c.current_account_eur,
    c.savings_account_eur,
    c.cash_eur,
    -- Holdings at cost = starting amount + everything paid in up to this month.
    s.etf_eur + sum(coalesce(i.etf_paid_eur, 0)) over (order by c.month) as etf_at_cost_eur,
    s.gold_eur + sum(coalesce(i.gold_paid_eur, 0)) over (order by c.month) as gold_at_cost_eur,
    -- Net worth at cost = cash + ETFs + gold, as above.
    c.cash_eur
        + s.etf_eur + sum(coalesce(i.etf_paid_eur, 0)) over (order by c.month)
        + s.gold_eur + sum(coalesce(i.gold_paid_eur, 0)) over (order by c.month) as net_worth_at_cost_eur
from cash as c
left join invested as i using (month)
cross join start_value as s
order by c.month
