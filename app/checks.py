"""Safety checks on what the AI returned, before any money math. Problems become warnings the user sees."""
from .split import cents

LOW_CONFIDENCE = 0.70


def check_receipt(receipt: dict) -> list[str]:
    warnings = []
    if not receipt.get("items"):
        raise ValueError("No items could be read from this receipt. Try a clearer photo.")
    if receipt.get("confidence", 1) < LOW_CONFIDENCE:
        warnings.append(f"The photo was hard to read (confidence {receipt['confidence']:.2f}). Please double-check the items.")
    expected = sum(cents(i["amount"]) for i in receipt["items"]) + cents(receipt.get("tax") or 0) + cents(receipt.get("tip") or 0)
    total = cents(receipt.get("total") or 0)
    if total and abs(expected - total) > max(5, total * 0.02):
        warnings.append(
            f"Items + tax + tip = {expected / 100:.2f} but the receipt total is {total / 100:.2f}. "
            "The difference is shared in proportion; please check."
        )
    return warnings


def check_plan(plan: dict, n_items: int, members: list[str]) -> tuple[list[list[str]], list[str], list[str]]:
    """Returns (people per item, reason per item, warnings). Anything invalid falls back to 'everyone'."""
    people: list[list[str] | None] = [None] * n_items
    reasons = ["Shared by everyone"] * n_items
    warnings = []
    lookup = {m.lower(): m for m in members}
    for a in plan.get("assignments", []):
        i = a.get("item_index")
        if not isinstance(i, int) or not 0 <= i < n_items:
            continue
        valid = [lookup[n.strip().lower()] for n in a.get("members", []) if n.strip().lower() in lookup]
        unknown = [n for n in a.get("members", []) if n.strip().lower() not in lookup]
        if unknown:
            warnings.append(f"Ignored unknown name(s) {', '.join(unknown)} on item {i + 1}.")
        if valid:
            people[i] = list(dict.fromkeys(valid))
            reasons[i] = a.get("reason") or reasons[i]
    for i, p in enumerate(people):
        if p is None:
            warnings.append(f"Item {i + 1} had no valid people, so it is shared by everyone.")
            people[i] = list(members)
    return people, reasons, warnings
