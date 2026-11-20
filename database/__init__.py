from .connection import Base, engine, get_db, SessionLocal
from .models import User, Category, Expense, Budget


def init_database():
    """Creates all database tables defined in models."""
    Base.metadata.create_all(bind=engine)


__all__ = [
    "Base",
    "engine",
    "get_db",
    "SessionLocal",
    "User",
    "Category",
    "Expense",
    "Budget",
    "init_database",
]

