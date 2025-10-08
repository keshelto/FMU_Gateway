import os
from pathlib import Path
from sqlalchemy import create_engine, Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime


# Database configuration ----------------------------------------------------
#
# The production deployment uses Postgres, but during local development agents
# may not have a database provisioned.  Previously this resulted in an
# exception during import which prevented the API from starting.  To make the
# gateway usable out-of-the-box we provide a deterministic SQLite fallback that
# mirrors the production schema.  The location can be overridden with the
# ``FMU_GATEWAY_DB_PATH`` environment variable for sandbox testing.

DATABASE_URL = os.getenv('DATABASE_URL')
connect_args = {}

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def _resolve_sqlite_url() -> tuple[str, dict]:
    """Return a SQLite connection string that is always writable.

    When the managed Postgres instance has been decommissioned we want the
    gateway to continue operating with zero configuration.  We attempt sensible
    defaults that work both locally and on Fly.io:

    1. An explicit ``FMU_GATEWAY_DB_PATH`` override (useful for tests).
    2. ``/data`` which is the conventional persistent volume mount on Fly.
    3. A repository-local ``local.db`` as a final fallback.
    """

    candidates = []

    override = os.getenv("FMU_GATEWAY_DB_PATH")
    if override:
        candidates.append(Path(override))

    # Fly.io persistent volumes are mounted at /data by convention.  Use a
    # descriptive filename so multiple apps can coexist if needed.
    candidates.append(Path("/data/fmu_gateway.sqlite3"))

    # Final fallback lives alongside the source tree for local development.
    candidates.append(Path(__file__).resolve().parent.parent / "local.db")

    for path in candidates:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8"):
                pass
            return f"sqlite:///{path}", {"check_same_thread": False}
        except OSError:
            continue
        except IOError:
            continue

    raise RuntimeError("Unable to determine a writable location for SQLite fallback")

if not DATABASE_URL:
    DATABASE_URL, connect_args = _resolve_sqlite_url()

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ApiKey(Base):
    __tablename__ = "api_keys"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(36), unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    stripe_customer_id = Column(String(255), nullable=True)

class Usage(Base):
    __tablename__ = "usage"
    id = Column(Integer, primary_key=True, index=True)
    api_key_id = Column(Integer, ForeignKey("api_keys.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    fmu_id = Column(String(255))
    duration_ms = Column(Integer)  # simulation duration in ms
