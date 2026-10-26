# Spendly

A personal expense and budget tracker built with FastAPI, SQLModel, SQLite, and plain HTML, CSS, and JavaScript.

## Run locally

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py -m uvicorn app:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The SQLite database (`spendly.db`) is created beside `app.py` on first launch and populated with the example transactions and budgets shown in the reference video. The JSON API is available under `/api`; FastAPI's interactive docs are at `/docs`.

## Features

- Dashboard with monthly totals, category spending, and a 12-month trend.
- Expense creation, editing, deletion, text search, category and date filters.
- Category creation and deletion, with a safeguard for categories that still have expenses.
- Monthly budgets with spent versus limit progress.
- Category and month reports, INR formatting, and a persistent light theme.
- Responsive layout for desktop and mobile.
