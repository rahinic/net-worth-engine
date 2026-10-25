"""Writes the truth ledger as two German-bank-style CSV exports, with mess.

Shared format: semicolon-delimited, ISO-8859-1, every field quoted, amounts as
1.234,56, newest booking first.

The two files differ in exactly three ways:
  1. Dates: salary account 31.01.2024, savings account 2024-01-31.
  2. Amounts: salary account one signed Betrag column, savings account separate
     Soll (debit) and Haben (credit) columns.
  3. Preamble: savings account has three metadata lines and a blank line above
     the header, salary account starts with the header.

Mess is added to the exports only, so the truth ledger stays clean. Every
injected problem is returned for the mess log: duplicated rows, rows with
changed case, spacing or umlauts, rows with the purpose missing, and rows out
of order.
"""
import csv

HEADER_SALARY = ["Buchungstag", "Wertstellung", "Buchungstext", "Verwendungszweck",
                 "Auftraggeber/Empfänger", "IBAN", "Betrag", "Währung"]
HEADER_SAVINGS = ["Buchungstag", "Wertstellung", "Buchungstext", "Verwendungszweck",
                  "Auftraggeber/Empfänger", "IBAN", "Soll", "Haben", "Währung"]
ENCODING = "latin-1"
UMLAUTS = {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"}


def fmt_amount(cents: int) -> str:
    euros, rest = divmod(abs(cents), 100)
    return f"{'-' if cents < 0 else ''}{euros:,}".replace(",", ".") + f",{rest:02d}"


def fmt_date_de(d) -> str:
    return d.strftime("%d.%m.%Y")


def fmt_date_iso(d) -> str:
    return d.strftime("%Y-%m-%d")


def _noisy(text: str, rng) -> tuple:
    kind = rng.choice(["upper", "lower", "double_space", "trailing_space", "ascii_umlauts"])
    if kind == "ascii_umlauts":
        changed = "".join(UMLAUTS.get(c, c) for c in text)
        if changed == text:
            kind = "upper"
    if kind == "upper":
        changed = text.upper()
    elif kind == "lower":
        changed = text.lower()
    elif kind == "double_space":
        changed = text.replace(" ", "  ", 1)
    elif kind == "trailing_space":
        changed = text + " "
    return changed, kind


def make_export(rows: list, mess: dict, rng) -> list:
    """Newest first, with mess. Each export row keeps its truth_id and its issues."""
    ordered = sorted(rows, key=lambda r: (r["date"], r["seq"], r["i"]), reverse=True)
    out = []
    for r in ordered:
        e = {k: r[k] for k in ("date", "text", "purpose", "counterparty", "iban", "amount")}
        e["truth_id"], e["issues"] = r["truth_id"], []
        if rng.random() < mess["text_noise_rate"]:
            e["purpose"], kind = _noisy(e["purpose"], rng)
            e["counterparty"], _ = _noisy(e["counterparty"], rng) if e["counterparty"] else ("", kind)
            e["issues"].append(f"text_noise:{kind}")
        if e["text"] == "KARTENZAHLUNG" and rng.random() < mess["missing_purpose_rate"]:
            e["purpose"] = ""
            e["issues"].append("missing_purpose")
        out.append(e)
        if rng.random() < mess["duplicate_rate"]:
            out.append({**e, "issues": e["issues"] + ["duplicate"]})
    k = 0
    while k < len(out) - 1:
        if rng.random() < mess["out_of_order_rate"]:
            out[k], out[k + 1] = out[k + 1], out[k]
            out[k]["issues"] = out[k]["issues"] + ["out_of_order"]
            out[k + 1]["issues"] = out[k + 1]["issues"] + ["out_of_order"]
            k += 1
        k += 1
    return out


def _writer(f):
    return csv.writer(f, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\r\n")


def write_salary_csv(path, export: list) -> None:
    with open(path, "w", encoding=ENCODING, newline="") as f:
        w = _writer(f)
        w.writerow(HEADER_SALARY)
        for e in export:
            d = fmt_date_de(e["date"])
            w.writerow([d, d, e["text"], e["purpose"], e["counterparty"], e["iban"],
                        fmt_amount(e["amount"]), "EUR"])


def write_savings_csv(path, export: list, opening: int, start, end) -> None:
    with open(path, "w", encoding=ENCODING, newline="") as f:
        w = _writer(f)
        w.writerow(["Kontoart", "Tagesgeldkonto"])
        w.writerow(["Zeitraum", f"{fmt_date_iso(start)} bis {fmt_date_iso(end)}"])
        w.writerow(["Anfangssaldo", f"{fmt_amount(opening)} EUR"])
        w.writerow([])
        w.writerow(HEADER_SAVINGS)
        for e in export:
            d = fmt_date_iso(e["date"])
            debit = fmt_amount(-e["amount"]) if e["amount"] < 0 else ""
            credit = fmt_amount(e["amount"]) if e["amount"] > 0 else ""
            w.writerow([d, d, e["text"], e["purpose"], e["counterparty"], e["iban"],
                        debit, credit, "EUR"])
