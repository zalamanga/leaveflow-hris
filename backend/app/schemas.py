from datetime import date
import re
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator


def canonical_email(value: str):
    value = value.strip().lower()
    if not 3 <= len(value) <= 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        raise ValueError("Provide an email with a complete domain")
    return value


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        return canonical_email(value)


class NewLeave(Payload):
    start_date: date
    end_date: date
    reason: str = Field(min_length=10, max_length=2000)
    expected_version: StrictInt = Field(ge=1)


class Decision(Payload):
    expected_version: StrictInt = Field(ge=1)
    reason: str = Field(default="", max_length=2000)


class Version(Payload):
    expected_version: StrictInt = Field(ge=1)
