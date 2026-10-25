-- Intermediate: one clean ledger for both bank accounts.
--
-- What it fixes:
--   - exact duplicate rows are dropped (the first one is kept)
--   - spacing in the free-text fields is tidied
--   - every row gets a category, looked up from the merchant_categories seed
--
-- What it cannot fix: upper or lower case, and "ae" written for "ä". The original is
-- not recoverable, so rows are matched on a normalised counterparty key instead.

-- Step 1: stack the two accounts. The staging models already have identical columns.
with unioned as (
    select * from {{ ref('stg_salary_account') }}
    union all
    select * from {{ ref('stg_savings_account') }}
),

-- Step 2: drop exact duplicates. A duplicate is the same booking exported twice, so
-- every field matches. Rows that only look alike (same merchant, different amount or
-- day) are different bookings and stay. qualify keeps the first copy in file order.
deduplicated as (
    select *
    from unioned
    qualify row_number() over (
        partition by account, booking_date, booking_text, purpose_raw,
                     counterparty_raw, iban, amount_eur
        order by source_file, source_row
    ) = 1
),

-- Step 3: tidy the free text. Missing values become empty strings, and runs of spaces
-- (leading, trailing or doubled) collapse to a single space.
tidied as (
    select
        *,
        trim(regexp_replace(coalesce(purpose_raw, ''), '\s+', ' ', 'g')) as purpose_clean,
        trim(regexp_replace(coalesce(counterparty_raw, ''), '\s+', ' ', 'g')) as counterparty_clean
    from deduplicated
)

-- Step 4: categorise. The seed maps a counterparty key (upper case, umlauts spelled out)
-- to a category. The same normalisation is applied to the counterparty here, so
-- "Bäckerei Schmidt", "BÄCKEREI SCHMIDT" and "baeckerei schmidt" all find the same key.
select
    t.account,
    t.booking_date,
    t.amount_eur,
    t.booking_text,
    t.purpose_clean,
    t.counterparty_clean,
    coalesce(
        -- Interest rows have no counterparty, so they are recognised by their booking text.
        case when t.booking_text = 'ABSCHLUSS' then 'interest' end,
        m.category,
        -- Anything the seed does not know stays visible, and a test fails on it.
        'unmapped'
    ) as category,
    t.source_file,
    t.source_row
from tidied as t
left join {{ ref('merchant_categories') }} as m
    on m.counterparty_key = replace(replace(replace(
        upper(replace(t.counterparty_clean, 'ß', 'ss')),
        'Ä', 'AE'), 'Ö', 'OE'), 'Ü', 'UE')
