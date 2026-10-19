"""Independent taxonomy contracts. Category slugs are stable public identifiers."""
from typing import Optional
from pydantic import BaseModel, Field, field_validator

CATEGORY_SLUG_PATTERN = r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"
CATEGORY_ICON_PATTERN = r"^[a-z][a-z0-9-]*$"

def normalize_category_slugs(values: list[str]) -> list[str]:
    normalized = list(dict.fromkeys(values))
    if len(normalized) > 3:
        raise ValueError("A Space may have at most three categories")
    return normalized

class CategoryCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=40, pattern=CATEGORY_SLUG_PATTERN)
    name: str = Field(min_length=2, max_length=80)
    icon: str = Field(default="tag", max_length=32, pattern=CATEGORY_ICON_PATTERN)
    description: Optional[str] = Field(default=None, max_length=300)
    locale: str = Field(default="ru", min_length=2, max_length=12, pattern=r"^[a-z]{2}(?:-[A-Z]{2})?$")
    position: int = Field(default=0, ge=0, le=100000)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Category name is required")
        return value

class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    icon: Optional[str] = Field(default=None, max_length=32, pattern=CATEGORY_ICON_PATTERN)
    description: Optional[str] = Field(default=None, max_length=300)
    locale: Optional[str] = Field(default=None, min_length=2, max_length=12, pattern=r"^[a-z]{2}(?:-[A-Z]{2})?$")
    position: Optional[int] = Field(default=None, ge=0, le=100000)
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Category name is required")
        return value
