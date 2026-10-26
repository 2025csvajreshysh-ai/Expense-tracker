from contextlib import asynccontextmanager
from datetime import date as Date, datetime
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Field, Session, SQLModel, create_engine, select

BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = f"sqlite:///{BASE_DIR / 'spendly.db'}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class Category(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True, min_length=1, max_length=40)


class Expense(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0)
    category: str = Field(index=True, max_length=40)
    date: Date = Field(index=True)
    notes: str = Field(default="", max_length=500)


class Budget(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    category: str = Field(index=True, unique=True, max_length=40)
    amount: float = Field(gt=0)


class CategoryInput(SQLModel):
    name: str = Field(min_length=1, max_length=40)


class ExpenseInput(SQLModel):
    title: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0)
    category: str = Field(min_length=1, max_length=40)
    date: Date
    notes: str = Field(default="", max_length=500)


class BudgetInput(SQLModel):
    category: str = Field(min_length=1, max_length=40)
    amount: float = Field(gt=0)


DEFAULT_CATEGORIES = ["Food", "Transport", "Shopping", "Bills", "Entertainment", "Others", "rent"]
DEFAULT_BUDGETS = {"Food": 8000, "Transport": 3000, "Shopping": 3000, "Bills": 4000,
                   "Entertainment": 2000, "Others": 1000, "rent": 2000}


def seed_database():
    with Session(engine) as session:
        if session.exec(select(Category)).first() is not None:
            return
        for name in DEFAULT_CATEGORIES:
            session.add(Category(name=name))
        for category, amount in DEFAULT_BUDGETS.items():
            session.add(Budget(category=category, amount=amount))
        sample = [
            ("Room", 1000, "rent", "2026-10-03", ""),
            ("foooood", 1000, "Food", "2026-10-03", ""),
            ("foood", 1000, "Food", "2026-10-03", ""),
            ("Lunch", 350, "Food", "2026-10-02", "With friends"),
            ("Bus Pass", 500, "Transport", "2026-10-01", ""),
            ("T-shirt", 1200, "Shopping", "2026-09-29", ""),
            ("Electricity Bill", 1000, "Bills", "2026-09-29", ""),
            ("Movie", 300, "Entertainment", "2026-09-25", ""),
        ]
        for title, amount, category, spent_on, notes in sample:
            session.add(Expense(title=title, amount=amount, category=category, date=Date.fromisoformat(spent_on), notes=notes))
        session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    seed_database()
    yield


