from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Vehicle
from app.routes.auth import get_current_admin, get_current_user
from app.vehicle_schemas import (
    VehicleCreate,
    VehicleResponse,
    VehicleUpdate,
)

from decimal import Decimal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/vehicles", tags=["Vehicles"])


@router.get("", response_model=list[VehicleResponse])
def list_vehicles(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.scalars(select(Vehicle).order_by(Vehicle.id)).all()


@router.get("/search", response_model=list[VehicleResponse])
def search_vehicles(
    make: str | None = Query(default=None, min_length=1),
    model: str | None = Query(default=None, min_length=1),
    category: str | None = Query(default=None, min_length=1),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if (
        min_price is not None
        and max_price is not None
        and min_price > max_price
    ):
        raise HTTPException(
            status_code=422,
            detail="min_price cannot exceed max_price.",
        )

    statement = select(Vehicle)

    if make is not None:
        statement = statement.where(
            Vehicle.make.ilike(f"%{make.strip()}%")
        )

    if model is not None:
        statement = statement.where(
            Vehicle.model.ilike(f"%{model.strip()}%")
        )

    if category is not None:
        statement = statement.where(
            Vehicle.category.ilike(f"%{category.strip()}%")
        )

    if min_price is not None:
        statement = statement.where(
            Vehicle.price >= min_price
        )

    if max_price is not None:
        statement = statement.where(
            Vehicle.price <= max_price
        )

    statement = statement.order_by(Vehicle.id)

    return db.scalars(statement).all()


@router.post(
    "",
    response_model=VehicleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_vehicle(
    payload: VehicleCreate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    vehicle = Vehicle(**payload.model_dump())

    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)

    return vehicle


@router.put("/{vehicle_id}", response_model=VehicleResponse)
def update_vehicle(
    vehicle_id: int,
    payload: VehicleUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    vehicle = db.get(Vehicle, vehicle_id)

    if vehicle is None:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found.",
        )

    changes = payload.model_dump(exclude_unset=True, exclude_none=True)

    for field, value in changes.items():
        setattr(vehicle, field, value)

    db.commit()
    db.refresh(vehicle)

    return vehicle


@router.delete(
    "/{vehicle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_vehicle(
    vehicle_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    vehicle = db.get(Vehicle, vehicle_id)

    if vehicle is None:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found.",
        )

    db.delete(vehicle)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)