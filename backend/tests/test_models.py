from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base
from app.models import User, Vehicle
from dotenv import load_dotenv
import os

load_dotenv()

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

if not TEST_DATABASE_URL:
    raise RuntimeError("TEST_DATABASE_URL is missing from backend/.env")

test_engine = create_engine(TEST_DATABASE_URL)


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=test_engine)

    with Session(test_engine) as session:
        yield session
        session.rollback()

    Base.metadata.drop_all(bind=test_engine)


def test_user_can_be_saved_and_retrieved(db_session):
    user = User(
        email="aria-test@example.com",
        password_hash="test-hash-not-a-real-password",
        role="user",
    )

    db_session.add(user)
    db_session.commit()

    saved_user = db_session.scalar(
        select(User).where(User.email == "aria-test@example.com")
    )

    assert saved_user is not None
    assert saved_user.role == "user"
    assert saved_user.password_hash == "test-hash-not-a-real-password"


def test_user_email_must_be_unique(db_session):
    db_session.add(
        User(
            email="duplicate@example.com",
            password_hash="hash-one",
            role="user",
        )
    )
    db_session.commit()

    db_session.add(
        User(
            email="duplicate@example.com",
            password_hash="hash-two",
            role="user",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_vehicle_can_be_saved_and_retrieved(db_session):
    vehicle = Vehicle(
        make="Toyota",
        model="Corolla",
        category="Sedan",
        price=Decimal("1500000.00"),
        quantity=5,
    )

    db_session.add(vehicle)
    db_session.commit()

    saved_vehicle = db_session.scalar(
        select(Vehicle).where(Vehicle.model == "Corolla")
    )

    assert saved_vehicle is not None
    assert saved_vehicle.make == "Toyota"
    assert saved_vehicle.price == Decimal("1500000.00")
    assert saved_vehicle.quantity == 5


@pytest.mark.parametrize("quantity", [-1, -5])
def test_vehicle_quantity_cannot_be_negative(db_session, quantity):
    vehicle = Vehicle(
        make="Honda",
        model="Civic",
        category="Sedan",
        price=Decimal("1200000.00"),
        quantity=quantity,
    )

    db_session.add(vehicle)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_vehicle_price_cannot_be_negative(db_session):
    vehicle = Vehicle(
        make="Honda",
        model="Civic",
        category="Sedan",
        price=Decimal("-1.00"),
        quantity=1,
    )

    db_session.add(vehicle)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()