app = FastAPI(title="Spendly", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


def get_session():
    with Session(engine) as session:
        yield session


@app.get("/")
def home():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/categories", response_model=list[Category])
def list_categories(session: Session = Depends(get_session)):
    return session.exec(select(Category).order_by(Category.name)).all()


@app.post("/api/categories", response_model=Category, status_code=201)
def add_category(data: CategoryInput, session: Session = Depends(get_session)):
    name = data.name.strip()
    if not name:
        raise HTTPException(400, "Enter a category name.")
    if session.exec(select(Category).where(Category.name.ilike(name))).first():
        raise HTTPException(409, "That category already exists.")
    item = Category(name=name)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@app.delete("/api/categories/{category_id}", status_code=204)
def remove_category(category_id: int, session: Session = Depends(get_session)):
    item = session.get(Category, category_id)
    if not item:
        raise HTTPException(404, "Category not found.")
    if session.exec(select(Expense).where(Expense.category == item.name)).first():
        raise HTTPException(409, "Move or remove this category's expenses before deleting it.")
    budget = session.exec(select(Budget).where(Budget.category == item.name)).first()
    if budget:
        session.delete(budget)
    session.delete(item)
    session.commit()


@app.get("/api/expenses", response_model=list[Expense])
def list_expenses(category: str = "", start: Optional[Date] = None, end: Optional[Date] = None,
                  q: str = "", session: Session = Depends(get_session)):
    statement = select(Expense)
    if category:
        statement = statement.where(Expense.category == category)
    if start:
        statement = statement.where(Expense.date >= start)
    if end:
        statement = statement.where(Expense.date <= end)
    if q.strip():
        term = f"%{q.strip()}%"
        statement = statement.where((Expense.title.ilike(term)) | (Expense.category.ilike(term)) | (Expense.notes.ilike(term)))
    return session.exec(statement.order_by(Expense.date.desc(), Expense.id.desc())).all()


@app.post("/api/expenses", response_model=Expense, status_code=201)
def add_expense(data: ExpenseInput, session: Session = Depends(get_session)):
    if not session.exec(select(Category).where(Category.name == data.category)).first():
        raise HTTPException(400, "Choose an existing category.")
    values = data.model_dump()
    values["title"] = data.title.strip()
    item = Expense(**values)
    if not item.title:
        raise HTTPException(400, "Enter a title.")
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@app.get("/api/expenses/{expense_id}", response_model=Expense)
def get_expense(expense_id: int, session: Session = Depends(get_session)):
    item = session.get(Expense, expense_id)
    if not item:
        raise HTTPException(404, "Expense not found.")
    return item


@app.put("/api/expenses/{expense_id}", response_model=Expense)
def update_expense(expense_id: int, data: ExpenseInput, session: Session = Depends(get_session)):
    item = session.get(Expense, expense_id)
    if not item:
        raise HTTPException(404, "Expense not found.")
    if not session.exec(select(Category).where(Category.name == data.category)).first():
        raise HTTPException(400, "Choose an existing category.")
    if not data.title.strip():
        raise HTTPException(400, "Enter a title.")
    for key, value in data.model_dump().items():
        setattr(item, key, value.strip() if key == "title" else value)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@app.delete("/api/expenses/{expense_id}", status_code=204)
def delete_expense(expense_id: int, session: Session = Depends(get_session)):
    item = session.get(Expense, expense_id)
    if not item:
        raise HTTPException(404, "Expense not found.")
    session.delete(item)
    session.commit()


@app.get("/api/budgets")
def list_budgets(session: Session = Depends(get_session)):
    budgets = session.exec(select(Budget).order_by(Budget.category)).all()
    by_category = {b.category: b for b in budgets}
    month_start = Date.today().replace(day=1)
    spent: dict[str, float] = {}
    for expense in session.exec(select(Expense).where(Expense.date >= month_start)).all():
        spent[expense.category] = spent.get(expense.category, 0) + expense.amount
    categories = session.exec(select(Category).order_by(Category.name)).all()
    return [{"id": by_category[c.name].id if c.name in by_category else None,
             "category": c.name,
             "amount": by_category[c.name].amount if c.name in by_category else 0,
             "spent": round(spent.get(c.name, 0), 2)} for c in categories]


@app.put("/api/budgets/{category}")
def save_budget(category: str, data: BudgetInput, session: Session = Depends(get_session)):
    if category != data.category:
        raise HTTPException(400, "Category mismatch.")
    if not session.exec(select(Category).where(Category.name == category)).first():
        raise HTTPException(404, "Category not found.")
    budget = session.exec(select(Budget).where(Budget.category == category)).first()
    if budget:
        budget.amount = data.amount
    else:
        budget = Budget(category=category, amount=data.amount)
    session.add(budget)
    session.commit()
    return {"category": budget.category, "amount": budget.amount}


@app.get("/api/summary")
def summary(session: Session = Depends(get_session)):
    today = Date.today()
    month_start = today.replace(day=1)
    expenses = session.exec(select(Expense)).all()
    budgets = session.exec(select(Budget)).all()
    total = sum(e.amount for e in expenses if e.date >= month_start and e.date <= today)
    budget_total = sum(b.amount for b in budgets)
    by_category = {}
    for expense in expenses:
        by_category[expense.category] = by_category.get(expense.category, 0) + expense.amount
    months = []
    year, month = today.year, today.month
    for _ in range(12):
        months.append((year, month))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    months.reverse()
    trend = [{"label": datetime(y, m, 1).strftime("%b %Y"), "total": round(sum(
        e.amount for e in expenses if e.date.year == y and e.date.month == m), 2)} for y, m in months]
    return {"month_total": round(total, 2), "budget_total": round(budget_total, 2),
            "remaining": round(budget_total - total, 2), "category_count": len(session.exec(select(Category)).all()),
            "expense_count": len(expenses), "by_category": by_category, "trend": trend}


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "Spendly"}

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/home")
def home():
    return FileResponse("/static/index.html")
