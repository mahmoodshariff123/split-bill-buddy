"""Split Bill Buddy web server.

Flow: create a trip with friends -> upload receipt photos -> AI reads them and applies
plain-English instructions -> code does the math -> each friend pays back with PayPal.
"""
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import ai, checks, config, split, store
from .paypal import PayPalError, get_client

app = FastAPI(title="Split Bill Buddy")
paypal = get_client()
IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp"}
STATIC_DIR = config.ROOT / "static"


class Member(BaseModel):
    name: str
    email: str = ""


class GroupIn(BaseModel):
    name: str
    currency: str = "USD"
    members: list[Member]


def _group_or_404(group_id: str) -> dict:
    group = store.get(group_id)
    if not group:
        raise HTTPException(404, "Trip not found")
    return group


def _view(group: dict) -> dict:
    bal = split.balances(group)
    return {
        **group,
        "balances": bal,
        "settle": split.settle_up(bal),
        "total_spent": sum(sum(e["shares"].values()) for e in group["expenses"]),
    }


@app.get("/api/config")
def get_config():
    return {
        "paypal_mode": paypal.mode,
        "paypal_client_id": config.PAYPAL_CLIENT_ID if config.paypal_live() else None,
        "ai_mode": f"gemini:{config.GEMINI_MODEL}" if config.ai_live() else "demo",
        "currencies": sorted(split.FX_TO_USD),
    }


@app.get("/api/groups")
def list_groups():
    return [_view(g) for g in store.list_groups()]


@app.post("/api/groups")
def create_group(body: GroupIn):
    names = [m.name.strip() for m in body.members if m.name.strip()]
    if len(names) < 2:
        raise HTTPException(400, "Add at least 2 friends")
    if len({n.lower() for n in names}) != len(names):
        raise HTTPException(400, "Friend names must be different")
    currency = body.currency.upper()
    if currency not in split.FX_TO_USD:
        raise HTTPException(400, f"Currency must be one of {', '.join(sorted(split.FX_TO_USD))}")
    group = {
        "id": store.new_id(), "created_at": store.now(), "name": body.name.strip() or "My trip",
        "currency": currency,
        "members": [{"name": m.name.strip(), "email": m.email.strip()} for m in body.members if m.name.strip()],
        "expenses": [], "payments": [],
    }
    store.save(group)
    return _view(group)


@app.get("/api/groups/{group_id}")
def get_group(group_id: str):
    return _view(_group_or_404(group_id))


@app.post("/api/groups/{group_id}/expenses")
def add_expense(group_id: str, paid_by: str = Form(...), instruction: str = Form(""),
                receipt: UploadFile = File(...)):
    group = _group_or_404(group_id)
    members = [m["name"] for m in group["members"]]
    if paid_by not in members:
        raise HTTPException(400, "'Paid by' must be one of the friends")
    ext = Path(receipt.filename or "").suffix.lower()
    if ext not in IMAGE_TYPES:
        raise HTTPException(400, "Upload a photo (jpg, png or webp)")
    folder = config.UPLOAD_DIR / group_id
    folder.mkdir(parents=True, exist_ok=True)
    photo = folder / f"{uuid.uuid4().hex[:10]}{ext}"
    photo.write_bytes(receipt.file.read())

    try:
        photo_warnings = checks.check_photo(photo)
        parsed = ai.read_receipt(photo)
        warnings = photo_warnings + checks.check_receipt(parsed)
        plan = ai.plan_split(parsed, members, instruction)
    except ValueError as e:
        photo.unlink(missing_ok=True)
        raise HTTPException(422, str(e))
    except Exception as e:
        photo.unlink(missing_ok=True)
        raise HTTPException(502, f"AI could not process this receipt: {e}")
    people, reasons, plan_warnings = checks.check_plan(plan, len(parsed["items"]), members)
    original = split.split_receipt(parsed, people)

    rate = split.fx_rate(parsed["currency"], group["currency"])
    if rate is None:
        raise HTTPException(422, f"Cannot convert {parsed['currency']} to {group['currency']} yet")
    shares = split.convert_shares(original, rate)
    if rate != 1.0:
        warnings.append(f"Converted {parsed['currency']} to {group['currency']} at an indicative rate of {rate:.4f}.")

    expense = {
        "id": store.new_id(), "created_at": store.now(), "title": parsed.get("merchant") or "Receipt",
        "paid_by": paid_by, "instruction": instruction.strip(),
        "photo": f"{group_id}/{photo.name}", "receipt": parsed,
        "items": [{**it, "people": p, "reason": r} for it, p, r in zip(parsed["items"], people, reasons)],
        "summary": plan.get("summary", ""), "ai_source": plan.get("source"),
        "currency": parsed["currency"], "fx_rate": rate,
        "shares_original": original, "shares": shares, "warnings": warnings + plan_warnings,
    }
    group["expenses"].append(expense)
    store.save(group)
    return _view(group)


