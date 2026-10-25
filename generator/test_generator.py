"""Run from the repo root: python3 -m generator.test_generator"""
import csv
import re
import tempfile
from pathlib import Path

from generator.bank_csv import ENCODING, HEADER_SALARY, HEADER_SAVINGS
from generator.ledger import SALARY, SAVINGS, build_ledger, opening_balances
from generator.run import generate, load

AMOUNT = re.compile(r"^-?\d{1,3}(\.\d{3})*,\d{2}$")


def _read(path):
    with open(path, encoding=ENCODING, newline="") as f:
        return list(csv.reader(f, delimiter=";"))


def _generated():
    persona, cfg = load()
    out = Path(tempfile.mkdtemp())
    generate(persona, cfg, out)
    return persona, cfg, out


def test_deterministic():
    persona, cfg = load()
    assert build_ledger(persona, cfg) == build_ledger(persona, cfg)


def test_inflation_matches_the_approved_assumption():
    import math
    import yaml
    _, cfg = load()
    rates = yaml.safe_load(Path("assumptions/inflation.yaml").read_text())["annual_rates_pct"]
    compound = math.prod(1 + v / 100 for v in rates.values()) ** (1 / len(rates)) - 1
    assert len(rates) == 10 and abs(cfg["inflation_per_year"] - compound) < 0.0005


def test_first_month_matches_persona():
    persona, cfg = load()
    jan = [r for r in build_ledger(persona, cfg) if (r["date"].year, r["date"].month) == (2024, 1)]
    total = lambda cat: sum(r["amount"] for r in jan if r["category"] == cat)
    assert total("salary") == 269_000
    assert total("fixed") == -121_000
    assert total("contribution_etf") == -53_800
    assert total("contribution_gold") == -9_000
    variable = -sum(r["amount"] for r in jan if r["account"] == SALARY
                    and r["category"] not in ("salary", "fixed", "sweep")
                    and not r["category"].startswith("contribution"))
    assert 65_000 < variable < 105_000


def test_balances_reconcile_and_cash_matches_persona():
    persona, cfg = load()
    rows = build_ledger(persona, cfg)
    opening = opening_balances(persona, cfg)
    assert sum(opening.values()) == 1_200_000
    for account in (SALARY, SAVINGS):
        mine = [r for r in rows if r["account"] == account]
        assert opening[account] + sum(r["amount"] for r in mine) == mine[-1]["balance_after"]


def test_current_account_stays_positive():
    persona, cfg = load()
    assert min(r["balance_after"] for r in build_ledger(persona, cfg) if r["account"] == SALARY) > 0


def test_transfers_net_to_zero():
    persona, cfg = load()
    assert sum(r["amount"] for r in build_ledger(persona, cfg) if r["category"] == "sweep") == 0


def test_the_two_formats_differ_in_three_ways():
    _, _, out = _generated()
    salary = _read(next((out / "raw").glob("salary_*.csv")))
    savings = _read(next((out / "raw").glob("savings_*.csv")))

    assert salary[0] == HEADER_SALARY                                   # no preamble
    assert [row[0] for row in savings[:3]] == ["Kontoart", "Zeitraum", "Anfangssaldo"]
    assert savings[3] == [] and savings[4] == HEADER_SAVINGS            # preamble, then header

    for row in salary[1:]:
        assert len(row) == 8 and re.fullmatch(r"\d\d\.\d\d\.\d{4}", row[0]) and AMOUNT.match(row[6])
    for row in savings[5:]:
        assert len(row) == 9 and re.fullmatch(r"\d{4}-\d\d-\d\d", row[0])
        assert (row[6] == "") != (row[7] == "")                          # one of Soll or Haben
        assert AMOUNT.match(row[6] or row[7])


def test_mess_log_lets_you_recover_the_truth():
    _, _, out = _generated()
    with open(out / "truth" / "mess_log.csv", encoding="utf-8", newline="") as f:
        log = list(csv.DictReader(f))
    with open(out / "truth" / "ledger.csv", encoding="utf-8", newline="") as f:
        truth = list(csv.DictReader(f))
    for account, pattern in ((SALARY, "salary_*.csv"), (SAVINGS, "savings_*.csv")):
        path = next((out / "raw").glob(pattern))
        data_rows = len(_read(path)) - (1 if account == SALARY else 5)
        duplicates = sum(1 for l in log if l["file"] == path.name and l["issue"] == "duplicate")
        assert data_rows - duplicates == sum(1 for t in truth if t["account"] == account)
        assert all(1 <= int(l["data_row"]) <= data_rows for l in log if l["file"] == path.name)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
