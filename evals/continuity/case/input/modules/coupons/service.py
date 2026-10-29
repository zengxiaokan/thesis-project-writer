"""Synthetic owner-bound fixed discounts; expiry equal to now is accepted."""
def discount(repo, coupon_id, resident_id, amount, now):
    if coupon_id is None:
        return 0
    row = repo.get("coupons", coupon_id)
    if row is None or row["resident_id"] != resident_id or not row["active"]:
        raise ValueError("coupon unavailable")
    if row["expires_at"] < now or amount < row["minimum_cents"]:
        raise ValueError("coupon condition not met")
    return min(amount, row["discount_cents"])
