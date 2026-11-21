from src.price_watch import PropertyWatch, decide_price


def test_rent_change_creates_a_notification_decision():
    watch = PropertyWatch("Harbor View Apartments", "harbor view rent", 2400, "https://example.com/check")

    decision = decide_price(watch, 2475)

    assert decision.change == 75
    assert decision.action == "notify"
