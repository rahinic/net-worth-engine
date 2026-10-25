-- Savings account export. Differences from the salary file are marked 1, 2, 3.
--   1. dates are yyyy-mm-dd
--   2. separate Soll (debit) and Haben (credit) columns, both positive
--   3. a preamble: 3 metadata lines and a blank line, so the header is line 5
with raw as (
    select *, row_number() over () as source_row
    from read_csv(
        '{{ var("raw_dir") }}/savings_account_*.csv',
        delim = ';', quote = '"', skip = 4, header = true, encoding = 'latin-1',
        all_varchar = true, filename = true
    )
)

select
    'savings' as account,
    source_row,
    strptime(Buchungstag, '%Y-%m-%d')::date as booking_date,
    Buchungstext as booking_text,
    Verwendungszweck as purpose_raw,
    "Auftraggeber/Empfänger" as counterparty_raw,
    IBAN as iban,
    coalesce(replace(replace(Haben, '.', ''), ',', '.')::decimal(18, 2), 0)
        - coalesce(replace(replace(Soll, '.', ''), ',', '.')::decimal(18, 2), 0) as amount_eur,
    filename as source_file
from raw
