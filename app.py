"""
Spendly - Main application runner
Re-exports the FastAPI app from backend.main for standard uvicorn/deployment workflows.
"""
import uvicorn
from backend.main import app

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
