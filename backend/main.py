import sys
from pathlib import Path

# Ensure project root is in sys.path regardless of working directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from contextlib import asynccontextmanager
from datetime import date as Date, datetime
from typing import Optional, List

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from database.connection import get_db
from database.models import User, Category, Expense, Budget
from database.init_db import init_database

try:
    from backend.schemas import (
        UserRegister,
        UserLogin,
        UserResponse,
        TokenResponse,
        CategoryCreate,
        CategoryResponse,
        ExpenseCreate,
        ExpenseUpdate,
        ExpenseResponse,
        BudgetCreate,
        BudgetResponse,
        SummaryResponse,
        TrendItem,
    )
    from backend.auth import (
        hash_password,
        verify_password,
        create_access_token,
        get_current_user,
    )
except ImportError:
    from schemas import (  # type: ignore
        UserRegister,
        UserLogin,
        UserResponse,
        TokenResponse,
        CategoryCreate,
        CategoryResponse,
        ExpenseCreate,
        ExpenseUpdate,
        ExpenseResponse,
        BudgetCreate,
        BudgetResponse,
        SummaryResponse,
        TrendItem,
    )
    from auth import (  # type: ignore
        hash_password,
        verify_password,
        create_access_token,
        get_current_user,
    )

BASE_DIR = PROJECT_ROOT
FRONTEND_DIR = BASE_DIR / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schema cleanly without demo data
    init_database()
    yield


app = FastAPI(title="Spendly API", version="2.0.0", lifespan=lifespan)

# Allow CORS for local dev / client flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Static Files & Frontend Serving
# ============================================================================
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def serve_index():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Spendly API is running. Frontend not found."}


@app.get("/home")
def serve_home():
    return serve_index()


