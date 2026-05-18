"""Trip planning API endpoints.

Provides CRUD operations for saved trip itineraries.
Trips are created by the agent via the save_trip tool; these endpoints
let users view, update, and delete their trips.
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.v1.auth import get_current_user
from app.core.limiter import limiter
from app.core.logging import logger
from app.models.user import User
from app.schemas.trip import (
    TripListResponse,
    TripResponse,
    TripStatus,
    TripUpdate,
)
from app.services.trip import TripService

router = APIRouter()


def _get_trip_service() -> TripService:
    from app.services.database import database_service
    return TripService(database_service.engine)


def _trip_to_response(trip) -> TripResponse:
    itinerary = trip.get_itinerary()
    return TripResponse(
        id=trip.id,
        user_id=trip.user_id,
        session_id=trip.session_id,
        title=trip.title,
        destination=trip.destination,
        total_days=trip.total_days,
        status=TripStatus(trip.status),
        itinerary=itinerary,
        created_at=trip.created_at,
        updated_at=trip.updated_at,
    )


@router.get("", response_model=TripListResponse)
@limiter.limit("30/minute")
async def list_trips(
    request: Request,
    user: User = Depends(get_current_user),
):
    """List all trips for the authenticated user."""
    service = _get_trip_service()
    trips = await service.list_by_user(user.id)
    return TripListResponse(
        trips=[_trip_to_response(t) for t in trips],
        total=len(trips),
    )


@router.get("/{trip_id}", response_model=TripResponse)
@limiter.limit("30/minute")
async def get_trip(
    trip_id: str,
    request: Request,
    user: User = Depends(get_current_user),
):
    """Get a specific trip by ID."""
    service = _get_trip_service()
    trip = await service.get(trip_id, user.id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return _trip_to_response(trip)


@router.patch("/{trip_id}", response_model=TripResponse)
@limiter.limit("20/minute")
async def update_trip(
    trip_id: str,
    data: TripUpdate,
    request: Request,
    user: User = Depends(get_current_user),
):
    """Update a trip (title, status, itinerary)."""
    service = _get_trip_service()
    trip = await service.update(trip_id, user.id, data)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    logger.info("trip_updated_via_api", trip_id=trip_id, user_id=user.id)
    return _trip_to_response(trip)


@router.delete("/{trip_id}")
@limiter.limit("10/minute")
async def delete_trip(
    trip_id: str,
    request: Request,
    user: User = Depends(get_current_user),
):
    """Delete a trip."""
    service = _get_trip_service()
    deleted = await service.delete(trip_id, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Trip not found")
    logger.info("trip_deleted_via_api", trip_id=trip_id, user_id=user.id)
    return {"status": "deleted", "trip_id": trip_id}