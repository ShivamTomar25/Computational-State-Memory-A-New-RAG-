from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class DoctorCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    specialization: Optional[str] = Field(default=None, max_length=150)
    medical_license_number: Optional[str] = Field(default=None, max_length=100)
    organization_name: Optional[str] = Field(default=None, max_length=200)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        cleaned_value = value.strip()

        if len(cleaned_value) < 2:
            raise ValueError("Full name must contain at least two characters.")

        return cleaned_value


class DoctorLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class DoctorUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    specialization: Optional[str] = Field(default=None, max_length=150)
    medical_license_number: Optional[str] = Field(default=None, max_length=100)
    organization_name: Optional[str] = Field(default=None, max_length=200)


class DoctorResponse(BaseModel):
    id: UUID
    full_name: str
    email: EmailStr
    specialization: Optional[str]
    medical_license_number: Optional[str]
    organization_name: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    doctor: DoctorResponse
