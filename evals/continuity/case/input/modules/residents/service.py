"""Synthetic resident rules, not authentication."""
def register(repo, name, zone):
    if not name.strip() or not zone.strip():
        raise ValueError("name and delivery zone required")
    return repo.insert("residents", {"name": name, "zone": zone, "active": True, "points": 0})

def require_active(repo, resident_id):
    row = repo.get("residents", resident_id)
    if row is None or not row["active"]:
        raise ValueError("resident inactive or missing")
    return row
