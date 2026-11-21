from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import admin, albums, entities, health

app = FastAPI(title="Album Deep-Dive API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_methods=["GET", "PATCH", "POST"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(albums.router)
app.include_router(entities.router)
app.include_router(admin.router)
