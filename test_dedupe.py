from app.services.dedupe import compute_duplicate_hash



def test_duplicate_hash_stable():
    a = compute_duplicate_hash("NJDOT", "Bridge Repair", "2026-04-11", "https://example.com")
    b = compute_duplicate_hash("NJDOT", "Bridge Repair", "2026-04-11", "https://example.com")
    assert a == b
