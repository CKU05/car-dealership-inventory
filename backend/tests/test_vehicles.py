import os
from collections.abc import Generator
from decimal import Decimal

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import User, Vehicle
from app.security import create_access_token

load_dotenv()

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

if not TEST_DATABASE_URL:
    raise RuntimeError("TEST_DATABASE_URL is missing from backend/.env")

test_engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    expire_on_commit=False,
)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def user_token(client: TestClient) -> str:
    with TestingSessionLocal() as session:
        user = User(
            email="customer@example.com",
            password_hash="test-hash",
            role="user",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return create_access_token(user.id, user.role)


@pytest.fixture
def admin_token(client: TestClient) -> str:
    with TestingSessionLocal() as session:
        admin = User(
            email="admin@example.com",
            password_hash="test-hash",
            role="admin",
        )
        session.add(admin)
        session.commit()
        session.refresh(admin)
        return create_access_token(admin.id, admin.role)


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def vehicle_payload() -> dict:
    return {
        "make": "Toyota",
        "model": "Corolla",
        "category": "Sedan",
        "price": "1500000.00",
        "quantity": 5,
    }


def test_authenticated_user_can_list_vehicles(
    client: TestClient,
    user_token: str,
):
    response = client.get(
        "/api/vehicles",
        headers=auth(user_token),
    )

    assert response.status_code == 200
    assert response.json() == []


def test_admin_can_create_vehicle(
    client: TestClient,
    admin_token: str,
):
    response = client.post(
        "/api/vehicles",
        json=vehicle_payload(),
        headers=auth(admin_token),
    )

    assert response.status_code == 201
    assert response.json()["make"] == "Toyota"
    assert response.json()["quantity"] == 5


def test_regular_user_cannot_create_vehicle(
    client: TestClient,
    user_token: str,
):
    response = client.post(
        "/api/vehicles",
        json=vehicle_payload(),
        headers=auth(user_token),
    )

    assert response.status_code == 403


def test_request_without_token_cannot_list_vehicles(
    client: TestClient,
):
    response = client.get("/api/vehicles")

    assert response.status_code == 401


def test_admin_can_update_vehicle(
    client: TestClient,
    admin_token: str,
):
    created = client.post(
        "/api/vehicles",
        json=vehicle_payload(),
        headers=auth(admin_token),
    )
    vehicle_id = created.json()["id"]

    response = client.put(
        f"/api/vehicles/{vehicle_id}",
        json={"price": "1400000.00"},
        headers=auth(admin_token),
    )

    assert response.status_code == 200
    assert Decimal(response.json()["price"]) == Decimal("1400000.00")


def test_admin_can_delete_vehicle(
    client: TestClient,
    admin_token: str,
):
    created = client.post(
        "/api/vehicles",
        json=vehicle_payload(),
        headers=auth(admin_token),
    )
    vehicle_id = created.json()["id"]

    response = client.delete(
        f"/api/vehicles/{vehicle_id}",
        headers=auth(admin_token),
    )

    assert response.status_code == 204


def test_regular_user_cannot_delete_vehicle(
    client: TestClient,
    admin_token: str,
    user_token: str,
):
    created = client.post(
        "/api/vehicles",
        json=vehicle_payload(),
        headers=auth(admin_token),
    )
    vehicle_id = created.json()["id"]

    response = client.delete(
        f"/api/vehicles/{vehicle_id}",
        headers=auth(user_token),
    )

    assert response.status_code == 403


def test_admin_cannot_create_vehicle_with_negative_quantity(
    client: TestClient,
    admin_token: str,
):
    payload = vehicle_payload()
    payload["quantity"] = -1

    response = client.post(
        "/api/vehicles",
        json=payload,
        headers=auth(admin_token),
    )

    assert response.status_code == 422


def test_search_by_make(client, admin_token, user_token):
    client.post(
        "/api/vehicles",
        json=vehicle_payload(),
        headers=auth(admin_token),
    )

    response = client.get(
        "/api/vehicles/search?make=toyota",
        headers=auth(user_token),
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["make"] == "Toyota"


def test_search_by_category(client, admin_token, user_token):
    cars = [
        {
            "make": "Toyota",
            "model": "Fortuner",
            "category": "SUV",
            "price": "3500000.00",
            "quantity": 2,
        },
        {
            "make": "Honda",
            "model": "City",
            "category": "Sedan",
            "price": "1200000.00",
            "quantity": 4,
        },
    ]

    for car in cars:
        client.post(
            "/api/vehicles",
            json=car,
            headers=auth(admin_token),
        )

    response = client.get(
        "/api/vehicles/search?category=SUV",
        headers=auth(user_token),
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["model"] == "Fortuner"


def test_search_by_price_range(client, admin_token, user_token):
    prices = ["1200000.00", "1500000.00", "3500000.00"]

    for index, price in enumerate(prices):
        payload = vehicle_payload()
        payload["model"] = f"Car{index}"
        payload["price"] = price

        client.post(
            "/api/vehicles",
            json=payload,
            headers=auth(admin_token),
        )

    response = client.get(
        "/api/vehicles/search"
        "?min_price=1300000&max_price=2000000",
        headers=auth(user_token),
    )

    assert response.status_code == 200
    results = response.json()

    assert len(results) == 1
    assert results[0]["model"] == "Car1"


def test_combined_filters(client, admin_token, user_token):
    cars = [
        {
            "make": "Toyota",
            "model": "Fortuner",
            "category": "SUV",
            "price": "3500000.00",
            "quantity": 2,
        },
        {
            "make": "Toyota",
            "model": "Corolla",
            "category": "Sedan",
            "price": "1500000.00",
            "quantity": 5,
        },
        {
            "make": "Honda",
            "model": "CRV",
            "category": "SUV",
            "price": "1800000.00",
            "quantity": 3,
        },
    ]

    for car in cars:
        client.post(
            "/api/vehicles",
            json=car,
            headers=auth(admin_token),
        )

    response = client.get(
        "/api/vehicles/search"
        "?make=Toyota&category=SUV&min_price=3000000",
        headers=auth(user_token),
    )

    assert response.status_code == 200
    results = response.json()

    assert len(results) == 1
    assert results[0]["model"] == "Fortuner"


def test_search_requires_authentication(client):
    response = client.get("/api/vehicles/search?make=Toyota")

    assert response.status_code == 401


def test_search_rejects_invalid_price_range(
    client,
    user_token,
):
    response = client.get(
        "/api/vehicles/search?min_price=2000000&max_price=1000000",
        headers=auth(user_token),
    )

    assert response.status_code == 422