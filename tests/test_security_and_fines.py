from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.security import create_access_token, decode_access_token, hash_password, verify_password
from app.services.loans import calculate_fine


def test_password_roundtrip():
    hashed = hash_password("s3cret-pass")
    assert hashed != "s3cret-pass"
    assert verify_password("s3cret-pass", hashed)
    assert not verify_password("wrong", hashed)


def test_token_roundtrip_and_expiry():
    assert decode_access_token(create_access_token("42")) == "42"
    assert decode_access_token(create_access_token("42", expires_minutes=-1)) is None
    assert decode_access_token("not-a-token") is None


def test_fine_calculation():
    due = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert calculate_fine(due, due - timedelta(days=1)) == Decimal("0.00")
    assert calculate_fine(due, due + timedelta(days=4, hours=3)) == Decimal("2.00")  # 4 full days late
