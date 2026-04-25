import pytest

from server.auth.ngo import (
    InvalidTokenError,
    create_operator_token,
    hash_password,
    verify_operator_token,
    verify_password,
)


def test_password_hash_and_verify_round_trip():
    h = hash_password("hunter2")
    assert verify_password("hunter2", h)
    assert not verify_password("wrong", h)


def test_token_round_trip_returns_operator_id():
    token = create_operator_token(operator_id="op-1", ngo_id="N1")
    payload = verify_operator_token(token)
    assert payload["operator_id"] == "op-1"
    assert payload["ngo_id"] == "N1"


def test_invalid_token_raises():
    with pytest.raises(InvalidTokenError):
        verify_operator_token("not.a.token")
