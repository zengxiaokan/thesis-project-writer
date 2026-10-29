"""Synthetic integer-cent pricing without a tax engine."""
def subtotal(lines):
    for line in lines:
        if type(line["unit_cents"]) is not int or line["unit_cents"] <= 0:
            raise ValueError("positive integer cents required")
    return sum(line["unit_cents"] * line["quantity"] for line in lines)
