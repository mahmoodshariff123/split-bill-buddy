"""All money math lives here, in plain code (never in the AI), in whole cents so totals always add up."""
from collections import defaultdict

# Indicative rates to USD, used only to convert foreign receipts into the group currency.
# The user can override the rate per expense.
FX_TO_USD = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "INR": 0.012, "THB": 0.028,
             "JPY": 0.0067, "AED": 0.272, "SGD": 0.74, "AUD": 0.65, "CAD": 0.73}


def cents(x: float) -> int:
    return int(round(x * 100))


def fx_rate(src: str, dst: str) -> float | None:
    if src == dst:
        return 1.0
    if src in FX_TO_USD and dst in FX_TO_USD:
        return FX_TO_USD[src] / FX_TO_USD[dst]
    return None


def allocate(total: int, weights: list[float]) -> list[int]:
    """Split `total` cents by weights so the parts always sum exactly to `total`."""
    if not weights:
        return []
    sign, total = (-1 if total < 0 else 1), abs(total)
    wsum = sum(weights) or len(weights)
    weights = weights if sum(weights) else [1] * len(weights)
    raw = [total * w / wsum for w in weights]
    parts = [int(r) for r in raw]
    order = sorted(range(len(raw)), key=lambda i: (raw[i] - parts[i], -i), reverse=True)
    for i in order[: total - sum(parts)]:
        parts[i] += 1
    return [sign * p for p in parts]


def receipt_total(receipt: dict) -> int:
    if receipt.get("total"):
        return cents(receipt["total"])
    return sum(cents(i["amount"]) for i in receipt["items"]) + cents(receipt.get("tax") or 0) + cents(receipt.get("tip") or 0)


def split_receipt(receipt: dict, assignments: list[list[str]]) -> dict[str, int]:
    """Who owes what (in receipt-currency cents). Tax/tip/discounts are shared in proportion to items.
    Exact fractional shares are summed first and rounded once, so equal splits stay equal."""
    weights: dict[str, float] = defaultdict(float)
    for item, people in zip(receipt["items"], assignments):
        for name in people:
            weights[name] += cents(item["amount"]) / len(people)
    names = list(weights)
    return dict(zip(names, allocate(receipt_total(receipt), [weights[n] for n in names])))


def convert_shares(shares: dict[str, int], rate: float) -> dict[str, int]:
    total = round(sum(shares.values()) * rate)
    names = list(shares)
    return dict(zip(names, allocate(total, [shares[n] for n in names])))


def balances(group: dict) -> dict[str, int]:
    """Positive = this person should get money back. Negative = this person owes."""
    bal = {m["name"]: 0 for m in group["members"]}
    for e in group["expenses"]:
        bal[e["paid_by"]] += sum(e["shares"].values())
        for name, amount in e["shares"].items():
            bal[name] -= amount
    for p in group["payments"]:
        if p["status"] == "COMPLETED":
            bal[p["from"]] += p["cents"]
            bal[p["to"]] -= p["cents"]
    return bal


def settle_up(bal: dict[str, int]) -> list[dict]:
    """Fewest simple payments: the biggest debtor pays the biggest creditor, repeat."""
    debtors = sorted(([n, -b] for n, b in bal.items() if b < 0), key=lambda x: -x[1])
    creditors = sorted(([n, b] for n, b in bal.items() if b > 0), key=lambda x: -x[1])
    out, i, j = [], 0, 0
    while i < len(debtors) and j < len(creditors):
        amount = min(debtors[i][1], creditors[j][1])
        if amount > 0:
            out.append({"from": debtors[i][0], "to": creditors[j][0], "cents": amount})
        debtors[i][1] -= amount
        creditors[j][1] -= amount
        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1
    return out
