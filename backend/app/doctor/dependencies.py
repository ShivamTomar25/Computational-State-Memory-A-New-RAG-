from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.doctor.model import Doctor
from app.doctor.repository import get_doctor_by_id
from app.security.token import InvalidTokenError, decode_access_token


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_doctor(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Doctor:
    authentication_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials are invalid or missing.",
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )

    if credentials is None:
        raise authentication_error

    if credentials.scheme.lower() != "bearer":
        raise authentication_error

    try:
        doctor_id = decode_access_token(credentials.credentials)
    except InvalidTokenError as error:
        raise authentication_error from error

    doctor = get_doctor_by_id(
        db=db,
        doctor_id=doctor_id,
    )

    if doctor is None:
        raise authentication_error

    if not doctor.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This doctor account is inactive.",
        )

    return doctor


CurrentDoctor = Annotated[Doctor, Depends(get_current_doctor)]
