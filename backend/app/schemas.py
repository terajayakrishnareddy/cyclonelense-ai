from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_serializer, field_validator

from .timeutil import iso_utc


class ObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    storm_id: str
    name: str
    basin: str
    timestamp: datetime
    latitude: float
    longitude: float
    wind_speed_kt: float | None
    pressure_hpa: float | None
    wind_source: str | None = None
    pressure_source: str | None = None
    status: str
    source: str
    is_demo: bool

    @field_serializer("timestamp")
    def _ts(self, v: datetime):
        return iso_utc(v)


class TrackRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    direction_degrees: float = Field(default=0, ge=0, lt=360, description="Direction of motion, degrees clockwise from north")
    speed_kmh: float = Field(default=15, ge=0, le=150)
    hours: int = Field(default=24, ge=1, le=120)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

    @field_validator("password")
    @classmethod
    def _bcrypt_limit(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes when UTF-8 encoded")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
