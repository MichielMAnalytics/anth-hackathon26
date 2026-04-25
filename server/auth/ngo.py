from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from server.config import get_settings


class InvalidTokenError(Exception):
    pass


def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain.encode(), salt).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_operator_token(operator_id: str, ngo_id: str, ttl_minutes: int = 60 * 12) -> str:
    payload = {
        "operator_id": operator_id,
        "ngo_id": ngo_id,
        "iat": int(datetime.now(UTC).timestamp()),
        "exp": int((datetime.now(UTC) + timedelta(minutes=ttl_minutes)).timestamp()),
    }
    return jwt.encode(payload, get_settings().jwt_secret, algorithm="HS256")


def verify_operator_token(token: str) -> dict:
    try:
        return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except JWTError as e:
        raise InvalidTokenError(str(e)) from e
