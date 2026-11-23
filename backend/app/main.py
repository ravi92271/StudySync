from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .api import router
from .db import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()  # creates backend/data/, the uploads folder and the SQLite tables
    yield


app = FastAPI(title="StudySync", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {"message": "Hello World"}
