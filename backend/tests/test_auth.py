import os
from collections.abc import Generator

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import User

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


def test_register_user(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == "newuser@example.com"
    assert response.json()["role"] == "user"
    assert "password" not in response.json()
    assert "password_hash" not in response.json()


def test_registration_stores_a_hash_not_the_password(
    client: TestClient,
):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "hashcheck@example.com",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 201

    with TestingSessionLocal() as session:
        user = session.query(User).filter_by(
            email="hashcheck@example.com"
        ).one()

        assert user.password_hash != "StrongPassword123!"
        assert user.password_hash


def test_duplicate_email_is_rejected(client: TestClient):
    payload = {
        "email": "duplicate@example.com",
        "password": "StrongPassword123!",
    }

    first = client.post("/api/auth/register", json=payload)
    second = client.post("/api/auth/register", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409


def test_login_returns_access_token(client: TestClient):
    client.post(
        "/api/auth/register",
        json={
            "email": "login@example.com",
            "password": "StrongPassword123!",
        },
    )

    response = client.post(
        "/api/auth/login",
        json={
            "email": "login@example.com",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_wrong_password_is_rejected(client: TestClient):
    client.post(
        "/api/auth/register",
        json={
            "email": "wrongpass@example.com",
            "password": "StrongPassword123!",
        },
    )

    response = client.post(
        "/api/auth/login",
        json={
            "email": "wrongpass@example.com",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401


def test_me_requires_authentication(client: TestClient):
    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_me_returns_authenticated_user(client: TestClient):
    client.post(
        "/api/auth/register",
        json={
            "email": "me@example.com",
            "password": "StrongPassword123!",
        },
    )

    login = client.post(
        "/api/auth/login",
        json={
            "email": "me@example.com",
            "password": "StrongPassword123!",
        },
    )

    token = login.json()["access_token"]

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"
    assert response.json()["role"] == "user"


def test_invalid_token_is_rejected(client: TestClient):
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401