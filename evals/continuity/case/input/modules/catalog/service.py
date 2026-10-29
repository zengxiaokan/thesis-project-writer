"""Synthetic saleable catalog and freeze action."""
def list_saleable(repo):
    return repo.find("catalog", lambda row: row["saleable"])

def require_saleable(repo, product_id):
    row = repo.get("catalog", product_id)
    if row is None or not row["saleable"]:
        raise ValueError("product unavailable")
    return row

def freeze(repo, product_id):
    row = repo.get("catalog", product_id)
    if row is None:
        raise ValueError("product missing")
    row["saleable"] = False
