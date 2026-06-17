from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import hotspots, analytics

app = FastAPI(
    title="Parking Intelligence API",
    description="Bengaluru illegal-parking hotspot intelligence — PS1 hackathon prototype.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for production
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(hotspots.router)
app.include_router(analytics.router)


@app.get("/health")
def health():
    return {"status": "ok"}
