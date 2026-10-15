from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.routes import (
    admin_ops_router,
    admin_router,
    auth_router,
    gameplay_router,
    user_router,
)
from app import SETTINGS
import uvicorn




app = FastAPI()
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(gameplay_router)
app.include_router(admin_router)
app.include_router(admin_ops_router)
app.mount(
    "/uploads",
    StaticFiles(directory=Path(__file__).resolve().parent / "uploads", check_dir=False),
    name="uploads",
)


origins = SETTINGS.frontend_url.split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