class ItemIn(BaseModel):
    name: str
    quantity: float = 1
    amount: float = Field(ge=0)


class ReviewIn(BaseModel):
    items: list[ItemIn]
    tax: float = Field(0, ge=0)
    tip: float = Field(0, ge=0)
    total: float = Field(gt=0)


@app.put("/api/groups/{group_id}/expenses/{expense_id}")
def review_expense(group_id: str, expense_id: str, body: ReviewIn):
    """Manual cross-check: the user corrects what the AI read; shares are recalculated by code."""
    group = _group_or_404(group_id)
    expense = next((e for e in group["expenses"] if e["id"] == expense_id), None)
    if not expense:
        raise HTTPException(404, "Unknown receipt")
    if len(body.items) != len(expense["items"]):
        raise HTTPException(400, "Keep the same number of items")
    receipt = {**expense["receipt"], "items": [i.model_dump() for i in body.items],
               "tax": body.tax, "tip": body.tip, "total": body.total, "confidence": 1.0}
    warnings = checks.check_receipt(receipt)
    people = [it["people"] for it in expense["items"]]
    original = split.split_receipt(receipt, people)
    expense.update(
        receipt=receipt, shares_original=original, shares=split.convert_shares(original, expense["fx_rate"]),
        items=[{**i, "people": old["people"], "reason": old["reason"]} for i, old in zip(receipt["items"], expense["items"])],
        warnings=warnings, checked_by_user=True,
    )
    store.save(group)
    return _view(group)


@app.delete("/api/groups/{group_id}/expenses/{expense_id}")
def delete_expense(group_id: str, expense_id: str):
    group = _group_or_404(group_id)
    group["expenses"] = [e for e in group["expenses"] if e["id"] != expense_id]
    store.save(group)
    return _view(group)


class SettleIn(BaseModel):
    from_name: str
    to_name: str


@app.post("/api/groups/{group_id}/settle/order")
def create_settle_order(group_id: str, body: SettleIn):
    group = _group_or_404(group_id)
    debt = next((d for d in split.settle_up(split.balances(group))
                 if d["from"] == body.from_name and d["to"] == body.to_name), None)
    if not debt:
        raise HTTPException(409, "That payment is no longer needed")
    payee = next(m["email"] for m in group["members"] if m["name"] == body.to_name)
    try:
        order_id = paypal.create_order(
            amount=debt["cents"] / 100, currency=group["currency"], payee_email=payee,
            description=f"{group['name']}: {body.from_name} pays back {body.to_name}", ref=group_id,
        )
    except PayPalError as e:
        raise HTTPException(502, str(e))
    group["payments"].append({"id": store.new_id(), "order_id": order_id, "from": body.from_name,
                              "to": body.to_name, "cents": debt["cents"], "status": "CREATED",
                              "created_at": store.now(), "mode": paypal.mode})
    store.save(group)
    return {"id": order_id}


class CaptureIn(BaseModel):
    order_id: str


@app.post("/api/groups/{group_id}/settle/capture")
def capture_settle_order(group_id: str, body: CaptureIn):
    group = _group_or_404(group_id)
    payment = next((p for p in group["payments"] if p["order_id"] == body.order_id), None)
    if not payment:
        raise HTTPException(404, "Unknown PayPal order")
    if payment["status"] != "COMPLETED":
        try:
            payment["capture_id"] = paypal.capture(body.order_id)
        except PayPalError as e:
            raise HTTPException(502, str(e))
        payment["status"], payment["paid_at"] = "COMPLETED", store.now()
        store.save(group)
    return _view(group)


@app.post("/api/demo/reset")
def demo_reset():
    store.reset()
    return {"ok": True}


config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=config.UPLOAD_DIR), name="uploads")
app.mount("/samples", StaticFiles(directory=config.SAMPLES_DIR), name="samples")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")
