-- Staging: savings account export (the Tagesgeld account).
--
-- This file differs from the salary file in three ways, marked 1, 2, 3 below:
--   1. dates are written yyyy-mm-dd
--   2. separate Soll (debit) and Haben (credit) columns, both positive
--   3. a preamble: 3 metadata lines and a blank line, so the header is line 5
--
-- Staging only reads and types the data. Cleaning happens in int_ledger_clean.

with raw as (
    select
        *,
        -- Row number in the file as exported (newest booking first), for tracing.
        row_number() over () as source_row
    from read_csv(
        '{{ var("raw_dir") }}/savings_account_*.csv',
        delim = ';',
        quote = '"',
        skip = 4,              -- (3) skip the preamble: 3 metadata lines and the blank line
        header = true,         -- the header is now the next line (line 5)
        encoding = 'latin-1',  -- the export is ISO-8859-1, not UTF-8
        all_varchar = true,    -- read everything as text; the typing below is explicit
        filename = true
    )
)

select
    'savings' as account,
    source_row,
    strptime(Buchungstag, '%Y-%m-%d')::date as booking_date,    -- (1) ISO date
    Buchungstext as booking_text,
    Verwendungszweck as purpose_raw,
    "Auftraggeber/Empfänger" as counterparty_raw,
    IBAN as iban,
    -- (2) Build one signed amount so both accounts look the same downstream:
    -- credits (Haben) count as money in, debits (Soll) as money out.
    -- A row only fills one of the two columns; the empty one becomes 0.
    coalesce(replace(replace(Haben, '.', ''), ',', '.')::decimal(18, 2), 0)
        - coalesce(replace(replace(Soll, '.', ''), ',', '.')::decimal(18, 2), 0) as amount_eur,
    filename as source_file
from raw
