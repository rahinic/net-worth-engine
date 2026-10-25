-- One clean ledger for both accounts.
--   - exact duplicate rows are dropped, keeping the first
--   - spacing is tidied; casing and ae/oe/ue spelling cannot be restored, so
--     matching uses a normalised counterparty key instead
--   - the category comes from the merchant_categories seed
with unioned as (
    select * from {{ ref('stg_salary_account') }}
    union all
    select * from {{ ref('stg_savings_account') }}
),

deduplicated as (
    select *
    from unioned
    qualify row_number() over (
        partition by account, booking_date, booking_text, purpose_raw,
                     counterparty_raw, iban, amount_eur
        order by source_file, source_row
    ) = 1
),

tidied as (
    select
        *,
        trim(regexp_replace(coalesce(purpose_raw, ''), '\s+', ' ', 'g')) as purpose_clean,
        trim(regexp_replace(coalesce(counterparty_raw, ''), '\s+', ' ', 'g')) as counterparty_clean
    from deduplicated
)

select
    t.account,
    t.booking_date,
    t.amount_eur,
    t.booking_text,
    t.purpose_clean,
    t.counterparty_clean,
    coalesce(
        case when t.booking_text = 'ABSCHLUSS' then 'interest' end,
        m.category,
        'unmapped'
    ) as category,
    t.source_file,
    t.source_row
from tidied as t
left join {{ ref('merchant_categories') }} as m
    on m.counterparty_key = replace(replace(replace(
        upper(replace(t.counterparty_clean, 'ß', 'ss')),
        'Ä', 'AE'), 'Ö', 'OE'), 'Ü', 'UE')
