from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import districts, rankings

app = FastAPI(title="Bharat Expansion Intelligence API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(districts.router)
app.include_router(rankings.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
