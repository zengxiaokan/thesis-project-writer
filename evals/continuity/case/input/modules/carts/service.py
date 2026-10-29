"""Synthetic cart lines indexed by resident and product."""
def put(repo, resident_id, product_id, quantity):
    if type(quantity) is not int or quantity <= 0:
        raise ValueError("positive integer quantity required")
    rows = repo.find("cart_lines", lambda row: row["resident_id"] == resident_id and row["product_id"] == product_id)
    if rows:
        rows[0]["quantity"] = quantity
        return rows[0]
    return repo.insert("cart_lines", {"resident_id": resident_id, "product_id": product_id, "quantity": quantity})

def lines_for(repo, resident_id):
    return repo.find("cart_lines", lambda row: row["resident_id"] == resident_id)
