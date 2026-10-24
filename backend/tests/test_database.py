from app.database import check_db_connection


def test_database_connection():
    assert check_db_connection() is True