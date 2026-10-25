"""Builds the clean truth ledger behind the two synthetic bank accounts.

Illustrative simulation, synthetic data. Amounts are integer cents.

Accounts:
  salary   current account: salary in, fixed and variable costs, ETF and gold
           standing orders out, and a transfer to or from savings after payday.
  savings  savings account: those transfers plus quarterly interest.

Rules:
  - Net pay comes from persona/tax.py, with the tax brackets indexed by the
    inflation placeholder. Gross steps up at each raise.
  - Contributions are flat. Costs grow with inflation (see config.yaml).
  - Salary lands on the last business day. After it, the current account is
    brought back to the target balance by a transfer to or from savings, so
    the persona's leftover cash ends up in savings. Weekdays only, no holidays.
  - Interest is credited quarterly on the end-of-quarter balance; it is assumed
    to sit inside the tax-free allowance, so no tax is booked on it.
"""
import calendar
import hashlib
import random
from datetime import date, timedelta

from persona.tax import net_pay

SALARY, SAVINGS = "salary", "savings"

# Order of rows booked on the same day
SEQ_SALARY, SEQ_FIXED, SEQ_CONTRIB, SEQ_VARIABLE, SEQ_SWEEP, SEQ_INTEREST = 10, 20, 30, 40, 90, 95


def cents(eur: float) -> int:
    return round(eur * 100)


def fake_iban(key: str) -> str:
    digits = "".join(str(int(c, 16) % 10) for c in hashlib.md5(key.encode()).hexdigest())[:16]
    return "DE00 " + " ".join(digits[i:i + 4] for i in range(0, 16, 4))


def months(start: date, end: date):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def last_business_day(y: int, m: int) -> date:
    d = date(y, m, calendar.monthrange(y, m)[1])
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def pay_date(y: int, m: int, day: int) -> date:
    """The given day of the month, moved to the next weekday, never past month end."""
    d = date(y, m, min(day, calendar.monthrange(y, m)[1]))
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return min(d, last_business_day(y, m))


def opening_balances(persona: dict, cfg: dict) -> dict:
    cash = cents(persona["start_net_worth_eur"]["savings"])
    current = cents(cfg["current_account_target_eur"])
    return {SALARY: current, SAVINGS: cash - current}


def build_ledger(persona: dict, cfg: dict) -> list:
    """Returns the truth rows, sorted by account, date and booking order."""
    rng = random.Random(cfg["seed"])
    start, end = persona["simulation"]["start_date"], cfg["statements_end"]
    infl = cfg["inflation_per_year"]
    raise_ = persona["income"]["raise"]
    tax = persona["tax"]
    monthly = persona["monthly_eur"]
    target = cents(cfg["current_account_target_eur"])
    iban = {SALARY: cfg["salary_iban"], SAVINGS: cfg["savings_iban"]}

    rows = []

    def add(account, d, seq, text, purpose, counterparty, amount, category, row_iban=""):
        rows.append({"account": account, "date": d, "seq": seq, "i": len(rows), "text": text,
                     "purpose": purpose, "counterparty": counterparty, "iban": row_iban,
                     "amount": amount, "category": category})

    bal = opening_balances(persona, cfg)
    for n, (y, m) in enumerate(months(start, end)):
        idx = (1 + infl) ** (n / 12)
        idx_year = (1 + infl) ** (n // 12)
        fmt = {"mm": f"{m:02d}", "yyyy": y}
        payday = last_business_day(y, m)
        month_start = len(rows)

        steps = n // (raise_["every_years"] * 12)
        gross = persona["income"]["gross_annual_eur"] * (1 + raise_["pct"] / 100) ** steps
        net = net_pay(gross, tax["tax_class"], childless=tax["children"] == 0, index=idx)
        add(SALARY, payday, SEQ_SALARY, "GEHALT", f"Gehalt {m:02d}/{y} Pers-Nr 004711",
            "Beispiel GmbH", cents(net["net_monthly"]), "salary", fake_iban("employer"))

        for item in cfg["fixed_costs"]:
            factor = {"monthly": idx, "yearly": idx_year, "none": 1.0}[item["index"]]
            add(SALARY, pay_date(y, m, item["day"]), SEQ_FIXED, item["text"],
                item["purpose"].format(**fmt), item["counterparty"],
                -cents(item["eur"] * factor), "fixed", fake_iban(item["counterparty"]))

        for key, eur in (("etf", monthly["etf_savings_plan"]), ("gold", monthly["indian_gold_scheme"])):
            item = cfg["contributions"][key]
            add(SALARY, pay_date(y, m, item["day"]), SEQ_CONTRIB, item["text"],
                item["purpose"].format(**fmt), item["counterparty"], -cents(eur),
                f"contribution_{key}", fake_iban(item["counterparty"]))

        total = cents(monthly["variable_costs"] * idx * (1 + rng.gauss(0, cfg["variable_cost_noise"])))
        names = list(cfg["variable_categories"])
        left = total
        for k, name in enumerate(names):
            cat = cfg["variable_categories"][name]
            cat_total = left if k == len(names) - 1 else round(total * cat["share"])
            left -= cat_total
            count = rng.randint(*cat["count"])
            weights = [rng.uniform(0.4, 1.6) for _ in range(count)]
            parts = [round(cat_total * w / sum(weights)) for w in weights]
            parts[-1] += cat_total - sum(parts)
            for amount in parts:
                merchant = rng.choice(cat["merchants"])
                day = date(y, m, rng.randint(1, payday.day))
                purpose = f"{merchant} {rng.randint(1000, 9999)} Karte 4711"
                add(SALARY, day, SEQ_VARIABLE, cat["text"], purpose, merchant, -amount, name)

        bal[SALARY] += sum(r["amount"] for r in rows[month_start:])
        diff = round((bal[SALARY] - target) / 100) * 100
        if diff:
            add(SALARY, payday, SEQ_SWEEP, "UMBUCHUNG", "Umbuchung Tagesgeld",
                "Eigenes Tagesgeldkonto", -diff, "sweep", iban[SAVINGS])
            add(SAVINGS, payday, SEQ_SWEEP, "EINZAHLUNG" if diff > 0 else "AUSZAHLUNG",
                "Umbuchung Girokonto", "Eigenes Girokonto", diff, "sweep", iban[SALARY])
            bal[SALARY] -= diff
            bal[SAVINGS] += diff
        if m % 3 == 0:
            interest = round(bal[SAVINGS] * cfg["savings_interest_per_year"] / 4)
            add(SAVINGS, payday, SEQ_INTEREST, "ABSCHLUSS", f"Zinsabschluss Q{m // 3}/{y}",
                "", interest, "interest")
            bal[SAVINGS] += interest

    rows.sort(key=lambda r: (r["account"], r["date"], r["seq"], r["i"]))
    opening = opening_balances(persona, cfg)
    running = dict(opening)
    for k, r in enumerate(rows, start=1):
        running[r["account"]] += r["amount"]
        r["truth_id"] = f"T{k:05d}"
        r["balance_after"] = running[r["account"]]
    return rows
