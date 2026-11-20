from datetime import date as Date, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field


# ===================== Auth Schemas =====================
class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class UserLogin(BaseModel):
    username_or_email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ===================== Category Schemas =====================
class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)


class CategoryResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


# ===================== Expense Schemas =====================
class ExpenseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    amount: float = Field(..., gt=0)
    category: str = Field(..., min_length=1, max_length=50)
    date: Date
    notes: Optional[str] = Field(default="", max_length=500)


class ExpenseUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    amount: float = Field(..., gt=0)
    category: str = Field(..., min_length=1, max_length=50)
    date: Date
    notes: Optional[str] = Field(default="", max_length=500)


class ExpenseResponse(BaseModel):
    id: int
    title: str
    amount: float
    category: str
    date: Date
    notes: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ===================== Budget Schemas =====================
class BudgetCreate(BaseModel):
    category: str = Field(..., min_length=1, max_length=50)
    amount: float = Field(..., gt=0)


class BudgetResponse(BaseModel):
    id: Optional[int] = None
    category: str
    amount: float
    spent: float = 0.0

    class Config:
        from_attributes = True


# ===================== Summary Schemas =====================
class TrendItem(BaseModel):
    label: str
    total: float


class SummaryResponse(BaseModel):
    month_total: float
    budget_total: float
    remaining: float
    category_count: int
    expense_count: int
    by_category: Dict[str, float]
    trend: List[TrendItem]
