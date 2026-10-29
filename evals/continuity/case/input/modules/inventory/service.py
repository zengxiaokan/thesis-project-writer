"""Synthetic available/reserved counters; caller supplies transaction."""
def stock(repo, product_id):
    rows = repo.find("inventory", lambda row: row["product_id"] == product_id)
    if not rows:
        raise ValueError("stock missing")
    return rows[0]

def reserve(repo, product_id, quantity):
    row = stock(repo, product_id)
    if row["available"] < quantity:
        raise ValueError("stock insufficient")
    row["available"] -= quantity
    row["reserved"] += quantity

def release(repo, product_id, quantity):
    row = stock(repo, product_id)
    if row["reserved"] < quantity:
        raise ValueError("reserved stock insufficient")
    row["reserved"] -= quantity
    row["available"] += quantity

def consume(repo, product_id, quantity):
    row = stock(repo, product_id)
    if row["reserved"] < quantity:
        raise ValueError("reserved stock insufficient")
    row["reserved"] -= quantity
