import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.connection import Base, engine
# Import all models so they register with Base.metadata
from database.models import User, Category, Expense, Budget


def init_database():
    """
    Creates all tables in the database schema without adding any demo data.
    """
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_database()
    print("Database tables initialized successfully (clean, no demo data).")

