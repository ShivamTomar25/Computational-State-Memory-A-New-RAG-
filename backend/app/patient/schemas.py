from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class PatientCreate(BaseModel):
    patient_code: str = Field(min_length=1, max_length=50)
    full_name: str = Field(min_length=1, max_length=150)
    date_of_birth: Optional[date] = None
    sex: Optional[str] = Field(default=None, max_length=20)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[EmailStr] = None
    address: Optional[str] = Field(default=None, max_length=2000)
    emergency_contact_name: Optional[str] = Field(default=None, max_length=150)
    emergency_contact_phone: Optional[str] = Field(default=None, max_length=50)

    model_config = ConfigDict(extra="forbid")


class PatientUpdate(BaseModel):
    patient_code: Optional[str] = Field(default=None, min_length=1, max_length=50)
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    date_of_birth: Optional[date] = None
    sex: Optional[str] = Field(default=None, max_length=20)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[EmailStr] = None
    address: Optional[str] = Field(default=None, max_length=2000)
    emergency_contact_name: Optional[str] = Field(default=None, max_length=150)
    emergency_contact_phone: Optional[str] = Field(default=None, max_length=50)

    model_config = ConfigDict(extra="forbid")


class PatientResponse(BaseModel):
    id: UUID
    doctor_id: UUID
    patient_code: str
    full_name: str
    date_of_birth: Optional[date]
    sex: Optional[str]
    phone: Optional[str]
    email: Optional[EmailStr]
    address: Optional[str]
    emergency_contact_name: Optional[str]
    emergency_contact_phone: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PatientListResponse(BaseModel):
    items: list[PatientResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
