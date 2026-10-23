"""Tests for password hashing, JWT operations, and PII masking."""

import uuid
from backend.app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    mask_pii,
    verify_password,
)


def test_password_hashing():
    raw_password = "superSecurePassword123!"
    hashed = get_password_hash(raw_password)

    assert hashed != raw_password
    assert verify_password(raw_password, hashed) is True
    assert verify_password("wrongPassword", hashed) is False


def test_jwt_token_encode_decode():
    user_id = uuid.uuid4()
    token = create_access_token(subject=user_id, role="compliance_analyst")

    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "compliance_analyst"
    assert "exp" in payload


def test_jwt_invalid_token():
    assert decode_access_token("invalid.token.structure") is None


def test_pii_masking_credit_card():
    text = "Customer card 4111 1111 1111 4321 failed with error 51"
    masked = mask_pii(text)
    assert "4111 1111 1111" not in masked
    assert "[CARD_REDACTED_*4321]" in masked


def test_pii_masking_email_and_phone():
    text = "Reach me at customer.support@example.com or call 555-123-4567 regarding my refund."
    masked = mask_pii(text)
    assert "customer.support@example.com" not in masked
    assert "[EMAIL_REDACTED]" in masked
    assert "555-123-4567" not in masked
    assert "[PHONE_REDACTED]" in masked


def test_pii_masking_bank_account_and_ssn():
    text = "Account: 9876543210 and SSN 123-45-6789 had duplicate debit."
    masked = mask_pii(text)
    assert "9876543210" not in masked
    assert "[ACCOUNT_ID_REDACTED]" in masked
    assert "123-45-6789" not in masked
    assert "[TAX_ID_REDACTED]" in masked
