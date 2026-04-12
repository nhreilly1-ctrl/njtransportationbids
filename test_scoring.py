from app.core.scoring import compute_transport_score


def test_transport_score_positive():
    assert compute_transport_score("road resurfacing and traffic signal improvements") > 0.1
