import os


os.environ.setdefault("ENV_FOR_DYNACONF", "testing")
os.environ.setdefault("PODIUM_DATABASE_URL", "postgresql+asyncpg://postgres:test@localhost/test?sslmode=disable")
os.environ.setdefault("PODIUM_JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("PODIUM_LOOPS_TRANSACTIONAL_ID", "test-transaction")
os.environ.setdefault("PODIUM_ACTIVE_EVENT_SERIES", "test-series")
