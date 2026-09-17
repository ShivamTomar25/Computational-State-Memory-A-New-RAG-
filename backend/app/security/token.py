from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import jwt

from app.config import settings


class InvalidTokenError(Exception):
    pass


def create_access_token(
    doctor_id: UUID,
    expires_minutes: Optional[int] = None,
) -> str:
    current_time = datetime.now(timezone.utc)
    expiration_minutes = (
        expires_minutes
        if expires_minutes is not None
        else settings.access_token_expire_minutes
    )

    payload = {
        "sub": str(doctor_id),
        "type": "access",
        "iat": current_time,
        "exp": current_time + timedelta(minutes=expiration_minutes),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> UUID:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={
                "require": ["sub", "exp", "iat", "type"],
            },
        )

        if payload.get("type") != "access":
            raise InvalidTokenError("Invalid token type.")

        subject = payload.get("sub")

        if not subject:
            raise InvalidTokenError("Token subject is missing.")

        return UUID(subject)

    except (
        jwt.ExpiredSignatureError,
        jwt.InvalidTokenError,
        ValueError,
    ) as error:
        raise InvalidTokenError("The access token is invalid or expired.") from error
