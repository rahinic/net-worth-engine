# Data cleaning notes

The two synthetic bank exports in `data/raw/` look alike on purpose, and differ in exactly
**three ways**. These are the core cleaning exercises. Everything else is shared, light mess
that is logged so you can check your cleaning against the answer key.

Illustrative simulation, synthetic data.

## The three differences

| # | What differs | Salary account | Savings account | How to handle it |
|---|---|---|---|---|
| 1 | **Date format** | `31.01.2024` (day.month.year) | `2024-01-31` (ISO) | Parse each file with its own format, then compare as dates. |
| 2 | **Amount columns** | One signed `Betrag` column, debits negative | Separate `Soll` (debit) and `Haben` (credit) columns, both positive | Build one signed amount: `Haben - Soll`. Check that every row has exactly one of the two. |
| 3 | **Preamble** | None, the header is the first line | 3 metadata lines and a blank line above the header | Skip 5 lines before the header. Keep `Anfangssaldo` (opening balance) for the balance check. |

### What they look like

Salary account, header and a payday row:

```
"Buchungstag";"Wertstellung";"Buchungstext";"Verwendungszweck";"Auftraggeber/Empfänger";"IBAN";"Betrag";"Währung"
"31.01.2024";"31.01.2024";"GEHALT";"Gehalt 01/2024 Pers-Nr 004711";"Beispiel GmbH";"DE00 4326 7712 6325 5602";"2.690,00";"EUR"
```

Savings account, preamble, header and a transfer row:

```
"Kontoart";"Tagesgeldkonto"
"Zeitraum";"2024-01-01 bis 2026-09-30"
"Anfangssaldo";"9.000,00 EUR"

"Buchungstag";"Wertstellung";"Buchungstext";"Verwendungszweck";"Auftraggeber/Empfänger";"IBAN";"Soll";"Haben";"Währung"
"2024-01-31";"2024-01-31";"EINZAHLUNG";"Umbuchung Girokonto";"Eigenes Girokonto";"DE00 0000 0000 0000 0001 01";"";"7,00";"EUR"
```

## The same in both files

- Semicolon-delimited, ISO-8859-1 (so `ä` and `ß` need the right encoding), every field quoted.
- German number format: `1.234,56` (dot for thousands, comma for decimals).
- Newest booking first.
- The same columns for booking text, purpose, counterparty and IBAN, with a `Währung` column.

### Mess injected into both files

| Mess | What it looks like |
|---|---|
| `duplicate` | A row appears twice, identical. |
| `text_noise` | Purpose and counterparty in upper or lower case, a double space, a trailing space, or `ae`/`oe`/`ue` instead of umlauts. |
| `missing_purpose` | Some card payments have an empty purpose. |
| `out_of_order` | A few neighbouring rows are swapped. |

Example of a card payment row:

```
"28.09.2026";"28.09.2026";"KARTENZAHLUNG";"Zalando 9992 Karte 4711";"Zalando";"";"-36,06";"EUR"
```

## Checking your cleaning

- `data/truth/ledger.csv` is the clean ledger with a running balance per account (`balance_after_cents`).
- `data/truth/mess_log.csv` lists every injected problem: the file, the row number in that file (after the header and any preamble), the truth id and the kind of mess.
- After cleaning, the row count per account should equal the ledger's row count, and the closing balances should match.
- Opening cash is €3,000.00 in the current account and €9,000.00 in savings.
- Regenerate with `python3 -m generator.run`. The seed is fixed, so the files are reproducible.
