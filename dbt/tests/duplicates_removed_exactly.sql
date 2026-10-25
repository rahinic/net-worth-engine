-- The number of rows dropped must equal the duplicates recorded in the mess log.
with dropped as (
    select
        (select count(*) from {{ ref('stg_salary_account') }})
        + (select count(*) from {{ ref('stg_savings_account') }})
        - (select count(*) from {{ ref('int_ledger_clean') }}) as n
),

logged as (
    select count(*) as n
    from read_csv('{{ var("truth_dir") }}/mess_log.csv', header = true)
    where issue = 'duplicate'
)

select dropped.n as dropped, logged.n as logged
from dropped, logged
where dropped.n <> logged.n
