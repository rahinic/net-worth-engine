-- Month by month cash movement and closing balance for each bank account.
with ledger as (
    select * from {{ ref('int_ledger_clean') }}
),

spine as (
    select
        a.account,
        unnest(generate_series(
            (select date_trunc('month', min(booking_date)) from ledger),
            (select date_trunc('month', max(booking_date)) from ledger),
            interval 1 month
        ))::date as month
    from (select distinct account from ledger) as a
),

monthly as (
    select
        account,
        date_trunc('month', booking_date)::date as month,
        sum(case when amount_eur > 0 then amount_eur else 0 end) as inflow_eur,
        sum(case when amount_eur < 0 then -amount_eur else 0 end) as outflow_eur
    from ledger
    group by 1, 2
),

opening as (
    select account, opening_eur from {{ ref('opening_balances') }}
),

joined as (
    select
        s.account,
        s.month,
        coalesce(m.inflow_eur, 0) as inflow_eur,
        coalesce(m.outflow_eur, 0) as outflow_eur
    from spine as s
    left join monthly as m using (account, month)
)

select
    j.account,
    j.month,
    o.opening_eur + coalesce(sum(j.inflow_eur - j.outflow_eur) over (
        partition by j.account order by j.month
        rows between unbounded preceding and 1 preceding), 0) as opening_balance_eur,
    j.inflow_eur,
    j.outflow_eur,
    o.opening_eur + sum(j.inflow_eur - j.outflow_eur) over (
        partition by j.account order by j.month) as closing_balance_eur
from joined as j
join opening as o using (account)
order by j.account, j.month
