-- The cleaned ledger must equal the answer key: same rows, amounts and categories.
-- Returns the rows that differ, so the test passes when there are none.
with clean as (
    select account, booking_date, round(amount_eur * 100)::bigint as amount_cents, category
    from {{ ref('int_ledger_clean') }}
),

truth as (
    select account, booking_date::date as booking_date, amount_cents::bigint as amount_cents, category
    from read_csv('{{ var("truth_dir") }}/ledger.csv', header = true)
),

missing as (
    select * from truth except all select * from clean
),

extra as (
    select * from clean except all select * from truth
)

select 'missing_from_clean' as problem, * from missing
union all
select 'extra_in_clean' as problem, * from extra
