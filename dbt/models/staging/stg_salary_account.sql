-- Staging: salary account export (the current account).
--
-- This file differs from the savings file in three ways, marked 1, 2, 3 below:
--   1. dates are written dd.mm.yyyy
--   2. one signed Betrag column (debits are negative)
--   3. no preamble: the header is the first line of the file
--
-- Staging only reads and types the data. Cleaning happens in int_ledger_clean.

with raw as (
    select
        *,
        -- Row number in the file as exported (newest booking first). Kept so that
        -- any row can be traced back to the file, and as the tie-breaker later.
        row_number() over () as source_row
    from read_csv(
        '{{ var("raw_dir") }}/salary_account_*.csv',
        delim = ';',
        quote = '"',
        header = true,         -- (3) the header is the first line, nothing to skip
        encoding = 'latin-1',  -- the export is ISO-8859-1, not UTF-8
        all_varchar = true,    -- read everything as text; the typing below is explicit
        filename = true
    )
)

select
    'salary' as account,
    source_row,
    strptime(Buchungstag, '%d.%m.%Y')::date as booking_date,    -- (1) day.month.year
    Buchungstext as booking_text,
    Verwendungszweck as purpose_raw,                              -- free text, cleaned later
    "Auftraggeber/Empfänger" as counterparty_raw,
    IBAN as iban,
    -- (2) German number to decimal: "-1.234,56" -> "-1234,56" -> "-1234.56"
    replace(replace(Betrag, '.', ''), ',', '.')::decimal(18, 2) as amount_eur,
    filename as source_file
from raw
