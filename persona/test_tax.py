from tax import (GRUNDFREIBETRAG, ZONE2_END, ZONE3_END, ZONE4_END,
                 BBG_PENSION_UNEMPLOYMENT, PENSION_RATE, net_pay, tariff)


def test_no_tax_up_to_grundfreibetrag():
    assert tariff(GRUNDFREIBETRAG) == 0
    assert tariff(GRUNDFREIBETRAG + 1) >= 0


def test_tariff_is_continuous_between_zones():
    for boundary in (ZONE2_END, ZONE3_END, ZONE4_END):
        assert 0 <= tariff(boundary + 1) - tariff(boundary) <= 1


def test_net_rises_with_gross():
    nets = [net_pay(g)["net_annual"] for g in range(20_000, 200_000, 5_000)]
    assert nets == sorted(nets)


def test_pension_contribution_is_capped():
    assert net_pay(200_000)["pension"] == round(PENSION_RATE * BBG_PENSION_UNEMPLOYMENT, 2)


def test_class_iv_matches_class_i_and_iii_pays_less_tax():
    assert net_pay(50_000, "IV") == net_pay(50_000, "I")
    assert net_pay(50_000, "III")["income_tax"] < net_pay(50_000, "I")["income_tax"]


def test_index_scales_everything():
    base = net_pay(50_000)
    scaled = net_pay(100_000, index=2.0)
    assert abs(scaled["net_annual"] - 2 * base["net_annual"]) < 0.05


def test_persona_net_is_plausible():
    assert 2_500 <= net_pay(50_000)["net_monthly"] <= 2_900


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
