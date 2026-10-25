-- Salary account export. Differences from the savings file are marked 1, 2, 3.
--   1. dates are dd.mm.yyyy
--   2. one signed Betrag column
--   3. no preamble: the header is the first line
with raw as (
    select *, row_number() over () as source_row
    from read_csv(
        '{{ var("raw_dir") }}/salary_account_*.csv',
        delim = ';', quote = '"', header = true, encoding = 'latin-1',
        all_varchar = true, filename = true
    )
)

select
    'salary' as account,
    source_row,
    strptime(Buchungstag, '%d.%m.%Y')::date as booking_date,
    Buchungstext as booking_text,
    Verwendungszweck as purpose_raw,
    "Auftraggeber/Empfänger" as counterparty_raw,
    IBAN as iban,
    replace(replace(Betrag, '.', ''), ',', '.')::decimal(18, 2) as amount_eur,
    filename as source_file
from raw
