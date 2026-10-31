"""Draws the sample receipt photos used by the demo."""
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).parent
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

RECEIPTS = {
    "dinner_receipt.jpg": {
        "merchant": "Beach Shack Kitchen", "date": "2026-10-18", "currency": "USD",
        "items": [{"name": "Fish Curry", "quantity": 3, "amount": 36.00},
                  {"name": "Beer", "quantity": 4, "amount": 24.00},
                  {"name": "Mango Lassi", "quantity": 1, "amount": 5.00}],
        "tax": 5.20, "tip": 0, "total": 70.20, "confidence": 0.97,
        "header": ["BEACH SHACK KITCHEN", "Palolem Beach, Goa", "Table 7   Guests 3"],
    },
    "taxi_receipt.jpg": {
        "merchant": "Bangkok Airport Taxi", "date": "2026-10-19", "currency": "THB",
        "items": [{"name": "Airport to Hotel fare", "quantity": 1, "amount": 450.00},
                  {"name": "Expressway toll", "quantity": 1, "amount": 75.00}],
        "tax": 0, "tip": 0, "total": 525.00, "confidence": 0.95,
        "header": ["BANGKOK AIRPORT TAXI", "Suvarnabhumi Rank 4", "Car 2231"],
    },
    "grocery_receipt.jpg": {
        "merchant": "FreshMart", "date": "2026-10-19", "currency": "USD",
        "items": [{"name": "Water 6-pack", "quantity": 1, "amount": 4.50},
                  {"name": "Potato Chips", "quantity": 2, "amount": 6.40},
                  {"name": "Sunscreen SPF50", "quantity": 1, "amount": 12.00},
                  {"name": "Beer 6-pack", "quantity": 1, "amount": 10.00},
                  {"name": "Fruit Platter", "quantity": 1, "amount": 6.30}],
        "tax": 0, "tip": 0, "total": 39.20, "confidence": 0.96,
        "header": ["FRESHMART", "24h Supermarket", "Store #118"],
    },
}


def draw(spec: dict) -> Image.Image:
    font, bold, big = ImageFont.truetype(MONO, 22), ImageFont.truetype(BOLD, 22), ImageFont.truetype(BOLD, 28)
    lines = len(spec["items"]) + 14
    img = Image.new("RGB", (560, 140 + lines * 34), (252, 250, 244))
    d = ImageDraw.Draw(img)
    y = 30
    d.text((280, y), spec["header"][0], font=big, fill=(20, 20, 20), anchor="ma"); y += 44
    for h in spec["header"][1:]:
        d.text((280, y), h, font=font, fill=(60, 60, 60), anchor="ma"); y += 30
    d.text((280, y), spec["date"], font=font, fill=(60, 60, 60), anchor="ma"); y += 40
    d.text((30, y), "-" * 36, font=font, fill=(90, 90, 90)); y += 34
    cur = spec["currency"]
    for it in spec["items"]:
        q = int(it["quantity"])
        label = f"{q}x {it['name']}" if q > 1 else it["name"]
        d.text((30, y), label, font=font, fill=(20, 20, 20))
        d.text((530, y), f"{it['amount']:.2f}", font=font, fill=(20, 20, 20), anchor="ra"); y += 34
    d.text((30, y), "-" * 36, font=font, fill=(90, 90, 90)); y += 34
    sub = sum(i["amount"] for i in spec["items"])
    d.text((30, y), "Subtotal", font=font, fill=(20, 20, 20)); d.text((530, y), f"{sub:.2f}", font=font, fill=(20, 20, 20), anchor="ra"); y += 34
    if spec["tax"]:
        d.text((30, y), "Tax 8%", font=font, fill=(20, 20, 20)); d.text((530, y), f"{spec['tax']:.2f}", font=font, fill=(20, 20, 20), anchor="ra"); y += 34
    d.text((30, y), f"TOTAL {cur}", font=big, fill=(0, 0, 0)); d.text((530, y), f"{spec['total']:.2f}", font=big, fill=(0, 0, 0), anchor="ra"); y += 50
    d.text((280, y), "Thank you! Come again", font=font, fill=(60, 60, 60), anchor="ma")
    img = img.crop((0, 0, img.width, y + 60))
    img = img.rotate(random.uniform(-2.5, 2.5), expand=True, fillcolor=(205, 200, 190))
    return img.filter(ImageFilter.GaussianBlur(0.6))


if __name__ == "__main__":
    random.seed(7)
    answers = {}
    for name, spec in RECEIPTS.items():
        draw(spec).save(OUT / name, quality=88)
        answers[name] = {k: v for k, v in spec.items() if k != "header"}
    (OUT / "demo_receipts.json").write_text(json.dumps(answers, indent=2))
    print("wrote", ", ".join(RECEIPTS))
