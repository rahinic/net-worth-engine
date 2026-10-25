-- The last closing balance per account must equal the answer key's running balance.
with clean as (
    select account, closing_balance_eur
    from {{ ref('mart_monthly_cash') }}
    qualify row_number() over (partition by account order by month desc) = 1
),

truth as (
    select account, balance_after_cents / 100.0 as closing_balance_eur
    from read_csv('{{ var("truth_dir") }}/ledger.csv', header = true)
    qualify row_number() over (partition by account order by truth_id desc) = 1
)

select c.account, c.closing_balance_eur, t.closing_balance_eur as truth_eur
from clean as c
join truth as t using (account)
where abs(c.closing_balance_eur - t.closing_balance_eur) > 0.005
