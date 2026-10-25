-- Month-end net worth at cost: cash in both accounts, plus what has been put
-- into ETFs and gold, valued at what was paid. No market movement yet; the
-- simulations add that.
with cash as (
    select
        month,
        sum(closing_balance_eur) as cash_eur,
        sum(case when account = 'salary' then closing_balance_eur end) as current_account_eur,
        sum(case when account = 'savings' then closing_balance_eur end) as savings_account_eur
    from {{ ref('mart_monthly_cash') }}
    group by month
),

invested as (
    select
        date_trunc('month', booking_date)::date as month,
        sum(case when category = 'contribution_etf' then -amount_eur else 0 end) as etf_paid_eur,
        sum(case when category = 'contribution_gold' then -amount_eur else 0 end) as gold_paid_eur
    from {{ ref('int_ledger_clean') }}
    group by 1
),

start_value as (
    select
        max(case when account = 'etf' then opening_eur end) as etf_eur,
        max(case when account = 'gold' then opening_eur end) as gold_eur
    from {{ ref('opening_balances') }}
)

select
    (c.month + interval 1 month - interval 1 day)::date as month_end,
    c.current_account_eur,
    c.savings_account_eur,
    c.cash_eur,
    s.etf_eur + sum(coalesce(i.etf_paid_eur, 0)) over (order by c.month) as etf_at_cost_eur,
    s.gold_eur + sum(coalesce(i.gold_paid_eur, 0)) over (order by c.month) as gold_at_cost_eur,
    c.cash_eur
        + s.etf_eur + sum(coalesce(i.etf_paid_eur, 0)) over (order by c.month)
        + s.gold_eur + sum(coalesce(i.gold_paid_eur, 0)) over (order by c.month) as net_worth_at_cost_eur
from cash as c
left join invested as i using (month)
cross join start_value as s
order by c.month
