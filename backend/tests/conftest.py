"""Shared pytest fixtures.

db_conn: a real connection to the project's Postgres instance, wrapped in a
transaction that is always rolled back at teardown — never committed. This
project has no separate provisioned test database, so tests that need real
SQL behaviour (pg_trgm similarity, actual constraint enforcement) run
against the same instance the app uses, but never persist anything: no test
row survives past the test that created it, and no test ever calls
conn.commit(). Fixture data uses an obviously-fake state, "TESTLAND", per
CLAUDE.md's own rule ("Test fixtures ... must be obviously fake").
"""

import psycopg
import pytest
from app.config import settings


@pytest.fixture
def db_conn():
    conn = psycopg.connect(settings.database_url.replace("+psycopg", ""))
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()
