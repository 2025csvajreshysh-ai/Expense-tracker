from datetime import datetime, date as Date
from sqlalchemy import Column, Integer, String, Float, Date as SqlDate, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from .connection import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    categories = relationship("Category", back_populates="user", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="user", cascade="all, delete-orphan")
    budgets = relationship("Budget", back_populates="user", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name = Column(String(50), nullable=False)

    user = relationship("User", back_populates="categories")

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uix_user_category_name"),
    )


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title = Column(String(120), nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String(50), nullable=False, index=True)
    date = Column(SqlDate, nullable=False, index=True)
    notes = Column(String(500), default="", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="expenses")


class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    category = Column(String(50), nullable=False, index=True)
    amount = Column(Float, nullable=False)

    user = relationship("User", back_populates="budgets")

    __table_args__ = (
        UniqueConstraint("user_id", "category", name="uix_user_budget_category"),
    )
