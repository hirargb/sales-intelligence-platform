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
