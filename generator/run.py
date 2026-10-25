"""Generates the synthetic bank statements: python3 -m generator.run [--out data]

Writes, under the output folder:
  raw/salary_account_<start>_<end>.csv    messy export, salary account
  raw/savings_account_<start>_<end>.csv   messy export, savings account
  truth/ledger.csv                        clean ledger with running balances
  truth/mess_log.csv                      every injected problem and where it is
and the dbt seed tables in dbt/seeds/.
"""
import argparse
import csv
import random
from pathlib import Path

import yaml

from generator.bank_csv import make_export, write_salary_csv, write_savings_csv
from generator.ledger import SALARY, SAVINGS, build_ledger, opening_balances
from generator.seeds import write_seeds

ROOT = Path(__file__).resolve().parent.parent


def load():
    persona = yaml.safe_load((ROOT / "persona" / "persona.yaml").read_text(encoding="utf-8"))
    cfg = yaml.safe_load((Path(__file__).parent / "config.yaml").read_text(encoding="utf-8"))
    return persona, cfg


def generate(persona: dict, cfg: dict, out: Path) -> dict:
    start, end = persona["simulation"]["start_date"], cfg["statements_end"]
    span = f"{start:%Y-%m}_{end:%Y-%m}"
    (out / "raw").mkdir(parents=True, exist_ok=True)
    (out / "truth").mkdir(parents=True, exist_ok=True)

    ledger = build_ledger(persona, cfg)
    opening = opening_balances(persona, cfg)
    rng = random.Random(cfg["seed"] + 1)
    salary_export = make_export([r for r in ledger if r["account"] == SALARY], cfg["mess"], rng)
    savings_export = make_export([r for r in ledger if r["account"] == SAVINGS], cfg["mess"], rng)

    salary_file, savings_file = f"salary_account_{span}.csv", f"savings_account_{span}.csv"
    write_salary_csv(out / "raw" / salary_file, salary_export)
    write_savings_csv(out / "raw" / savings_file, savings_export, opening[SAVINGS], start, end)

    with open(out / "truth" / "ledger.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["truth_id", "account", "booking_date", "text", "purpose", "counterparty",
                    "iban", "amount_cents", "category", "balance_after_cents"])
        for r in ledger:
            w.writerow([r["truth_id"], r["account"], r["date"].isoformat(), r["text"], r["purpose"],
                        r["counterparty"], r["iban"], r["amount"], r["category"], r["balance_after"]])

    issues = 0
    with open(out / "truth" / "mess_log.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "data_row", "truth_id", "issue"])
        for name, export in ((salary_file, salary_export), (savings_file, savings_export)):
            for n, e in enumerate(export, start=1):
                for issue in e["issues"]:
                    w.writerow([name, n, e["truth_id"], issue])
                    issues += 1
    return {"ledger_rows": len(ledger), "salary_export_rows": len(salary_export),
            "savings_export_rows": len(savings_export), "issues": issues}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data"))
    args = ap.parse_args()
    persona, cfg = load()
    print(generate(persona, cfg, Path(args.out)))
    write_seeds(persona, cfg, ROOT / "dbt" / "seeds")
