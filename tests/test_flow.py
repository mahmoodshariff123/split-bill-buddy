"""Full flow in demo mode: no PayPal or AI keys needed."""
import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SPLITBILL_DATA", str(tmp_path))
    for var in ("PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET", "GEMINI_API_KEY"):
        monkeypatch.setenv(var, "")
    from app import config, main, store
    importlib.reload(config); importlib.reload(store); importlib.reload(main)
    return TestClient(main.app), config.SAMPLES_DIR


def add(c, samples, gid, name, paid_by="Ali"):
    with open(samples / name, "rb") as f:
        return c.post(f"/api/groups/{gid}/expenses", data={"paid_by": paid_by},
                      files={"receipt": (name, f, "image/jpeg")})


def test_trip_end_to_end(client):
    c, s = client
    g = c.post("/api/groups", json={"name": "Goa Trip", "currency": "USD",
               "members": [{"name": "Ali"}, {"name": "Ravi"}, {"name": "Sara"}]}).json()
    g = add(c, s, g["id"], "dinner_receipt.jpg").json()
    assert g["total_spent"] == 7020
    g = add(c, s, g["id"], "taxi_receipt.jpg", paid_by="Ravi").json()
    assert g["total_spent"] == 7020 + 1470
    assert any("Converted THB" in w for w in g["expenses"][1]["warnings"])
    assert sum(g["balances"].values()) == 0
    for debt in g["settle"]:
        order = c.post(f"/api/groups/{g['id']}/settle/order", json={"from_name": debt["from"], "to_name": debt["to"]}).json()
        g = c.post(f"/api/groups/{g['id']}/settle/capture", json={"order_id": order["id"]}).json()
    assert g["settle"] == [] and all(v == 0 for v in g["balances"].values())


def test_rejects_unknown_payer_and_non_images(client):
    c, s = client
    g = c.post("/api/groups", json={"name": "T", "members": [{"name": "A"}, {"name": "B"}]}).json()
    assert add(c, s, g["id"], "dinner_receipt.jpg", paid_by="Zed").status_code == 400
    r = c.post(f"/api/groups/{g['id']}/expenses", data={"paid_by": "A"}, files={"receipt": ("x.txt", b"hi", "text/plain")})
    assert r.status_code == 400


def test_needs_two_distinct_friends(client):
    c, _ = client
    assert c.post("/api/groups", json={"name": "T", "members": [{"name": "A"}]}).status_code == 400
    assert c.post("/api/groups", json={"name": "T", "members": [{"name": "A"}, {"name": "a"}]}).status_code == 400


def test_cannot_pay_a_debt_that_does_not_exist(client):
    c, _ = client
    g = c.post("/api/groups", json={"name": "T", "members": [{"name": "A"}, {"name": "B"}]}).json()
    assert c.post(f"/api/groups/{g['id']}/settle/order", json={"from_name": "A", "to_name": "B"}).status_code == 409


def _trip(c):
    return c.post("/api/groups", json={"name": "Goa Trip", "currency": "USD",
                  "members": [{"name": "Ali"}, {"name": "Ravi"}, {"name": "Sara"}]}).json()


def test_blurry_photo_gets_a_warning(tmp_path):
    from PIL import Image, ImageFilter
    from app import checks, config
    sharp = config.SAMPLES_DIR / "dinner_receipt.jpg"
    blurry = tmp_path / "blurry.jpg"
    Image.open(sharp).filter(ImageFilter.GaussianBlur(4)).save(blurry)
    assert checks.check_photo(sharp) == []
    assert "clearer photo" in checks.check_photo(blurry)[0]
    with __import__("pytest").raises(ValueError):
        checks.check_photo(tmp_path / "missing.jpg")


def test_unreadable_receipt_is_rejected():
    import pytest as _pytest
    from app import checks
    with _pytest.raises(ValueError, match="clearer photo"):
        checks.check_receipt({"items": [{"amount": 5}], "total": 5, "confidence": 0.3})


def test_manual_fix_recalculates_shares(client):
    c, s = client
    g = _trip(c)
    g = add(c, s, g["id"], "dinner_receipt.jpg").json()
    e = g["expenses"][0]
    items = [{"name": i["name"], "quantity": i["quantity"], "amount": i["amount"]} for i in e["items"]]
    items[2]["amount"] = 8.0
    r = c.put(f"/api/groups/{g['id']}/expenses/{e['id']}", json={"items": items, "tax": 5.2, "tip": 0, "total": 73.2})
    assert r.status_code == 200
    fixed = r.json()["expenses"][0]
    assert fixed["checked_by_user"] and sum(fixed["shares"].values()) == 7320
    assert sum(r.json()["balances"].values()) == 0
