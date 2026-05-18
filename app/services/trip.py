"""Trip planning business logic service."""

from datetime import UTC, datetime

from sqlmodel import Session, col, select

from app.core.logging import logger
from app.models.trip import Trip
from app.schemas.trip import Itinerary, TripCreate, TripStatus, TripUpdate


class TripService:
    """CRUD operations for Trip entities."""

    def __init__(self, engine) -> None:
        self._engine = engine

    async def create(
        self,
        user_id: int,
        data: TripCreate,
        session_id: str | None = None,
    ) -> Trip:
        itinerary = Itinerary(
            destination=data.destination,
            total_days=data.total_days,
            days=data.days,
            tips=data.tips,
            budget_estimate=data.budget_estimate,
        )
        trip = Trip(
            user_id=user_id,
            session_id=session_id,
            title=data.title,
            destination=data.destination,
            total_days=data.total_days,
            itinerary_json=itinerary.model_dump_json(ensure_ascii=False),
        )
        with Session(self._engine) as db:
            db.add(trip)
            db.commit()
            db.refresh(trip)
        logger.info("trip_created", trip_id=trip.id, user_id=user_id, destination=data.destination)
        return trip

    async def get(self, trip_id: str, user_id: int) -> Trip | None:
        with Session(self._engine) as db:
            trip = db.get(Trip, trip_id)
            if trip and trip.user_id == user_id:
                return trip
            return None

    async def list_by_user(self, user_id: int) -> list[Trip]:
        with Session(self._engine) as db:
            rows = db.exec(
                select(Trip)
                .where(col(Trip.user_id) == user_id)
                .order_by(col(Trip.updated_at).desc())
            ).all()
            return list(rows)

    async def update(self, trip_id: str, user_id: int, data: TripUpdate) -> Trip | None:
        with Session(self._engine) as db:
            trip = db.get(Trip, trip_id)
            if not trip or trip.user_id != user_id:
                return None

            if data.title is not None:
                trip.title = data.title
            if data.status is not None:
                trip.status = data.status.value

            if data.days is not None:
                itinerary = trip.get_itinerary()
                itinerary.days = data.days
                if data.tips is not None:
                    itinerary.tips = data.tips
                if data.budget_estimate is not None:
                    itinerary.budget_estimate = data.budget_estimate
                trip.set_itinerary(itinerary)
            elif data.tips is not None or data.budget_estimate is not None:
                itinerary = trip.get_itinerary()
                if data.tips is not None:
                    itinerary.tips = data.tips
                if data.budget_estimate is not None:
                    itinerary.budget_estimate = data.budget_estimate
                trip.set_itinerary(itinerary)

            trip.updated_at = datetime.now(UTC)
            db.add(trip)
            db.commit()
            db.refresh(trip)

        logger.info("trip_updated", trip_id=trip_id)
        return trip

    async def delete(self, trip_id: str, user_id: int) -> bool:
        with Session(self._engine) as db:
            trip = db.get(Trip, trip_id)
            if not trip or trip.user_id != user_id:
                return False
            db.delete(trip)
            db.commit()
        logger.info("trip_deleted", trip_id=trip_id)
        return True