# ============================================================================
# Authentication Endpoints (First step: Login / Sign In / Register)
# ============================================================================
@app.post("/api/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    username = payload.username.strip()
    email = payload.email.strip().lower()

    if db.query(User).filter(User.username.ilike(username)).first():
        raise HTTPException(status_code=400, detail="Username is already taken.")
    if db.query(User).filter(User.email.ilike(email)).first():
        raise HTTPException(status_code=400, detail="Email is already registered.")

    new_user = User(
        username=username,
        email=email,
        hashed_password=hash_password(payload.password)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Provide initial standard categories for this user (clean, 0 demo expenses)
    default_cats = ["Food", "Transport", "Shopping", "Bills", "Entertainment", "Health", "Others"]
    for c_name in default_cats:
        db.add(Category(user_id=new_user.id, name=c_name))
    db.commit()

    token = create_access_token(data={"sub": str(new_user.id), "username": new_user.username})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(new_user)
    )


@app.post("/api/auth/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    identifier = payload.username_or_email.strip()
    user = db.query(User).filter(
        or_(User.username.ilike(identifier), User.email.ilike(identifier))
    ).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(data={"sub": str(user.id), "username": user.username})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@app.get("/api/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


# ============================================================================
# Categories Endpoints (Scoped to authenticated user)
# ============================================================================
@app.get("/api/categories", response_model=List[CategoryResponse])
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Category).filter(Category.user_id == current_user.id).order_by(Category.name.asc()).all()


@app.post("/api/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def add_category(
    data: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Category name cannot be empty.")

    existing = db.query(Category).filter(
        Category.user_id == current_user.id,
        Category.name.ilike(name)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Category already exists.")

    item = Category(user_id=current_user.id, name=name)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.delete("/api/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    item = db.query(Category).filter(
        Category.id == category_id,
        Category.user_id == current_user.id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Category not found.")

    has_expenses = db.query(Expense).filter(
        Expense.user_id == current_user.id,
        Expense.category == item.name
    ).first()
    if has_expenses:
        raise HTTPException(
            status_code=409,
            detail="Move or delete expenses under this category before removing it."
        )

    budget = db.query(Budget).filter(
        Budget.user_id == current_user.id,
        Budget.category == item.name
    ).first()
    if budget:
        db.delete(budget)

    db.delete(item)
    db.commit()
    return None


# ============================================================================
# Expenses Endpoints (Scoped to authenticated user)
# ============================================================================
@app.get("/api/expenses", response_model=List[ExpenseResponse])
def list_expenses(
    category: str = "",
    start: Optional[Date] = None,
    end: Optional[Date] = None,
    q: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Expense).filter(Expense.user_id == current_user.id)

    if category:
        query = query.filter(Expense.category == category)
    if start:
        query = query.filter(Expense.date >= start)
    if end:
        query = query.filter(Expense.date <= end)
    if q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Expense.title.ilike(term),
                Expense.category.ilike(term),
                Expense.notes.ilike(term)
            )
        )

    return query.order_by(Expense.date.desc(), Expense.id.desc()).all()


@app.post("/api/expenses", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def add_expense(
    data: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cat = db.query(Category).filter(
        Category.user_id == current_user.id,
        Category.name == data.category
    ).first()
    if not cat:
        raise HTTPException(status_code=400, detail="Selected category does not exist.")

    title = data.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title cannot be empty.")

    item = Expense(
        user_id=current_user.id,
        title=title,
        amount=data.amount,
        category=data.category,
        date=data.date,
        notes=(data.notes or "").strip()
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.get("/api/expenses/{expense_id}", response_model=ExpenseResponse)
def get_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    item = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.user_id == current_user.id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Expense not found.")
    return item


@app.put("/api/expenses/{expense_id}", response_model=ExpenseResponse)
def update_expense(
    expense_id: int,
    data: ExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    item = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.user_id == current_user.id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Expense not found.")

    cat = db.query(Category).filter(
        Category.user_id == current_user.id,
        Category.name == data.category
    ).first()
    if not cat:
        raise HTTPException(status_code=400, detail="Selected category does not exist.")

    title = data.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title cannot be empty.")

    item.title = title
    item.amount = data.amount
    item.category = data.category
    item.date = data.date
    item.notes = (data.notes or "").strip()

    db.commit()
    db.refresh(item)
    return item


@app.delete("/api/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    item = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.user_id == current_user.id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Expense not found.")

    db.delete(item)
    db.commit()
    return None


# ============================================================================
# Budgets Endpoints (Scoped to authenticated user)
# ============================================================================
@app.get("/api/budgets", response_model=List[BudgetResponse])
def list_budgets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    budgets = db.query(Budget).filter(Budget.user_id == current_user.id).all()
    by_category = {b.category: b for b in budgets}

    today = Date.today()
    month_start = today.replace(day=1)

    month_expenses = db.query(Expense).filter(
        Expense.user_id == current_user.id,
        Expense.date >= month_start,
        Expense.date <= today
    ).all()

    spent: dict[str, float] = {}
    for exp in month_expenses:
        spent[exp.category] = spent.get(exp.category, 0.0) + exp.amount

    categories = db.query(Category).filter(Category.user_id == current_user.id).order_by(Category.name.asc()).all()

    res = []
    for c in categories:
        b = by_category.get(c.name)
        res.append(BudgetResponse(
            id=b.id if b else None,
            category=c.name,
            amount=round(b.amount, 2) if b else 0.0,
            spent=round(spent.get(c.name, 0.0), 2)
        ))
    return res


@app.put("/api/budgets/{category}", response_model=BudgetResponse)
def save_budget(
    category: str,
    data: BudgetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if category != data.category:
        raise HTTPException(status_code=400, detail="Category name mismatch.")

    cat = db.query(Category).filter(
        Category.user_id == current_user.id,
        Category.name == category
    ).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category does not exist.")

    budget = db.query(Budget).filter(
        Budget.user_id == current_user.id,
        Budget.category == category
    ).first()

    if budget:
        budget.amount = data.amount
    else:
        budget = Budget(user_id=current_user.id, category=category, amount=data.amount)
        db.add(budget)

    db.commit()
    db.refresh(budget)

    # Calculate current month spent for response
    today = Date.today()
    month_start = today.replace(day=1)
    month_spent = db.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id,
        Expense.category == category,
        Expense.date >= month_start,
        Expense.date <= today
    ).scalar() or 0.0

    return BudgetResponse(
        id=budget.id,
        category=budget.category,
        amount=budget.amount,
        spent=round(month_spent, 2)
    )


# ============================================================================
# Summary / Analytics Endpoint (Scoped to authenticated user)
# ============================================================================
@app.get("/api/summary", response_model=SummaryResponse)
def summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    today = Date.today()
    month_start = today.replace(day=1)

    expenses = db.query(Expense).filter(Expense.user_id == current_user.id).all()
    budgets = db.query(Budget).filter(Budget.user_id == current_user.id).all()

    month_total = sum(e.amount for e in expenses if e.date >= month_start and e.date <= today)
    budget_total = sum(b.amount for b in budgets)

    by_category: dict[str, float] = {}
    for e in expenses:
        by_category[e.category] = round(by_category.get(e.category, 0.0) + e.amount, 2)

    # 12-month trend
    months = []
    year, month = today.year, today.month
    for _ in range(12):
        months.append((year, month))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    months.reverse()

    trend = [
        TrendItem(
            label=datetime(y, m, 1).strftime("%b %Y"),
            total=round(sum(e.amount for e in expenses if e.date.year == y and e.date.month == m), 2)
        )
        for y, m in months
    ]

    cat_count = db.query(Category).filter(Category.user_id == current_user.id).count()

    return SummaryResponse(
        month_total=round(month_total, 2),
        budget_total=round(budget_total, 2),
        remaining=round(budget_total - month_total, 2),
        category_count=cat_count,
        expense_count=len(expenses),
        by_category=by_category,
        trend=trend
    )


# ============================================================================
# Health Check Endpoint
# ============================================================================
@app.get("/api/health")
def health():
    return {"status": "ok", "service": "Spendly API", "version": "2.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

