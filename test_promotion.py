from types import SimpleNamespace

from app.services.promoter import should_promote


def test_should_promote_true():
    lead = SimpleNamespace(
        verification_status="matched_official_source",
        transport_score=0.8,
        confidence_score=0.7,
        lead_status="verified",
        is_open=True,
        official_url="https://example.com",
    )
    assert should_promote(lead) is True
