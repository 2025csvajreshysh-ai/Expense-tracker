import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Load environment variables from .env file if present
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEFAULT_SQLITE_PATH = Path(__file__).resolve().parent / "spendly.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")

# Fix postgres:// or postgresql:// prefix to use psycopg2 dialect
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)

# Handle special characters (like '@') in password automatically
if "://" in DATABASE_URL and DATABASE_URL.count("@") > 1:
    scheme, remainder = DATABASE_URL.split("://", 1)
    last_at = remainder.rfind("@")
    user_part = remainder[:last_at]
    host_part = remainder[last_at + 1:]
    if ":" in user_part:
        uname, pword = user_part.split(":", 1)
        pword_encoded = pword.replace("@", "%40")
        DATABASE_URL = f"{scheme}://{uname}:{pword_encoded}@{host_part}"

# SQLite requires check_same_thread=False, Postgres does not
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    # PostgreSQL / Supabase connection with pool keep-alive
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

