"""Writes the two dbt seed tables from the persona and the generator config.

merchant_categories: counterparty key -> category. In real life an analyst keeps this
  by hand; here it is derived from config.yaml so it always matches the generator.
opening_balances: where each account and holding starts.
"""
import csv
from pathlib import Path

from generator.ledger import SALARY, SAVINGS, opening_balances


def counterparty_key(name: str) -> str:
    """Upper case, umlauts spelled out, single spaces. The dbt model does the same."""
    key = name.replace("ß", "ss").upper()
    for umlaut, ascii_ in (("Ä", "AE"), ("Ö", "OE"), ("Ü", "UE")):
        key = key.replace(umlaut, ascii_)
    return " ".join(key.split())


def merchant_categories(cfg: dict) -> list:
    rows = [("Beispiel GmbH", "salary"),
            ("Eigenes Tagesgeldkonto", "sweep"),
            ("Eigenes Girokonto", "sweep"),
            (cfg["contributions"]["etf"]["counterparty"], "contribution_etf"),
            (cfg["contributions"]["gold"]["counterparty"], "contribution_gold")]
    rows += [(item["counterparty"], "fixed") for item in cfg["fixed_costs"]]
    for name, cat in cfg["variable_categories"].items():
        rows += [(merchant, name) for merchant in cat["merchants"]]
    keyed = {counterparty_key(name): category for name, category in rows}
    assert len(keyed) == len(rows), "two counterparties share a key"
    return sorted(keyed.items())


def write_seeds(persona: dict, cfg: dict, seed_dir: Path) -> None:
    seed_dir.mkdir(parents=True, exist_ok=True)
    with open(seed_dir / "merchant_categories.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["counterparty_key", "category"])
        w.writerows(merchant_categories(cfg))
    opening = opening_balances(persona, cfg)
    start = persona["start_net_worth_eur"]
    with open(seed_dir / "opening_balances.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["account", "opening_eur"])
        w.writerow([SALARY, f"{opening[SALARY] / 100:.2f}"])
        w.writerow([SAVINGS, f"{opening[SAVINGS] / 100:.2f}"])
        w.writerow(["etf", f"{start['etf']:.2f}"])
        w.writerow(["gold", f"{start['gold']:.2f}"])
