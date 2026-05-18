"""Trip and itinerary ORM models."""

import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlmodel import Field, SQLModel

from app.schemas.trip import Itinerary


class Trip(SQLModel, table=True):
    """Persists a structured trip itinerary.

    The itinerary is stored as a JSON string in `itinerary_json` and can be
    deserialized back to an `Itinerary` Pydantic model via `get_itinerary()`.
    """

    __tablename__ = "trip"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    session_id: str | None = Field(default=None, foreign_key="session.id", index=True)
    title: str = Field(max_length=200)
    destination: str = Field(max_length=100)
    total_days: int
    status: str = Field(default="draft", max_length=20)
    itinerary_json: str = Field(default="{}")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def get_itinerary(self) -> Itinerary:
        return Itinerary.model_validate_json(self.itinerary_json)

    def set_itinerary(self, itinerary: Itinerary) -> None:
        self.itinerary_json = itinerary.model_dump_json(ensure_ascii=False)
        self.updated_at = datetime.now(UTC)
