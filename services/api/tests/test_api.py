"""Contract tests for the HTTP layer."""

from __future__ import annotations


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_stats_shape(client):
    r = client.get("/api/stats")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"companies", "markets", "high_confidence"}
    assert body["companies"] > 0
    assert body["high_confidence"] <= body["companies"]


def test_markets_sorted_desc(client):
    r = client.get("/api/markets")
    assert r.status_code == 200
    counts = [m["companies"] for m in r.json()]
    assert counts == sorted(counts, reverse=True)


def test_companies_default_page(client):
    r = client.get("/api/companies")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= len(body["items"])
    assert len(body["items"]) <= 50
    row = body["items"][0]
    assert isinstance(row["reasons"], list)
    assert 0 <= row["need_score"] <= 100
    # priority is need scaled by fit, so it never exceeds need.
    assert row["priority"] <= row["need_score"] + 1e-6


def test_companies_sorted_by_priority(client):
    r = client.get("/api/companies?limit=25")
    prio = [c["priority"] for c in r.json()["items"]]
    assert prio == sorted(prio, reverse=True)


def test_high_confidence_filter(client):
    r = client.get("/api/companies?high_confidence=true&limit=30")
    assert all(c["has_cert_identity"] for c in r.json()["items"])


def test_size_filter(client):
    r = client.get("/api/companies", params={"size": "small", "limit": 50})
    assert r.status_code == 200
    assert all(2 <= c["exposed_ips"] <= 9 for c in r.json()["items"])


def test_bad_size_rejected(client):
    assert client.get("/api/companies?size=huge").status_code == 422


def test_limit_cap_rejected(client):
    # Over the max page size is a validation error, not a silent clamp.
    assert client.get("/api/companies?limit=500").status_code == 422


def test_bad_sort_rejected(client):
    assert client.get("/api/companies?sort=company").status_code == 422


def test_company_detail(client):
    name = client.get("/api/companies?limit=1").json()["items"][0]["company"]
    r = client.get("/api/company", params={"name": name})
    assert r.status_code == 200
    body = r.json()
    assert body["company"] == name
    assert isinstance(body["reasons"], list)
    # Named evidence is present and typed, with no hostnames (company-level only).
    assert isinstance(body["kev_cves"], list)
    assert isinstance(body["db_services"], list)
    assert isinstance(body["remote_services"], list)
    assert "worst_service" in body


def test_company_detail_404(client):
    r = client.get("/api/company", params={"name": "no-such-company-zzz-000"})
    assert r.status_code == 404


def test_evidence_actually_populates(client):
    # Type checks pass even if the evidence join silently returns empty lists.
    # This asserts the wiring is live: across the top of the ranked list, at
    # least one company carries a named service and at least one carries a CVE.
    items = client.get("/api/companies?limit=50").json()["items"]
    assert any(c["worst_service"] for c in items)
    assert any(len(c["kev_cves"]) > 0 for c in items)


def test_detail_matches_list_row(client):
    # The same company must read the same in the list and on its detail page.
    row = client.get("/api/companies?limit=1").json()["items"][0]
    detail = client.get("/api/company", params={"name": row["company"]}).json()
    for field in ("priority", "need_score", "worst_service", "kev_cves", "reasons"):
        assert detail[field] == row[field]


def test_market_filter(client):
    market = client.get("/api/markets").json()[0]["country"]
    r = client.get("/api/companies", params={"market": market, "limit": 50})
    assert r.status_code == 200
    assert all(c["country"] == market for c in r.json()["items"])


def test_min_need_filter(client):
    r = client.get("/api/companies", params={"min_need": 50, "limit": 50})
    assert r.status_code == 200
    assert all(c["need_score"] >= 50 for c in r.json()["items"])


def test_xlarge_size_has_no_upper_bound(client):
    r = client.get("/api/companies", params={"size": "xlarge", "limit": 50})
    assert r.status_code == 200
    assert all(c["exposed_ips"] >= 200 for c in r.json()["items"])


def test_offset_pages_forward(client):
    first = client.get("/api/companies?limit=5&offset=0").json()["items"]
    second = client.get("/api/companies?limit=5&offset=5").json()["items"]
    first_names = {c["company"] for c in first}
    second_names = {c["company"] for c in second}
    assert first_names and second_names
    assert first_names.isdisjoint(second_names)


def test_fuzzy_ranks_exact_match_first(client):
    # An exact-name query must return that company as the first, most relevant
    # result, above any fuzzy-only neighbours.
    name = client.get("/api/companies?limit=1").json()["items"][0]["company"]
    r = client.get("/api/companies", params={"q": name, "limit": 10})
    assert r.status_code == 200
    items = r.json()["items"]
    assert items and items[0]["company"] == name


def test_fuzzy_search_tolerates_typo(client):
    # Take a real company, swap two adjacent characters, and expect the fuzzy
    # search to still find it.
    first = client.get("/api/companies?limit=1").json()["items"][0]["company"]
    if len(first) < 4:
        return
    i = len(first) // 2
    typo = first[:i] + first[i + 1] + first[i] + first[i + 2 :]
    assert typo != first
    r = client.get("/api/companies", params={"q": typo, "limit": 50})
    assert r.status_code == 200
    names = [c["company"] for c in r.json()["items"]]
    assert first in names


def test_rate_limit_returns_429(strict_client):
    # Burst is 2, so the third quick call is rejected with a Retry-After.
    assert strict_client.get("/api/stats").status_code == 200
    assert strict_client.get("/api/stats").status_code == 200
    r = strict_client.get("/api/stats")
    assert r.status_code == 429
    assert "Retry-After" in r.headers
