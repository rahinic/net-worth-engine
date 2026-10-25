"""Simplified German net pay for the synthetic persona.

Illustrative simulation, not tax advice. Parameters are the 2025 values for an
employee with statutory health insurance, no church tax and no kinder.

What it does:
  1. Employee social contributions on gross pay, capped at the contribution
     ceilings (Beitragsbemessungsgrenzen).
  2. Taxable income = gross - Werbungskosten-Pauschbetrag - deductible
     contributions.
  3. Income tax from the 2025 tariff (section 32a EStG), plus Solidaritaetszuschlag.
  4. Net = gross - social contributions - income tax - Soli.

Simplifications, on purpose:
  - Annual figures. No monthly Lohnsteuer withholding, so no year-end true-up.
  - Deductible contributions: employee pension share, 96% of the health share
    (the 4% Krankengeld part is excluded) and the care share. Unemployment
    insurance is not deducted, because basic health and care contributions
    already use up the allowance for other contributions.
  - No other allowances or deductions. Salary is the only income.
  - Tax classes: I and IV are the same here (IV assumes a spouse on a similar
    income). III is splitting with a spouse who has no income.
  - One year's rules for every simulated year. Pass `index` (cumulative
    inflation since the start) to scale all thresholds, allowances and
    ceilings, so wage growth is not eaten by frozen brackets. Rates stay fixed.
  - The Soli threshold uses the 2025 value, without the 2026 increase.
"""
import math

# Income tax tariff 2025 (section 32a EStG), EUR per year of taxable income
GRUNDFREIBETRAG = 12_096
ZONE2_END = 17_443
ZONE3_END = 68_480
ZONE4_END = 277_825
WERBUNGSKOSTEN_PAUSCHBETRAG = 1_230

# Solidaritaetszuschlag
SOLI_RATE = 0.055
SOLI_PHASE_IN = 0.119
SOLI_FREIGRENZE = 19_950   # on income tax, single; doubled for splitting

# Contribution ceilings 2025, EUR per year of gross pay
BBG_PENSION_UNEMPLOYMENT = 96_600
BBG_HEALTH_CARE = 66_150

# Employee shares of the contribution rates
PENSION_RATE = 0.093
UNEMPLOYMENT_RATE = 0.013
HEALTH_RATE = 0.073 + 0.0125     # general rate + half the 2.5% average extra contribution
CARE_RATE = 0.018
CARE_CHILDLESS_SURCHARGE = 0.006
KRANKENGELD_SHARE = 0.04


def tariff(taxable_income: int) -> int:
    """Income tax for a single person, EUR per year, rounded down."""
    x = taxable_income
    if x <= GRUNDFREIBETRAG:
        return 0
    if x <= ZONE2_END:
        y = (x - GRUNDFREIBETRAG) / 10_000
        return math.floor((932.30 * y + 1_400) * y)
    if x <= ZONE3_END:
        z = (x - ZONE2_END) / 10_000
        return math.floor((176.64 * z + 2_397) * z + 1_015.13)
    if x <= ZONE4_END:
        return math.floor(0.42 * x - 10_911.92)
    return math.floor(0.45 * x - 19_246.67)


def net_pay(gross_annual: float, tax_class: str = "I", childless: bool = True,
            index: float = 1.0) -> dict:
    """Net pay from gross pay. All amounts are EUR per year unless named monthly.

    index is the cumulative inflation factor since 2025 (1.0 = 2025 prices).
    """
    if tax_class not in ("I", "III", "IV"):
        raise ValueError(f"unsupported tax class: {tax_class}")

    # Work in 2025 prices, then scale every amount back by `index`.
    g = gross_annual / index
    pension = PENSION_RATE * min(g, BBG_PENSION_UNEMPLOYMENT)
    unemployment = UNEMPLOYMENT_RATE * min(g, BBG_PENSION_UNEMPLOYMENT)
    health = HEALTH_RATE * min(g, BBG_HEALTH_CARE)
    care = (CARE_RATE + (CARE_CHILDLESS_SURCHARGE if childless else 0)) * min(g, BBG_HEALTH_CARE)
    social = pension + unemployment + health + care

    deductible = pension + health * (1 - KRANKENGELD_SHARE) + care
    taxable = max(0, math.floor(g - WERBUNGSKOSTEN_PAUSCHBETRAG - deductible))

    splitting = tax_class == "III"
    income_tax = 2 * tariff(taxable // 2) if splitting else tariff(taxable)
    freigrenze = SOLI_FREIGRENZE * (2 if splitting else 1)
    soli = min(SOLI_RATE * income_tax, SOLI_PHASE_IN * max(0, income_tax - freigrenze))

    net = g - social - income_tax - soli
    parts = {
        "gross": g, "pension": pension, "unemployment": unemployment,
        "health": health, "care": care, "social_total": social,
        "taxable_income": taxable, "income_tax": income_tax, "soli": soli,
        "net_annual": net,
    }
    out = {k: round(v * index, 2) for k, v in parts.items()}
    out["net_monthly"] = round(net * index / 12, 2)
    return out


if __name__ == "__main__":
    for gross in (50_000, 55_000, 60_500):
        for tax_class in ("I", "III"):
            r = net_pay(gross, tax_class)
            print(f"gross {gross:>6,}  class {tax_class:<3}  "
                  f"social {r['social_total']:>9,.0f}  tax {r['income_tax']:>7,.0f}  "
                  f"net/month {r['net_monthly']:>8,.2f}")
