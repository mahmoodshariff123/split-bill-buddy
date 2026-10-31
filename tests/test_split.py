from app.checks import check_plan, check_receipt
from app.split import allocate, balances, convert_shares, fx_rate, settle_up, split_receipt

DINNER = {"items": [{"name": "Fish Curry", "amount": 36.0}, {"name": "Beer", "amount": 24.0},
                    {"name": "Mango Lassi", "amount": 5.0}], "tax": 5.2, "tip": 0, "total": 70.2}


def test_allocate_always_adds_up():
    for total in (100, 101, 7020, 1, -7):
        for w in ([1, 1, 1], [3, 1], [0.2, 0.3, 0.5]):
            assert sum(allocate(total, w)) == total


def test_sara_did_not_drink():
    shares = split_receipt(DINNER, [["Ali", "Ravi", "Sara"], ["Ali", "Ravi"], ["Sara"]])
    assert sum(shares.values()) == 7020
    assert shares["Ali"] == shares["Ravi"]
    assert shares["Sara"] < shares["Ali"]


def test_tax_shared_in_proportion():
    shares = split_receipt(DINNER, [["Ali", "Ravi", "Sara"], ["Ali", "Ravi"], ["Sara"]])
    assert shares == {"Ali": 2592, "Ravi": 2592, "Sara": 1836}


def test_fx_conversion_keeps_total():
    taxi = convert_shares({"Ali": 17500, "Ravi": 17500, "Sara": 17500}, fx_rate("THB", "USD"))
    assert sum(taxi.values()) == 1470


def test_balances_and_fewest_payments():
    g = {"members": [{"name": n} for n in ("Ali", "Ravi", "Sara")], "payments": [],
         "expenses": [{"paid_by": "Ali", "shares": {"Ali": 2340, "Ravi": 2340, "Sara": 2340}},
                      {"paid_by": "Ravi", "shares": {"Ali": 300, "Ravi": 300, "Sara": 300}}]}
    bal = balances(g)
    assert sum(bal.values()) == 0
    plan = settle_up(bal)
    assert {(p["from"], p["to"]) for p in plan} <= {("Sara", "Ali"), ("Ravi", "Ali"), ("Sara", "Ravi")}
    assert len(plan) <= 2
    g["payments"] = [{"from": p["from"], "to": p["to"], "cents": p["cents"], "status": "COMPLETED"} for p in plan]
    assert all(v == 0 for v in balances(g).values())


def test_unknown_names_fall_back_to_everyone():
    people, _, warnings = check_plan({"assignments": [{"item_index": 0, "members": ["Bob"], "reason": ""}]},
                                     2, ["Ali", "Ravi"])
    assert people == [["Ali", "Ravi"], ["Ali", "Ravi"]] and warnings


def test_names_match_case_insensitively():
    people, _, _ = check_plan({"assignments": [{"item_index": 0, "members": ["sara"], "reason": "lassi"}]},
                              1, ["Ali", "Sara"])
    assert people == [["Sara"]]


def test_receipt_total_mismatch_is_flagged():
    bad = {**DINNER, "total": 90.0, "confidence": 0.9}
    assert any("total" in w for w in check_receipt(bad))
    assert check_receipt({**DINNER, "confidence": 0.95}) == []


def test_equal_split_with_tax_stays_equal():
    receipt = {"items": [{"amount": 36}, {"amount": 24}, {"amount": 5}], "tax": 5.2, "total": 70.2}
    everyone = [["Ali", "Ravi", "Sara"]] * 3
    assert split_receipt(receipt, everyone) == {"Ali": 2340, "Ravi": 2340, "Sara": 2340}
